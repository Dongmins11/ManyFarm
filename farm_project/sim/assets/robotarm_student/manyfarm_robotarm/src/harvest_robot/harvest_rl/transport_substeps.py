"""Read-only 60Hz recorder; no extra simulate, target, or state writes."""
import torch


def snapshot(env):
    fruit=env._target_fruit().data
    tcp,_=env._tcp()
    q=env.robot.data.joint_pos[:,env.jids]
    qd=env.robot.data.joint_vel[:,env.jids]
    fields=dict(transport=env.transport_before.float(),
        episode_step_before=env.episode_length_buf.float(),
        attached=env._t(env.attached).float(),
        fixed_N=env._target_contact(env.fixed_contact).norm(dim=-1),
        moving_N=env._target_contact(env.moving_contact).norm(dim=-1),
        jaw_q_rad=q[:,-1],jaw_qd_rad_s=qd[:,-1],jaw_target_rad=env.targets[:,-1])
    for label,value in [('tcp',tcp-env.scene.env_origins),
                        ('link',fruit.root_link_pos_w-env.scene.env_origins),
                        ('com',fruit.root_com_pos_w-env.scene.env_origins),
                        ('v',fruit.root_com_lin_vel_w),('w',fruit.root_com_ang_vel_w)]:
        for j,axis in enumerate('xyz'):fields[label+'_'+axis]=value[:,j]
    for j in range(4):fields['quat_'+str(j)]=fruit.root_link_quat_w[:,j]
    for j in range(5):
        fields['q_'+str(j)]=q[:,j]
        fields['qd_'+str(j)]=qd[:,j]
        fields['target_'+str(j)]=env.targets[:,j]
    columns=sorted(fields)
    return columns,torch.stack([fields[k] for k in columns],-1).clone()


class SubstepRecorder:
    def __init__(self,env):
        self.env=env;self.original=env.scene.update
        self.last=env._sim_step_counter;self.frames=[]
        env.scene.update=self.update

    def update(self,*args,**kwargs):
        result=self.original(*args,**kwargs)
        counter=self.env._sim_step_counter
        if counter>self.last:
            columns,values=snapshot(self.env)
            self.frames.append((counter,columns,values))
            self.last=counter
        return result

    def drain(self,active):
        frames=self.frames;self.frames=[]
        return [dict(physics_step=counter,time_s=counter*self.env.physics_dt,
            env_ids=active,columns=columns,rows=values[active].cpu().tolist())
            for counter,columns,values in frames]

    def close(self):
        self.env.scene.update=self.original
