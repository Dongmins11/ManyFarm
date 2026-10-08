"""HarvestTask 입력과 누적 결과 계약. 후보 선택·수확 판정은 하지 않습니다."""
import math


def validate_task(goal, config: dict) -> None:
    task = goal.harvest_task
    # 새 규약의 ID는 opaque identifier입니다. 삭제된 Section/Segment를 추정하지 않습니다.
    if any(not isinstance(value, str) or not value.strip()
           for value in (task.task_id, task.window_id)):
        raise ValueError('task_id/window_id가 비어 있음')
    if goal.robot_id != config['robot_id'] or goal.map_id != config['map_id']:
        raise ValueError('robot_id/map_id 불일치')
    p, yaw = task.goal_pose.position, task.goal_pose.yaw
    if (task.goal_pose.frame_id != 'map' or task.expected_count < 0
            or not all(math.isfinite(v) for v in (p.x, p.y, p.z, yaw)) or abs(p.z) > .1):
        raise ValueError('목표 pose/expected_count 오류')


def validate_counts(success: int, failed: int, previous: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """확정 수량은 음수가 아니며 같은 실행에서 감소하지 않아야 합니다."""
    if (type(success) is not int or type(failed) is not int or success < previous[0]
            or failed < previous[1] or success < 0 or failed < 0):
        raise ValueError('팔 누적 수량이 음수/역행/정수가 아님')
    return success, failed


def result_fields(goal, code: str, error_code: str = 'NONE', message: str = '', *,
                  harvested_count: int = 0, failed_count: int = 0) -> dict:
    validate_counts(harvested_count, failed_count)
    task = goal.harvest_task
    return dict(robot_id=goal.robot_id, task_id=task.task_id, window_id=task.window_id,
                result_code=code, expected_count=task.expected_count, harvested_count=harvested_count,
                failed_count=failed_count, error_code=error_code, error_message=message)
