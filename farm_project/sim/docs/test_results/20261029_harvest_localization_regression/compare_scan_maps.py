"""저장된 수확 scan을 실제 자세에 투영하여 지도 변경과 Y축 구분력을 비교한다. 제어 입력 없음."""
from pathlib import Path
import json, math
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
import yaml
root=Path(__file__).resolve().parents[4]
trial=root/'sim/runs/transport_full_resume_20261029_attempt02'
drive=[json.loads(x) for x in (root/'sim/runs/drive_diagnostics/89508b4e79c6490c97f41f7ff044dae2/harvest_01.jsonl').open()]
times=np.array([x['sim_time_s'] for x in drive]);poses=np.array([[x['T_world_base'][0][3],x['T_world_base'][1][3],math.atan2(x['T_world_base'][1][0],x['T_world_base'][0][0])] for x in drive]);poses[:,2]=np.unwrap(poses[:,2])
folder=root/'sim/ros_ws/src/farm_sim_config/maps';cfg=yaml.safe_load((folder/'hcr_farm_map.yaml').read_text());resolution=cfg['resolution'];origin=np.array(cfg['origin'][:2]);images={n:np.flipud(np.array(Image.open(folder/(n+'.png')).convert('L'))) for n in ('count_test_farm_map','hcr_farm_map')}
assert images['count_test_farm_map'].shape==images['hcr_farm_map'].shape
fields={n:distance_transform_edt(a>=round(255*(1-cfg['occupied_thresh'])))*resolution for n,a in images.items()}
yy,xx=np.where(images['count_test_farm_map']!=images['hcr_farm_map']);changes=dict(cells=len(xx),bounds_xy=[(origin+resolution*np.array([xx.min(),yy.min()])).tolist(),(origin+resolution*np.array([xx.max()+1,yy.max()+1])).tolist()])
def score(points,name):
 field=fields[name];ij=np.floor((points-origin)/resolution).astype(int);valid=(ij[:,0]>=0)&(ij[:,0]<field.shape[1])&(ij[:,1]>=0)&(ij[:,1]<field.shape[0]);d=np.full(len(ij),2.);d[valid]=np.minimum(field[ij[valid,1],ij[valid,0]],2.);return float(np.mean(np.exp(-d*d/(2*.2**2))))
rows=[]
for line in (trial/'events.jsonl').open():
 e=json.loads(line)
 if e['kind']!='harvest_scan':continue
 s=e['data'];t=s['header']['stamp']['sec']+s['header']['stamp']['nanosec']/1e9
 if not times[0]<=t<=times[-1]:continue
 pose=np.array([np.interp(t,times,poses[:,i]) for i in range(3)]);a=pose[2];ranges=np.array(s['ranges']);angles=s['angle_min']+np.arange(len(ranges))*s['angle_increment'];valid=np.isfinite(ranges)&(ranges>s['range_min'])&(ranges<s['range_max']);angles=angles[valid]+a+math.pi;ranges=ranges[valid]
 sensor=pose[:2]+np.array([math.cos(a),math.sin(a)])*(-.185)
 points=sensor+np.stack((np.cos(angles)*ranges,np.sin(angles)*ranges),axis=1)
 if not len(points):continue
 old=score(points,'count_test_farm_map');new=score(points,'hcr_farm_map')
 rows.append(dict(sim_s=t,old_score=old,new_score=new,y_minus5cm_score=score(points+[0,-.05],'hcr_farm_map'),y_plus5cm_score=score(points+[0,.05],'hcr_farm_map')))
result=dict(method='全 valid beams mean exp(-map_distance^2/(2*0.2^2)); not AMCL particle weight'.replace('全','전체'),map_changes=changes,scan_count=len(rows),max_old_new_score_difference=max(abs(x['old_score']-x['new_score']) for x in rows),samples=[min(rows,key=lambda x:abs(x['sim_s']-t)) for t in (9.35,216.45,302.25,317.75,323.95,328.05)],rows=rows)
Path(__file__).with_name('scan_map_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2))
