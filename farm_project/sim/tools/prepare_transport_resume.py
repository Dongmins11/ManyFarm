"""완료된 수확 결과와 마지막 장면 좌표로 운송 재개용 초기 배치를 만든다."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import yaml
from prepare_harvest_handoff import ROOT, CONFIG


def prepare_resume(base: Path, source: Path, snapshot: Path) -> None:
    runtime=base/'runtime'
    result=json.loads((source/'partial_result.json').read_text())
    saved=json.loads(snapshot.read_text())
    results=result['harvest_results']
    if len(results)!=result['window_count'] or not all(r['status']==4 and r['result']['result_code']=='SUCCESS' for r in results):
        raise ValueError('모든 수확 윈도우의 성공 결과 필요')
    proof=None
    for line in (source/'events.jsonl').open():
        if '"kind": "basket_alignment"' in line:
            event=json.loads(line)['data']
            if event['session']==saved['scene_session']:proof=event['proof']
    if not saved['complete'] or not proof or abs(proof['sim_time_s']-saved['stamp_ns']/1e9)>2:
        raise ValueError('같은 세션의 마지막 장면·바구니 위치 기록 필요')
    corners=np.asarray(proof['harvest_corners_world']);origin=corners.mean(axis=0)
    u=corners[1]-corners[0];v=corners[3]-corners[0];sizes=np.array([np.linalg.norm(u),np.linalg.norm(v)])
    u/=sizes[0];v/=sizes[1];w=np.cross(u,v)
    fruits=[]
    for fruit in saved['fruits']:
        delta=np.asarray(fruit['center_world_m'])-origin
        if (abs(delta@u)<sizes[0]/2 and abs(delta@v)<sizes[1]/2 and 0<delta@w<.25
                and fruit['class_name'] in ('red','yellow')):fruits.append(fruit)
    if not fruits:raise ValueError('스냅샷 바구니 안에 실제 과실 없음')
    manifest=dict(source=str(source),source_session=saved['scene_session'],
        snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        source_result_sha256=hashlib.sha256((source/'partial_result.json').read_bytes()).hexdigest(),
        harvested_count=sum(r['result']['harvested_count'] for r in results),
        physical_basket_count=len(fruits),fruits=fruits,
        basket_corners_world=proof['harvest_corners_world'],
        restore_mode='saved bbox centers; original asset orientations; zero velocities; not full physics checkpoint',
        T_world_base=saved['T_world_base'])
    (base/'resume_scene.json').write_bytes(snapshot.read_bytes())
    (base/'resume_harvest_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (base/'resume_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    # 정답 좌표는 초기 배치에만 사용한다. 실행 중 위치추정 입력으로 보내지 않는다.
    stations=json.loads((runtime/'stations.json').read_text())
    T=np.asarray(stations['T_map_world'])@np.asarray(saved['T_world_base'])
    xy=T[:2,3].tolist();yaw=math.atan2(T[1,0],T[0,0])
    # 새 노드에는 과거 window 도착 문맥이 없다. 기존 도착 전용 액션으로
    # 다시 확인할 수 있도록 마지막 목표 10cm 전에서 시작하는 시험 배치다.
    last_task=json.loads((base/'reused_scout_result.json').read_text())['scout_result']['result']['harvest_tasks'][-1]
    goal=last_task['goal_pose'];heading=goal['yaw']
    start=np.array([goal['position']['x']-.1*math.cos(heading),goal['position']['y']-.1*math.sin(heading)])
    delta_map=np.r_[start-np.asarray(xy),0.]
    delta_world=np.asarray(stations['T_map_world'])[:3,:3].T@delta_map
    for fruit in manifest['fruits']:
        fruit['center_world_m']=(np.asarray(fruit['center_world_m'])+delta_world).tolist()
    manifest['basket_corners_world']=(corners+delta_world).tolist()
    restored_base=np.asarray(saved['T_world_base']).copy();restored_base[:3,3]+=delta_world
    manifest.update(T_world_base=restored_base.tolist(),arrival_revalidation_task=last_task,
        initial_shift_world_m=delta_world.tolist(),
        restore_mode='saved cargo translated with harvest robot to 0.10m before last window; fresh arrival-only validation required')
    (base/'resume_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    xy=start.tolist()
    stations['stations']['harvest_01'].update(xy_m=xy,yaw_rad=yaw)
    (runtime/'stations.json').write_text(json.dumps(stations,indent=2))
    nav=yaml.safe_load((CONFIG/'nav2_harvest.yaml').read_text())
    nav['bindings']['initial_pose']=dict(x=xy[0],y=xy[1],z=0.,yaw=yaw)
    (runtime/'nav2_harvest.yaml').write_text(yaml.safe_dump(nav,sort_keys=False))
    profile=yaml.safe_load((runtime/'harvest_runtime.yaml').read_text())
    profile['nav_params']=str((runtime/'nav2_harvest.yaml').relative_to(ROOT))
    (runtime/'harvest_runtime.yaml').write_text(yaml.safe_dump(profile,sort_keys=False))
    task_config=json.loads((runtime/'harvest_task.json').read_text())
    task_config['completion_policy']='ARRIVAL_ONLY_NO_HARVEST'
    (runtime/'harvest_task.json').write_text(json.dumps(task_config,ensure_ascii=False,indent=2)+'\n')
    sorter=json.loads((runtime/'sorter.json').read_text())
    sorter['harvest_resume_manifest']=str((base/'resume_manifest.json').relative_to(ROOT))
    (runtime/'sorter.json').write_text(json.dumps(sorter,indent=2))
    (runtime/'pickup_goal.json').write_bytes((source/'runtime/pickup_goal.json').read_bytes())
    for path in (base/'fixture.json',base/'post_sorter/fixture.json'):
        f=json.loads(path.read_text());f.update(scope='resume after completed harvest; transport pickup/handoff/sort/returns',
            resumed_harvest_source=str(source),actual_harvest_tested=False,historical_harvest_results_reused=True,
            resumed_physical_fruit_count=len(fruits),resumed_harvested_count=manifest['harvested_count'],
            restore_mode=manifest['restore_mode'],robot_initial_stations=stations['stations'])
        f.update(arrival_revalidation_required=True,resume_completion_policy='ARRIVAL_ONLY_NO_HARVEST')
        path.write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n')
