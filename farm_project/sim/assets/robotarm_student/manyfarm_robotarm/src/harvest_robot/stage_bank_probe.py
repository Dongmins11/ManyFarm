"""Check restored contact and native attachment geometry without learned actions."""
import argparse,json
from pathlib import Path
from isaaclab.app import AppLauncher
p=argparse.ArgumentParser();p.add_argument('--transport-start-min',type=float,default=0.);p.add_argument('--transport-start-max',type=float,default=0.);p.add_argument('--split',choices=['train','eval'],default='train');p.add_argument('--bank',required=True);p.add_argument('--source-run',required=True)
AppLauncher.add_app_launcher_args(p);a=p.parse_args();a.kit_args=(a.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1';app=AppLauncher(a).app
failed=False
try:
 import torch
 from harvest_rl.env import HarvestEnv
 from harvest_rl.settings import TaskSettings
 from isaaclab.utils.math import quat_apply
 class Probe(HarvestEnv):
  def _get_dones(self):
   self._update_task();return torch.zeros_like(self.success),torch.zeros_like(self.failure)
 cfg=json.loads((Path(a.source_run)/'run.json').read_text())['task'];cfg.update(task='transport',reward_version=8,start_bank=a.bank,workspace_split=a.split,transport_start_min=a.transport_start_min,transport_start_max=a.transport_start_max)
 env=Probe(TaskSettings(**cfg),num_envs=32,device=a.device);env.reset()
 from pxr import UsdGeom,Gf
 cache=UsdGeom.XformCache();errors=[]
 for e in range(32):
  for i in range(3):
   if env.attached[e,i]:
    m=cache.GetLocalToWorldTransform(env.sim.stage.GetPrimAtPath(f'/World/envs/env_{e}/Fruit_{i}'))
    v=m.Transform(Gf.Vec3d(*env.tips_np[i]));target=env.anchors[e,i].cpu().tolist()
    errors.append(sum((v[j]-target[j])**2 for j in range(3))**.5)
 print('USD_ANCHOR_ERROR',max(errors),flush=True)
 assert max(errors)<1e-4
 for step in range(20):
  if step==10:env._reset_idx(torch.arange(1,32,2,device=env.device))
  env.step(torch.zeros(32,6,device=env.device))
  print('RESTORE',step,'grip',int(env.grip.sum()),'failures',{k:int(v.sum()) for k,v in env.last_diagnostics.items() if k.startswith('failure')},flush=True)
  assert env.grip.all() and not env.failure.any(), 'Restored physical grip failed'
 print('LOCAL_TARGETS',(env._target_fruit().data.root_link_pos_w-env.scene.env_origins).tolist(),flush=True)
 print('GRASP_DISTANCES',env.distance.tolist(),flush=True)
 print('DONE',flush=True)
except Exception:
 import traceback;traceback.print_exc();failed=True
finally:
 from harvest_rl.lifecycle import close_simulator
 close_simulator(app,locals().get('env'),failed)
