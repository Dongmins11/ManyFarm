"""통신 계층의 성공/취소/실패 결과와 평가 독립성을 ROS 객체 대역으로 검사."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/harvest_robot'))
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/farm_common'))
from farm_common.action_handoff import ActionHandoff
from harvest_robot.mission import MissionCanceled

def module(name,**values):
    m=ModuleType(name);m.__dict__.update(values);return m

class ActionTests(unittest.TestCase):
    def test_result_status_and_audit_independence(self):
        fake_action=NS(Feedback=NS,Result=NS)
        mocks={'rclpy':module('rclpy'), 'rclpy.action':module('rclpy.action',ActionServer=lambda *a,**k:None,
            GoalResponse=NS(ACCEPT=1,REJECT=2),CancelResponse=NS(ACCEPT=1)),
            'farm_interfaces':module('farm_interfaces'),
            'farm_interfaces.action':module('farm_interfaces.action',HarvestTask=fake_action)}
        with patch.dict(sys.modules,mocks):
            sys.modules.pop('harvest_robot.communication',None)
            com=importlib.import_module('harvest_robot.communication')
            for mode in ('success','cancel','failure','cancel_unconfirmed'):
                with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                    task=NS(task_id='one',window_id='SEC01_G01_W01',expected_count=7,
                        goal_pose=NS(position=NS(x=1.,y=2.),yaw=0.))
                    goal=NS(robot_id='harvest_01',map_id='farm_map_v1',harvest_task=task)
                    feedback=[];statuses=[];records=[]
                    handle=NS(request=goal,is_cancel_requested=False,
                        publish_feedback=feedback.append,succeed=lambda:statuses.append('success'),
                        canceled=lambda:statuses.append('canceled'),abort=lambda:statuses.append('aborted'))
                    def evaluate(*args):
                        if mode=='audit_missing':raise FileNotFoundError('snapshot')
                        return dict(status='OK',actual_in_workspace=3,count_delta=-4)
                    n=NS(callbacks=None,lock=threading.Lock(),busy=True,blocked=False,stopping=False,
                         completed_ids=set(),mode='sim',output=Path(directory),check=lambda:None,
                         emit_record=records.append,get_logger=lambda:NS(info=lambda s:None,error=lambda s:None))
                    n.handoff = ActionHandoff()
                    n.handoff.reserve('work', task.task_id)
                    def run():
                        handle.is_cancel_requested = mode.startswith('cancel')
                        if mode=='cancel':raise MissionCanceled('cancel requested')
                        if mode=='cancel_unconfirmed':n.blocked=True;raise RuntimeError('stop unknown')
                        if mode=='failure':raise RuntimeError('navigation failed')
                        return {'stamp_ns':123}
                    with patch.object(com,'HarvestMission',lambda *args:NS(run=run)):
                        result=com.HarvestCommunication(n).execute(handle)
                    expected={'success':('success','SUCCESS'),'audit_missing':('success','SUCCESS'),
                              'cancel':('canceled','CANCELED'),'failure':('aborted','FAILED'),
                              'cancel_unconfirmed':('aborted','FAILED')}[mode]
                    self.assertEqual((statuses[0],result.result_code),expected)
                    self.assertEqual((result.expected_count,result.harvested_count,result.failed_count),(7,0,0))
                    self.assertTrue(all(f.success_count==f.failed_count==0 for f in feedback))
                    self.assertFalse(n.busy);self.assertIsNone(n.active_goal)
                    self.assertEqual(len(records),1)
                    record=records[0]
                    self.assertNotIn('evaluation',record)
                    if mode=='audit_missing':self.assertEqual(record['evaluation']['status'],'UNAVAILABLE')
                    if mode=='cancel_unconfirmed':self.assertEqual(result.error_code,'CANCEL_UNCONFIRMED')
        sys.modules.pop('harvest_robot.communication',None)

if __name__=='__main__':unittest.main()
