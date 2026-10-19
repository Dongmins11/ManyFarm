"""Learned grasp followed by physical Cartesian pull; no fruit forces or teleports."""
import json
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from harvest_rl.kinematics import ArmKinematics
from harvest_rl.settings import CACHE

@torch.inference_mode()
def evaluate(env,wrapped,policy,args,out,app):
    kin=ArmKinematics(CACHE/'harvest_training.urdf');reports=[]
    base_hold=env.settings.gripper_hold_error;base_max=env.settings.gripper_max_error
    for trial in range(args.episodes):
        env.settings.gripper_hold_error=base_hold;env.settings.gripper_max_error=base_max
        mode='policy' if args.probe_policy else args.probe_mode if args.probe_mode else 'command_pull' if args.probe_close else ('measured_hold','command_hold','command_pull')[trial%3]
        torch.manual_seed(args.seed+(trial if (args.probe_close or args.probe_policy) else 0));torch.cuda.manual_seed_all(args.seed+(trial if (args.probe_close or args.probe_policy) else 0))
        noise_rng=torch.Generator(device=env.device).manual_seed(args.seed+10000+trial)
        obs,_=wrapped.reset();trace=[];grasped=False;origin=None
        initial_position=env.fruits[0].data.root_link_pos_w[0].cpu().tolist()
        threshold=float(env.threshold[0,0])
        for step in range(round((args.probe_duration or env.settings.episode_s)/env.step_dt)):
            if not app.is_running():break
            if not grasped or args.probe_policy:
                action=policy(obs)
                if args.probe_policy and args.probe_noise_scale:
                    action=action+torch.randn(action.shape,device=env.device,generator=noise_rng)*args.probe_std*args.probe_noise_scale
            else:
                if args.probe_ramp:
                    from harvest_rl.logic import pull_squeeze_error
                    env.settings.gripper_hold_error=float(pull_squeeze_error(base_hold,env.grip_time,env.grip,env.has_grasped)[0])
                    env.settings.gripper_max_error=max(base_max,env.settings.gripper_hold_error)
                q=env.robot.data.joint_pos[0,env.jids].cpu().numpy().copy()
                xyz=kin.grasp_fk(q)[:3,3]
                target=origin.copy();target[0]-=min(.10,max(0.,(step-start)*env.step_dt-1.)*.015) if mode=='command_pull' else 0.
                if args.probe_recenter:
                    fruit_center=env._grasp_center(env._target_fruit())[0].cpu().numpy()
                    target[1:]=fruit_center[1:]-fruit_offset[1:]
                rotation=kin.grasp_fk(q)[:3,:3]
                jac=np.zeros((6,5))
                for j in range(5):
                    dq=q.copy();dq[j]+=1e-4
                    moved=kin.grasp_fk(dq)
                    jac[:3,j]=(moved[:3,3]-xyz)/1e-4
                    jac[3:,j]=.08*Rotation.from_matrix(moved[:3,:3]@rotation.T).as_rotvec()/1e-4
                error=np.r_[target-xyz,.08*Rotation.from_matrix(rest_rotation@rotation.T).as_rotvec()]
                delta=np.linalg.solve(jac.T@jac+.002**2*np.eye(5),jac.T@error)
                desired=held_command.copy()
                if mode=='measured_hold':desired[:5]=q[:5]
                elif mode=='command_pull' and (step-start)*env.step_dt>1.:
                    desired[:5]=env.targets[0,:5].cpu().numpy()+np.clip(delta,-.25*env.step_dt,.25*env.step_dt)
                    desired[:5]=np.clip(desired[:5],q[:5]-.08,q[:5]+.08)
                desired[5]=q[5]-.025
                speed=torch.tensor([env.settings.action_speed]*5+[env.settings.gripper_speed],device=env.device)
                action=((torch.tensor(desired,device=env.device)-env.targets)/(speed*env.step_dt)).clamp(-1,1).float()
            if grasped and args.probe_close and not args.probe_policy:action[:,-1]=-.1
            obs,_,_,_=wrapped.step(action)
            if not grasped and bool(env.has_grasped[0]):
                if args.probe_preload and not args.probe_ramp:
                    env.settings.gripper_hold_error=args.probe_preload
                    env.settings.gripper_max_error=max(base_max,args.probe_preload)
                held_command=env.targets[0].cpu().numpy().copy()
                rest_rotation=kin.grasp_fk(env.robot.data.joint_pos[0,env.jids].cpu().numpy())[:3,:3].copy()
                grasped=True;start=step;origin=kin.grasp_fk(env.robot.data.joint_pos[0,env.jids].cpu().numpy())[:3,3].copy()
            if grasped and step==start:
                fruit_offset=env._grasp_center(env._target_fruit())[0].cpu().numpy()-origin
            d=env.last_diagnostics
            trace_keys=['stem_load_N','stem_retreat_m','bilateral_contact','centered_grasp','fixed_force_N','moving_force_N','distance_m','valid_detach','detached_hold_s','success','failure','gripper_q_rad','gripper_target_rad','close_action','center_error_x_m','center_error_y_m','center_error_z_m']
            # One device synchronization for scalar diagnostics instead of one per key.
            values=torch.stack([d[k][0].float() for k in trace_keys]).cpu().tolist()
            trace.append(dict(step=step,after_grasp_s=(step-start)*env.step_dt if grasped else -1,
                              **dict(zip(trace_keys,values))))
            trace[-1]['squeeze_active']=bool(env.squeeze_active[0])
            trace[-1]['grip_hold_s']=float(env.grip_time[0])
            trace[-1]['joint_error_rad']=(env.targets[0]-env.robot.data.joint_pos[0,env.jids]).cpu().tolist()
            trace[-1]['joint_effort_Nm']=env.robot.data.applied_torque[0,env.jids].cpu().tolist()
            if grasped and not args.probe_policy:
                trace[-1]['tcp_tracking_error_m']=float(np.linalg.norm(target-kin.grasp_fk(env.robot.data.joint_pos[0,env.jids].cpu().numpy())[:3,3])) if step>start else 0.
            if bool(env.success[0]) or bool(env.failure[0]):break
        report=dict(torque_source='IsaacLab implicit actuator PD estimate; not measured PhysX drive torque',noise_scale=args.probe_noise_scale,trial=trial,seed=args.seed+trial,initial_position=initial_position,threshold_N=threshold,mode=mode,grasped=grasped,success=bool(env.success[0]),attached=bool(env.attached[0,0]),
                    peak_tension_N=max(x['stem_load_N'] for x in trace),trace=trace)
        reports.append(report);(out/('grasp_eval.json' if getattr(args,'grasp_eval',False) else 'pull_probe.json')).write_text(json.dumps(reports,indent=2))
        print('PULL_PROBE', {k:v for k,v in report.items() if k!='trace'},flush=True)
