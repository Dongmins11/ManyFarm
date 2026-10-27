"""명시적 domain231/loopback에서만 가짜 팔 서버로 실제 ROS 요청·응답을 검증한다."""
from pathlib import Path
import json
import os
import subprocess
import sys
import threading
import time
import unittest


@unittest.skipUnless(os.getenv('MANYFARM_JETSON_ROS_TEST')=='1','격리 ROS 환경 명시 필요')
class ArmAgentRosTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.getenv('ROS_DOMAIN_ID')!='231' or '127.0.0.1' not in os.getenv('CYCLONEDDS_URI',''):
            raise RuntimeError('시험 domain/loopback 제한')
        import rclpy
        from rclpy.action import ActionServer, CancelResponse, GoalResponse
        from rclpy.executors import MultiThreadedExecutor
        from rclpy.callback_groups import ReentrantCallbackGroup
        from rclpy.node import Node
        from farm_interfaces.action import HarvestTask, Discharge
        from jetson_harvest_interfaces.msg import RuntimeStatus
        from jetson_harvest_interfaces.srv import GetOperation,Recover
        from std_srvs.srv import Trigger,SetBool
        from std_msgs.msg import Bool
        self.rclpy=rclpy;rclpy.init()
        self.node=Node('test_console_server');self.group=ReentrantCallbackGroup()
        self.ready=True;self.sequence=0;self.received=[];self.events=[];self.stop_event=threading.Event()
        from geometry_msgs.msg import PoseWithCovarianceStamped
        from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
        self.pose_pub=self.node.create_publisher(PoseWithCovarianceStamped,'/console_test/amcl_pose',
            QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE))
        pose=PoseWithCovarianceStamped()
        pose.header.frame_id='map';pose.header.stamp=self.node.get_clock().now().to_msg()
        pose.pose.pose.position.x=1.25;pose.pose.pose.orientation.w=1.
        self.pose_pub.publish(pose)  # 클라이언트 연결 이전 한 번만 발행한다.
        self.pub=self.node.create_publisher(RuntimeStatus,'/console_test/arm/runtime_status',10)
        def status() -> None:
            self.sequence+=1
            self.pub.publish(RuntimeStatus(robot_id='console_test',boot_id='test-boot',sequence=self.sequence,
                stamp=self.node.get_clock().now().to_msg(),mode='depth_v11',ready=self.ready,box_state='UNKNOWN'))
        self.timer=self.node.create_timer(.1,status,callback_group=self.group)
        def execute(handle: object) -> object:
            self.received.append(handle.request)
            self.ready=False
            handle.publish_feedback(HarvestTask.Feedback(robot_id='console_test',task_id=handle.request.harvest_task.task_id,success_count=1))
            end=time.monotonic()+3
            while time.monotonic()<end and not handle.is_cancel_requested and not self.stop_event.is_set():time.sleep(.02)
            result=HarvestTask.Result(robot_id='console_test',task_id=handle.request.harvest_task.task_id,
                window_id=handle.request.harvest_task.window_id,expected_count=0,harvested_count=1)
            if handle.is_cancel_requested:handle.canceled();result.result_code='CANCELED'
            elif self.stop_event.is_set():handle.abort();result.result_code='FAILED'
            else:handle.succeed();result.result_code='SUCCESS'
            self.ready=True
            return result
        self.server=ActionServer(self.node,HarvestTask,'/console_test/arm/harvest_task',execute,
            cancel_callback=lambda _:CancelResponse.ACCEPT,callback_group=self.group)
        self.discharge=ActionServer(self.node,Discharge,'/console_test/arm/discharge',lambda _:None,
            goal_callback=lambda _:GoalResponse.REJECT,callback_group=self.group)
        def trigger(request: object,response: object) -> object:
            response.success=True;response.message='test-only service response';return response
        def lookup(request: object,response: object) -> object:
            response.found=True;response.terminal=True;response.result_json=json.dumps({'key':request.key});return response
        self.test_enabled=False
        self.test_pub=self.node.create_publisher(Bool,'/console_test/transfer_test_mode/enabled',10)
        self.test_timer=self.node.create_timer(.1,lambda:self.test_pub.publish(Bool(data=self.test_enabled)))
        def toggle(request: object,response: object) -> object:
            self.test_enabled=request.data
            response.success=True;response.message='test-only mode toggle';return response
        self.test_service=self.node.create_service(SetBool,'/console_test/transfer_test_mode/set_enabled',toggle)
        self.services=[self.node.create_service(Trigger,'/console_test/arm/'+name,trigger,callback_group=self.group) for name in ['prepare','stop']]
        self.services.append(self.node.create_service(GetOperation,'/console_test/arm/get_operation',lookup,callback_group=self.group))
        self.services.append(self.node.create_service(Recover,'/console_test/arm/recover',trigger,callback_group=self.group))
        self.executor=MultiThreadedExecutor(num_threads=4);self.executor.add_node(self.node)
        self.worker=threading.Thread(target=self.executor.spin,daemon=True);self.worker.start()
        cfg=dict(robot_id='console_test',map_id='test_map',readiness_timeout_s=.5,response_timeout_s=1.,execution_timeout_s=5.,cancel_timeout_s=1.)
        self.process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'arm_agent.py'),json.dumps(cfg)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.reader=threading.Thread(target=lambda:[self.events.append(json.loads(line)) for line in self.process.stdout],daemon=True);self.reader.start()
        self.wait(lambda e:e['kind']=='snapshot' and e['services']['prepare'] and not e['runtime']['stale'])

    def tearDown(self) -> None:
        self.stop_event.set()
        self.process.stdin.close()
        self.process.wait(timeout=5)
        self.reader.join(2)
        self.executor.shutdown(timeout_sec=5);self.worker.join(2)
        self.node.destroy_node();self.rclpy.shutdown()

    def wait(self, predicate: object, timeout: float=5.) -> dict:
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            for event in list(self.events):
                if predicate(event):return event
            if self.process.poll() is not None:raise AssertionError(self.process.stderr.read())
            time.sleep(.02)
        raise AssertionError('event timeout: '+str(self.events[-4:]))

    def send(self, action: str, body: dict=None) -> str:
        request_id=str(time.time_ns())
        self.process.stdin.write(json.dumps({'id':request_id,'action':action,'body':body or {}})+'\n');self.process.stdin.flush()
        return request_id

    def goal(self) -> dict:
        return dict(robot_id='console_test',map_id='test_map',timestamp='TEST_ONLY',harvest_task=dict(task_id='test-task',window_id='test-window',expected_count=0,goal_pose=dict(frame_id='map',position=dict(x=0.,y=0.,z=0.),yaw=0.)))

    def test_transfer_test_roundtrip_uses_pinky_service_without_action(self) -> None:
        self.wait(lambda e:e['kind']=='snapshot' and e['services']['transfer_test'])
        key=self.send('transfer_test',{'enabled':True})
        self.wait(lambda e:e['kind']=='service_response' and e.get('id')==key and e['payload']['success'])
        self.wait(lambda e:e['kind']=='snapshot' and e.get('observations',{}).get('transfer_test',{}).get('payload',{}).get('data') is True)
        self.assertTrue(self.test_enabled)
        key=self.send('transfer_test',{'enabled':False})
        self.wait(lambda e:e['kind']=='service_response' and e.get('id')==key)
        self.assertFalse(self.test_enabled)
        self.assertFalse(self.received)
        self.assertEqual(self.node.count_publishers('/console_test/control_state'),0)

    def test_retained_pose_received_without_motion_or_republication(self) -> None:
        event=self.wait(lambda e:e['kind']=='snapshot' and 'pose' in e['observations'])
        self.assertEqual(event['observations']['pose']['payload']['pose']['pose']['position']['x'],1.25)
        self.assertFalse(self.received)

    def test_feedback_cancel_and_terminal_while_ready_false(self) -> None:
        key=self.send('harvest',{'goal':self.goal()})
        self.wait(lambda e:e['kind']=='goal_response' and e.get('id')==key and e['accepted'])
        self.wait(lambda e:e['kind']=='feedback' and e.get('id')==key)
        self.send('cancel')
        self.wait(lambda e:e['kind']=='cancel_ack' and e.get('id')==key)
        result=self.wait(lambda e:e['kind']=='result' and e.get('id')==key)
        self.assertEqual(result['ros_status'],5);self.assertFalse(result['success'])
        self.assertEqual(result['payload']['harvested_count'],1)
        self.assertEqual(len(self.received),1)

    def test_services_and_discharge_rejection_are_not_faked_success(self) -> None:
        for action,body in [('prepare',{}),('stop',{}),('get_operation',{'kind':'harvest','key':'["test"]'}),('recover',{'acknowledgement':'DEVICE_AND_LOAD_RECONCILED'})]:
            key=self.send(action,body)
            self.wait(lambda e:e['kind']=='service_response' and e.get('id')==key)
        key=self.send('discharge',{'goal':{'transfer_id':'test-transfer'}})
        event=self.wait(lambda e:e['kind']=='goal_response' and e.get('id')==key)
        self.assertFalse(event['accepted'])
        self.assertFalse(any(e['kind']=='result' and e.get('id')==key for e in self.events))

    def test_unready_sends_no_goal_and_connection_publishes_no_controlstate(self) -> None:
        self.ready=False
        time.sleep(.25)
        key=self.send('harvest',{'goal':self.goal()})
        self.wait(lambda e:e['kind']=='not_sent' and e.get('id')==key)
        self.assertFalse(self.received)
        self.assertEqual(self.node.count_publishers('/console_test/control_state'),0)
