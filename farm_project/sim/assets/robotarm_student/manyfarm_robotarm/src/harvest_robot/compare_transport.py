"""Paired deterministic checkpoint comparison; one episode per physical bank state."""
import argparse,json,hashlib
from pathlib import Path
from isaaclab.app import AppLauncher
p=argparse.ArgumentParser()
p.add_argument('--checkpoints',nargs='+',required=True);p.add_argument('--bank',required=True)
p.add_argument('--output',required=True);p.add_argument('--min-distance',type=float,default=.03)
p.add_argument('--max-distance',type=float,default=.15)
AppLauncher.add_app_launcher_args(p);a=p.parse_args()
if Path(a.output).exists():p.error('Output exists')
a.kit_args=(a.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(a).app;failed=False
try:
 import torch
 from harvest_rl.settings import TaskSettings
 from harvest_rl.stage_bank import select_start_indices
 from harvest_rl.env import HarvestEnv
 from harvest_rl.policy import teacher_config
 from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
 from rsl_rl.runners import OnPolicyRunner
 configs=[json.loads((Path(c).parent/'run.json').read_text()) for c in a.checkpoints]
 # Start distribution is explicitly replaced by the same evaluation bank below.
 ignored={'start_bank','transport_start_min','transport_start_max','transport_replay_fraction','seed','workspace_split'}
 contracts=[{k:v for k,v in c['task'].items() if k not in ignored} for c in configs]
 if any(contract!=contracts[0] or c['asset']!=configs[0]['asset'] for contract,c in zip(contracts,configs)):
  raise ValueError('Paired comparison requires identical physics/task contracts and assets')
 payload=torch.load(a.bank,map_location='cpu',weights_only=True)
 cfg=dict(configs[0]['task']);cfg.update(start_bank=a.bank,workspace_split=payload['metadata']['workspace_split'],transport_start_min=a.min_distance,transport_start_max=a.max_distance,transport_replay_fraction=0.)
 settings=TaskSettings(**cfg)
 selected,distance=select_start_indices(payload['states'],settings)
 n=len(selected);total=n*len(a.checkpoints)
 class Probe(HarvestEnv):
  def _get_dones(self):
   self._update_task()
   return torch.zeros_like(self.success),torch.zeros_like(self.failure)
 env=Probe(settings,num_envs=total,device=a.device)
 env.start_bank.sample_indices=lambda ids:selected.to(env.device)[ids%n]
 wrapped=RslRlVecEnvWrapper(env,clip_actions=1.)
 policies=[]
 for ckpt in a.checkpoints:
  runner=OnPolicyRunner(wrapped,teacher_config(),None,device=a.device)
  runner.load(ckpt,load_optimizer=False)
  policies.append(runner.get_inference_policy(device=a.device))
 env.reset();obs=wrapped.get_observations()
 ended=torch.zeros(total,dtype=torch.bool,device=env.device)
 success=ended.clone();failure=ended.clone();steps=torch.zeros(total,device=env.device)
 for step in range(env.max_episode_length):
  with torch.inference_mode():
   action=torch.cat([policy(obs[i*n:(i+1)*n]) for i,policy in enumerate(policies)])
   action[ended]=0
   obs,_,_,_=wrapped.step(action)
  fresh=~ended & (env.success|env.failure)
  success[fresh]=env.success[fresh];failure[fresh]=env.failure[fresh];steps[fresh]=step+1;ended|=fresh
  if step%100==0:print('PAIRED_STEP',step,'ended',int(ended.sum()),'success',int(success.sum()),flush=True)
  if ended.all():break
 steps[~ended]=env.max_episode_length
 result={'bank':a.bank,'bank_sha256':hashlib.sha256(Path(a.bank).read_bytes()).hexdigest(),
         'split':settings.workspace_split,'states_per_checkpoint':n,'deterministic':True,'results':[]}
 near=(distance[selected]<.10).to(env.device)
 for i,ckpt in enumerate(a.checkpoints):
  sl=slice(i*n,(i+1)*n);out={'checkpoint':ckpt,'sha256':hashlib.sha256(Path(ckpt).read_bytes()).hexdigest()}
  for name,mask in [('all',torch.ones_like(near)),('near',near),('next',~near)]:
   count=int(mask.sum());ok=success[sl][mask];bad=failure[sl][mask]
   out[name]={'episodes':count,'success':int(ok.sum()),'failure':int(bad.sum()),'timeout':int((~ok&~bad).sum()),
              'success_rate':float(ok.float().mean()) if count else None,
              'mean_success_s':float(steps[sl][mask][ok].mean()*env.step_dt) if ok.any() else None}
  result['results'].append(out)
 Path(a.output).parent.mkdir(parents=True,exist_ok=True)
 with Path(a.output).open('x') as f:json.dump(result,f,indent=2)
 print('PAIRED_RESULT',json.dumps(result),flush=True)
except Exception:
 import traceback;traceback.print_exc();failed=True
finally:
 from harvest_rl.lifecycle import close_simulator
 close_simulator(app,locals().get('env'),failed)
