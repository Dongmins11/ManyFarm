"""Separate candidate; original Teacher chain/controllers and gates remain intact."""
import torch
from .teacher_friction_progress_env import TeacherFrictionProgressEnv
from .hook_connector import HookConnectors, HookSpec
from isaaclab.utils.math import quat_apply


class TeacherHookConnectorEnv(TeacherFrictionProgressEnv):
    def __init__(self,*args,hook_spec=None,**kwargs):
        self.hook_spec=(hook_spec or HookSpec()).validate()
        super().__init__(*args,**kwargs)
        self.hook_connectors=HookConnectors(self,self.hook_spec)

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'hook_connectors'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            before=[f.data.root_state_w[selected].clone() for f in self.fruits]
            self.hook_connectors.reset(selected)
            if any(not torch.equal(state,f.data.root_state_w[selected])
                   for state,f in zip(before,self.fruits)):
                raise RuntimeError('Connector reset changed initial fruit center/pose')

    def _draw_stems(self):
        # The pivot is a separate visual/constraint point, never a new fruit
        # center or a rewrite of the original anchors used by policy logic.
        if not self.visual_updates:return
        spec=self.hook_spec
        direction=self.anchors.new_tensor(spec.pivot_offset_direction)
        direction=direction/direction.norm()
        pivot=self.anchors+spec.length_m*direction
        tips=torch.stack([f.data.root_link_pos_w+quat_apply(f.data.root_link_quat_w,
            self.fruit_tips[i][None].expand(self.num_envs,-1)) for i,f in enumerate(self.fruits)],1)
        end=torch.where(self.attached[...,None],tips,pivot-spec.length_m*direction)
        # Two segments show slack/bending while retaining the60mm contour
        # visually. A taut connector becomes a straight line with real excess.
        span=end-pivot;distance=span.norm(dim=-1)
        unit=span/distance.clamp_min(1e-9)[...,None]
        side=torch.cross(unit,unit.new_tensor([0.,1.,0.]).expand_as(unit),dim=-1)
        fallback=torch.cross(unit,unit.new_tensor([1.,0.,0.]).expand_as(unit),dim=-1)
        side=torch.where((side.norm(dim=-1)<1e-6)[...,None],fallback,side)
        side=side/side.norm(dim=-1).clamp_min(1e-9)[...,None]
        slack=.5*(spec.length_m**2-distance.square()).clamp_min(0).sqrt()
        middle=(pivot+end)/2+slack[...,None]*side
        begin=torch.cat((pivot.reshape(-1,3),middle.reshape(-1,3)))
        finish=torch.cat((middle.reshape(-1,3),end.reshape(-1,3)))
        delta=finish-begin;length=delta.norm(dim=-1).clamp_min(1e-6);u=delta/length[:,None]
        q=torch.stack((1+u[:,2],-u[:,1],u[:,0],torch.zeros_like(length)),-1)
        fallback=torch.zeros_like(q);fallback[:,1]=1
        q=torch.nn.functional.normalize(torch.where((u[:,2]<-.999999)[:,None],fallback,q),dim=-1)
        scale=torch.stack((torch.full_like(length,.002),torch.full_like(length,.002),length),-1)
        self.stems.visualize((begin+finish)/2,q,scale,
            marker_indices=torch.zeros(len(begin),dtype=torch.long,device=self.device))

    def _get_rewards(self):
        value=super()._get_rewards()
        if hasattr(self,'hook_connectors'):
            fields=dict(hook_physical_break=self.hook_pending_breaks.any(-1),
                        stem_force_measured=torch.zeros_like(self.success),
                        hook_load_is_estimate=torch.ones_like(self.success))
            self.chain_snapshot.update(fields);self.last_diagnostics.update(fields)
        return value

    def close(self):
        if hasattr(self,'hook_connectors'):self.hook_connectors.close()
        super().close()

