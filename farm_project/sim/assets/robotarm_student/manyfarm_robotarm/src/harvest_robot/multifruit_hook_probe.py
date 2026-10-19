"""Eight fruit in ONE scene, scripted external loads; not robot-policy validation."""
import argparse,json
from pathlib import Path
from isaaclab.app import AppLauncher
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,default=Path('outputs/harvest_rl/eight_fruit_hook.json'))
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
  def _apply_action(self):
   super()._apply_action()
   if not hasattr(self,'fixture_tick'):return
   t=self.fixture_tick*self.physics_dt
   for i,f in enumerate(self.fruits):
    force=torch.zeros(1,1,3,device=self.device)
    if 1<=t<1.025:
     if i in (0,1):force[...,1]=2
     if i in (2,3):force[...,0]=6
    if 2<=t<2.3 and i in (4,5):force[...,2]=-2
    if 4<=t<5 and i==6:force[...,0]=-3
    f.instantaneous_wrench_composer.set_forces_and_torques(forces=force,torques=torch.zeros_like(force),is_global=True)
   self.fixture_tick+=1
 s=TaskSettings(task='pull',num_fruits=8,random_colors=False,episode_s=30)
 apply_gentle_hook(s)
 usd,kin,asset=prepare_current_robot();bank=np.load(CACHE/'workspace.npz')
 frame,_=current_to_policy_frame(ArmKinematics(CACHE/'harvest_training.urdf'),kin,np.vstack((bank['home'],bank['q'])))
 q=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
 env=Probe(s,num_envs=1,device=a.device,robot_usd=usd,robot_root_pose=(tuple(frame[:3,3]),tuple(q)),fruit_color_override=['Red','Yellow']*4,fruit_asset_cache=usd.parent/'hook_eight_assets')
 env.sim.set_camera_view(eye=(2.,-1.8,1.7),target=(.8,0,1.))
 reports=[]
 for cycle in range(a.cycles):
  if not app.is_running():break
  env.reset()
  # Controlled clearance fixture, not an assertion of arm reachability.
  for i,f in enumerate(env.fruits):
   state=f.data.root_state_w.clone();state[:,:3]=torch.tensor([.85,(i%4-1.5)*.14,1.+(i//4)*.18],device=env.device)
   state[:,3:7]=torch.tensor([1.,0,0,0],device=env.device);state[:,7:]=0
   f.write_root_state_to_sim(state);f.reset();env.rest_quat[:,i]=state[:,3:7]
   tip=torch.tensor(env.tips_np[i],dtype=torch.float32,device=env.device).reshape(1,3)
   env.anchors[:,i]=state[:,:3]+quat_apply(state[:,3:7],tip)
  env.attached.fill_(True);env.threshold.fill_(2.5);env.break_timer.zero_();env.fixture_tick=0
  for step in range(round(6/env.step_dt)):
   if not app.is_running():break
   env.step(torch.zeros(1,6,device=env.device))
  attached=env.attached[0].tolist()
  reports.append(dict(cycle=cycle,attached=attached,passed=attached==[True]*6+[False,True]))
  print('EIGHT_FRUIT_HOOK',reports[-1],flush=True)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(dict(note='Scripted external loads, stationary robot, 14cm grid; not a robot collision test',scenes=reports),indent=2))
 if len(reports)!=a.cycles or not all(r['passed'] for r in reports):raise RuntimeError('Fixture failed or interrupted; inspect result')
except Exception:
 import traceback
 traceback.print_exc();failed=True
finally:
 from harvest_rl.lifecycle import close_simulator
 close_simulator(app,env,failed)
