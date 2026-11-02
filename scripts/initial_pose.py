"""선택한 로봇 그래프의 노드·방향을 초기위치로 발행. 로봇 이동 명령이 아니다."""
import argparse,json,math,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('role',choices=['scout','transport']);p.add_argument('node',type=int);p.add_argument('toward',type=int);p.add_argument('--print-only',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1]
g=json.loads((root/f'farm_project/robot/config/maps/{a.role}_real/graph.geojson').read_text())
n={f['properties']['id']:f['geometry']['coordinates'] for f in g['features'] if f['geometry']['type']=='Point'}
x,y=n[a.node][:2];tx,ty=n[a.toward][:2]
if a.node==a.toward:raise SystemExit('위치와 방향 기준 노드는 달라야 합니다.')
yaw=math.atan2(ty-y,tx-x);cov=[0.]*36;cov[0]=cov[7]=.04;cov[35]=.0685
msg={'header':{'frame_id':'map'},'pose':{'pose':{'position':{'x':x,'y':y,'z':0.},'orientation':{'x':0.,'y':0.,'z':math.sin(yaw/2),'w':math.cos(yaw/2)}},'covariance':cov}}
if a.print_only:print(json.dumps(msg,ensure_ascii=False));raise SystemExit
subprocess.run(['ros2','topic','pub','--once',f'/{a.role}_01/initialpose','geometry_msgs/msg/PoseWithCovarianceStamped',json.dumps(msg)],check=True)
