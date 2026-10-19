"""Camera-only v20 integration session for a receiver-owned scene and commands.

No Isaac/ROS dependency or simulator state reads. The receiver supplies native
camera captures, measured joints and confirmation of the actually applied goal.
This synchronous adapter retains the validated 20Hz simulation-time contract.
"""
import numpy as np
from student60_bundle import ROOT, deployment


class Student60Session:
    def __init__(self, detector, world_from_robot, device='cpu'):
        from harvest_rl.kinematics import ArmKinematics
        from harvest_rl.settings import URDF
        from harvest_runtime.student60_camera_controller import make_controller
        from harvest_runtime.student60_faster_capture import FasterCaptureCameraHarvestController
        from harvest_vision.student60_camera_center import CenterCorrector
        self.release = deployment()
        self.contract = self.release['contract']
        self.kin = ArmKinematics(URDF)
        self.arm_from_robot = np.linalg.inv(self.kin.fk(np.zeros(6), 'arm_2/base_link'))
        self.arm_from_world = np.linalg.inv(np.asarray(world_from_robot) @ self.kin.fk(np.zeros(6), 'arm_2/base_link'))
        self.detector = detector
        self.core = make_controller(ROOT / self.release['models']['student']['path'], self.contract, device)
        self.controller = FasterCaptureCameraHarvestController(self.core, self.kin, self.contract,
                                                              body_center=False, entry_jaw_gate=True)
        self.center = CenterCorrector(ROOT / self.release['models']['center']['path'])
        self.target_id = None

    def start(self, target_id, label, initial_applied_joint_goals_rad):
        from harvest_vision.student60_tracking import AssignedFruitTracker
        from harvest_vision.workspace import load_workspace
        if label not in ('Red', 'Yellow'):
            raise ValueError('This release validates Red/Yellow assigned fruit only')
        self.roi, _ = load_workspace()
        self.tracker = AssignedFruitTracker(self.roi)
        self.target_id, self.label = target_id, label
        self.controller.start(target_id, initial_applied_joint_goals_rad)

    def step(self, capture, q_rad, qd_rad_s, elapsed_s):
        from harvest_vision.geometry import Frame
        from harvest_sensors.student60_native_fast import process_native
        from harvest_vision.student60_camera_center import selected_record
        if self.target_id is None:
            raise ValueError('Assign a target before inference')
        if self.core.pending:
            raise ValueError('Acknowledge the actually applied command before another step')
        frames = {name: Frame(d['rgb'], d['aligned_depth_m'], d['intrinsics']['rgb'],
                  self.arm_from_world @ d['world_from_optical']['rgb'],
                  d['stamp_s'], d['pose_stamp_s'], name) for name, d in capture.items()}
        detections, _ = process_native(frames['rear'], capture['rear'], self.detector, elapsed_s,
            self.contract['centre_offset_m'], arm_roi=self.roi if self.tracker.selected is None else None)
        self.tracker.update(detections, elapsed_s)
        if self.tracker.selected is None:
            candidates = [key for key, target in self.tracker.snapshot(elapsed_s).items()
                          if target['valid'] and target['label'] == self.label]
            if len(candidates) == 1:
                self.tracker.assign(elapsed_s, candidates[0])
        target = dict(self.tracker.observation(elapsed_s), target_id=self.target_id)
        uncorrected = self.core.target_filter.filter(target)
        observed = selected_record(uncorrected['position_m'], detections) if uncorrected['valid'] else None
        assigned = (observed if observed is not None
            and np.linalg.norm(np.asarray(observed['grasp_estimate_arm_m']) - uncorrected['position_m']) < 1e-7
            and abs(elapsed_s - uncorrected['age_s'] - observed['stamp_s']) < 1e-7 else None)
        if uncorrected['valid'] and observed is not None:
            corrected, _ = self.center.predict(None, uncorrected['position_m'], observed)
            target = dict(target, position_m=corrected.tolist())
        tcp = (self.arm_from_robot @ self.kin.grasp_fk(q_rad, self.contract['task']['diameter']))[:3, 3]
        return self.controller.step(frames, q_rad, qd_rad_s, tcp, target, elapsed_s,
            dict(capture, student_target_detections=detections, student_assigned_detection=assigned))

    def acknowledge(self, actually_applied_command):
        self.controller.acknowledge(actually_applied_command)
