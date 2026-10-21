"""격리 시험 단계 기록 검증. 이전 성공 기록을 생략하거나 다른 출발과 섞지 않는다."""
import hashlib
import json
import math
from pathlib import Path

STAGES=('departure','wall','retreat','align','return')


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def matrix_pose(matrix) -> tuple:
    values=(float(matrix[0,3]),float(matrix[1,3]),math.atan2(matrix[1,0],matrix[0,0]))
    if not all(math.isfinite(v) for v in values):raise ValueError('TF 자세 오류')
    return values


def pose_error(pose: tuple, target: tuple) -> dict:
    if any(len(p)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in p) for p in (pose,target)):
        raise ValueError('자세 오류')
    return {'position_error_m':math.dist(pose[:2],target[:2]),
            'heading_error_rad':abs(math.atan2(math.sin(pose[2]-target[2]),math.cos(pose[2]-target[2])))}


def completed(record: dict) -> bool:
    return (record.get('ok') is True and record.get('phase')=='SUCCEEDED'
            and record.get('cleanup_stopped') is True and record.get('ros_cleanup_complete') is True
            and (record.get('execute') is True or record.get('mode')=='execute'))


def verify_predecessor(file: Path, direction: str, cycle: str, session: str,
                       departure_sha: str, current: tuple) -> str:
    if file is None:raise ValueError('직전 성공 기록 증명 누락')
    proof=json.loads(Path(file).read_text())
    if proof.get('kind') == 'stopped_wall_failure_recovery_v1':
        from recovery_support import validate_recovery
        validate_recovery(proof, direction, cycle, session, departure_sha)
        # 현재 자세는 기존 runtime의 정지·세션·후진 경로 검사로 검증한다.
        # execute에서는 require_plan이 plan 이후 자세 변화도 검사한다.
        return digest(file)
    expected={'retreat':'wall','align':'retreat','forward_right':'align'}[direction]
    if any(proof.get(k)!=v for k,v in dict(stage=expected,cycle_id=cycle,
            odom_session=session,departure_sha256=departure_sha).items()):
        raise ValueError('복귀 단계 순서/세션/출발 기준 불일치')
    result=Path(proof['result_file'])
    if digest(result)!=proof['result_sha256']:raise ValueError('직전 성공 기록 변경')
    record=json.loads(result.read_text())
    if not completed(record) or record.get('cycle_id')!=cycle or record.get('odom_session')!=session:
        raise ValueError('직전 동작 성공·정지·세션 미확인')
    if expected!='wall' and record.get('departure_sha256')!=departure_sha:
        raise ValueError('다른 출발 기록을 사용한 직전 동작')
    error=pose_error(current,record['final_pose'])
    if error['position_error_m']>.005 or error['heading_error_rad']>.02:
        raise ValueError('직전 정지 이후 자세 변경')
    return digest(file)


def require_wall_start(record: dict, departure: dict) -> None:
    if record.get('phase')!='PLAN_ONLY' or not record.get('ok'):raise ValueError('벽 계획 실패')
    if record.get('odom_session')!=departure.get('odom_session'):raise ValueError('벽 계획 세션 불일치')
    error=pose_error(record['origin'],departure['final_pose'])
    if error['position_error_m']>.008 or error['heading_error_rad']>math.radians(1):
        raise ValueError('출발 곡선 종료 자세에서 벗어남')


def next_stage(state: dict) -> str:
    done=state.get('completed',[])
    if done!=list(STAGES[:len(done)]) or len(done)>=len(STAGES):
        raise ValueError('단계 기록 손상 또는 전체 시험 완료')
    if state.get('executing'):raise ValueError('이전 실행 종료 미확인: 자동 재시도 금지')
    if state.get('failed'):raise ValueError('직전 단계 실패: 자동 재시도 금지')
    return STAGES[len(done)]
