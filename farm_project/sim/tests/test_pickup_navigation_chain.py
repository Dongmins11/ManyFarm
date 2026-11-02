"""인계 → 제어권 래퍼 → 실제 운송 어댑터까지 후방 접근 옵션을 전달한다."""
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as S
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2]
for package in ('farm_docking','farm_navigation','transport_robot'):
    sys.path.insert(0,str(ROOT/'robot/ros_ws/src'/package))
from farm_docking.clients import ExclusiveNavigator
from transport_robot.harvest_approach import HarvestApproach
from transport_robot.navigation_adapter import TransportNavigator
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.route import RouteGraph

@pytest.mark.parametrize('reject',[False,True])
def test_real_pickup_wrapper_adapter_chain(reject):
    calls=[]; pose=np.eye(4);pose[0,3]=2.;pose[1,3]=13.25
    node=S(get_clock=lambda:S(now=lambda:S(to_msg=lambda:None)))
    # 실제 navigate 진입 후 실제 plan 결과를 검사하고 ROS 실행 직전에 종료한다.
    class Planned(Exception):pass
    navigator=TransportNavigator(node,NavigationSettings(mode='follow_path'),S(has_goal=False),
        S(current=lambda check:pose),S(),lambda:None,
        RouteGraph(ROOT/'sim/ros_ws/src/farm_sim_config/maps/transport_graph.geojson'))
    actual_plan=navigator.plan
    def plan(xy,**options):
        assert options==dict(approach_yaw=np.pi/2)
        p=actual_plan(xy,**options)
        assert (-4.045,0.) in p.points
        calls.append('planned')
        if reject:raise ValueError('no safe route')
        raise Planned()
    navigator.plan=plan
    lease=S(acquire=lambda:calls.append('acquire'),release=lambda:calls.append('release'))
    approach=HarvestApproach.__new__(HarvestApproach)
    approach.node=S(navigator=ExclusiveNavigator(navigator,lease),get_logger=lambda:S(info=lambda message:None))
    approach.lock=threading.Lock();approach.ready=None;approach.armed=False
    approach.enable=lambda value:calls.append(('camera',value))
    with pytest.raises(ValueError if reject else Planned):
        approach.move(S(xy=(-4.045,8.3),yaw=np.pi/2))
    assert calls==[('camera',True),'acquire','planned','release',('camera',False)]


def test_existing_navigation_without_options_still_works():
    events=[]
    wrapped=ExclusiveNavigator(S(navigate=lambda xy,yaw:events.append((xy,yaw)) or 'ok'),
        S(acquire=lambda:events.append('acquire'),release=lambda:events.append('release')))
    assert wrapped.navigate((1,2),0)=='ok'
    assert events==['acquire',((1,2),0),'release']
