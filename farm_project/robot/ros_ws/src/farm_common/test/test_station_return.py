"""공통 복귀의 경로 선택과 최종 방향/실패/취소 계약. ROS 입출력만 대역이다."""
import json
import math
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch

import numpy as np
import pytest
from builtin_interfaces.msg import Time

from farm_common.action_handoff import ActionHandoff, ActionInterrupted
from farm_common.station_return import Station, StationReturn, plan_station_return
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from farm_navigation.path_builder import build_path
from farm_navigation.route import RouteGraph


def line_graph(tmp_path, bidirectional=True):
    features = [dict(geometry=dict(type='Point', coordinates=xy), properties=dict(id=i))
                for i, xy in enumerate(((0., 0.), (0., 4.)))]
    edges = [(0, 1), (1, 0)] if bidirectional else [(1, 0)]
    for i, (a, b) in enumerate(edges):
        features.append(dict(geometry=dict(type='LineString', coordinates=[[0., 4.*a], [0., 4.*b]]),
                             properties=dict(id=str(i), startid=a, endid=b)))
    file = tmp_path/'graph.json'
    file.write_text(json.dumps(dict(type='FeatureCollection', features=features)))
    return RouteGraph(file)


@pytest.mark.parametrize('yaw,reverse', [(math.pi/2, False), (-math.pi/2, True)])
def test_equal_length_uses_current_heading(tmp_path, yaw, reverse):
    plan, selected, audit = plan_station_return(line_graph(tmp_path),
        Station('station', (0., 4.), -math.pi/2), (0., 0.), yaw, NavigationSettings())
    assert selected is reverse
    assert plan.points[-1] == (0., 4.)
    assert audit['forward']['distance_m'] == audit['reverse']['distance_m'] == 4.
    path = build_path(plan, -math.pi/2, Time(), reverse=selected)
    q = path.poses[-1].pose.orientation
    assert math.isclose(2*math.atan2(q.z, q.w), -math.pi/2)
    if not reverse:
        # 전진 경로는 북향, 마지막 pose는 남향: 위치 도착 뒤180도 정렬을 요청한다.
        first = path.poses[0].pose.orientation
        assert math.isclose(2*math.atan2(first.z, first.w), math.pi/2)


@pytest.mark.parametrize('forward_distance,reverse_distance,reverse', [(6., 4., True), (3., 4., False)])
def test_shorter_route_has_priority(forward_distance, reverse_distance, reverse):
    def plan(start, goal, *limits):
        distance = reverse_distance if start == (0., 4.) else forward_distance
        return RoutePlan('test', 'revision', 'map', (start, goal), ('edge',), distance)
    _, selected, _ = plan_station_return(S(plan=plan), Station('station', (0., 4.), -math.pi/2),
                                         (0., 0.), -math.pi/2, NavigationSettings())
    assert selected is reverse


def test_unavailable_or_incompatible_route_never_falls_back_to_straight_line(tmp_path):
    graph = line_graph(tmp_path, bidirectional=False)
    with pytest.raises(ValueError, match='실행 가능한'):
        plan_station_return(graph, Station('station', (0., 4.), -math.pi/2),
                            (0., 0.), math.pi/2, NavigationSettings())
    plan, reverse, _ = plan_station_return(graph, Station('station', (0., 4.), -math.pi/2),
                                           (0., 0.), -math.pi/2, NavigationSettings())
    assert reverse and plan.distance_m == 4.


def test_at_station_wrong_heading_uses_forward_rotation(tmp_path):
    _, reverse, _ = plan_station_return(line_graph(tmp_path), Station('station', (0., 4.), -math.pi/2),
                                        (0., 4.), math.pi/2, NavigationSettings())
    assert not reverse  # 후진 제어기의180도 거절 조건으로 보내지 않는다.


def make_return(tmp_path, yaw, mode):
    server = StationReturn.__new__(StationReturn)
    server._settings = NavigationSettings()
    server._station = Station('station', (0., 4.), -math.pi/2)
    server._graph = line_graph(tmp_path)
    server._profile = dict(mode=mode)
    server._node = Mock()
    server._handoff = ActionHandoff()
    server._unavailable = lambda: False
    server._block = Mock()
    server._prepare = None
    server._tag_control = None
    server._tag_active = False
    server._navigator, server._forward_navigator = Mock(), Mock()
    transform = np.eye(4)
    transform[:2, :2] = [[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]]
    server._poses = S(current=lambda check: transform)
    handle = Mock()
    handle.request = S(robot_id='scout_01', task_id='task', station_id='station')
    handle.is_cancel_requested = False
    assert server._handoff.reserve('return', 'task')
    return server, handle


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('mode', ['sim', 'real'])
def test_selected_controller_finishes_heading_and_preserves_result_contract(tmp_path, reverse, mode):
    server, handle = make_return(tmp_path, -math.pi/2 if reverse else math.pi/2, mode)
    with patch('rclpy.ok', return_value=True):
        result = server.execute(handle)
    chosen = server._navigator if reverse else server._forward_navigator
    other = server._forward_navigator if reverse else server._navigator
    chosen.preflight_navigation.assert_called_once()
    args, kwargs = chosen.navigate.call_args
    assert args == ((0., 4.), -math.pi/2) and kwargs['reverse'] is reverse
    chosen.cancel_nav.assert_called_once()
    other.navigate.assert_not_called()
    assert result.result_code == 'SUCCESS' and result.docked == (mode == 'sim')
    assert not server._handoff.busy


@pytest.mark.parametrize('fault', ['navigation', 'cancellation', 'stop_unconfirmed'])
def test_failure_cancel_and_stop_confirmation_cannot_be_success(tmp_path, fault):
    server, handle = make_return(tmp_path, math.pi/2, 'sim')
    if fault == 'navigation':server._forward_navigator.navigate.side_effect = RuntimeError('collision')
    if fault == 'cancellation':
        def cancel_during_navigation(*args, **kwargs):
            handle.is_cancel_requested = True
            raise ActionInterrupted('cancel')
        server._forward_navigator.navigate.side_effect = cancel_during_navigation
    if fault == 'stop_unconfirmed':server._forward_navigator.cancel_nav.side_effect = RuntimeError('stop')
    with patch('rclpy.ok', return_value=True):
        result = server.execute(handle)
    assert result.result_code != 'SUCCESS' and not result.docked
    handle.succeed.assert_not_called()
    server._forward_navigator.cancel_nav.assert_called_once()
    if fault == 'cancellation':handle.canceled.assert_called_once()
    if fault == 'stop_unconfirmed':
        assert result.error_code == 'CANCEL_UNCONFIRMED'
        server._block.assert_called_once()
    assert not server._handoff.busy


def test_controller_wiring_preserves_limits_and_closes_both_clients(tmp_path):
    graph = line_graph(tmp_path)
    settings = NavigationSettings(arrival_tolerance_m=.04, heading_tolerance_rad=.05)
    with patch('farm_common.station_return.RouteGraph', return_value=graph), \
         patch('farm_common.station_return.load_station', return_value=Station('s', (0., 4.), -math.pi/2)), \
         patch('farm_common.station_return.Nav2Client') as client, \
         patch('farm_common.station_return.Navigator'), \
         patch('farm_common.station_return.ActionServer'):
        client.side_effect = [Mock(), Mock()]
        server = StationReturn(Mock(), root=tmp_path, profile={'route_graph': 'graph'}, settings=settings,
            poses=Mock(), motion=Mock(), callbacks=Mock(), handoff=Mock(),
            unavailable=lambda: False, block=Mock())
        selected = [call.args[1] for call in client.call_args_list]
        assert [s.controller_id for s in selected] == ['StationReverse', 'RPP']
        assert all(s.arrival_tolerance_m == .04 and s.heading_tolerance_rad == .05 for s in selected)
        server.close()
        server._client.close.assert_called_once()
        server._forward_client.close.assert_called_once()
