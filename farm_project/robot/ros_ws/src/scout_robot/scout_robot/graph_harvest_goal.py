"""선택된 그래프 직선으로 수확 정차선을 정한다. 기존 작업창 범위/팔 치수는 유지."""
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import math
from .b_planner import Config


@dataclass(frozen=True)
class GraphLineConfig(Config):
    graph_normal_m: float = 0.0

    @property
    def route_y(self) -> float:
        """베드 좌표계에서 그래프 주행선의 법선 거리(m)."""
        return self.graph_normal_m


def load_harvest_route(root: Path, cfg: dict) -> list | None:
    """옵션이 없으면 그래프를 읽지 않는다. map의 연결된 노드 순서를 검증한다."""
    goal = cfg.get('harvest_goal', {})
    if goal.get('mode', 'window_offset') != 'graph_line':
        return None
    from farm_navigation.route import load_route
    return load_route(root / goal['route_file'], goal['node_ids'])


def constrain_to_graph(bed: Any, route: list | None) -> GraphLineConfig:
    """현재 직선 베드와 평행·동일 진행 방향인 경로만 지원한다. 범위 밖 목표는 기존 hold 처리."""
    if route is None or len(route) < 2:
        raise ValueError('graph_line requires a connected harvest route')
    coords = [bed.local([x, y, 0.0]) for _, x, y, _ in route]
    normal = coords[0][1]
    if any(not all(math.isfinite(v) for v in p) for p in coords):
        raise ValueError('Harvest graph contains non-finite coordinates')
    if any(abs(p[1] - normal) > 1e-6 for p in coords):
        raise ValueError('Harvest graph must be straight and parallel to survey bed')
    if any(b[0] <= a[0] for a, b in zip(coords, coords[1:])):
        raise ValueError('Harvest graph must follow survey direction')
    if abs(math.remainder(bed.harvest_yaw-bed.yaw, 2*math.pi)) > 1e-6:
        raise ValueError('Graph goal heading must follow the selected route')
    values = asdict(bed.plan_cfg)
    values.update(route_start=coords[0][0], route_end=coords[-1][0], graph_normal_m=normal)
    result = GraphLineConfig(**values)
    result.validate()
    if bed.bed_n - normal - result.mount_y <= 0:
        raise ValueError('Harvest arm must remain on the approach side of the bed')
    return result
