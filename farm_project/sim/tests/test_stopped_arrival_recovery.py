"""정지 후 오차를 안전한 재보정으로 연결하고 다른 실패를 삼키지 않는지 검증한다."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from builtin_interfaces.msg import Time

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_navigation', 'harvest_robot', 'farm_docking', 'transport_robot'):
    sys.path.insert(0, str(ROOT/'robot/ros_ws/src'/package))
from farm_navigation.arrival import ArrivalValidationError
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from harvest_robot.handoff_navigation import HandoffNavigationSteps, NavigationBinding, NavigationStep
from farm_docking.initial_marker_recovery import ApproachReentryRequired
from transport_robot.states.transfer_states import TaggingState
from transport_robot.states.navigation_move_state import NavigationMoveState


def wall_fixture(accepted):
    events, records = [], []
    state = dict(plans=0, stamp=100)
    def stop(check):
        check(); events.append('stopped'); state['stamp'] += 1
        return state['stamp']
    def plan(stage, reference, check):
        check(); state['plans'] += 1
        number=state['plans']
        events.append(('plan', number))
        route=RoutePlan(str(number),'','odom',((number/100.,0.),(.2,0.)),(),.2)
        def validate(stamp, check):
            check(); events.append(('validate', number, stamp))
            # 실패 기록의0.541도처럼 정지 후에만 기존0.5도 한도를 벗어난다.
            return dict(accepted=accepted[number-1], final_angle_error=.009439,
                        final_distance=.43334)
        return NavigationStep(route,0.,validate,lambda:events.append('guard'), wall_parameters={})
    client=NS(has_goal=False, preflight=lambda *a,**kw: events.append('preflight'),
              execute=lambda *a: events.append('goal') or 4,
              cancel=lambda: events.append('cancel'))
    node=NS(get_clock=lambda:NS(now=lambda:NS(to_msg=lambda:Time())),
            get_logger=lambda:NS(warning=lambda x:events.append(x)))
    steps=HandoffNavigationSteps(node=node,motion=NS(wait_stopped=stop),spin=NS(),
        bindings={k:NavigationBinding(NavigationSettings(mode='follow_path',map_frame='odom'),client)
                  for k in ('wall','departure','retreat','return')},
        capture=lambda c:None,plan=plan,check=lambda:None,settling_check=lambda:None,
        arm_output=lambda stage:events.append('arm'),stop_output=lambda:events.append('zero'),
        record=records.append)
    return steps, client, state, events, records


def test_wall_replans_after_stopped_error_and_only_returns_confirmed_arrival():
    steps, _, state, events, records=wall_fixture([False, True])
    result=steps.execute('wall',object(),lambda:None)
    assert result.measurement['accepted']
    assert state['plans']==2
    assert events.index('cancel') < events.index(('plan',2))
    failures=[r for r in records if r.get('event')=='STOPPED_ARRIVAL_REJECTED']
    assert len(failures)==1 and failures[0]['measurement']['final_angle_error']==.009439
    assert steps._active is None and not steps._owns_output


def test_wall_exhaustion_is_failure_after_two_retries():
    steps, _, state, events, records=wall_fixture([False]*3)
    with pytest.raises(ArrivalValidationError):steps.execute('wall',object(),lambda:None)
    assert state['plans']==3
    assert [r['retry'] for r in records if 'retry' in r]==[True, True, False]
    assert events.count('goal')==3


@pytest.mark.parametrize('stage', ['departure','retreat','return'])
def test_other_stages_are_not_replayed(stage):
    steps, _, state, _, _=wall_fixture([False])
    with pytest.raises(ArrivalValidationError):steps.execute(stage,object(),lambda:None)
    assert state['plans']==1


def test_nav_failure_is_not_treated_as_arrival_drift():
    steps, client, state, _, _=wall_fixture([False])
    client.execute=Mock(side_effect=RuntimeError('collision'))
    with pytest.raises(RuntimeError,match='collision'):steps.execute('wall',object(),lambda:None)
    assert state['plans']==1


def test_cleanup_failure_prevents_wall_replan():
    steps, client, state, _, _=wall_fixture([False])
    client.cancel=Mock(side_effect=RuntimeError('cancel unconfirmed'))
    with pytest.raises(RuntimeError,match='cancel unconfirmed'):steps.execute('wall',object(),lambda:None)
    assert state['plans']==1


def test_cancel_after_stop_prevents_wall_replan():
    steps, _, state, events, _=wall_fixture([False])
    def check():
        if 'cancel' in events:raise RuntimeError('user canceled')
    with pytest.raises(RuntimeError,match='user canceled'):steps.execute('wall',object(),check)
    assert state['plans']==1


def transport_fixture():
    c=NS(check=Mock(),mission=NS(set_contact=Mock(),record_stage=Mock()),
         approach_reentry_count=0, request=object(),feedback=Mock(),transition=Mock())
    return TaggingState(c),c


def test_stopped_pre_approach_failure_returns_to_navigation_with_limit():
    state,c=transport_fixture()
    error=ApproachReentryRequired('stopped target too far')
    for count in (1,2):
        state._done(error)
        assert c.approach_reentry_count==count
        assert isinstance(c.transition.call_args.args[0],NavigationMoveState)
        c.mission.set_contact.assert_called_with(False)
    with pytest.raises(RuntimeError,match='2회 소진'):state._done(error)
    assert c.transition.call_count==2


def test_ordinary_failed_docking_does_not_reenter_navigation():
    state,c=transport_fixture()
    with pytest.raises(RuntimeError,match='마커 확인 실패'):state._done(False)
    c.transition.assert_not_called()
    c.mission.set_contact.assert_not_called()


def test_cancel_precedes_reentry_transition():
    state,c=transport_fixture()
    c.check.side_effect=RuntimeError('user canceled')
    with pytest.raises(RuntimeError,match='user canceled'):
        state._done(ApproachReentryRequired('stopped'))
    c.transition.assert_not_called()
    c.mission.set_contact.assert_not_called()


def test_visible_outside_envelope_requests_reentry_before_any_search_motion():
    from test_harvest_route_envelope import setup_route, report
    from farm_docking.precision_server import PrecisionServer
    import numpy as np
    server,_,_,_=setup_route()
    profile=server.profiles['pickup']
    frame=report(1.765)  # 0.54m 이격 목표를 빼면1.225m: 기존1.2m 밖.
    tracker=server._target_tracker
    assert not tracker.update(frame,np.eye(4),10_000_000_000,1.2,.3)
    server._raw_reports=[frame]
    server.motion_time=lambda:10.
    server.motion_elapsed=lambda started:10.-started
    server.image_header_max_age_s=.5
    server.stopped=lambda:True
    server.finish=Mock()
    server.drive=Mock()
    session=dict(handle=NS(request=NS(operation='DOCK')),observation_start_ns=9_000_000_000)
    assert PrecisionServer.run_initial_marker_recovery(server,session,profile)
    assert 'approach_reentry_error' in session
    server.finish.assert_called_once()
    server.drive.assert_not_called()  # 후진 탐색/임의 전진을 이 경로에서 출력하지 않는다.
    assert tracker.phase=='ACQUIRE' and tracker.goal is None
    tracker.update(report(1.,marker_id=41),np.eye(4),10_000_000_000,1.2,.3)
    assert tracker.envelope_rejection is None


@pytest.mark.parametrize('change', ['stale','old_session','already_moved','not_stopped'])
def test_reentry_proof_rejects_stale_or_moving_inputs(change):
    from test_harvest_route_envelope import setup_route, report
    from farm_docking.precision_server import PrecisionServer
    from farm_docking.initial_marker_recovery import InitialMarkerRecovery
    import numpy as np
    server,_,_,_=setup_route(); profile=server.profiles['pickup']
    frame=report(1.765)
    server._target_tracker.update(frame,np.eye(4),10_000_000_000,1.2,.3)
    server._raw_reports=[frame]; server.image_header_max_age_s=.5
    server.motion_time=lambda:10.
    server.motion_elapsed=lambda started:0.
    server.stopped=lambda:change!='not_stopped'
    server.finish=Mock();server.drive=Mock();server.phase_feedback=Mock()
    server.lidar_odom=lambda p:(0.,0.,0.)
    policy=InitialMarkerRecovery(profile['initial_marker_recovery'],10.)
    session=dict(handle=NS(request=NS(operation='DOCK')),observation_start_ns=9_000_000_000,
                 initial_marker_policy=policy)
    if change=='stale':server._target_tracker.envelope_rejection['stamp_ns']=1
    if change=='old_session':session['observation_start_ns']=9_950_000_000
    if change=='already_moved':policy.origin=(0.,0.,0.)
    policy.step=Mock(return_value=(0.,0.,False,'WAIT_INITIAL_MARKER'))
    PrecisionServer.run_initial_marker_recovery(server,session,profile)
    assert 'approach_reentry_error' not in session
    server.finish.assert_not_called()


@pytest.mark.parametrize('stopped,released,canceled,changed,proof', [
    (True,True,False,False,True), (False,True,False,False,False),
    (True,False,False,False,False), (True,True,True,False,False),
    (True,True,False,True,False)])
def test_server_reports_reentry_only_with_terminal_safety_proof(stopped,released,canceled,changed,proof):
    from farm_docking.precision_server import PrecisionServer
    handle=NS(is_cancel_requested=canceled,canceled=Mock(),succeed=Mock(),abort=Mock())
    def finish_pending(item):
        session=item[1]
        session.update(error='cleanup error' if changed else 'range', approach_reentry_error='range',
                       lease_released=released)
        session['done'].set()
    server=NS(_pending=NS(put=finish_pending),motion_time=lambda:0.,stopped=lambda:stopped,
              _reservation=NS(release=Mock()))
    result=PrecisionServer.execute(server,handle)
    assert result.error_message.startswith(ApproachReentryRequired.prefix)==proof
    assert not result.success
    if canceled and stopped:handle.canceled.assert_called_once()


@pytest.mark.parametrize('status,stopped,cleanup_failure,typed', [
    (6,True,False,True), (5,True,False,False), (6,False,False,False),
    (6,True,True,False)])
def test_precision_client_preserves_reentry_only_after_confirmed_cleanup(status,stopped,cleanup_failure,typed):
    from threading import RLock
    from farm_docking.clients import PrecisionClient
    client=PrecisionClient.__new__(PrecisionClient)
    client._goal_lock=RLock();client._accept_future=None;client.handle=None
    client._late_error='';client.result_future=None
    client.client=NS(wait_for_server=lambda **kw:True);client.check=lambda:None;client.timeout=120.
    response=NS(status=status,result=NS(stopped=stopped,success=False,
                error_message=ApproachReentryRequired.prefix+'range'))
    future=NS(done=lambda:True,result=lambda:response)
    handle=NS(accepted=True,get_result_async=lambda:future)
    def accept(goal):client.handle=handle;return handle
    client._accept=accept
    if cleanup_failure:client.stop=Mock(side_effect=RuntimeError('cleanup failed'))
    request=NS(task_id='t',profile_id='pickup',target_marker_id=42,docking_marker_id=42,
               clearance_xy=None,xy=(0.,0.),clearance_yaw=None,yaw=0.)
    with pytest.raises(RuntimeError) as caught:client.run(request,'DOCK')
    assert isinstance(caught.value,ApproachReentryRequired)==typed
    if typed:assert not client.pending


@pytest.mark.parametrize('outcomes', [[False,True],[False,False,False]])
def test_alignment_replans_after_stopped_residual(outcomes):
    from harvest_robot.handoff_navigation import AlignmentStep
    steps,_,state,events,records=wall_fixture(outcomes)
    def plan(stage,reference,check):
        check();state['plans']+=1;attempt=state['plans']
        def validate(stamp,check):
            check()
            if not outcomes[attempt-1]:
                raise ArrivalValidationError(dict(heading_error_rad=.019540),stamp)
            return dict(accepted=True)
        return AlignmentStep(.019540/attempt,40.,False,validate,lambda:events.append('guard'))
    from harvest_robot.handoff_components import SpinMotion
    steps._spin=NS(ready=lambda:True,execute=lambda *a:events.append('spin'),cancel=lambda:events.append('spin_cancel'))
    # 동작 구성의 실제 실행 경로를 사용한다.
    from harvest_robot.handoff_components import ComponentSteps
    actions=dict(steps.components.actions);actions['align']=SpinMotion('align',plan,steps._align)
    steps.components=ComponentSteps(capture=steps._capture_checked,actions=actions,stop=steps.stop)
    if outcomes[-1]:
        steps.execute('align',object(),lambda:None)
    else:
        with pytest.raises(ArrivalValidationError):steps.execute('align',object(),lambda:None)
    assert state['plans']==len(outcomes)
    assert events.count('spin')==len(outcomes)
    assert events.count('spin_cancel')==outcomes.count(False)
