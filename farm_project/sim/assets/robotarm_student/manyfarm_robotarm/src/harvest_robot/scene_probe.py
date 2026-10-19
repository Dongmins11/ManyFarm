"""Native attachment + sequential scene regression fixture (not a trained policy evaluation)."""
import argparse
import json
from pathlib import Path
from isaaclab.app import AppLauncher

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output",type=Path,default=Path("outputs/harvest_rl/scene_probe"))
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args()
args.kit_args=(args.kit_args or "")+" --/plugins/carb.tasking.plugin/threadCount=1"
app=AppLauncher(args).app
failed=False
try:
    import torch
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    class Probe(HarvestEnv):
        def _apply_action(self):
            super()._apply_action()
            if hasattr(self,"probe_force"):
                for i,fruit in enumerate(self.fruits):
                    fruit.instantaneous_wrench_composer.set_forces_and_torques(forces=self.probe_force[:,i,None,:],is_global=True)
        def _get_dones(self):
            self._update_task()
            return torch.zeros_like(self.success),torch.zeros_like(self.success)
    env=Probe(TaskSettings(task="harvest",attachment_version=3,sequence=True,random_colors=False,num_fruits=3,background="grove",episode_s=60),num_envs=2,device=args.device,cameras=args.enable_cameras,render_mode="rgb_array" if args.enable_cameras else None)
    env.reset()
    origin=env.scene.env_origins[0].cpu().numpy()
    env.sim.set_camera_view(eye=origin+[1.8,-2.,1.65],target=origin+[.35,-.1,.8])
    action=torch.zeros(2,6,device=env.device)
    env.probe_force=torch.zeros(2,3,3,device=env.device)
    report={"colors":env.fruit_colors,"thresholds":env.threshold.tolist()}
    def step(n):
        for _ in range(n):env.step(action)
    step(12)
    if args.enable_cameras:
        from PIL import Image
        args.output.mkdir(parents=True,exist_ok=True)
        env.render()
        for _ in range(8):env.sim.render()
        Image.fromarray(env.render()).save(args.output/"initial_overview.png")
        Image.fromarray(env.camera.data.output["rgb"][0,:,:,:3].cpu().numpy()).save(args.output/"initial_wrist.png")
    report["gravity_attached"]=env.attached.tolist()
    env.probe_force[:,:,0]=.5
    step(12)
    report["below_threshold_attached"]=env.attached.tolist()
    from isaaclab.utils.math import quat_apply
    error=[]
    for i,fruit in enumerate(env.fruits):
        tip=torch.tensor(env.tips_np[i],dtype=torch.float32,device=env.device).expand(env.num_envs,-1)
        error.append((fruit.data.root_link_pos_w+quat_apply(fruit.data.root_link_quat_w,tip)-env.anchors[:,i]).norm(dim=-1))
    report["joint_anchor_error_m"]=float(torch.stack(error).max())
    env.probe_force[0,0,0]=6.
    step(8)
    report["above_threshold_attached"]=env.attached.tolist()
    env.probe_force.zero_()
    env.reset()
    step(12)
    report["reset_reattached"]=env.attached.tolist()
    env.probe_force[0,2,0]=6.
    step(8)
    report["green_break_failure"]=bool(env.failure[0]) and not bool(env.attached[0,2])
    # Controlled state-machine fixture: place first ripe fruit, keep green protected,
    # advance without resetting robot/other fruits, then place the second ripe fruit.
    env.probe_force.zero_();env.reset();step(4)
    from pxr import UsdPhysics
    def fixture_place():
        # Inject prerequisites to test transitions independently of learned control.
        target=env.target_index.clone()
        for e in range(2):
            i=int(target[e])
            joint=UsdPhysics.Joint.Get(env.sim.stage,f"/World/envs/env_{e}/StemJoint_{i}")
            joint.CreateJointEnabledAttr().Set(False)
            fruit=env.fruits[i];state=fruit.data.root_state_w[e:e+1].clone()
            state[:,:3]=torch.tensor([.36 if i==0 else .44,0.,.542],device=env.device)+env.scene.env_origins[e]
            state[:,3:7]=torch.tensor([1.,0,0,0],device=env.device);state[:,7:]=0
            fruit.write_root_state_to_sim(state,env_ids=torch.tensor([e],device=env.device))
            env.attached[e,i]=False
        env.valid_detach[:]=True;env.has_retained[:]=True;env.valid_release[:]=True
        env.bad_release[:]=False
        step(30)
        return target.tolist()
    first=fixture_place()
    report["after_first_collected"]=env.collected.tolist()
    report["second_target"]=env.target_index.tolist()
    report["next_fruit_still_attached"]=env._t(env.attached).tolist()
    report["first_targets"]=first
    fixture_place()
    report["all_ripe_success"]=env.success.tolist()
    report["green_still_attached"]=env.attached[:,2].tolist()
    if args.enable_cameras:
        from PIL import Image
        args.output.mkdir(parents=True,exist_ok=True)
        for _ in range(8):env.sim.render()
        env.render()
        for _ in range(8):env.sim.render()
        Image.fromarray(env.render()).save(args.output/"overview.png")
        Image.fromarray(env.camera.data.output["rgb"][0,:,:,:3].cpu().numpy()).save(args.output/"wrist.png")
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)
    assert all(all(v) for v in report["gravity_attached"])
    assert all(all(v) for v in report["below_threshold_attached"])
    assert report["joint_anchor_error_m"] < .005
    assert not report["above_threshold_attached"][0][0]
    assert all(report["above_threshold_attached"][1])
    assert all(all(v) for v in report["reset_reattached"])
    assert report["green_break_failure"]
    assert all(sum(row)==1 for row in report["after_first_collected"])
    assert all(report["next_fruit_still_attached"])
    assert all(report["all_ripe_success"])
    assert all(report["green_still_attached"])
except Exception:
    import traceback
    traceback.print_exc()
    failed=True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app,locals().get("env"),failed)
