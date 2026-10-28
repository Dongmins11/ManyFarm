"""Exact rectangular-cell clearance with bounded continuous swept-footprint checks.

Input poses define constant-twist (circular, or straight) segments. This matches
transfer_arc.arc_path. Padding is already present in the published footprint.
This preflight never replaces Nav2's live collision checking.
"""
import math
import numpy as np

class ObstacleBlocked(RuntimeError):
    """경로에 장애물/unknown 셀이 접촉함. 계산·입력 오류와 구분한다."""


_EPS = 1e-9
_MAX_DEPTH = 16
_MAX_EVALUATIONS = 20000


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def _midpoint(a, b):
    angle = _wrap(b[2] - a[2])
    chord = np.asarray(b[:2]) - a[:2]
    # Circular midpoint; straight translation is the angle -> 0 limit.
    middle = (np.asarray(a[:2]) + b[:2]) / 2
    middle -= np.array([-chord[1], chord[0]]) * (.5 * math.tan(angle / 4))
    return np.array([middle[0], middle[1], a[2] + angle / 2])


def _half_motion_bound(a, b, radius):
    angle = abs(_wrap(b[2] - a[2]))
    chord = math.hypot(b[0] - a[0], b[1] - a[1])
    length = chord if angle < 1e-8 else chord * angle / (2 * math.sin(angle / 2))
    return (length + radius * angle) / 2


def _cell_distance(pose, half, centers, resolution):
    """Minimum distance of a rectangle and closed square cells; touching is 0."""
    if not len(centers):
        return math.inf
    x, y, yaw = pose
    c, s = math.cos(yaw), math.sin(yaw)
    rot = np.array([[c, -s], [s, c]])
    delta = centers - [x, y]
    local = delta @ rot
    extent = resolution / 2 * (abs(c) + abs(s))
    hit = (abs(local[:, 0]) <= half[0] + extent) & (abs(local[:, 1]) <= half[1] + extent)
    hit &= abs(delta[:, 0]) <= abs(c) * half[0] + abs(s) * half[1] + resolution / 2
    hit &= abs(delta[:, 1]) <= abs(s) * half[0] + abs(c) * half[1] + resolution / 2
    if np.any(hit):
        return 0.
    signs = np.array([[-1, -1], [-1, 1], [1, 1], [1, -1]])
    cell_vertices = centers[:, None, :] + signs[None, :, :] * resolution / 2
    relative = (cell_vertices - [x, y]) @ rot
    first = np.linalg.norm(np.maximum(abs(relative) - half, 0), axis=2)
    robot_vertices = (signs * half) @ rot.T + [x, y]
    second = np.linalg.norm(np.maximum(abs(robot_vertices[None, :, :] - centers[:, None, :]) - resolution / 2, 0), axis=2)
    return float(min(first.min(), second.min()))


def check_grid(poses: list, footprint: list, current: tuple, grid: dict) -> float:
    path = np.asarray(poses, dtype=float)
    current = np.asarray(current, dtype=float)
    vertices = np.asarray(footprint, dtype=float)
    if path.ndim != 2 or path.shape[1:] != (3,) or len(path) < 2 or not np.isfinite(path).all():
        raise ValueError('유효한 경로 자세가 두 개 이상 필요합니다.')
    if current.shape != (3,) or not np.isfinite(current).all():
        raise ValueError('현재 자세 오류')
    if vertices.shape != (4, 2) or not np.isfinite(vertices).all():
        raise ValueError('이번 시험은 사각 footprint만 지원합니다.')
    c, s = math.cos(current[2]), math.sin(current[2])
    local = (vertices - current[:2]) @ np.array([[c, -s], [s, c]])
    half = np.max(abs(local), axis=0)
    if np.min(half) <= 0 or not np.allclose(abs(local), half, atol=.001):
        raise ValueError('중심 대칭 사각 footprint 확인 실패')
    if len(np.unique(np.sign(local), axis=0)) != 4:
        raise ValueError('footprint 모서리 중복')
    md = grid['metadata']; res = float(md['resolution'])
    nx, ny = md['size_x'], md['size_y']
    origin = md['origin']['position']; q = md['origin']['orientation']
    values = [res, origin['x'], origin['y'], q['x'], q['y'], q['z'], q['w']]
    if not all(math.isfinite(v) for v in values) or res <= 0 or nx <= 0 or ny <= 0:
        raise ValueError('costmap 규격 오류')
    if abs(q['x']) + abs(q['y']) + abs(q['z']) > 1e-6 or abs(abs(q['w']) - 1) > 1e-6:
        raise ValueError('회전된 costmap은 지원하지 않습니다.')
    raw = np.asarray(grid['data'])
    if raw.size != nx * ny or not np.isfinite(raw).all() or np.any(raw < 0) or np.any(raw > 255) or np.any(raw != np.floor(raw)):
        raise ValueError('costmap 셀 값 오류')
    cells = raw.reshape(ny, nx)
    iy, ix = np.where(cells >= 254)  # unknown remains blocked.
    centers = np.column_stack((origin['x'] + (ix + .5) * res, origin['y'] + (iy + .5) * res))
    radius = float(np.linalg.norm(half))
    evaluations = 0

    def clearance(p):
        nonlocal evaluations
        evaluations += 1
        if evaluations > _MAX_EVALUATIONS:
            raise RuntimeError('곡선 검사 계산 한도 초과: 안전 여유 확인 불가')
        c, s = math.cos(p[2]), math.sin(p[2])
        extent = np.array([abs(c)*half[0]+abs(s)*half[1], abs(s)*half[0]+abs(c)*half[1]])
        boundary = min(p[0]-extent[0]-origin['x'], origin['x']+nx*res-p[0]-extent[0],
                       p[1]-extent[1]-origin['y'], origin['y']+ny*res-p[1]-extent[1])
        if boundary <= _EPS:
            raise RuntimeError('시험 경로 footprint가 costmap 경계와 접촉/이탈합니다.')
        distance = _cell_distance(p, half, centers, res)
        if distance <= _EPS:
            raise ObstacleBlocked('경로의 장애물/unknown 셀과 footprint 접촉/겹침')
        return min(boundary, distance)

    for p in path:
        clearance(p)

    def segment(a, b, depth):
        if abs(_wrap(b[2]-a[2])) > math.pi/2 + _EPS:
            raise ValueError('곡선 검사 구간 각도가 너무 큽니다.')
        middle = _midpoint(a, b)
        distance = clearance(middle)
        lower = distance - _half_motion_bound(a, b, radius)
        if lower > _EPS:
            return lower
        if depth >= _MAX_DEPTH:
            raise RuntimeError('곡선 구간 여유 확인 불가: 세분화 한도')
        return min(segment(a, middle, depth+1), segment(middle, b, depth+1))

    return float(min(segment(a, b, 0) for a, b in zip(path, path[1:])))
