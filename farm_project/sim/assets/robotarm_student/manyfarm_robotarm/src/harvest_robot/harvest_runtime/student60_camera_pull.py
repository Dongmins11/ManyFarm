"""Bounded camera-guided grasp-to-pull assist; original physical grading only.

Pull timing starts from the controller's observed loaded-grip intent/hold, never
from environment phase/attachment. Known task pull direction and URDF geometry
are used to bound Cartesian speed and preserve the measured handoff orientation.
"""
import numpy as np
from scipy.spatial.transform import Rotation
from .student60_approach_anchor import AnchoredRetainedController
from .student60 import encode_command,decode_command


class CameraPullController(AnchoredRetainedController):
    def start(self,*args):
        super().start(*args)
        self.pull_started=None;self.pull_origin=None;self.pull_rotation=None

    def tool_pose(self,q):
        return self.arm_from_robot@self.kin.grasp_fk(q,self.contract['task']['diameter'])

    def step(self,frames,q,qd,tcp,target,now,capture):
        motor_trigger=(not self.guard_finished and self.hold_start is None and self.captured
                       and self.entry_ready and now-self.last_near_time<=.75)
        if motor_trigger:
            self.hold_start=now;self.hold_arm=self.inner.previous_q[:5].copy()
            self.hold_jaw=float(self.inner.previous_q[-1])
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        if motor_trigger:note['visual_servo']['grip_hold_trigger']='measured_stall_and_recent_camera_alignment'
        if not self.guard_finished:return command,note
        pose=self.tool_pose(q)
        if self.pull_started is None:
            self.pull_started=now;self.pull_origin=pose[:3,3].copy();self.pull_rotation=pose[:3,:3].copy()
        elapsed=now-self.pull_started
        if elapsed>=3.5:
            note['visual_servo']['bounded_camera_pull_completed']=True
            return command,note
        axis=np.linalg.inv(np.asarray(self.contract['box_from_arm']))[:3,:3]@np.asarray(self.contract['task']['tension_axis'])
        axis=axis/np.linalg.norm(axis)
        wanted_position=self.pull_origin+axis*min(.055,.03*elapsed)
        wanted_rotation=self.pull_rotation
        jac=np.zeros((6,5));epsilon=1e-4;length=.04
        for j in range(5):
            moved=np.asarray(q,float).copy();moved[j]+=epsilon;p=self.tool_pose(moved)
            jac[:3,j]=(p[:3,3]-pose[:3,3])/epsilon
            jac[3:,j]=length*Rotation.from_matrix(p[:3,:3]@pose[:3,:3].T).as_rotvec()/epsilon
        linear=(wanted_position-pose[:3,3])*.2
        linear*=min(1.,.0015/max(np.linalg.norm(linear),1e-12))
        angular=Rotation.from_matrix(wanted_rotation@pose[:3,:3].T).as_rotvec()*.2
        angular*=min(1.,.02/max(np.linalg.norm(angular),1e-12))
        delta=np.linalg.solve(jac.T@jac+.003**2*np.eye(5),jac.T@np.r_[linear,length*angular])
        scale=min(1.,.015/max(np.max(np.abs(delta)),1e-12),.0015/max(np.linalg.norm(jac[:3]@delta),1e-12))
        delta*=scale
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        goal[:5]=np.clip(self.inner.previous_q[:5]+delta,self.contract['lower_rad'][:5],self.contract['upper_rad'][:5])
        command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
        note['visual_servo'].update(bounded_camera_pull=True,own_pull_elapsed_s=elapsed,
            own_pull_travel_m=min(.055,.03*elapsed),pull_tracking_error_m=float(np.linalg.norm(wanted_position-pose[:3,3])),
            predicted_tcp_step_m=float(np.linalg.norm(jac[:3]@delta)),pull_joint_step_max_rad=float(np.max(np.abs(delta))))
        return command,note
