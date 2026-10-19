"""Observe beside the fruit before moving into the aligned insertion pose."""
import numpy as np
from scipy.optimize import least_squares
from .student60_bounded_occlusion import BoundedOcclusionCameraHarvestController,BoundedInsertionAnchor


class SideScanInsertionAnchor(BoundedInsertionAnchor):
    def update(self,target,tcp,qjaw,records,now,finished):
        point,note=super().update(target,tcp,qjaw,records,now,finished)
        if point is not None:return point,note
        last=self.last_supported if self.last_supported is not None else self.stamp
        if (not self.allow_blind or finished or self.position is None or last is None
                or qjaw<1.35 or not 0<=now-last<=5. or not 0<=now-self.stamp<=8.
                or np.linalg.norm(self.position-np.asarray(tcp))>.08):return None,note
        note.update(active=True,source='bounded_insertion_memory_after_side_camera_scan',
            blind_interval_s=float(now-last),maximum_blind_interval_s=5.,fresh_bbox=False)
        return self.position.copy(),note


class SideScanCameraHarvestController(BoundedOcclusionCameraHarvestController):
    def plan(self,q,root):
        plan=super().plan(q,root)
        if not plan['valid']:return plan
        if self.refined or self.refinement.position is not None:
            plan['scan_kind']='aligned_after_side_observation'
            return plan
        optical=self.arm_from_robot@self.kin.fk(np.zeros(6),'top_camera_color_optical_frame')
        side=optical[:3,0]-self.up*float(optical[:3,0]@self.up);side/=np.linalg.norm(side)
        reference=np.asarray(q,float)[:5].copy()
        if side@(np.array([.10,-.16,.18])-np.asarray(root))<0:side=-side
        lo=np.asarray(self.contract['lower_rad'][:5]);hi=np.asarray(self.contract['upper_rad'][:5])
        for offset in [.16,.14,.12]:
            wanted=plan['goal']-plan['rotation'][:,2]*.08+side*offset+self.up*.03
            def residual(arm):
                pose=self.tool_pose(np.r_[arm,1.5])
                return np.r_[pose[:3,3]-wanted,.001*(arm-reference),.003*(arm[-1]-.2)]
            solved=least_squares(residual,reference,bounds=(lo,hi),max_nfev=300,
                xtol=1e-10,ftol=1e-10,gtol=1e-10)
            pose=self.tool_pose(np.r_[solved.x,1.5]);error=float(np.linalg.norm(pose[:3,3]-wanted))
            margin=float(np.min(np.r_[solved.x-lo,hi-solved.x]))
            if error<.003 and margin>=.035:
                plan.update(pregrasp=wanted,rotation=pose[:3,:3].copy(),pregrasp_joint_goal=solved.x.copy(),
                    pregrasp_waypoint_fk_error_m=error,scan_side_offset_m=offset,
                    scan_joint_margin_rad=margin,scan_kind='stationary_camera_side_observation')
                return plan
        plan['valid']=False
        return plan

    def step(self,frames,q,qd,tcp,target,now,capture):
        if not isinstance(self.inner.anchor,SideScanInsertionAnchor):
            anchor=SideScanInsertionAnchor();anchor.__dict__.update(vars(self.inner.anchor));self.inner.anchor=anchor
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        if self.pregrasp_plan is not None:
            note['visual_servo'].update(scan_kind=self.pregrasp_plan.get('scan_kind'),
                scan_side_offset_m=self.pregrasp_plan.get('scan_side_offset_m'),
                scan_joint_margin_rad=self.pregrasp_plan.get('scan_joint_margin_rad'))
        return command,note
