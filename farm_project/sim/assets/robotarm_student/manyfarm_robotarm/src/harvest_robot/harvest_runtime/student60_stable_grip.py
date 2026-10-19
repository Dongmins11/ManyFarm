"""Camera/encoder-only entry and bounded grip stabilization.

This is an explicitly assisted Student, not pure neural inference. The neural
policy keeps running with actual executed goals. No task phase, simulator fruit
pose, contact/attachment flag or Teacher actor is available to this controller.
"""
import numpy as np
from .student60_entry_servo import EntryVisualServoController
from .student60 import encode_command, decode_command


class StableGripController(EntryVisualServoController):
    def __init__(self, *args, entry_jaw_gate=False, entry_tolerance_m=.008, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_jaw_gate = entry_jaw_gate
        if not .001<=entry_tolerance_m<=.010:raise ValueError('Invalid observed entry tolerance')
        self.entry_tolerance_m=float(entry_tolerance_m)

    def start(self, target_id, initial_target_rad):
        super().start(target_id, initial_target_rad)
        self.last_near_time = -float('inf')
        self.loaded_since = None
        self.hold_start = None
        self.hold_arm = None
        self.hold_jaw = None
        self.guard_finished = False
        self.alignment_s = 0.
        self.entry_ready = not self.entry_jaw_gate

    def step(self, frames, q_rad, qd_rad_s, tcp_arm, target, now, capture):
        command, note = super().step(frames, q_rad, qd_rad_s, tcp_arm, target, now, capture)
        report = note['visual_servo']
        goal, servo = decode_command(command, self.contract['lower_rad'], self.contract['upper_rad'])
        previous = self.inner.previous_q
        distance = report.get('observed_target_distance_m')
        if distance is not None and distance < .05:
            self.last_near_time = now
        near_recent = now-self.last_near_time <= .75
        if not self.entry_ready:
            aligned = (distance is not None and distance < getattr(self,'entry_tolerance_m',.008)
                       and abs(report.get('closing_vertical_component', 1.)) < .10
                       and q_rad[-1] > 1.4)
            self.alignment_s = self.alignment_s+.05 if aligned else 0.
            self.entry_ready = self.alignment_s >= .15-1e-6
            if not self.entry_ready:
                # Open before advancing into the pocket. Absolute goals change
                # by at most the same .10rad/tick recurrent command bound.
                goal[-1] = np.clip(max(goal[-1], 1.5), previous[-1]-.1, previous[-1]+.1)
                report['entry_open_gate'] = True
        loaded_hint = servo[1] < .4 and near_recent and self.entry_ready
        self.loaded_since = (now if self.loaded_since is None else self.loaded_since) if loaded_hint else None
        if (not self.guard_finished and self.hold_start is None
                and self.loaded_since is not None and now-self.loaded_since >= .1-1e-6):
            self.hold_start = now
            self.hold_arm = previous[:5].copy()
            self.hold_jaw = float(previous[-1])
        if self.hold_start is not None and now-self.hold_start < 2.1:
            elapsed = now-self.hold_start
            goal[:5] = self.hold_arm
            # Fix the contact preload origin. Letting the neural jaw goal rise
            # during this hold had reduced bilateral forces and lost the fruit.
            goal[-1] = self.hold_jaw-min(np.deg2rad(4.), np.deg2rad(6.)*elapsed)
            goal[-1] = np.clip(goal[-1], self.contract['lower_rad'][-1], self.contract['upper_rad'][-1])
            servo = np.array([8., .15])
            report.update(active=True, bounded_grip_hold=True,
                          hold_remaining_s=2.1-elapsed, preload_rad=self.hold_jaw-goal[-1])
        elif self.hold_start is not None:
            self.guard_finished = True
            self.captured = True
            report['bounded_grip_hold_completed'] = True
        elif not note['target']['valid'] and near_recent and not self.guard_finished:
            goal[:5] = previous[:5]
            report.update(active=True, brief_occlusion_arm_hold=True)
        report.update(entry_ready=self.entry_ready, entry_alignment_s=self.alignment_s)
        return encode_command(goal, servo, self.contract['lower_rad'], self.contract['upper_rad']), note
