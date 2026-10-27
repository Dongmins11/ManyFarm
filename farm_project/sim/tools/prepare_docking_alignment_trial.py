"""원본 커밋의 수치를 보존한 정밀도킹 시험 설정을 sim/runs에 생성한다."""
from pathlib import Path
import json,yaml,copy,subprocess,hashlib,math,sys
r=Path(__file__).resolve().parents[2];out=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else r/'sim/runs/docking_alignment_20261027'; cfg=r/'sim/ros_ws/src/farm_sim_config/config'
out.mkdir(parents=True,exist_ok=True)
ref='9686aca909cb52191862ee3500c62fadf7a8ed38'
def source(path):
 raw=subprocess.check_output(['git','show',ref+':farm_project/'+path],cwd=r); (out/Path(path).name).write_bytes(raw);return yaml.safe_load(raw)
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
profiles=source('robot/config/docking/waffle_profiles.yaml');targets=source('robot/config/docking/waffle_marker_targets.yaml');nav=source('robot/config/robots/waffle/transport_nav2.yaml')
selected={k:profiles['profiles'][k] for k in ['harvest_approach_42','harvest_dock_41','harvest_clear']}
changes=[]
def replace(value,path=''):
 if isinstance(value,dict):return {k:replace(v,path+'/'+k) for k,v in value.items()}
 if isinstance(value,list):return [replace(v,path+f'/{i}') for i,v in enumerate(value)]
 if value in ['base_footprint','base_link','base_scan','odom'] if isinstance(value,str) else False:
  changes.append(dict(path=path,before=value,after='transport_01/'+value));return 'transport_01/'+value
 return value
selected=replace(selected);targets=replace(targets)
for p in selected.values():
 changes.append(dict(path='collision_guard/nav2_file',before=p['collision_guard']['nav2_file'],after='nav2_frame.yaml'))
 p['collision_guard']['nav2_file']='nav2_frame.yaml'
nav=replace(nav)
(out/'profiles.yaml').write_text(yaml.safe_dump(dict(profiles=selected),sort_keys=False))
(out/'targets.yaml').write_text(yaml.safe_dump(targets,sort_keys=False))
(out/'nav2_frame.yaml').write_text(yaml.safe_dump(nav,sort_keys=False))
(out/'sites.yaml').write_text('sites: {}\n')
write(out/'source_adaptations.json',dict(commit=ref,changes=changes,numeric_changes=[]))
for phase,pos,yaw in [('41',[0,-1.105],math.pi/2),('42',[-1.04,-.3004382180792312],0),('41_surface',[0,-1.105],math.pi/2)]:
 d=out/phase;d.mkdir(exist_ok=True)
 h=json.loads((cfg/'harvest.json').read_text()); t=json.loads((cfg/'transport.json').read_text())
 h['runtime']['harvest_arm']['enabled']=False
 h['runtime']['harvest_activity']['enabled']=False
 h['camera']['enabled']=False
 if 'tag_camera'in h:h['tag_camera']['enabled']=False
 h['runtime'].pop('physics_profile',None)
 for key in ['apriltag_map']:h.pop(key,None)
 t['camera']['ros_info_reliable']=True
 for name,v,frames in [('harvest',h,['harvest_lid_fixed','box_front_wall','box_left_wall','box_rear_wall','box_right_wall']),('transport',t,['cargo_box','base_scan'])]:
  v['runtime'].update(diagnostic_frames=frames,diagnostic_period_s=.05)
  write(d/(name+'.json'),v)
 stations=json.loads((cfg/'station_spawn.json').read_text());stations['stations']['harvest_01'].update(xy_m=[0,0],yaw_rad=math.pi);stations['stations']['transport_01'].update(xy_m=pos,yaw_rad=yaw)
 write(d/'stations.json',stations)
 write(d/'fleet.json',dict(schema_version=1,station_config=str((d/'stations.json').relative_to(r)),device_configs=[str((d/(n+'.json')).relative_to(r)) for n in ['harvest','transport']],clock=dict(command_port=17690,telemetry_port=17691),docking_markers='sim/assets/docking_markers/layout.provisional.json',basket_alignment=dict(evaluation_config='sim/ros_ws/src/farm_sim_config/config/docking/basket_alignment_evaluation.json',robots=dict(harvest='harvest_01',transport='transport_01'))))
params=dict(use_sim_time=True,camera_frame_id='transport_01/camera_optical_frame',profiles_file=str(out/'profiles.yaml'),sites_file=str(out/'sites.yaml'),pose_control_file=str(out/'targets.yaml'),pose_control_target='harvest_42_wait_pose',log_dir=str(out/'precision'),skip_staging=True,cam_auto=False,autostart=False,dry_run=False,camera_input_backend='ros',image_topic='camera/image_raw',info_topic='camera/camera_info',lidar_topic='scan',marker_pose_mode='tf_observe',marker_base_frame='transport_01/base_footprint',odom_frame='transport_01/odom',pose_output_enabled=True)
(out/'params.yaml').write_text(yaml.safe_dump({'/**':{'ros__parameters':params}},sort_keys=False))
print(out)

# 운영 배치표를 보존하고 시험 복사본만 라이다 면에 맞춘다.
d=out/'41_surface'
l=json.loads((r/'sim/assets/docking_markers/layout.provisional.json').read_text())
for m in l['markers']:
 if m['id']==41:m['center_m'][1]=-.251;m['basis']='DIAGNOSTIC_VARIANT: lidar body surface -0.25; explicit -0.251 override'
write(d/'layout.json',l)
f=json.loads((d/'fleet.json').read_text());f['docking_markers']=str((d/'layout.json').relative_to(r));write(d/'fleet.json',f)
