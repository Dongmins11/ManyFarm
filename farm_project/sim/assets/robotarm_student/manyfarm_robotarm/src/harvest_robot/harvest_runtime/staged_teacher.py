"""Monotonic expert routing, optionally preceded by an entry-grasp expert."""
import copy
import json
from pathlib import Path
import torch


def next_stage(stage, detached, retained, grip, stopped):
    ready=detached & retained & grip
    result=torch.where((stage==0)&ready,1,stage)
    return torch.where((result==1)&ready&stopped,2,result)


def retention_open_guard(action, stage, active, attached, valid_detach, pending, contact):
    """No extra squeezing: keep non-opening command until captured retention is done."""
    mask=active & (stage==0) & ~attached & (valid_detach | pending) & contact
    result=action.clone()
    result[:,5]=torch.where(mask,result[:,5].clamp(max=0.),result[:,5])
    return result,mask & (action[:,5]>0)


def capture_settle_action(action, active, entry_active, stage, attached,
                          centered_grip, raw_contact, confirmed, valid_detach,
                          retained, pending):
    """Hold existing arm targets only during physically qualified confirmation.

    Never invent contact, bypass orientation, or increase squeeze beyond the policy.
    Release to normal routing immediately when physical qualification is lost.
    """
    entry = active & entry_active & attached & centered_grip & ~confirmed
    retention = active & (stage == 0) & ~attached & raw_contact & centered_grip & (
        valid_detach | pending) & ~retained
    mask=entry | retention
    result=action.clone()
    result[mask,:5]=0.
    result[mask,5]=result[mask,5].clamp(max=0.)
    return result,entry,retention


class StagedTeacher:
    def __init__(self, env, template, transport, place, grasp=None, *, allow_mass_transfer=False, allow_contact_transfer=False):
        self.env=env
        self.stage=torch.zeros(env.num_envs,dtype=torch.long,device=env.device)
        self.stage_steps=torch.zeros(env.num_envs,device=env.device)
        self.active=torch.ones(env.num_envs,dtype=torch.bool,device=env.device)
        self.experts=[template]
        self.contract={"runtime":env.settings.as_dict(),"experts":[]}
        if allow_mass_transfer:self.contract["evaluation_mass_override_kg"]=env.settings.mass
        contact_defaults={'contact_substeps':1,'fruit_collision_mode':'legacy','gripper_stiffness':8.0,'gripper_damping':.3,'contact_stiffness':0.,'contact_damping':0.}
        if allow_contact_transfer:
            self.contract['evaluation_contact_override']={k:getattr(env.settings,k) for k in contact_defaults}
        def compatible(metadata,field):
            if allow_contact_transfer and field in contact_defaults:return True
            return metadata.get(field,contact_defaults.get(field))==getattr(env.settings,field,contact_defaults.get(field))
        for path,task in [(transport,'transport'),(place,'place')]:
            metadata=json.loads((Path(path).parent/'run.json').read_text())['task']
            if metadata['task']!=task:raise ValueError(f'Expected {task} expert')
            self.contract['experts'].append(dict(path=str(path),task=metadata))
            for field in ('stage_transfer','attachment_version','stem_response_version','mass','diameter','length','gripper_effort','contact_substeps','fruit_collision_mode','gripper_stiffness','gripper_damping','contact_stiffness','contact_damping','spring_k','spring_d','break_force','tension_hold_s','stem_max_extension','stem_vertical_stiffness','lateral_stiffness_ratio','grip_friction','dynamic_friction','restitution'):
                if field=='mass' and allow_mass_transfer:continue
                if not compatible(metadata,field):
                    raise ValueError(f'Expert {task} incompatible {field}')
            expert=copy.deepcopy(template)
            expert.load_state_dict(torch.load(path,map_location=env.device,weights_only=False)['model_state_dict'],strict=True)
            expert.eval()
            self.experts.append(expert)

        if grasp is not None:
            metadata=json.loads((Path(grasp).parent/'run.json').read_text())['task']
            if metadata['task']!='grasp' or not metadata.get('entry_first_grasp',False):
                raise ValueError('Expected entry-first grasp expert')
            fields=('stage_transfer','attachment_version','stem_response_version','mass','diameter','length',
                    'gripper_effort','contact_substeps','spring_k','spring_d','break_force','tension_hold_s',
                    'stem_max_extension','stem_vertical_stiffness','lateral_stiffness_ratio','grip_friction',
                    'dynamic_friction','restitution','action_speed','gripper_speed','gripper_max_error',
                    'gripper_hold_error','grip_hold_s','grasp_center_tolerance','grasp_orientation',
                    'grasp_angle_tolerance','grasp_version','episode_s','fruit_collision_mode','gripper_stiffness','gripper_damping','contact_stiffness','contact_damping')
            for field in fields:
                if field=='mass' and allow_mass_transfer:continue
                if not compatible(metadata,field):
                    raise ValueError(f'Grasp expert incompatible {field}')
            self.grasp_expert=copy.deepcopy(template)
            self.grasp_expert.load_state_dict(torch.load(grasp,map_location=env.device,weights_only=False)['model_state_dict'],strict=True)
            self.grasp_expert.eval()
            self.grasp_active=torch.ones_like(self.active)
            env.entry_grasp_active=self.grasp_active
            env.expert_stage=torch.full_like(self.stage,-1)
            self.contract['experts'].append(dict(path=str(grasp),task=metadata))
            self.contract['routing']='entry grasp -> pull -> transport -> place; no scene reset'

    def reset(self):
        """Reset policy routing for a new target without resetting the scene."""
        self.stage.zero_()
        self.stage_steps.zero_()
        self.active.fill_(True)
        self.env.expert_stage=self.stage
        if hasattr(self,'grasp_expert'):
            self.grasp_active.fill_(True)
            self.env.entry_grasp_active=self.grasp_active
            self.env.expert_stage=torch.full_like(self.stage,-1)
            if hasattr(self.grasp_expert,'reset'):
                self.grasp_expert.reset(torch.ones_like(self.active))
        if hasattr(self,'recovery'):
            self.recovery.targets.clear()
        for expert in self.experts:
            if hasattr(expert,'reset'):
                expert.reset(torch.ones_like(self.active))

    def __call__(self,obs):
        e=self.env
        handoff=torch.zeros_like(self.active)
        if hasattr(self,'grasp_expert'):
            handoff=self.active & self.grasp_active & e.has_grasped & e.grip & (e._t(e.attached) | e.valid_detach)
            self.grasp_active &= ~handoff
            e.entry_grasp_active=self.grasp_active
        previous_stage=self.stage.clone()
        self.stage=torch.where(self.active,next_stage(self.stage,e.valid_detach,e.has_retained,e.grip,e.release_armed),self.stage)
        e.capture_transport_started=self.active & (previous_stage==0) & (self.stage==1)
        if hasattr(self,"collector"):
            self.collector.capture(e,(self.active & (previous_stage==0) & (self.stage>=1)).nonzero().flatten(),require_success=False)
        if hasattr(self,"place_collector"):
            self.place_collector.capture(e,(self.active & (previous_stage==1) & (self.stage==2)).nonzero().flatten(),require_success=False)
        changed=(self.stage!=previous_stage) | handoff
        self.stage_steps=torch.where(changed,0.,self.stage_steps)
        e.expert_stage=self.stage
        if hasattr(self,'grasp_expert'):
            e.expert_stage=torch.where(self.grasp_active,-1,self.stage)
        expert_obs=obs.clone() if hasattr(obs,'clone') else dict(obs)
        expert_obs['policy']=obs['policy'].clone()
        expert_obs['policy'][:,42]=(1-self.stage_steps/e.max_episode_length).clamp(0,1)
        actions=torch.stack([p.act_inference(expert_obs) for p in self.experts],dim=1)
        self.stage_steps+=self.active
        result=actions[torch.arange(e.num_envs,device=e.device),self.stage]
        if hasattr(self,'grasp_expert'):
            grasp_actions=self.grasp_expert.act_inference(expert_obs)
            result=torch.where(self.grasp_active[:,None],grasp_actions,result)
        scale=getattr(self,'near_fruit_arm_scale',1.)
        if scale!=1. and hasattr(e,'distance'):
            near=(self.stage==0)&e._t(e.attached)&(e.distance<.06)
            result[near,:5]=result[near,:5].clamp(-1.,1.)*scale
        diagnostic_scale=getattr(self,"diagnostic_transport_scale",1.)
        if diagnostic_scale!=1.:
            ramp_s=getattr(self,"diagnostic_transport_ramp_s",0.)
            if ramp_s:
                elapsed=(self.stage_steps-1).clamp_min(0)*e.step_dt
                scale=diagnostic_scale+(1-diagnostic_scale)*(elapsed/ramp_s).clamp(0,1)
                scale=scale[self.stage==1,None]
            else:
                scale=diagnostic_scale
            result[self.stage==1,:5]=result[self.stage==1,:5].clamp(-1.,1.)*scale
        if getattr(self,"block_transport_opening",False):
            result[self.stage==1,5]=result[self.stage==1,5].clamp(max=0.)
        if getattr(self,"release_mode","policy")=="fixed":
            # Zero increments retain the preceding arm position targets.
            result[self.stage==2,:5]=0.
            result[self.stage==2,5]=.15
        if hasattr(self,"recovery"):
            result=self.recovery.apply(e,self.stage,self.stage_steps,self.active,result)
        # Hold arm targets during bounded post-break verification, without welding fruit.
        if getattr(e.settings if hasattr(e,'settings') else None,'spring_grasp_grace',False):
            result[e.pending_detach,:5]=0.
        if getattr(getattr(e,'settings',None),'post_detach_hold_guard',False):
            result,e.retention_open_blocked=retention_open_guard(result,self.stage,self.active,
                e._t(e.attached),e.valid_detach,e.pending_detach,e.raw_grip)
        if getattr(self,"capture_settle",False):
            result,e.capture_settle_entry,e.capture_settle_retention = capture_settle_action(
                result,self.active,getattr(self,"grasp_active",torch.zeros_like(self.active)),
                self.stage,e._t(e.attached),e.grip,getattr(e,"raw_grip",torch.zeros_like(self.active)),e.has_grasped,
                e.valid_detach,e.has_retained,e.pending_detach)
        return result
