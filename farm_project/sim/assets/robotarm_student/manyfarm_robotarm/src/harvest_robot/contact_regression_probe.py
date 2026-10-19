"""Regression: rotating world-wrench frame, tap vs pull, detached free fall.

External load fixtures isolate physics from policies; they do not certify every
arm contact or the measured properties of the demonstration hook.
"""
import argparse
import json
from pathlib import Path
from isaaclab.app import AppLauncher
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=Path('outputs/harvest_rl/contact_response3_probe.json'))
parser.add_argument('--response',type=int,choices=(3,4),default=4)
parser.add_argument('--mass',type=float,default=.035)
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args();args.kit_args=(args.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(args).app
env=None;failed=False
try:
    import torch
    from isaaclab.utils.math import quat_apply
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    class Probe(HarvestEnv):
        def _get_dones(self):
            self._update_task()
            return torch.zeros_like(self.success),torch.zeros_like(self.success)
        def _apply_action(self):
            super()._apply_action()
            if not hasattr(self,'probe_step'):return
            force=torch.zeros(6,1,3,device=self.device)
            if self.probe_step < 6:
                force[0,0,1]=2.  # 25 ms sideways tap
                force[1,0,0]=6.  # 25 ms compression
            force[4,0,0]=-3.  # modest sustained pull
            if self.probe_step < 72:force[5,0,2]=-2.  # press for 0.3s, then release
            force[2,0,0]=-4.     # sustained outward pull
            self.fruits[0].instantaneous_wrench_composer.set_forces_and_torques(
                forces=force,torques=torch.zeros_like(force),is_global=True)
            self.probe_step+=1
    settings=TaskSettings(task='pull',attachment_version=4,stem_response_version=3,mass=args.mass)
    if args.response==4:
        from harvest_rl.behavior_contract import apply_gentle_hook
        apply_gentle_hook(settings)
    env=Probe(settings,num_envs=6,device=args.device)
    env.reset();fruit=env.fruits[0];device=env.device
    state=fruit.data.default_root_state.clone()
    state[:,:3]=env.scene.env_origins+torch.tensor([1.4,0.,2.],device=device)
    state[:,3:7]=torch.tensor([1.,0.,0.,0.],device=device);state[:,7:]=0
    fruit.write_root_state_to_sim(state)
    force=torch.zeros(6,3,device=device);force[:,0]=1.;zero=torch.zeros_like(force)
    fruit.permanent_wrench_composer.reset()
    fruit.permanent_wrench_composer.set_forces_and_torques(forces=force[:,None],torques=zero[:,None],is_global=True)
    state[:,3:7]=torch.tensor([.70710678,0.,0.,.70710678],device=device)
    fruit.write_root_state_to_sim(state)
    # Reproduce stale conversion: same global force after a 90-degree rotation.
    fruit.permanent_wrench_composer.set_forces_and_torques(forces=force[:,None],torques=zero[:,None],is_global=True)
    stale_world=quat_apply(fruit.data.root_link_quat_w,fruit.permanent_wrench_composer.composed_force_as_torch[:,0])
    stale_error=(stale_world-force).norm(dim=-1).max().item()
    env._set_stem_wrench(fruit,0,force,zero)
    fresh_world=quat_apply(fruit.data.root_link_quat_w,fruit.permanent_wrench_composer.composed_force_as_torch[:,0])
    fresh_error=(fresh_world-force).norm(dim=-1).max().item()
    assert stale_error>1. and fresh_error<1e-5,(stale_error,fresh_error)
    # Reset physical bodies for the pulse/pull/drop scenarios.
    state[:,3:7]=torch.tensor([1.,0.,0.,0.],device=device)
    fruit.write_root_state_to_sim(state)
    env.rest_quat[:,0]=state[:,3:7]
    tip=torch.as_tensor(env.tips_np[0],device=device,dtype=torch.float32).expand(6,-1)
    env.anchors[:,0]=state[:,:3]+quat_apply(state[:,3:7],tip)
    env.threshold.fill_(2.5);env.attached[3,0]=False
    env.probe_step=0
    report={'response':args.response,'mass_kg':args.mass,'stale_world_force_error_N':stale_error,'fresh_world_force_error_N':fresh_error}
    max_detached_force=0.;max_detached_torque=0.
    max_rebound=0.;max_up_speed=0.;min_z=float(state[5,2]);min_after_release=float(state[5,2])
    for step in range(40):
        env.step(torch.zeros(6,6,device=device))
        z=float(fruit.data.root_link_pos_w[5,2]);min_z=min(min_z,z)
        if step>=6:
            max_rebound=max(max_rebound,z-float(state[5,2]))
            min_after_release=min(min_after_release,z)
            max_up_speed=max(max_up_speed,float(fruit.data.root_com_lin_vel_w[5,2]))
        max_detached_force=max(max_detached_force,float(env.applied_stem_force[3,0].norm()))
        max_detached_torque=max(max_detached_torque,float(env.applied_stem_torque[3,0].norm()))
        assert fruit.permanent_wrench_composer.composed_force_as_torch[3].abs().max().item()==0.
        assert fruit.permanent_wrench_composer.composed_torque_as_torch[3].abs().max().item()==0.
        if step==3:
            report['detached_drop_0_2s_m']=float(state[3,2]-fruit.data.root_link_pos_w[3,2])
            report['detached_velocity_0_2s_m_s']=float(fruit.data.root_com_lin_vel_w[3,2])
    report.update(press_depth_m=float(state[5,2])-min_z,rebound_above_initial_m=max_rebound,peak_upward_speed_m_s=max_up_speed,final_press_z_m=float(fruit.data.root_link_pos_w[5,2]),
                  break_load_N=env.break_load[:,0].tolist())
    report.update(final_attached=env.attached[:,0].tolist(),max_detached_force_N=max_detached_force,
                  max_detached_torque_Nm=max_detached_torque,break_dwell_s=env.break_duration[:,0].tolist())
    report['passed']=(report['final_attached']==[True,True,False,False,False,True] and
        .17<report['detached_drop_0_2s_m']<.23 and -2.1<report['detached_velocity_0_2s_m_s']<-1.8
        and max_rebound<.01 and max_up_speed<.5 and max_detached_force==0. and max_detached_torque==0.)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('CONTACT_REGRESSION',json.dumps(report),flush=True)
    assert report['passed'],report
except Exception:
    import traceback
    traceback.print_exc();failed=True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app,env,failed)
