"""운송 단독 시험의 잔존 모델 제외가 실행 대상 로봇을 숨기지 않도록 검사한다."""
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim/tools'))
import run_sorter_cycle_trial as trial


def test_active_scout_cannot_be_excluded(tmp_path,monkeypatch):
    monkeypatch.setattr(trial,'ROOT',tmp_path)
    config=tmp_path/'config';config.mkdir();monkeypatch.setattr(trial,'CONFIG',config)
    runtime=tmp_path/'runtime';runtime.mkdir()
    scout=dict(robot_id='scout_test',scene_binding=dict(robot_prim='/World/Scout'))
    (config/'scout_fleet.json').write_text(json.dumps(scout))
    (runtime/'scout.json').write_text(json.dumps(scout))
    (runtime/'fleet.json').write_text(json.dumps(dict(device_configs=['runtime/scout.json'])))
    with pytest.raises(ValueError,match='실행 fleet'):
        trial.configure_unused_scout_exclusion(tmp_path,runtime)
    assert not (runtime/'without_unused_scout.usda').exists()
    assert json.loads((runtime/'scout.json').read_text())==scout
