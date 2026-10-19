"""Attached, physically certified grasp snapshots for a separate 60Hz pull task.

Only reset restores a measured state. Contact flags are always recomputed.
This format is deliberately incompatible with legacy detached stage banks.
"""
import hashlib
import json
from pathlib import Path
import torch

SCHEMA = 'attached_grasp_handoff_60hz_v1'
HISTORY = ('has_grasped', 'valid_detach', 'has_retained', 'grasp_relative',
           'grip_time', 'detached_time', 'squeeze_active', 'pull_start_x', 'entry_inside')
EXCLUDED = {'task', 'reward_version', 'seed', 'workspace_split', 'start_bank',
            'pull_direction_shaping', 'pull_recovery_shaping'}


def physical_signature(task):
    return {k:v for k,v in json.loads(json.dumps(task)).items() if k not in EXCLUDED}


def contract_digest(contract):
    return hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()


def certify(attached, qualified, confirmed, failed, dwell, required_dwell):
    return attached & qualified & confirmed & ~failed & (dwell >= required_dwell)


class GraspHandoffCollector:
    def __init__(self, run, contract, checkpoint, limit):
        self.limit, self.count, self.chunks, self.active = limit, 0, [], None
        self.metadata = dict(schema=SCHEMA, source_task='grasp', split=run['split'],domain_stage=run['domain_stage'],
            physics_hz=60, policy_hz=20, source_checkpoint=str(Path(checkpoint).resolve()),
            source_checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
            source_contract_sha256=contract_digest(contract), source_run=run,
            source_contract=contract, physical_signature=physical_signature(run['task']),
            certification='pre-auto-reset real qualified contact, confirmed >=250ms, attached, no failure')

    def begin_batch(self, num_envs, required, device):
        self.active = torch.arange(num_envs, device=device) < required

    def capture(self, env):
        if self.active is None or self.count >= self.limit:
            return
        valid = certify(env._t(env.attached), env.grip & env.raw_grip,
            env.has_grasped, env.failure, env.grip_time, env.settings.grip_hold_s)
        ids = (self.active & env.success & valid).nonzero().flatten()[:self.limit-self.count]
        terminal = env.success | env.failure | (env._target_elapsed_steps() >= env.max_episode_length-1)
        self.active &= ~terminal
        if not len(ids):
            return
        fruit = torch.stack([f.data.root_state_w[ids].clone() for f in env.fruits], 1)
        fruit[:, :, :3] -= env.scene.env_origins[ids, None, :]
        states = dict(q=env.robot.data.joint_pos[ids], qd=env.robot.data.joint_vel[ids],
            targets=env.targets[ids], fruits=fruit, rest_quat=env.rest_quat[ids],
            anchors=env.anchors[ids]-env.scene.env_origins[ids, None, :],
            attached=env.attached[ids], threshold=env.threshold[ids],
            break_timer=env.break_timer[ids],
            target_index=env.target_index[ids], color_ids=env.color_ids[ids],
            domain_samples=env.domain_samples[ids])
        states.update({name:getattr(env, name)[ids] for name in HISTORY})
        states['pull_start_x']=states['pull_start_x']-env.scene.env_origins[ids,0]
        self.chunks.append({name:v.detach().cpu().clone() for name,v in states.items()})
        self.count += len(ids)

    def save(self, path):
        if not self.count:
            raise RuntimeError('No physically certified attached grasps; no handoff bank created')
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            torch.save(dict(metadata=self.metadata, states={k:torch.cat([c[k] for c in self.chunks])
                for k in self.chunks[0]}), stream)
        print('GRASP_HANDOFF_SAVED', path, self.count, flush=True)


def validate_payload(payload, split=None):
    m, s = payload['metadata'], payload['states']
    if (m.get('schema') != SCHEMA or m.get('source_task') != 'grasp'
            or m.get('physics_hz') != 60 or m.get('policy_hz') != 20):
        raise ValueError('Requires a certified attached-grasp 60/20Hz bank')
    if split is not None and m['split'] != split:
        raise ValueError('Train/validation/test bank mismatch')
    if contract_digest(m['source_contract']) != m['source_contract_sha256']:
        raise ValueError('Handoff source contract changed')
    task=m['source_run']['task']
    if (task['task']!='grasp' or abs(task['physics_dt']-1/60)>1e-12
            or task['contact_substeps']!=1 or task['decimation']!=3):
        raise ValueError('Source task must actually use grasp at 60/20Hz')
    if physical_signature(m['source_contract']['task']) != physical_signature(task):
        raise ValueError('Source contract and recorded physics differ')
    n = len(s['target_index'])
    required = {'q','qd','targets','fruits','rest_quat','anchors','attached','threshold',
                'target_index','color_ids','domain_samples','break_timer',*HISTORY}
    if set(s) != required or n < 1 or any(len(v)!=n or not torch.isfinite(v).all() for v in s.values()):
        raise ValueError('Empty, inconsistent or nonfinite handoff states')
    shapes = {'targets':(n,6),'fruits':(n,2,13),'rest_quat':(n,2,4),
              'anchors':(n,2,3),'attached':(n,2),'threshold':(n,2),
              'color_ids':(n,2),'domain_samples':(n,6),'target_index':(n,), 'break_timer':(n,2),
              'grasp_relative':(n,3),'qd':tuple(s['q'].shape)}
    shapes.update({k:(n,) for k in HISTORY if k!='grasp_relative'})
    if s['q'].ndim!=2 or s['q'].shape[1]<6 or any(tuple(s[k].shape)!=shape for k,shape in shapes.items()):
        raise ValueError('Invalid handoff shapes')
    for k in ('attached','has_grasped','valid_detach','has_retained','squeeze_active','entry_inside'):
        if s[k].dtype!=torch.bool:raise ValueError('Handoff boolean flags must retain their type')
    if (not torch.allclose(s['fruits'][:,:,3:7].norm(dim=-1),torch.ones((n,2)),atol=1e-4)
            or not torch.allclose(s['rest_quat'].norm(dim=-1),torch.ones((n,2)),atol=1e-4)
            or (s['threshold']<=0).any() or (s['break_timer']<0).any()):
        raise ValueError('Invalid physical handoff quaternion/threshold/timer')
    index=s['target_index'].long()
    if ((index<0)|(index>=2)).any() or (s['target_index']!=index).any():
        raise ValueError('Invalid handoff target')
    row=torch.arange(n)
    if (not s['attached'].all() or not s['has_grasped'].all() or not s['entry_inside'].all()
            or s['valid_detach'].any() or s['has_retained'].any()
            or (s['grip_time'] < m['source_run']['task']['grip_hold_s']).any()
            or ((s['color_ids'][row,index]<0)|(s['color_ids'][row,index]>=2)).any()):
        raise ValueError('Uncertified attached/confirmed state')
    if physical_signature(m['source_run']['task']) != m['physical_signature']:
        raise ValueError('Handoff physics metadata changed')
    if m['domain_stage'] not in range(4) or (s['domain_samples'][:,-1]!=m['domain_stage']).any():
        raise ValueError('Handoff stage differs from actual sampled poses')
    return payload


class GraspHandoffBank:
    def __init__(self, path, split, device):
        payload=validate_payload(torch.load(path,map_location='cpu',weights_only=True),split)
        self.metadata=payload['metadata']; self.count=len(payload['states']['q'])
        self.states={k:v.to(device) for k,v in payload['states'].items()}
        self.sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def restore(self, env, ids):
        if physical_signature(env.settings.as_dict()) != self.metadata['physical_signature']:
            raise ValueError('Pull/probe physics differ from measured grasp bank')
        ix=torch.randint(self.count,(len(ids),),device=env.device)
        if not hasattr(env,'handoff_indices'):
            env.handoff_indices=torch.full((env.num_envs,),-1,device=env.device,dtype=torch.long)
        env.handoff_indices[ids]=ix
        b={k:v[ix] for k,v in self.states.items()}
        if b['q'].shape[1]!=env.robot.data.joint_pos.shape[1]:
            raise ValueError('Handoff robot joint count mismatch')
        env.robot.write_joint_state_to_sim(b['q'],b['qd'],env_ids=ids)
        env.targets[ids]=b['targets']
        env.robot.set_joint_position_target(b['targets'],joint_ids=env.jids,env_ids=ids)
        for k in ('attached','threshold','target_index','color_ids','rest_quat','domain_samples','break_timer',*HISTORY):
            getattr(env,k)[ids]=b[k]
        env.pull_start_x[ids]+=env.scene.env_origins[ids,0]
        env.anchors[ids]=b['anchors']+env.scene.env_origins[ids,None,:]
        states=b['fruits'].clone();states[:,:,:3]+=env.scene.env_origins[ids,None,:]
        for i,fruit in enumerate(env.fruits):
            fruit.write_root_state_to_sim(states[:,i],env_ids=ids);fruit.reset(ids)
            fruit.permanent_wrench_composer.reset()
        env.ripe[ids]=False;env.ripe[ids,env.target_index[ids]]=True
        env.raw_grip[ids]=False;env.grip[ids]=False  # Revalidate real contact after reset.
        env.easy_episode[ids]=True
        env._draw_stems()
