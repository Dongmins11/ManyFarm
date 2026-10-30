"""SEC01 새 예찰부터 양 로봇 복귀까지 한 세션·한 시도만 실행한다."""
import json
import hashlib
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import yaml
from prepare_harvest_handoff import ROOT, CONFIG
from run_sorter_cycle_trial import prepare_sorter, configure_sorting


def prepare_cycle(base: Path, scout_result: Path | None = None) -> Path:
    runtime=prepare_sorter(base)
    configure_sorting(base,runtime)
    def read(name):return json.loads((runtime/name).read_text())
    def write(name,data): (runtime/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    stations=json.loads((CONFIG/'station_spawn.json').read_text())
    write('stations.json',stations)
    nav=read('nav2_transport.json');s=stations['stations']['transport_01']
    nav['amcl']['ros__parameters']['initial_pose']=dict(x=s['xy_m'][0],y=s['xy_m'][1],z=0.,yaw=s['yaw_rad'])
    write('nav2_transport.json',nav)
    sorter=read('sorter.json');sorter['fixture_fruit_paths']=[];write('sorter.json',sorter)
    fleet=json.loads((CONFIG/'transport_fleet.json').read_text())
    fleet['device_configs']=[str((runtime/'harvest.json').relative_to(ROOT)) if p.endswith('/harvest.json') else
                           str((runtime/'transport.json').relative_to(ROOT)) if p.endswith('/transport.json') else p
                           for p in fleet['device_configs']]
    fleet['station_config']=str((runtime/'stations.json').relative_to(ROOT))
    fleet['sorter_config']=str((runtime/'sorter.json').relative_to(ROOT))
    markers=json.loads((ROOT/fleet['docking_markers']).read_text())
    # 이전 실제 SEC01 인계시험에서 사용한 동일 임시 장착 위치를 보존한다.
    marker=next(m for m in markers['markers'] if m['id']==42)
    marker.update(center_m=[.34,-.06,.081],right=[0,1,0],
                  basis='Existing SEC01 handoff trial provisional mounting; not measured hardware')
    markers['markers']=[m for m in markers['markers'] if m['id']!=40]+read('sorter_layout.json')['markers']
    write('cycle_layout.json',markers);fleet['docking_markers']=str((runtime/'cycle_layout.json').relative_to(ROOT))
    write('fleet.json',fleet)
    map_yaml=read('transport_runtime.json')['map_yaml']
    for name,source in [('scout_runtime.yaml','scout_fleet_runtime.yaml'),('harvest_runtime.yaml',None)]:
        profile=yaml.safe_load(((CONFIG/source) if source else runtime/name).read_text())
        old_map=yaml.safe_load((ROOT/profile['map_yaml']).read_text())
        map_path=ROOT/map_yaml;new_map=yaml.safe_load(map_path.read_text())
        if {k:v for k,v in old_map.items() if k!='image'}!={k:v for k,v in new_map.items() if k!='image'}:
            raise ValueError('태그 좌표 재등록 필요: 지도 좌표계/해상도 변경')
        tag=yaml.safe_load((ROOT/profile['tag_localization_config']).read_text())
        if tag.get('pixel_bias_profile'):raise ValueError('새 지도 pixel bias 검증 필요')
        assets=json.loads((ROOT/tag['assets_file']).read_text())
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        tag['map_yaml_sha256']=digest(map_path)
        tag['map_image_sha256']=digest(map_path.parent/new_map['image'])
        from build_tag_localization import version
        assets['map_version']=version([tag['map_yaml_sha256'],tag['map_image_sha256']])
        assets['registration_evidence']['cycle_map_rebinding']='HCR static obstacle update only; unchanged map frame/resolution/origin and tag placements'
        asset_name=name.replace('_runtime.yaml','_tag_assets.json');write(asset_name,assets)
        tag['assets_file']=str((runtime/asset_name).relative_to(ROOT))
        tag_name=name.replace('_runtime.yaml','_tag.yaml');(runtime/tag_name).write_text(yaml.safe_dump(tag,sort_keys=False))
        profile['tag_localization_config']=str((runtime/tag_name).relative_to(ROOT))
        profile['map_yaml']=map_yaml
        (runtime/name).write_text(yaml.safe_dump(profile,sort_keys=False))
        from farm_tag_localization.runtime import validate_binding
        validate_binding(tag,profile,ROOT)
    f=json.loads((base/'fixture.json').read_text())
    f.update(scope='SEC01 fresh survey/all windows/handoff/sorting/harvest and transport returns; scout continues SEC02, one attempt',
             scout_after_sec01='survey_SEC02_then_hold',
             fresh_scout=True,full_section=True,fruit_paths=[],initial_pose_only=True,
             actual_harvest_tested=True,frontend_http_tested=False,
             robot_initial_stations=stations['stations'],source_progress_changes=f['progress_checker_changes'])
    # 분리시험의 접근점 초기배치 필드는 전체시험에 적용하지 않는다.
    f.pop('initial_xy',None);f.pop('initial_yaw',None)
    if scout_result is not None:
        saved=json.loads(scout_result.read_text())['scout_result'];result=saved['result'];tasks=result['harvest_tasks']
        if (saved['status']!=4 or result['result_code']!='SUCCESS' or result['section_id']!='SEC01'
                or not tasks or len(tasks)!=result['harvest_task_count']
                or len({t['window_id'] for t in tasks})!=len(tasks)
                or sum(t['expected_count'] for t in tasks)!=result['total_expected_count']):
            raise ValueError('재사용 가능한 SEC01 예찰 성공 결과가 아님')
        for task in tasks:
            pose=task['goal_pose']
            if (pose['frame_id']!='map' or not all(math.isfinite(v) for v in [*pose['position'].values(),pose['yaw']])
                    or type(task['expected_count']) is not int or task['expected_count']<0):
                raise ValueError('저장 윈도우 좌표/수량 오류')
        ys=[t['goal_pose']['position']['y'] for t in tasks]
        if ys!=sorted(ys,reverse=True):raise ValueError('SEC01 작업 방향 순서 불일치')
        prior_tag=yaml.safe_load((scout_result.parent/'runtime/scout_tag.yaml').read_text())
        current_tag=yaml.safe_load((runtime/'scout_tag.yaml').read_text())
        if any(prior_tag[k]!=current_tag[k] for k in ('map_yaml_sha256','map_image_sha256')):
            raise ValueError('저장 예찰 당시 지도와 현재 지도 불일치')
        (base/'reused_scout_result.json').write_bytes(scout_result.read_bytes())
        f.update(fresh_scout=False,scout_after_sec01='not_commanded',
                 scope='reuse SEC01 survey; harvest/handoff/sort/transport and harvest returns, one attempt',
                 reused_scout_source=str(scout_result),reused_scout_sha256=hashlib.sha256(scout_result.read_bytes()).hexdigest())
    (base/'fixture.json').write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n')
    (base/'single_cycle.json').write_text(json.dumps(dict(section='SEC01',attempts=1))+'\n')
    # 장치 서비스는 시작부터 제공하되 운송/선별 명령은 실제 인계 완료 뒤에만 보낸다.
    post=base/'post_sorter';post.mkdir()
    (post/'fixture.json').write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n')
    return runtime


def main() -> None:
    base=Path(sys.argv[1]).resolve()
    if os.environ.get('ROS_DOMAIN_ID')!='13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE')!='SUBNET':
        raise ValueError('ROS Domain13/SUBNET 필요')
    if not base.is_relative_to(ROOT/'sim/runs'):raise ValueError('sim/runs 아래 새 경로 필요')
    from ament_index_python.packages import get_package_prefix
    get_package_prefix('hcr_sorting')  # 선별 overlay 누락은 시뮬 시작 전에 거절한다.
    subprocess.run(['/home/ysy/venv/robot_venv/bin/python','-c','import torch, ultralytics'],check=True)
    scout_result=(Path(sys.argv[sys.argv.index('--scout-result')+1]).resolve() if '--scout-result' in sys.argv else None)
    resume=(Path(sys.argv[sys.argv.index('--resume-harvest')+1]).resolve() if '--resume-harvest' in sys.argv else None)
    if resume is not None:
        scout_result=resume/'reused_scout_result.json'
    overlap='--overlap-cycle' in sys.argv
    if overlap and (scout_result is not None or '--pickup-preflight' in sys.argv):
        raise ValueError('병행 전체시험은 새 예찰·수확만 허용')
    if scout_result is not None and '--pickup-preflight' in sys.argv:raise ValueError('예찰 재사용과 접수 단독검증은 별도 실행')
    runtime=prepare_cycle(base,scout_result)
    if overlap:
        schedule=dict(section='SEC01',attempts=1,overlap_cycle=True,
                      scout_return='after_SEC02_and_other_robot_returns')
        (base/'single_cycle.json').write_text(json.dumps(schedule)+'\n')
        for path in (base/'fixture.json',base/'post_sorter/fixture.json'):
            fixture=json.loads(path.read_text())
            fixture.update(overlap_cycle=True,require_all_sorted=True,
                scout_after_sec01='survey_SEC02_then_return_after_other_robots',
                scope='fresh SEC01 survey/harvest; SEC02 survey; concurrent handoff returns/sorting; all robots return')
            path.write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
    if resume is not None:
        from prepare_transport_resume import prepare_resume
        prepare_resume(base,resume,Path(sys.argv[sys.argv.index('--resume-scene')+1]).resolve())
    if '--stop-after-docking' in sys.argv:
        if resume is None:raise ValueError('도킹 단독시험은 수확 완료 상태 재사용 필요')
        for path in (base/'fixture.json',base/'post_sorter/fixture.json'):
            fixture=json.loads(path.read_text())
            fixture.update(scope='transport departure through docking only; stop before cargo transfer',stop_after_docking=True)
            path.write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
    if '--prepare-only' in sys.argv:return
    # 반복시험 중 설정 개선이 적용되면 시도별 소스/수치를 구분한다.
    selected = {}
    for relative in ('sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml',
                     'sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json',
                     'sim/ros_ws/src/farm_sim_config/config/student_policy.json',
                     'sim/ros_ws/src/farm_sim_config/config/harvest.json',
                     'sim/ros_ws/src/farm_sim_devices/farm_sim_devices/student_camera.py',
                     'sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/teacher_arm_alignment.py',
                     'sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py',
                     'sim/ros_ws/src/farm_sim_devices/farm_sim_devices/student_session.py'):
        raw = (ROOT/relative).read_bytes()
        selected[relative] = dict(sha256=hashlib.sha256(raw).hexdigest(), text=raw.decode())
    (base/'selected_sim_sources.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
    os.environ['ROS_LOG_DIR']=str(base/'ros_logs')
    os.environ['FASTRTPS_DEFAULT_PROFILES_FILE']=os.environ.get('FASTRTPS_DEFAULT_PROFILES_FILE',str(CONFIG/'fastdds_discovery.xml'))
    os.environ['HANDOFF_INPUT_TRACE']=str(base/'input_trace')
    os.environ['MOTION_GATE_TRACE']=str(base/'gate_timing.jsonl')
    os.environ['DOCKING_FRESHNESS_TRACE']=str(base/'freshness_trace.jsonl')
    processes=[];streams=[]
    def start(name,cmd):
        stream=(base/(name+'.log')).open('w');streams.append(stream)
        p=subprocess.Popen(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append((name,p));return p
    try:
        for robot in ('scout','harvest'):
            if robot=='scout' and scout_result is not None:continue
            cmd=['ros2','launch','farm_sim_runtime',robot+'.launch.py','project_root:='+str(ROOT),
                 'environment_config:='+str(runtime/(robot+'_runtime.yaml')),'tag_correction:=true']
            if robot=='harvest':
                cmd+=['handoff_config:='+str(runtime/'handoff.json')]
                if resume is not None:cmd+=['initial_spawn_config:='+str(runtime/'stations.json')]
            else:cmd+=['vision_python:=/home/ysy/venv/robot_venv/bin/python']
            start(robot,cmd)
        start('adapter',['ros2','run','farm_sim_devices','ros_adapter','--ros-args','-r','__ns:=/transport_01',
                         '-p','use_sim_time:=true','-p','config_file:='+str(runtime/'transport.json')])
        start('gate',['/usr/bin/python3','sim/tools/trace_motion_gate.py','--ros-args','-r','__ns:=/transport_01','-p','use_sim_time:=true'])
        start('precision',['/usr/bin/python3','sim/tools/trace_docking_freshness.py','--ros-args','--params-file',str(runtime/'precision.yaml'),
                           '-r','__ns:=/transport_01','-r','/cmd_vel:=motion/precision','-r','/odom:=odom',
                           '-r','/dock/cmd:=precision_legacy_disabled','-r','/dock/state:=precision_legacy_state'])
        start('transport',['ros2','launch','farm_sim_runtime','transport_navigation.launch.py','project_root:='+str(ROOT),
                           'environment_config:='+str(runtime/'transport_runtime.json'),'journal_dir:='+str(base/'transport_journal')])
        output=base/'sorting'
        start('sorter',['ros2','run','hcr_sorting','sorter_node','--ros-args','-p','modbus_host:=127.0.0.1','-p','modbus_peer:=127.0.0.1',
                        '-p','modbus_port:=1502','-p','receive_enabled:=true','-p','camera_state:='+str(output/'state.json'),
                        '-p','journal:='+str(output/'journal.sqlite3'),'-p','runtime_state:='+str(output/'ros_runtime.json')])
        start('post_sorter',['/usr/bin/python3','sim/tools/probe_sorter_cycle.py',str(base/'post_sorter'),'--wait-for-handoff'])
        start('isaac',['ros2','launch','farm_sim_runtime','isaac.launch.py','project_root:='+str(ROOT),'fleet_config:='+str(runtime/'fleet.json'),
                       'headless:=true','physics_device:=cpu','performance_log:='+str(base/'frame_performance.jsonl'),
                       'duration_s:=14400','isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python'])
        if overlap:
            start('camera_history',['/usr/bin/python3','sim/tools/capture_sorter_cycle.py',str(base)])
        probe_command=['/usr/bin/python3','sim/tools/probe_handoff_window.py',str(base)]
        if '--stop-after-docking' in sys.argv:probe_command.append('--stop-after-docking')
        if '--pickup-preflight' in sys.argv:
            goal_path=Path(sys.argv[sys.argv.index('--pickup-preflight')+1]).resolve()
            probe_command+=['--pickup-preflight',str(goal_path)]
            fixture=json.loads((base/'fixture.json').read_text())
            fixture.update(scope='pickup acceptance/cancel only; no survey/harvest/handoff/sorting',
                           fresh_scout=False,full_section=False,actual_harvest_tested=False)
            (base/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
            (base/'single_cycle.json').rename(base/'pickup_preflight.json')
        probe=start('probe',probe_command)
        deadline=time.monotonic()+28800
        while probe.poll() is None:
            failed=[(n,p.returncode) for n,p in processes if n!='probe' and p.poll() is not None
                    and not (n=='post_sorter' and p.returncode==0)]
            if failed:raise RuntimeError('시험 프로세스 종료: '+str(failed))
            if time.monotonic()>deadline:raise TimeoutError('한 사이클 시험 watchdog')
            time.sleep(1)
        if probe.returncode:raise RuntimeError('한 사이클 실패; result.json 확인, 자동 재시도 없음')
    finally:
        for _,p in reversed(processes):
            if p.poll() is None:os.killpg(p.pid,signal.SIGINT)
        deadline=time.monotonic()+45
        while any(p.poll() is None for _,p in processes) and time.monotonic()<deadline:time.sleep(.5)
        for _,p in processes:
            if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        (base/'process_exit.json').write_text(json.dumps({n:p.poll() for n,p in processes},indent=2)+'\n')
        for stream in streams:stream.close()

if __name__=='__main__':main()
