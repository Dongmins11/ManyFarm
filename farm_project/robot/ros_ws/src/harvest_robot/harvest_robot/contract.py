"""HarvestTask 입력 검사와 이동 전용 결과 계약. ROS import 없이 검사 가능합니다."""
import math


def validate_task(goal, config: dict) -> None:
    task = goal.harvest_task
    # 새 규약의 ID는 opaque identifier입니다. 삭제된 Section/Segment를 추정하지 않습니다.
    if any(not isinstance(value, str) or not value.strip()
           for value in (task.task_id, task.window_id)):
        raise ValueError('task_id/window_id가 비어 있음')
    if goal.robot_id != config['robot_id'] or goal.map_id != config['map_id']:
        raise ValueError('robot_id/map_id 불일치')
    if config.get("movement_mode") == "route_then_pose":
        if getattr(goal, "section_id", "") not in config.get("sections", {}):
            raise ValueError("등록된 section_id 필요; window_id에서 추측하지 않음")
    p, yaw = task.goal_pose.position, task.goal_pose.yaw
    if (task.goal_pose.frame_id != 'map' or task.expected_count < 0
            or not all(math.isfinite(v) for v in (p.x, p.y, p.z, yaw)) or abs(p.z) > .1):
        raise ValueError('목표 pose/expected_count 오류')


def result_fields(goal, code: str, error_code: str = 'NONE', message: str = '') -> dict:
    task = goal.harvest_task
    return dict(robot_id=goal.robot_id, task_id=task.task_id, window_id=task.window_id,
                result_code=code, expected_count=task.expected_count, harvested_count=0,
                failed_count=0, error_code=error_code, error_message=message)
