"""실물 설정이 실행 묶음 생성 과정에서 누락되지 않는지 검증한다."""
import json
import math
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/tools'))
from prepare_harvest_handoff import prepare
from scout_new.observer import SurveyObserver
from farm_navigation.navigation_types import NavigationSettings


def test_generated_handoff_keeps_real_arrival_and_retry_policy():
    with tempfile.TemporaryDirectory(dir=ROOT/'sim/runs') as temporary:
        result = prepare(Path(temporary)/'runtime')
        profile = yaml.safe_load((ROOT/result['environment_config']).read_text())
        task = json.loads((ROOT/profile['harvest_config']).read_text())
        assert profile['navigation']['heading_tolerance_rad'] == math.radians(6)
        assert task['navigation_collision_retry_count'] == 5
        assert task['transfer']['enabled']
        # 팔 단독 프로필에는 인계 정지 소유자 없는 충돌 재시도를 켜지 않는다.
        standalone = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest_task.json').read_text())
        assert standalone.get('navigation_collision_retry_count', 0) == 0


@pytest.mark.parametrize('name', ['scout_runtime.yaml', 'scout_fleet_runtime.yaml'])
def test_selected_scout_profile_enables_real_readiness_and_tf_wait(name):
    profile = yaml.safe_load((ROOT/'sim/ros_ws/src/farm_sim_config/config'/name).read_text())
    settings = NavigationSettings.from_mapping(profile['navigation'])
    assert settings.require_active_nav2
    assert settings.tf_recovery_enabled
    assert settings.tf_recovery_wait_forever


@pytest.mark.parametrize('value', [0, -1, float('inf'), float('nan'), True, '180'])
def test_invalid_rpc_timeout_does_not_start_worker(value, tmp_path):
    with patch('scout_new.observer.subprocess.Popen') as popen:
        with pytest.raises(ValueError, match='rpc_timeout_s'):
            SurveyObserver(['unused'], tmp_path/'worker.log', rpc_timeout_s=value)
        popen.assert_not_called()


def test_observer_uses_selected_timeout(tmp_path):
    with patch('scout_new.observer.subprocess.Popen'), patch('scout_new.observer.threading.Thread'):
        observer = SurveyObserver(['unused'], tmp_path/'worker.log', rpc_timeout_s=180)
        try:
            with patch.object(observer, 'receive', return_value={'id': 1, 'ok': True, 'result': {}}) as receive:
                check = lambda: None
                observer.call('capture', check)
                receive.assert_called_once_with(check, 180.)
        finally:
            observer._log.close()
