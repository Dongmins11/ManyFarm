"""Map internal survey windows to the four-field control protocol, preserving order."""
from farm_interfaces.msg import HarvestTask


def tasks_from_windows(windows):
    tasks = []
    for window in windows:
        task = HarvestTask()
        task.task_id = window['window_id'].replace('_W', '_TASK')
        task.window_id = window['window_id']
        pose = window['goal_pose']
        task.goal_pose.frame_id = pose.get('frame_id', 'map')
        task.goal_pose.position.x = float(pose['position'][0])
        task.goal_pose.position.y = float(pose['position'][1])
        task.goal_pose.position.z = 0.0
        task.goal_pose.yaw = float(pose['yaw'])
        task.expected_count = int(window['expected_count'])
        tasks.append(task)
    return tasks


def task_record(task):
    p = task.goal_pose.position
    return dict(task_id=task.task_id, window_id=task.window_id,
                goal_pose=dict(frame_id=task.goal_pose.frame_id,
                               position=dict(x=p.x, y=p.y, z=p.z), yaw=task.goal_pose.yaw),
                expected_count=task.expected_count)
