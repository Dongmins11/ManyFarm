"""Certified physical snapshots from successful predecessor-policy rollouts.

These are measured states, not artificial hand welds or arbitrary success flags.
Restoration is still subject to subsequent physical contact/failure checks.
"""
import hashlib
import json
from pathlib import Path
import torch
from .settings import CACHE

PHYSICS_FIELDS=('attachment_version','num_fruits','diameter','length','mass','grip_friction',
    'dynamic_friction','gripper_effort','physics_dt','decimation','break_force','grasp_center_tolerance',
    'max_slip','region_origin','region_min','region_max','box_min','box_max','stage_transfer')
CONTACT_DEFAULTS={'fruit_collision_mode':'legacy','gripper_stiffness':8.0,'gripper_damping':.3,'contact_stiffness':0.,'contact_damping':0.}
HISTORY=('has_grasped','valid_detach','has_retained','grasp_relative','grip_time','detached_time','squeeze_active')

def signature(settings):
    # JSON canonicalization makes tuple/list representations identical.
    return json.loads(json.dumps({k:getattr(settings,k) for k in (*PHYSICS_FIELDS,*CONTACT_DEFAULTS)}))

def select_start_indices(states,settings):
    """Select measured fruit-root distance; never modify physical poses."""
    from .logic import placement_target, above_box
    rows=torch.arange(len(states['target_index']))
    positions=states['fruits'][rows,states['target_index'],:3]
    distance=(positions-placement_target(settings,'cpu')).norm(dim=-1)
    selected=torch.ones(len(rows),dtype=torch.bool)
    if settings.transport_start_max:
        selected=(distance>=settings.transport_start_min)&(distance<=settings.transport_start_max)
        # Already in the stop zone would reward standing still instead of transport.
        selected &= ~above_box(positions,states['fruits'][rows,states['target_index'],3:7],settings)
    indices=selected.nonzero().flatten()
    if not len(indices):
        raise ValueError('No physical start states in requested distance range; build curriculum bank first')
    return indices,distance

class StageBankCollector:
    def __init__(self, settings, checkpoint, limit):
        if settings.task not in ('pull','transport') or limit < 1:
            raise ValueError('Collect successful pull or transport states only')
        self.limit=limit;self.count=0;self.chunks=[]
        self.metadata={'version':1,'source_task':settings.task,'workspace_split':settings.workspace_split,
            'physics':signature(settings),'asset':json.loads((CACHE/'preparation.json').read_text()),
            'connector':{k:getattr(settings,k) for k in ('stem_response_version','spring_k','spring_d','stem_max_extension','tension_hold_s','pull_squeeze_ramp','pull_squeeze_rearm')},
            'checkpoint':str(Path(checkpoint).resolve()),
            'integration':dict(contact_substeps=settings.contact_substeps),
            'checkpoint_sha256':hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()}

    def capture(self, env, ids, require_success=True):
        if self.count >= self.limit or not len(ids):return
        self.metadata['robot_usd_sha256']=hashlib.sha256(Path(env.robot_usd).read_bytes()).hexdigest()
        certified=(~env.failure[ids] & env.grip[ids] & env.has_retained[ids]
                   & env.valid_detach[ids] & ~env._t(env.attached)[ids] & (env.slip[ids]<env.settings.max_slip))
        if require_success:
            certified &= env.success[ids]
        ids=ids[certified][:self.limit-self.count]
        if not len(ids):return
        state=torch.stack([f.data.root_state_w[ids].clone() for f in env.fruits],1)
        state[:,:,:3]-=env.scene.env_origins[ids,None,:]
        data={'q':env.robot.data.joint_pos[ids], 'qd':env.robot.data.joint_vel[ids],
              'targets':env.targets[ids], 'fruits':state,
              'anchors':env.anchors[ids]-env.scene.env_origins[ids,None,:],
              'attached':env.attached[ids],'threshold':env.threshold[ids],
              'target_index':env.target_index[ids],'color_ids':env.color_ids[ids]}
        data.update({k:getattr(env,k)[ids] for k in HISTORY})
        self.chunks.append({k:v.detach().cpu().clone() for k,v in data.items()});self.count+=len(ids)

    def save(self,path):
        if not self.count:raise RuntimeError('No physically certified start states collected')
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as handle:
            torch.save({'metadata':self.metadata,'states':{k:torch.cat([c[k] for c in self.chunks])
                       for k in self.chunks[0]}},handle)
        print('STAGE_BANK_SAVED',path,self.count,flush=True)

class StageStartBank:
    def __init__(self,path,settings,device):
        payload=torch.load(path,map_location='cpu',weights_only=True)
        m=payload['metadata'];expected={'transport':'pull','place':'transport'}.get(settings.task)
        if m.get('version')!=1 or m['source_task']!=expected:
            raise ValueError('Start bank predecessor does not match task')
        if m['workspace_split']!=settings.workspace_split:
            raise ValueError('Train/eval bank mismatch: collect a separate bank for this split')
        if settings.attachment_version==4 and m.get('connector')!={k:getattr(settings,k) for k in ('stem_response_version','spring_k','spring_d','stem_max_extension','tension_hold_s','pull_squeeze_ramp','pull_squeeze_rearm')}:
            raise ValueError('Start bank connector/controller differs or is uncertified')
        if 'integration' in m and m['integration']!={'contact_substeps':settings.contact_substeps}:
            raise ValueError('Start bank integration settings differ')
        # Missing fields in old banks mean the unchanged historical contact model.
        if {**CONTACT_DEFAULTS,**m['physics']}!=signature(settings):raise ValueError('Start bank physical settings differ')
        prep=json.loads((CACHE/'preparation.json').read_text())
        if any(m['asset'].get(k)!=prep.get(k) for k in ('sha256','workspace_sha256')):
            raise ValueError('Start bank robot/workspace mismatch')
        self.robot_usd_sha256=m.get('robot_usd_sha256')
        states=payload['states']
        required={'q','qd','targets','fruits','anchors','attached','threshold','target_index','color_ids',*HISTORY}
        if set(states)!=required:raise ValueError('Invalid stage bank fields')
        n=len(states['q']);f=settings.num_fruits
        shapes={'qd':states['q'].shape,'targets':(n,6),'fruits':(n,f,13),'anchors':(n,f,3),
                'attached':(n,f),'threshold':(n,f),'target_index':(n,),'color_ids':(n,f),
                'grasp_relative':(n,3)}
        shapes.update({k:(n,) for k in HISTORY if k!='grasp_relative'})
        if any(tuple(states[k].shape)!=tuple(shape) for k,shape in shapes.items()):raise ValueError('Invalid stage bank shapes')
        if ((states['target_index']<0)|(states['target_index']>=f)).any():raise ValueError('Invalid bank target index')
        if not n or any(len(v)!=n or not torch.isfinite(v).all() for v in states.values()):
            raise ValueError('Empty, inconsistent or nonfinite start bank')
        rows=torch.arange(n);targets=states['target_index']
        if states['attached'][rows,targets].any() or not all(states[k].all() for k in ('has_grasped','valid_detach','has_retained')):
            raise ValueError('Uncertified detached/retained state')
        if (states['color_ids'][rows,targets]==2).any():raise ValueError('Green target in start bank')
        self.states={k:v.to(device) for k,v in states.items()};self.count=n
        self.indices,distance=select_start_indices(states,settings)
        self.indices=self.indices.to(device)
        selected=distance[self.indices.cpu()]
        print("STAGE_BANK_RANGE",len(self.indices),"of",n,"distance_m",float(selected.min()),float(selected.max()),flush=True)
        self.distance=distance.to(device)
        self.replay_fraction=settings.transport_replay_fraction
        self.replay_indices=None
        if self.replay_fraction:
            from dataclasses import replace
            replay_settings=replace(settings,transport_start_min=.03,transport_start_max=settings.transport_start_min)
            self.replay_indices,_=select_start_indices(states,replay_settings)
            self.replay_indices=self.replay_indices.to(device)
            print('STAGE_BANK_REPLAY',len(self.replay_indices),'fraction',self.replay_fraction,flush=True)
        self.sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def sample_indices(self,ids):
        index=self.indices[torch.randint(len(self.indices),(len(ids),),device=ids.device)]
        if self.replay_fraction:
            replay=torch.rand(len(ids),device=ids.device)<self.replay_fraction
            extra=self.replay_indices[torch.randint(len(self.replay_indices),(len(ids),),device=ids.device)]
            index=torch.where(replay,extra,index)
        return index

    def restore(self,env,ids):
        index=self.sample_indices(ids)
        b={k:v[index] for k,v in self.states.items()}
        if b['q'].shape[1]!=env.robot.data.joint_pos.shape[1]:raise ValueError('Bank robot joint count mismatch')
        env.robot.write_joint_state_to_sim(b['q'],b['qd'],env_ids=ids)
        env.targets[ids]=b['targets'];env.robot.set_joint_position_target(b['targets'],joint_ids=env.jids,env_ids=ids)
        for k in ('attached','threshold','target_index','color_ids',*HISTORY):getattr(env,k)[ids]=b[k]
        env.transport_replay[ids]=self.distance[index]<env.settings.transport_start_min
        env.easy_episode[ids]=True  # Bank resets must not be reported as HOME starts.
        env.ripe[ids]=b['color_ids']!=2
        env.anchors[ids]=b['anchors']+env.scene.env_origins[ids,None,:]
        states=b['fruits'].clone();states[:,:,:3]+=env.scene.env_origins[ids,None,:]
        for i,fruit in enumerate(env.fruits):
            fruit.write_root_state_to_sim(states[:,i],env_ids=ids);fruit.reset(ids)
            env.rest_quat[ids,i]=states[:,i,3:7]
        if hasattr(env,'raw_grip'):env.raw_grip[ids]=False
        if env.joint_attachments is not None:
            env.joint_attachments.reset(ids.tolist(),env.anchors[ids].cpu().tolist(),
                [v.tolist() for v in env.tips_np],env.threshold[ids].cpu().tolist(),
                root_states=states.cpu().tolist(),attached=b['attached'].cpu().tolist())
        if not env.visual_updates:
            return
        from pxr import UsdGeom
        for row,e in enumerate(ids.tolist()):
            for i,color in enumerate(b['color_ids'][row].tolist()):
                for code,name in enumerate(('Red','Yellow','Green')):
                    visual=UsdGeom.Imageable(env.sim.stage.GetPrimAtPath(f'/World/envs/env_{e}/Fruit_{i}/Visual_{name}'))
                    if visual:visual.GetVisibilityAttr().Set('inherited' if code==color else 'invisible')
        env._draw_stems()
