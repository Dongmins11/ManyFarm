"""Read-only pre-solve connector bookkeeping; estimates never labelled measured."""
import json
from pathlib import Path
import torch
from isaaclab.utils.math import quat_apply


class NativeConnectorRecorder:
    def __init__(self,env):
        self.env=env;self.original=env._apply_action;self.frames=[]
        env._apply_action=self.record

    def record(self):
        env=self.env;before=env.attached.clone();target=env.target_index.clone()
        self.original()
        if env.applied_stem_force.abs().max()>1e-6 or env.applied_stem_torque.abs().max()>1e-6:
            raise ValueError('Native connector must be the sole stem wrench owner')
        for slot,fruit in enumerate(env.fruits):
            point=fruit.data.root_link_pos_w+quat_apply(fruit.data.root_link_quat_w,env.fruit_tips[slot][None].expand(env.num_envs,-1))
            displacement=point-env.anchors[:,slot]
            values=dict(attached_before=before[:,slot],attached_after=env.attached[:,slot],
                detached_event=before[:,slot] & ~env.attached[:,slot],target_index_before_reset=target,
                extension_axial_m=-displacement[:,0],extension_total_m=displacement.norm(dim=-1),
                axial_open= -displacement[:,0]>=env.connector_spec.axial_release_m,
                spring_load_estimate_N=env.load[:,slot],timer_after_s=env.break_timer[:,slot],
                virtual_stem_force_N=env.applied_stem_force[:,slot].norm(dim=-1),
                virtual_stem_torque_Nm=env.applied_stem_torque[:,slot].norm(dim=-1))
            columns=sorted(values)
            self.frames.append((env._sim_step_counter,slot,columns,
                torch.stack([values[k].float() for k in columns],-1).clone()))

    def drain(self,active):
        frames=self.frames;self.frames=[];records=[]
        for step,slot,columns,values in frames:
            j=columns.index('target_index_before_reset');ids=[i for i in active if int(values[i,j])==slot]
            if ids:records.append(dict(physics_step=step,time_s=step*self.env.physics_dt,
                fruit_slot=slot,env_ids=ids,columns=columns,rows=values[ids].cpu().tolist()))
        return records

    def close(self):self.env._apply_action=self.original


def summarize(path):
    metrics={}
    with Path(path).open() as f:
        for line in f:
            row=json.loads(line)
            for i,data in zip(row['env_ids'],row['rows']):
                v=dict(zip(row['columns'],data));m=metrics.setdefault(i,dict(trial_id=i,
                    max_axial_extension_m=0.,max_load_estimate_N=0.,detachments=[]))
                if v['virtual_stem_force_N']>1e-6 or v['virtual_stem_torque_Nm']>1e-6:raise ValueError('Duplicate stem wrench')
                m['max_axial_extension_m']=max(m['max_axial_extension_m'],v['extension_axial_m'])
                m['max_load_estimate_N']=max(m['max_load_estimate_N'],v['spring_load_estimate_N'])
                if v['detached_event']:m['detachments'].append(dict(time_s=row['time_s'],**v))
    return dict(schema='native_connector_audit_v1',metrics=list(metrics.values()),
        virtual_stem_force_zero=True,force_values_are_estimates=True,
        note='Native D6 solver reaction is not exported by this recorder. Controlled isolated probes measure known external pull resistance. Physical contacts, poses and release are in substeps.jsonl.')
