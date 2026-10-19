"""Measured-state hold/pull diagnostics. Commands move joints, never fruit bodies."""
import json
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from .kinematics import ArmKinematics
from .settings import CACHE

TRACE_KEYS=['distance_m','bilateral_contact','centered_grasp','fixed_force_N','moving_force_N',
            'stem_load_N','stem_extension_m','valid_detach','has_retained','detached_hold_s',
            'attached','success','failure','gripper_q_rad','gripper_target_rad',
            'qualified_grasp','slip_m','gripper_velocity_rad_s','jaw_target_held',
            'automatic_jaw_target_rad','arm_target_error_max_rad','arm_velocity_max_rad_s',
            'grasp_orientation_required','grasp_orientation_ok',
            'tcp_x_m','tcp_y_m','tcp_z_m',
            *[f'arm_q_{j}_rad' for j in range(5)],
            *[f'arm_target_{j}_rad' for j in range(5)]]


def cartesian_pull_action(kin, q, target, origin_pose, targets, cfg):
    pose=kin.grasp_fk(q,cfg.diameter);jac=np.zeros((6,5))
    for j in range(5):
        dq=q.copy();dq[j]+=1e-4
        moved=kin.grasp_fk(dq,cfg.diameter)
        jac[:3,j]=(moved[:3,3]-pose[:3,3])/1e-4
        jac[3:,j]=.08*Rotation.from_matrix(moved[:3,:3]@pose[:3,:3].T).as_rotvec()/1e-4
    error=np.r_[target-pose[:3,3],.08*Rotation.from_matrix(origin_pose[:3,:3]@pose[:3,:3].T).as_rotvec()]
    delta=np.linalg.solve(jac.T@jac+.002**2*np.eye(5),jac.T@error)
    desired=targets[:5]+np.clip(delta,-.25*cfg.step_dt,.25*cfg.step_dt)
    desired=np.clip(desired,q[:5]-.08,q[:5]+.08)
    a=np.zeros(6);a[:5]=np.clip((desired-targets[:5])/(cfg.action_speed*cfg.step_dt),-1,1)
    return a


@torch.inference_mode()
def probe(env, wrapped, mode, duration, out, metadata, seed):
    from types import SimpleNamespace
    kin=ArmKinematics(CACHE/'harvest_training.urdf');wrapped.reset()
    cfg=SimpleNamespace(**env.settings.as_dict(),step_dt=env.step_dt)
    q=env.robot.data.joint_pos[:,env.jids].cpu().numpy()
    origin=[kin.grasp_fk(row,cfg.diameter) for row in q]
    tcp=(env._tcp()[0]-env.scene.env_origins).cpu().numpy()
    initial=dict(bank_state_indices=env.handoff_indices.cpu().tolist(),
        joint_q_rad=q.tolist(),joint_velocity_rad_s=env.robot.data.joint_vel[:,env.jids].cpu().tolist(),
        joint_targets_rad=env.targets.cpu().tolist(),tcp_m=tcp.tolist(),
        fruit_states_local=[torch.cat((f.data.root_state_w[:,:3]-env.scene.env_origins,
            f.data.root_state_w[:,3:]),-1).cpu().tolist() for f in env.fruits],
        meaning='After reset, before any probe physics step; contacts have not yet been rechecked.')
    with (out/'initial_state.json').open('x') as stream:json.dump(initial,stream,indent=2)
    fk_error=np.linalg.norm(tcp-np.array([t[:3,3] for t in origin]),axis=-1)
    if np.max(fk_error)>.005:
        raise ValueError(f'Cached FK/actual TCP disagree ({np.max(fk_error):.4f}m); no pull command issued')
    completed={};traces=[[] for _ in range(env.num_envs)];continuous=torch.zeros(env.num_envs,device=env.device)
    ever_bad=torch.zeros(env.num_envs,device=env.device,dtype=torch.bool)
    first_bad=[None]*env.num_envs
    qualification_reasons=[set() for _ in range(env.num_envs)]
    total_steps=round(duration/env.step_dt)
    with (out/'trace.jsonl').open('x') as stream:
        for step in range(total_steps):
            actions=torch.zeros((env.num_envs,6),device=env.device)
            if mode=='pull-probe' and step*env.step_dt>=1.:
                measured=env.robot.data.joint_pos[:,env.jids].cpu().numpy()
                command=env.targets.cpu().numpy()
                detached=~env._t(env.attached)
                for i in range(env.num_envs):
                    if i in completed or bool(detached[i]):continue
                    target=origin[i][:3,3].copy()
                    target[0]-=min(.10,(step*env.step_dt-1.)*.015)
                    actions[i]=torch.tensor(cartesian_pull_action(kin,measured[i],target,origin[i],command[i],cfg),device=env.device)
            _,_,_,_=wrapped.step(actions)
            snap=env.followup_snapshot
            stable=snap['qualified'] & (snap['slip']<cfg.max_slip)
            if mode=='hold':stable &= snap['attached']
            continuous=torch.where(stable,continuous+env.step_dt,torch.zeros_like(continuous))
            ever_bad |= ~stable
            values=torch.stack([snap['diagnostics'][k].float() for k in TRACE_KEYS],-1).cpu().tolist()
            active=[i for i in range(env.num_envs) if i not in completed]
            stream.write(json.dumps(dict(step=step,time_s=(step+1)*env.step_dt,
                env_ids=active,columns=TRACE_KEYS,rows=[values[i] for i in active]))+'\n')
            for i in active:
                traces[i].append(values[i])
                if not bool(stable[i]):
                    if first_bad[i] is None:first_bad[i]=(step+1)*env.step_dt
                    d=snap['diagnostics']
                    if not bool(d['bilateral_contact'][i]):qualification_reasons[i].add('contact_lost')
                    if float(d['distance_m'][i])>cfg.grasp_center_tolerance:qualification_reasons[i].add('offcenter')
                    if float(snap['slip'][i])>=cfg.max_slip:qualification_reasons[i].add('slip')
                    if not bool(snap['attached'][i]) and mode=='hold':qualification_reasons[i].add('detached')
                    if not bool(snap['qualified'][i]) and not qualification_reasons[i]:qualification_reasons[i].add('other_qualification')
                if bool(snap['failure'][i]) or bool(snap['success'][i]) or step==total_steps-1:
                    passed=(not bool(snap['failure'][i]) and
                        (not bool(ever_bad[i]) if mode=='hold' else bool(snap['success'][i])))
                    completed[i]=dict(env_id=i,passed=passed,
                        failure=bool(snap['failure'][i]),valid_detach=bool(snap['valid_detach'][i]),
                        retained=bool(snap['retained'][i]),attached=bool(snap['attached'][i]),
                        last_continuous_contact_s=float(continuous[i]),
                        first_unstable_s=first_bad[i],qualification_failures=sorted(qualification_reasons[i]),
                        peak_stem_load_N=max(r[TRACE_KEYS.index('stem_load_N')] for r in traces[i]),
                        bank_state_index=int(snap['bank_indices'][i]),
                        reasons=[k for k,v in snap['diagnostics'].items() if k.startswith('failure_') and bool(v[i])])
            if step%5==0 or step==total_steps-1:print('FOLLOWUP_PROBE',mode,'step',step,'completed',len(completed),
                'currently_stable',int(stable.sum()),
                'passed',sum(r['passed'] for r in completed.values()),flush=True)
            if len(completed)==env.num_envs:break
    report=dict(mode=mode,learning=False,physics_hz=60,policy_hz=20,split=metadata['split'],
        probe_bank_sha256=metadata['probe_bank_sha256'],domain_stage=metadata['domain_stage'],
        source_grasp_sha256=metadata['source_checkpoint_sha256'],
        source_grasp_contract_sha256=metadata['source_contract_sha256'],
        followup_contract_sha256=metadata['followup_contract_sha256'],
        maintenance=metadata['maintenance'],bank_assignment_sha256=metadata['bank_assignment_sha256'],
        physical_signature=metadata['physical_signature'],duration_s=duration,seed=seed,
        episodes=[completed[i] for i in sorted(completed)],
        unique_bank_states_tested=len({r['bank_state_index'] for r in completed.values()}),
        meaning='Reset measured attached grasp; real contacts rechecked. Hold has no extra external load. Pull uses 15mm/s joint-driven retreat; no fruit force/teleport.',
        fk_error_m=fk_error.tolist())
    (out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print('FOLLOWUP_PROBE_COMPLETE',mode,'passed',sum(r['passed'] for r in completed.values()),'of',len(completed),flush=True)
    return report
