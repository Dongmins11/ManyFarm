"""운송 실물/시뮬 진행 판정 정합과 원본의 다른 수치 보존을 검사한다."""
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '4648f762ca0fc842c0b0e917c764c19d03bec949'
REAL = 'robot/config/robots/waffle/transport_nav2.yaml'
SIM = 'sim/ros_ws/src/farm_sim_config/config/nav2_transport.yaml'


def test_transport_real_and_sim_use_same_progress_policy():
    real = yaml.safe_load((ROOT/REAL).read_text())
    sim = yaml.safe_load((ROOT/SIM).read_text())
    expected = dict(plugin='nav2_controller::PoseProgressChecker',
                    required_movement_radius=.1, required_movement_angle=.5,
                    movement_time_allowance=10.)
    for config in (real, sim):
        params = config['controller_server']['ros__parameters']
        assert params['progress_checker_plugins'] == ['progress_checker']
        assert params['progress_checker'] == expected


def test_real_profile_preserves_every_other_upstream_parameter():
    source = yaml.safe_load(subprocess.check_output(
        ['git', 'show', SOURCE+':farm_project/'+REAL], cwd=ROOT))
    selected = yaml.safe_load((ROOT/REAL).read_text())
    original_checker = source['controller_server']['ros__parameters']['progress_checker']
    selected['controller_server']['ros__parameters']['progress_checker'] = original_checker
    assert selected == source
