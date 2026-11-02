"""정지 엔코더 목표 유지와 주행 재개 시 제동 해제를 검증한다."""
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/farm_common'))
from farm_sim_devices.base_sim import BaseSim


def test_hold_latches_once_and_releases_for_motion(monkeypatch):
    monkeypatch.setitem(sys.modules, 'isaacsim.core.utils.types',
                        SimpleNamespace(ArticulationAction=lambda **kw: kw))
    gains, actions = [], []
    positions = np.array([1., 2.])
    base = BaseSim.__new__(BaseSim)
    base.config = dict(wheel_position_hold=True, wheel_radius_m=.1,
        wheel_separation_m=.4, max_linear_mps=.15, max_angular_rps=.6)
    base.indices = np.array([1, 3]); base.signs = np.ones(2)
    base.servo = None; base._hold_positions = None
    base._wheel_drive_gains = (np.zeros(2), np.array([100., 200.]))
    base.robot = SimpleNamespace(
        get_joint_positions=lambda **kw: positions,
        apply_action=actions.append,
        _articulation_view=SimpleNamespace(set_gains=lambda **kw: gains.append(kw)))
    base.command(0., 0.)
    positions[:] += .01
    base.command(0., 0.)
    np.testing.assert_array_equal(actions[-1]['joint_positions'], [1., 2.])
    assert len(gains) == 1
    np.testing.assert_array_equal(gains[0]['kps'], [[100., 200.]])
    base.command(.1, 0.)
    assert base._hold_positions is None
    assert 'joint_positions' not in actions[-1]
    np.testing.assert_array_equal(gains[-1]['kps'], [[0., 0.]])
    base.command(0., 0.)
    np.testing.assert_array_equal(actions[-1]['joint_positions'], positions)
    assert len(gains) == 3


def test_default_drive_does_not_enable_position_hold(monkeypatch):
    monkeypatch.setitem(sys.modules, 'isaacsim.core.utils.types',
                        SimpleNamespace(ArticulationAction=lambda **kw: kw))
    actions = []
    base = BaseSim.__new__(BaseSim)
    base.config = dict(wheel_radius_m=.1, wheel_separation_m=.4,
                       max_linear_mps=.15, max_angular_rps=.6)
    base.indices = np.array([0, 1]); base.signs = np.ones(2); base.servo = None
    base.robot = SimpleNamespace(apply_action=actions.append)
    base.command(0., 0.)
    assert 'joint_positions' not in actions[-1]
