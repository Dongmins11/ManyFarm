"""External assignment API smoke; terminal state injection tests lifecycle, not policy performance."""
import argparse
from isaaclab.app import AppLauncher
p=argparse.ArgumentParser(description=__doc__)
AppLauncher.add_app_launcher_args(p)
p.add_argument("--single-fruit",action="store_true")
a=p.parse_args();a.kit_args=(a.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(a).app
env=None;failed=False
try:
 import torch
 from harvest_rl.env import HarvestEnv
 from harvest_rl.settings import TaskSettings
 settings=TaskSettings(task='harvest',sequence=not a.single_fruit,target_mode='external',curriculum=1,num_fruits=1 if a.single_fruit else 3)
 env=HarvestEnv(settings,num_envs=1,device=a.device)
 env.reset()
 assert env.assignment_status=='WAIT_TARGET'
 try:env.step(torch.zeros(1,6,device=env.device))
 except RuntimeError:pass
 else:raise AssertionError('Idle step accepted')
 slot=int(env.ripe[0].nonzero()[0]);obs=env.assign_target(slot)
 assert env.assignment_status=='RUNNING' and int(env.target_index[0])==slot
 try:env.assign_target(slot)
 except RuntimeError:pass
 else:raise AssertionError('Active replacement accepted')
 env.step(torch.zeros(1,6,device=env.device))
 # Isolate terminal lifecycle from physical success criteria, which remain unchanged.
 env._update_task=lambda:None
 env.failure.zero_();env.success.fill_(True)
 done,timeout=env._get_dones()
 assert env.assignment_status=='SUCCEEDED' and not bool(done.any()|timeout.any())
 assert int(env.target_index[0])==slot
 env.reset();slot=int(env.ripe[0].nonzero()[0]);env.assign_target(slot)
 env.cancel_target()
 assert env.assignment_status=='CANCELLED'
 try:env.step(torch.zeros(1,6,device=env.device))
 except RuntimeError:pass
 else:raise AssertionError('Step after cancellation accepted')
 try:env.assign_target(slot)
 except RuntimeError:pass
 else:raise AssertionError('Cancelled assignment replaced without reset')
 print('PASS cancellation and explicit recovery; external wait, assignment, running replacement rejection, terminal no auto-reset',flush=True)
except Exception:
 import traceback;traceback.print_exc();failed=True
finally:
 from harvest_rl.lifecycle import close_simulator
 close_simulator(app,env,failed)
