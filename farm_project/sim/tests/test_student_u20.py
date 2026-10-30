"""전달 U20 실가중치·좌표·농장 연결 검사. GPU/물리 수확 성능 시험과 구분한다."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT/'sim/assets/robotarm_student/manyfarm_robotarm'
sys.path[:0] = [str(ROOT/'sim/ros_ws/src/farm_sim_devices'), str(RELEASE/'src/harvest_robot')]
from farm_sim_devices.student_session import StudentRuntime
from harvest_rl.kinematics import ArmKinematics
from harvest_rl.settings import URDF
from harvest_sensors.u20_deployment import reference_urdf
try:
    from pxr import Usd, UsdGeom, PhysxSchema
except ImportError:
    Usd = None


class StudentU20Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((RELEASE/'handoff/MISSION_RELEASE.json').read_text())
        cls.contract = torch.load(RELEASE/cls.manifest['models']['u20']['path'],
                                  weights_only=True, map_location='cpu')['contract']

    def test_runtime_loads_u20_model_without_d435_center_and_preserves_rear(self):
        settings = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/student_policy.json').read_text())
        settings.update(camera='u20', device='cpu')
        config = json.loads((RELEASE/self.manifest['config']).read_text())
        device = SimpleNamespace(config={'policy_arm_position_m': np.asarray(self.contract['box_from_arm'])[:3, 3]},
            lower=np.asarray(self.contract['lower_rad']), upper=np.asarray(self.contract['upper_rad']),
            home=np.asarray(config['home_rad']), travel=np.asarray(config['stow_rad']), robot_id='test')
        rig = SimpleNamespace(world_from_robot=np.eye(4), native_processor=None, close=Mock(),
            cameras={'rear': {'rgb': SimpleNamespace(get_rgb=lambda: np.zeros((90, 160, 3), np.uint8))}})
        detector = Mock()
        with patch('farm_sim_devices.student_camera.FarmD435Rig', return_value=rig) as make_rig, \
                patch('harvest_vision.client.Detector', return_value=detector), \
                patch('farm_sim_devices.basket_laser.BasketLaserSensor'):
            runtime = StudentRuntime(ROOT, settings, object(), device, self.contract['task'])
        self.assertEqual(runtime.camera.camera_kind, 'u20')
        self.assertIsNone(runtime.camera.center)
        self.assertEqual(type(runtime.camera.core.policy).__name__, 'U20Inference')
        profile = make_rig.call_args.args[3]
        self.assertEqual(set(profile['views']['right']['streams']), {'rgb'})
        self.assertEqual(set(profile['views']['rear']['streams']), {'rgb', 'depth'})
        # 실가중치로 3-frame history 및 실제 적용 명령 ACK 연결을 검사한다.
        observation = dict(rgb=np.zeros((2, 90, 160, 3), np.uint8),
            depth_m=np.zeros((2, 90, 160), np.float32), camera_valid=np.ones(2, bool),
            state=np.zeros(23, np.float32))
        observation['depth_m'][1] = .5
        policy = runtime.camera.core.policy
        for _ in range(4):
            command = policy.predict(observation, 'camera_target')
            self.assertEqual(command.shape, (8,))
            self.assertTrue(np.isfinite(command).all())
            policy.acknowledge(command)
            observation['state'][12:18] = command[:6]
        runtime.close()

    def test_u20_changes_sensor_pose_without_changing_arm_or_rear_fk(self):
        old = ArmKinematics(URDF)
        new = ArmKinematics(reference_urdf(self.contract['camera_config']))
        np.testing.assert_array_equal(old.lower, new.lower)
        np.testing.assert_array_equal(old.upper, new.upper)
        profile = self.contract['camera_config']
        for q in (np.zeros(6), (new.lower+new.upper)/2, np.array([.3, -.2, .4, -.3, .2, .8])):
            for link in ('arm_2/base_link', 'arm_2/gripper_link', 'arm_2/tool0',
                         profile['views']['rear']['rgb_optical_frame']):
                np.testing.assert_allclose(old.fk(q, link), new.fk(q, link), atol=1e-12)
            link = profile['views']['right']['rgb_optical_frame']
            self.assertFalse(np.allclose(old.fk(q, link), new.fk(q, link)))

    @unittest.skipIf(Usd is None, 'Isaac USD 라이브러리 필요; 렌더/GPU 불필요')
    def test_farm_wrist_visuals_preserve_all_physics(self):
        from farm_sim_devices.student_camera import FarmD435Rig
        from harvest_sensors.u20_visuals import physics_signature
        sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
        from farm_sim_runtime.robotarm_asset_setup import configure_harvest_arm
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageMetersPerUnit(stage, 1.)
        UsdGeom.SetStageUpAxis(stage, 'Z')
        UsdGeom.Xform.Define(stage, '/Robot').GetPrim().GetReferences().AddReference(
            str(ROOT/'sim/assets/robots/harvest_count_test/harvest_robot.usd'))
        config = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json').read_text())
        for key in ('box_floor', 'teacher_alignment'):
            if 'asset_path' in config[key]:
                config[key]['asset_path'] = str(ROOT/config[key]['asset_path'])
        configure_harvest_arm(stage, '/Robot', config)
        before = physics_signature(stage)
        rig = FarmD435Rig.__new__(FarmD435Rig)
        rig.world = SimpleNamespace(stage=stage)
        rig.device = SimpleNamespace(robot_path='/Robot', _fixed_path='/Robot/arm_2_gripper_link')
        rig.config = self.contract['camera_config']
        rig.kin = ArmKinematics(reference_urdf(rig.config))
        rig.install_visuals()
        self.assertEqual(physics_signature(stage), before)
        self.assertTrue(stage.GetPrimAtPath('/World/StudentSensors/WristVisuals'))
        self.assertTrue(stage.GetPrimAtPath('/Robot/arm_1_gripper_link/StudentU20Visuals'))
        self.assertEqual(stage.GetPrimAtPath('/Robot/arm_1_wrist_camera_link/visuals').GetAttribute('visibility').Get(), 'invisible')


if __name__ == '__main__':
    unittest.main()
