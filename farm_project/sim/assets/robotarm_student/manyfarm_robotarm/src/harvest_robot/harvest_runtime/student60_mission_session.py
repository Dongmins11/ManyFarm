"""D435 and U20 camera adapters for the same explicit multi-target mission.

U20 uses its own RGB-only weights/packing; no synthetic IR or D435 center model.
An assignment anchor is an earlier camera observation, never simulator truth.
"""
from pathlib import Path
import numpy as np
from .student60_controller import Student60Controller
from .student60 import TargetFilter


class U20Controller(Student60Controller):
    def __init__(self, checkpoint, contract, device='cpu'):
        from harvest_rl.student60_u20_model import U20Inference
        self.policy = U20Inference(checkpoint, contract, device)
        self.contract = contract
        self.target_filter = TargetFilter(contract['box_from_arm'], contract['box_min'], contract['box_max'])
        self.target_id = None; self.pending = False

    def step(self, frames, q_rad, qd_rad_s, tcp_arm, target, now, capture):
        from harvest_rl.student_v2 import measured_proprio
        from harvest_sensors.u20_deployment import pack_observation
        if self.pending or target['target_id'] != self.target_id:
            raise ValueError('Require matching assignment and previous applied-command acknowledgement')
        if self.last_stamp is not None and abs(now-self.last_stamp-.05) > 1e-6:
            raise ValueError('Require sequential 20Hz')
        filtered = self.target_filter.filter(target)
        proprio = measured_proprio(q_rad, qd_rad_s, self.previous, self.contract['lower_rad'], self.contract['upper_rad'])
        observation = pack_observation(frames, proprio, tcp_arm, filtered, now, capture)
        command = self.policy.predict(observation, self.target_id)
        self.pending = True; self.tcp = np.asarray(tcp_arm).copy(); self.last_stamp = now
        self.measured_jaw = float(q_rad[-1])
        return command, dict(target=filtered, release_latched=self.target_filter.released)


def select_anchored_track(snapshot, target, gate=.04, ambiguity_margin=.02):
    distances = sorted((float(np.linalg.norm(np.asarray(t['position_m'])-target.anchor_arm_m)), key)
                       for key, t in snapshot.items() if t['valid'] and t['label'] == target.label)
    if not distances or distances[0][0] > gate: return None
    if len(distances) > 1 and distances[1][0]-distances[0][0] < ambiguity_margin: return None
    return distances[0][1]


class MissionCameraSession:
    def __init__(self, checkpoint, contract, detector, kin, world_from_robot, *,
                 camera_kind='d435', center_checkpoint=None, device='cpu'):
        from .student60_camera_controller import make_controller
        from .student60_faster_capture import FasterCaptureCameraHarvestController
        from harvest_vision.workspace import load_workspace
        self.contract = contract; self.kin = kin; self.detector = detector
        self.camera_kind = camera_kind; self.roi, _ = load_workspace()
        base = kin.fk(np.zeros(6), 'arm_2/base_link')
        self.arm_from_robot = np.linalg.inv(base)
        self.arm_from_world = np.linalg.inv(np.asarray(world_from_robot) @ base)
        if camera_kind == 'u20':
            if center_checkpoint is not None: raise ValueError('D435 center model is not a U20 calibration')
            self.core = U20Controller(checkpoint, contract, device)
        elif camera_kind == 'd435': self.core = make_controller(checkpoint, contract, device)
        else: raise ValueError('Unknown camera family')
        self.controller = FasterCaptureCameraHarvestController(self.core, kin, contract, body_center=False, entry_jaw_gate=True)
        self.center = None
        if center_checkpoint:
            from harvest_vision.student60_camera_center import CenterCorrector
            self.center = CenterCorrector(Path(center_checkpoint))
        self.target = None

    def observe(self, capture, now):
        from harvest_vision.geometry import Frame
        from harvest_sensors.student60_native_fast import process_native
        frames = {name: Frame(d['rgb'], d['aligned_depth_m'], d['intrinsics']['rgb'],
                  self.arm_from_world @ d['world_from_optical']['rgb'], d['stamp_s'], d['pose_stamp_s'], name)
                  for name, d in capture.items()}
        detections, _ = process_native(frames['rear'], capture['rear'], self.detector, now,
                                      self.contract['centre_offset_m'], arm_roi=self.roi if self.target is None or self.tracker.selected is None else None)
        return frames, detections

    def start(self, target, initial_applied_joint_goals_rad):
        from harvest_vision.student60_tracking import AssignedFruitTracker
        if self.core.pending: raise ValueError('Outstanding command before target switch')
        self.target = target; self.tracker = AssignedFruitTracker(self.roi)
        self.time_origin = None
        self.controller.start(target.target_id, initial_applied_joint_goals_rad)

    def step(self, capture, q, qd, now):
        from harvest_vision.student60_camera_center import selected_record
        if self.target is None or self.core.pending: raise ValueError('Assign and acknowledge before inference')
        if self.time_origin is None: self.time_origin = now
        # Rebase all timestamps together for the trained per-target elapsed
        # feature. Original captures are untouched and their age is preserved.
        capture = {name: dict(d, stamp_s=d['stamp_s']-self.time_origin,
                   pose_stamp_s=d['pose_stamp_s']-self.time_origin) for name, d in capture.items()}
        now -= self.time_origin
        frames, detections = self.observe(capture, now)
        self.tracker.update(detections, now)
        if self.tracker.selected is None:
            key = select_anchored_track(self.tracker.snapshot(now), self.target)
            if key is not None: self.tracker.assign(now, key)
        target = dict(self.tracker.observation(now), target_id=self.target.target_id)
        filtered = self.core.target_filter.filter(target)
        observed = selected_record(filtered['position_m'], detections) if filtered['valid'] else None
        assigned = observed if (observed is not None and
            np.linalg.norm(np.asarray(observed['grasp_estimate_arm_m'])-filtered['position_m']) < 1e-7 and
            abs(now-filtered['age_s']-observed['stamp_s']) < 1e-7) else None
        if observed is not None and self.center is not None:
            corrected, _ = self.center.predict(None, filtered['position_m'], observed)
            target = dict(target, position_m=corrected.tolist())
        tcp = (self.arm_from_robot @ self.kin.grasp_fk(q, self.contract['task']['diameter']))[:3, 3]
        return self.controller.step(frames, q, qd, tcp, target, now,
            dict(capture, student_target_detections=detections, student_assigned_detection=assigned))

    def acknowledge(self, command): self.controller.acknowledge(command)


def lifted_return_path(kin, contract, config, current, home):
    """Public FK + known tray geometry; lift clear before HOME and stow.

Sampled kinematic path is a candidate, not an exact mesh collision certificate.
The scene/hardware supervisor must retain collision and occupancy interlocks.
"""
    from scipy.optimize import least_squares
    from scipy.spatial.transform import Rotation
    arm_from_robot = np.linalg.inv(kin.fk(np.zeros(6), 'arm_2/base_link'))
    def pose(q): return np.asarray(contract['box_from_arm']) @ arm_from_robot @ kin.grasp_fk(q, contract['task']['diameter'])
    start = pose(current); wanted = start[:3, 3].copy()
    wanted[2] = max(wanted[2]+config['return_lift_m'], contract['box_max'][2]+.18)
    # Keep the released jaw open while lifting out of the tray.
    q = np.asarray(current).copy(); q[-1] = max(current[-1], home[-1])
    def residual(arm):
        trial = q.copy(); trial[:5] = arm; p = pose(trial)
        return np.r_[p[:3, 3]-wanted, .025*Rotation.from_matrix(p[:3, :3] @ start[:3, :3].T).as_rotvec()]
    solved = least_squares(residual, q[:5], bounds=(np.asarray(contract['lower_rad'])[:5]+.02,
                           np.asarray(contract['upper_rad'])[:5]-.02), max_nfev=150)
    q[:5] = solved.x
    if np.linalg.norm(pose(q)[:3, 3]-wanted) > .015:
        raise RuntimeError('Public-geometry return lift is unreachable')
    return [q, np.asarray(home).copy()]
