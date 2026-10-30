"""실물 복귀 그래프를 직선·후진 원호로 나눈다. 좌표는 입력 경로에서만 얻는다."""
from dataclasses import dataclass, replace
import math
import uuid
from farm_navigation.navigation_types import RoutePlan
from farm_navigation.route import RouteGraph, project
from farm_navigation.transfer_arc import ArcSpec, arc_path, wrap


@dataclass(frozen=True)
class Corner:
    approach: RoutePlan
    entry_yaw: float
    spec: ArcSpec
    nominal_exit: tuple[float, float]


def subroute(template: RoutePlan, points: list, *, headings: tuple | None = None,
             frame: str | None = None) -> RoutePlan:
    """원본 그래프 출처를 유지한 실행 경로(m/rad)를 만든다."""
    return replace(template, plan_id=uuid.uuid4().hex, points=tuple(points),
                   frame_id=frame or template.frame_id, headings=headings,
                   distance_m=sum(math.dist(a, b) for a, b in zip(points, points[1:])))


def split_corners(plan: RoutePlan, radius: float) -> tuple[list[Corner], RoutePlan]:
    """공선 중간점은 합치고 기존 ArcController가 지원하는 후진 좌회전만 계획한다."""
    ArcSpec(radius=radius)
    points: list[tuple[float, float]] = []
    for point in plan.points:
        if points and math.dist(points[-1], point) < 1e-9:
            continue
        points.append(point)
        while len(points) >= 3:
            a, b, c = points[-3:]
            first, second = math.atan2(b[1]-a[1], b[0]-a[0]), math.atan2(c[1]-b[1], c[0]-b[0])
            if abs(wrap(second-first)) > 1e-8:
                break
            points.pop(-2)
    if len(points) < 2:
        return [], plan
    corners = []
    start = points[0]
    for index in range(1, len(points)-1):
        a, vertex, b = points[index-1:index+2]
        incoming = math.atan2(vertex[1]-a[1], vertex[0]-a[0])
        outgoing = math.atan2(b[1]-vertex[1], b[0]-vertex[0])
        angle = wrap(outgoing-incoming)
        if not 0 < angle <= math.pi/2 + 1e-8:
            raise ValueError('기존 후진 원호는 좌회전 90도 이하 경로만 지원합니다.')
        spec = ArcSpec(radius=radius, angle=min(angle, math.pi/2))
        trim = radius * math.tan(spec.angle/2)
        entry = (vertex[0]-trim*math.cos(incoming), vertex[1]-trim*math.sin(incoming))
        exit_xy = (vertex[0]+trim*math.cos(outgoing), vertex[1]+trim*math.sin(outgoing))
        available = (vertex[0]-start[0])*math.cos(incoming)+(vertex[1]-start[1])*math.sin(incoming)
        if available <= trim or math.dist(vertex, b) <= trim:
            raise ValueError('그래프 선분이 원호 접선 길이보다 짧습니다.')
        corners.append(Corner(subroute(plan, [start, entry]), wrap(incoming+math.pi), spec, exit_xy))
        start = exit_xy
    return corners, subroute(plan, [start, points[-1]])


def anchored_arc(template: RoutePlan, origin: tuple, spec: ArcSpec, frame: str) -> RoutePlan:
    """정지한 실제 odom 자세를 원점으로 기존 원호 계산을 재사용한다."""
    poses = arc_path(origin, spec)
    return subroute(template, [p[:2] for p in poses], headings=tuple(p[2] for p in poses), frame=frame)


def split_graph_corners(plan: RoutePlan, radius: float, graph: RouteGraph) -> tuple[list[Corner], RoutePlan]:
    """역순 계획의 선택된 엣지로 실제 코너를 구하고 실측 시작점을 직선 진입에 연결한다."""
    edges = {edge.edge_id: edge for edge in graph.edges}
    selected = [edges[key] for key in plan.edge_ids]
    first, last = selected[0], selected[-1]
    # 후진 계획은 원본 방향 엣지의 역순이다. 끝점 투영으로 연결선을 코너에서 분리한다.
    start = project(plan.points[0], graph.nodes[first.end], graph.nodes[first.start])[2]
    end = project(plan.points[-1], graph.nodes[last.end], graph.nodes[last.start])[2]
    core = subroute(plan, [start, *[graph.nodes[e.start] for e in selected[:-1]], end])
    corners, tail = split_corners(core, radius)
    if not corners:
        return [], plan
    # 시작점은 실측값을 유지한다. 투영점으로 횡이동하거나 자세를 초기화하지 않는다.
    approach = corners[0].approach
    corners[0] = replace(corners[0], approach=subroute(approach, [plan.points[0], *approach.points[1:]]))
    return corners, subroute(tail, [*tail.points[:-1], plan.points[-1]])
