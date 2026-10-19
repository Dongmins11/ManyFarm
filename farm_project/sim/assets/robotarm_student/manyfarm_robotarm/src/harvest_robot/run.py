"""Teacher training/playback, smoke test, student DAgger/playback.

Example: python src/harvest_robot/run.py train --task grasp --num-envs 32 --headless
"""
import argparse
from datetime import datetime
import importlib.metadata
import hashlib
import json
from pathlib import Path
import sys
from harvest_rl.settings import ROOT, CACHE, URDF, TaskSettings


def create_run_directory(requested):
    """Atomically reserve a fresh directory without overwriting earlier runs."""
    requested = Path(requested)
    candidate = requested
    suffix = 0
    while True:
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            if candidate != requested:
                print(f"OUTPUT_EXISTS: preserving {requested}; new run: {candidate}", flush=True)
            print(f"RUN_OUTPUT: {candidate.resolve()}", flush=True)
            return candidate
        except FileExistsError:
            suffix += 1
            candidate = requested.with_name(f"{requested.name}_{suffix:03d}")


def simulator_kit_args(existing, worker_threads):
    """Bound native task concurrency before Kit starts (PhysX startup workaround)."""
    if worker_threads < 1:
        raise ValueError("sim-worker-threads must be positive")
    key = "--/plugins/carb.tasking.plugin/threadCount"
    if any(arg.split("=",1)[0] == key for arg in existing.split()):
        raise ValueError("Use --sim-worker-threads instead of threadCount in --kit_args")
    return f"{existing} {key}={worker_threads}".strip()


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["smoke", "train", "play", "student-train", "student-play"])
    parser.add_argument("--normalization-mode", choices=["adaptive", "selective-frozen", "stage-frozen"], default="adaptive", help="selective-frozen: correct extra-fruit constants on warm-start and freeze observation statistics")
    parser.add_argument("--warm-start-arm-scale", type=float, default=1.0)
    parser.add_argument("--warm-start-noise-std", type=float, default=0.3)
    parser.add_argument("--max-noise-std", type=float, default=0.6)
    parser.add_argument("--assigned-eval", action="store_true", help="Single-fruit external assignment integration, play only, one env")
    parser.add_argument("--target-mode", choices=["nearest","random","external"], default=None)
    parser.add_argument("--transport-replay-fraction", type=float, default=None)
    parser.add_argument("--transport-start-min", type=float, default=None)
    parser.add_argument("--transport-start-max", type=float, default=None)
    parser.add_argument("--start-bank", type=str, default=None)
    parser.add_argument("--export-stage-bank", type=Path)
    parser.add_argument("--bank-size", type=int, default=512)
    parser.add_argument("--task", choices=["grasp","hold","pull","harvest","transport","place"], default=None)
    parser.add_argument("--num-envs", type=int, default=None)
    parser.add_argument("--num-fruits", type=int, default=None)
    parser.add_argument("--diameter", type=float, default=None)
    parser.add_argument("--fruit-front-range", type=float, nargs=2, metavar=("MIN_M","MAX_M"), help="Fruit centre distance from cached mount plate front edge; warm-start required to change checkpoint")
    parser.add_argument("--curriculum", type=float, default=None)
    parser.add_argument("--mass", type=float, default=None, help="Measured plastic fruit mass in kg")
    parser.add_argument("--static-friction", dest="grip_friction", type=float, default=None)
    parser.add_argument("--dynamic-friction", type=float, default=None)
    parser.add_argument("--eval-fix-fruit-normalization", action="store_true", help="Teacher play only: neutralize constant extra-fruit normalization slots; weights unchanged")
    parser.add_argument("--eval-environment-override", action="store_true", help="Teacher play only: explicitly allow recorded environment changes without learning")
    parser.add_argument("--eval-break-force", type=float, default=None, help="Explicit play-only force robustness test; saved in run metadata")
    parser.add_argument("--break-force", type=float, default=None)
    parser.add_argument("--stage-transfer", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument("--fixed-learning-rate", action="store_true")
    parser.add_argument("--entropy-coef", type=float, default=None)
    parser.add_argument("--eval-stage-normalization", action="store_true")
    parser.add_argument("--lock-attachment", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--native-detach-recovery", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--native-grasp-grace", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--attachment-version", type=int, choices=[1,2,3,4], default=None)
    parser.add_argument("--sequence", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--random-colors", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--timeout-scope", choices=["fruit","episode"], default=None)
    parser.add_argument("--background", choices=["single","grove"], default=None)
    parser.add_argument("--visual-scene", choices=["greenhouse_v1","legacy"], default="greenhouse_v1", help="Appearance only; legacy replays the previous tree/grid background")
    parser.add_argument("--episode-s", type=float, default=None)
    parser.add_argument("--valid-pull-distance", type=float, default=None, help="Minimum extension for attachment v2/v4, metres")
    parser.add_argument("--stem-response-version", type=int, choices=[1,2,3,4], default=None)
    parser.add_argument("--stem-vertical-stiffness", type=float, default=None)
    parser.add_argument("--stem-max-extension", type=float, default=None)
    parser.add_argument("--tension-axis", type=float, nargs=3, default=None, help="v4 outward pull axis in simulation world frame")
    parser.add_argument("--tension-hold-s", type=float, default=None, help="v4 continuous overload duration (default 0.12 s)")
    parser.add_argument("--lateral-stiffness-ratio", type=float, default=None, help="v4 transverse / axial stiffness (default 0.25)")
    parser.add_argument("--spring-k", type=float, default=None)
    parser.add_argument("--spring-d", type=float, default=None)
    parser.add_argument("--break-hold-s", type=float, default=None)
    parser.add_argument("--hold-force", type=float, default=None)
    parser.add_argument("--pregrasp-fraction", type=float, default=None)
    parser.add_argument("--reward-version", type=int, choices=[1,2,3,4,5,6,7,8], default=None)
    parser.add_argument("--grasp-orientation", choices=["free","horizontal"], default=None)
    parser.add_argument("--grasp-angle-tolerance", type=float, default=None, help="Initial grasp angular tolerance, radians (default 25 degrees)")
    parser.add_argument("--grasp-orientation-weight", type=float, default=None)
    parser.add_argument("--grasp-version", type=int, choices=[1,2], default=None)
    parser.add_argument("--grasp-center-tolerance", type=float, default=None, help="Grasp centre error limit in metres")
    parser.add_argument("--sim-worker-threads", type=int, default=1,
                        help="Kit native task threads; 1 avoids observed PhysX startup heap corruption")
    parser.add_argument("--use-prepared-assets", action="store_true",
                        help="Explicitly use cached USD/bank for teacher training or evaluation despite source URDF edits")
    parser.add_argument("--trace", action="store_true", help="Save env-0 per-step grasp diagnostics for play/smoke")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split",choices=["train","eval"],default=None)
    parser.add_argument("--episodes",type=int,default=100,help="Completed episodes to evaluate; --steps remains an upper bound")
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--checkpoint", type=Path, help="Teacher for play/student; student for student-play")
    parser.add_argument("--resume", type=Path, help="Teacher policy + optimizer resume; environments reset")
    parser.add_argument("--warm-start", type=Path, help="Policy/value weights only, e.g. grasp -> harvest")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--show-camera", action="store_true", help="Isaac Sim RGB panel, one environment only")
    parser.add_argument("--random-actions", action="store_true", help="Random instead of zero smoke actions")
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    try:
        args.kit_args = simulator_kit_args(args.kit_args, args.sim_worker_threads)
    except ValueError as exc:
        parser.error(str(exc))
    if args.resume and args.warm_start:
        parser.error("--resume and --warm-start are mutually exclusive")
    if args.mode in ("play","student-train","student-play") and not args.checkpoint:
        parser.error("This mode requires an explicit --checkpoint")
    if args.mode.startswith("student") or args.show_camera:
        args.enable_cameras = True
    args.num_envs = args.num_envs or (1 if args.mode.endswith("play") or args.show_camera else 32)
    if args.show_camera and args.num_envs != 1:
        parser.error("--show-camera requires --num-envs 1")
    if args.steps < 1 or args.iterations < 1 or args.num_envs < 1:
        parser.error("steps, iterations and num-envs must be positive")
    return args


def validate_prepared_bank(cache, prep):
    import numpy as np
    for name in ("harvest_robot.usd", "harvest_training.urdf", "workspace.npz"):
        if not (cache / name).is_file():
            raise ValueError(f"Missing prepared asset: {cache / name}")
    with np.load(cache / "workspace.npz", allow_pickle=False) as bank:
        digest = hashlib.sha256(bank["q"].tobytes()+bank["points"].tobytes()+bank["home"].tobytes()).hexdigest()
    if digest != prep.get("workspace_sha256"):
        raise ValueError("Prepared workspace contents do not match preparation.json")


def load_settings(args):
    source = args.resume or args.checkpoint or args.warm_start
    if getattr(args,"eval_fix_fruit_normalization",False) and (args.mode != "play" or not args.checkpoint or args.warm_start or args.resume):
        raise ValueError("--eval-fix-fruit-normalization requires play --checkpoint only")
    eval_override = getattr(args,"eval_environment_override",False)
    if eval_override and (args.mode != "play" or not args.checkpoint or args.warm_start or args.resume):
        raise ValueError("--eval-environment-override requires play --checkpoint only")
    if eval_override:
        print("EVALUATION_ENVIRONMENT_OVERRIDE: evaluating unchanged policy on explicit task settings",flush=True)
    saved = None
    if source:
        if not source.is_file():
            raise FileNotFoundError(source)
        saved = json.loads((source.parent / "run.json").read_text())
        if saved.get("current_asset") and not getattr(args,"current_asset_adapter",False):
            raise ValueError("Current-robot checkpoint requires eval_current_pair.py/current robot adapter; do not replay on legacy assets")
        if saved["task"].get("contract_version") != 2:
            raise ValueError("Legacy checkpoint uses unverified materials/old observation semantics. Start v2 grasp training; do not silently resume it.")
        if "gripper_hold_error" not in saved["task"] and not args.warm_start:
            raise ValueError("This v2 checkpoint predates compliant hold. Use --warm-start for the controller change, and explicitly select rubber friction if appropriate.")
    if saved:
        saved["task"].setdefault("stem_response_version", 1)
        saved["task"].setdefault("native_grasp_grace", False)
        saved["task"].setdefault("native_detach_recovery", False)
        saved["task"].setdefault("lock_attachment", False)
        saved["task"].setdefault("stage_transfer", False)
        saved["task"].setdefault("random_colors", False)
        saved["task"].setdefault("timeout_scope", "episode")
        saved["task"].setdefault("attachment_version", 1)
        saved["task"].setdefault("grasp_version", 1)
        saved["task"].setdefault("reward_version", 1)
        saved["task"].setdefault("pregrasp_fraction", 0.0)
    settings = TaskSettings(**saved["task"]) if saved else TaskSettings()
    settings.seed = args.seed
    settings.workspace_split = args.split or ("eval" if args.mode in ("play","student-play") else "train")
    for name in ("transport_replay_fraction", "transport_start_min", "transport_start_max", "start_bank", "stage_transfer", "lock_attachment", "native_detach_recovery", "native_grasp_grace", "target_mode", "task", "num_fruits", "diameter", "curriculum", "mass", "grip_friction", "dynamic_friction", "break_force", "attachment_version", "sequence", "random_colors", "timeout_scope", "background", "episode_s", "valid_pull_distance", "spring_k", "spring_d", "stem_response_version", "stem_vertical_stiffness", "stem_max_extension", "tension_axis", "tension_hold_s", "lateral_stiffness_ratio", "break_hold_s", "hold_force", "pregrasp_fraction", "reward_version", "grasp_version", "grasp_orientation", "grasp_angle_tolerance", "grasp_orientation_weight", "grasp_center_tolerance"):
        value = getattr(args,name,None)
        if value is not None:
            if saved and not args.warm_start and not eval_override and value != getattr(settings,name):
                raise ValueError(f"{name} differs from checkpoint. Use --warm-start for curriculum/task changes.")
            setattr(settings,name,value)
            if name == "diameter":
                settings.length = value*.075/.070
    front_range = getattr(args,"fruit_front_range",None)
    if front_range is not None:
        near,far = front_range
        if not 0 <= near < far:
            raise ValueError("fruit-front-range requires 0 <= min < max")
        if saved and not args.warm_start and not eval_override and (near != settings.region_min[0] or far != settings.region_max[0]):
            raise ValueError("Fruit region differs from checkpoint; use --warm-start")
        settings.region_min = (near,*settings.region_min[1:])
        settings.region_max = (far,*settings.region_max[1:])
    # A curriculum checkpoint must still be evaluated from ordinary HOME resets.
    if args.mode in ("play", "student-play"):
        settings.pregrasp_fraction = 0.0
    evaluation_force = getattr(args, "eval_break_force", None)
    if evaluation_force is not None:
        if args.mode != "play":
            raise ValueError("--eval-break-force is for teacher play only")
        settings.break_force = evaluation_force
        print(f"EVALUATION_FORCE_OVERRIDE: {evaluation_force} N nominal (+/-20%)", flush=True)
    if getattr(args,"eval_stage_normalization",False) and (args.mode != "play" or not args.checkpoint):
        raise ValueError("--eval-stage-normalization requires play --checkpoint")
    if getattr(args,"export_stage_bank",None) and (args.mode != "play" or settings.task not in ("pull","transport")):
        raise ValueError("Stage bank collection requires play pull/transport")
    settings.validate()
    if getattr(args, "assigned_eval", False):
        if args.mode != "play" or args.num_envs != 1 or settings.num_fruits != 1 or settings.sequence or settings.task != "harvest":
            raise ValueError("--assigned-eval requires play, one env, single-fruit harvest checkpoint")
        settings.target_mode = "external"
        settings.validate()
    if settings.target_mode == "external" and not getattr(args, "assigned_eval", False):
        raise ValueError("External mode is a single-env Python assign_target API; use random for PPO and standard play")
    if settings.target_mode != "nearest" and args.mode.startswith("student"):
        raise ValueError("Assigned-target Student inputs are not implemented yet")
    # Never silently evaluate a checkpoint on a different robot model.
    prep = json.loads((CACHE / "preparation.json").read_text())
    use_prepared = getattr(args, "use_prepared_assets", False)
    if use_prepared:
        if args.mode not in ("train", "play", "student-play") or (args.mode == "train" and args.checkpoint):
            raise ValueError("--use-prepared-assets supports teacher training or checkpoint evaluation")
        validate_prepared_bank(CACHE, prep)
        print("PREPARED_ASSETS: cached training USD and workspace; current source URDF is not used", flush=True)
    elif prep["sha256"] != hashlib.sha256(URDF.read_bytes()).hexdigest():
        raise ValueError("Original URDF changed. For an existing checkpoint use play --use-prepared-assets with its matching cache; do not overwrite the cache with prepare.py before preserving it.")
    if saved and saved["asset"]["sha256"] != prep["sha256"]:
        raise ValueError("Robot asset hash differs from checkpoint")
    if saved and saved["asset"].get("workspace_sha256") != prep.get("workspace_sha256"):
        raise ValueError("Workspace/home seed bank differs from checkpoint. Restore its preparation files first.")
    return settings


def main():
    args = arguments()
    if not 0 <= args.warm_start_arm_scale <= 1:
        raise ValueError("warm-start-arm-scale must be between zero and one")
    if not 0.05 <= args.warm_start_noise_std <= args.max_noise_std:
        raise ValueError("Require 0.05 <= warm-start-noise-std <= max-noise-std")
    if args.mode == "train" and args.normalization_mode in ("selective-frozen", "stage-frozen") and not (args.warm_start or args.resume):
        raise ValueError("Frozen normalization training requires warm-start or resume")
    settings = load_settings(args)
    if args.warm_start_arm_scale != 1 and (args.mode != "train" or not args.warm_start or settings.task != "transport"):
        raise ValueError("Arm output scaling is only for explicit transport warm-start")
    from isaaclab.app import AppLauncher
    print("SIM_WORKER_THREADS", args.sim_worker_threads, flush=True)
    app = AppLauncher(args).app
    env = None
    runner = None
    failed = False
    trace_file = None
    try:
        import torch
        from harvest_rl.env import HarvestEnv
        from harvest_rl.policy import teacher_config
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from rsl_rl.runners import OnPolicyRunner
        env = HarvestEnv(settings, num_envs=args.num_envs, device=args.device, cameras=args.enable_cameras,
                         visual_scene=args.visual_scene,
                         render_mode="rgb_array" if args.enable_cameras else None)
        out = args.output or ROOT / "runs/harvest_rl" / f"{settings.task}_{args.mode}_{datetime.now():%Y%m%d_%H%M%S}"
        out = create_run_directory(out)
        config = teacher_config()
        config["seed"] = settings.seed
        if args.learning_rate is not None:
            if args.learning_rate <= 0: raise ValueError("learning-rate must be positive")
            config["algorithm"]["learning_rate"] = args.learning_rate
        if args.fixed_learning_rate: config["algorithm"]["schedule"] = "fixed"
        if args.entropy_coef is not None:
            if args.entropy_coef < 0: raise ValueError("entropy-coef must be nonnegative")
            config["algorithm"]["entropy_coef"] = args.entropy_coef
        meta = {"task": settings.as_dict(), "mode": args.mode, "num_envs": args.num_envs,
            "observation_dim": 82, "action_dim": 6,
            "teacher": config, "command": sys.argv,
            "normalization_mode": args.normalization_mode,
            "start_bank_sha256": env.start_bank.sha256 if env.start_bank else None,
            "exploration": {"warm_start_arm_scale":args.warm_start_arm_scale, "warm_start_reset_std": args.warm_start_noise_std if args.warm_start else None, "minimum": 0.05, "maximum": args.max_noise_std, "warm_start_normalizer_prior_count": 8192, "constant_feature_std_threshold": 1e-4},
            "runtime": {"use_prepared_assets": args.use_prepared_assets, "sim_worker_threads": args.sim_worker_threads, "kit_args": args.kit_args},
            "material_colliders": env.material_colliders, "visual_scene": env.visual_scene,
            "asset": json.loads((CACHE / "preparation.json").read_text()),
            "versions": {n: importlib.metadata.version(n) for n in ("isaacsim","isaaclab","rsl-rl-lib","torch")}}
        meta["source_hashes"] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (ROOT / "src/harvest_robot").rglob("*.py")}
        (out / "run.json").write_text(json.dumps(meta, indent=2))
        print("RUN_DIRECTORY", out, flush=True)
        if args.export_stage_bank:
            if args.export_stage_bank.exists():raise FileExistsError(args.export_stage_bank)
            from harvest_rl.stage_bank import StageBankCollector
            env.bank_collector=StageBankCollector(settings,args.checkpoint,args.bank_size)
        wrapped = RslRlVecEnvWrapper(env, clip_actions=1.0)
        obs = wrapped.get_observations()
        runner = None
        if args.mode not in ("smoke", "student-play"):
            runner = OnPolicyRunner(wrapped, config, str(out) if args.mode == "train" else None, device=args.device)
            source = args.resume or args.warm_start or args.checkpoint
            if source:
                runner.load(str(source), load_optimizer=bool(args.resume))
                if args.warm_start:
                    runner.current_learning_iteration = 0
                if args.eval_stage_normalization:
                    from harvest_rl.exploration import prepare_stage_normalizers
                    changes=prepare_stage_normalizers(runner.alg.policy)
                    (out / "normalization_override.json").write_text(json.dumps(changes,indent=2))
                if args.eval_fix_fruit_normalization:
                    from harvest_rl.exploration import correct_unused_fruit_normalization
                    changes=correct_unused_fruit_normalization(runner.alg.policy)
                    (out / "normalization_override.json").write_text(json.dumps(changes,indent=2))
        if args.mode == "train":
            from harvest_rl.exploration import configure_exploration, adapt_warm_start_normalizers
            if args.normalization_mode == "stage-frozen":
                from harvest_rl.exploration import prepare_stage_normalizers
                changes=prepare_stage_normalizers(runner.alg.policy)
                (out / "normalization_override.json").write_text(json.dumps(changes,indent=2))
            elif args.normalization_mode == "selective-frozen":
                from harvest_rl.exploration import freeze_normalizers, correct_unused_fruit_normalization
                if args.warm_start:
                    changes=correct_unused_fruit_normalization(runner.alg.policy)
                    (out / "normalization_override.json").write_text(json.dumps(changes,indent=2))
                freeze_normalizers(runner.alg.policy)
            elif args.warm_start:
                adapt_warm_start_normalizers(runner.alg.policy)
            if args.warm_start and args.warm_start_arm_scale != 1:
                from harvest_rl.exploration import scale_warm_start_arm
                scale_warm_start_arm(runner.alg.policy,args.warm_start_arm_scale)
            noise_guard = configure_exploration(runner.alg.policy,runner.alg.optimizer,
                reset_std=args.warm_start_noise_std if args.warm_start else None,
                maximum=args.max_noise_std)
            runner.learn(num_learning_iterations=args.iterations, init_at_random_ep_len=False)
            runner.save(str(out / "teacher_final.pt"))
            print("TEACHER_SAVED", out / "teacher_final.pt", flush=True)
            (out / "metrics.json").write_text(json.dumps(env.episode_metrics,indent=2))
        elif args.assigned_eval:
            from harvest_rl.assigned_eval import evaluate
            evaluate(env, wrapped, runner.get_inference_policy(device=args.device), args, out, app)
        elif args.mode == "student-train":
            from harvest_rl.student import train_student
            train_student(env, wrapped, runner.get_inference_policy(device=args.device), args, out)
        else:
            policy = runner.get_inference_policy(device=args.device) if runner else None
            if args.mode == "student-play":
                from harvest_rl.policy import VisionStudent, History
                model = VisionStudent().to(args.device).eval()
                model.load_state_dict(torch.load(args.checkpoint, map_location=args.device, weights_only=True)["student"])
                history = History(*env.student_observations())
            if args.trace:
                trace_file = (out / "grasp_trace.jsonl").open("w")
            for step in range(args.steps):
                if not app.is_running():
                    break
                with torch.inference_mode():
                    if args.mode == "student-play":
                        action = model(history.rgb, history.proprio)
                    elif policy:
                        action = policy(obs)
                    else:
                        action = torch.rand(args.num_envs,6,device=args.device)*2-1 if args.random_actions else torch.zeros(args.num_envs,6,device=args.device)
                    obs, reward, done, extras = wrapped.step(action)
                    if not torch.isfinite(reward).all() or not torch.isfinite(obs["policy"]).all():
                        raise FloatingPointError("Smoke/play produced non-finite values")
                    if args.mode == "student-play":
                        history.update(*env.student_observations(), done.bool())
                if trace_file:
                    record = {key: value[0].item() for key,value in env.last_diagnostics.items()}
                    record.update(step=step, done=bool(done[0]))
                    trace_file.write(json.dumps(record)+"\n")
                if args.show_camera:
                    show_camera(env)
                if step % 100 == 0:
                    print("STEP", step, "reward", reward.mean().item(), "metrics", env.episode_metrics, flush=True)
                if env.bank_collector is not None and env.bank_collector.count >= args.bank_size:
                    break
                if args.mode in ("play","student-play") and env.episode_metrics["episodes"] >= args.episodes:
                    break
            if env.bank_collector is not None:
                env.bank_collector.save(args.export_stage_bank)
            print("FINAL_METRICS", env.episode_metrics, flush=True)
            (out / "metrics.json").write_text(json.dumps(env.episode_metrics, indent=2))
        counts = {key: int(value.item()) for key,value in env.diagnostic_counts.items()}
        (out / "diagnostics.json").write_text(json.dumps({"env_steps": env.diagnostic_steps,
            "counts": counts, "note": "Overlapping step-level categories, not episode failure rates"}, indent=2))
        if args.enable_cameras:
            from PIL import Image
            rgb, _ = env.student_observations()
            Image.fromarray(rgb[0].detach().cpu().numpy()).save(out / "wrist_rgb.png")
            env.render()
            for _ in range(3):
                env.sim.render()
            Image.fromarray(env.render()).save(out / "scene.png")
    except Exception:
        failed = True
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        raise
    finally:
        if trace_file is not None:
            trace_file.close()
        if runner is not None and runner.writer is not None:
            runner.writer.close()
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,env,failed)


def show_camera(env):
    import numpy as np
    import omni.ui as ui
    if not hasattr(env, "_student_camera_window"):
        env._student_camera_provider = ui.ByteImageProvider()
        env._student_camera_window = ui.Window("Student wrist RGB - actual policy input",width=520,height=430)
        with env._student_camera_window.frame:
            ui.ImageWithProvider(env._student_camera_provider,width=512,height=384)
    rgb, _ = env.student_observations()
    pixels = rgb[0].detach().cpu().numpy()
    h,w = pixels.shape[:2]
    rgba = np.dstack((pixels,np.full((h,w,1),255,dtype=np.uint8)))
    env._student_camera_provider.set_bytes_data(rgba.flatten().data,[w,h])


if __name__ == "__main__":
    main()
