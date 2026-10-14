"""관제 실제 ID 수신·좌표 보존·미등록 입력 거절을 ROS 없이 검사한다."""
import copy
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace as S
from dataclasses import dataclass
ROOT = Path(__file__).resolve().parents[5]
for package in ('farm_navigation', 'harvest_robot'):
    sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
from harvest_robot.contract import validate_task, resolve_section
from harvest_robot.configuration import load_harvest_config
from harvest_robot.mission import HarvestMission

def message(value):
    return S(**{k: message(v) if isinstance(v, dict) else v for k, v in value.items()})


@dataclass
class Arrival:
    accepted: bool = True


class ControlAliases(unittest.TestCase):
    def setUp(self):
        self.config = load_harvest_config(ROOT/'robot/config/harvest/harvest_real.json', ROOT)
        self.goal = message(dict(robot_id='harvest_01', map_id='farm_map_v1', section_id='SEC01',
            harvest_task=dict(task_id='opaque_task', window_id='opaque_window', expected_count=3,
                goal_pose=dict(frame_id='map', position=dict(x=1.188,y=-2.351,z=0.),yaw=-1.5707963267948966))))

    def test_control_and_frozen_ids(self):
        validate_task(self.goal,self.config)
        self.assertEqual(resolve_section(self.goal.section_id,self.config),'SEC_01')
        self.goal.map_id='many_farm_v1';self.goal.section_id='SEC_01'
        validate_task(self.goal,self.config)

    def test_unknown_inputs_rejected(self):
        for name,value in [('map_id','other'),('robot_id','scout_01'),('section_id','SEC02'),('section_id','')]:
            with self.subTest(name=name,value=value):
                goal=copy.deepcopy(self.goal);setattr(goal,name,value)
                with self.assertRaises(ValueError):validate_task(goal,self.config)

    def test_no_implicit_alias_for_other_environments(self):
        self.config.pop('control_aliases')
        with self.assertRaises(ValueError):validate_task(self.goal,self.config)

    def test_original_goal_and_tag_lifetime_preserved(self):
        before=copy.deepcopy(self.goal);calls=[];tags=[]
        def navigate(section,xy,yaw):
            calls.append((section,xy,yaw));return Arrival()
        node=S(config=self.config,check=lambda:None,arm_client=None,
            staged_navigation=S(navigate=navigate),
            tag_control=S(begin=lambda:tags.append('begin'),end=lambda:tags.append('end')))
        HarvestMission(node,self.goal).run()
        self.assertEqual(self.goal,before)
        self.assertEqual(calls,[('SEC_01',(1.188,-2.351),self.goal.harvest_task.goal_pose.yaw)])
        self.assertEqual(tags,['begin','end'])


if __name__=='__main__':unittest.main()
