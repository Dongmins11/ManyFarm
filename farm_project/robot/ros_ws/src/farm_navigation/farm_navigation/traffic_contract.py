"""교통 계약의 로컬 자료 검사. 예약·허가의 최종 판단은 관제에서 수행한다."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import fcntl
import hashlib
import math
import sqlite3
import yaml
from .route import RouteGraph, project


class TrafficIds:
    """로봇별 ID 발급 번호를 커밋한 뒤 반환한다. 같은 로봇의 중복 실행은 거절한다."""
    def __init__(self, path: Path, robot_id: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = open(str(path) + '.lock', 'a')
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            raise RuntimeError('같은 로봇의 교통 프로세스가 이미 실행 중입니다.')
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute('CREATE TABLE IF NOT EXISTS ids (robot TEXT, kind TEXT, value INTEGER, PRIMARY KEY(robot, kind))')
        self._robot = robot_id

    def next(self, kind: str) -> str:
        if kind not in ('boot', 'req', 'query'):
            raise ValueError('로봇이 발급할 수 없는 교통 ID')
        with self._db:
            self._db.execute('INSERT INTO ids VALUES (?, ?, 1) ON CONFLICT(robot,kind) DO UPDATE SET value=value+1', (self._robot, kind))
            number = self._db.execute('SELECT value FROM ids WHERE robot=? AND kind=?', (self._robot, kind)).fetchone()[0]
        return f'{kind}_{number:0{2 if kind == "boot" else 3}d}'

    def close(self) -> None:
        self._db.close()
        self._lock.close()


@dataclass(frozen=True)
class TrafficRoute:
    nodes: tuple[str, ...]
    edges: tuple[str, ...]
    hold: frozenset[str] = frozenset()


class TrafficRegistry:
    """등록 파일과 실제 그래프를 대조하고 실행 경로를 원래 노드/엣지 ID로 대응한다."""
    def __init__(self, filename: Path, graph: RouteGraph, robot_id: str) -> None:
        self.data = yaml.safe_load(filename.read_text())
        self.graph = graph
        self.participant = self.data['participants'][robot_id]
        self.graph_id = self.participant['graph_id']
        self.graph_config = self.data['graphs'][self.graph_id]
        source = filename.parent / self.graph_config['source_file']
        if hashlib.sha256(source.read_bytes()).hexdigest() != graph.revision:
            raise ValueError('교통 등록 그래프와 실행 그래프의 파일 해시가 다릅니다.')
        self.zones = self.data['zones']
        self.profile = self.data['footprint_profiles'][self.participant['footprint_profile_id']]
        self.edges = {e.edge_id: e for e in graph.edges}
        self.nodes = {str(n): n for n in graph.nodes}

    def route(self, points: list[tuple[float, float]], tolerance: float) -> TrafficRoute:
        """실행 선분을 1cm 간격으로 검사한다. 방향/연결 불명인 경로는 승인 요청도 하지 않는다."""
        if not points or any(not all(map(math.isfinite, p)) for p in points):
            raise ValueError('교통 요청 경로 좌표 오류')
        # 위치추정 오차를 잇는 짧은 시작/끝 연결선은 인접 주행 엣지의 점유에 포함한다.
        # 전체 경로를 가장 가까운 다른 차선으로 이동시키지는 않는다.
        graph_points = list(points)
        def on_graph(point: tuple[float,float]) -> bool:
            return any(project(point,self.graph.nodes[e.start],self.graph.nodes[e.end])[0] <= 1e-6 for e in self.graph.edges)
        first = next((i for i,p in enumerate(graph_points) if on_graph(p)), None)
        last = next((i for i in range(len(graph_points)-1,-1,-1) if on_graph(graph_points[i])), None)
        if first is None or last is None:
            raise ValueError('실행 경로가 등록 그래프와 연결되지 않습니다.')
        if (sum(math.dist(a,b) for a,b in zip(graph_points[:first+1],graph_points[1:first+1])) > tolerance
            or sum(math.dist(a,b) for a,b in zip(graph_points[last:],graph_points[last+1:])) > tolerance):
            raise ValueError('그래프 시작/끝 연결선이 위치 허용 범위를 넘습니다.')
        graph_points = graph_points[first:last+1]
        used = []
        for a, b in zip(graph_points, graph_points[1:]):
            distance = math.dist(a, b)
            if distance < 1e-7:
                continue
            direction = (b[0]-a[0], b[1]-a[1])
            count = max(1, math.ceil(distance/.01))
            for i in range(count):
                t = (i+.5)/count
                p = (a[0]+direction[0]*t, a[1]+direction[1]*t)
                candidates = []
                for e in self.graph.edges:
                    x, y = self.graph.nodes[e.start], self.graph.nodes[e.end]
                    dot = direction[0]*(y[0]-x[0])+direction[1]*(y[1]-x[1])
                    if dot <= 0:
                        continue
                    d, ratio, _ = project(p, x, y)
                    # 끝점 밖으로 투영된 다른 통로를 연속 경로로 오인하지 않는다.
                    along = ((p[0]-x[0])*(y[0]-x[0])+(p[1]-x[1])*(y[1]-x[1]))/math.dist(x,y)**2
                    if d <= tolerance and -1e-6 <= along <= 1+1e-6:
                        candidates.append((d, e))
                if not candidates:
                    raise ValueError('실행 경로를 등록 그래프에 대응할 수 없습니다.')
                candidates.sort(key=lambda item:item[0])
                near = [e for d,e in candidates if d <= candidates[0][0]+1e-6]
                if used:
                    contiguous = [e for e in near if e == used[-1] or e.start == used[-1].end]
                    near = contiguous or near
                if len(near) != 1:
                    raise ValueError('실행 경로의 교통 엣지가 모호합니다.')
                e = near[0]
                if not used or used[-1] != e:
                    if used and used[-1].end != e.start:
                        raise ValueError('실행 경로의 교통 엣지가 연결되지 않습니다.')
                    used.append(e)
        if not used:
            near = [str(n) for n,p in self.graph.nodes.items() if math.dist(p,points[0]) <= 1e-5]
            if len(near) != 1:
                raise ValueError('정차 요청은 명확한 그래프 노드가 필요합니다.')
            return TrafficRoute(tuple(near), ())
        nodes = [str(used[0].start)] + [str(e.end) for e in used]
        hold = set()
        # 수확 구간은 작업 중간 목표라도 출구까지 예약한다. 원래 실행 목표는 바꾸지 않는다.
        for section in self.data.get('harvest_work_sections', {}).values():
            if section['graph_id'] != self.graph_id:
                continue
            work_nodes = {ref['node_id'] for z in section['hold_zone_ids']
                          for ref in self.zones[z]['graph_refs'] if 'node_id' in ref}
            if nodes[-1] in work_nodes:
                exit_id = section['exit_node_id']
                if nodes[-1] != exit_id:
                    tail = self.graph.plan(self.graph.nodes[self.nodes[nodes[-1]]], self.graph.nodes[self.nodes[exit_id]])
                    for eid in tail.edge_ids:
                        edge = self.edges[eid]
                        if str(edge.start) == nodes[-1] and str(edge.end) != nodes[-1]:
                            used.append(edge); nodes.append(str(edge.end))
                    if nodes[-1] != exit_id:
                        raise ValueError('수확 출구까지 예약 경로를 연결하지 못했습니다.')
                hold.update(section['hold_zone_ids'])
        mapping = self.data['graph_mappings'][self.graph_id]
        resources = {mapping['node_to_zone'][n] for n in nodes}
        resources.update(mapping['edge_to_zone'][e.edge_id] for e in used)
        for section in self.data.get('harvest_work_sections', {}).values():
            if section['graph_id'] == self.graph_id and resources.intersection(section['hold_zone_ids']):
                hold.update(section['hold_zone_ids'])
                hold.add(mapping['node_to_zone'][section['exit_node_id']])
        return TrafficRoute(tuple(nodes), tuple(e.edge_id for e in used), frozenset(hold))

    def blocked_work_edges(self, blocked_nodes: tuple[str, ...], blocked_edges: tuple[str, ...]) -> frozenset[str]:
        """작업 구간 출구/예약 공간이 막히면 그 구간으로 들어가는 후보 엣지도 제외한다."""
        mapping = self.data['graph_mappings'][self.graph_id]
        blocked = {mapping['node_to_zone'][n] for n in blocked_nodes}
        blocked.update(mapping['edge_to_zone'][e] for e in blocked_edges)
        excluded = set(blocked_edges)
        for section in self.data.get('harvest_work_sections', {}).values():
            if section['graph_id'] != self.graph_id:
                continue
            hold = set(section['hold_zone_ids'])
            resources = hold | {mapping['node_to_zone'][section['exit_node_id']]}
            if not resources & blocked:
                continue
            for edge in self.graph.edges:
                arc = {mapping['node_to_zone'][str(edge.start)],
                       mapping['node_to_zone'][str(edge.end)], mapping['edge_to_zone'][edge.edge_id]}
                if arc & hold:
                    excluded.add(edge.edge_id)
        return frozenset(excluded)

    def occupied(self, x: float, y: float, yaw: float) -> set[str]:
        """회전한 여유 포함 차체와 구역 사각형의 SAT 교차. 접촉도 점유로 보고한다."""
        p = self.profile
        hx = p['length_m']/2+p['margin_each_side_m']
        hy = p['width_m']/2+p['margin_each_side_m']
        c, s = math.cos(yaw), math.sin(yaw)
        result = set()
        for zid,z in self.zones.items():
            xmin,ymin,xmax,ymax = z['bounds_m']
            dx,dy = (xmin+xmax)/2-x, (ymin+ymax)/2-y
            ax,ay = (xmax-xmin)/2, (ymax-ymin)/2
            if (abs(dx) <= ax+abs(c)*hx+abs(s)*hy+1e-9
                and abs(dy) <= ay+abs(s)*hx+abs(c)*hy+1e-9
                and abs(dx*c+dy*s) <= hx+ax*abs(c)+ay*abs(s)+1e-9
                and abs(-dx*s+dy*c) <= hy+ax*abs(s)+ay*abs(c)+1e-9):
                result.add(zid)
        return result
