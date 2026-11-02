"""설정 기반 전진 접근·정지 회전·후진 진입. ROS 장치는 호출자로부터 받는다."""
from dataclasses import replace
import math
import uuid
import time


def staged_geometry(graph, options: dict, station_xy: tuple) -> tuple:
    """노드에서 접근점과 바깥을 바라보는 yaw(rad), 명시적 후진 경로를 만든다."""
    if options.get('strategy') == 'forward_wall_then_turn':
        from .station_forward_stages import forward_geometry
        approach, _, final_yaw = forward_geometry(graph, options, station_xy)
        return approach, final_yaw, None
    if options.get('strategy') != 'forward_then_reverse':
        raise ValueError('Unknown staged station strategy')
    if options.get('tag_alignment', {}).get('enabled', False):
        raise ValueError('태그 최종 정렬 어댑터는 아직 연결되지 않았습니다.')
    approach = graph.nodes[options['approach_node_id']]
    if math.dist(approach, station_xy) < 1e-6:
        raise ValueError('접근 노드와 스테이션은 달라야 합니다.')
    outward = math.atan2(approach[1]-station_xy[1], approach[0]-station_xy[0])
    forward = graph.plan(station_xy, approach, .001, .001)
    # 마지막 진입은 설정한 두 노드 사이 직선. 우회 경로를 후진 진입으로 오인하지 않는다.
    for p in forward.points:
        cross = (p[0]-station_xy[0])*(approach[1]-station_xy[1])-(p[1]-station_xy[1])*(approach[0]-station_xy[0])
        if abs(cross) > 1e-6:
            raise ValueError('마지막 후진 진입 경로는 직선이어야 합니다.')
    reverse = replace(forward, plan_id=uuid.uuid4().hex,
                      points=tuple(reversed(forward.points)), edge_ids=tuple(reversed(forward.edge_ids)))
    return approach, outward, reverse


def run_stages(*, graph, options: dict, station_xy: tuple, forward, backward,
               spin, poses, motion, settings, check, phase, wall_reverse=None) -> None:
    """전진 완료 뒤 회전·정지를 확인하고 후진한다. 태그 비활성 시 관측 대기 없음."""
    if options.get('strategy') == 'forward_wall_then_turn':
        from .station_forward_stages import run_forward_stages
        return run_forward_stages(graph=graph, options=options, station_xy=station_xy,
            forward=forward, spin=spin, poses=poses, motion=motion, settings=settings,
            check=check, phase=phase, wall_runtime=wall_reverse)
    approach, yaw, route = staged_geometry(graph, options, station_xy)
    retries = options.get('approach_retry_count', 0)
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 2:
        raise ValueError('approach_retry_count: 0~2 정수 필요')
    for attempt in range(retries + 1):
        check()
        plan = forward.plan(approach)
        heading = yaw
        for a, b in reversed(list(zip(plan.points, plan.points[1:]))):
            if math.dist(a, b) > 1e-6:
                heading = math.atan2(b[1]-a[1], b[0]-a[0])
                break
        phase(f'APPROACH_STATION attempt={attempt + 1} points={plan.points}')
        forward.navigate(approach, heading, route_plan=plan)
        check()
        motion.wait_stopped(check)
        current = poses.current(check)
        error = math.dist((current[0,3], current[1,3]), approach)
        phase(f'VERIFY_APPROACH attempt={attempt + 1} distance={error:.4f}m limit={settings.arrival_tolerance_m:.4f}m')
        # Nav2 성공만으로 회전하지 않는다. 정지 후 실측 위치가 벗어나면 재계획한다.
        if error > settings.arrival_tolerance_m:
            if attempt < retries:
                continue
            raise RuntimeError('스테이션 접근 위치 오차 초과: 재접근 소진')
        check()
        if wall_reverse is not None:
            align_entry(yaw, options, spin, poses, motion, settings, check, phase)
            check()
            wall_reverse.execute(check, phase, math.dist(approach, station_xy))
            motion.wait_stopped(check)
            phase('STATION_STOPPED')
            return
        phase('ALIGN_REVERSE_ENTRY')
        delta = math.remainder(yaw-math.atan2(current[1,0], current[0,0]), 2*math.pi)
        if abs(delta) > settings.heading_tolerance_rad:
            spin.execute(delta, options.get('rotation_timeout_s', 30.), check)
        motion.wait_stopped(check)
        current = poses.current(check)
        error = math.dist((current[0,3], current[1,3]), approach)
        phase(f'VERIFY_REVERSE_ENTRY attempt={attempt + 1} distance={error:.4f}m')
        if error > settings.arrival_tolerance_m:
            if attempt < retries:
                continue
            raise RuntimeError('후진 시작점 위치 오차 초과: 재접근 소진')
        if abs(math.remainder(yaw-math.atan2(current[1,0],current[0,0]),2*math.pi)) > settings.heading_tolerance_rad:
            raise RuntimeError('후진 시작 방향 정렬 미완료')
        break
    check()
    phase('REVERSE_TO_STATION')
    backward.navigate(station_xy, yaw, route_plan=route, reverse=True)
    check()
    motion.wait_stopped(check)
    current = poses.current(check)
    if math.dist((current[0,3],current[1,3]),station_xy) > settings.arrival_tolerance_m:
        raise RuntimeError('스테이션 도착 위치 오차 초과')
    if abs(math.remainder(yaw-math.atan2(current[1,0],current[0,0]),2*math.pi)) > settings.heading_tolerance_rad:
        raise RuntimeError('스테이션 도착 방향 오차 초과')
    phase('STATION_STOPPED')


def align_entry(yaw, options, spin, poses, motion, settings, check, phase) -> None:
    """Spin 완료 뒤 map 각도를 재측정한다. 위치 재접근 대신 제자리 각도만 다시 맞춘다."""
    config=options['wall_reverse']
    deadline=time.monotonic()+config['alignment_timeout_s']
    while True:
        check()
        motion.wait_stopped(check)
        current=poses.current(check)
        delta=math.remainder(yaw-math.atan2(current[1,0],current[0,0]),2*math.pi)
        phase(f'ALIGN_REVERSE_ENTRY error_deg={math.degrees(delta):.2f}')
        if abs(delta)<=settings.heading_tolerance_rad:
            # 한 표본의 일시적 각도 일치가 아니라 정지 후 재확인한다.
            motion.wait_stopped(check)
            current=poses.current(check)
            if abs(math.remainder(yaw-math.atan2(current[1,0],current[0,0]),2*math.pi))<=settings.heading_tolerance_rad:
                return
        elif time.monotonic()<deadline:
            try:
                spin.execute(delta, options.get('rotation_timeout_s',30.),check)
            except (RuntimeError, TimeoutError) as error:
                # Goal 종료가 확인되는 경우에만 정지 재관측으로 전환한다.
                spin.cancel()
                phase(f'WAIT_ENTRY_REALIGN: {error}')
                motion.wait_stopped(check)
                time.sleep(.5)
            continue
        if time.monotonic()>=deadline:
            phase('WAIT_ENTRY_ALIGNMENT: 회전 시간 한도, 정지 재측정 대기; 취소 가능')
            # 무한 회전하지 않는다. 외부 재배치/위치 보정으로 각도가 맞으면 재개한다.
            while True:
                check();current=poses.current(check)
                if abs(math.remainder(yaw-math.atan2(current[1,0],current[0,0]),2*math.pi))<=settings.heading_tolerance_rad:
                    break
                time.sleep(.2)
        time.sleep(.05)
