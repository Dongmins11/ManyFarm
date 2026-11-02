"""ROS 없이 시험 순서만 검증: 운송 도킹 전 수확 복귀를 보내지 않는다."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.mark.parametrize('outcome', ['docked', 'transport_failed', 'missing', 'rejected'])
def test_harvest_waits_for_transport(tmp_path, outcome):
    source = Path(__file__).resolve().parents[1] / 'tools/single_cycle_steps.py'
    function = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'after_handoff')
    post = tmp_path / 'post_sorter'
    post.mkdir()
    (tmp_path / 'fixture.json').write_text(json.dumps({'overlap_cycle': True}))
    (tmp_path / 'cargo_manifest.json').write_text(json.dumps({'fruit_paths': ['fruit']}))
    sent = []
    events = []

    def start(*args):
        assert json.loads((post / 'sorter_docked.json').read_text())['unload_ready_accepted']
        sent.append(args[-1])
        return 'action'

    def wait(predicate, timeout, label):
        if '수확 복귀 허가' in label:
            assert not predicate()
            assert not sent
            if outcome == 'transport_failed':
                (post / 'result.json').write_text(json.dumps({'passed': False, 'error': '105'}))
            elif outcome != 'missing':
                (post / 'sorter_docked.json').write_text(json.dumps({
                    'station_id': 'SORT_01', 'unload_ready_accepted': outcome == 'docked'}))
            if not predicate():
                raise TimeoutError(label)
        else:
            (post / 'result.json').write_text(json.dumps({'passed': True}))
            assert predicate()

    namespace = dict(json=json, uuid4=uuid4, utc=lambda: 'now', start_action=start,
                     ReturnToStation=SimpleNamespace(Goal=lambda **kw: kw),
                     finish_action=lambda *args: None)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    args = (tmp_path, None, wait, None, lambda event, **kw: events.append(event), {}, [])
    if outcome == 'docked':
        namespace['after_handoff'](*args)
        assert sent == ['harvest_return']
        assert events.index('harvest_return_waiting') < events.index('harvest_return_released')
    else:
        with pytest.raises((RuntimeError, TimeoutError)):
            namespace['after_handoff'](*args)
        assert not sent
