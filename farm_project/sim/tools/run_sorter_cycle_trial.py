"""선별장 BucketUnload→스테이션 복귀를 실제 시뮬에서 분리 검증한다.

인계 성공을 가정해 결과를 만들지 않는다. 선별장 접근 경로에서 시작하는 별도
시험이며 공통 도킹/하역 FSM은 그대로 사용한다. --sorting은 기존 농장 과실의
가상 레인 투입과 실제 HCR 선별을 연결한다. 배출 기구 물리는 평가하지 않는다.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import yaml

from prepare_harvest_handoff import ROOT, CONFIG, prepare
from prepare_pickup_trial import prepare_pickup, SOURCE


def prepare_sorter(base: Path) -> Path:
    """원본 업무 설정의 지도 참조·가상 장치 endpoint만 시험 환경에 연결한다."""
    base.mkdir(parents=True, exist_ok=False)
    runtime = base/'runtime'
    prepare(runtime)
    def write(name: str, value: dict) -> str:
        path = runtime/name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        return str(path.relative_to(ROOT))
    stations = json.loads((CONFIG/'station_spawn.json').read_text())
    write('stations.json', stations)
    # 기존 프로파일 조립기를 재사용한다. 이 pose는 인계 실행이나 결과로 쓰지 않는다.
    prepare_pickup(runtime, dict(goal_pose=dict(frame_id='map', position=dict(x=0.,y=0.,z=0.),yaw=0.)),sorter=True)
    profile = json.loads((runtime/'transport_runtime.json').read_text())
    source = yaml.safe_load(subprocess.check_output(['git','show',SOURCE+
        ':farm_project/robot/config/environments/transport_docking_trial.yaml'],cwd=ROOT))
    registry = yaml.safe_load((ROOT/profile['destinations']).read_text())
    sorter = registry['destinations']['SORT_01']
    graph = json.loads((ROOT/profile['route_graph']).read_text())
    nodes = {f['properties']['id']:f['geometry']['coordinates'][:2]
             for f in graph['features'] if f['geometry']['type']=='Point'}
    end = sorter['approach_node_id']
    incoming = {f['properties']['startid'] for f in graph['features']
        if f['geometry']['type'] in ('LineString','MultiLineString') and f['properties']['endid']==end}
    if len(incoming)!=1:raise ValueError('선별장에 연결되는 기존 단일 접근 edge 필요')
    start = next(iter(incoming))
    yaw = math.atan2(nodes[end][1]-nodes[start][1],nodes[end][0]-nodes[start][0])
    sorter.update(docking_profile='sort_01_distance_trial',clearance_node_id=start,
                  clearance_yaw_rad=sorter['approach_yaw_rad'],scope='BucketUnload docking/virtual unload/clear trial')
    profile['destinations'] = write('destinations.json',registry)
    profile['unload_workflows'] = copy.deepcopy(source['unload_workflows'])
    profile['sorter_distance_handoff'] = copy.deepcopy(source['sorter_distance_handoff'])
    profile['sorter_distance_handoff'].update(observation_start_node=start,approach_end_node=end)
    profile['mechanical_device'].update(unload_service='sim/sorter/unload',stop_service='sim/sorter/stop')
    stations = json.loads((CONFIG/'station_spawn.json').read_text())
    stations['stations']['transport_01'].update(xy_m=nodes[start],yaw_rad=yaw)
    write('stations.json',stations)
    nav = json.loads((runtime/'nav2_transport.json').read_text())
    nav['amcl']['ros__parameters']['initial_pose'] = dict(x=nodes[start][0],y=nodes[start][1],z=0.,yaw=yaw)
    write('nav2_transport.json',nav)
    write('transport_runtime.json',profile)
    fleet = json.loads((runtime/'fleet.json').read_text())
    fleet['device_configs'] = [profile['device_config']]
    fleet.pop('evaluation_config',None)
    fleet.pop('basket_alignment',None)
    fleet['station_config'] = str((runtime/'stations.json').relative_to(ROOT))
    # 인계42 시험 배치를 이 시험에 사용하지 않는다. 기존40번 임시 마커 유지.
    marker_path = json.loads((CONFIG/'transport_fleet.json').read_text())['docking_markers']
    markers = json.loads((ROOT/marker_path).read_text())
    markers['markers'] = [m for m in markers['markers'] if m['id']==profile['sorter_distance_handoff']['marker_id']]
    if len(markers['markers'])!=1:raise ValueError('기존 선별장 마커 1개 필요')
    fleet['docking_markers'] = write('sorter_layout.json',markers)
    write('fleet.json',fleet)
    real_nav = yaml.safe_load(subprocess.check_output(['git','show',SOURCE+':farm_project/'+source['nav_params']],cwd=ROOT))
    original_amcl = real_nav['amcl']['ros__parameters']
    selected_amcl = nav['amcl']['ros__parameters']
    localization_changes = [dict(parameter='amcl.'+key, original=original_amcl[key], selected=selected_amcl[key],
        reason='sim recorded sensor replay: more frequent observation updates; real file unchanged')
        for key in ('update_min_d','update_min_a') if original_amcl[key]!=selected_amcl[key]]
    fixture = dict(source_commit=SOURCE,scope='isolated public BucketUnload + ReturnToStation',
        domain=13,discovery='SUBNET',initial_xy=nodes[start],initial_yaw=yaw,
        initial_pose_only=True,truth_injected_into_control=False,traffic_enabled=False,
        fresh_scout=False,handoff_tested=False,frontend_http_tested=False,
        virtual_mechanism=True,fruit_physics_tested=False,count_valid=False,
        unload_guard='own task WAITING_FOR_UNLOAD then UNLOADING_STARTED; fresh odom stopped 0.8s; one completion',
        original_sorter_distance_handoff=source['sorter_distance_handoff'],
        selected_sorter_distance_handoff=profile['sorter_distance_handoff'],
        original_unload_workflows=source['unload_workflows'],selected_unload_workflows=profile['unload_workflows'],
        numeric_control_changes=localization_changes)
    (base/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
    return runtime


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--keep-unused-scout',action='store_true',help='진단 전용: 이전 씬의 미실행 예찰 모델을 남겨 비교')
    parser.add_argument('--sorting',action='store_true',help='농장 HCR 모델·기존 과실 가상 투입·SortBatch까지 연결')
    parser.add_argument('--dock-entry-fixture',action='store_true',help='기존 접근 edge의 도킹 직전에서 시작하는 분리 시험')
    args=parser.parse_args();base=args.output.resolve()
    if not base.is_relative_to(ROOT/'sim/runs'):raise ValueError('sim/runs 아래 새 경로 필요')
    if os.environ.get('ROS_DOMAIN_ID')!='13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE')!='SUBNET':
        raise ValueError('ROS Domain13/SUBNET 필요')
    runtime=prepare_sorter(base)
    if args.sorting:
        configure_sorting(base, runtime)
    if args.dock_entry_fixture:
        if not args.sorting:raise ValueError('--dock-entry-fixture는 --sorting 시험 전용')
        configure_dock_entry(base, runtime)
    if not args.keep_unused_scout:
        configure_unused_scout_exclusion(base,runtime)
    if args.prepare_only:return
    os.environ['ROS_LOG_DIR']=str(base/'ros_logs')
    os.environ['MOTION_GATE_TRACE']=str(base/'gate_timing.jsonl')
    os.environ['DOCKING_FRESHNESS_TRACE']=str(base/'freshness_trace.jsonl')
    processes=[];streams=[]
    def start(name: str,command: list[str]) -> subprocess.Popen:
        stream=(base/(name+'.log')).open('w');streams.append(stream)
        process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append((name,process));return process
    try:
        if args.sorting:
            output=base/'sorting'
            start('sorter',['ros2','run','hcr_sorting','sorter_node','--ros-args',
                '-p','modbus_host:=127.0.0.1','-p','modbus_peer:=127.0.0.1','-p','modbus_port:=1502',
                '-p','receive_enabled:=true','-p','camera_state:='+str(output/'state.json'),
                '-p','journal:='+str(output/'journal.sqlite3'),'-p','runtime_state:='+str(output/'ros_runtime.json')])
        start('adapter',['ros2','run','farm_sim_devices','ros_adapter','--ros-args','-r','__ns:=/transport_01',
            '-p','use_sim_time:=true','-p','config_file:='+str(runtime/'transport.json')])
        start('gate',['/usr/bin/python3','sim/tools/trace_motion_gate.py','--ros-args',
            '-r','__ns:=/transport_01','-p','use_sim_time:=true'])
        start('precision',['/usr/bin/python3','sim/tools/trace_docking_freshness.py','--ros-args',
            '--params-file',str(runtime/'precision.yaml'),'-r','__ns:=/transport_01',
            '-r','/cmd_vel:=motion/precision','-r','/odom:=odom',
            '-r','/dock/cmd:=precision_legacy_disabled','-r','/dock/state:=precision_legacy_state'])
        start('transport',['ros2','launch','farm_sim_runtime','transport_navigation.launch.py',
            'project_root:='+str(ROOT),'environment_config:='+str(runtime/'transport_runtime.json'),
            'journal_dir:='+str(base/'transport_journal')])
        start('isaac',['ros2','launch','farm_sim_runtime','isaac.launch.py','project_root:='+str(ROOT),
            'fleet_config:='+str(runtime/'fleet.json'),'headless:=true','physics_device:=cpu',
            'performance_log:='+str(base/'frame_performance.jsonl'),'duration_s:=1200',
            'isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python'])
        probe=start('probe',['/usr/bin/python3','sim/tools/probe_sorter_cycle.py',str(base)])
        deadline=time.monotonic()+2000
        while probe.poll() is None:
            failed=[(n,p.returncode) for n,p in processes if n!='probe' and p.poll() is not None]
            if failed:raise RuntimeError('시험 프로세스 종료: '+str(failed))
            if time.monotonic()>deadline:raise TimeoutError('시험 watchdog')
            time.sleep(1)
        if probe.returncode:raise RuntimeError('시험 실패; result.json 확인')
    finally:
        for _,p in reversed(processes):
            if p.poll() is None:os.killpg(p.pid,signal.SIGINT)
        deadline=time.monotonic()+45
        while any(p.poll() is None for _,p in processes) and time.monotonic()<deadline:time.sleep(.5)
        for _,p in processes:
            if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        (base/'process_exit.json').write_text(json.dumps({n:p.poll() for n,p in processes},indent=2)+'\n')
        for stream in streams:stream.close()


def configure_sorting(base: Path, runtime: Path) -> None:
    """도킹 기준면을 유지하고 신규 HCR 모델/시험 초기 적재를 설정으로 연결한다."""
    settings=json.loads((CONFIG/'sorter_integration.json').read_text())
    trial=json.loads((CONFIG/'sorter_cycle_fixture.json').read_text())
    settings['fixture_fruit_paths']=trial['fruit_paths']
    settings['output_dir']=str((base/'sorting').relative_to(ROOT))
    fixture=json.loads((base/'fixture.json').read_text())
    profile=json.loads((runtime/'transport_runtime.json').read_text())
    graph=json.loads((ROOT/profile['route_graph']).read_text())
    nodes={f['properties']['id']:f['geometry']['coordinates'][:2] for f in graph['features'] if f['geometry']['type']=='Point'}
    registry=json.loads((runtime/'destinations.json').read_text())
    destination=registry['destinations']['SORT_01']
    end=nodes[destination['approach_node_id']]
    yaw=fixture['initial_yaw']
    c=json.loads((ROOT/settings['source_workspace']/settings['source_config']).read_text())
    r=c['intake'];front=r['low_x']+math.sqrt(r['slope_length']**2-r['rise']**2)-.02+.0125
    # 기존 접근 edge와 투입면을 직교시킨다. 제어기의 거리/각도 허용치를 바꾸지 않는다.
    setback=settings['intake_distance_from_approach_m']
    settings['station_pose_world_m']=[end[0]+(setback+front)*math.cos(yaw),end[1]+(setback+front)*math.sin(yaw),0.]
    settings['station_yaw_rad']=yaw-math.pi
    from build_sorter_map import validate
    profile['map_yaml'] = validate(settings)
    (runtime/'transport_runtime.json').write_text(json.dumps(profile,indent=2))
    destination.update(approach_yaw_rad=yaw,clearance_yaw_rad=yaw)
    destination['model_reference']=dict(prim_path='/World/HCRStation',
        world_xy_m=settings['station_pose_world_m'][:2],basis=settings['placement_basis'])
    profiles=json.loads((runtime/'precision_profiles.json').read_text())
    profiles['profiles']['sort_departure_distance_trial']['distance_departure']['map_yaw_rad']=yaw
    (runtime/'precision_profiles.json').write_text(json.dumps(profiles,indent=2))
    (runtime/'destinations.json').write_text(json.dumps(registry,indent=2))
    (runtime/'sorter.json').write_text(json.dumps(settings,indent=2))
    device=json.loads((runtime/'transport.json').read_text())
    device['runtime']['robotarm_physics_config']=json.loads((CONFIG/'harvest.json').read_text())['runtime']['robotarm_physics_config']
    device['lidar']['diagnostic_front_hits']=True
    (runtime/'transport.json').write_text(json.dumps(device,indent=2))
    fleet=json.loads((runtime/'fleet.json').read_text())
    fleet['sorter_config']=str((runtime/'sorter.json').relative_to(ROOT))
    (runtime/'fleet.json').write_text(json.dumps(fleet,indent=2))
    markers=json.loads((runtime/'sorter_layout.json').read_text())
    marker=markers['markers'][0]
    marker.update(parent_prim='/World/HCRStation',reference_prim='/World/HCRStation',
        center_m=[front+.001,0.,.106],right=[0,1,0],up=[0,0,1],
        basis='HCR 기존 IntakeSupport 전면; 접근 edge와 직교, 원본 후진 종료 거리와 URDF 센서 offset을 반영한 배치; 실측아님')
    (runtime/'sorter_layout.json').write_text(json.dumps(markers,indent=2))
    fixture=json.loads((base/'fixture.json').read_text())
    fixture.update(integrated_sorting=True,sorting_output=str(base/'sorting'),
        fruit_paths=settings['fixture_fruit_paths'],actual_harvest_tested=False,
        original_fruit_identity_preserved=True,fruit_physics_tested=True,
        source_hcr_geometry_unchanged=True,scope='farm model + BucketUnload + virtual existing-fruit deposit + clearance + SortBatch + ReturnToStation')
    (base/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2))


def configure_unused_scout_exclusion(base: Path, runtime: Path) -> None:
    """진단용 USD 세션 레이어. 원본 씬/실행 중인 예찰 로봇은 수정하지 않는다."""
    scout=json.loads((CONFIG/'scout_fleet.json').read_text())
    fleet=json.loads((runtime/'fleet.json').read_text())
    active=[json.loads((ROOT/p).read_text()) for p in fleet['device_configs']]
    if any(c['robot_id']==scout['robot_id'] for c in active):
        raise ValueError('실행 fleet의 예찰 로봇은 제외할 수 없습니다.')
    prim=scout['scene_binding']['robot_prim']
    parts=prim.strip('/').split('/')
    if len(parts)!=2:raise ValueError('진단 대상은 World 바로 아래 모델이어야 합니다.')
    source=ROOT/'sim/assets'/active[0]['scene']
    layer=runtime/'without_unused_scout.usda'
    layer.write_text('#usda 1.0\n(\n    metersPerUnit = 1\n    upAxis = "Z"\n    subLayers = [@'+str(source)+'@]\n)\n'
        +'over '+json.dumps(parts[0])+'\n{\n    over '+json.dumps(parts[1])+' (active = false)\n    {\n    }\n}\n')
    for path,cfg in zip(fleet['device_configs'],active):
        cfg['scene']=str(layer)
        (ROOT/path).write_text(json.dumps(cfg,indent=2))
    fixture=json.loads((base/'fixture.json').read_text())
    fixture['excluded_unused_scene_robot']=prim
    (base/'fixture.json').write_text(json.dumps(fixture,indent=2))


def configure_dock_entry(base: Path, runtime: Path) -> None:
    """초기 위치만 기존 edge 위로 옮긴다. 실행 중 정답 주입/도킹 완료 가정은 없다."""
    trial=json.loads((CONFIG/'sorter_cycle_fixture.json').read_text())
    fixture=json.loads((base/'fixture.json').read_text())
    profile=json.loads((runtime/'transport_runtime.json').read_text())
    graph=json.loads((ROOT/profile['route_graph']).read_text())
    nodes={f['properties']['id']:f['geometry']['coordinates'][:2] for f in graph['features'] if f['geometry']['type']=='Point'}
    c=profile['sorter_distance_handoff'];a,b=nodes[c['observation_start_node']],nodes[c['approach_end_node']]
    distance=trial['entry_distance_before_approach_m'];length=math.dist(a,b)
    if not 0<distance<length:raise ValueError('도킹 분리 시험 시작점은 기존 edge 내부여야 합니다.')
    xy=[b[i]+(a[i]-b[i])*distance/length for i in range(2)]
    yaw=fixture['initial_yaw']
    stations=json.loads((runtime/'stations.json').read_text())
    stations['stations']['transport_01'].update(xy_m=xy,yaw_rad=yaw)
    (runtime/'stations.json').write_text(json.dumps(stations,indent=2))
    nav=json.loads((runtime/'nav2_transport.json').read_text())
    nav['amcl']['ros__parameters']['initial_pose']=dict(x=xy[0],y=xy[1],z=0.,yaw=yaw)
    (runtime/'nav2_transport.json').write_text(json.dumps(nav,indent=2))
    fixture.update(initial_xy=xy,dock_entry_fixture=True,full_approach_edge_tested=False,
                   docking_control_policy='unchanged real source; align_before_lidar absent/false')
    (base/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
