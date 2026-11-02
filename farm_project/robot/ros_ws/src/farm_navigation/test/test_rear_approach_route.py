"""인계 접근은 목표 뒤쪽에서 진입하며 반대편 통과/목표 초과를 허용하지 않는다."""
import json
import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from farm_navigation.route import RouteGraph


def graph(tmp_path, *, detour=True, split=False):
    nodes={0:(2,10),1:(0,10),2:(0,0),3:(2,0)}
    pairs=[(0,1),(1,2),(2,1)]
    if detour:pairs.extend([(0,3),(3,2)])
    if split:
        nodes[4]=(0,5);pairs.remove((1,2));pairs.remove((2,1))
        pairs.extend([(1,4),(4,2),(2,4),(4,1)])
    features=[dict(geometry=dict(type='Point',coordinates=xy),properties=dict(id=n)) for n,xy in nodes.items()]
    features.extend(dict(geometry=dict(type='LineString',coordinates=[nodes[a],nodes[b]]),
                         properties=dict(id=f'{a}-{b}',startid=a,endid=b)) for a,b in pairs)
    path=tmp_path/'graph.json';path.write_text(json.dumps(dict(type='FeatureCollection',features=features)))
    return RouteGraph(path)


@pytest.mark.parametrize('split',[False,True])
def test_approach_detours_to_rear_instead_of_crossing_target(tmp_path,split):
    g=graph(tmp_path,split=split)
    ordinary=g.plan((2,10),(0,8))
    assert (0.,10.) in ordinary.points
    approach=g.plan((2,10),(0,8),goal_yaw=math.pi/2)
    assert (0.,0.) in approach.points and (0.,10.) not in approach.points
    assert all(b[1]>=a[1] for a,b in zip(approach.points,approach.points[1:]) if a[0]==b[0]==0)


def test_no_rear_route_rejects_instead_of_using_front(tmp_path):
    with pytest.raises(ValueError):graph(tmp_path,detour=False).plan((2,10),(0,8),goal_yaw=math.pi/2)


def test_start_behind_target_can_use_partial_edge(tmp_path):
    assert graph(tmp_path).plan((0,3),(0,8),goal_yaw=math.pi/2).points==((0,3),(0,8))


def test_start_ahead_cannot_cross_target_and_loop_back(tmp_path):
    with pytest.raises(ValueError):graph(tmp_path).plan((0,9),(0,8),goal_yaw=math.pi/2)


def test_existing_blocked_edge_policy_preserved(tmp_path):
    with pytest.raises(ValueError):graph(tmp_path).plan((2,10),(0,8),goal_yaw=math.pi/2,blocked_edges=frozenset({'3-2'}))


def test_small_goal_yaw_error_still_blocks_opposite_corridor(tmp_path):
    p=graph(tmp_path,split=True).plan((2,10),(0,8),goal_yaw=math.pi/2+.05)
    assert (0.,0.) in p.points and (0.,10.) not in p.points
