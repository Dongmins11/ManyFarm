"""Read the exact response6 linear-solve output at 60Hz; never alter it."""
import torch
from unittest.mock import patch


def branch_flags(displacement,raw_force,cfg,threshold):
    axis=displacement.new_tensor(cfg.tension_axis);axis/=axis.norm()
    axial=(displacement*axis).sum(-1)
    tensile=(-(raw_force*axis).sum(-1)).clamp_min(0)
    return axial,tensile,(tensile>threshold)&(axial>cfg.valid_pull_distance),axial>=.025,displacement.norm(dim=-1)>=cfg.stem_max_extension


class StemForceRecorder:
    def __init__(self,env):
        from . import attachment_60hz_runtime as runtime
        self.env=env;self.runtime=runtime;self.original=runtime.coupled_wrench
        self.frames=[];self.call=0
        runtime.coupled_wrench=self.record

    def record(self,displacement,velocity,lever,omega,error,inverse,cfg,attached,timer,dt,threshold,**kwargs):
        raw=[];solve=torch.linalg.solve
        def observe(a,b,*args,**kw):
            value=solve(a,b,*args,**kw)
            if a.shape[-2:]==(6,6):raw.append(value.squeeze(-1).clone())
            return value
        # Scoped synchronously around this one existing solve. Returning the
        # exact original tensor leaves every force/torque and break flag intact.
        with patch.object(torch.linalg,'solve',observe):
            result=self.original(displacement,velocity,lever,omega,error,inverse,cfg,attached,timer,dt,threshold,**kwargs)
        if len(raw)!=1:raise ValueError('Expected exactly one original response6 solve')
        force,torque,after,next_timer,load=result
        axial,tensile,overload,axial_open,total_open=branch_flags(displacement,raw[0][:,:3],cfg,threshold)
        slot=self.call%len(self.env.fruits);self.call+=1
        values=dict(attached_before=attached,attached_after=after,detached_event=attached & ~after,
            raw_tension_N=tensile,raw_force_norm_N=raw[0][:,:3].norm(dim=-1),
            returned_load_before_detach_mask_N=load,applied_force_norm_N=force.norm(dim=-1),
            applied_torque_norm_Nm=torque.norm(dim=-1),threshold_N=threshold,
            extension_axial_m=axial,extension_total_m=displacement.norm(dim=-1),
            force_branch=overload,axial_25mm_branch=axial_open,total_extension_branch=total_open,
            timer_before_s=timer,timer_after_s=next_timer)
        for name,data in [('displacement',displacement),('raw_force',raw[0][:,:3]),('applied_force',force),('point_velocity',velocity)]:
            for j,axis in enumerate('xyz'):values[f'{name}_{axis}']=data[:,j]
        columns=sorted(values)
        self.frames.append((self.env._sim_step_counter+1,slot,columns,torch.stack([values[k].float() for k in columns],-1).clone()))
        return result

    def drain(self,active):
        frames=self.frames;self.frames=[]
        # Record only the assigned target, excluding spare/off-workspace fruit.
        target=self.env.target_index.cpu().tolist()
        records=[]
        for step,slot,columns,values in frames:
            ids=[i for i in active if target[i]==slot]
            if ids:records.append(dict(physics_step=step,time_s=step*self.env.physics_dt,fruit_slot=slot,
                env_ids=ids,columns=columns,rows=values[ids].cpu().tolist()))
        return records

    def close(self):self.runtime.coupled_wrench=self.original


def summarize(path):
    import json
    from pathlib import Path
    records={}
    with Path(path).open() as f:
        for line in f:
            r=json.loads(line)
            for i,row in zip(r['env_ids'],r['rows']):
                v=dict(zip(r['columns'],row));m=records.setdefault(i,dict(trial_id=i,
                    physics_samples=0,max_applied_force_N=0.,max_raw_tension_N=0.,max_applied_torque_Nm=0.,
                    detachments=[],after_detach_force_max_N=0.))
                m['physics_samples']+=1
                if v['attached_before']:
                    m['max_applied_force_N']=max(m['max_applied_force_N'],v['applied_force_norm_N'])
                    m['max_raw_tension_N']=max(m['max_raw_tension_N'],v['raw_tension_N'])
                    m['max_applied_torque_Nm']=max(m['max_applied_torque_Nm'],v['applied_torque_norm_Nm'])
                else:m['after_detach_force_max_N']=max(m['after_detach_force_max_N'],v['applied_force_norm_N'])
                if v['detached_event']:m['detachments'].append(dict(time_s=r['time_s'],physics_step=r['physics_step'],**v))
    if any(m['after_detach_force_max_N']>1e-8 for m in records.values()):raise ValueError('Stem force after physical detachment')
    return dict(schema='response6_exact_force_audit_v1',physics_hz=60,
        measured_reference_horizontal_peak_N=2.5,measured_extension_unknown=True,
        max_applied_force_N=max((m['max_applied_force_N'] for m in records.values()),default=0.),
        max_raw_tension_N=max((m['max_raw_tension_N'] for m in records.values()),default=0.),
        metrics=list(records.values()),after_detach_force_zero=True,
        note='Exact original 6x6 solve and returned/applied forces, including last break tick. No artificial forces or new substeps. A max-force parameter is not measured pull resistance.')
