"""Offline empty-view integration check: FK, command units and acknowledgement."""
import argparse
import json
from pathlib import Path
import numpy as np
from student60_bundle import ROOT, deployment
from student60_session import Student60Session


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    from harvest_sensors.deployment import expected_poses
    from harvest_sensors.profile import matrix
    from harvest_runtime.student60 import decode_command
    class EmptyDetector:
        def predict(self, rgb):
            return []
    d = deployment(); c = d['contract']
    world = np.asarray(d['robot_root_to_policy_world'])
    session = Student60Session(EmptyDetector(), world, device='cpu')
    q = (np.asarray(c['lower_rad']) + c['upper_rad']) / 2
    session.start('receiver-empty-scene', 'Red', q)
    poses = expected_poses(session.kin, q, c['camera_config'], world)
    capture = {}
    for name, view in c['camera_config']['views'].items():
        capture[name] = dict(rgb=np.zeros((720, 1280, 3), np.uint8),
            aligned_depth_m=np.zeros((720, 1280), np.float32),
            depth_m=np.zeros((480, 848), np.float32), raw_depth_m=np.zeros((480, 848), np.float32),
            ir={'ir_right': np.zeros((480, 848), np.uint8)} if name == 'right' else {},
            intrinsics={key: matrix(spec) for key, spec in view['streams'].items()},
            world_from_optical=poses[name], color_from_depth=np.asarray(view['rgb_from_stream']['depth']),
            stamp_s=0., pose_stamp_s=0., frame_number=0)
    command, note = session.step(capture, q, np.zeros(6), 0.)
    goals, servo = decode_command(command, c['lower_rad'], c['upper_rad'])
    blocked = False
    try:
        session.step(capture, q, np.zeros(6), .05)
    except ValueError as error:
        blocked = 'cknowledge' in str(error)
    if not blocked or note['target']['valid']:
        raise AssertionError('Missing observation/ack boundary failed')
    session.acknowledge(command)
    for item in capture.values():
        item.update(stamp_s=1/30, pose_stamp_s=1/30, frame_number=1)
    next_command, _ = session.step(capture, q, np.zeros(6), .05)
    session.acknowledge(next_command)
    result = dict(passed=True, camera_target_valid=False, empty_view_steps=2,
        outstanding_command_blocks_step=True, acknowledgement_unblocks_step=True,
        first_joint_goals_rad=goals.tolist(), first_jaw_stiffness_velocity=servo.tolist(),
        teacher_actor_loads=0, simulator_or_hardware_reads=0,
        note='Synthetic empty-view API check, not farm integration or harvest success')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
