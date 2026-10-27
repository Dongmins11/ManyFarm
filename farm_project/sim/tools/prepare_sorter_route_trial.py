"""설정의 북쪽 통로 시험 배치에서 인계·선별장 연속 이동을 준비한다. 원본 USD 불변."""
import json
import math
import subprocess
import sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2];CFG=ROOT/'sim/ros_ws/src/farm_sim_config/config'

def main() -> None:
    out=Path(sys.argv[1]).resolve()
    if not out.is_relative_to(ROOT/'sim/runs') or out.exists():raise ValueError('sim/runs 아래 새 결과 경로 필요')
    subprocess.run([sys.executable,str(ROOT/'sim/tools/prepare_docking_alignment_trial.py'),str(out)],check=True)
    trial=json.loads((CFG/'docking/sorter_route_trial.json').read_text())
    graph=json.loads((CFG.parent/'maps/transport_graph.geojson').read_text())
    nodes={f['properties']['id']:f['geometry']['coordinates'] for f in graph['features'] if f['geometry']['type']=='Point'}
    xy=[a+b for a,b in zip(nodes[trial['anchor_node_id']],trial['harvest_offset_map_m'])]
    transport_xy=[a+b for a,b in zip(xy,trial['transport_offset_from_harvest_map_m'])]
    phase=out/'41'
    stations=json.loads((phase/'stations.json').read_text())
    stations['stations']['harvest_01'].update(xy_m=xy,yaw_rad=trial['harvest_yaw_rad'])
    stations['stations']['transport_01'].update(xy_m=transport_xy,yaw_rad=trial['transport_yaw_rad'])
    (phase/'stations.json').write_text(json.dumps(stations,ensure_ascii=False,indent=2)+'\n')
    nav=yaml.safe_load((CFG/'nav2_transport.yaml').read_text())
    nav['amcl']['ros__parameters']['initial_pose']=dict(x=transport_xy[0],y=transport_xy[1],z=0.,yaw=trial['transport_yaw_rad'])
    (phase/'nav2_transport.yaml').write_text(yaml.safe_dump(nav,sort_keys=False))
    profile=yaml.safe_load((CFG/'transport_runtime.yaml').read_text());profile['nav_params']=str((phase/'nav2_transport.yaml').relative_to(ROOT))
    (phase/'transport_runtime.yaml').write_text(yaml.safe_dump(profile,sort_keys=False))
    (phase/'trial_geometry.json').write_text(json.dumps(dict(spec=trial,harvest_xy=xy,transport_xy=transport_xy),indent=2)+'\n')
    print(out)

if __name__=='__main__':main()
