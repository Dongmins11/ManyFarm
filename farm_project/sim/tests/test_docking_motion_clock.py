"""느린/일시정지 시뮬에서도 동작 예산은 /clock으로, 통신 대기는 실제시간으로 계산한다."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'robot/ros_ws/src/farm_docking'))
import farm_docking.precision_server as module
from farm_docking.precision_server import PrecisionServer


def server(monkeypatch, sim=True):
    clock={'wall':100.,'sim':10.}
    monkeypatch.setattr(module,'time',NS(monotonic=lambda:clock['wall']))
    n=NS(get_parameter=lambda _:NS(value=sim),get_clock=lambda:NS(now=lambda:NS(nanoseconds=int(clock['sim']*1e9))))
    n.motion_time=lambda:PrecisionServer.motion_time(n)
    n.motion_elapsed=lambda t:PrecisionServer.motion_elapsed(n,t)
    n.lidar_status=lambda s,p:(0.,0.,True,.203)
    n.phase_feedback=lambda *args:None
    n.drive=lambda *args,**kwargs:None
    n.get_logger=lambda:NS(info=lambda *args:None)
    n.stopped=lambda:True
    finished=[];n.finish=lambda *args:finished.append(args)
    s=dict(lidar_started=n.motion_time(),motion_started=n.motion_time(),started=clock['wall'],
           lidar_log_at=clock['wall'],lidar_controller=NS(surface=None,good_since=None))
    p={'lidar_approach':{'timeout_s':25.5,'target_distance_m':.2,'stale_wait_s':1.}}
    return n,s,p,clock,finished


def test_reproduced_25_wall_seconds_14_sim_seconds_can_finish(monkeypatch):
    n,s,p,c,done=server(monkeypatch)
    c.update(wall=125.72,sim=24.03)
    PrecisionServer.run_lidar_approach(n,s,p)
    assert done and n.motion_elapsed(s['motion_started'])==pytest.approx(14.03)


def test_pause_does_not_spend_movement_budget(monkeypatch):
    n,s,p,c,done=server(monkeypatch)
    n.lidar_status=lambda s,p:(0.,0.,False,.203)
    for wall in (200.,500.,1000.):
        c['wall']=wall
        PrecisionServer.run_lidar_approach(n,s,p)
    assert n.motion_elapsed(s['motion_started'])==0 and not done


@pytest.mark.parametrize('sim',[True,False])
def test_timeout_still_fails_on_selected_clock(monkeypatch,sim):
    n,s,p,c,done=server(monkeypatch,sim)
    c['sim' if sim else 'wall']+=25.6
    with pytest.raises(TimeoutError,match='Final lidar approach timed out'):
        PrecisionServer.run_lidar_approach(n,s,p)
    assert not done


def test_real_uses_monotonic_even_when_ros_clock_changes(monkeypatch):
    n,s,p,c,done=server(monkeypatch,False)
    c.update(wall=114.,sim=9999.)
    PrecisionServer.run_lidar_approach(n,s,p)
    assert done and n.motion_elapsed(s['motion_started'])==14.


def test_clock_reset_aborts_instead_of_negative_elapsed(monkeypatch):
    n,s,p,c,done=server(monkeypatch)
    c['sim']=0.
    with pytest.raises(RuntimeError,match='clock moved backwards'):
        PrecisionServer.run_lidar_approach(n,s,p)
    assert not done


def test_input_recovery_does_not_mix_wall_and_sim_seconds(monkeypatch):
    n,s,p,c,done=server(monkeypatch)
    s.update(lidar_input_wait_since=101.,lidar_input_wait_motion=10.5)
    c.update(wall=101.8,sim=10.7)
    PrecisionServer.run_lidar_approach(n,s,p)
    assert s['lidar_started']==pytest.approx(10.2)
    assert s['motion_started']==pytest.approx(10.2)
    assert s['started']==pytest.approx(100.8)
    assert 'lidar_input_wait_motion' not in s and 'lidar_input_wait_since' not in s


def test_missing_sensor_watchdog_keeps_wall_time_even_when_sim_pauses(monkeypatch):
    n,s,p,c,done=server(monkeypatch)
    s['lidar_stage']=True;n.log_scan_delay=lambda *args:None
    assert PrecisionServer.wait_lidar_inputs(n,s,p,RuntimeError('No raw front scan'))
    c['wall']+=1.1
    assert PrecisionServer.wait_lidar_inputs(n,s,p,RuntimeError('No raw front scan'))
    assert done and 'Lidar input wait timeout' in done[-1][1]


def test_begin_uses_motion_clock_without_changing_distance_budget(monkeypatch):
    n,s,p,c,done=server(monkeypatch)
    p['base_frame']='base';p['distance_heading_trial']={'marker_id':41}
    p['lidar_approach'].update(scan_frame='scan',max_travel_m=1.5,max_linear_mps=.04,timeout_s=65.)
    n.lidar_odom=lambda p:(0.,0.,0.)
    n.lidar_status=lambda s,p:(0.,0.,False,.613)
    n.tf=NS(lookup_transform=lambda *a,**k:NS(transform=NS(rotation=NS(x=0.,y=0.,z=0.,w=1.))))
    monkeypatch.setattr(module,'LidarApproach',lambda *a,**k:NS(surface=None))
    PrecisionServer.begin_lidar_approach(n,s,p)
    assert s['lidar_started']==10.
    assert s['lidar_limits']['timeout_s']==pytest.approx(25.4875)
    assert p['lidar_approach']['timeout_s']==65.


def marker_setup(monkeypatch, sim=True):
    n,s,p,c,done=server(monkeypatch,sim)
    p.update(target_marker_id=42,initial_marker_recovery=dict(enabled=True,wait_s=3.,
        reverse_distance_m=.05,reverse_speed_mps=.02,search_angle_rad=.26,
        search_speed_rps=.12,timeout_s=30.))
    s.update(handle=NS(request=NS(operation='DOCK')),observation_start_ns=0)
    n._raw_reports=[];n.image_header_max_age_s=.5
    n._target_tracker=NS(phase='ACQUIRE');n.lidar_odom=lambda p:(0.,0.,0.)
    return n,s,p,c


@pytest.mark.parametrize('sim',[True,False])
def test_initial_marker_recovery_uses_selected_motion_clock(monkeypatch,sim):
    n,s,p,c=marker_setup(monkeypatch,sim)
    assert PrecisionServer.run_initial_marker_recovery(n,s,p)
    if sim:
        c['wall']+=100.
        assert PrecisionServer.run_initial_marker_recovery(n,s,p)
        assert s['initial_marker_policy'].origin is None  # 정지된 시뮬은 후진도 시작하지 않음.
    c['sim' if sim else 'wall']+=30.1
    with pytest.raises(TimeoutError,match='Initial marker reacquisition exhausted'):
        PrecisionServer.run_initial_marker_recovery(n,s,p)


def test_marker_verification_and_heading_acquisition_share_sim_clock(monkeypatch):
    n,s,p,c=marker_setup(monkeypatch)
    n._raw_reports=[dict(stamp_ns=int(c['sim']*1e9),markers=[dict(marker_id=42)])]
    assert PrecisionServer.run_initial_marker_recovery(n,s,p)
    c['wall']+=60.
    assert PrecisionServer.run_initial_marker_recovery(n,s,p)
    assert s['initial_marker_policy'].rejected_pose is None  # 2초 검증 대기도 /clock.
    c['sim']+=.3;n._target_tracker.phase='TRANSIT'
    assert not PrecisionServer.run_initial_marker_recovery(n,s,p)
    assert s['distance_acquire_started']==10.3
    p['distance_heading_trial']={'acquire_timeout_s':5.}
    n.capture_distance_heading=lambda s,p:None
    PrecisionServer.run_distance_heading_trial(n,s,p)
    c['sim']+=5.1
    with pytest.raises(TimeoutError,match='stable front marker not acquired'):
        PrecisionServer.run_distance_heading_trial(n,s,p)


def test_initial_marker_clock_reset_fails(monkeypatch):
    n,s,p,c=marker_setup(monkeypatch)
    PrecisionServer.run_initial_marker_recovery(n,s,p)
    c['sim']=0.
    with pytest.raises(RuntimeError,match='clock moved backwards'):
        PrecisionServer.run_initial_marker_recovery(n,s,p)
