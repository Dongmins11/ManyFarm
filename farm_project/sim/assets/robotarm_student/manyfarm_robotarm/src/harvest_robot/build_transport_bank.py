"""Generate transport curriculum starts through physical, contact-checked arm motion."""
import argparse,json,hashlib
from pathlib import Path
from isaaclab.app import AppLauncher
p=argparse.ArgumentParser()
p.add_argument('--source-run',required=True);p.add_argument('--bank',required=True)
p.add_argument('--output',required=True);p.add_argument('--num-envs',type=int,default=32)
p.add_argument('--batches',type=int,default=4)
p.add_argument('--seed',type=int,default=42)
AppLauncher.add_app_launcher_args(p);a=p.parse_args()
a.kit_args=(a.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
if a.batches<1 or a.num_envs<1:p.error('batches and num-envs must be positive')
if Path(a.output).exists():p.error('Output already exists; choose a new path')
app=AppLauncher(a).app;failed=False
try:
 import numpy as np, torch
 from scipy.optimize import least_squares
 from harvest_rl.env import HarvestEnv
 from harvest_rl.settings import TaskSettings,CACHE
 from harvest_rl.kinematics import ArmKinematics
 from harvest_rl.logic import placement_target
 from harvest_rl.stage_bank import StageBankCollector
 class Builder(HarvestEnv):
  def _get_dones(self):
   self._update_task()
   return torch.zeros_like(self.success),torch.zeros_like(self.failure)
 source=json.loads((Path(a.source_run)/'run.json').read_text())
 if source['task']['task']!='pull':raise ValueError('Build from a validated pull source run')
 payload=torch.load(a.bank,map_location='cpu',weights_only=True)
 cfg=dict(source['task']);cfg.update(seed=a.seed,task='transport',target_mode='random',reward_version=8,start_bank=a.bank,workspace_split=payload['metadata']['workspace_split'],transport_start_min=0.,transport_start_max=0.)
 common={}
 if source.get('robot_source')=='current':
  from harvest_rl.current_robot import prepare_current_robot
  from scipy.spatial.transform import Rotation
  usd,_,asset=prepare_current_robot()
  if asset!=source['current_asset']:raise ValueError('Current asset changed since bank collection')
  frame=np.asarray(source['current_base_to_policy_world'])
  q=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
  common=dict(robot_usd=usd,robot_root_pose=(tuple(frame[:3,3]),tuple(q)),fruit_asset_cache=usd.parent/'pair_fruit_assets')
 env=Builder(TaskSettings(**cfg),num_envs=a.num_envs,device=a.device,**common)
 kin=ArmKinematics(CACHE/'harvest_training.urdf')
 predecessor=dict(source['task']);predecessor['workspace_split']=cfg['workspace_split']
 collector=StageBankCollector(TaskSettings(**predecessor),payload['metadata']['checkpoint'],100000)
 collector.metadata['generation']={'method':'physical_joint_rollout','parent_bank_sha256':hashlib.sha256(Path(a.bank).read_bytes()).hexdigest(),'step_dt':env.step_dt,'action_limit':.25,'batches':a.batches,'seed':a.seed,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 successful_paths=0
 for batch in range(a.batches):
  env.reset();env.step(torch.zeros(a.num_envs,6,device=env.device))
  qs=env.robot.data.joint_pos[:,env.jids].cpu().numpy()
  pos=(env._target_fruit().data.root_link_pos_w-env.scene.env_origins).cpu().numpy()
  goal=placement_target(env.settings,'cpu').numpy();qgoal=[];errors=[]
  for q,pos0 in zip(qs,pos):
   tf=kin.grasp_fk(q);offset=tf[:3,:3].T@(pos0-tf[:3,3])
   def residual(x):
    t=kin.grasp_fk(np.r_[x,q[5]])
    return np.r_[t[:3,3]+t[:3,:3]@offset-goal,.002*(x-q[:5])]
   sol=least_squares(residual,np.clip(q[:5],kin.lower[:5]+.001,kin.upper[:5]-.001),bounds=(kin.lower[:5]+.001,kin.upper[:5]-.001),max_nfev=150)
   qgoal.append(np.r_[sol.x,q[5]]);errors.append(np.linalg.norm(residual(sol.x)[:3]))
  desired=torch.tensor(np.array(qgoal),device=env.device,dtype=torch.float32)
  alive=~env.failure.clone();ever_success=torch.zeros_like(alive)
  records=[]
  print('IK',batch,'reachable',sum(x<.01 for x in errors),flush=True)
  for step in range(220):
   delta=desired-env.targets
   action=(delta/(env.settings.action_speed*env.step_dt)).clamp(-.25,.25);action[:,-1]=0
   env.step(action)
   alive &= ~env.failure & env.grip
   ever_success |= alive & env.success
   if step%5==0:
    ids=alive.nonzero().flatten()
    before=len(collector.chunks)
    collector.capture(env,ids,require_success=False)
    if len(collector.chunks)>before:
     # Match the collector slip certification in addition to the uninterrupted-contact mask.
     ids=ids[env.slip[ids]<env.settings.max_slip]
     records.append((collector.chunks.pop(),ids.cpu()))
   if step%40==0 or step==219:
    print('MOVE',batch,step,'alive',int(alive.sum()),'success',int(ever_success.sum()),'mean_distance',float(env.last_diagnostics['placement_distance_m'][alive].mean()),flush=True)
  successful_paths+=int(ever_success.sum())
  for record,ids in records:
   keep=ever_success.cpu()[ids]
   if keep.any():collector.chunks.append({k:v[keep] for k,v in record.items()})
  collector.count=sum(len(c['q']) for c in collector.chunks)
  print('BANK_PROGRESS',batch,collector.count,'successful_paths',successful_paths,flush=True)
 if not collector.count:raise RuntimeError('No successful physical transport paths; no bank saved')
 collector.metadata['generation']['successful_paths']=successful_paths
 collector.save(a.output)
 print('BUILDER_DONE',flush=True)
except Exception:
 import traceback;traceback.print_exc();failed=True
finally:
 from harvest_rl.lifecycle import close_simulator
 close_simulator(app,locals().get('env'),failed)
