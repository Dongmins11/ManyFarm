"""실제 Isaac 없는 작업 계약 시험: 재전송/실패 후 계속/취소/물리 정지 확인."""
import importlib
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_devices'))
from farm_sim_devices.arm_session import ArmSession, PhysicalReturn


class Device:
    def __init__(self):
        self.home = np.array([0., -1.39, .77, .62, .0488, 1.1])
        self.lower, self.upper = np.full(6, -3.), np.full(6, 3.)
        self.q, self.qd = self.home.copy(), np.zeros(6)
        self.selected = None
        self.targets = ['red', 'yellow', 'red2']
        self.now = 0.
        self.commands = []
        self.max_force = 0.
        self.selected_ids = []
    def joint_positions(self): return self.q.copy()
    def joint_velocities(self): return self.qd.copy()
    def command(self, q): self.commands.append(np.asarray(q).copy())
    def clear_target(self): self.selected = None
    def escaped_deposits(self, target_ids): return []
    def contacts_for_recovery(self): return {'max_force_N': self.max_force}
    def candidates(self, completed=()):
        return [dict(target_id=t, home_distance_m=i) for i,t in enumerate(self.targets) if t not in completed]
    def candidate_ids(self, completed=()): return [r['target_id'] for r in self.candidates(completed)]
    def select_target(self, target, completed=()):
        self.selected = target
        self.selected_ids.append(target)
    def sample(self):
        return dict(time_s=self.now, q=self.q.copy(), qd=self.qd.copy(), attached=self.selected=='yellow',
                    fruit_position=np.array([0.,0.,0.]), dock_displacement_m=0., dock_rotation_delta_rad=0.,
                    other_detached=False)
    def observe_physics_tick(self, dt, now): self.now = now


class Controller:
    def __init__(self): self.target=None; self.ticks=0; self.cancelled=False
    def start_target(self, target, sample): self.target=target; self.ticks=0
    def cancel(self): self.cancelled=True
    def tick(self, sample, dt):
        self.ticks+=1
        return self.observe(sample)
    def observe(self, sample):
        success = self.target != 'yellow'
        return SimpleNamespace(status='SUCCEEDED' if success else 'FAILED', reason='outcome', stage=1,
            joint_targets=sample['q'],diagnostics={'physical_status':'SUCCEEDED' if success else 'PENDING',
                                                 'teacher_strict_success':False})


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.device, self.controller = Device(), Controller()
        self.activity=[]
        cfg=dict(control_dt_s=.05, lease_s=2., settle_s=.1, stop_hold_s=.15, stop_timeout_s=.4,
                 recovery_contact_limit_N=2., recovery_waypoint_timeout_s=3., recovery_timeout_s=90.,
                 recovery_velocity_rad_s=.5, base_drift_limit_m=.02, base_yaw_drift_limit_rad=.05)
        self.arm=ArmSession('session','harvester','map',self.device,self.controller,
            SimpleNamespace(set_activity=lambda robot,value:self.activity.append(value)),cfg,Path(self.tmp.name))
        self.addCleanup(self.arm.close)
        self.seq=0;self.now=0.
    def msg(self, op='start', job='ab', **updates):
        self.seq+=1
        return dict(kind='harvest_arm',op=op,session='session',robot_id='harvester',seq=self.seq,
            sent=self.now,job_id=job,map_id='map',task_id='task',window_id='window',expected_count=3,
            goal_pose={'x':1.,'y':2.,'yaw':0.},**updates)
    def tick(self, heartbeat=True):
        if heartbeat:self.arm.accept(self.msg('keepalive'),now=self.now)
        self.device.now=self.now
        self.arm.tick(self.now,base_stationary=True,wall_now=self.now)
        self.now=round(self.now+.05,8)
    def run_done(self):
        for _ in range(300):
            self.tick()
            if self.arm.state['status']!='RUNNING':return
        self.fail('session did not terminate')
    def test_failure_continues_and_terminal_has_physical_counts(self):
        self.assertTrue(self.arm.accept(self.msg(),now=0.))
        self.run_done()
        self.assertEqual(self.device.selected_ids,['red','yellow','red2'])
        self.assertEqual((self.arm.state['status'],self.arm.state['success_count'],self.arm.state['failed_count']),('SUCCESS',2,1))
        result=__import__('json').loads((Path(self.tmp.name)/'session/ab/result.json').read_text())
        self.assertEqual(len(result['attempts']),3)
        self.assertTrue(self.arm.state['safe_stopped'])
        self.assertFalse(self.activity[-1])
    def test_repeated_start_and_completed_replay_never_pick_twice(self):
        self.arm.accept(self.msg(),now=0.)
        self.assertTrue(self.arm.accept(self.msg(),now=0.))
        self.run_done(); count=len(self.device.commands)
        self.assertTrue(self.arm.accept(self.msg(),now=self.now))
        self.tick()
        self.assertEqual(len(self.device.commands),count)
        self.assertEqual(len(self.device.selected_ids),3)
    def test_completed_job_rejects_changed_payload(self):
        self.arm.accept(self.msg(),now=0.);self.run_done()
        changed=self.msg();changed['expected_count']=100
        self.assertFalse(self.arm.accept(changed,now=self.now))
        changed=self.msg();changed['goal_pose']['x']=99.
        self.assertFalse(self.arm.accept(changed,now=self.now))

    def test_cancel_active_target_with_stop_failure_preserves_previous_counts(self):
        self.arm.accept(self.msg(),now=0.);self.tick();self.tick()
        self.assertIsNotNone(self.arm._target)
        self.device.qd[:]=1.
        self.arm.accept(self.msg('cancel'),now=self.now);self.run_done()
        self.assertEqual(self.arm.state['error_code'],'CANCEL_UNCONFIRMED')
        self.assertEqual(self.arm.state['success_count']+self.arm.state['failed_count'],0)

    def test_stale_wrong_robot_and_job_are_rejected(self):
        m=self.msg();m['robot_id']='other';self.assertFalse(self.arm.accept(m,now=0.))
        m=self.msg();m['sent']=-3.;self.assertFalse(self.arm.accept(m,now=0.))
        self.arm.accept(self.msg(),now=0.)
        self.assertFalse(self.arm.accept(self.msg('cancel',job='cd'),now=0.))
    def test_cancel_waits_for_measured_stop_and_does_not_open_gripper(self):
        self.arm.accept(self.msg(),now=0.);self.tick()
        self.device.q[-1]=.2;self.device.qd[:]=1.
        self.arm.accept(self.msg('cancel'),now=self.now)
        self.tick();self.assertEqual(self.arm.state['status'],'RUNNING')
        self.assertAlmostEqual(self.device.commands[-1][-1],.2)
        self.device.qd[:]=0.
        self.run_done()
        self.assertEqual(self.arm.state['status'],'CANCELED')
        self.assertEqual(self.arm.state['success_count']+self.arm.state['failed_count'],0)
    def test_unconfirmed_stop_blocks_new_job(self):
        self.arm.accept(self.msg(),now=0.);self.tick()
        self.device.qd[:]=1.
        self.arm.accept(self.msg('cancel'),now=self.now);self.run_done()
        self.assertEqual(self.arm.state['error_code'],'CANCEL_UNCONFIRMED')
        self.assertTrue(self.arm.busy);self.assertFalse(self.arm.state['safe_stopped'])
        self.assertFalse(self.arm.accept(self.msg(job='cd'),now=self.now))
    def test_lease_expiry_stops_without_advancing_policy(self):
        self.arm.accept(self.msg(),now=0.);self.tick()
        self.now=3.;self.arm.tick(.05,base_stationary=True,wall_now=3.)
        self.assertEqual(self.arm.state['stage'],'STOPPING')
        self.assertEqual(self.controller.ticks,0)
    def test_stop_measurement_exception_terminates_as_unconfirmed(self):
        self.arm.accept(self.msg(),now=0.);self.tick()
        self.arm.accept(self.msg('cancel'),now=self.now)
        self.device.joint_velocities=lambda: (_ for _ in ()).throw(RuntimeError('sensor lost'))
        self.tick()
        self.assertEqual(self.arm.state['status'],'FAILED')
        self.assertEqual(self.arm.state['error_code'],'CANCEL_UNCONFIRMED')
        self.assertFalse(self.arm.state['safe_stopped'])
        self.assertTrue(self.arm.busy)

    def test_empty_candidates_result_only_after_stationary_check(self):
        self.device.targets=[];self.arm.accept(self.msg(),now=0.)
        self.tick();self.assertEqual(self.arm.state['status'],'RUNNING')
        self.run_done();self.assertEqual(self.arm.state['status'],'SUCCESS')
        self.assertEqual(self.device.selected_ids,[])
    def test_previous_deposit_escape_stops_later_attempts(self):
        self.arm.accept(self.msg(),now=0.)
        for _ in range(60):
            self.tick()
            if self.arm.state['success_count']:
                break
        self.device.escaped_deposits=lambda ids:['red']
        self.run_done()
        self.assertEqual(self.arm.state['status'],'FAILED')
        self.assertEqual(self.arm.state['error_code'],'PREVIOUS_DEPOSIT_LOST')
        self.assertEqual(self.device.selected_ids,['red'])

    def test_return_contact_is_a_fault_not_next_target(self):
        self.arm.accept(self.msg(),now=0.)
        self.tick();self.tick()
        self.device.max_force=3.
        self.arm.observe_physics_tick(1/480,self.now)
        self.run_done()
        self.assertEqual(self.arm.state['error_code'],'RETURN_FAILED')
        self.assertEqual(self.device.selected_ids,['red'])
        self.assertEqual(self.arm.state['success_count'],1)


if __name__=='__main__': unittest.main()
