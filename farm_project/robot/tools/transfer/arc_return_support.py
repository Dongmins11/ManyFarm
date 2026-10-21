"""곡선 단독 시험의 기록 검증. 경로/오차 계산은 기존 공통 transfer_arc를 사용한다."""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from farm_navigation.transfer_arc import ArcSpec, arc_path, check_motion, wrap

RETURN_HEADING = math.radians(1.)
RETURN_CHECKER = math.radians(.5)


from farm_navigation.motion_reference import session_identity


def load_departure(file, *, session, baseline_hash, spec):
    data = Path(file).read_bytes()
    record = json.loads(data)
    if (record.get('ok') is not True or record.get('execute') is not True
            or record.get('phase') != 'SUCCEEDED' or record.get('cleanup_stopped') is not True
            or record.get('ros_cleanup_complete') is not True
            or record.get('direction') != 'reverse_left'):
        raise ValueError('정지·종료까지 성공한 신규 후진 곡선 실행 기록 필요')
    if record.get('odom_session') != session:
        raise ValueError('odom 발행자/부팅 세션 변경: 이전 곡선 기록 사용 불가')
    if record.get('baseline_hash') != baseline_hash or record.get('arc_spec') != asdict(spec):
        raise ValueError('출발 기록의 실행 설정/곡선 설정 불일치')
    origin = tuple(record['origin'])
    path = arc_path(origin, spec)
    stored = record.get('path')
    if not isinstance(stored, list) or len(stored) != len(path):
        raise ValueError('출발 원호 경로 누락')
    for a, b in zip(stored, path):
        if len(a) != 3 or not all(type(x) in (int,float) and math.isfinite(x) for x in a):
            raise ValueError('출발 원호 경로 오류')
        if any(abs(x-y)>1e-9 for x,y in zip(a,b)):
            raise ValueError('출발 원호 경로 불일치')
    return origin, list(reversed(path)), hashlib.sha256(data).hexdigest()


def check_reentry(current, path, spec):
    if len(current)!=3 or not all(math.isfinite(x) for x in current):
        raise ValueError('유효한 현재 자세 필요')
    distance=math.dist(current[:2],path[0][:2]);angle=abs(wrap(current[2]-path[0][2]))
    if distance>spec.endpoint_tolerance or angle>RETURN_HEADING:
        raise RuntimeError('복귀 시작 자세 오차 초과: 위치 %.6fm / 각도 %.3f도' % (distance,math.degrees(angle)))
    return {'position_error_m':distance,'heading_error_rad':angle}


def check_return_complete(departure_origin, current, spec):
    result=check_motion(departure_origin,current,spec)
    result['endpoint_error']=math.dist(current[:2],departure_origin[:2])
    result['yaw_error']=abs(wrap(current[2]-departure_origin[2]))
    if result['endpoint_error']>spec.endpoint_tolerance or result['yaw_error']>RETURN_HEADING:
        raise RuntimeError('복귀 종료 위치·방향 오차 초과')
    return result


def require_plan(reference, *, direction, session, source_hash, baseline_hash, radius, origin):
    if (reference.get('ok') is not True or reference.get('phase')!='PLAN_ONLY'
            or reference.get('radius')!=radius or reference.get('direction')!=direction
            or reference.get('odom_session')!=session or reference.get('departure_sha256')!=source_hash
            or reference.get('baseline_hash')!=baseline_hash):
        raise ValueError('계획의 방향·세션·출발 기록·설정 불일치')
    p=reference['origin']
    if len(p)!=3 or not all(math.isfinite(x) for x in p):raise ValueError('계획 자세 오류')
    if math.dist(origin[:2],p[:2])>.005 or abs(wrap(origin[2]-p[2]))>.02:
        raise RuntimeError('계획 이후 출발 자세가 달라졌습니다.')
