"""방향 그래프의 엣지 중간 목표까지 탐색. 미니관제 RouteToPose를 일반화했습니다."""
from __future__ import annotations
import hashlib
import heapq
import itertools
import json
import math
from pathlib import Path
import uuid
from dataclasses import dataclass, replace
from .navigation_types import RoutePlan

Point = tuple[float, float]
NodeId = int | str


def reverse_plan(plan: RoutePlan) -> RoutePlan:
    """계획의 점·엣지 순서만 뒤집는다. 방향 그래프 재탐색이나 주행 실행은 하지 않는다."""
    return replace(plan, plan_id=uuid.uuid4().hex,
                   points=tuple(reversed(plan.points)), edge_ids=tuple(reversed(plan.edge_ids)))


@dataclass(frozen=True)
class Edge:
    edge_id: str
    start: NodeId
    end: NodeId


def project(point: Point, a: Point, b: Point) -> tuple[float, float, Point]:
    """선분 투영 거리(m), 진행 비율[0,1], 투영점을 반환합니다."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ratio = max(0., min(1., ((point[0]-a[0])*dx + (point[1]-a[1])*dy)/(dx*dx+dy*dy)))
    projected = (a[0]+ratio*dx, a[1]+ratio*dy)
    return math.dist(point, projected), ratio, projected


class RouteGraph:
    def __init__(self, path: str | Path, frame: str = 'map') -> None:
        raw = Path(path).read_bytes()
        data = json.loads(raw)
        if data.get('type') != 'FeatureCollection':
            raise ValueError('GeoJSON FeatureCollection 필요')
        self.parallel_corridors = data.get('metadata', {}).get('parallel_approach_corridors', [])
        self.frame: str = frame
        self.revision: str = hashlib.sha256(raw).hexdigest()
        self.node_sections: dict[NodeId, str] = {}
        self.nodes: dict[NodeId, Point] = {}
        self.edges: list[Edge] = []
        for feature in data['features']:
            geom, props = feature['geometry'], feature['properties']
            if geom['type'] != 'Point':
                continue
            key = props['id']
            if isinstance(key, bool) or not isinstance(key, (int, str)) or key in self.nodes:
                raise ValueError(f'잘못되었거나 중복된 노드 ID: {key}')
            if props.get('frame', frame) != frame:
                raise ValueError('노드 좌표계 불일치')
            point = tuple(map(float, geom['coordinates'][:2]))
            if len(point) != 2 or not all(map(math.isfinite, point)):
                raise ValueError('노드 좌표는 유한한 평면 m 좌표여야 합니다.')
            self.nodes[key] = point
            section = props.get('section', props.get('metadata', {}).get('section'))
            if isinstance(section, str) and section.strip():
                self.node_sections[key] = section
        identifiers: set[str] = set()
        for feature in data['features']:
            geom, props = feature['geometry'], feature['properties']
            if geom['type'] not in ('LineString', 'MultiLineString'):
                continue
            a, b = props['startid'], props['endid']
            if a not in self.nodes or b not in self.nodes or math.dist(self.nodes[a], self.nodes[b]) < 1e-6:
                raise ValueError(f'엣지 끝점이 없거나 길이가 0입니다: {a} → {b}')
            # 현재 계약은 노드 사이 직선 엣지. 곡선 형상을 조용히 직선으로 바꾸지 않습니다.
            lines = [geom['coordinates']] if geom['type']=='LineString' else geom['coordinates']
            if len(lines) != 1 or len(lines[0]) < 2:
                raise ValueError('연속된 단일 직선 엣지 형상이 필요합니다.')
            points = [tuple(map(float, p[:2])) for p in lines[0]]
            if any(len(p)!=2 or not all(map(math.isfinite,p)) for p in points):
                raise ValueError('엣지 형상에 유효하지 않은 좌표가 있습니다.')
            if math.dist(points[0],self.nodes[a])>1e-5 or math.dist(points[-1],self.nodes[b])>1e-5:
                raise ValueError(f'엣지 형상과 노드 좌표가 다릅니다: {a} → {b}')
            if any(project(p,self.nodes[a],self.nodes[b])[0]>1e-5 for p in points):
                raise ValueError('현재 경로 계산은 직선 엣지 형상을 지원합니다.')
            eid = str(props.get('id', f'{a}->{b}'))
            if eid in identifiers:
                raise ValueError(f'중복 엣지 ID: {eid}')
            identifiers.add(eid)
            self.edges.append(Edge(eid,a,b))
        if not self.nodes or not self.edges:
            raise ValueError('그래프에 노드와 엣지가 필요합니다.')
        self._adj: dict[NodeId,list[Edge]] = {n:[] for n in self.nodes}
        for edge in self.edges:
            self._adj[edge.start].append(edge)

    def _candidates(self, point: Point, limit: float) -> list[tuple[Edge,float,float,Point]]:
        if not all(map(math.isfinite, point)) or not math.isfinite(limit) or limit <= 0:
            raise ValueError('위치와 그래프 대응 허용값이 유효하지 않습니다.')
        items = [(e,*project(point,self.nodes[e.start],self.nodes[e.end])) for e in self.edges]
        items = [item for item in items if item[1] <= limit]
        if not items:
            raise ValueError(f'위치 {point}가 그래프에서 {limit}m 이상 떨어져 있습니다.')
        nearest = min(item[1] for item in items)
        return [item for item in items if item[1] <= nearest+1e-5]

    def section_at(self, xy: Point, yaw: float, max_distance: float, heading_tolerance: float) -> str | None:
        """반복 태그 구역은 가장 가까운 작업 엣지와 실제 차체 방향이 맞을 때만 선택한다."""
        try:
            candidates = self._candidates(xy, max_distance)
        except ValueError:
            return None
        sections = set()
        for edge, _, _, _ in candidates:
            a, b = self.nodes[edge.start], self.nodes[edge.end]
            heading = math.atan2(b[1]-a[1], b[0]-a[0])
            section = self.node_sections.get(edge.start)
            if (section is not None and section == self.node_sections.get(edge.end)
                    and abs(math.remainder(yaw-heading, 2*math.pi)) <= heading_tolerance):
                sections.add(section)
        return next(iter(sections)) if len(sections) == 1 else None

    def plan(self, start: Point, goal: Point, max_start: float=.10, max_goal: float=.02) -> RoutePlan:
        """거리 기반 다익스트라 탐색. 교통·장애물 비용이나 진입 허가는 포함하지 않습니다."""
        starts, goals = self._candidates(start,max_start), self._candidates(goal,max_goal)
        best: tuple[float,list[Point],list[str]] | None = None
        order = itertools.count()  # 같은 비용에서 문자열/숫자 노드 ID를 비교하지 않도록 합니다.
        for edge, distance, ratio, snapped in starts:
            for target, tail, target_ratio, endpoint in goals:
                if edge.edge_id==target.edge_id and ratio<=target_ratio:
                    candidate=(distance+math.dist(snapped,endpoint)+tail,[start,snapped,endpoint,goal],[edge.edge_id])
                    if best is None or candidate[0]<best[0]: best=candidate
            queue=[(distance+math.dist(snapped,self.nodes[edge.end]),next(order),edge.end,[start,snapped,self.nodes[edge.end]],[edge.edge_id])]
            seen: set[NodeId] = set()
            while queue:
                cost, _, node, points, used = heapq.heappop(queue)
                if node in seen: continue
                seen.add(node)
                for target, tail, _, endpoint in goals:
                    if node==target.start:
                        candidate=(cost+math.dist(self.nodes[node],endpoint)+tail,points+[endpoint,goal],used+[target.edge_id])
                        if best is None or candidate[0]<best[0]: best=candidate
                for following in self._adj[node]:
                    if following.end not in seen:
                        heapq.heappush(queue,(cost+math.dist(self.nodes[node],self.nodes[following.end]),next(order),following.end,points+[self.nodes[following.end]],used+[following.edge_id]))
        if best is None:
            raise ValueError('목표까지 연결되는 방향 경로가 없습니다. 그래프 연결을 확인하세요.')
        clean: list[Point] = []
        for point in best[1]:
            if not clean or math.dist(clean[-1],point)>1e-7: clean.append(point)
        return RoutePlan(uuid.uuid4().hex,self.revision,self.frame,tuple(clean),tuple(best[2]),best[0])


def load_route(path: str | Path, node_ids: list[NodeId], frame: str='map') -> list[tuple[NodeId,float,float,float]]:
    """기존 직선 베드 정의용 노드 순서를 유지합니다. 새 경로 탐색과 별개입니다."""
    graph=RouteGraph(path,frame)
    if len(node_ids)<2 or len(set(node_ids))!=len(node_ids):
        raise ValueError('경로 노드는 중복 없이 2개 이상 필요합니다.')
    pairs={(e.start,e.end) for e in graph.edges}
    for a,b in zip(node_ids,node_ids[1:]):
        if (a,b) not in pairs: raise ValueError(f'경로 연결이 없습니다: {a} → {b}')
    points=[graph.nodes[n] for n in node_ids]
    output=[]
    for i,(x,y) in enumerate(points):
        a,b=(points[i],points[i+1]) if i+1<len(points) else (points[i-1],points[i])
        output.append((node_ids[i],x,y,math.atan2(b[1]-a[1],b[0]-a[0])))
    return output
