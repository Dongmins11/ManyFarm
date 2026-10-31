"""실물 상태 컴포넌트를 시뮬 경로·완료 계약에 연결하는 회귀 검사."""
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
from harvest_robot.station_return_components import ComponentStationReturn
from harvest_robot.station_return_mission import StationReturnMission
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.configuration import load_environment, load_nav2_parameters

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/farm_common/test'))
from test_station_return import make_return


def component(tmp_path, reverse=False):
    base,handle=make_return(tmp_path,-math.pi/2 if reverse else math.pi/2,'sim')
    server=ComponentStationReturn.__new__(ComponentStationReturn)
    server.__dict__.update(base.__dict__)
    server._mission=server._controller=None
    server._node.section_resolution={'corridors':{}}
    server._node.get_clock.return_value=NS(ros_time_is_active=False)
    return server,handle


@pytest.mark.parametrize('reverse',[False,True])
def test_selected_route_success_cleans_up_then_reports_docked(tmp_path,reverse):
    server,handle=component(tmp_path,reverse)
    with patch('rclpy.ok',return_value=True):result=server.execute(handle)
    chosen=server._navigator if reverse else server._forward_navigator
    assert chosen.navigate.call_args.kwargs['reverse'] is reverse
    assert chosen.navigate.call_args.args==((0.,4.),-math.pi/2)
    chosen.preflight_navigation.assert_called_once()
    chosen.cancel_nav.assert_called_once()
    assert result.result_code=='SUCCESS' and result.docked
    assert server._mission is None and not server._handoff.busy


@pytest.mark.parametrize('fault',['prepare','navigate','cleanup','cancel'])
def test_failure_cannot_report_success_and_ownership_released(tmp_path,fault):
    server,handle=component(tmp_path)
    if fault=='prepare':server._prepare=Mock(side_effect=RuntimeError('prepare'))
    if fault=='navigate':server._forward_navigator.navigate.side_effect=RuntimeError('collision')
    if fault=='cleanup':server._forward_navigator.cancel_nav.side_effect=RuntimeError('stop')
    if fault=='cancel':
        server._forward_navigator.navigate.side_effect=lambda *a,**k:setattr(handle,'is_cancel_requested',True)
    with patch('rclpy.ok',return_value=True):result=server.execute(handle)
    assert result.result_code!='SUCCESS' and not result.docked
    assert not server._handoff.busy
    if fault=='cleanup':
        assert result.error_code=='CANCEL_UNCONFIRMED'
        server._block.assert_called_once()
    if fault=='cancel':handle.canceled.assert_called_once()


def test_tag_session_survives_heading_change_and_uses_sim_clock():
    import numpy as np
    t=[10.];pose=np.eye(4);pose[0,3]=1.
    tags=Mock()
    mission=StationReturnMission(prepare=lambda:None,check=lambda:None,
        navigator=Mock(),graph=Mock(),station=Mock(),poses=NS(current=lambda _:pose),
        settings=NavigationSettings(),tag_control=tags,
        corridors={'A':{'entry':[0.,0.],'exit':[2.,0.],'yaw':0.}},clock=lambda:t[0])
    mission._navigating=True;mission.check()
    tags.begin.assert_called_once_with('A')
    pose[:2,:2]=[[0.,-1.],[1.,0.]];t[0]+=.21;mission.check()
    tags.begin.assert_called_once();tags.end.assert_not_called()
    pose[0,3]=5.;mission.check() # 같은 시뮬 시각: 갱신하지 않는다.
    tags.end.assert_not_called()
    t[0]+=.21;mission.check();tags.end.assert_called_once()


def test_effective_sim_return_settings_and_goal_checker():
    p=load_environment(ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml',ROOT,'sim',require_survey=False)
    assert p['station_return_components'] is True
    s=NavigationSettings.from_mapping({**p['navigation'],**p['station_return_navigation']})
    assert s.collision_retry_count==0 and s.arrival_tolerance_m==.05
    assert s.heading_tolerance_rad==pytest.approx(math.radians(6))
    nav=load_nav2_parameters(p['nav_params'],ROOT)['controller_server']['ros__parameters']
    assert nav['general_goal_checker']['xy_goal_tolerance']==.04
    assert nav['general_goal_checker']['yaw_goal_tolerance']==pytest.approx(math.radians(2.5))



def test_upstream_default_still_reverses_and_requires_selected_docking():
    import numpy as np
    from harvest_robot.station_return_states import ReturnController
    from farm_navigation.navigation_types import RoutePlan
    navigator=Mock();docking=Mock()
    graph=NS(plan=lambda *a:RoutePlan('p','r','map',((0.,4.),(0.,0.)),('e',),4.))
    mission=StationReturnMission(prepare=lambda:None,check=lambda:None,
        navigator=navigator,graph=graph,station=NS(xy=(0.,4.),yaw=-math.pi/2),
        poses=NS(current=lambda _:np.eye(4)),settings=NavigationSettings(),
        tag_control=None,corridors={},docking=docking)
    ReturnController(mission).run()
    assert navigator.navigate.call_args.kwargs['reverse'] is True
    assert navigator.navigate.call_args.kwargs['route_plan'].points==((0.,0.),(0.,4.))
    assert mission.docked
    docking.execute.assert_called_once();docking.cleanup.assert_called_once()
    navigator.cancel_nav.assert_called_once()


def test_tag_cleanup_exception_does_not_skip_nav_cancel_or_release(tmp_path):
    server,handle=component(tmp_path)
    server._tag_control=Mock()
    def navigate(*a,**k):
        server._mission._tag_active=True
        server._tag_control.end.side_effect=RuntimeError('tag end failed')
    server._forward_navigator.navigate.side_effect=navigate
    with patch('rclpy.ok',return_value=True):result=server.execute(handle)
    server._forward_navigator.cancel_nav.assert_called_once()
    assert result.error_code=='CANCEL_UNCONFIRMED' and not result.docked
    assert not server._handoff.busy
