"""Isaac wiring regression. Contact fixtures are NOT a physical grasp test."""
import argparse
from isaaclab.app import AppLauncher
parser=argparse.ArgumentParser(description=__doc__)
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args();args.kit_args=(args.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(args).app
env=None;failed=False
try:
    import torch
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    class Probe(HarvestEnv):
        def _tcp(self):
            p,q=super()._tcp()
            if getattr(self,'fixture',False):
                q=torch.tensor(self.fixture_quat,device=self.device).repeat(self.num_envs,1)
            return p,q
        def _grasp_center(self,fruit):
            if getattr(self,'fixture',False):
                p,_=self._tcp();p=p.clone();p[:,0]+=.005;return p
            return super()._grasp_center(fruit)
    env=Probe(TaskSettings(task='grasp',attachment_version=4,grasp_orientation='horizontal'),num_envs=1,device=args.device)
    env.reset()
    for _ in range(4):env.step(torch.zeros(1,6,device=env.device))
    report={'real_step_reward_finite':bool(torch.isfinite(env._get_rewards()).all())}
    for label,quat,expected in [('vertical',[.70710678,0.,.70710678,0.],False),('horizontal',[1.,0.,0.,0.],True)]:
        env.fixture=False;env.reset();env.fixture=True;env.fixture_quat=quat
        for sensor,sign in [(env.fixed_contact,1.),(env.moving_contact,-1.)]:
            sensor.data.force_matrix_w.zero_();sensor.data.net_forces_w.zero_()
            sensor.data.force_matrix_w[:,0,0,0]=sign*5.
        env.arm_contact.data.net_forces_w.zero_()
        # Avoid unwanted-finger false fixture force: net must equal filtered force.
        env.fixed_contact.data.net_forces_w[:,0,0]=5.
        env.moving_contact.data.net_forces_w[:,0,0]=-5.
        for _ in range(6):env._update_task()
        assert bool(env.success[0]) == expected, (label,env.last_diagnostics)
        report[label+'_success']=bool(env.success[0])
    env.fixture_quat=[.70710678,0.,.70710678,0.]
    env._update_task()
    assert bool(env.grip[0]) and not bool(env.last_diagnostics['grasp_orientation_required'][0])
    report['rotation_after_confirmation_allowed']=True
    print('HORIZONTAL_PROBE',report,flush=True)
except Exception:
    import traceback
    traceback.print_exc();failed=True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app,env,failed)
