"""신규 작업창만 진행축으로 이동한다. 단위 m, 기존 창/배정/깊이/높이는 유지한다."""
from dataclasses import replace
import math


def reduce_overlap(task, existing, fruits, config, trigger_ratio: float):
    """배정 과실과 경로 범위를 지키며 기존 창과의 겹침 길이 합을 최소화한다.

    trigger_ratio는 한 창 너비 대비 교집합 길이(0~1)다. 보장이 불가능한
    겹침은 남긴다. 작업을 버리거나 기존 창을 이동하지 않는다.
    """
    if not math.isfinite(trigger_ratio) or not 0 <= trigger_ratio <= 1:
        raise ValueError('overlap trigger_ratio must be between 0 and 1')
    width = task.window_x_max - task.window_x_min
    occupied = [t for t in existing if t.member_ids]
    def overlap(left, other):
        return max(0., min(left + width, other.window_x_max) - max(left, other.window_x_min))
    original = task.window_x_min
    if not occupied or max(overlap(original, t) / width for t in occupied) <= trigger_ratio:
        return task
    # 배정점은 새 위치에서도 nominal membership 범위 안에 둔다.
    # 원래 허용오차로만 들어온 점은 그 점의 기존 초과량까지만 허용한다.
    offset = width / 2 - config.work_world_xy[0] - config.mount_world_xy[0]
    lo, hi = config.route_start - offset, config.route_end - offset
    inset = config.membership_margin
    for fid in task.member_ids:
        x = fruits[fid].x
        left_slack = max(0., original + inset - x)
        right_slack = max(0., x - (original + width - inset))
        lo = max(lo, x - width + inset - right_slack)
        hi = min(hi, x - inset + left_slack)
    anchor = fruits[task.anchor_id].x
    lo = max(lo, anchor - width + config.margin)
    hi = min(hi, anchor - config.margin)
    if lo > hi + 1e-9:
        return task
    if lo > hi:
        lo = hi
    # 겹침 합은 구간별 선형이므로 경계와 꺾임점만 비교하면 된다.
    candidates = [original, lo, hi]
    for t in occupied:
        candidates += [t.window_x_min-width, t.window_x_max-width,
                       t.window_x_min, t.window_x_max]
    candidates = [max(lo, min(hi, x)) for x in candidates]
    def cost(left):
        return sum(overlap(left,t) for t in occupied)
    best = min(candidates, key=lambda x:(cost(x), abs(x-original)))
    if cost(best) >= cost(original) - 1e-9:
        return task
    shift = best-original
    return replace(task, window_x_min=best, window_x_max=best+width,
                   safe_x_min=best+inset, safe_x_max=best+width-inset,
                   arm_x=task.arm_x+shift, base_x=task.base_x+shift)
