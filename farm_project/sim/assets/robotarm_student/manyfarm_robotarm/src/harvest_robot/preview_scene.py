"""Render one randomized harvest scene without stepping physics or running a policy.

Uses the preserved training USD/workspace, not the current source URDF.
"""
import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--num-fruits", type=int, default=5, choices=range(3, 9))
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--frames", type=int, default=0, help="0: keep window open")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.kit_args = (args.kit_args or "") + " --/plugins/carb.tasking.plugin/threadCount=1"
app = AppLauncher(args).app
env = None
failed = False
try:
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    env = HarvestEnv(TaskSettings(task="harvest", sequence=True, random_colors=True,
        num_fruits=args.num_fruits, seed=args.seed, background="grove",
        attachment_version=3, timeout_scope="fruit", curriculum=1.0), num_envs=1, device=args.device)
    env.reset()
    import torch
    positions = torch.stack([f.data.root_link_pos_w[0] for f in env.fruits]) - env.scene.env_origins[0]
    lo = torch.tensor(env.settings.region_origin,device=env.device)+torch.tensor(env.settings.region_min,device=env.device)
    hi = torch.tensor(env.settings.region_origin,device=env.device)+torch.tensor(env.settings.region_max,device=env.device)
    assert bool(((positions >= lo-1e-6)&(positions <= hi+1e-6)).all())
    print("Fruit centres in cached robot frame:",positions.tolist(),flush=True)
    print("Static preview: cached training robot; no policy or physics steps.", flush=True)
    print("Fruit colors:", [ ("Red", "Yellow", "Green")[i] for i in env.color_ids[0].tolist()], flush=True)
    frame = 0
    while app.is_running() and (args.frames == 0 or frame < args.frames):
        env.sim.render()
        frame += 1
except KeyboardInterrupt:
    pass
except Exception:
    import traceback
    traceback.print_exc()
    failed = True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app, env, failed)
