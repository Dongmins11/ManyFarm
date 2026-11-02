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

def harvest_handoff_ready(base,node,wait,future,record) -> None:
    """인계 전용 lifecycle·실제 충돌 입력·장치 연결을 출발 전에 확인한다."""
    from lifecycle_msgs.srv import GetState
    from nav2_msgs.msg import Costmap
    from geometry_msgs.msg import PolygonStamped
    from farm_interfaces.action import Discharge
    from nav2_msgs.action import Spin
    from rclpy.qos import qos_profile_sensor_data
    config=json.loads((base/'runtime/harvest_task.json').read_text())
    prefix='/'+config['robot_id']+'/handoff'
    states={}; samples={}; pending={}
    clients={name:node.create_client(GetState,prefix+'/'+name+'/get_state')
             for name in ('controller_server','behavior_server')}
    services=[node.create_client(Trigger,path) for path in config['transfer']['device_services'].values()]
    actions=[ActionClient(node,Discharge,config['transfer']['discharge_action']['endpoint']),
             ActionClient(node,Spin,prefix+'/spin')]
    def observe(key,msg):
        stamp=msg.header.stamp
        samples[key]=(node.get_clock().now().nanoseconds,stamp.sec*10**9+stamp.nanosec)
    subscriptions=[node.create_subscription(kind,prefix+'/local_costmap/'+topic,
        lambda msg,k=key:observe(k,msg),qos_profile_sensor_data)
        for key,kind,topic in (('costmap',Costmap,'costmap_raw'),
                              ('footprint',PolygonStamped,'published_footprint'))]
    def check():
        for name,client in clients.items():
            ticket=pending.get(name)
            if ticket is not None and ticket.done():
                states[name]=ticket.result().current_state.id
                del pending[name]
            if name not in pending and client.service_is_ready():
                pending[name]=client.call_async(GetState.Request())
        now=node.get_clock().now().nanoseconds
        return (all(states.get(name)==3 for name in clients)
            and all(key in samples and 0<=now-samples[key][0]<=500_000_000
                    and -100_000_000<=now-samples[key][1]<=500_000_000
                    for key in ('costmap','footprint'))
            and all(c.service_is_ready() for c in services)
            and all(c.server_is_ready() for c in actions))
    try:
        wait(check,60,'인계 전용 제어기·충돌 입력·배출 장치 준비')
        record('harvest_handoff_ready',states=states,samples=samples)
    except Exception:
        record('harvest_handoff_not_ready',states=states,samples=samples,
            services=[c.service_is_ready() for c in services],
            actions=[c.server_is_ready() for c in actions])
        raise
    finally:
        for sub in subscriptions:node.destroy_subscription(sub)
        for c in [*clients.values(),*services]:node.destroy_client(c)
        for c in actions:c.destroy()

def transport_robot_ready(node,wait,record) -> None:
    """액션 서버 발견과 실제 TF·센서·정지 준비를 구분한다. 새 상태만 받는다."""
    from farm_interfaces.msg import RobotStatus
    from rclpy.qos import qos_profile_sensor_data
    status={}
    def observe(message):
        data=dict(message_to_ordereddict(message))
        if any(status.get(k)!=data.get(k) for k in ('ready','state','error_code','error_message')):
            record('transport_readiness',data=data)
        status.update(data)
    subscription=node.create_subscription(RobotStatus,'/transport_01/status',observe,qos_profile_sensor_data)
    try:
        wait(lambda:status.get('ready',False),180,'운송 실제 TF·센서·정지 준비')
        record('transport_robot_ready',data=status.copy())
    except Exception:
        record('transport_not_ready',data=status.copy())
        raise
    finally:
        node.destroy_subscription(subscription)

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
    schedule=json.loads((base/'single_cycle.json').read_text())
    section=schedule.get('section','SEC01')
    result.update(section=section, single_section=schedule.get('single_section',False))
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
    snapshot=ROOT/'sim/runs/runtime/harvest_scene.json'
    if snapshot.exists():
        (base/'initial_scene.json').write_bytes(snapshot.read_bytes())
    goal=ScoutArea.Goal(robot_id='scout_01',task_id='cycle_scout_'+uuid4().hex[:12],section_id=section,
        map_id='farm_map_v1',frame_id='map',crop_type='PAPRIKA',target_ripeness='RIPE',timestamp=utc())
    bundle=start_action(node,wait,future,record,ScoutArea,'/scout_01/scout_area',goal,'scout');owned.append(bundle)
    response=finish_action(bundle,future,record,result,'scout',2400)
    (base/'scout_result.json').write_text(json.dumps(dict(scout_result=result['scout']),ensure_ascii=False,indent=2)+'\n')
    tasks=[dict(message_to_ordereddict(t)) for t in response.result.harvest_tasks]
    if len(tasks)!=response.result.harvest_task_count or not tasks:raise RuntimeError('새 예찰 윈도우 없음/개수 불일치; 수확·인계 성공 생성 금지')
    if schedule.get('single_section'):
        # 교통 미연결 캠페인은 예찰 복귀 완료 후 수확을 출발시킨다.
        result['window_count']=len(tasks);result['harvest_results']=[]
        return_scout(base,node,wait,future,record,result,owned,None)
        return tasks,None
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
    schedule=json.loads((base/'single_cycle.json').read_text())
    if schedule.get('single_section'):
        import yaml
        profile=json.loads((base/'runtime/transport_runtime.json').read_text())
        graph=json.loads((ROOT/profile['route_graph']).read_text())
        spec=yaml.safe_load((ROOT/'sim/ros_ws/src/farm_sim_config/config/task.yaml').read_text())
        route=spec['sections'][schedule['section']]['harvest_route']
        nodes={f['properties']['id']:f['geometry']['coordinates'] for f in graph['features']
               if f['geometry']['type']=='Point'}
        start,end=nodes[route['entry_node_id']],nodes[route['exit_node_id']]
        if abs(start[0]-end[0])>1e-8:raise ValueError('직선 베드 운송 주행선 필요')
        goal=copy.deepcopy(task['goal_pose'])
        if not min(start[1],end[1])<=goal['position']['y']<=max(start[1],end[1]):
            raise ValueError('인계 목표가 해당 섹션 주행선 밖임')
        goal['position']['x']=start[0]
        # 차체 중심까지 보내면 마커 전환을 놓쳤을 때 수확로봇을 밀고 들어간다.
        # 장착표와 기존 접근 거리로 대기점을 계산한다. 실제 자세 정답은 사용하지 않는다.
        import math
        fleet=json.loads((base/'runtime/fleet.json').read_text())
        layout=json.loads((ROOT/fleet['docking_markers']).read_text())
        profiles=json.loads((ROOT/profile['precision_profiles']).read_text())['profiles']
        approach=profiles[profile['pickup_workflow']['approach_profile']]
        marker=next(m for m in layout['markers'] if m['id']==approach['target_marker_id'])
        harvest=json.loads((base/'runtime/harvest.json').read_text())
        binding=harvest['scene_binding']
        if marker['reference_prim']!=binding['robot_prim']+'/'+binding['articulation_relative']:
            raise ValueError('인계 마커와 수확 자산 기준 프레임 불일치')
        asset_yaw=binding.get('control_frame_yaw_rad',0.)
        marker_forward=math.cos(asset_yaw)*marker['center_m'][0]+math.sin(asset_yaw)*marker['center_m'][1]
        marker_range=approach['acquire_then_odom']['distance_corridor']['target_range_m']
        margin=approach['route_handoff']['approach_margin_m']
        stand_off=marker_range+margin-marker_forward
        if not math.isfinite(stand_off) or stand_off<=0:
            raise ValueError('인계 접근 대기 거리 오류')
        goal['position']['y']-=stand_off*math.sin(goal['yaw'])
        if not min(start[1],end[1])<=goal['position']['y']<=max(start[1],end[1]):
            raise ValueError('안전한 인계 대기점이 해당 섹션 주행선 밖임')
        (base/'runtime/pickup_goal.json').write_text(json.dumps(goal)+'\n')
        (base/'pickup_projection.json').write_text(json.dumps(dict(section=schedule['section'],
            original=task['goal_pose'],selected=goal,route=route,stand_off_m=stand_off,
            marker_forward_m=marker_forward,marker_range_m=marker_range,approach_margin_m=margin),indent=2)+'\n')
        return
    # 기존 SEC01 분리시험의 투영 계약은 보존한다.
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
    from cycle_departure_gate import DepartureGate
    post=base/'post_sorter'
    fixture=json.loads((base/'fixture.json').read_text());cargo=json.loads((base/'cargo_manifest.json').read_text())
    gate=DepartureGate(base,node,wait,record)
    bundle=None
    def start_return():
        goal=ReturnToStation.Goal(robot_id='harvest_01',task_id='cycle_harvest_return_'+uuid4().hex[:12],station_id='STATION_HARVEST_01',map_id='farm_map_v1',timestamp=utc())
        ticket=start_action(node,wait,future,record,ReturnToStation,'/harvest_01/return_to_station',goal,'harvest_return')
        owned.append(ticket)
        return ticket
    def return_clear():
        if bundle[2].done() and 'harvest_return' not in result:
            finish_action(bundle,future,record,result,'harvest_return',1500)
        return gate.cleared('harvest')
    def transport_clear():
        if (post/'result.json').exists():
            data=json.loads((post/'result.json').read_text())
            if not data['passed']:raise RuntimeError('운송 출발 실패: '+data.get('error',''))
        return gate.cleared('transport')
    try:
        first=gate.plan()
        if first=='harvest':
            bundle=start_return()
            wait(return_clear,1500,'수확 선행 복귀 경로 이탈')
        fixture.update(fruit_paths=cargo['fruit_paths'],actual_harvest_tested=True,handoff_complete=True,
                       harvest_return_gate=uuid4().hex)
        temp=post/'fixture.tmp';temp.write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n');temp.replace(post/'fixture.json')
        if first=='transport':
            wait(transport_clear,2400,'운송 선행 출발 경로 이탈')
            bundle=start_return()
        # 선별장 작업과 병행하되 운송 스테이션 복귀는 수확 복귀 SUCCESS 이후다.
        if 'harvest_return' not in result:finish_action(bundle,future,record,result,'harvest_return',1500)
        grant=dict(token=fixture['harvest_return_gate'],reply=result['harvest_return'])
        temp=post/'harvest_return_complete.tmp';temp.write_text(json.dumps(grant,ensure_ascii=False)+'\n');temp.replace(post/'harvest_return_complete.json')
        record('transport_station_return_authorized',**grant)
        wait(lambda:(post/'result.json').exists(),3660,'선별장 이동·도킹·선별·운송 복귀')
        data=json.loads((post/'result.json').read_text());result['sorter_and_transport_return']=data
        record('sorter_sequence_result',data=data)
        if not data['passed']:raise RuntimeError('선별장/운송복귀 실패: '+data.get('error',''))
        if 'harvest_return' not in result:finish_action(bundle,future,record,result,'harvest_return',1500)
    finally:gate.close()

def return_scout(base,node,wait,future,record,result,owned,next_scout):
    """SEC02와 다른 로봇 복귀 후 기존 예찰 복귀 액션을 실행한다."""
    if result.get('single_section'):
        if 'scout_return' in result:return
    else:
        if next_scout is None:raise RuntimeError('새 SEC02 예찰 결과 누락')
        finish_action(next_scout,future,record,result,'scout_sec02',2400)
    goal=ReturnToStation.Goal(robot_id='scout_01',task_id='cycle_scout_return_'+uuid4().hex[:12],
        station_id='STATION_SCOUT_01',map_id='farm_map_v1',timestamp=utc())
    bundle=start_action(node,wait,future,record,ReturnToStation,'/scout_01/return_to_station',goal,'scout_return')
    owned.append(bundle)
    finish_action(bundle,future,record,result,'scout_return',1500)
