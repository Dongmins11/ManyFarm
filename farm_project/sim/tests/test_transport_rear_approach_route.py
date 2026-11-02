"""실제 농장 16섹션의 인계 접근 방향과 SEC02 재발 경로를 검사한다."""
import json
import math
from pathlib import Path
import sys
import pytest
import yaml
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/farm_navigation'))
from farm_navigation.route import RouteGraph

@pytest.mark.parametrize('section',[f'SEC{i:02}' for i in range(1,17)])
def test_station_pickup_enters_each_section_from_rear(section):
    cfg=ROOT/'sim/ros_ws/src/farm_sim_config/config'
    task=yaml.safe_load((cfg/'task.yaml').read_text())['sections'][section]
    profile=yaml.safe_load((cfg/'transport_runtime.yaml').read_text())
    g=RouteGraph(ROOT/profile['route_graph'])
    route=task['harvest_route'];yaw=route['heading_rad']
    x=g.nodes[route['entry_node_id']][0]
    goal=(x,8.414898712534665 if section=='SEC02' else (g.nodes[route['entry_node_id']][1]+g.nodes[route['exit_node_id']][1])/2)
    p=g.plan((2.,13.25),goal,.15,.02,goal_yaw=yaw)
    last=next((a,b) for a,b in reversed(list(zip(p.points,p.points[1:]))) if math.dist(a,b)>1e-6)
    assert abs(math.remainder(math.atan2(last[1][1]-last[0][1],last[1][0]-last[0][0])-yaw,2*math.pi))<.12
    if section=='SEC02':
        # 7차에서 수확로봇이 있던 Y9.39를 가로지르는 북→남 구간이 없어야 한다.
        assert not any(abs(a[0]-x)<.02 and abs(b[0]-x)<.02 and a[1]>9.39>b[1] for a,b in zip(p.points,p.points[1:]))
