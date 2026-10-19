"""Simulator-only physical HOME return with contact interlocks.

No teleport, reset, or default collision-free claim. The static scene is unchanged
and direct HOME interpolation is conservatively screened; legacy retrace is opt-in. Physical contacts, attachment
loss and deposited-fruit escape stop the return instead of bypassing obstacles.
"""
import numpy as np
from .executor import Feedback
from .return_path import reverse_path, bounded_target


class IsaacReturn:
    def __init__(self, env, *, velocity=.5, contact_limit=2., tracking_timeout=3., path_mode="direct"):
        if path_mode not in ("direct","retrace"):raise ValueError("Invalid return path mode")
        self.path_mode=path_mode
        self.env=env
        self.velocity=velocity
        self.contact_limit=contact_limit
        self.tracking_timeout=tracking_timeout
        self.history=[]
        self.records=[]
        self.stable=0.
        self.stopping=False
        self.problem=''

    def measured(self):
        return self.env.robot.data.joint_pos[0,self.env.jids].detach().cpu().numpy().copy()

    def record(self):
        self.history.append(self.measured())

    def begin_target(self):
        self.history=[self.measured()]

    def _guard(self):
        import torch
        from .deposit_guard import still_in_box
        e=self.env
        if not torch.isfinite(e.robot.data.joint_pos).all():return 'nonfinite_joint'
        sensors=(e.arm_contact,e.fixed_contact,e.moving_contact)
        if not all(bool(torch.isfinite(s.data.net_forces_w).all()) for s in sensors):
            return 'nonfinite_contact'
        if not all(bool(torch.isfinite(f.data.root_link_pos_w).all()) for f in e.fruits):
            return 'nonfinite_fruit_position'
        force=max(float(torch.linalg.vector_norm(s.data.net_forces_w,dim=-1).max()) for s in sensors)
        self.peak_force=max(getattr(self,'peak_force',0.),force)
        if force>self.contact_limit:return f'return_contact_{force:.3f}N'
        if bool(((~e.attached)&~e.collected).any()):return 'uncollected_fruit_detached'
        for i,f in enumerate(e.fruits):
            if bool(e.collected[0,i]):
                if not still_in_box(f,e):
                    return f'collected_fruit_{i}_outside_box'
        return ''

    def _physical_step(self, command):
        import torch
        e=self.env
        e.targets[:]=torch.as_tensor(command,device=e.device,dtype=e.targets.dtype)
        for _ in range(e.settings.decimation):
            e._sim_step_counter+=1
            # Maintain genuine stem forces on all remaining fruit during return.
            e._apply_action()
            e.scene.write_data_to_sim()
            e.sim.step(render=False)
            e.scene.update(e.physics_dt)
            if not self.stopping:
                self.problem=self._guard()
                if self.problem:
                    e.targets[:]=e.robot.data.joint_pos[:,e.jids]
                    e.robot.set_joint_position_target(e.targets,joint_ids=e.jids)
                    break
        e.episode_length_buf+=1
        if e.sim.has_gui():e.sim.render()

    def start_return(self, request, now_s):
        e=self.env
        self.stopping=False;self.problem='';self.stable=0.;self.peak_force=0.
        self.start=now_s;self.waypoint_start=now_s
        home=e.home.detach().cpu().numpy()
        current=self.measured()
        self.command=current.copy()
        self.bias=np.zeros(6)
        self.previous_measured=current.copy()
        self.initial_return=not bool(self.history)
        if not self.history:
            # Initial scene must already be HOME; no unrecorded shortcut allowed.
            if np.max(abs(current[:5]-home[:5]))>.03:
                raise RuntimeError('Initial pose not HOME and no recorded return path')
            self.history=[current]
        if self.initial_return or self.path_mode=='retrace':
            self.path=reverse_path(self.history+[current],home,float(home[-1]))
        else:
            from harvest_rl.settings import CACHE
            from harvest_rl.kinematics import ArmKinematics
            from .home_clearance import screened_home_path
            fruit_positions=[(f.data.root_link_pos_w[0]-e.scene.env_origins[0]).cpu().numpy() for f in e.fruits]
            self.path=screened_home_path(current,home,ArmKinematics(CACHE/'harvest_training.urdf'),fruit_positions,e.settings)
        self.index=0
        self.problem=self._guard()
        self.records.append(dict(request_id=request.request_id,start_s=now_s,waypoints=len(self.path),path_mode=self.path_mode))

    def tick_return(self, request, now_s):
        def result(status,reason=''):
            self.records[-1].update(status=status,reason=reason,peak_force_N=self.peak_force,elapsed_s=now_s-self.start)
            return Feedback(request.request_id,request.target_id,status,reason)
        if self.problem:return result('FAILED',self.problem)
        current=self.measured()
        if self.initial_return:
            import torch
            if (np.max(abs(current-self.path[-1]))<.03 and
                    bool((torch.abs(self.env.robot.data.joint_vel[0,self.env.jids])<.1).all())):
                self.history=[]
                return result('SUCCEEDED','measured_initial_home_stationary')
        control_speed=float(np.max(abs(current-self.previous_measured))/self.env.step_dt)
        self.previous_measured=current.copy()
        goal=self.path[self.index]
        if np.max(abs(current-goal))<.035:
            if self.index<len(self.path)-1:
                self.index+=1;self.waypoint_start=now_s;goal=self.path[self.index];self.stable=0.
            else:
                import torch
                speed=float(torch.abs(self.env.robot.data.joint_vel[0,self.env.jids]).max())
                self.records[-1].update(joint_speed_rad_s=speed,control_speed_rad_s=control_speed)
                self.stable=self.stable+self.env.step_dt if control_speed<.05 and speed<.5 and current[-1]>.65 else 0.
                if self.stable>=.25:
                    self.env.targets[:]=self.env.robot.data.joint_pos[:,self.env.jids]
                    self.history=[]
                    return result('SUCCEEDED','physical_home_open_gripper_settled')
        else:
            self.stable=0.
        if now_s-self.waypoint_start>self.tracking_timeout:
            self.records[-1].update(measured=current.tolist(),goal=goal.tolist(),error=(goal-current).tolist())
            return result('FAILED','return_tracking_stalled')
        # Compensate steady gravity error in the existing position drives without
        # changing actuator gains/physics. Limited integral; contact still stops.
        self.bias=np.clip(self.bias+.5*(goal-current)*self.env.step_dt,-.06,.06)
        desired=np.clip(goal+self.bias,self.env.lower.cpu().numpy(),self.env.upper.cpu().numpy())
        self.command=bounded_target(self.command,desired,self.velocity,self.env.step_dt)
        self.command=np.clip(self.command,current-.08,current+.08)
        self._physical_step(self.command)
        if self.problem:return result('FAILED',self.problem)
        return result('RUNNING')

    def stop(self, reason, now_s):
        self.stopping=True
        if getattr(self.env,'assignment_status',None)=='RUNNING':
            self.env.cancel_target()
        self.hold=self.measured()
        self.env.targets[:]=self.env.robot.data.joint_pos[:,self.env.jids]
        self.env.robot.set_joint_position_target(self.env.targets,joint_ids=self.env.jids)

    def tick_stop(self, now_s):
        import torch
        self._physical_step(self.hold)
        return bool(torch.isfinite(self.env.robot.data.joint_vel).all() and
                    (torch.abs(self.env.robot.data.joint_vel[0,self.env.jids])<.1).all())
