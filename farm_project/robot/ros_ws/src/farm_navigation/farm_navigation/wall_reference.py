"""정지 라이다 기록의 벽 거리·방향 분석. ROS/로봇 종류와 무관하며 명령을 발행하지 않는다."""

from __future__ import annotations
from functools import lru_cache
import argparse
import json
import math
from pathlib import Path
import numpy as np


def scan_points(record: dict, sector_deg: tuple[float, float]) -> np.ndarray:
    """센서 점을 기록된 TF로 base 좌표에 옮긴 뒤 base 방위각으로 영역을 선택한다."""
    lo, hi = sector_deg
    if not (-180 <= lo < hi <= 180):
        raise ValueError('영역은 -180 <= 시작 < 끝 <= 180도여야 합니다.')
    scan = record['scan']
    values = np.array([np.nan if x is None else x for x in scan['ranges']], dtype=float)
    if not math.isfinite(scan['angle_increment']) or scan['angle_increment'] == 0:
        raise ValueError('라이다 각도 간격 오류')
    angle = scan['angle_min'] + np.arange(len(values)) * scan['angle_increment']
    valid = np.isfinite(values) & (values >= scan['range_min']) & (values <= scan['range_max'])
    points = np.array([values[valid]*np.cos(angle[valid]), values[valid]*np.sin(angle[valid]),
                       np.zeros(valid.sum()), np.ones(valid.sum())])
    matrix = np.asarray(record['base_from_scan'], dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError('TF 행렬 오류')
    points = (matrix @ points).T[:, :2]
    bearings = np.degrees(np.arctan2(points[:, 1], points[:, 0]))
    return points[(bearings >= lo) & (bearings <= hi)]


@lru_cache(maxsize=16)
def _candidate_pairs(n: int) -> np.ndarray:
    """동일 점 개수에 대한 기존 seed/160회 후보 선택 순서를 재사용한다."""
    rng=np.random.default_rng(0)
    pairs=np.array([rng.choice(n,2,replace=False) for _ in range(160)])
    pairs.flags.writeable=False
    return pairs


def fit_wall(points: np.ndarray, threshold_m: float = .01, min_points: int = 20,
             min_ratio: float = .8, min_span_m: float = .15) -> dict:
    """고정 seed 후보 직선과 TLS 정제. 결과는 벽 후보이며 화단의 자동 식별이 아니다."""
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or not np.isfinite(p).all():
        raise ValueError('유효한 2차원 점 필요')
    if not (math.isfinite(threshold_m) and threshold_m > 0 and min_points >= 3
            and 0 < min_ratio <= 1 and math.isfinite(min_span_m) and min_span_m > 0):
        raise ValueError('직선 분석 설정 오류')
    if len(p) < min_points:
        raise ValueError('벽 후보 점 부족')
    pairs = _candidate_pairs(len(p))
    aa=p[pairs[:,0]];d=p[pairs[:,1]]-aa
    lengths=np.linalg.norm(d,axis=1)
    valid=lengths>=min_span_m/3
    normals=np.column_stack((-d[:,1],d[:,0]))/np.where(lengths>0,lengths,1)[:,None]
    diff=p[None,:,:]-aa[:,None,:]
    masks=np.abs(diff[:,:,0]*normals[:,None,0]+diff[:,:,1]*normals[:,None,1])<=threshold_m
    masks[~valid]=False
    counts=masks.sum(axis=1)
    best=masks[int(np.argmax(counts))].copy()
    if best.sum() < min_points or best.mean() < min_ratio:
        raise ValueError('단일 벽 지지율 부족: 영역 선택 확인 필요')
    for _ in range(3):
        selected = p[best]
        center = selected.mean(axis=0)
        _, _, vh = np.linalg.svd(selected-center, full_matrices=False)
        normal = vh[-1]
        distance = float(center @ normal)
        if distance < 0:
            normal = -normal
            distance = -distance
        best = np.abs(p @ normal-distance) <= threshold_m
        if best.sum() < min_points or best.mean() < min_ratio:
            raise ValueError('정제 후 벽 지지율 부족')
    tangent = np.array([-normal[1], normal[0]])
    span = float(np.ptp(p[best] @ tangent))
    if span < min_span_m or distance <= threshold_m:
        raise ValueError('벽 길이 또는 거리 부족')
    return {'distance_m': distance, 'normal_angle_rad': float(math.atan2(normal[1], normal[0])),
            'normal_xy': normal.tolist(), 'inlier_count': int(best.sum()), 'point_count': len(p),
            'inlier_ratio': float(best.mean()), 'span_m': span,
            'residual_rms_m': float(np.sqrt(np.mean((p[best] @ normal-distance)**2)))}


def footprint_gap(wall: dict, vertices: list) -> float:
    """base 기준 실제 외곽 꼭짓점과 무한 벽 직선 사이 간격. 충돌 안전 판정은 아니다."""
    p = np.asarray(vertices, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('base 기준 외곽 꼭짓점 필요')
    return float(wall['distance_m'] - np.max(p @ np.asarray(wall['normal_xy'])))


def summarize(records: list[dict], sector: tuple[float, float], threshold_m: float = .01) -> dict:
    """개별 프레임 실패도 보존. 자동 운영 목표 승인이나 위치 복원을 수행하지 않는다."""
    results, failures = [], []
    previous = -1
    for index, record in enumerate(records):
        try:
            stamp = record['stamp_ns']
            if stamp <= previous:
                raise ValueError('중복 또는 역행 라이다 시각')
            previous = stamp
            result = fit_wall(scan_points(record, sector), threshold_m)
            result['stamp_ns'] = stamp
            results.append(result)
        except (ValueError, KeyError) as error:
            failures.append({'index': index, 'reason': str(error)})
    if not results:
        raise ValueError('분석 가능한 벽 프레임 없음')
    distances = np.array([r['distance_m'] for r in results])
    angles = np.array([r['normal_angle_rad'] for r in results])
    mean_angle = math.atan2(float(np.sin(angles).mean()), float(np.cos(angles).mean()))
    delta = np.arctan2(np.sin(angles-mean_angle), np.cos(angles-mean_angle))
    return {'schema_version': 1, 'approved_for_motion': False,
            'meaning': '벽 거리·방향 후보. 원래 그래프 위치 복원 증거가 아님',
            'sector_base_deg': list(sector), 'fit_threshold_m': threshold_m,
            'accepted_frames': len(results), 'rejected_frames': failures,
            'distance_median_m': float(np.median(distances)),
            'distance_p05_p95_m': np.percentile(distances, [5,95]).tolist(),
            'normal_angle_rad': mean_angle, 'angle_std_rad': float(np.std(delta)),
            'frames': results}


def main() -> None:
    parser = argparse.ArgumentParser(description='라이다 벽 후보 오프라인 분석. 이동 없음')
    parser.add_argument('capture', type=Path)
    parser.add_argument('--sector', nargs=2, type=float, required=True, metavar=('MIN_DEG','MAX_DEG'))
    parser.add_argument('--threshold', type=float, default=.01)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.capture.open() as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    report = summarize(records, tuple(args.sector), args.threshold)
    with args.output.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k:v for k,v in report.items() if k != 'frames'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

