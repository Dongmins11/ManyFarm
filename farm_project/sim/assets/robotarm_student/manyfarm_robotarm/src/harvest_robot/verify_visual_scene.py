"""Static RL scenery regression snapshot. No policy, training or hardware calls.

Run separately with --visual-scene legacy / greenhouse_v1 and compare 'physical'.
Small two-environment fixture checks cloning and episode RNG independently of RGB.
"""
import argparse
import hashlib
import json
from pathlib import Path
from isaaclab.app import AppLauncher

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--visual-scene',choices=('legacy','greenhouse_v1'),required=True)
p.add_argument('--output',type=Path,required=True)
AppLauncher.add_app_launcher_args(p)
a=p.parse_args();a.kit_args=(a.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(a).app;env=None;failed=False
try:
    from pxr import Usd,UsdPhysics
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    settings=TaskSettings(task='harvest',num_fruits=3,sequence=True,random_colors=True,
        background='grove',seed=42,mass=.009)
    env=HarvestEnv(settings,num_envs=2,device=a.device,visual_scene=a.visual_scene)
    obs,_=env.reset()
    inventory={};new_physics=[]
    for prim in Usd.PrimRange(env.sim.stage.GetPseudoRoot(),Usd.TraverseInstanceProxies()):
        schemas=[s for s in prim.GetAppliedSchemas() if s.startswith(('Physics','Physx'))]
        attrs={x.GetName():str(x.Get()) for x in prim.GetAttributes() if x.GetName().startswith(('physics:','physx'))}
        relationships={r.GetName():[str(t) for t in r.GetTargets()] for r in prim.GetRelationships() if 'physics' in r.GetName().lower()}
        if schemas or attrs or relationships:
            inventory[str(prim.GetPath())]=dict(schemas=schemas,attrs=attrs,relationships=relationships)
            if '/GreenhouseVisual/' in str(prim.GetPath()):new_physics.append(str(prim.GetPath()))
    assert not new_physics,new_physics
    physical=dict(task=env.settings.as_dict(),robot_root=env.robot.data.root_state_w.cpu().tolist(),
        joint_positions=env.robot.data.joint_pos.cpu().tolist(),
        fruits=[f.data.root_state_w.cpu().tolist() for f in env.fruits],
        anchors=env.anchors.cpu().tolist(),threshold=env.threshold.cpu().tolist(),
        colors=env.color_ids.cpu().tolist(),observation=obs['policy'].cpu().tolist(),
        physics_inventory=inventory,step_dt=env.step_dt,physics_dt=env.sim.get_physics_dt())
    report=dict(visual_scene=env.visual_scene,physical=physical,
        physical_sha256=hashlib.sha256(json.dumps(physical,sort_keys=True).encode()).hexdigest(),
        new_physics_api_count=len(new_physics),note='Static cloning/RNG/physics invariance; not a harvest success-rate evaluation')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(report,f,indent=2)
    print('VISUAL_INVARIANCE_SNAPSHOT',a.output,report['physical_sha256'],flush=True)
except Exception:
    import traceback
    traceback.print_exc();failed=True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app,env,failed)
