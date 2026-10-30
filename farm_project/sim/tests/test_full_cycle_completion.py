"""액션 일부만 성공하거나 선별 잔류가 있으면 전체 재시도를 멈추지 않는다."""
import copy
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from run_fresh_cycle_until_success import complete


def successful():
    ok = dict(status=4, result=dict(result_code='SUCCESS'))
    data = {k: copy.deepcopy(ok) for k in ('scout', 'scout_sec02', 'scout_return', 'harvest_return', 'pickup_final', 'dock_final')}
    data['dock_final']['result'].update(transfer_complete=True, transport_clear=True, restore_complete=True)
    data.update(passed=True, window_count=1, harvest_results=[copy.deepcopy(ok)])
    data['sorter_and_transport_return'] = dict(unload=ok, sort=ok, **{'return': ok}, count_valid=True,
        input_count=2, sorted_count=2, remaining_fruit_paths=[], all_input_fruits_sorted=True)
    return data


def test_full_success():
    assert complete(successful())


@pytest.mark.parametrize('key', ['scout', 'scout_sec02', 'scout_return', 'harvest_return', 'pickup_final', 'dock_final'])
def test_missing_robot_step_rejected(key):
    data = successful(); del data[key]
    assert not complete(data)


@pytest.mark.parametrize('change', [dict(sorted_count=1), dict(remaining_fruit_paths=['fruit']),
    dict(input_count=0, sorted_count=0), dict(count_valid=False), dict(all_input_fruits_sorted=False)])
def test_incomplete_physical_sorting_rejected(change):
    data = successful(); data['sorter_and_transport_return'].update(change)
    assert not complete(data)


def test_reuse_and_missing_window_rejected():
    data = successful(); data['harvest_reused'] = True
    assert not complete(data)
    data = successful(); data['window_count'] = 2
    assert not complete(data)
