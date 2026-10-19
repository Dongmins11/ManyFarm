"""Small Isaac regression: native lock physics and injected contact/done transitions.

Contact fixtures test task wiring, not physical grasp quality or policy performance.
"""
import argparse
import json
from pathlib import Path
from isaaclab.app import AppLauncher
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--harvest-reward-version',type=int,choices=(7,8),default=7)
parser.add_argument('--output',type=Path,default=Path('outputs/harvest_rl/stage_probe'))
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args();args.kit_args=(args.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(args).app
failed=False
try:
    import torch
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    class Probe(HarvestEnv):
        def _get_dones(self):
            self._update_task()
            return torch.zeros_like(self.success),torch.zeros_like(self.success)
        def _apply_action(self):
            super()._apply_action()
            if hasattr(self,'probe_force'):
                for fruit in self.fruits:
                    fruit.instantaneous_wrench_composer.set_forces_and_torques(forces=self.probe_force,is_global=True)
        def _grasp_center(self,fruit):
            if getattr(self,'fixture',False):
                tcp,_=self._tcp()
                result=tcp.clone();result[:,0]+=self.fixture_distance
                return result
            return super()._grasp_center(fruit)
    cfg=TaskSettings(task='grasp',sequence=True,target_mode='random',num_fruits=3,
                     attachment_version=3,lock_attachment=True,curriculum=1,stage_transfer=True)
    env=Probe(cfg,num_envs=2,device=args.device)
    env.reset();action=torch.zeros(2,6,device=env.device)
    env.probe_force=torch.zeros(2,1,3,device=env.device);env.probe_force[:,:,0]=6.
    for _ in range(12):env.step(action)
    report={'locked_under_6N':bool(env.attached.all())}
    assert report['locked_under_6N']
    env.probe_force.zero_()
    # Stage success must terminate the assigned task without marking fruit collected.
    for stage in ('grasp','hold'):
        cfg.task=stage;env.fixture=False;env.reset();env.fixture=True;env.fixture_distance=.008
        for sensor,sign in ((env.fixed_contact,1.),(env.moving_contact,-1.)):
            sensor.data.force_matrix_w.zero_();sensor.data.net_forces_w.zero_()
            for e in range(2):
                i=int(env.target_index[e]);sensor.data.force_matrix_w[e,0,i,0]=5.*sign
                sensor.data.net_forces_w[e,0,0]=5.*sign
        env.arm_contact.data.net_forces_w.zero_()
        for _ in range(50):done,_=HarvestEnv._get_dones(env)
        assert env.success.all() and done.all() and not env.collected.any()
        report[stage+'_assigned_success']=True
        if stage == 'hold':
            assert (env._get_observations()['policy'][:,39] == 1).all()
            # Regrasp an attached fruit after losing contact: refresh slip origin,
            # retain episode grasp history, and never award a second grasp event.
            for sensor in (env.fixed_contact,env.moving_contact):
                sensor.data.force_matrix_w.zero_();sensor.data.net_forces_w.zero_()
            HarvestEnv._get_dones(env)
            env.grasp_relative += .03
            for sensor,sign in ((env.fixed_contact,1.),(env.moving_contact,-1.)):
                for e in range(2):
                    i=int(env.target_index[e]);sensor.data.force_matrix_w[e,0,i,0]=5.*sign
                    sensor.data.net_forces_w[e,0,0]=5.*sign
            for _ in range(5):HarvestEnv._get_dones(env)
            assert (env.slip < .001).all() and not env.grasp_event.any()
            report['attached_regrasp_refreshes_without_bonus']=True
    for task in ('pull','harvest'):
        cfg.task=task;cfg.reward_version=args.harvest_reward_version if task=='harvest' else 7;cfg.lock_attachment=False
        env.fixture=False;env.reset()
        env.fixture=True;env.fixture_distance=.0101
        # Inject opposing measured contacts and a native break event for the assigned target.
        def contacts(enabled=True):
            for sensor,sign in ((env.fixed_contact,1.),(env.moving_contact,-1.)):
                sensor.data.force_matrix_w.zero_();sensor.data.net_forces_w.zero_()
                for e in range(2):
                    i=int(env.target_index[e]);sensor.data.force_matrix_w[e,0,i,0]=5.*sign*enabled
                    sensor.data.net_forces_w[e,0,0]=5.*sign*enabled
            env.arm_contact.data.net_forces_w.zero_()
        contacts();env.joint_attachments.pending=[(e,int(env.target_index[e])) for e in range(2)]
        done,_=HarvestEnv._get_dones(env)
        assert env.pending_detach.all() and not done.any(),env.last_diagnostics
        contacts(False);done,_=HarvestEnv._get_dones(env)
        assert not done.any()
        contacts();env.fixture_distance=.008
        for _ in range(5):done,_=HarvestEnv._get_dones(env)
        assert env.valid_detach.all() and not env.failure.any()
        assert not done.any()  # neither immediate harvest completion nor immediate pull completion
        report[task+'_break_recovers_without_reset']=True
        # Long contact loss on a fresh provisional break must still fail.
        env.fixture=False;env.reset();env.fixture=True;env.fixture_distance=.0101
        contacts();env.joint_attachments.pending=[(e,int(env.target_index[e])) for e in range(2)]
        HarvestEnv._get_dones(env);contacts(False)
        for _ in range(3):done,_=HarvestEnv._get_dones(env)
        assert env.failure.all() and done.all()
        report[task+'_lost_contact_fails']=True
    env.fixture=False;env.probe_force[:,:,0]=6.;env.reset()
    for _ in range(12):env.step(action)
    report['unlocked_6N_breaks']=bool((~env.attached).any())
    assert report['unlocked_6N_breaks']
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'report.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
except Exception:
    import traceback
    traceback.print_exc();failed=True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app,locals().get('env'),failed)
