"""SEC 번호 없이 경로 점유/이탈과 현재 상태 신선도를 검사한다."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim/tools'))
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/farm_navigation'))
from cycle_departure_gate import choose_first,DepartureGate

@pytest.mark.parametrize('index',range(16))
def test_order_independent_of_section_and_world_offset(index):
    x=index*3.
    routes={'transport':[(x,0),(x,5),(x-3,5)],'harvest':[(x,1),(x,5),(x+3,5)]}
    assert choose_first((x,1),(x,0),routes,.8)=='harvest'
    routes['transport']=[(x,0),(x,-5),(x-3,-5)]
    assert choose_first((x,1),(x,0),routes,.8)=='transport'

def test_close_robots_can_depart_away_but_not_through_each_other():
    routes={'transport':[(0,0),(0,5)],'harvest':[(0,.72),(0,5),(3,5)]}
    assert choose_first((0,.72),(0,0),routes,.81)=='harvest'
    routes['harvest']=[(0,.72),(0,-5)]
    with pytest.raises(RuntimeError):choose_first((0,.72),(0,0),routes,.81)

def test_release_requires_leader_outside_followers_route():
    g=DepartureGate.__new__(DepartureGate);g.routes={'transport':[(0,0),(0,5)]};g.clearance=.8;g.record=lambda *a,**k:None
    g.pose=lambda r:(0,3,0)
    assert not g.cleared('harvest')
    g.pose=lambda r:(2,5,0)
    assert g.cleared('harvest')
    g.pose=lambda r:None
    assert not g.cleared('harvest')

def test_stale_status_never_releases():
    g=DepartureGate.__new__(DepartureGate);g.node=NS(get_clock=lambda:NS(now=lambda:NS(nanoseconds=3_000_000_000)))
    g.latest={'harvest':({'pose':{'frame_id':'map','position':{'x':2,'y':5},'yaw':0}},1_000_000_000)}
    assert g.pose('harvest') is None
