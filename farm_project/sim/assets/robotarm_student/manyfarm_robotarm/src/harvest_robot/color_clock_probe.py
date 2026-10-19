"""Integration checks for reset colors, USD visibility, partial reset and target clocks."""
import argparse
import json
from pathlib import Path
from isaaclab.app import AppLauncher
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output",type=Path,default=Path("outputs/harvest_rl/color_clock_probe.json"))
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args()
args.kit_args=(args.kit_args or "")+" --/plugins/carb.tasking.plugin/threadCount=1"
app=AppLauncher(args).app
failed=False
env=None
try:
    import torch
    from pxr import UsdGeom
    from harvest_rl.env import HarvestEnv
    from harvest_rl.settings import TaskSettings
    env=HarvestEnv(TaskSettings(task="harvest",sequence=True,random_colors=True,timeout_scope="fruit",
        attachment_version=3,num_fruits=4,episode_s=20),num_envs=2,device=args.device)
    samples=[]
    def check_visuals():
        for e in range(2):
            for i in range(4):
                color=int(env.color_ids[e,i])
                for code,name in enumerate(("Red","Yellow","Green")):
                    visual=UsdGeom.Imageable(env.sim.stage.GetPrimAtPath(f"/World/envs/env_{e}/Fruit_{i}/Visual_{name}"))
                    assert (visual.ComputeVisibility()!="invisible") == (code==color)
                assert bool(env.ripe[e,i]) == (color!=2)
        assert bool(env._t(env.ripe).all())
    for _ in range(5):
        env.reset();check_visuals();samples.append(env.color_ids.cpu().tolist())
    old=env.color_ids[1].clone()
    env._reset_idx(torch.tensor([0],device=env.device));check_visuals()
    assert torch.equal(old,env.color_ids[1])
    while not bool((env.ripe.sum(-1)>=2).all()):env.reset()
    env.step(torch.zeros((2,env.cfg.action_space),device=env.device))
    env.episode_length_buf[:]=torch.tensor([390,500],device=env.device)
    env.target_start_step[:]=torch.tensor([0,450],device=env.device)
    old_target=int(env.target_index[0]);env.collected[0,old_target]=True
    env.pending_next[0]=True
    env._advance_target()
    elapsed=env._target_elapsed_steps().tolist()
    assert elapsed==[0,50] and int(env.target_index[0])!=old_target
    assert int(env.target_start_step[1])==450
    env.episode_length_buf[0]+=env.max_episode_length
    _,timeout=env._get_dones()
    assert timeout.tolist()==[True,False]
    report={"colors_by_reset":samples,"partial_reset_preserved_other_env":True,
        "visuals_match_ripeness":True,"elapsed_after_target_switch":elapsed,"timeout":timeout.tolist()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)
except Exception:
    import traceback
    traceback.print_exc();failed=True
finally:
    from harvest_rl.lifecycle import close_simulator
    close_simulator(app,env,failed)
