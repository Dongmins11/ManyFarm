"""Vision-derived pregrasp and straight insertion before the camera Student closes.

A direct HOME-to-centre line can sweep a fixed finger into an elevated fruit.
First align behind the observed fruit, then insert along the tool axis with the
jaws open. All geometry is public URDF; no fruit truth/contacts/phase are read.
"""
import numpy as np
from scipy.spatial.transform import Rotation
from .student60_camera_pull import CameraPullController
from .student60 import decode_command,encode_command


class PregraspCameraController(CameraPullController):
    def start(self,*args):
        super().start(*args)
        self.pregrasp_plan=None;self.insertion_start=None;self.pregrasp_settle_s=0.

    def plan(self,q,root):
        desired=np.asarray(root)-self.up*self.contract['task']['length']*.08
        estimate=np.asarray(q,float).copy()
        for _ in range(100):
            position,vertical=self.pose(estimate)
            if np.linalg.norm(desired-position)<.0015 and abs(vertical)<.04:break
            jac=np.zeros((4,5));eps=1e-4
            for j in range(5):
                moved=estimate.copy();moved[j]+=eps;p,v=self.pose(moved)
                jac[:3,j]=(p-position)/eps;jac[3,j]=.05*(v-vertical)/eps
            delta=np.linalg.solve(jac.T@jac+.004**2*np.eye(5),jac.T@np.r_[desired-position,-.05*vertical])
            delta*=min(1.,.04/max(np.max(np.abs(delta)),1e-12))
            estimate[:5]=np.clip(estimate[:5]+delta,self.contract['lower_rad'][:5],self.contract['upper_rad'][:5])
        pose=self.tool_pose(estimate);error=float(np.linalg.norm(desired-pose[:3,3]))
        return dict(valid=error<.003,goal=desired,rotation=pose[:3,:3].copy(),
            pregrasp=desired-pose[:3,2]*.06,endpoint_fk_error_m=error)

    def step(self,frames,q,qd,tcp,target,now,capture):
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        anchor=self.inner.anchor
        if self.entry_ready or anchor.position is None:return command,note
        if self.pregrasp_plan is None:self.pregrasp_plan=self.plan(q,anchor.position)
        plan=self.pregrasp_plan
        if not plan['valid']:
            goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
            goal[:5]=self.inner.previous_q[:5]
            note['visual_servo']['pregrasp_unreachable']=True
            return encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad']),note
        pose=self.tool_pose(q)
        rotation_error=Rotation.from_matrix(plan['rotation']@pose[:3,:3].T).as_rotvec()
        if self.insertion_start is None:
            reached=np.linalg.norm(plan['pregrasp']-pose[:3,3])<.004 and np.linalg.norm(rotation_error)<.08
            self.pregrasp_settle_s=self.pregrasp_settle_s+.05 if reached else 0.
            if self.pregrasp_settle_s>=.15-1e-6:self.insertion_start=now
        alpha=0. if self.insertion_start is None else min(1.,(now-self.insertion_start)*.04/.06)
        wanted=plan['pregrasp']+(plan['goal']-plan['pregrasp'])*alpha
        jac=np.zeros((6,5));eps=1e-4;length=.04
        for j in range(5):
            moved=np.asarray(q,float).copy();moved[j]+=eps;p=self.tool_pose(moved)
            jac[:3,j]=(p[:3,3]-pose[:3,3])/eps
            jac[3:,j]=length*Rotation.from_matrix(p[:3,:3]@pose[:3,:3].T).as_rotvec()/eps
        linear=(wanted-pose[:3,3])*.25;linear*=min(1.,.003/max(np.linalg.norm(linear),1e-12))
        angular=rotation_error*.25;angular*=min(1.,.04/max(np.linalg.norm(angular),1e-12))
        delta=np.linalg.solve(jac.T@jac+.004**2*np.eye(5),jac.T@np.r_[linear,length*angular])
        delta*=min(1.,.025/max(np.max(np.abs(delta)),1e-12),.003/max(np.linalg.norm(jac[:3]@delta),1e-12))
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        goal[:5]=np.clip(self.inner.previous_q[:5]+delta,self.contract['lower_rad'][:5],self.contract['upper_rad'][:5])
        note['visual_servo'].update(pregrasp_path=True,pregrasp_endpoint_fk_error_m=plan['endpoint_fk_error_m'],
            insertion_fraction=alpha,pregrasp_tracking_error_m=float(np.linalg.norm(wanted-pose[:3,3])),
            insertion_clock_s=None if self.insertion_start is None else now-self.insertion_start)
        return encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad']),note
