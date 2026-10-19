"""Inference-only continuation of a certified grasp bridge, without a second prefix.

Frozen grasp/pull sources are not edited. Only reset restores measured physical
states. The jaw origin/budget and elapsed prefix are carried across the handoff.
"""
import json
import math
from pathlib import Path
from types import SimpleNamespace
import torch

from .grasp_bridge_60hz import SPEC, validate_bridge_payload
from .grasp_handoff_60hz import GraspHandoffBank, validate_payload, contract_digest
from .teacher_asset_reference import sha

ROOT = Path(__file__).resolve().parents[3]
FILES = ['src/harvest_robot/harvest_rl/bridge_pull_60hz.py',
         'scripts/eval_teacher60_bridge_pull.py']


def verify_checkpoint(checkpoint, metadata):
    """Allow existing ready/response actors as explicit, checked inference transfers."""
    from .followup_60hz import verify_source
    checkpoint = Path(checkpoint).resolve()
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    run = json.loads((checkpoint.parent/'run.json').read_text())
    contract = json.loads((checkpoint.parent/'followup_contract.json').read_text())
    if contract['schema'] not in ('teacher60_pull_ready_v1', 'teacher60_fast_preload_contact_pull_v1'):
        raise ValueError('Only verified 60Hz ready/response pull actors are supported')
    digest = contract_digest(contract)
    if (saved['infos']['followup_contract_sha256'] != digest
            or run['followup_contract_sha256'] != digest or run['mode'] != 'train-pull'):
        raise ValueError('Pull model and its original training contract differ')
    old_bank = Path(run['start_bank'])
    if sha(old_bank) != run['start_bank_sha256'] or saved['infos']['start_bank_sha256'] != sha(old_bank):
        raise ValueError('Original pull training bank changed')
    old = validate_payload(torch.load(old_bank, map_location='cpu', weights_only=True), 'train')['metadata']
    for source in (old, metadata):
        verify_source(source)
        grasp = torch.load(source['source_checkpoint'], map_location='cpu', weights_only=True)
        if grasp['infos']['domain_contract_sha256'] != source['source_contract_sha256']:
            raise ValueError('Source grasp weights do not match bank contract')
    if old['physical_signature'] != metadata['physical_signature'] or old['domain_stage'] != metadata['domain_stage']:
        raise ValueError('Physical parameters/stage changed during pull transfer')
    for key in ('domain', 'robot_usd_sha256', 'current_base_to_policy_world', 'visual_scene_requested', 'normalization_contract'):
        if old['source_run'][key] != metadata['source_run'][key]:
            raise ValueError('Pull transfer assets/frame/observation/domain mismatch: '+key)
    old_files = old['source_contract']['domain_files']
    new_files = metadata['source_contract']['domain_files']
    if any(new_files[k] != h for k,h in old_files.items() if k in new_files):
        raise ValueError('Shared frozen grasp/physics sources differ')
    node = contract
    while True:
        for name,h in node['files'].items():
            if sha(ROOT/name) != h:
                raise ValueError('Frozen pull source changed: '+name)
        if 'parent' not in node:
            break
        if node['parent_contract_sha256'] != contract_digest(node['parent']):
            raise ValueError('Nested pull source contract differs')
        node = node['parent']
    return saved, dict(checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint),
        original_contract_sha256=digest, completed_iteration=saved['infos']['completed_iteration'],
        original_grasp_sha256=old['source_checkpoint_sha256'],
        executed_grasp_sha256=metadata['source_checkpoint_sha256'],
        role='Explicit inference transfer to bridge continuation; not same-contract PPO resume',
        optimizer_transferred=False, normalizer_buffers_transferred=True)


def load_bank(path, split):
    payload = validate_bridge_payload(torch.load(path, map_location='cpu', weights_only=True))
    if split not in ('validation', 'test') or payload['metadata']['split'] != split:
        raise ValueError('This inference path uses matching held-out bridge banks only')
    verified = json.loads((Path(path).parent/'verified_bridge.json').read_text())
    if (not verified['source_and_actual_contact_evidence_verified']
            or verified['bank_sha256'] != sha(path) or verified['split'] != split
            or verified['passed'] != len(payload['states']['q'])
            or verified['checkpoint_sha256'] != payload['metadata']['source_checkpoint_sha256']):
        raise ValueError('Bridge bank has no matching actual2s source evaluation')
    return payload


def seed_preload(controller, control, indices, ids):
    """Do not latch a new origin at the final jaw target or add another4 degrees."""
    if (abs(controller.budget-math.radians(SPEC['preload_deg'])) > 1e-8
            or abs(controller.rate-math.radians(SPEC['preload_rate_deg_s'])) > 1e-8):
        raise ValueError('Continuation must retain bridge total budget and rate')
    for destination,source in [('origin','jaw_origin'),('latched','jaw_latched'),('released','jaw_released')]:
        getattr(controller,destination)[ids] = control[source][indices]


class BridgeBank:
    def __init__(self, path, split, device):
        payload = load_bank(path, split)
        self.metadata = payload['metadata']
        self.count = len(payload['states']['q'])
        self.states = {k:v.to(device) for k,v in payload['states'].items()}
        self.control = {k:v.to(device) for k,v in payload['control'].items()}
        self.events = []

    def restore(self, env, ids, assignments):
        if (assignments.shape != (env.num_envs,) or ((assignments < 0)|(assignments >= self.count)).any()):
            raise ValueError('Complete pinned bridge assignment required before every reset')
        for name in ('raw_grip','grip'):
            if not hasattr(env,name):
                setattr(env,name,torch.zeros(env.num_envs,device=env.device,dtype=torch.bool))
        chosen = assignments[ids]
        for index in chosen.unique().tolist():
            selected = ids[chosen == index]
            view = SimpleNamespace(metadata=self.metadata,count=1,
                states={k:v[index:index+1] for k,v in self.states.items()})
            # The frozen method restores measured q/qd/body/targets/history and
            # invalidates contact flags for physical revalidation. No relabelled
            # bank is written or accepted by the legacy validator.
            GraspHandoffBank.restore(view, env, selected)
            env.handoff_indices[selected] = index
        seed_preload(env.continuation_preload,self.control,chosen,ids)
        env.continuation_prefix_s[ids] = self.control['actual_post_confirmation_hold_s'][chosen]
        if not torch.allclose(env.targets[ids,:5],self.control['stored_arm_targets'][chosen],atol=1e-6,rtol=0):
            raise ValueError('Bridge stored arm targets were not preserved')
        self.events.append(dict(ids=ids.cpu().tolist(),indices=chosen.cpu().tolist(),
            jaw_origin=env.continuation_preload.origin[ids].cpu().tolist(),
            prefix_s=env.continuation_prefix_s[ids].cpu().tolist()))


def make_contract(metadata, model):
    return dict(schema='teacher60_bridge_pull_inference_v1', learning=False,
        hardware_executed=False, comparison_only=True, training_gate_eligible=False,
        source_grasp_contract_sha256=metadata['source_contract_sha256'],
        source_grasp_sha256=metadata['source_checkpoint_sha256'],
        physical_signature=metadata['physical_signature'],pull_model=model,
        continuation=dict(arm_settle_repeated=False,jaw_origin_rebased=False,
            jaw_budget_deg=4.,jaw_rate_deg_s=6.,stored_targets_preserved=True,
            prefix_s=2.,observation_clock='Existing pull phase clock includes completed bridge2s',
            timeout='Original20s pull phase including completed2s; <=18s further physics',
            arm_ramp_s=.5,initial_scale=.2,hold_after_detach=False),
        scope='Actual valid detachment plus original0.5s physical retention; no transport/place/PPO certificate',
        files={f:sha(ROOT/f) for f in FILES})
