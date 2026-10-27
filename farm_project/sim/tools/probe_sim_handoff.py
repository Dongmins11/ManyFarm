"""시험 전용 조립: 공통 인계 State/DeviceBridge/PrecisionClient를 실제 DDS 장치에 연결한다.
관제 TransportPickup 전체 서버나 수확 배출 동작을 대체하지 않는다.
"""
import json
import time
from threading import Thread
from types import SimpleNamespace
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String
from farm_docking.clients import PrecisionClient
from transport_robot.device_bridge import DeviceBridge
from transport_robot.transfer_session import TransferSession
from transport_robot.mission_types import Request
from transport_robot.states.transfer_states import ReceiveLidState


def run_handoff(log) -> dict:
    node=Node('sim_handoff_probe',namespace='/transport_01',parameter_overrides=[rclpy.parameter.Parameter('use_sim_time',value=True)])
    parent_log=log
    def log(kind: str, **fields) -> None:
        parent_log(kind,handoff_sim_ns=node.get_clock().now().nanoseconds,**fields)
    group=ReentrantCallbackGroup();executor=MultiThreadedExecutor(num_threads=2);executor.add_node(node)
    thread=Thread(target=executor.spin,daemon=True);thread.start()
    measured={};deadline=time.monotonic()+180.;result={};cancelled=False
    def proof(msg):measured.update(data=json.loads(msg.data),received=time.monotonic())
    node.create_subscription(String,'sim/basket_alignment',proof,10,callback_group=group)
    def check():
        if cancelled or time.monotonic()>deadline:raise TimeoutError('인계/이격 시험 제한시간')
    def valid_proof():
        d=measured.get('data',{});p=d.get('proof') or {}
        age=node.get_clock().now().nanoseconds/1e9-p.get('sim_time_s',-1000.)
        return (time.monotonic()-measured.get('received',0)<.5 and d.get('fresh') and p.get('hold_pass')
                and 0<=age<=.5)
    device=DeviceBridge(node,group);docking=PrecisionClient(node,group,check,timeout=120.)
    request=Request(task_id='sim_handoff_'+str(time.time_ns()),kind='pickup',xy=(0.,0.),yaw=0.,
        transfer_id='transfer_'+str(time.time_ns()),harvest_robot_id='harvest_01')
    transfer=TransferSession();transfer.begin(request)
    # 실제 DOCK 성공은 호출자가 검증한다. 시험은 도킹 이후부터 공통 State를 실행한다.
    controller=SimpleNamespace(request=request,device=device,docking=docking,transfer=transfer,
        pickup_workflow=dict(enabled=True,final_marker_id=41,clearance_profile='harvest_clear',transfer_timeout_s=60.),
        check=check,loaded_count=None,docked_request=request)
    controller.mission=SimpleNamespace(
        record_stage=lambda req,stage,*args:log('handoff_stage',stage=stage,task_id=req.task_id),
        set_contact=lambda value:log('contact',value=value))
    def feedback(event):
        log('handoff_feedback',event=event)
        if event=='DOCK_STABLE':
            if not valid_proof() or not measured['data']['lid_open']:raise RuntimeError('인계 정렬/덮개 상태 미확인')
            transfer.accept(request.task_id,request.transfer_id,request.harvest_robot_id,'TRANSFER_COMPLETE')
            log('sim_transfer_complete',task_id=request.task_id,transfer_id=request.transfer_id,
                proof=measured['data'],count_valid=False,scope='common TransferSession direct; not DDS service')
    controller.feedback=feedback
    def run_async(state,work,done):done(work())
    controller.run_async=run_async
    controller.transition=lambda state:state.enter()
    controller.finish=lambda outcome:result.update(result_code=outcome.result_code,count_valid=False,loaded_count=None)
    try:
        while not (valid_proof() and device.available()):check();time.sleep(.02)
        # 덮개 완료 이후 proof 토픽의 최신 상태 수신도 기다린다.
        original_feedback=controller.feedback
        def synchronized_feedback(event):
            if event=='DOCK_STABLE':
                until=time.monotonic()+5.
                while not (measured.get('data',{}).get('lid_open') and measured['data'].get('task_id')==request.task_id):
                    check()
                    if time.monotonic()>until:raise TimeoutError('가상 덮개 열림 상태 미수신')
                    time.sleep(.02)
            original_feedback(event)
        controller.feedback=synchronized_feedback
        log('handoff_begin',proof=measured['data'],task_id=request.task_id)
        ReceiveLidState(controller,'LID_OPEN').enter()
        log('handoff_result',**result);return result
    finally:
        cancelled=True
        try:docking.stop();device.stop()
        finally:
            transfer.close();executor.shutdown(timeout_sec=3.);thread.join(timeout=3.);node.destroy_node()
