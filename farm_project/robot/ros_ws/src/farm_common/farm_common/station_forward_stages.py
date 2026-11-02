"""실물 전진 스테이션: 경로 도착 → 벽 정밀 접근 → 반대 방향 정렬."""
import math
from .station_stages import align_entry


def forward_geometry(graph, options: dict, station_xy: tuple) -> tuple:
    """진입 기준 노드→접근 노드 벡터로 지도 목표각을 만든다. 실측 도킹 XY는 요구하지 않는다."""
    if options.get('tag_alignment', {}).get('enabled', False):
        raise ValueError('태그 정렬 어댑터는 아직 연결되지 않았습니다.')
    approach = graph.nodes[options['approach_node_id']]
    reference = graph.nodes[options['entry_reference_node_id']]
    if math.dist(reference, approach) < 1e-6:
        raise ValueError('진입 방향 기준 노드가 접근 노드와 같습니다.')
    if math.dist(approach, station_xy) > 1e-6:
        raise ValueError('전진 도킹의 경로 도착 노드와 station 노드가 다릅니다.')
    c = options['wall_forward']
    if not c.get('enabled') or c.get('direction') != 'forward':
        raise ValueError('전진 벽 도킹 설정이 필요합니다.')
    if not math.isfinite(c['max_travel_m']) or c['max_travel_m'] <= 0:
        raise ValueError('전진 최대 접근 거리 설정 오류')
    offset = options['final_rotation_rad']
    if not math.isfinite(offset):
        raise ValueError('최종 회전각 설정 오류')
    yaw = math.atan2(approach[1]-reference[1], approach[0]-reference[0])
    return approach, yaw, math.remainder(yaw+offset, 2*math.pi)


def run_forward_stages(*, graph, options: dict, station_xy: tuple, forward,
                       spin, poses, motion, settings, check, phase, wall_runtime) -> None:
    """모든 단계와 최종 정지가 확인되어야 반환한다. 취소·실패를 성공으로 변환하지 않는다."""
    approach, entry_yaw, exit_yaw = forward_geometry(graph, options, station_xy)
    if wall_runtime is None:
        raise ValueError('전진 정밀 접근 런타임 없음')
    retries = options.get('approach_retry_count', 0)
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 2:
        raise ValueError('approach_retry_count: 0~2 정수 필요')
    for attempt in range(retries+1):
        check()
        plan = forward.plan(approach)
        phase(f'APPROACH_STATION_FORWARD attempt={attempt+1} points={plan.points}')
        forward.navigate(approach, entry_yaw, route_plan=plan)
        motion.wait_stopped(check)
        current = poses.current(check)
        error = math.dist((current[0,3], current[1,3]), approach)
        phase(f'VERIFY_FORWARD_APPROACH distance={error:.4f}m')
        if error <= settings.arrival_tolerance_m:
            break
        if attempt == retries:
            raise RuntimeError('스테이션 접근 위치 오차 초과: 재접근 소진')
    align_options = dict(options, wall_reverse=options['wall_forward'])
    align_entry(entry_yaw, align_options, spin, poses, motion, settings, check,
                lambda text: phase(text.replace('REVERSE_ENTRY', 'FORWARD_ENTRY')))
    check()
    phase('FORWARD_WALL_APPROACH')
    # 최대 거리는 그래프 노드 간 거리와 별개다. 물리 도킹점은 라이다 티칭으로 결정한다.
    wall_runtime.execute(check, phase, options['wall_forward']['max_travel_m'])
    wall_runtime.stop()
    motion.wait_stopped(check)
    check()
    phase('ALIGN_STATION_EXIT')
    align_entry(exit_yaw, align_options, spin, poses, motion, settings, check,
                lambda text: phase(text.replace('REVERSE_ENTRY', 'STATION_EXIT')))
    check()
    motion.wait_stopped(check)
    phase('STATION_DOCKED_EXIT_ALIGNED')
