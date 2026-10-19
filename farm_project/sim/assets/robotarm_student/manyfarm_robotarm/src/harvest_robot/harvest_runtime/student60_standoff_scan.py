"""Choose a farther stationary camera scan with usable joint-limit margin."""
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .student60_bounded_occlusion import BoundedOcclusionCameraHarvestController


class StandoffScanCameraHarvestController(BoundedOcclusionCameraHarvestController):
    def plan(self,q,root):
        plan=super().plan(q,root)
        if not plan['valid']:return plan
        reference=np.array([-.7,-1.5,.6,.5,.2]);lo=np.asarray(self.contract['lower_rad'][:5]);hi=np.asarray(self.contract['upper_rad'][:5])
        for distance in [.11,.10,.09,.08,.07,.06]:
            wanted=plan['goal']-plan['rotation'][:,2]*distance
            def residual(arm):
                pose=self.tool_pose(np.r_[arm,1.5])
                return np.r_[pose[:3,3]-wanted,
                    .04*Rotation.from_matrix(plan['rotation']@pose[:3,:3].T).as_rotvec(),.00005*(arm-reference)]
            solved=least_squares(residual,plan['pregrasp_joint_goal'],bounds=(lo,hi),
                max_nfev=300,xtol=1e-10,ftol=1e-10,gtol=1e-10)
            error=residual(solved.x);margin=float(np.min(np.r_[solved.x-lo,hi-solved.x]))
            if np.linalg.norm(error[:3])<.003 and np.linalg.norm(error[3:6])/.04<.08 and margin>=.035:
                plan.update(pregrasp=wanted,pregrasp_joint_goal=solved.x.copy(),
                    pregrasp_waypoint_fk_error_m=float(np.linalg.norm(error[:3])),
                    scan_standoff_m=distance,scan_joint_margin_rad=margin)
                return plan
        plan['valid']=False
        return plan

    def step(self,*args):
        command,note=super().step(*args)
        if self.pregrasp_plan is not None:
            note['visual_servo'].update(scan_standoff_m=self.pregrasp_plan.get('scan_standoff_m'),
                scan_joint_margin_rad=self.pregrasp_plan.get('scan_joint_margin_rad'))
        return command,note
