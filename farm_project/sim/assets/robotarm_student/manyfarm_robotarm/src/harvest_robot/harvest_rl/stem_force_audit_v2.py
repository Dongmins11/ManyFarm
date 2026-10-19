"""Align pre-solve force records to IsaacLab's already-incremented step counter."""
from .stem_force_audit import StemForceRecorder as OriginalRecorder,summarize


class StemForceRecorder(OriginalRecorder):
    def record(self,*args,**kwargs):
        result=super().record(*args,**kwargs)
        counter,slot,columns,values=self.frames[-1]
        self.frames[-1]=(counter-1,slot,columns,values)
        return result
