"""Separate attached-grasp objective: prove the pull controller's two-second hold.

This is a training/evaluation objective, not a relaxed harvest success rule.
The original contact, attachment, actuator and failure criteria remain intact.
"""
import copy
import json
from pathlib import Path
import torch

SCHEMA = 'attached_grasp_bridge_60hz_v1'
SPEC = dict(version=1, post_confirmation_hold_s=2., preload_deg=4.,
    preload_rate_deg_s=6., proposal_cost_per_s=2.,
    scope='HOME approach/grasp followed by the same stored arm target and finite jaw preload as response pull; no pulling',
    success='Original attached 250ms qualification, then uninterrupted actual qualified contact/slip for two additional seconds',
    failure='Original physical failure, or actual qualification/contact/slip/attachment loss after confirmation',
    velocity='Measured velocities recorded; no arbitrary velocity cutoff or velocity reset',
    physics='Unchanged9g/v1/response6,60Hz physics,20Hz policy; no auxiliary forces, weld or pose correction')
FILES = ['scripts/train_teacher60_grasp_bridge.py',
    'src/harvest_robot/harvest_rl/grasp_bridge_60hz.py',
    'src/harvest_robot/harvest_rl/teacher_grasp_bridge_env.py',
    'src/harvest_robot/harvest_rl/bounded_grip_60hz.py']


def bridge_step(started, hold_time, original_success, qualified, attached, failed, dt):
    """Confirmation's first sample earns no post-confirmation hold time."""
    if not 0 < dt <= .05+1e-9:
        raise ValueError('Positive bridge sample period at most50ms required')
    first = ~started & original_success & attached & qualified & ~failed
    lost = started & ~(qualified & attached)
    updated = torch.where(started & qualified & attached & ~failed,
        hold_time+dt, torch.zeros_like(hold_time))
    started = started | first
    success = started & ~failed & ~lost & (updated >= SPEC['post_confirmation_hold_s']-1e-6)
    return started, updated, success, lost, first


def verify_parent_transfer(checkpoint, saved, contract, root):
    """Contact-grasp weights/normalizer only; physical parent must match exactly."""
    from .grasp_load_reserve_60hz import verify_parent_transfer as verify_load_parent
    expected = copy.deepcopy(contract)
    expected.pop('grasp_bridge', None)
    for name in FILES:
        expected['domain_files'].pop(name, None)
    result = verify_load_parent(checkpoint, saved, expected, root)
    result.update(grasp_bridge_objective_changed=True, bridge_optimizer_transferred=False)
    return result


class BridgeHandoffCollector:
    """Attach proof provenance to the parent's unmodified physical snapshots."""
    def __init__(self, run, contract, checkpoint, limit):
        from .grasp_handoff_60hz import GraspHandoffCollector
        self.parent = GraspHandoffCollector(run, contract, checkpoint, limit)
        self.controls = []
        self.parent.metadata.update(schema=SCHEMA,source_task='grasp_bridge',grasp_bridge=SPEC,
            continuation='Bridge-only schema: original250ms bank readers must reject. Carry jaw origin/latched flags and arm targets; do not restart4deg preload or repeat2s settling.',
            certification='Pre-reset attached real250ms qualification plus2s uninterrupted actual qualified/slip contact under bounded4deg/6deg_s preload; no pulling proof')

    def begin_batch(self, *args):
        return self.parent.begin_batch(*args)

    def capture(self, env):
        if (env.success & (env.bridge_hold_time < SPEC['post_confirmation_hold_s']-1e-6)).any():
            raise RuntimeError('Bridge bank attempted export before actual two-second hold')
        if self.parent.active is None or self.parent.count >= self.parent.limit:
            return
        from .grasp_handoff_60hz import certify
        valid=certify(env._t(env.attached),env.grip & env.raw_grip,env.has_grasped,
            env.failure,env.grip_time,env.settings.grip_hold_s)
        ids=(self.parent.active & env.success & valid).nonzero().flatten()[:self.parent.limit-self.parent.count]
        self.parent.capture(env)
        if len(ids):
            self.controls.append({k:v[ids].detach().cpu().clone() for k,v in dict(
                jaw_origin=env.bridge_preload.origin,jaw_latched=env.bridge_preload.latched,
                jaw_released=env.bridge_preload.released,stored_arm_targets=env.bridge_arm_targets,
                actual_post_confirmation_hold_s=env.bridge_hold_time).items()})

    def save(self, path):
        if not self.parent.count:
            raise RuntimeError('No actual two-second bridge states; bank not created')
        payload=dict(metadata=self.parent.metadata,
            states={k:torch.cat([c[k] for c in self.parent.chunks]) for k in self.parent.chunks[0]},
            control={k:torch.cat([c[k] for c in self.controls]) for k in self.controls[0]})
        validate_bridge_payload(payload)
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:torch.save(payload,stream)
        print('GRASP_BRIDGE_BANK_SAVED',str(path),self.parent.count,flush=True)


def validate_bridge_payload(payload):
    from .grasp_handoff_60hz import validate_payload,SCHEMA as PARENT_SCHEMA
    m=payload['metadata']
    if m.get('schema')!=SCHEMA or m.get('source_task')!='grasp_bridge' or m.get('grasp_bridge')!=SPEC:
        raise ValueError('Requires explicitly marked bridge-only bank')
    # Validate the unchanged measured physical snapshot with the parent's full
    # checks, without making the bridge payload acceptable to legacy readers.
    parent=dict(metadata=copy.deepcopy(m),states=payload['states'])
    parent['metadata'].update(schema=PARENT_SCHEMA,source_task='grasp')
    validate_payload(parent)
    c=payload['control'];n=len(payload['states']['q'])
    shapes=dict(jaw_origin=(n,),jaw_latched=(n,),jaw_released=(n,),
        stored_arm_targets=(n,5),actual_post_confirmation_hold_s=(n,))
    if set(c)!=set(shapes) or any(tuple(c[k].shape)!=v or not torch.isfinite(c[k]).all() for k,v in shapes.items()):
        raise ValueError('Incomplete/nonfinite bridge control state')
    if (not c['jaw_latched'].all() or c['jaw_released'].any()
            or (c['actual_post_confirmation_hold_s']<SPEC['post_confirmation_hold_s']-1e-6).any()
            or not torch.allclose(c['stored_arm_targets'],payload['states']['targets'][:,:5],atol=1e-6,rtol=0)
            or (c['jaw_origin']-payload['states']['targets'][:,-1]>torch.pi/180*SPEC['preload_deg']+1e-6).any()):
        raise ValueError('Bridge hold/arm goal/single-origin preload evidence invalid')
    return payload
