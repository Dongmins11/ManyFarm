"""Read-only first-episode physical/control history shared by two pathways."""
import json
from pathlib import Path
import torch


class HandoffObserver:
    def __init__(self,*args,observer_output,**kwargs):
        super().__init__(*args,**kwargs)
        self.observer_stream=(Path(observer_output)/'handoff_observer.jsonl').open('x')
        self.observer_done=torch.zeros(self.num_envs,device=self.device,dtype=torch.bool)
        self.observer_bridge=torch.zeros_like(self.observer_done)
        self.observer_handoff=torch.zeros_like(self.observer_done)
        self.observer_moved=torch.zeros_like(self.observer_done)

    def _get_rewards(self):
        result=super()._get_rewards()
        if not hasattr(self,'observer_stream'):return result
        active=(~self.observer_done).nonzero().flatten().cpu().tolist()
        d=self.last_diagnostics
        from .contact_points_60hz import capture_contact_points
        contacts=capture_contact_points(self,self.margin_views)
        p,q=self._tcp();fruit=self._target_fruit().data
        handoff=getattr(self,'motion_started',getattr(self,'pull_active',torch.zeros_like(self.observer_done)))
        moved=getattr(self,'motion_moved',torch.zeros_like(self.observer_done))
        phase=(self._target_elapsed_steps()*self.step_dt).cpu().tolist()
        serial=self.bridge_serial.cpu().tolist()
        values={k:v.detach().cpu().tolist() for k,v in dict(
            q=self.robot.data.joint_pos[:,self.jids],qd=self.robot.data.joint_vel[:,self.jids],targets=self.targets,
            fruit_link_position=fruit.root_link_pos_w-self.scene.env_origins,fruit_quat=fruit.root_link_quat_w,
            fruit_com=fruit.root_com_pos_w-self.scene.env_origins,fruit_v=fruit.root_com_lin_vel_w,fruit_omega=fruit.root_com_ang_vel_w,
            tcp=p-self.scene.env_origins,tcp_quat=q,grasp_relative=self.grasp_relative,
            attached=self._t(self.attached),grip=self.grip,raw_grip=self.raw_grip,slip=self.slip,
            jaw_origin=self.bridge_preload.origin,jaw_latched=self.bridge_preload.latched,
            bridge_hold=self.bridge_hold_time,bridge_started=self.bridge_started,
            handoff=handoff,moved=moved,success=self.success,failure=self.failure,
            fixed=d['fixed_force_N'],moving=d['moving_force_N'],center=self.distance,
            sample=self.domain_samples).items()}
        times=(self.episode_length_buf*self.step_dt).cpu().tolist()
        events=[]
        for i in active:
            markers=[]
            if self.bridge_started[i] and not self.observer_bridge[i]:markers.append('bridge_confirmation')
            if handoff[i] and not self.observer_handoff[i]:markers.append('bridge_handoff')
            if moved[i] and not self.observer_moved[i]:markers.append('probe_moved')
            events.append(dict(env_id=i,serial=serial[i],time_s=times[i],phase_time_s=phase[i],
                events=markers,**{k:v[i] for k,v in values.items()},contacts={k:v[i] for k,v in contacts.items()}))
        self.observer_stream.write(json.dumps(events)+'\n')
        self.observer_stream.flush()
        self.observer_bridge|=self.bridge_started;self.observer_handoff|=handoff;self.observer_moved|=moved
        self.observer_done|=self.success|self.failure|self.reset_time_outs
        return result

    def close(self):
        if hasattr(self,'observer_stream') and not self.observer_stream.closed:self.observer_stream.close()
        return super().close()


from .teacher_transport_posture_env import TeacherTransportPostureEnv
from .teacher_dynamic_grasp_env import TeacherDynamicGraspEnv

class ObservedTransportEnv(HandoffObserver,TeacherTransportPostureEnv):
    pass

class ObservedDynamicEnv(HandoffObserver,TeacherDynamicGraspEnv):
    pass
