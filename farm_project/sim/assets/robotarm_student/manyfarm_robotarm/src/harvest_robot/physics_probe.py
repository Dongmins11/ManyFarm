"""Physical fixtures, NOT policy evaluation: fit/grasp, pulling, reset, settling.

The fruit is deliberately placed between the fingers in this fixture.
The optional training curriculum also starts near the open grasp pocket at reset;
no within-episode grasp teleport or weld exists.
"""
import argparse
import json
import sys
import traceback
from pathlib import Path
from isaaclab.app import AppLauncher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("outputs/harvest_rl/physics_probe.json"))
    parser.add_argument("--diameter",type=float,default=.070)
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--require-scripted-pull",action="store_true",
                        help="Also require the diagnostic IK pull to detach and keep holding")
    parser.add_argument("--require-loaded-hold",action="store_true",
                        help="Also fail unless the loaded holding fixture passes")
    AppLauncher.add_app_launcher_args(parser)
    args=parser.parse_args()
    app=AppLauncher(args).app
    env=None
    failed=False
    try:
        import numpy as np
        import torch
        from harvest_rl.env import HarvestEnv
        from harvest_rl.settings import TaskSettings
        from harvest_rl.kinematics import ArmKinematics
        from isaaclab.utils.math import quat_apply

        class ProbeEnv(HarvestEnv):
            def _apply_action(self):
                super()._apply_action()
                if getattr(self,"test_force",None) is not None:
                    self.fruits[0].instantaneous_wrench_composer.set_forces_and_torques(
                        forces=self.test_force,is_global=True)

            def _get_dones(self):
                self._update_task()
                # Keep fixture observable instead of autoresetting at first success/failure.
                return torch.zeros_like(self.success),torch.zeros_like(self.success)

        env=ProbeEnv(TaskSettings(task="harvest",episode_s=120,diameter=args.diameter,seed=args.seed,
                                 length=args.diameter*.075/.070),num_envs=1,device=args.device)
        env.reset()
        zero=torch.zeros(1,6,device=env.device)
        for _ in range(40):
            env.step(zero)
        report={"zero_action_attached":bool(env.attached.all()),
            "material_colliders":env.material_colliders,
            "settings":env.settings.as_dict(),
            "home_arm_contact_N":float(env.arm_contact.data.net_forces_w.norm(dim=-1).max()),
            "joints":env.robot.joint_names}
        # Dedicated extended fixture posture has enough joint-limit margin for a
        # straight pull. It is not an assertion that every sampled pose does.
        fixture_q=torch.tensor([[0.,-.97,.68,.29,-1.522,1.1]],device=env.device)
        all_q=env.robot.data.joint_pos.clone()
        all_q[:,env.jids]=fixture_q
        env.robot.write_joint_state_to_sim(all_q,torch.zeros_like(all_q))
        env.targets[:]=fixture_q
        for _ in range(20):
            env.step(zero)
        report["fixture_joint_pose"]=fixture_q[0].tolist()
        fruit=env.fruits[0]
        tcp,quat=env._tcp()
        # Upright fruit, exactly as in training resets (not aligned to a tilted wrist).
        quat=torch.tensor([[1.,0.,0.,0.]],device=env.device)
        state=fruit.data.root_state_w.clone()
        state[:,:3]=tcp
        state[:,3:7]=quat
        state[:,7:]=0
        fruit.write_root_state_to_sim(state)
        fruit.reset()
        env.rest_quat[:,0]=quat
        env.anchors[:,0]=tcp+quat_apply(quat,env.tip)
        env.attached[:]=True
        env.break_timer.zero_()
        env.has_grasped.zero_()
        env.grip_time.zero_()
        env.valid_detach.zero_()
        env.scene.write_data_to_sim()
        env.sim.forward()
        close=zero.clone();close[:,-1]=-.25
        samples=[]
        for step in range(50):
            env.step(close)
            if step%5==0:
                samples.append({"step":step,"grip":bool(env.grip[0]),
                    "attached":bool(env.attached[0,0]),"distance":float(env.distance[0]),
                    "finger_forces": [env.fixed_contact.data.force_matrix_w[0,0,0].tolist(),
                                      env.moving_contact.data.force_matrix_w[0,0,0].tolist()],
                    "gripper_q":float(env.robot.data.joint_pos[0,env.jids[-1]])})
            if env.has_grasped[0] and env.grip[0]:
                # Stop integrating a squeeze command after grasp. Hold a small
                # compliant position error instead of driving through the object.
                env.targets[:,-1]=env.robot.data.joint_pos[:,env.jids[-1]]-env.settings.gripper_hold_error
                close[:,-1]=0
                break
        report["grasp_samples"]=samples
        report["grasp_confirmed"]=bool(env.has_grasped[0])
        env.settings.task="hold"
        loaded_failure=False
        for _ in range(25):
            env.step(zero)
            loaded_failure |= bool(env.failure[0])
        report["loaded_hold_pass"]=bool(env.success[0]) and not loaded_failure
        report["loaded_hold_s"]=float(env.loaded_time[0])
        report["loaded_slip_m"]=float(env.slip[0])
        env.settings.task="harvest"
        kin=ArmKinematics()
        from harvest_rl.reference import pull_waypoint, solve_pull_ik
        initial_q=env.robot.data.joint_pos[0,env.jids].cpu().numpy()
        initial_pose=kin.grasp_fk(initial_q,env.settings.diameter)
        pull_samples=[]
        pull_failure=False
        for step in range(160):
            q=env.robot.data.joint_pos[0,env.jids].cpu().numpy()
            desired=pull_waypoint(initial_pose,(step+1)/160)
            solution,ik_error=solve_pull_ik(kin,q,initial_pose,desired,env.settings.diameter)
            action=close.clone()
            dq=solution-env.targets[0,:5].cpu().numpy()
            action[0,:5]=torch.tensor(dq/(env.settings.action_speed*env.step_dt),device=env.device).clamp(-1,1)
            env.step(action)
            pull_failure |= bool(env.failure[0])
            if step%5==0:
                pull_samples.append({"step":step,"grip":bool(env.grip[0]),"attached":bool(env.attached[0,0]),
                    "load":float(env.load[0,0]),"valid":bool(env.valid_detach[0]),"distance":float(env.distance[0]),
                    "slip_m":float(env.slip[0]),"ik_error_m":ik_error,
                    "gripper_q":float(env.robot.data.joint_pos[0,env.jids[-1]])})
            if not env.attached[0,0]:
                break
        for _ in range(20):
            env.step(close)
            pull_failure |= bool(env.failure[0])
        report["pull_samples"]=pull_samples
        report["pull_detached"]=not bool(env.attached[0,0])
        report["pull_valid"]=bool(env.valid_detach[0])
        report["break_displacement"]=env.break_displacement[0,0].tolist()
        report["pull_still_gripped"]=bool(env.grip[0])
        report["detached_hold_s"]=float(env.detached_time[0])
        report["pull_failure_seen"]=pull_failure
        report["scripted_pull_gate"]=(report["pull_valid"] and report["pull_still_gripped"]
            and float(env.detached_time[0]) >= env.settings.detached_hold_s and not pull_failure)
        # Free fall away from robot/tree: simulation-time check, independent of UI FPS.
        env.reset()
        state=fruit.data.root_state_w.clone()
        state[:,:3]=torch.tensor([-.8,-.8,1.5],device=env.device)+env.scene.env_origins
        state[:,7:]=0
        fruit.write_root_state_to_sim(state); fruit.reset()
        env.attached[:]=False
        for _ in range(4):
            env.step(zero)
        fall=1.5-float((fruit.data.root_link_pos_w-env.scene.env_origins)[0,2])
        vz=float(fruit.data.root_com_lin_vel_w[0,2])
        report["free_fall_0_2s"]={"drop_m":fall,"vz_m_s":vz}
        report["free_fall_pass"]=abs(fall-.5*9.81*.2**2)<.02 and abs(vz+9.81*.2)<.15
        # Force-injection fixture independently proves the dynamic break mechanism
        # and verifies that knocking a fruit off without grasping earns no credit.
        env.reset()
        env.test_force=torch.tensor([[[-4.,0.,0.]]],device=env.device)
        for _ in range(12):
            env.step(zero)
        report["force_injection_detached"]=not bool(env.attached[0,0])
        report["ungrasped_detach_not_credited"]=not bool(env.valid_detach[0]) and bool(env.failure[0])
        env.test_force=None
        # Independent box geometry/settling fixture, not counted as learned success.
        env.reset()
        state=fruit.data.root_state_w.clone()
        state[:,:3]=torch.tensor([.4,0.,.80],device=env.device)+env.scene.env_origins
        state[:,3:7]=torch.tensor([1.,0.,0.,0.],device=env.device)
        state[:,7:]=0
        fruit.write_root_state_to_sim(state)
        fruit.reset()
        env.attached[:]=False
        env.has_grasped[:]=True
        env.valid_detach[:]=True
        env.has_retained[:]=True  # Independent settling fixture, not learned carry evidence.
        for _ in range(80):
            env.step(zero)
        report["box_settled_pos"]=(fruit.data.root_link_pos_w-env.scene.env_origins)[0].tolist()
        report["box_containment_success"]=bool(env.success[0])
        env.reset()
        report["reset_reattached"]=bool(env.attached.all()) and not bool(env.valid_detach.any())
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2),flush=True)
        required=("zero_action_attached","grasp_confirmed","force_injection_detached",
                  "ungrasped_detach_not_credited","box_containment_success","reset_reattached","free_fall_pass")
        if args.require_scripted_pull:
            required += ("scripted_pull_gate",)
        if args.require_loaded_hold:
            required += ("loaded_hold_pass",)
        failed=[key for key in required if not report[key]]
        if failed:
            raise AssertionError(f"Physical fixture checks failed: {failed}; see {args.output}")
    except Exception:
        failed=True
        traceback.print_exc()
        sys.stderr.flush()
        raise
    finally:
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)


if __name__=="__main__":
    main()
