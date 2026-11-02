"""벽 보정의 거리 상한, 충돌/취소 전파, 정지 후 벽 일치 검증."""
import math
from types import SimpleNamespace as S
import pytest
from harvest_robot.handoff_planning import HandoffPlanner


def setup(distance=.64239, angle=0.):
    state={'pose':(0.,0.,0.),'wall':(distance,angle),'guards':0}
    p=HandoffPlanner.__new__(HandoffPlanner)
    p._wall=dict(target_distance=.4325,max_distance=.2,distance_tolerance=.005,target_angle=.04276,max_yaw=.2618)
    p._motion=S(wait_stopped=lambda c:c())
    p._inputs=S(context=lambda:('m','w','s'),pose=lambda t,c:state['pose'],wall_error=lambda c:state['wall'])
    def guard(stage,path,check):
        assert stage=='window';state['guards']+=1
        return check
    p._guard=guard
    r=S(require_context=lambda *a:None,odom_frame='odom')
    return p,r,state


def test_small_excess_remeasured_after_stop():
    p,r,s=setup();step=p.plan_wall_approach(r,lambda:None)
    assert .019<step.route.distance_m<.021 and s['guards']==1
    step.monitor()
    s['pose']=(*step.route.points[-1],0.)
    s['wall']=(.64239-step.route.distance_m,0.)
    assert step.validate(1,lambda:None)['accepted']


@pytest.mark.parametrize('distance,angle',[(.6154,0.),(.4325,0.)])
def test_normal_wall_unchanged(distance,angle):
    p,r,s=setup(distance,angle)
    assert p.plan_wall_approach(r,lambda:None) is None
    assert s['guards']==0


@pytest.mark.parametrize('distance,angle',[(.67,0.),(.64239,.1),(float('nan'),0.)])
def test_large_or_invalid_input_rejected(distance,angle):
    p,r,s=setup(distance,angle)
    with pytest.raises((RuntimeError,ValueError)):p.plan_wall_approach(r,lambda:None)
    assert s['guards']==0


def test_wrong_wall_and_no_motion_rejected():
    p,r,s=setup();step=p.plan_wall_approach(r,lambda:None)
    with pytest.raises(RuntimeError):step.validate(1,lambda:None)
    s['pose']=(*step.route.points[-1],0.);s['wall']=(.58,0.)
    with pytest.raises(RuntimeError):step.validate(1,lambda:None)
    s['pose']=(0.,.01,0.)
    with pytest.raises(RuntimeError):step.monitor()


def test_collision_and_cancel_propagate():
    p,r,s=setup()
    def fail(*a):raise RuntimeError('blocked')
    with pytest.raises(RuntimeError):p.plan_wall_approach(r,fail)
    p._guard=fail
    with pytest.raises(RuntimeError):p.plan_wall_approach(r,lambda:None)
