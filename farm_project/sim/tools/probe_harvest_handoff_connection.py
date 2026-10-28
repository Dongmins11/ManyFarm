"""실제 DDS/Isaac 입력으로 인계 조립과 미준비 요청 거절을 검사한다. 움직임 요청 없음."""
from pathlib import Path
import argparse
import json
import time
import threading
from datetime import datetime, timezone
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.parameter import Parameter
from rcl_interfaces.srv import GetParameters
from std_srvs.srv import Trigger
from farm_interfaces.action import DockTransfer, Discharge, MechanicalOperation
from lifecycle_msgs.srv import GetState
from std_msgs.msg import String
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    parser.add_argument('--aligned',action='store_true')
    args=parser.parse_args();out=args.output
    rclpy.init();node=Node('harvest_handoff_connection_probe',parameter_overrides=[Parameter('use_sim_time',value=True)])
    executor=MultiThreadedExecutor(num_threads=2);executor.add_node(node)
    thread=threading.Thread(target=executor.spin,daemon=True);thread.start()
    result={'scope':'stationary Isaac + actual ROS runtime/device connection; no handoff body motion',
            'domain':13,'range':'SUBNET','passed':False}
    deadline=time.monotonic()+240.;seen={}
    def wait(test, label):
        while not test():
            if time.monotonic()>deadline:raise TimeoutError(label)
            time.sleep(.05)
    def future(f, label):wait(f.done,label);return f.result()
    for name,kind in [('scan',LaserScan),('odom',Odometry)]:
        node.create_subscription(kind,'/harvest_01/'+name,
            lambda msg,k=name:seen.update({k:time.monotonic()}),qos_profile_sensor_data)
    prepare=node.create_client(Trigger,'/harvest_01/sim/transfer/prepare_arm')
    transfer=ActionClient(node,DockTransfer,'/harvest_01/dock_transfer')
    discharge=ActionClient(node,Discharge,'/harvest_01/sim/discharge')
    proof={}
    node.create_subscription(String,'/transport_01/sim/basket_alignment',
        lambda msg:proof.update(json.loads(msg.data)),10)
    try:
        wait(lambda:prepare.service_is_ready() and transfer.server_is_ready() and discharge.server_is_ready(), '인계 서버 연결')
        wait(lambda:node.get_clock().now().nanoseconds>0 and all(time.monotonic()-seen.get(k,0)<.5 for k in ('scan','odom')), '실제 센서·시계')
        # 초기 실제 팔 접힘을 기다린다. 장치 응답을 성공으로 덮어쓰지 않는다.
        replies=[]
        while True:
            reply=future(prepare.call_async(Trigger.Request()),'팔 준비 서비스')
            replies.append(dict(success=reply.success,message=reply.message))
            if reply.success:break
            if time.monotonic()>deadline:raise TimeoutError('팔 준비: '+reply.message)
            time.sleep(.5)
        result['prepare']=replies[-1];result['prepare_attempts']=len(replies)
        parameters={}
        for endpoint in ['/harvest_01/handoff/controller_server','/harvest_01/handoff/behavior_server',
                         '/harvest_01/handoff/local_costmap/local_costmap','/harvest_01/handoff/lifecycle_manager']:
            client=node.create_client(GetParameters,endpoint+'/get_parameters')
            wait(client.service_is_ready,endpoint)
            reply=future(client.call_async(GetParameters.Request(names=['use_sim_time'])),endpoint)
            parameters[endpoint]=reply.values[0].bool_value
            if not parameters[endpoint]:raise AssertionError('시뮬 시계 누락: '+endpoint)
        result['use_sim_time']=parameters
        active={}
        for endpoint in ['/harvest_01/handoff/controller_server','/harvest_01/handoff/behavior_server',
                         '/harvest_01/controller_server','/harvest_01/planner_server','/harvest_01/velocity_smoother']:
            client=node.create_client(GetState,endpoint+'/get_state')
            wait(client.service_is_ready,endpoint)
            while True:
                state=future(client.call_async(GetState.Request()),endpoint).current_state
                if state.id==3:break
                if time.monotonic()>deadline:raise TimeoutError('활성화 대기: '+endpoint)
                time.sleep(.1)
            active[endpoint]=state.label
        result['active_servers']=active
        topic='/harvest_01/cmd_vel_nav'
        wait(lambda:len(node.get_publishers_info_by_topic(topic))>0,'출력 소유자')
        pubs=node.get_publishers_info_by_topic(topic)
        result['output_publishers']=[p.node_namespace+'/'+p.node_name for p in pubs]
        if len(pubs)!=1:raise AssertionError('단일 출력 위반: '+str(result['output_publishers']))
        goal=DockTransfer.Goal(robot_id='harvest_01',task_id='connection_'+str(time.time_ns()),
            transfer_id='connection_'+str(time.time_ns()),transport_robot_id='transport_01',expected_count=0,
            timestamp=datetime.now(timezone.utc).isoformat())
        handle=future(transfer.send_goal_async(goal),'윈도우 없는 DockTransfer')
        result['missing_window_goal_accepted']=handle.accepted
        if handle.accepted:
            future(handle.cancel_goal_async(),'예상 밖 인계 취소')
            raise AssertionError('완료 윈도우 없는 인계 요청이 수락됨')
        if args.aligned:
            wait(lambda:proof.get('fresh') is True and (proof.get('proof') or {}).get('hold_pass') is True,'실제 바구니 정렬 유지')
            result['alignment_proof']=dict(proof)
            mechanical=ActionClient(node,MechanicalOperation,'/transport_01/devices/mechanical_operation')
            wait(mechanical.server_is_ready,'운송 덮개 장치')
            task='aligned_device_'+str(time.time_ns())
            def lid(operation):
                h=future(mechanical.send_goal_async(MechanicalOperation.Goal(task_id=task,operation=operation)),'덮개 요청')
                if not h.accepted:raise AssertionError(operation+' 거절')
                reply=future(h.get_result_async(),'덮개 결과')
                if reply.status!=4 or not reply.result.success:raise AssertionError(operation+' 실패')
            lid('LID_OPEN')
            phases=[]
            h=future(discharge.send_goal_async(Discharge.Goal(transfer_id=task),
                feedback_callback=lambda message:phases.append(message.feedback.phase)),'정렬 후 배출')
            if not h.accepted:raise AssertionError('정렬 후 배출 거절')
            reply=future(h.get_result_async(),'배출 결과')
            result['discharge']=dict(status=reply.status,error_codes=list(reply.result.error_codes),
                detail=reply.result.error_message,phases=phases,count_valid=False)
            lid('LID_CLOSE')
            if reply.status!=4 or reply.result.error_codes:raise AssertionError('배출 실패')
        else:
            handle=future(discharge.send_goal_async(Discharge.Goal(transfer_id='unaligned_'+str(time.time_ns()))),'정렬 전 배출')
            result['unaligned_discharge_accepted']=handle.accepted
            if handle.accepted:
                future(handle.cancel_goal_async(),'예상 밖 배출 취소')
                raise AssertionError('서로 떨어진 바구니에서 배출 수락')
        result['passed']=True
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        executor.shutdown(timeout_sec=3);thread.join(3)
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':main()
