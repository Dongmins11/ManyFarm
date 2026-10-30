#!/usr/bin/env python3
"""PC의 신뢰된 오프라인 분석 산출물에서 태그 보정 모델을 벽 관측과 대조한다.

run 폴더의 events.jsonl 및 기존 wall_input.pkl을 읽는다. ROS/주행 명령과 설정 변경은 없다.
절대 위치 정답 대신 같은 직선 벽의 위치·방향 일관성을 비교한다.
"""
from __future__ import annotations
import argparse
import json
import math
import pickle
from pathlib import Path
from typing import Any
import numpy as np
from farm_navigation.wall_reference import fit_wall


def compare(run: Path, start: float, end: float) -> dict[str, Any]:
    """촬영 시각에 가까운 벽 표본과 원시/거리/방향/전체 보정 자세를 비교한다(초/m/rad)."""
    # 자체 생성한 로컬 중간 산출물 전용이며 외부 첨부 pickle을 입력하지 않는다.
    with (run/'wall_input.pkl').open('rb') as stream:
        scans, _, _, chain = pickle.load(stream)
    events = list(run.rglob('events.jsonl'))
    if len(events) != 1:
        raise ValueError('단일 태그 세션 기록 폴더를 지정해야 합니다.')
    times = np.array([s[0] for s in scans])
    rows, excluded = [], []
    for line in events[0].read_text().splitlines():
        event = json.loads(line)
        if event['kind'] != 'tag_correction_requested':
            continue
        stamp = event['source_stamp_ns']/1e9
        if not start <= stamp <= end:
            continue
        index = int(np.argmin(abs(times-stamp)))
        age = float(times[index]-stamp)
        if abs(age) > .1:  # 분석의 시각 매칭 한도. 운영 판단/주행 정지 조건이 아니다.
            excluded.append(dict(stamp=stamp, reason='대응 스캔 없음', offset_s=age))
            continue
        points = (chain @ scans[index][2].T).T[:, :2]
        points = points[(abs(points[:, 0]) < .8) & (points[:, 1] > .2) & (points[:, 1] < .8)]
        try:
            wall = fit_wall(points, threshold_m=.015, min_points=30, min_span_m=.7)
        except ValueError as error:
            excluded.append(dict(stamp=stamp, reason=str(error)))
            continue
        bias = event['pixel_bias']
        raw, corrected = np.array(bias['source_raw']), np.array(bias['source_adjusted'])
        variants = dict(raw=raw, yaw_only=np.array([*raw[:2], corrected[2]]),
                        distance_only=np.array([*corrected[:2], raw[2]]), full=corrected)
        item = dict(stamp=stamp, tag=event['tag'], u_px=bias['u_px'], scan_offset_s=age,
                    wall_rms_m=wall['residual_rms_m'], variants={})
        for name, pose in variants.items():
            theta = pose[2]+wall['normal_angle_rad']-math.pi/2
            item['variants'][name] = dict(x=pose[0], wall_y=pose[1]+wall['distance_m']/math.cos(theta),
                                         wall_angle_deg=math.degrees(theta))
        rows.append(item)
    if len(rows) < 3:
        raise ValueError('비교 가능한 태그/벽 표본 부족')
    summary = {}
    for name in rows[0]['variants']:
        values = [r['variants'][name] for r in rows]
        x = np.array([v['x'] for v in values]); y = np.array([v['wall_y'] for v in values])
        angles = np.array([v['wall_angle_deg'] for v in values])
        line = np.polyfit(x, y, 1)
        residual = y-np.polyval(line, x)
        summary[name] = dict(wall_y_line_residual_rms_cm=float(np.sqrt(np.mean(residual**2))*100),
                             wall_angle_std_deg=float(angles.std()),
                             wall_angle_mean_deg=float(angles.mean()))
    return dict(run=str(run), sample_count=len(rows), excluded=excluded, summary=summary, samples=rows,
                limitation='같은 벽의 상대적 일관성이다. 절대 위치 정확도나 보정 해제 후 주행을 보장하지 않는다.')


def main() -> None:
    """CLI의 시간은 Unix 초. stdout JSON만 출력하며 운영 파일을 쓰지 않는다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--start', type=float, required=True)
    parser.add_argument('--end', type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.run, args.start, args.end), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
