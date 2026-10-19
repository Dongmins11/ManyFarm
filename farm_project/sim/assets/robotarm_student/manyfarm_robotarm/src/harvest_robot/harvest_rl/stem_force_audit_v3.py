"""Freeze target identity before auto-reset and align the actual physics counter."""
import torch
from .stem_force_audit_v2 import StemForceRecorder as PriorRecorder,summarize


class StemForceRecorder(PriorRecorder):
    def record(self,*args,**kwargs):
        target=self.env.target_index.clone()
        result=super().record(*args,**kwargs)
        counter,slot,columns,values=self.frames[-1]
        self.frames[-1]=(counter,slot,columns+['target_index_before_reset'],
            torch.cat((values,target.float()[:,None]),-1))
        return result

    def drain(self,active):
        frames=self.frames;self.frames=[];records=[]
        for step,slot,columns,values in frames:
            ids=[i for i in active if int(values[i,-1])==slot]
            if ids:records.append(dict(physics_step=step,time_s=step*self.env.physics_dt,fruit_slot=slot,
                env_ids=ids,columns=columns,rows=values[ids].cpu().tolist()))
        return records
