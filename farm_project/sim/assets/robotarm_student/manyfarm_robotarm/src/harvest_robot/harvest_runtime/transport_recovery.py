"""Opt-in simulation recovery for a retained fruit during stalled transport."""
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from harvest_rl.kinematics import ArmKinematics
from harvest_rl.settings import CACHE
from harvest_rl.logic import fruit_bounds

class TransportRecovery:
    def __init__(self,env):
        self.kin=ArmKinematics(CACHE/'harvest_training.urdf')
        self.targets={}
        self.used=set()

    def apply(self,env,stage,stage_steps,active,action):
        if not hasattr(env,"raw_grip") or not hasattr(env,"distance"):
            return action
        mask=active & (stage==1) & (stage_steps*env.step_dt>=10.) & getattr(env,"raw_grip",env.grip) & (env.distance<.02) & (env.slip<env.settings.max_slip*1.5) & env.has_retained
        # Discard episode/target-specific goals when transport ends or restarts.
        for i in list(self.targets):
            if not bool(active[i]) or int(stage[i]) != 1 or int(stage_steps[i]) == 0:
                del self.targets[i]
        fruit=env._target_fruit()
        pos=fruit.data.root_link_pos_w-env.scene.env_origins
        center,extent=fruit_bounds(pos,fruit.data.root_link_quat_w,env.settings)
        for i in mask.nonzero().flatten().tolist():
            q=env.robot.data.joint_pos[i,env.jids].cpu().numpy().copy()
            frame=self.kin.grasp_fk(q,env.settings.diameter)
            if i not in self.targets:
                # Fail explicitly if the saved policy frame no longer matches robot FK.
                tcp=env._tcp()[0][i]-env.scene.env_origins[i]
                if np.linalg.norm(frame[:3,3]-tcp.cpu().numpy())>.005:
                    raise ValueError('Recovery FK differs from runtime TCP by >5mm')
                lo=np.asarray(env.settings.box_min);hi=np.asarray(env.settings.box_max)
                c=center[i].cpu().numpy();ex=extent[i].cpu().numpy()
                goal=c.copy();goal[:2]=np.clip(c[:2],lo[:2]+ex[:2]+.015,hi[:2]-ex[:2]-.015)
                goal[2]=hi[2]+ex[2]+.03
                # Local correction only; distant stalls need a separately planned path.
                if np.linalg.norm(goal-c)>.08:
                    continue
                self.targets[i]=(frame[:3,3]+goal-c,frame[:3,:3].copy())
                self.used.add(i)
            target,rotation=self.targets[i]
            jac=np.zeros((6,5))
            for j in range(5):
                shifted=q.copy();shifted[j]+=1e-4
                other=self.kin.grasp_fk(shifted,env.settings.diameter)
                jac[:3,j]=(other[:3,3]-frame[:3,3])/1e-4
                jac[3:,j]=.08*Rotation.from_matrix(other[:3,:3]@frame[:3,:3].T).as_rotvec()/1e-4
            error=np.r_[target-frame[:3,3],.08*Rotation.from_matrix(rotation@frame[:3,:3].T).as_rotvec()]
            error[:3]=np.clip(error[:3],-.002,.002)
            delta=np.linalg.solve(jac.T@jac+.01**2*np.eye(5),jac.T@error)
            previous=env.targets[i,:5].cpu().numpy()
            desired=np.clip(previous+np.clip(delta,-.15*env.step_dt,.15*env.step_dt),q[:5]-.08,q[:5]+.08)
            desired=np.clip(desired,self.kin.lower[:5],self.kin.upper[:5])
            cmd=(desired-previous)/(env.settings.action_speed*env.step_dt)
            action[i,:5]=torch.as_tensor(np.clip(cmd,-.3,.3),device=env.device,dtype=action.dtype)
            action[i,5]=0.  # compliant squeeze remains active; never force opening
        return action
