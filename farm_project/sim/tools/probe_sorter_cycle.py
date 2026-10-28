"""실제 공통 선별장 액션과 가상 하역 장치를 연결하는 단독 시험기.

하역 기구/낙하 물리는 범위 밖이다. 실제 도킹 완료 피드백 및 정지 odom이
확인된 자기 작업에만 가상 장치 완료를 반환하며, 수량은 생성하지 않는다.
"""
import json
import math
from pathlib import Path
import sys
import threading
import time
from uuid import uuid4

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.convert import message_to_ordereddict
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped
from tf2_msgs.msg import TFMessage
from std_srvs.srv import Trigger
from farm_interfaces.action import BucketUnload, ReturnToStation, SortBatch
from farm_interfaces.msg import RobotStatus
from farm_interfaces.srv import UnloadEvent
from transport_robot.mission_types import utc


def main() -> None:
    base=Path(sys.argv[1]).resolve()
    fixture=json.loads((base/'fixture.json').read_text())
    sorting=bool(fixture.get('integrated_sorting'))
    events=(base/'events.jsonl').open('w');lock=threading.RLock()
    result={'passed':False,'virtual_mechanism':True,'count_valid':False}
    state=dict(phase='',waiting_seen=False,ready_requested=False,ready_accepted=False,active=False,completed=False,
               odom_at=0.,stamp=0.,stopped_since=None,status=None)
    task_id='sorter_'+uuid4().hex[:16]
    rclpy.init()
    node=Node('sorter_cycle_trial',parameter_overrides=[Parameter('use_sim_time',value=True)])
    group=ReentrantCallbackGroup()
    def record(kind: str,**data) -> None:
        with lock:
            events.write(json.dumps(dict(at=utc(),mono=time.monotonic(),kind=kind,**data),ensure_ascii=False)+'\n')
            events.flush()
    localization=(base/'localization.jsonl').open('w')
    def localization_record(kind: str, msg: object) -> None:
        with lock:
            localization.write(json.dumps(dict(mono=time.monotonic(),kind=kind,
                data=message_to_ordereddict(msg)))+'\n')
    def tf_record(msg: TFMessage) -> None:
        selected=[t for t in msg.transforms if t.header.frame_id=='map'
                  and t.child_frame_id=='transport_01/odom']
        if selected:localization_record('map_to_odom',TFMessage(transforms=selected))
    node.create_subscription(TFMessage,'/tf',tf_record,qos_profile_sensor_data,callback_group=group)
    node.create_subscription(LaserScan,'/transport_01/scan',lambda m:localization_record('scan',m),qos_profile_sensor_data,callback_group=group)
    node.create_subscription(PoseWithCovarianceStamped,'/transport_01/amcl_pose',lambda m:localization_record('amcl_pose',m),qos_profile_sensor_data,callback_group=group)
    def odom(msg: Odometry) -> None:
        localization_record('odom',msg)
        with lock:
            now=time.monotonic();v=msg.twist.twist
            stopped=all(math.isfinite(x) for x in (v.linear.x,v.linear.y,v.angular.z)) and math.hypot(v.linear.x,v.linear.y)<.005 and abs(v.angular.z)<.02
            continuous=now-state['odom_at']<=.5
            state['stopped_since']=(state['stopped_since'] if continuous and state['stopped_since'] is not None else now) if stopped else None
            state.update(odom_at=now,stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9)
            record('odom',stamp=state['stamp'],linear=[v.linear.x,v.linear.y],angular=v.angular.z,
                   stopped_since=state['stopped_since'])
    def stopped() -> bool:
        now=time.monotonic();age=node.get_clock().now().nanoseconds/1e9-state['stamp']
        return (now-state['odom_at']<=.5 and 0<=age<=.5 and state['stopped_since'] is not None
                and now-state['stopped_since']>=.8)
    def unload(request,response):
        with lock:
            accepted=(state['active'] and state['waiting_seen'] and state['ready_requested']
                      and state['phase']=='UNLOADING_STARTED' and not state['completed'] and stopped())
            response.success=bool(accepted)
            response.message=('SIM_VIRTUAL_UNLOAD: real dock feedback + measured stop; mechanism/fruit count not evaluated'
                              if accepted else 'SIM_VIRTUAL_UNLOAD_REJECT: 도킹/준비허가/정지/세션 조건 불충족')
            record('virtual_unload_guard',accepted=accepted,task_id=task_id,state=dict(state),count_valid=False)
            if accepted and sorting:
                output=Path(fixture['sorting_output'])
                try:
                    runtime=json.loads((output/'runtime.json').read_text())
                    request_id=uuid4().hex
                    request=dict(session=runtime['session'],request_id=request_id,task_id=task_id,
                                 fruit_paths=fixture['fruit_paths'])
                    temp=output/'deposit_request.tmp';temp.write_text(json.dumps(request));temp.replace(output/'deposit_request.json')
                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline:
                        runtime=json.loads((output/'runtime.json').read_text())
                        deposit=runtime.get('deposit_result')
                        if deposit and deposit.get('request_id')==request_id:
                            accepted=bool(deposit['success']);record('actual_deposit',**deposit)
                            response.success=accepted;response.message=json.dumps(deposit)
                            break
                        time.sleep(.05)
                    else:raise TimeoutError('기존 과실 레인 투입 결과 대기')
                except Exception as exc:
                    accepted=False;response.success=False;response.message=str(exc)
                    record('deposit_error',error=str(exc))
            if accepted:state['completed']=True
            return response
    def stop(request,response):
        with lock:
            response.success=stopped();response.message='SIM 가상 기구 무동작·현재 차체 정지 확인'
            record('virtual_stop',success=response.success)
            return response
    node.create_subscription(Odometry,'/transport_01/odom',odom,qos_profile_sensor_data,callback_group=group)
    def status(msg: RobotStatus) -> None:
        data=dict(message_to_ordereddict(msg))
        with lock:
            state['status']=data
            record('robot_status',data=data)
    node.create_subscription(RobotStatus,'/transport_01/status',status,qos_profile_sensor_data,callback_group=group)
    node.create_service(Trigger,'/transport_01/sim/sorter/unload',unload,callback_group=group)
    node.create_service(Trigger,'/transport_01/sim/sorter/stop',stop,callback_group=group)
    unload_client=ActionClient(node,BucketUnload,'/transport_01/bucket_unload',callback_group=group)
    return_client=ActionClient(node,ReturnToStation,'/transport_01/return_to_station',callback_group=group)
    sort_client=ActionClient(node,SortBatch,'/sorter_01/sort_batch',callback_group=group) if sorting else None
    ready_client=node.create_client(UnloadEvent,'/transport_01/unload_event',callback_group=group)
    executor=MultiThreadedExecutor(num_threads=4);executor.add_node(node)
    spinner=threading.Thread(target=executor.spin,daemon=True);spinner.start()
    handles=[]
    def wait(predicate,timeout: float,label: str) -> None:
        deadline=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>deadline:raise TimeoutError(label)
            time.sleep(.05)
    def future(ticket,timeout: float,label: str):
        wait(ticket.done,timeout,label);return ticket.result()
    def feedback(msg):
        data=dict(message_to_ordereddict(msg.feedback))
        with lock:
            if data.get('task_id')!=task_id:return
            state['phase']=data['event']
            if data['event']=='WAITING_FOR_UNLOAD':state['waiting_seen']=True
            record('unload_feedback',data=data)
    def outcome(ticket,name: str,timeout: float):
        reply=future(ticket,timeout,name+' result')
        data=dict(status=reply.status,result=dict(message_to_ordereddict(reply.result)))
        result[name]=data;record(name+'_result',**data)
        if reply.status!=4 or data['result']['result_code']!='SUCCESS':raise RuntimeError(name+' failed: '+json.dumps(data,ensure_ascii=False))
        return data
    try:
        wait(lambda:unload_client.server_is_ready() and return_client.server_is_ready() and
             ready_client.service_is_ready() and state['status'] is not None and state['status'].get('ready') and stopped(),
             180,'운송·Nav2·가상 센서 준비')
        # 가상 하역 장치는 도킹 전 호출을 거절해야 한다.
        before=unload(Trigger.Request(),Trigger.Response())
        if before.success:raise RuntimeError('도킹 전 가상 하역 허용')
        goal=BucketUnload.Goal(robot_id='transport_01',task_id=task_id,station_id='SORT_01',map_id='farm_map_v1',timestamp=utc())
        record('unload_goal',data=dict(message_to_ordereddict(goal)))
        handle=future(unload_client.send_goal_async(goal,feedback_callback=feedback),15,'BucketUnload 접수')
        if not handle.accepted:raise RuntimeError('BucketUnload Goal 거절')
        ticket=handle.get_result_async();handles.append((handle,ticket));state['active']=True
        wait(lambda:state['waiting_seen'] or ticket.done(),600,'실제 선별장 도킹 완료')
        if ticket.done():
            outcome(ticket,'unload',1)
            raise RuntimeError('UNLOAD_READY 이전 액션 종료')
        wait(stopped,10,'선별장 정지 확인')
        request=UnloadEvent.Request(robot_id='transport_01',task_id=task_id,station_id='SORT_01',event='UNLOAD_READY',timestamp=utc())
        # 서비스 응답과 뒤따르는 Trigger는 다른 executor에서 경합할 수 있다.
        # 요청 전 증거를 기록하되, 실제 허가는 공통 FSM의 접수·단계 전이가 책임진다.
        state['ready_requested']=True
        reply=future(ready_client.call_async(request),10,'UNLOAD_READY 접수')
        result['ready_response']=dict(message_to_ordereddict(reply));record('ready_response',**result['ready_response'])
        state['ready_accepted']=bool(reply.accepted)
        if not reply.accepted:
            state['ready_accepted']=False
            raise RuntimeError('UNLOAD_READY 거절')
        outcome(ticket,'unload',300);state['active']=False
        if not state['completed']:raise RuntimeError('가상 기구 완료 누락')
        wait(stopped,10,'이격 후 정지')
        if sorting:
            wait(sort_client.server_is_ready,30,'선별 서버 준비')
            goal=SortBatch.Goal(robot_id='sorter_01',task_id='sort_'+task_id,batch_id=task_id,timestamp=utc())
            record('sort_goal',data=dict(message_to_ordereddict(goal)))
            handle=future(sort_client.send_goal_async(goal,feedback_callback=lambda msg:
                record('sort_feedback',data=dict(message_to_ordereddict(msg.feedback)))),15,'선별 접수')
            if not handle.accepted:raise RuntimeError('SortBatch Goal 거절')
            ticket=handle.get_result_async();handles.append((handle,ticket))
            data=outcome(ticket,'sort',600)
            physical=json.loads((Path(fixture['sorting_output'])/'physical_report.json').read_text())
            result['physical_sorting']=physical
            if physical['counts']!=[data['result']['red_count'],data['result']['yellow_count']]:
                raise RuntimeError('선별 물리/관제 수량 불일치')
            result['count_valid']=True
            result['sequence_through_sort_passed']=True
            result['input_count']=len(fixture['fruit_paths'])
            result['sorted_count']=sum(physical['counts'])
            result['remaining_fruit_paths']=[f['path'] for f in physical['fruits'] if not f['sorted']]
            result['all_input_fruits_sorted']=not result['remaining_fruit_paths']
        goal=ReturnToStation.Goal(robot_id='transport_01',task_id='return_'+uuid4().hex[:16],
            station_id='STATION_TRANSPORT_01',map_id='farm_map_v1',timestamp=utc())
        record('return_goal',data=dict(message_to_ordereddict(goal)))
        handle=future(return_client.send_goal_async(goal,feedback_callback=lambda msg:
            record('return_feedback',data=dict(message_to_ordereddict(msg.feedback)))),15,'복귀 접수')
        if not handle.accepted:raise RuntimeError('ReturnToStation Goal 거절')
        ticket=handle.get_result_async();handles.append((handle,ticket))
        outcome(ticket,'return',900);result['passed']=True
    except BaseException as exc:
        result['error']=type(exc).__name__+': '+str(exc);record('error',detail=result['error'])
        raise
    finally:
        state['active']=False
        try:
            for handle,ticket in handles:
                if not ticket.done():
                    future(handle.cancel_goal_async(),10,'취소 접수');future(ticket,30,'취소 정지 결과')
        except Exception as exc:result['cleanup_error']=str(exc)
        result['final_state']=dict(state)
        (base/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        executor.shutdown(timeout_sec=3);spinner.join(3);node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
        events.close();localization.close()


if __name__=='__main__':main()
