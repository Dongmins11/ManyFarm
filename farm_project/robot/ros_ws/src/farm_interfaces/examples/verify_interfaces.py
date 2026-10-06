#!/usr/bin/env python3
"""2026-10-02 single-Section Result contract. No ROS nodes or commands."""
from rclpy.serialization import serialize_message, deserialize_message
from farm_interfaces.action import ScoutArea, HarvestTask as HarvestAction
from farm_interfaces.msg import HarvestTask, RobotPose


def check(message):
    assert deserialize_message(serialize_message(message),type(message)) == message
    return message


def main():
    fields={
        ScoutArea.Goal: 'robot_id task_id section_id map_id frame_id crop_type target_ripeness timestamp',
        ScoutArea.Feedback: 'robot_id task_id phase section_id segment_id completed_segment_count segment_expected_count harvest_tasks timestamp',
        ScoutArea.Result: 'robot_id task_id result_code section_id completed_segment_count harvest_task_count total_expected_count harvest_tasks error_code error_message timestamp',
        HarvestTask: 'task_id window_id goal_pose expected_count',
        HarvestAction.Goal: 'robot_id map_id harvest_task timestamp',
        HarvestAction.Feedback: 'robot_id task_id success_count failed_count timestamp',
        HarvestAction.Result: 'robot_id task_id window_id result_code expected_count harvested_count failed_count error_code error_message timestamp',
    }
    for cls,expected in fields.items():
        assert list(cls.get_fields_and_field_types()) == expected.split(),f'Stale interface: {cls}'
    goal=check(ScoutArea.Goal(robot_id='scout_01',task_id='SCOUT_101',section_id='SEC01',
        map_id='farm_map_v1',frame_id='map',crop_type='PAPRIKA',target_ripeness='RIPE',timestamp='2026-10-02T10:00:00+09:00'))
    tasks=[]
    for name in ('HARVEST_202','HARVEST_201'):
        pose=RobotPose(frame_id='map',yaw=0.5);pose.position.x=1.25
        tasks.append(check(HarvestTask(task_id=name,window_id='SEC01_G01_'+name,goal_pose=pose,expected_count=2)))
    check(ScoutArea.Feedback(robot_id=goal.robot_id,task_id=goal.task_id,section_id=goal.section_id,
        phase='SEGMENT_COMPLETE',segment_id='SEC01_G01',completed_segment_count=1,segment_expected_count=4,harvest_tasks=tasks))
    for code,items in (('SUCCESS',tasks),('SUCCESS',[]),('FAILED',tasks[:1]),('CANCELED',tasks[:1])):
        result=check(ScoutArea.Result(robot_id=goal.robot_id,task_id=goal.task_id,section_id=goal.section_id,
            result_code=code,harvest_tasks=items,harvest_task_count=len(items),
            total_expected_count=sum(t.expected_count for t in items),error_code='NONE' if code=='SUCCESS' else 'STOPPED'))
        assert result.harvest_tasks==items
    sent=[check(HarvestAction.Goal(robot_id='harvest_01',map_id=goal.map_id,harvest_task=t,timestamp=goal.timestamp)) for t in tasks]
    assert [g.harvest_task.task_id for g in sent]==['HARVEST_202','HARVEST_201']
    for g in sent:
        check(HarvestAction.Feedback(robot_id=g.robot_id,task_id=g.harvest_task.task_id,success_count=1))
        check(HarvestAction.Result(robot_id=g.robot_id,task_id=g.harvest_task.task_id,window_id=g.harvest_task.window_id,
            result_code='SUCCESS',expected_count=2,harvested_count=2,error_code='NONE'))
    print('PASS: exact ScoutArea / HarvestTask schemas; all CDR round trips')
    print('PASS: final, empty and partial Result arrays; unchanged FIFO Window goals')
    print('No ROS nodes or robot commands were started.')


if __name__=='__main__':main()
