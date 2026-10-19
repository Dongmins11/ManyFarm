"""Bounded final insertion through expected hand occlusion after reobservation.

Only the servo uses its previously measured point. The neural observation keeps
the original invalid flag, zero target and actual camera age.
"""
import numpy as np
from .student60_reobserved_harvest import ReobservedCameraHarvestController,AssignedViewAnchor


class BoundedInsertionAnchor(AssignedViewAnchor):
    allow_blind=False
    last_supported=None

    def update(self,target,tcp,qjaw,records,now,finished):
        point,note=super().update(target,tcp,qjaw,records,now,finished)
        if point is not None:
            self.last_supported=now
            return point,note
        last=self.last_supported if self.last_supported is not None else self.stamp
        if (not self.allow_blind or finished or self.position is None or last is None
                or qjaw<1.35 or not 0<=now-last<=2.5 or not 0<=now-self.stamp<=8.
                or np.linalg.norm(self.position-np.asarray(tcp))>.08):return None,note
        note.update(active=True,source='bounded_final_insertion_memory_after_stationary_camera_reobservation',
            blind_interval_s=float(now-last),maximum_blind_interval_s=2.5,fresh_bbox=False)
        return self.position.copy(),note


class BoundedOcclusionCameraHarvestController(ReobservedCameraHarvestController):
    def step(self,frames,q,qd,tcp,target,now,capture):
        if not isinstance(self.inner.anchor,BoundedInsertionAnchor):
            anchor=BoundedInsertionAnchor();anchor.__dict__.update(vars(self.inner.anchor));self.inner.anchor=anchor
        # Only the short final insertion after the verified stationary scan.
        # A failure to finish within this fixed window cannot renew the lease.
        self.inner.anchor.allow_blind=bool(self.refined and self.insertion_start is not None
            and 0<=now-self.insertion_start<=3.)
        return super().step(frames,q,qd,tcp,target,now,capture)
