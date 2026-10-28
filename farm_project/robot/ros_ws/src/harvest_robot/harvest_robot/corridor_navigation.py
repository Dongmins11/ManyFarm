"""수확 직선 구간 중간 시작. 좌표는 설정 노드에서 읽고 전방 이동만 요청한다."""
import math
import uuid
from typing import Any
from farm_navigation.navigator import Navigator
from farm_navigation.navigation_types import RoutePlan
from farm_navigation.parallel_approach import straight_plan
from farm_navigation.route import project


def load_corridors(config: dict, graph: Any) -> dict:
    """명시적으로 지정한 직선 구간만 활성화한다. 기존 환경 기본 동작은 유지한다."""
    result = {}
    for section_id, section in config.get('sections', {}).items():
        nodes = section.get('work_corridor_nodes')
        if nodes is None:
            continue
        if not isinstance(nodes, list) or len(nodes) != 2:
            raise ValueError('work_corridor_nodes는 시작/끝 노드 두 개여야 합니다.')
        start, end = (graph.nodes[n] for n in nodes)
        if math.dist(start, end) < 1e-6:
            raise ValueError('작업 구간 길이는 0보다 커야 합니다.')
        yaw = math.atan2(end[1]-start[1], end[0]-start[0])
        entry = graph.nodes[section['entry_node']]
        heading = graph.nodes[section['entry_heading_node']]
        if project(entry, start, end)[0] > 1e-6 or abs(math.remainder(
                math.atan2(heading[1]-entry[1], heading[0]-entry[0])-yaw, 2*math.pi)) > 1e-6:
            raise ValueError('작업 구간과 기존 진입 위치/방향이 일치하지 않습니다.')
        result[section_id] = {'entry': start, 'exit': end, 'yaw': yaw}
    return result


def contains(corridor: dict, xy: tuple, margin: float) -> bool:
    """끝점까지 포함하되 진행 축의 구간 밖 위치는 제외한다."""
    a, b = corridor['entry'], corridor['exit']
    dx, dy = b[0]-a[0], b[1]-a[1]
    along = ((xy[0]-a[0])*dx+(xy[1]-a[1])*dy)/(dx*dx+dy*dy)
    return -1e-9 <= along <= 1+1e-9 and project(xy, a, b)[0] <= margin


class CorridorNavigator(Navigator):
    """기존 FollowPath/정지/도착 검사를 재사용하고 작업 경로 생성만 제한한다."""
    def __init__(self, *args: Any, corridors: dict,
                 path_heading_limit: float | None = None, **kwargs: Any) -> None:
        if path_heading_limit is not None and (
                isinstance(path_heading_limit, bool) or not isinstance(path_heading_limit, (int, float))
                or not math.isfinite(path_heading_limit) or not 0 < path_heading_limit < math.pi / 2):
            raise ValueError('work_path_heading_limit_rad는 0~pi/2 사이의 유한한 각도여야 합니다.')
        self._path_heading_limit = path_heading_limit
        super().__init__(*args, **kwargs)
        self._corridors = corridors

    def _corridor(self, goal: tuple, yaw: float | None = None) -> dict:
        matches = [c for c in self._corridors.values()
                   if project(goal, c['entry'], c['exit'])[0] <= self._settings.max_goal_distance_m
                   and contains(c, goal, self._settings.max_goal_distance_m)]
        if len(matches) != 1:
            raise RuntimeError('WORK_CORRIDOR_INVALID: 작업 목표가 지정된 직선 구간에 없습니다.')
        c = matches[0]
        if yaw is not None and abs(math.remainder(yaw-c['yaw'], 2*math.pi)) > self._settings.heading_tolerance_rad:
            raise RuntimeError('WORK_DIRECTION_INVALID: 목표 방향이 작업 구간 진행 방향과 다릅니다.')
        return c

    def _plan_current(self, corridor: dict, goal: tuple) -> RoutePlan:
        current = self._poses.current(self._check)
        xy = (float(current[0, 3]), float(current[1, 3]))
        if not contains(corridor, xy, self._settings.max_start_distance_m):
            raise RuntimeError('WORK_CORRIDOR_INVALID: 현재 위치가 작업 구간을 벗어났습니다.')
        direction = (math.cos(corridor['yaw']), math.sin(corridor['yaw']))
        if sum((goal[i]-xy[i])*direction[i] for i in (0, 1)) <= 0:
            raise RuntimeError('WORK_TARGET_NOT_AHEAD: 목표가 현재 위치의 전방이 아닙니다. 회전/후진은 요청하지 않았습니다.')
        template = RoutePlan(uuid.uuid4().hex, self._graph.revision, self._graph.frame, (), (), 0.)
        return straight_plan(template, corridor, xy, math.atan2(current[1, 0], current[0, 0]),
                             goal, self._settings.arrival_tolerance_m, self._settings.heading_tolerance_rad,
                             path_heading_limit=self._path_heading_limit)

    def resume_current(self, section_id: str, goal: tuple, yaw: float) -> bool:
        """이동 요청 전에 구간 안이면 전방/방향 검증 후 진입 단계 생략을 허용한다."""
        corridor = self._corridors.get(section_id)
        if corridor is None:
            return False
        current = self._poses.current(self._check)
        xy = (float(current[0, 3]), float(current[1, 3]))
        if not contains(corridor, xy, self._settings.max_start_distance_m):
            return False
        if self._corridor(goal, yaw) is not corridor:
            raise RuntimeError('WORK_CORRIDOR_INVALID: 요청 화단과 목표 구간이 다릅니다.')
        self._plan_current(corridor, goal)
        return True

    def navigate(self, xy: Any, yaw: float) -> Any:
        self._corridor(tuple(xy), yaw)
        return super().navigate(xy, yaw)

    def plan(self, goal: tuple) -> RoutePlan:
        return self._plan_current(self._corridor(goal), goal)
