"""실제시간 지연이 센서·제어권·응답 예산을 소모하지 않는지 검증한다."""
from types import SimpleNamespace as NS
from concurrent.futures import Future
import pytest
from farm_navigation.operation_clock import operation_time
from farm_docking.motion_gate import Lease
from farm_docking.clients import wait
from transport_robot.transport_node import TransportNode
from transport_robot.transfer_session import TransferSession
from transport_robot.unload_session import UnloadSession


def fixture(monkeypatch):
    times = {'sim': 10., 'wall': 100.}
    clock = NS(ros_time_is_active=True, now=lambda: NS(nanoseconds=int(times['sim']*1e9)))
    node = NS(get_clock=lambda:clock)
    monkeypatch.setattr('time.monotonic', lambda:times['wall'])
    return times, clock, node


def test_clock_initial_zero_pause_resume_and_real(monkeypatch):
    t,c,n = fixture(monkeypatch)
    t['sim']=0.
    assert operation_time(n)==0.
    t['wall']=10000.
    assert operation_time(n)==0.
    t['sim']=2.
    assert operation_time(n)==2.
    c.ros_time_is_active=False
    assert operation_time(n)==10000.


def test_lease_survives_wall_stall_but_expires_in_sim(monkeypatch):
    t,c,n=fixture(monkeypatch)
    lease=Lease()
    accepted,token=lease.request('nav','',False,operation_time(n))
    assert accepted
    t['wall']+=1000.
    assert lease.permits('nav',operation_time(n))
    t['sim']+=.61
    assert not lease.permits('nav',operation_time(n))
    assert not lease.request('nav',token,False,operation_time(n))[0]


def test_transport_pose_and_scan_age_follow_sim(monkeypatch):
    t,c,n=fixture(monkeypatch)
    n.check_precision=lambda:None
    n.lease=None;n.sorter_approach=None;n.harvest_approach=None
    n._pose=(0,0,0);n._pose_at=10.;n._scan_at=10.
    n.settings=NS(tf_max_age_s=1.)
    t['wall']+=1000.
    TransportNode.check_motion(n)
    t['sim']=11.01;n._scan_at=11.01
    with pytest.raises(RuntimeError,match='TF 단절'):TransportNode.check_motion(n)


def test_response_budget_only_advances_with_sim(monkeypatch):
    t,c,n=fixture(monkeypatch)
    pending=Future()
    def tick(_):
        t['wall']+=1.
        if t['wall']>200.:t['sim']+=.1
    monkeypatch.setattr('farm_docking.clients.time.sleep',tick)
    with pytest.raises(TimeoutError):wait(pending,1.,clock=lambda:operation_time(n))
    assert t['wall']>200. and t['sim']>11.


@pytest.mark.parametrize('kind',[TransferSession,UnloadSession])
def test_event_wait_checks_cancel_while_sim_paused(monkeypatch,kind):
    t,c,n=fixture(monkeypatch)
    session=kind(timeout=1.,clock=lambda:operation_time(n))
    calls=[]
    def check():
        calls.append(1);t['wall']+=100.
        if len(calls)==3:raise RuntimeError('operator cancel')
    monkeypatch.setattr(session._cv,'wait',lambda _:None)
    with pytest.raises(RuntimeError,match='operator cancel'):
        if kind is TransferSession:session.wait('DOCK_READY',check)
        else:session.wait(check)
    assert len(calls)==3


def test_reset_invalidates_old_lease_and_cached_pose(monkeypatch):
    t,c,n=fixture(monkeypatch)
    lease=Lease()
    _,token=lease.request('nav','',False,operation_time(n))
    t['sim']=0.
    assert not lease.permits('nav',operation_time(n))
    assert not lease.request('nav',token,False,operation_time(n))[0]
    n.check_precision=lambda:None;n.lease=None
    n._pose=(0,0,0);n._pose_at=10.;n._scan_at=10.
    n.settings=NS(tf_max_age_s=1.)
    with pytest.raises(RuntimeError,match='단절'):TransportNode.check_motion(n)
