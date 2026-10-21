"""Camera-independent, measured-feedback mission. No simulator or actuator I/O.

The caller owns a complete task list, collision supervision and box sensing.
Targets are never inferred complete from missing detections. Policy commands
and motion commands require actual acknowledgement. No reset is a return.
"""
from dataclasses import dataclass
import numpy as np
from .student60 import encode_command, decode_command


@dataclass(frozen=True)
class HarvestTarget:
    target_id: str
    label: str
    anchor_arm_m: tuple


class StudentHarvestMission:
    def __init__(self, session, targets, config, return_path, *, task_list_complete,
                 recover_harvest_timeout=False):
        if not task_list_complete or not targets:
            raise ValueError('A nonempty, explicitly complete assigned target list is required')
        self.targets = list(targets)
        if (len({t.target_id for t in targets}) != len(targets) or
                any(not t.target_id or t.label not in ('Red', 'Yellow') or
                    np.asarray(t.anchor_arm_m).shape != (3,) or
                    not np.isfinite(t.anchor_arm_m).all() for t in targets)):
            raise ValueError('Unique ripe IDs and camera-observed finite anchors required')
        self.session, self.config, self.return_path = session, dict(config), return_path
        self.contract = session.contract
        # Gravity-aligned task/world Z, not detector confidence order or the
        # possibly tilted camera/arm optical Z. Coordinates come from vision.
        frame = np.asarray(self.contract['box_from_arm'], dtype=float)
        if (frame.shape != (4,4) or not np.isfinite(frame).all() or
                not np.allclose(frame[3],[0,0,0,1])):
            raise ValueError('Require gravity-aligned task frame for lowest-first ordering')
        self.target_heights = {t.target_id: float((frame @ np.r_[t.anchor_arm_m,1.])[2]) for t in targets}
        self.targets.sort(key=lambda t:(self.target_heights[t.target_id], t.target_id))
        self.lower = np.asarray(self.contract['lower_rad'])
        self.upper = np.asarray(self.contract['upper_rad'])
        self.home = self._pose(config['home_rad']); self.stow = self._pose(config['stow_rad'])
        self.via = [self._pose(v) for v in config['home_to_stow_via_rad']]
        for key in ('speed_rad_s', 'max_command_lead_rad', 'position_tolerance_rad',
                    'stop_speed_rad_s', 'settle_s', 'waypoint_timeout_s',
                    'harvest_timeout_s', 'joint_ttl_s', 'box_evidence_ttl_s'):
            if not np.isfinite(config[key]) or config[key] <= 0:
                raise ValueError('Positive finite motion setting required: ' + key)
        self.state = 'STOW_WAIT'; self.index = 0; self.harvested = []
        self.events = []; self.failure = None; self.pending = None
        self.last_time = None; self.stable = 0.; self.previous = None
        self.phase_start = None; self.path = []; self.path_index = 0
        self.last_measured_q = None; self.measured_speed = float('inf')
        self.motion_bias = np.zeros(6)
        # 농장 sim만 선택한다. 수확 시간초과는 측정 복귀 후 호출자가 재관측한다.
        self.recover_harvest_timeout = recover_harvest_timeout
        self.harvest_timed_out = False

    def _pose(self, values):
        q = np.asarray(values, dtype=float)
        if q.shape != (6,) or not np.isfinite(q).all() or np.any(q < self.lower) or np.any(q > self.upper):
            raise ValueError('Pose outside original joint limits')
        return q.copy()

    @property
    def target(self):
        return self.targets[self.index]

    def _enter(self, state, now):
        self.state, self.phase_start, self.stable = state, now, 0.
        self.events.append(dict(state=state, stamp_s=now, target_id=self.target.target_id))

    def _route(self, poses, state, now):
        self.path = [self._pose(q) for q in poses]
        if not self.path:
            raise ValueError('Empty motion route')
        self.path_index = 0; self._enter(state, now)
        self.motion_bias[:] = 0.

    def _settled(self, q, qd, goal, dt):
        good = (np.max(abs(q-goal)) <= self.config['position_tolerance_rad'] and
                self.measured_speed <= self.config['stop_speed_rad_s'] and
                np.max(abs(qd)) <= self.config['instantaneous_speed_limit_rad_s'])
        self.stable = self.stable + dt if good else 0.
        return self.stable >= self.config['settle_s'] - 1e-8

    def _move(self, q, goal, dt):
        # Integrate the actually acknowledged goal, bounded near measured q.
        lead = self.config['max_command_lead_rad']
        # Bounded compensation of gravity tracking error. Measured pose, not
        # command arrival, still gates completion. Original drive gains stay.
        if self.state in ('TO_HOME','RETURN_STOW'):
            self.motion_bias = np.clip(self.motion_bias+.5*(goal-q)*dt,-.06,.06)
        else:
            self.motion_bias[:] = 0.
        desired = np.clip(goal+self.motion_bias, q-lead, q+lead)
        delta = np.clip(desired-self.previous, -self.config['speed_rad_s']*dt,
                        self.config['speed_rad_s']*dt)
        return encode_command(np.clip(self.previous+delta, self.lower, self.upper),
                              [1., .3], self.lower, self.upper)

    def tick(self, now, q, qd, joint_stamp_s, capture=None, *, box_evidence=None, fault=''):
        if self.pending is not None:
            raise ValueError('Acknowledge the applied command before the next tick')
        q, qd = np.asarray(q, float), np.asarray(qd, float)
        if (q.shape != (6,) or qd.shape != (6,) or not np.isfinite(np.r_[q, qd, now, joint_stamp_s]).all()):
            raise ValueError('Finite measured joint feedback required')
        if self.last_time is not None and abs(now-self.last_time-.05) > 1e-6:
            raise ValueError('This version retains sequential 20Hz simulation control')
        dt = .05; self.last_time = now
        self.measured_speed = (float('inf') if self.last_measured_q is None else
                               float(np.max(abs(q-self.last_measured_q))/.05))
        self.last_measured_q = q.copy()
        if self.previous is None: self.previous = q.copy()
        if self.phase_start is None: self.phase_start = now
        if not 0 <= now-joint_stamp_s <= self.config['joint_ttl_s']:
            fault = 'stale_joint_feedback'
        if fault and self.state not in ('FAILED', 'STOPPING'):
            self.failure = fault; self.stop_goal = q.copy(); self._enter('STOPPING', now)
        if self.state == 'DONE':
            # Completion is not a license to stop monitoring the physical arm.
            if (np.max(abs(q-self.stow)) > self.config['position_tolerance_rad'] or
                    self.measured_speed > self.config['stop_speed_rad_s'] or
                    np.max(abs(qd)) > self.config['instantaneous_speed_limit_rad_s']):
                self.failure = 'lost_final_stow'; self.stop_goal = q.copy(); self._enter('STOPPING', now)
        if self.state in ('STOW_WAIT', 'FINAL_STOP'):
            if self._settled(q, qd, self.stow, dt):
                if self.state == 'FINAL_STOP': self._enter('DONE', now)
                else: self._route(list(reversed(self.via))+[self.home], 'TO_HOME', now)
            elif now-self.phase_start > self.config['waypoint_timeout_s']:
                return self._fail(now, q, 'initial_or_final_stow_not_confirmed')
            # Initial STOW_WAIT verifies the initial pose; never moves from an
            # unknown arbitrary posture along an unplanned shortcut.
            if self.state == 'STOW_WAIT' and np.max(abs(q-self.stow)) > .10:
                return self._fail(now, q, 'start_requires_stowed_pose')
        if self.state in ('TO_HOME', 'RETURN_STOW'):
            goal = self.path[self.path_index]
            if self._settled(q, qd, goal, dt):
                self.path_index += 1; self.stable = 0.; self.phase_start = now
                self.motion_bias[:] = 0.
                if self.path_index == len(self.path):
                    if self.state == 'TO_HOME':
                        self.session.start(self.target, self.previous.copy())
                        self.harvest_start = now; self._enter('HARVEST', now)
                    elif self.harvest_timed_out or len(self.harvested) == len(self.targets): self._enter('FINAL_STOP', now)
                    else:
                        self.index += 1; self._enter('STOW_WAIT', now)
                else: goal = self.path[self.path_index]
            elif now-self.phase_start > self.config['waypoint_timeout_s']:
                return self._fail(now, q, 'motion_tracking_timeout')
            if self.state in ('TO_HOME', 'RETURN_STOW'):
                return self._issued(self._move(q, goal, dt), False)
        if self.state in ('HARVEST', 'WAIT_BOX'):
            if box_evidence is not None:
                e = box_evidence
                if (e.get('target_id') != self.target.target_id or not e.get('settled') or
                        not np.isfinite(e.get('stamp_s', float('nan'))) or
                        not self.harvest_start <= e['stamp_s'] <= now or
                        now-e['stamp_s'] > self.config['box_evidence_ttl_s']):
                    return self._fail(now, q, 'invalid_box_confirmation')
                self.harvested.append(self.target.target_id)
                self.events.append(dict(state='BOX_CONFIRMED', target_id=self.target.target_id, stamp_s=now,
                                        evidence_source=e.get('source', 'unspecified')))
                try:
                    route = self.return_path(q.copy(), self.home.copy())
                    self._route(list(route)+self.via+[self.stow], 'RETURN_STOW', now)
                except (ValueError, RuntimeError) as error:
                    return self._fail(now, q, 'return_path_rejected: '+str(error))
                return self._issued(self._move(q, self.path[0], dt), False)
            if now-self.harvest_start >= self.config['harvest_timeout_s']:
                return self._fail(now, q, 'harvest_or_box_timeout')
            command, note = self.session.step(capture, q, qd, now)
            if note.get('release_latched') and self.state == 'HARVEST': self._enter('WAIT_BOX', now)
            return self._issued(command, True, note)
        if self.state == 'STOPPING':
            if self._settled(q, qd, self.stop_goal, dt): self._enter('FAILED', now)
        goal = self.stop_goal if self.state in ('STOPPING', 'FAILED') else self.stow
        return self._issued(self._move(q, goal, dt), False)

    def _fail(self, now, q, reason):
        if reason == 'harvest_or_box_timeout' and self.recover_harvest_timeout:
            self.harvest_timed_out = True
            self.events.append(dict(state='HARVEST_TIMEOUT', stamp_s=now,
                                    target_id=self.target.target_id))
            try:
                route = self.return_path(q.copy(), self.home.copy())
                self._route(list(route)+self.via+[self.stow], 'RETURN_STOW', now)
                return self._issued(self._move(q, self.path[0], .05), False)
            except (ValueError, RuntimeError) as error:
                reason = 'return_path_rejected: '+str(error)
        self.failure = reason; self.stop_goal = q.copy(); self._enter('STOPPING', now)
        return self._issued(encode_command(q, [1., .3], self.lower, self.upper), False)

    def _issued(self, command, policy, note=None):
        decode_command(command, self.lower, self.upper)
        self.pending = dict(command=np.asarray(command).copy(), policy=policy)
        return command, dict(state=self.state, target_id=self.target.target_id,
                             harvested=list(self.harvested), failure=self.failure, policy_note=note)

    def acknowledge(self, actual_command):
        if self.pending is None: raise ValueError('No outstanding command')
        q, _ = decode_command(actual_command, self.lower, self.upper)
        if self.pending['policy']: self.session.acknowledge(actual_command)
        self.previous = q.copy(); self.pending = None

    def report(self):
        return dict(state=self.state, mission_complete=self.state == 'DONE',
                    target_priority='lowest_camera_observed_world_height_first',
                    ordered_target_ids=[t.target_id for t in self.targets],
                    observed_target_heights_m=self.target_heights,
                    harvest_successes=len(self.harvested), planned_targets=len(self.targets),
                    harvested_ids=list(self.harvested), failure=self.failure, events=self.events,
                    harvest_timed_out=self.harvest_timed_out)
