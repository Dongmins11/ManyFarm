"""Fixed batch: no autoreset, all successes, failures and timeouts in denominator."""
import json
import torch
from harvest_rl.logic import above_box,placement_target

def evaluate(env,wrapped,policy,args,out):
    obs=wrapped.get_observations()
    n=env.num_envs;device=env.device
    active=torch.ones(n,dtype=torch.bool,device=device)
    success=torch.zeros_like(active);failure=success.clone()
    names=['zone','fruit_slow','tcp_slow','angular_slow','stable','all']
    counts={k:torch.zeros(n,device=device) for k in names};steps=torch.zeros(n,device=device)
    distances=torch.zeros(n,device=device);speeds=distances.clone();best=torch.full_like(distances,100.)
    previous=env._tcp()[0].clone()
    trace=[]
    failure_details={}
    release_details={}
    previous_grip=torch.zeros(n,dtype=torch.bool,device=device)
    opening=torch.zeros_like(active)
    bad=torch.zeros_like(active);valid=torch.zeros_like(active)
    grasp=torch.zeros_like(active);detach=torch.zeros_like(active)
    with torch.inference_mode():
        for i in range(min(args.steps,env.max_episode_length)):
            if hasattr(policy,'stage'):policy.active=active.clone()
            action=policy(obs) if args.stop_probe in ('policy','place-policy','harvest-policy') else torch.zeros(n,6,device=device)
            if args.stop_probe=='release':
                opening |= env.release_armed
                action[:,-1]=torch.where(opening,.15,0.)
            prior_intent=env.release_intent.clone();prior_armed=env.release_armed.clone()
            prior_age=env.release_intent_age.clone()
            obs,_,_,_=wrapped.step(action)
            f=env._target_fruit();tcp=env._tcp()[0];position=f.data.root_link_pos_w-env.scene.env_origins
            distance=(position-placement_target(env.settings,device)).norm(dim=-1)
            speed=f.data.root_com_lin_vel_w.norm(dim=-1)
            masks=dict(zone=above_box(position,f.data.root_link_quat_w,env.settings),fruit_slow=speed<=env.settings.release_speed,
                tcp_slow=(tcp-previous).norm(dim=-1)/env.step_dt<=env.settings.release_speed,
                angular_slow=env.stop_angular_slow,
                stable=env.grip & env.has_grasped & (env.slip<env.settings.max_slip))
            masks['all']=torch.stack(list(masks.values())).all(0)
            for k,v in masks.items():counts[k]+=active & v
            steps+=active;distances+=distance*active;speeds+=speed*active
            best=torch.where(active,torch.minimum(best,distance),best)
            for idx in (active & previous_grip & ~env.raw_grip & env.valid_detach).nonzero().flatten().tolist():
                release_details.setdefault(str(idx),[]).append(dict(step=i+1,stage=int(policy.stage[idx]) if hasattr(policy,'stage') else None,
                    position=position[idx].tolist(),velocity=f.data.root_com_lin_vel_w[idx].tolist(),
                    in_zone=bool(masks['zone'][idx]),gripper_q=float(env.robot.data.joint_pos[idx,env.jids[-1]])))
            previous_grip=env.raw_grip.clone()
            for idx in (active & env.failure).nonzero().flatten().tolist():
                failure_details[str(idx)]=dict(break_evidence=env.break_evidence[idx].tolist(),step=i+1,bad_release=bool(env.bad_release[idx]),
                    position=position[idx].tolist(),velocity=f.data.root_com_lin_vel_w[idx].tolist(),expert_stage=int(policy.stage[idx]) if hasattr(policy,"stage") else None,
                    reasons={k:float(v[idx]) for k,v in env.last_diagnostics.items() if k.startswith("failure_")},
                    detached=bool(env.valid_detach[idx]),retained=bool(env.has_retained[idx]),
                    gripper_action=float(action[idx,-1]),prior_intent=bool(prior_intent[idx]),
                    prior_armed=bool(prior_armed[idx]),prior_age=float(prior_age[idx]),
                    tcp_speed=float((tcp[idx]-previous[idx]).norm()/env.step_dt),
                    intent_tcp_displacement=float((tcp[idx]-env.release_intent_tcp[idx]).norm()) if prior_intent[idx] else None,
                    intent_arm_displacement=float((env.robot.data.joint_pos[idx,env.jids[:5]]-env.release_intent_arm[idx]).abs().max()) if prior_intent[idx] else None)
            if getattr(args,'trace_transition',False):
                trace.append({k:v.detach().cpu().clone() for k,v in dict(
                    active=active,stage=policy.stage,action=action,
                    q=env.robot.data.joint_pos[:,env.jids],qd=env.robot.data.joint_vel[:,env.jids],
                    targets=env.targets,fruit=position,quat=f.data.root_link_quat_w,velocity=f.data.root_com_lin_vel_w,
                    tcp=tcp-env.scene.env_origins,grip=env.raw_grip,slip=env.slip,
                    fixed_force=env.last_diagnostics['fixed_force_N'],moving_force=env.last_diagnostics['moving_force_N'],
                    center=env.distance,in_box=env.last_diagnostics['in_box'],place_time=env.place_time).items()})
            grasp |= active & env.has_grasped;detach |= active & env.valid_detach
            bad |= active & env.bad_release;valid |= active & env.valid_release
            success|=active & env.success;failure|=active & env.failure
            active &= ~(env.success|env.failure);previous=tcp.clone()
            if i%100==0:print('PROBE_PROGRESS',i,'success',int(success.sum()),'failure',int(failure.sum()),'remaining',int(active.sum()),flush=True)
            if not active.any():break
    report=dict(recovery_used=sorted(policy.recovery.used) if hasattr(policy,"recovery") else [],expert_stages=policy.stage.tolist() if hasattr(policy,'stage') else None,mode=args.stop_probe,checkpoint=str(args.checkpoint),environments=n,seed=args.seed,
      grasp=int(grasp.sum()),detach=int(detach.sum()),bad_release=int(bad.sum()),valid_release=int(valid.sum()),success=int(success.sum()),failure=int(failure.sum()),timeout=int(active.sum()),
      success_rate=float(success.float().mean()),physics_dt_s=env.physics_dt,control_dt_s=env.step_dt,
      mean_distance_m=float((distances/steps.clamp_min(1)).mean()),
      mean_speed_m_s=float((speeds/steps.clamp_min(1)).mean()),
      break_evidence_fields=["confirmed_grasp","qualified_contact","outward_extension_ok","center_error_m","fixed_contact_N","moving_contact_N"],
      release_details=release_details,failure_details=failure_details,step_gate_fraction={k:float(v.sum()/steps.sum().clamp_min(1)) for k,v in counts.items()},
      per_env=[dict(success=bool(success[i]),failure=bool(failure[i]),steps=int(steps[i]),best_distance_m=float(best[i]),
                    gates={k:float(v[i]/steps[i].clamp_min(1)) for k,v in counts.items()}) for i in range(n)])
    if trace:torch.save({k:torch.stack([r[k] for r in trace]) for k in trace[0]},out/'transition_trace.pt')
    (out/'stop_probe.json').write_text(json.dumps(report,indent=2))
    print('STOP_PROBE', {k:v for k,v in report.items() if k not in ('per_env','failure_details','release_details','expert_stages')},flush=True)
