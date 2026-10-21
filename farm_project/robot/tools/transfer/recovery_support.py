"""명시적으로 요청한 벽 실패 후 복귀의 진입 증명. 성공 기록으로 바꾸지 않는다."""
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_checked(item: dict) -> dict:
    path = Path(item['file'])
    if digest(path) != item['sha256']:
        raise ValueError('복귀 근거 기록 변경: ' + str(path))
    return json.loads(path.read_text())


def validate_recovery(proof: dict, direction: str, cycle: str, session: str,
                      departure_sha: str) -> None:
    if proof.get('kind') != 'stopped_wall_failure_recovery_v1' or direction != 'retreat':
        raise ValueError('실패 후 복귀 증명은 최초 후진에만 사용합니다.')
    if (proof.get('cycle_id') != cycle or proof.get('odom_session') != session
            or proof.get('departure_sha256') != departure_sha):
        raise ValueError('복귀 cycle/session/출발 불일치')
    state = load_checked(proof['original_state'])
    departure = load_checked(proof['departure'])
    wall = load_checked(proof['wall_failure'])
    if (state.get('cycle_id') != cycle or state.get('completed') != ['departure']
            or state.get('executing') != 'wall' or not state.get('failed')):
        raise ValueError('벽 실패 상태가 아닙니다.')
    record = state['records']['departure']
    if (record['result_sha256'] != departure_sha
            or Path(record['result_file']).resolve() != Path(proof['departure']['file']).resolve()
            or proof['departure']['sha256'] != departure_sha):
        raise ValueError('상태의 출발 기록 불일치')
    for item in (departure, wall):
        if item.get('cycle_id') != cycle or item.get('odom_session') != session:
            raise ValueError('실패/출발 세션 불일치')
        if item.get('cleanup_stopped') is not True or item.get('ros_cleanup_complete') is not True:
            raise ValueError('정지 또는 종료 미확인')
    if (departure.get('ok') is not True or departure.get('execute') is not True
            or departure.get('phase') != 'SUCCEEDED' or departure.get('direction') != 'reverse_left'):
        raise ValueError('출발 성공 증명 필요')
    if (wall.get('ok') is not False or wall.get('mode') != 'execute'
            or wall.get('motion_requested') is not True or wall.get('phase') != 'EXECUTING'
            or wall.get('baseline_unchanged') is not True or wall.get('velocity_events') != []
            or wall.get('baseline_hash') != departure.get('baseline_hash')
            or wall.get('error') != 'Nav2 실패: status=6, error_code=106, '):
        raise ValueError('지원하는 벽 관측 실패 기록이 아닙니다.')
    log = Path(proof['controller_log']['file'])
    if digest(log) != proof['controller_log']['sha256']:
        raise ValueError('제어기 로그 변경')
    errors = [line for line in log.read_text().splitlines() if '[ERROR]' in line]
    if not errors or any('Wall observation expired / future' not in line for line in errors):
        raise ValueError('벽 관측 만료 외 오류가 포함됐습니다.')
    expected = Path(proof['original_state']['file']).parent / 'wall'
    if not Path(proof['wall_failure']['file']).resolve().is_relative_to(expected.resolve()):
        raise ValueError('다른 시험의 벽 기록')
    if log.resolve() != Path(proof['wall_failure']['file']).parent.resolve() / 'controller.log':
        raise ValueError('실패 로그 경로 불일치')
