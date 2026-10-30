"""한 번의 SEC01 시험에서 기존 공용 액션을 순서대로 연결한다."""
import copy
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from rclpy.action import ActionClient
from farm_interfaces.action import ScoutArea, ReturnToStation
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.set_message import set_message_fields
from std_srvs.srv import Trigger

ROOT=Path(__file__).resolve().parents[2]

def utc():return datetime.now(timezone.utc).isoformat()

def start_action(node,wait,future,record,kind,endpoint,goal,label):
    client=ActionClient(node,kind,endpoint)
    wait(client.server_is_ready,300,label+' 서버 준비')
    record(label+'_goal',goal=dict(message_to_ordereddict(goal)))
    handle=future(client.send_goal_async(goal,feedback_callback=lambda m:record(label+'_feedback',data=dict(message_to_ordereddict(m.feedback)))),30,label+' 접수')
    if not handle.accepted:raise RuntimeError(label+' Goal 거절')
    return client,handle,handle.get_result_async()

def finish_action(bundle,future,record,result,label,timeout):
    reply=future(bundle[2],timeout,label+' 결과')
    data=dict(status=reply.status,result=dict(message_to_ordereddict(reply.result)))
    result[label]=data;record(label+'_result',**data)
    if reply.status!=4 or reply.result.result_code!='SUCCESS':raise RuntimeError(label+' 실패: '+json.dumps(data,ensure_ascii=False))
    return reply

def transport_devices_ready(base,node,wait,record) -> None:
    """긴 예찰/수확 전에 실제 운송 장치 endpoint 연결을 확인한다."""
    profile=json.loads((base/'runtime/transport_runtime.json').read_text())
    config=profile['mechanical_device']
    names=[config[key] for key in ('lid_open_service','lid_close_service','unload_service','stop_service')]
    endpoints=[name if name.startswith('/') else '/'+profile['robot_id']+'/'+name for name in names]
    clients=[node.create_client(Trigger,name) for name in endpoints]
    try:
        wait(lambda:all(c.service_is_ready() for c in clients),180,'운송 덮개·하역·정지 서비스 준비')
        record('transport_devices_ready',endpoints=endpoints)
    finally:
        for client in clients:node.destroy_client(client)

def check_pickup_acceptance(base,goal_path,node,wait,future,record,result,owned) -> None:
    """실제 서버 접수 후 취소하는 짧은 시험. 인계 성공으로 집계하지 않는다."""
    from farm_interfaces.action import TransportPickup
    from farm_interfaces.msg import RobotStatus
    from rclpy.qos import qos_profile_sensor_data
    status={}
    subscription=node.create_subscription(RobotStatus,'/transport_01/status',
        lambda msg:status.update(ready=msg.ready),qos_profile_sensor_data)
    try:
        wait(lambda:status.get('ready'),180,'운송 주행 준비')
    finally:
        node.destroy_subscription(subscription)
    # 서비스 존재만으로 하역 성공을 만들지 않는지 실제 호출로 확인한다.
    client=node.create_client(Trigger,'/transport_01/sim/sorter/unload')
    try:
        reply=future(client.call_async(Trigger.Request()),10,'인계/도킹 전 하역 거절 검사')
        result['premature_unload_rejected']=not reply.success
        if reply.success:raise RuntimeError('인계/도킹 전 하역이 허용됨')
    finally:
        node.destroy_client(client)
    goal=TransportPickup.Goal(robot_id='transport_01',task_id='preflight_'+uuid4().hex[:12],
        transfer_id='preflight_transfer_'+uuid4().hex[:12],harvest_robot_id='harvest_01',
        map_id='farm_map_v1',target_marker_id=42,docking_marker_id=41,timestamp=utc())
    set_message_fields(goal.staging_pose,json.loads(goal_path.read_text()))
    bundle=start_action(node,wait,future,record,TransportPickup,'/transport_01/transport_pickup',goal,'pickup_preflight')
    owned.append(bundle);result['pickup_accepted']=True
    cancellation=future(bundle[1].cancel_goal_async(),10,'접수 시험 취소')
    if not cancellation.goals_canceling:raise RuntimeError('접수 시험 취소 요청 거절')
    reply=future(bundle[2],40,'접수 시험 정지 결과')
    result['pickup_cancellation']=dict(status=reply.status,result=dict(message_to_ordereddict(reply.result)))
    record('pickup_preflight_result',**result['pickup_cancellation'])
    if reply.status!=5 or reply.result.result_code!='CANCELED':raise RuntimeError('접수 시험 취소·정지 실패')
    if (base/'post_sorter/fixture.json').exists():
        assert not json.loads((base/'post_sorter/fixture.json').read_text()).get('handoff_complete')

def survey(base,node,wait,future,record,result,owned):
    reused=base/'reused_scout_result.json'
    if reused.exists():
        saved=json.loads(reused.read_text())['scout_result']
        result['scout']=saved;result['scout_reused']=True
        result['window_count']=saved['result']['harvest_task_count'];result['harvest_results']=[]
        record('scout_reused',source=json.loads((base/'fixture.json').read_text())['reused_scout_source'],**saved)
        return copy.deepcopy(saved['result']['harvest_tasks']),None
    # 교통 미연결 예찰은 RobotStatus를 발행하지 않는다. 실제 영상 준비 로그와
    # Nav2 lifecycle 응답을 확인하며 별도 ready 신호를 생성하지 않는다.
    wait(lambda:'영상 사전 준비 완료' in (base/'scout.log').read_text(),300,'예찰 영상 준비')
    from lifecycle_msgs.srv import GetState
    clients=[node.create_client(GetState,'/scout_01/'+name+'/get_state')
             for name in ('controller_server','planner_server','amcl')]
    try:
        wait(lambda:all(c.service_is_ready() for c in clients),300,'예찰 Nav2 서비스')
        def active():
            return all(future(c.call_async(GetState.Request()),10,'예찰 lifecycle').current_state.id==3 for c in clients)
        wait(active,300,'예찰 Nav2 활성화')
    finally:
        for client in clients:node.destroy_client(client)
    goal=ScoutArea.Goal(robot_id='scout_01',task_id='cycle_scout_'+uuid4().hex[:12],section_id='SEC01',
        map_id='farm_map_v1',frame_id='map',crop_type='PAPRIKA',target_ripeness='RIPE',timestamp=utc())
    bundle=start_action(node,wait,future,record,ScoutArea,'/scout_01/scout_area',goal,'scout');owned.append(bundle)
    response=finish_action(bundle,future,record,result,'scout',2400)
    (base/'scout_result.json').write_text(json.dumps(dict(scout_result=result['scout']),ensure_ascii=False,indent=2)+'\n')
    tasks=[dict(message_to_ordereddict(t)) for t in response.result.harvest_tasks]
    if len(tasks)!=response.result.harvest_task_count or not tasks:raise RuntimeError('새 예찰 윈도우 없음/개수 불일치; 수확·인계 성공 생성 금지')
    # SEC01 뒤에는 북쪽 스테이션으로 역주행하지 않고 SEC02 예찰을 이어간다.
    # SEC02 결과는 별도로 보존하며 이번 SEC01 수확 목록에 합치지 않는다.
    goal=ScoutArea.Goal(robot_id='scout_01',task_id='cycle_scout_sec02_'+uuid4().hex[:12],section_id='SEC02',
        map_id='farm_map_v1',frame_id='map',crop_type='PAPRIKA',target_ripeness='RIPE',timestamp=utc())
    next_scout=start_action(node,wait,future,record,ScoutArea,'/scout_01/scout_area',goal,'scout_sec02');owned.append(next_scout)
    def save_next_scout(ticket) -> None:
        reply=ticket.result()
        data=dict(status=reply.status,result=dict(message_to_ordereddict(reply.result)))
        (base/'scout_sec02_result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        record('scout_sec02_completed',**data)
    next_scout[2].add_done_callback(save_next_scout)
    result['window_count']=len(tasks);result['harvest_results']=[]
    return tasks,next_scout

def pickup_pose(base,task):
    # 기존 분리시험과 같은 그래프 X 투영 계약. 관제 운영 계약 변경이 아니다.
    path=base/'runtime/pickup_goal.json';prior=json.loads(path.read_text());goal=copy.deepcopy(task['goal_pose'])
    goal['position']['x']=prior['position']['x'];path.write_text(json.dumps(goal)+'\n')

def resumed_harvest(base,node,wait,record,result) -> None:
    """과거 수확 집계와 이번 물리 적재 복원을 분리하고 운송 전에 확인한다."""
    import numpy as np
    manifest=json.loads((base/'resume_manifest.json').read_text())
    wait(lambda:(base/'sorting/harvest_restored.json').exists(),120,'수확 과실 초기 배치 복원')
    restored=json.loads((base/'sorting/harvest_restored.json').read_text())
    start=node.get_clock().now().nanoseconds
    wait(lambda:node.get_clock().now().nanoseconds-start>=5_000_000_000,60,'복원 과실 물리 안정화')
    snapshot=json.loads((ROOT/'sim/runs/runtime/harvest_scene.json').read_text())
    if snapshot['scene_session']!=restored['session']:raise ValueError('복원 장면 세션 불일치')
    corners=np.asarray(manifest['basket_corners_world']);origin=corners.mean(axis=0)
    u=corners[1]-corners[0];v=corners[3]-corners[0];sizes=np.array([np.linalg.norm(u),np.linalg.norm(v)])
    u/=sizes[0];v/=sizes[1];w=np.cross(u,v)
    positions={f['gt_id']:f['center_world_m'] for f in snapshot['fruits']}
    inside=[]
    for path in restored['fruit_paths']:
        delta=np.asarray(positions[path])-origin
        if abs(delta@u)<sizes[0]/2 and abs(delta@v)<sizes[1]/2 and 0<delta@w<.25:inside.append(path)
    record('restored_basket_check',source_session=manifest['source_session'],session=restored['session'],
           expected_paths=restored['fruit_paths'],inside_paths=inside)
    if set(inside)!=set(restored['fruit_paths']):raise ValueError('복원 후 바구니 적재 과실 누락; 운송 시작 거절')
    saved=json.loads((base/'resume_harvest_result.json').read_text())
    for key in ('scout','window_count','harvest_results'):result[key]=saved[key]
    result.update(scout_reused=True,harvest_reused=True,scope='transport resume from reconstructed post-harvest state')
    record('scout_reused',source=manifest['source'],**saved['scout'])
    record('harvest_reused',source=manifest['source'],results=saved['harvest_results'],
           historical_harvested_count=manifest['harvested_count'],restored_physical_count=len(inside))

def revalidate_resume_window(base,node,wait,future,record,result,owned) -> None:
    """운송 출발 전에 기존 도착 전용 Action으로 현재 세션의 window 기록을 만든다."""
    from farm_interfaces.action import HarvestTask
    config=json.loads((base/'runtime/harvest_task.json').read_text())
    if config['completion_policy']!='ARRIVAL_ONLY_NO_HARVEST':
        raise ValueError('재개 도착 검증에서 팔 실행 금지')
    manifest=json.loads((base/'resume_manifest.json').read_text())
    task=copy.deepcopy(manifest['arrival_revalidation_task'])
    task['task_id']='resume_arrival_'+uuid4().hex[:12]
    goal=HarvestTask.Goal()
    set_message_fields(goal,dict(robot_id=config['robot_id'],map_id=config['map_id'],
                                harvest_task=task,timestamp=utc()))
    bundle=start_action(node,wait,future,record,HarvestTask,'/harvest_01/harvest_task',goal,'resume_window_arrival')
    owned.append(bundle)
    finish_action(bundle,future,record,result,'resume_window_arrival',180)
    record('resume_window_ready',window_id=task['window_id'],arm_executed=False,
           historical_harvested_count=manifest['harvested_count'])

def transfer_cargo(base,node,wait,record):
    output=base/'sorting';state=json.loads((output/'runtime.json').read_text());rid=uuid4().hex
    request=dict(session=state['session'],request_id=rid,authorized_event='TRANSFER_COMPLETE')
    temp=output/'handoff_request.tmp';temp.write_text(json.dumps(request));temp.replace(output/'handoff_request.json')
    def complete():
        p=output/'handoff_result.json'
        if not p.exists():return False
        data=json.loads(p.read_text())
        return data.get('request_id')==rid
    wait(complete,20,'실제 바구니 과실 가상 인계')
    data=json.loads((output/'handoff_result.json').read_text());record('actual_cargo_transfer',**data)
    if not data['success']:raise RuntimeError('가상 인계 실패: '+data.get('error',''))
    (base/'cargo_manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def after_handoff(base,node,wait,future,record,result,owned):
    post=base/'post_sorter'
    fixture=json.loads((base/'fixture.json').read_text());cargo=json.loads((base/'cargo_manifest.json').read_text())
    fixture['fruit_paths']=cargo['fruit_paths'];fixture['actual_harvest_tested']=True;fixture['handoff_complete']=True
    temp=post/'fixture.tmp';temp.write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n');temp.replace(post/'fixture.json')
    bundle=None
    if fixture.get('overlap_cycle'):
        goal=ReturnToStation.Goal(robot_id='harvest_01',task_id='cycle_harvest_return_'+uuid4().hex[:12],station_id='STATION_HARVEST_01',map_id='farm_map_v1',timestamp=utc())
        bundle=start_action(node,wait,future,record,ReturnToStation,'/harvest_01/return_to_station',goal,'harvest_return');owned.append(bundle)
    wait(lambda:(post/'result.json').exists(),2400,'선별장 이동·도킹·선별·운송 복귀')
    data=json.loads((post/'result.json').read_text());result['sorter_and_transport_return']=data
    record('sorter_sequence_result',data=data)
    if not data['passed']:raise RuntimeError('선별장/운송복귀 실패: '+data.get('error',''))
    if bundle is None:
        goal=ReturnToStation.Goal(robot_id='harvest_01',task_id='cycle_harvest_return_'+uuid4().hex[:12],station_id='STATION_HARVEST_01',map_id='farm_map_v1',timestamp=utc())
        bundle=start_action(node,wait,future,record,ReturnToStation,'/harvest_01/return_to_station',goal,'harvest_return');owned.append(bundle)
    finish_action(bundle,future,record,result,'harvest_return',1500)

def return_scout(base,node,wait,future,record,result,owned,next_scout):
    """SEC02와 다른 로봇 복귀 후 기존 예찰 복귀 액션을 실행한다."""
    if next_scout is None:raise RuntimeError('새 SEC02 예찰 결과 누락')
    finish_action(next_scout,future,record,result,'scout_sec02',2400)
    goal=ReturnToStation.Goal(robot_id='scout_01',task_id='cycle_scout_return_'+uuid4().hex[:12],
        station_id='STATION_SCOUT_01',map_id='farm_map_v1',timestamp=utc())
    bundle=start_action(node,wait,future,record,ReturnToStation,'/scout_01/return_to_station',goal,'scout_return')
    owned.append(bundle)
    finish_action(bundle,future,record,result,'scout_return',1500)
