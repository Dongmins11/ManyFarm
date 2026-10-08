"""물리 진단은 관측만 수행하며 랜덤 rest 자세/고정 상태와 중력 적용을 구분한다."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_sim_devices', 'farm_sim_runtime'):
    sys.path.insert(0, str(ROOT/'sim/ros_ws/src'/package))
from farm_sim_devices.fruit_attachment import FruitAttachments
from farm_sim_devices.stem_physics import StemSettings
from farm_sim_runtime.harvest_physics_inspector import diagnostic_summary, enable_physics_debug_ui


class PhysicsDebugUiTests(unittest.TestCase):
    def test_extension_layer_change_is_restored_even_on_failure(self) -> None:
        """공식 layers 확장의 root 전환이 후속 session 물리 쓰기를 깨지 않게 한다."""
        for fail in (False, True):
            with self.subTest(fail=fail):
                session = SimpleNamespace(GetLayer=lambda: 'session')
                root = SimpleNamespace(GetLayer=lambda: 'root')
                stage = SimpleNamespace(target=session)
                stage.GetEditTarget = lambda: stage.target
                stage.SetEditTarget = lambda target: setattr(stage, 'target', target)
                manager = SimpleNamespace(
                    set_extension_enabled_immediate=lambda *_: stage.SetEditTarget(root),
                    is_extension_enabled=lambda _: not fail)
                app = SimpleNamespace(get_app=lambda: SimpleNamespace(get_extension_manager=lambda: manager))
                usd = SimpleNamespace(get_context=lambda: SimpleNamespace(get_stage=lambda: stage))
                kit = SimpleNamespace(app=app)
                modules = {'omni': SimpleNamespace(kit=kit, usd=usd),
                           'omni.kit': kit, 'omni.kit.app': app, 'omni.usd': usd}
                with patch.dict(sys.modules, modules):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, '시각화 확장'):
                            enable_physics_debug_ui()
                    else:
                        enable_physics_debug_ui()
                self.assertIs(stage.target, session)


class InspectorTests(unittest.TestCase):
    def fixture(self) -> FruitAttachments:
        obj = FruitAttachments.__new__(FruitAttachments)
        obj._ready = True
        obj.paths = ['/Fruit']
        obj.masses = np.array([.009])
        obj.records = [dict(initial_position_world_m=[0., 0., 1.])]
        obj.tips = np.array([[0., 0., .035]])
        obj.local_com = np.zeros((1, 3))
        q = np.array([np.cos(np.pi/8), np.sin(np.pi/8), 0., 0.])
        obj.rest_orientation = np.array([q])
        obj._cached_orientations = np.array([q])
        obj.anchors = np.array([[0., -.035/np.sqrt(2), 1.+.035/np.sqrt(2)]])
        obj.current_positions = lambda: np.array([[0., 0., .998]])
        obj.current_velocities = lambda: np.array([[0., 0., -.001, 0., 0., 0.]])
        obj.active, obj.attached = np.array([True]), np.array([True])
        obj.last_step = SimpleNamespace(force=np.array([[0., 0., .08829]]), torque=np.array([[.001, 0., 0.]]))
        obj.settings = StemSettings()
        return obj

    def test_rest_rotation_stays_tilted_while_sag_and_force_are_nonzero(self) -> None:
        obj = self.fixture()
        sample = obj.diagnostic_state('/Fruit')
        self.assertAlmostEqual(sample['root_z_change_mm'], -2.)
        self.assertAlmostEqual(sample['tip_displacement_mm'], 2.)
        self.assertAlmostEqual(sample['rest_rotation_change_deg'], 0.)
        self.assertAlmostEqual(sample['com_tip_tilt_deg'], 45.)
        self.assertAlmostEqual(sample['stem_force_N'][2], .08829)
        self.assertTrue(sample['active'])

    def test_readout_cannot_mutate_attachment_reference_arrays(self) -> None:
        obj = self.fixture()
        before = obj.anchors.copy(), obj.rest_orientation.copy(), obj.attached.copy()
        sample = obj.diagnostic_state('/Fruit')
        sample['anchor_world_m'][0] = 999
        sample['orientation_wxyz'][0] = 0
        for value, expected in zip((obj.anchors, obj.rest_orientation, obj.attached), before):
            np.testing.assert_array_equal(value, expected)
        with self.assertRaises(ValueError):
            obj.diagnostic_state('/Missing')

    def test_frozen_gravity_setting_does_not_claim_dynamic_response(self) -> None:
        sample = self.fixture().diagnostic_state('/Fruit')
        sample.update(active=False, kinematic=True, gravity_enabled=True,
                      gravity_force_N=[0., 0., 0.], enabled_collider_count=1, collider_count=1,
                      arm_contact_max_N=0., finger_contact_N=[0., 0.])
        text = diagnostic_summary(sample)
        self.assertIn('FROZEN | gravity ON', text)
        self.assertIn('Gravity Fz +0.0000 N', text)
        self.assertIn('Not a freely swinging connector joint', text)

    def test_quaternion_sign_does_not_report_fake_rotation(self) -> None:
        obj = self.fixture()
        obj._cached_orientations *= -1
        self.assertAlmostEqual(obj.diagnostic_state('/Fruit')['rest_rotation_change_deg'], 0.)


if __name__ == '__main__':
    unittest.main()
