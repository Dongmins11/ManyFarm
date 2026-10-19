"""Current robot physically sweeps through eight fruit. No injected fruit forces, no policy."""
import argparse,json
from pathlib import Path
from isaaclab.app import AppLauncher
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--short-hook',action='store_true',help='Opt-in finite-travel response5 connector')
p.add_argument('--output',type=Path,default=Path('outputs/harvest_rl/dense_arm_contact.json'))
p.add_argument('--require-pass',action='store_true',help='Exit nonzero if contact retention test does not pass')
p.add_argument('--cycles',type=int,default=3)
AppLauncher.add_app_launcher_args(p)
a=p.parse_args()
if a.cycles<1:p.error('cycles must be positive')
a.kit_args=(a.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(a).app
env=None;failed=False
try:
 import torch,numpy as np
 from scipy.spatial.transform import Rotation
 from isaaclab.utils.math import quat_apply
 from harvest_rl.env import HarvestEnv
 from harvest_rl.settings import TaskSettings,CACHE
 from harvest_rl.behavior_contract import apply_gentle_hook
 from harvest_rl.current_robot import prepare_current_robot
 from harvest_rl.current_pair_geometry import current_to_policy_frame
 from harvest_rl.kinematics import ArmKinematics
 class Probe(HarvestEnv):
  def _get_dones(self):
   self._update_task()
   return torch.zeros_like(self.success),torch.zeros_like(self.success)
 s=TaskSettings(task='pull',num_fruits=8,random_colors=False,episode_s=30)
 apply_gentle_hook(s)
 if a.short_hook:
  from harvest_rl.behavior_contract import apply_short_hook
  apply_short_hook(s)
 usd,kin,asset=prepare_current_robot();bank=np.load(CACHE/'workspace.npz')
 frame,_=current_to_policy_frame(ArmKinematics(CACHE/'harvest_training.urdf'),kin,np.vstack((bank['home'],bank['q'])))
 q=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
 env=Probe(s,num_envs=1,device=a.device,robot_usd=usd,robot_root_pose=(tuple(frame[:3,3]),tuple(q)),fruit_color_override=['Red','Yellow']*4,fruit_asset_cache=usd.parent/'hook_eight_assets')
 env.sim.set_camera_view(eye=(1.5,-1.5,1.5),target=(.48,-.2,.95))
 old=ArmKinematics(CACHE/'harvest_training.urdf')
 reports=[]
 for cycle in range(a.cycles):
  if not app.is_running():break
  # Reset bookkeeping with a deterministic, spacious staging fixture; the
  # sweep layout below is installed before any test motion/physics begins.
  env._candidate_cache_key=(s.diameter,s.curriculum,tuple(s.region_origin),tuple(s.region_min),tuple(s.region_max))
  env._reset_home_tcp=torch.tensor(old.grasp_fk(env.bank_np['home'])[:3,3],device=env.device,dtype=torch.float32)
  env._reset_candidates=torch.tensor([[1.2,j*.2,1.+k*.2] for k in range(2) for j in range(4)],device=env.device)
  env.reset()
  # Initial setup only: real joint drives perform the subsequent sweep.
  q0=torch.tensor([[-1.,-.97,.68,.29,-1.522,1.1]],device=env.device)
  all_q=env.robot.data.joint_pos.clone();all_q[:,env.jids]=q0
  env.robot.write_joint_state_to_sim(all_q,torch.zeros_like(all_q));env.targets[:]=q0
  placements=[]
  for i in range(8):
   sample=np.array([-.3+(i%4)*.35,-.97,.68,.29,-1.522,1.1])
   point=old.grasp_fk(sample)[:3,3].copy();point[2]+=(i//4)*.085
   placements.append(point)

  for i,f in enumerate(env.fruits):
   state=f.data.root_state_w.clone();state[:,:3]=torch.tensor(placements[i],dtype=torch.float32,device=env.device)
   state[:,3:7]=torch.tensor([1.,0,0,0],device=env.device);state[:,7:]=0
   f.write_root_state_to_sim(state);f.reset();env.rest_quat[:,i]=state[:,3:7]
   tip=torch.tensor(env.tips_np[i],dtype=torch.float32,device=env.device).reshape(1,3)
   env.anchors[:,i]=state[:,:3]+quat_apply(state[:,3:7],tip)
  env.attached.fill_(True);env.threshold.fill_(2.5);env.break_timer.zero_();env.fixture_tick=0
  peak=torch.zeros(8,device=env.device);contact_steps=torch.zeros(8,device=env.device)
  peak_arm=0.;aborted='';samples=[]
  for step in range(round(12/env.step_dt)):
   if not app.is_running():aborted='window_closed';break
   t=step*env.step_dt
   desired=q0.clone();desired[:,0]=min(.95,-1.+max(0.,t-1.)*.2)
   # Policy-free bounded joint controller. Gripper stays open.
   measured=env.robot.data.joint_pos[:,env.jids]
   speed=torch.tensor([env.settings.action_speed]*5+[env.settings.gripper_speed],device=env.device)
   action=((desired-env.targets)/(speed*env.step_dt)).clamp(-1,1)
   env.step(action)
   force=torch.maximum(env.fixed_contact.data.force_matrix_w.norm(dim=-1).amax(dim=(0,1)),
                       env.moving_contact.data.force_matrix_w.norm(dim=-1).amax(dim=(0,1)))
   peak=torch.maximum(peak,force);contact_steps+=(force>.1)
   arm=float(env.arm_contact.data.net_forces_w.norm(dim=-1).max());peak_arm=max(peak_arm,arm)
   if step%10==0:samples.append(dict(t=t,attached=env.attached[0].tolist(),finger_force_N=force.tolist()))
   if not bool(torch.isfinite(measured).all()) or max(arm,float(force.max()))>20:
    aborted='nonfinite_or_contact_above_20N';break
  attached=env.attached[0].tolist();touched=(contact_steps>=2).tolist()
  status=('ABORTED' if aborted else 'DETACHED' if not all(attached) else
          'CONTACT_RETAINED' if sum(touched)>=2 else 'INSUFFICIENT_CONTACT')
  reports.append(dict(cycle=cycle,status=status,reason=aborted,attached=attached,
      touched=touched,peak_finger_force_N=peak.tolist(),peak_arm_force_N=peak_arm,
      placements=placements,trace=samples))
  # Convert numpy fixture coordinates for JSON.
  reports[-1]['placements']=[x.tolist() for x in placements]
  print('DENSE_ARM_CONTACT',status,'touched',touched,'attached',attached,flush=True)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(dict(note='Current URDF, eight fruit, physical joint sweep, no injected fruit forces. Finger contacts are resolved per fruit; other arm contacts are aggregate. Not policy performance.',scenes=reports),indent=2))
 if a.require_pass and (len(reports)!=a.cycles or not all(r['status']=='CONTACT_RETAINED' for r in reports)):
  raise RuntimeError('Fixture did not pass; inspect saved result')
except Exception:
 import traceback
 traceback.print_exc();failed=True
finally:
 from harvest_rl.lifecycle import close_simulator
 close_simulator(app,env,failed)
