"""기존 URDF/evidence FK로 03/04/07 촬영 키프레임 생성. 물리/ROS를 실행하지 않는다."""
import json, math, sys, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).parent
E=ROOT/'sim/runs/presentation_stills_20261031/delivery/evidence'
sys.path.insert(0,str(ROOT/'sim/assets/robotarm_student/manyfarm_robotarm/src/smartfarm_description/scripts'))
from model_geometry import fk
urdf=ET.parse(ROOT/'sim/assets/robots/harvest_robot/urdf/harvest_robot.urdf').getroot()
ref=json.loads((E/'harvest-grasp-closeup.json').read_text())
robot='/World/harvest_robot';link=robot+'/arm_2_gripper_link'
fruit='/World/Vegetation/Bed_02/Fruits/Pepper_0003_red'
T=np.eye(4);T[:3,:3]=Rotation.from_euler('z',math.pi/2).as_matrix();T[:3,3]=ref['placements'][robot]['xyz']
F=np.asarray(ref['inspected'][fruit]);q0=np.array([ref['joints']['arm_2_'+x] for x in ('shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll')])
names=['arm_2_'+x for x in ('shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll')]
names_urdf=[x.replace('arm_2_','arm_2/') for x in names]
jmap={j.get('name'):j for j in urdf.findall('joint')}
lo=np.array([float(jmap[n].find('limit').get('lower')) for n in names_urdf]);hi=np.array([float(jmap[n].find('limit').get('upper')) for n in names_urdf])
def wrist(q):return T@fk(urdf,dict(zip(names_urdf,q)))['arm_2/gripper_link']
np.testing.assert_allclose(wrist(q0),ref['inspected'][link],atol=5e-7)
relative=np.linalg.inv(wrist(q0))@F
R=wrist(q0)[:3,:3]
fits=[]
def solve(target,seed,regularization=.0003):
 def residual(q):
  w=wrist(q);p=(w@relative)[:3,3]
  return np.r_[(p-target)*10,.015*Rotation.from_matrix(R@w[:3,:3].T).as_rotvec(),regularization*(q-seed)]
 best=least_squares(residual,seed,bounds=(lo,hi),max_nfev=800,ftol=1e-11,gtol=1e-11,xtol=1e-11)
 err=np.linalg.norm((wrist(best.x)@relative)[:3,3]-target)
 if err>.001:raise ValueError(('unreachable',target,err))
 fits.append(dict(target=np.asarray(target).tolist(),q=best.x.tolist(),error_m=float(err)))
 return best.x

def joints(q,grip):return dict(zip(names,map(float,q)),arm_2_gripper=grip)
def placed(m):return {'matrix':np.asarray(m).tolist()}
def k(time,state):return {'time':time,'state':state}
def attach(rel=relative,whichlink=link):return [{'fruit':fruit,'link':whichlink,'matrix':np.asarray(rel).tolist()}]
def save(name,base,keys):
 req=dict(name=name,fps=30,duration_s=5,preview_only=True,base=base,keyframes=keys,evidence='GUI staged animation; positions based on existing project assets, not autonomous test result')
 (OUT/(name+'.json')).write_text(json.dumps(req,ensure_ascii=False,indent=2)+'\n')
 return req
p=F[:3,3];pre=solve(p+[-.065,0,0],q0);pull=solve(p+[-.055,0,.012],q0)
base={a:ref[a] for a in ('show','hide','placements','joints','eye','target','focal_mm','fill_intensity')}
base['hide']+=['/World/transport_robot','/World/HCRRobot','/World/HCRStation','/World/scout_robot_camera_fixed']
base['placements']=dict(base['placements'],**{fruit:placed(F)})
base['joints']=dict(base['joints'],**joints(pre,1.1));base['attach_fruits']=[]
base['inspect']=[fruit,link,robot+'/box_front_wall',robot+'/box_bottom_left']
base['eye']=[-6.0,7.0,1.25];base['target']=[-5.57,7.63,1.02];base['focal_mm']=43;base['fill_intensity']=1100
req3=save('03_grasp',base,[k(0,{}),k(1,{}),k(2.3,{'joints':joints(q0,1.1)}),k(2.8,{'joints':joints(q0,.65),'attach_fruits':attach()}),k(3.7,{'joints':joints(pull,.65)}),k(5,{})])
last=wrist(pull)@relative
way1=solve([-5.61,7.69,1.045],pull,.01)
way2=solve([-5.65,7.80,.94],way1,.01)
release=solve([-5.65,7.8228,.86],way2,.01)
releaseF=wrist(release)@relative
bottom=releaseF.copy();bottom[:3,3]=[-5.65,7.8228,.541]
base4=dict(base);base4['placements']={robot:ref['placements'][robot],fruit:placed(last)};base4['joints']=dict(ref['joints'],**joints(pull,.65));base4['attach_fruits']=attach()
base4['eye']=[-5.95,7.85,2.1];base4['target']=[-5.65,7.82,.65];base4['focal_mm']=36;base4['fill_intensity']=800
keys=[k(0,{}),k(1,{}),k(1.65,{'joints':joints(way1,.65)}),k(2.4,{'joints':joints(way2,.65)}),k(2.9,{'joints':joints(release,.65)}),k(3.15,{'joints':joints(release,1.1),'attach_fruits':[],'placements':{fruit:placed(releaseF)}})]
# 30fps에 맞춘 중력 낙하. 마지막 0.5초는 바구니 안착 화면이다.
fall_duration=math.sqrt(2*(releaseF[2,3]-bottom[2,3])/9.81)
for dt in np.linspace(fall_duration/4,fall_duration,4):
 m=releaseF.copy();m[2,3]=max(bottom[2,3],releaseF[2,3]-.5*9.81*dt*dt)
 keys.append(k(3.15+float(dt),{'placements':{fruit:placed(m)}}))
keys.append(k(5,{}));req4=save('04_deposit',base4,keys)
# 현재 선별 설정의 RED_CLEAR/RED 경유점. 기존 사진은 YELLOW였으므로 그대로 쓰지 않는다.
settings=json.loads((ROOT/'sim/runs/presentation_stills_20261031/delivery/settings/sorter.json').read_text())
sys.path.insert(0,str(ROOT/settings['source_workspace']/'src/sorting_station'))
from hcr_sim.model import teach,Arm
cfg=json.loads((ROOT/settings['source_workspace']/settings['source_config']).read_text());poses=teach(cfg);arm=Arm(cfg)
ST=np.eye(4);ST[:3,:3]=Rotation.from_euler('z',settings['station_yaw_rad']).as_matrix();ST[:3,3]=settings['station_pose_world_m']
def sw(x):return (ST@np.r_[x,1])[:3]
qclear=poses['RED_CLEAR']['q'];qred=poses['RED']['q']
def sj(q,jaw):return dict(zip([f'joint{i}' for i in range(1,7)],q),left_jaw=jaw,right_jaw=jaw)
clearfruit=F.copy();clearfruit[:3,3]=sw(poses['RED_CLEAR']['xyz']);sr=np.linalg.inv(ST@arm.fk(qclear))@clearfruit
redfruit=ST@arm.fk(qred)@sr
s=cfg['storage'];run=math.sqrt(s['ramp_length']**2-s['ramp_rise']**2);xlow=s['drop_x']-run;zlow=s['drop_z']-s['ramp_rise']
ramp=redfruit.copy();ramp[:3,3]=sw([s['drop_x']-.05,s['width']/4,s['drop_z']-.05*s['ramp_rise']/run+.041])
end=redfruit.copy();end[:3,3]=sw([xlow-s['bin_length']*.50,s['width']/4,zlow+.041])
base7=dict(show=['/World/HCRRobot','/World/HCRStation'],hide=[robot,'/World/StudentSensors/WristVisuals','/World/transport_robot','/World/scout_robot_camera_fixed'],joints=dict(ref['joints'],**sj(qclear,.004)),placements={fruit:placed(clearfruit)},attach_fruits=attach(sr,'/World/HCRRobot/tcp'),eye=sw([-.93,-.65,1.45]).tolist(),target=sw([-.39,.04,.62]).tolist(),focal_mm=34,fill_intensity=450,inspect=[fruit,'/World/HCRRobot/tcp','/World/HCRStation/RedBinFloor'])
base7['hide'] += ['/World/farm_framechanged/Frame_15_Post__1','/World/farm_framechanged/Cover_Side_soft_film__1','/World/farm_framechanged/Cover_Side_soft_film_1']
keys7=[k(0,{}),k(1,{}),k(2.3,{'joints':sj(qred,.004)}),k(2.55,{'joints':sj(qred,.01)}),k(2.6,{'attach_fruits':[],'placements':{fruit:placed(redfruit)}}),k(2.85,{'placements':{fruit:placed(ramp)}}),k(3.5,{'placements':{fruit:placed(end)}}),k(5,{})]
req7=save('07_sorting',base7,keys7)
(OUT/'arm_geometry_plan.json').write_text(json.dumps(dict(source_urdf='sim/assets/robots/harvest_robot/urdf/harvest_robot.urdf',offline_fk_evidence_atol_m=5e-7,harvest_fruit=fruit,harvest_grip_relative=relative.tolist(),harvest_ik_fits=fits,harvest_final_q=pull.tolist(),harvest_final_fruit_matrix=last.tolist(),harvest_release_matrix=releaseF.tolist(),sorter_red=poses['RED'],sorter_red_clear=poses['RED_CLEAR'],sorter_red_bin_world=end[:3,3].tolist(),limitations=['offline FK matches saved pose; no collision-free claim until GUI preview','fruit attachment and fall are explicitly staged animation','full matrix interpolation must preserve fruit scale']),ensure_ascii=False,indent=2)+'\n')
print('Wrote 03_grasp,04_deposit,07_sorting. Max offline positional IK error',max(x['error_m'] for x in fits))
# 샘플별 허용 관절 범위 검증. 링크 중심 검사는 메시 충돌 검증을 대체하지 않는다.
sys.path.insert(0,str(ROOT/'sim/tools'))
from presentation_video_frames import state_at
checks={}
for req in (req3,req4,req7):
 samples=[state_at(req,i/30) for i in range(150)]
 if req['name']=='07_sorting':
  ns=[f'joint{i}' for i in range(1,7)]; lower,upper=arm.lower,arm.upper
 else:ns=names;lower,upper=lo,hi
 qs=np.array([[s['joints'][n] for n in ns] for s in samples])
 good=bool(np.all(qs>=lower-1e-10) and np.all(qs<=upper+1e-10))
 assert good
 checks[req['name']]=dict(sample_count=150,joint_names=ns,all_within_limits=good,lower_rad=lower.tolist(),upper_rad=upper.tolist(),sampled_min_rad=qs.min(axis=0).tolist(),sampled_max_rad=qs.max(axis=0).tolist(),max_frame_joint_delta_rad=float(np.abs(np.diff(qs,axis=0)).max()))
plan=json.loads((OUT/'arm_geometry_plan.json').read_text())
plan['offline_joint_limit_validation']=checks
plan['offline_fk_saved_wrist_max_matrix_error']=float(np.max(np.abs(wrist(q0)-np.asarray(ref['inspected'][link]))))
plan['shot_03_end_04_start_equal']=dict(joints=all(state_at(req3,149/30)['joints'][n]==state_at(req4,0)['joints'][n] for n in names+['arm_2_gripper']),fruit_path=fruit,relative_matrix=True)
plan['collision_validation']='미실행: 메시 충돌/가림/바구니 안착은 GUI 프리뷰 검수 필요'
(OUT/'arm_geometry_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
