"""오프라인 진단: run_dir drive_jsonl 인자. 정답은 평가에만 사용한다.
라이다 평면 투영/전체 빔 거리장 점수이며 AMCL 실제 입자 가중치의 재구현이 아니다.
"""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
base=Path(sys.argv[1]);drive=Path(sys.argv[2]);root=Path(__file__).resolve().parents[4]
rows=[json.loads(l) for l in (base/'events.jsonl').open()];raw=[json.loads(l) for l in drive.open()]
times=np.array([r['sim_time_s'] for r in raw]);poses=np.array([[r['T_world_base'][0][3],r['T_world_base'][1][3],math.atan2(r['T_world_base'][1][0],r['T_world_base'][0][0])] for r in raw]);poses[:,2]=np.unwrap(poses[:,2])
def stamp(d):s=d['header']['stamp'];return s['sec']+s['nanosec']/1e9
def pose(d):p=d['position'];q=d['orientation'];return np.array([p['x'],p['y'],2*math.atan2(q['z'],q['w'])])
def truth(t):return np.array([np.interp(t,times,poses[:,i]) for i in range(3)])
scan=[r['data'] for r in rows if r['kind']=='harvest_scan'];st=np.array([stamp(d) for d in scan])
static={r['data']['child_frame_id']:r['data']['transform'] for r in rows if r['kind']=='harvest_tf_static'}
offset=np.zeros(2);laser_yaw=0.
for child in ('harvest_01/base_link','harvest_01/base_scan'):
 tr=static[child];v=tr['translation'];q=tr['rotation'];c,s=math.cos(laser_yaw),math.sin(laser_yaw)
 offset+=np.array([c*v['x']-s*v['y'],s*v['x']+c*v['y']]);laser_yaw+=2*math.atan2(q['z'],q['w'])
import yaml
mapp=root/'sim/ros_ws/src/farm_sim_config/maps/count_test_farm_map.yaml';cfg=yaml.safe_load(mapp.read_text());img=np.array(Image.open(mapp.parent/cfg['image']).convert('L'));dist=distance_transform_edt(~(img<(1-cfg['occupied_thresh'])*255))*cfg['resolution']
print('map',img.shape,np.unique(img,return_counts=True))
def scores(sc,p):
 rr=np.array(sc['ranges']);aa=sc['angle_min']+np.arange(len(rr))*sc['angle_increment'];valid=np.isfinite(rr)&(rr>=sc['range_min'])&(rr<sc['range_max']);rr=rr[valid];aa=aa[valid]+p[2]+laser_yaw
 xx=p[0]+offset[0]*math.cos(p[2])-offset[1]*math.sin(p[2])+rr*np.cos(aa);yy=p[1]+offset[0]*math.sin(p[2])+offset[1]*math.cos(p[2])+rr*np.sin(aa)
 ix=np.floor((xx-cfg['origin'][0])/cfg['resolution']).astype(int);iy=img.shape[0]-1-np.floor((yy-cfg['origin'][1])/cfg['resolution']).astype(int);ok=(ix>=0)&(ix<img.shape[1])&(iy>=0)&(iy<img.shape[0]);dd=np.ones(len(rr))*2;dd[ok]=dist[iy[ok],ix[ok]]
 return float(dd.mean()),float(np.mean(dd<.075)),float(np.mean(np.exp(-dd**2/(2*.2**2))))
result=[]
for r in rows:
 if r['kind']!='harvest_amcl':continue
 d=r['data'];t=stamp(d);p=pose(d['pose']['pose']);tr=truth(t);s=scan[np.argmin(abs(st-t))];e=p-tr;e[2]=math.atan2(math.sin(e[2]),math.cos(e[2]));cov=d['pose']['covariance']
 entry=dict(t=t,truth=tr.tolist(),amcl=p.tolist(),error=e.tolist(),sd_xy=[math.sqrt(max(0,cov[i])) for i in (0,7)],truth_fit=scores(s,tr),amcl_fit=scores(s,p))
 result.append(entry)
 print('t %.2f err_cm %+.1f %+.1f yaw %+.1f sd_cm %.1f %.1f fit truth/amcl %.3f %.3f'% (t,e[0]*100,e[1]*100,e[2]*180/math.pi,*[v*100 for v in entry['sd_xy']],entry['truth_fit'][2],entry['amcl_fit'][2]))
for t in [20,45,65,100,145]:
 i=np.argmin(abs(st-t));tr=truth(st[i]);s=scan[i];print('yfit',st[i],[(round(float(dy),2),round(scores(s,tr+np.array([0,dy,0]))[2],4)) for dy in np.arange(-.15,.151,.025)])
(base/'amcl_analysis.json').write_text(json.dumps(dict(samples=result,description='평면 투영 전체 빔 평균 exp(-d²/(2 sigma²)); 실제 AMCL 점수 아님',drive_file=str(drive),map_file=str(mapp),laser_offset_xy=offset.tolist(),laser_yaw=laser_yaw),indent=2)+'\n')
