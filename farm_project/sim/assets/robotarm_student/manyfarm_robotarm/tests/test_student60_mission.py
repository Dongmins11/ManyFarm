import json
from pathlib import Path
import numpy as np
import pytest
from harvest_runtime.student60_mission import StudentHarvestMission, HarvestTarget
from harvest_runtime.student60_mission_session import select_anchored_track
from harvest_runtime.student60 import encode_command, decode_command

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'src/harvest_robot/config/student60_mission_v1.json').read_text())


class Session:
    contract = dict(lower_rad=[-2.]*6, upper_rad=[2.]*6,box_from_arm=np.eye(4).tolist())
    def __init__(self): self.started = []; self.pending = False
    def start(self, target, previous): self.started.append(target.target_id)
    def step(self, capture, q, qd, now):
        self.pending = True
        return encode_command(q, [1., .3], [-2.]*6, [2.]*6), dict(release_latched=True)
    def acknowledge(self, actual): assert self.pending; self.pending = False


def mission():
    session = Session()
    targets = [HarvestTarget(str(i), 'Red', (.2+i*.1, 0., .3)) for i in range(2)]
    return StudentHarvestMission(session, targets, CONFIG, lambda q, home: [home], task_list_complete=True)


def run(m, *, return_stuck=False):
    q = np.array(CONFIG['stow_rad']); previous = q.copy(); states = []
    for i in range(2500):
        now = i*.05; qd = (q-previous)/.05; previous = q.copy()
        evidence = dict(target_id=m.target.target_id, settled=True, stamp_s=now, source='unit_test_only') if m.state == 'WAIT_BOX' else None
        cmd, note = m.tick(now, q, qd, now, {}, box_evidence=evidence)
        states.append(m.state); m.acknowledge(cmd)
        if not (return_stuck and m.state == 'RETURN_STOW'):
            q = decode_command(cmd, [-2.]*6, [2.]*6)[0]
        if m.state in ('DONE', 'FAILED'): return states
    raise AssertionError('Mission never terminated')


def test_two_same_colour_targets_physically_return_between_each():
    m = mission(); states = run(m)
    assert m.report()['mission_complete'] and m.harvested == ['0', '1']
    assert m.session.started == ['0', '1']
    events = [e['state'] for e in m.events]
    assert events.count('RETURN_STOW') == 2 and events.count('TO_HOME') == 2
    assert events[-2:] == ['FINAL_STOP', 'DONE']
    first = events.index('RETURN_STOW'); second = events.index('TO_HOME', first)
    assert 'STOW_WAIT' in events[first:second]


def test_box_success_does_not_hide_return_failure():
    m = mission(); run(m, return_stuck=True)
    assert m.harvested == ['0'] and not m.report()['mission_complete']
    assert m.failure == 'motion_tracking_timeout'


def test_ack_and_initial_stow_are_required():
    m = mission(); q = np.array(CONFIG['stow_rad'])
    m.tick(0., q, q*0, 0.)
    with pytest.raises(ValueError, match='Acknowledge'): m.tick(.05, q, q*0, .05)
    m = mission(); q = np.array(CONFIG['home_rad'])
    m.tick(0., q, q*0, 0.)
    assert m.failure == 'start_requires_stowed_pose'


@pytest.mark.parametrize('changed', [dict(target_id='other'), dict(stamp_s=-1.), dict(settled=False)])
def test_invalid_box_evidence_never_counts(changed):
    m = mission(); m.state = 'WAIT_BOX'; m.harvest_start = 0.
    e = dict(target_id='0', stamp_s=0., settled=True); e.update(changed)
    q = np.array(CONFIG['stow_rad']); m.tick(0., q, q*0, 0., box_evidence=e)
    assert not m.harvested and m.failure == 'invalid_box_confirmation'


def test_lost_or_ambiguous_same_colour_target_is_not_reassigned():
    t = HarvestTarget('x', 'Red', (.2, 0., .3))
    def track(x): return dict(valid=True, label='Red', position_m=[x, 0., .3])
    assert select_anchored_track({'a': track(.21), 'b': track(.3)}, t) == 'a'
    assert select_anchored_track({'a': track(.21), 'b': track(.22)}, t) is None
    assert select_anchored_track({'b': track(.3)}, t) is None


def test_unknown_inventory_not_all_harvested():
    with pytest.raises(ValueError, match='complete assigned'):
        StudentHarvestMission(Session(), [], CONFIG, lambda q, h: [h], task_list_complete=False)


def test_nonfinite_and_out_of_bounds_stow_rejected():
    session=Session();t=[HarvestTarget('x','Red',(.2,0.,.3))]
    for q in ([0,0,0,0,0,float('nan')],[3,0,0,0,0,0]):
        config=dict(CONFIG,stow_rad=q)
        with pytest.raises(ValueError,match='Pose outside'):
            StudentHarvestMission(session,t,config,lambda q,h:[h],task_list_complete=True)


def test_stale_joint_feedback_and_external_collision_stop_without_success():
    for options in [dict(joint_stamp_s=-1.),dict(joint_stamp_s=0.,fault='collision')]:
        m=mission();q=np.array(CONFIG['stow_rad'])
        m.tick(0.,q,q*0,**options)
        assert m.state=='STOPPING' and not m.harvested and not m.report()['mission_complete']


def test_real_displacement_prevents_stationary_confirmation_even_if_velocity_says_zero():
    m=mission();q=np.array(CONFIG['stow_rad'])
    for i in range(20):
        sample=q.copy();sample[0]+=.02 if i%2 else -.02
        cmd,_=m.tick(i*.05,sample,q*0,i*.05);m.acknowledge(cmd)
    assert m.state=='STOW_WAIT' and not m.session.started


def test_completed_mission_still_detects_lost_stow():
    m=mission();run(m);q=np.array(CONFIG['stow_rad']);q[0]+=.1
    now=m.last_time+.05;m.tick(now,q,q*0,now)
    assert m.failure=='lost_final_stow' and not m.report()['mission_complete']


def test_lowest_first_uses_world_height_not_detector_order_or_arm_z():
    s=Session()
    # Arm X maps to vertical world Z. Sorting arm Z would reverse the result.
    frame=np.array([[0,0,-1,0],[0,1,0,0],[1,0,0,.7],[0,0,0,1.]])
    s.contract=dict(s.contract,box_from_arm=frame.tolist())
    targets=[HarvestTarget('high','Red',(.4,0,.1)),HarvestTarget('low','Yellow',(.2,0,.4)),
             HarvestTarget('middle','Red',(.3,0,.2))]
    m=StudentHarvestMission(s,targets,CONFIG,lambda q,h:[h],task_list_complete=True)
    assert [t.target_id for t in m.targets]==['low','middle','high']
    assert list(t.target_id for t in targets)==['high','low','middle']
    assert m.report()['target_priority']=='lowest_camera_observed_world_height_first'
    run(m)
    assert s.started==['low','middle','high']
    assert m.harvested==['low','middle','high'] and m.report()['mission_complete']


def test_height_ties_are_deterministic_by_id():
    targets=[HarvestTarget('b','Red',(.2,0,.3)),HarvestTarget('a','Yellow',(.3,0,.3))]
    m=StudentHarvestMission(Session(),targets,CONFIG,lambda q,h:[h],task_list_complete=True)
    assert [t.target_id for t in m.targets]==['a','b']
