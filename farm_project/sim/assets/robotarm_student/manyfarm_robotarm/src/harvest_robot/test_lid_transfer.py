#!/usr/bin/env python3
"""Open two real robot lids and measure eight-pepper gravity transfer in Isaac."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

from lid_transfer.model import (
    OUT, ROOT, TransferMonitor, inside_box, lid_spec, load_settings,
    random_poses, scene_geometry, source_paths, world_points,
)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, help="Optional Settings JSON overrides")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--trials", type=int, default=1, help="Seeds seed, seed+1, ...")
    p.add_argument("--output", type=Path, help="New results directory; default unique timestamp")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--save-images", action="store_true", help="Save overview PNG at each phase")
    p.add_argument("--export-scene", action="store_true", help="Export final USD scene per trial")
    p.add_argument("--keep-open", action="store_true", help="Keep GUI at the final state")
    p.add_argument("--fast", action="store_true", help="Run GUI without real-time pacing")
    p.add_argument("--plan", action="store_true", help="Print geometry/loading plan without starting Isaac")
    p.add_argument("--max-sim-seconds", type=float, default=0,
                   help="Optional early-stop limit; an unfinished trial fails")
    p.add_argument("--diameter", type=float, help="Pepper diameter in m (default .070)")
    p.add_argument("--length", type=float, help="Whole pepper height in m (default .075)")
    p.add_argument("--mass", type=float, help="Pepper mass in kg (default .009, nominal model)")
    p.add_argument("--offset-x", type=float, help="Carrier misalignment in world X, m")
    p.add_argument("--offset-y", type=float, help="Carrier misalignment in world Y, m")
    p.add_argument("--transport-yaw", type=float, help="Carrier heading in rad (default 0)")
    return p


def main():
    p = parser()
    args = p.parse_args()
    cfg = load_settings(args.config)
    for argument, field in (("diameter", "diameter"), ("length", "length"), ("mass", "mass"),
                            ("offset_x", "transport_offset_x"), ("offset_y", "transport_offset_y")):
        if getattr(args, argument) is not None:
            setattr(cfg, field, getattr(args, argument))
    if args.transport_yaw is not None:
        cfg.transport_yaw = args.transport_yaw
    try:
        cfg.validate()
        if args.trials < 1 or args.max_sim_seconds < 0:
            raise ValueError("trials must be positive; max-sim-seconds must be non-negative")
        if args.headless and args.keep_open:
            raise ValueError("--keep-open requires GUI mode")
        geometry = scene_geometry(cfg)
        poses = random_poses(cfg, args.seed, geometry)
    except ValueError as error:
        p.error(str(error))
    if args.plan:
        print(json.dumps(dict(settings=asdict(cfg), seeds=list(range(args.seed, args.seed + args.trials)),
            geometry={k: [v.tolist() for v in value] if isinstance(value, tuple)
                      else value.tolist() if hasattr(value, "tolist") else value
                      for k, value in geometry.items()},
            lids={name: lid_spec(name) for name in ("harvest", "transport")},
            initial_poses=poses, physics_executed=False), indent=2))
        return 0
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d_%H%M%S_%f")
    output = (args.output or OUT / stamp).resolve()
    if output.exists() and any(output.iterdir()):
        p.error(f"Output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "configuration.json").write_text(json.dumps(asdict(cfg), indent=2))
    sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in source_paths()}
    code_files = [Path(__file__), *sorted(Path(__file__).with_name("lid_transfer").glob("*.py"))]
    from importlib.metadata import version, PackageNotFoundError
    versions = {}
    for package in ("isaaclab", "isaacsim", "torch"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "unavailable"
    (output / "metadata.json").write_text(json.dumps(dict(
        sources=sources, code={str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in code_files},
        versions=versions,
        physics_device="cpu", rendering_device="gpu", physics_dt=cfg.physics_dt,
        actuation="force-limited rotary pinion + passive PhysX mimic racks",
        robot_self_collision=False, pepper_collision="full mesh convex decomposition including stem",
        friction=dict(static=.5, dynamic=.4, restitution=.02),
        scope="standalone simulation; parked bases/arms; no ROS or physical motor commands",
    ), indent=2))
    print(f"RESULTS {output}", flush=True)
    from isaaclab.app import AppLauncher
    app = AppLauncher(headless=args.headless, device="cpu", enable_cameras=args.save_images,
                      kit_args="--/plugins/carb.tasking.plugin/threadCount=1").app
    code = 2
    try:
        code = run(args, cfg, geometry, poses, output, app)
    except (Exception, KeyboardInterrupt) as error:
        import traceback
        traceback.print_exc()
        (output / "error.json").write_text(json.dumps(dict(error=repr(error), success=False), indent=2))
    finally:
        # Kit fast shutdown exits Python with status 0. Preserve failure status
        # after writing reports; the OS releases this worker's simulator context.
        if code != 0:
            import os
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)
        app.close(wait_for_replicator=False, skip_cleanup=True)
    return code


def read_state(cfg, geometry, fruits, hulls, robots):
    import numpy as np

    details = []
    finite, escaped = True, False
    for i, (fruit, hull) in enumerate(zip(fruits, hulls)):
        state = fruit.data.root_state_w[0].cpu().numpy()
        good = bool(np.isfinite(state).all())
        finite &= good
        if not good:
            details.append(dict(id=i, finite=False, in_harvest=False, in_transport=False, stable=False))
            continue
        p, q, v, w = state[:3], state[3:7], state[7:10], state[10:13]
        stable = bool(np.linalg.norm(v) <= cfg.linear_speed and np.linalg.norm(w) <= cfg.angular_speed)
        h = inside_box(p, q, hull, geometry["harvest_pose"], geometry["harvest_bounds"], cfg.boundary_tolerance)
        t = inside_box(p, q, hull, geometry["transport_box_pose"], geometry["transport_bounds"], cfg.boundary_tolerance)
        points = world_points(p, q, hull)
        # Escapes are permanent low falls or bodies far outside the receiving area.
        cargo_z = geometry["transport_box_pose"][2, 3] + geometry["transport_bounds"][0][2]
        fallen = bool(points[:, 2].max() < cargo_z - .02)
        far = bool(np.linalg.norm(p[:2] - geometry["harvest_pose"][:2, 3]) > .65)
        escaped |= fallen or far
        details.append(dict(id=i, finite=True, position=p.tolist(), rotation_wxyz=q.tolist(),
            linear_speed=float(np.linalg.norm(v)), angular_speed=float(np.linalg.norm(w)),
            in_harvest=h, in_transport=t, stable=stable, escaped=fallen or far))
    lids = {}
    for name, robot in robots.items():
        spec = lid_spec(name)
        q = robot.data.joint_pos[0].cpu().numpy()
        joint_finite = bool(np.isfinite(q).all() and np.isfinite(robot.data.joint_vel[0].cpu().numpy()).all())
        finite &= joint_finite
        positions = {j: float(q[robot.joint_names.index(j)]) for j in (spec["motor"], *spec["slides"])}
        angle = positions[spec["motor"]]
        slides = [positions[j] for j in spec["slides"]]
        coupling_error = max(abs(s - angle * spec["radius"]) for s in slides) if joint_finite else None
        opened = bool(joint_finite and abs(angle - spec["open_angle"]) <= cfg.motor_tolerance
            and all(abs(s - spec["travel"]) <= cfg.slide_tolerance for s in slides)
            and coupling_error <= cfg.slide_tolerance)
        effort = float(robot.data.applied_torque[0, robot.joint_names.index(spec["motor"])])
        finite &= bool(np.isfinite(effort))
        lids[name] = dict(positions={j: v if np.isfinite(v) else None for j, v in positions.items()},
            coupling_error_m=coupling_error, open=opened,
            motor_drive_effort_estimate_Nm=effort if np.isfinite(effort) else None)
    return dict(peppers=details, lids=lids, finite=bool(finite), escaped=bool(escaped),
        loaded=sum(f["in_harvest"] and f["stable"] for f in details),
        received=sum(f["in_transport"] and f["stable"] for f in details),
        in_transport=sum(f["in_transport"] for f in details))


def run(args, cfg, geometry, poses, output, app):
    import numpy as np
    import torch
    import isaaclab.sim as sim
    from isaaclab.sensors import ContactSensor, ContactSensorCfg
    from lid_transfer.scene import prepare_robot, spawn_robot, spawn_peppers, bind_materials, apply_rack_coupling

    context = sim.SimulationContext(sim.SimulationCfg(dt=cfg.physics_dt, device="cpu",
        use_fabric=False, render_interval=8, physx=sim.PhysxCfg(enable_ccd=True)))
    context.set_camera_view(eye=(1.0, -1.25, 1.15), target=(0, -.30, .50))
    ground = sim.GroundPlaneCfg(color=(.17, .18, .20))
    ground.func("/World/Ground", ground)
    light = sim.DomeLightCfg(intensity=2500)
    light.func("/World/Light", light)
    robots = {name: spawn_robot(name, prepare_robot(name, cfg, output / "assets"), cfg, geometry)
              for name in ("harvest", "transport")}
    coupling = apply_rack_coupling()
    (output / "rack_coupling.json").write_text(json.dumps(coupling, indent=2))
    fruits, hulls = spawn_peppers(cfg, poses, output / "assets/peppers")
    bind_materials()
    lid_contacts = ContactSensor(ContactSensorCfg(prim_path="/World/Transport/top_lid_.*",
        filter_prim_paths_expr=["/World/Harvest/base_footprint"], history_length=1))
    stage = sim.get_current_stage()
    # A missing native coupling must fail before a visually plausible motor demo.
    mimic = [str(p.GetPath()) for p in stage.Traverse()
             if any("PhysxMimicJointAPI" in s for s in p.GetAppliedSchemas())]
    if len(mimic) != 4:
        raise RuntimeError(f"Expected four passive PhysX mimic racks, found {mimic}")
    camera = None
    if args.save_images:
        from isaaclab.sensors import Camera, CameraCfg
        camera = Camera(CameraCfg(prim_path="/World/TransferCamera", height=720, width=960,
            update_period=0, data_types=["rgb"], spawn=sim.PinholeCameraCfg(
                focal_length=24, horizontal_aperture=36, clipping_range=(.01, 10))))
    context.reset()
    context.carb_settings.set_bool("/physics/updateToUsd", True)
    if camera:
        camera.set_world_poses_from_view(torch.tensor([[1.0, -1.25, 1.15]]),
                                         torch.tensor([[0, -.30, .50]]))

    def snapshot(folder, label):
        if camera:
            import cv2
            for _ in range(3):
                context.render()
            camera.update(cfg.physics_dt, force_recompute=True)
            rgb = camera.data.output["rgb"][0, :, :, :3].cpu().numpy()
            cv2.imwrite(str(folder / (label + ".png")), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    reports = []
    for trial in range(args.trials):
        seed = args.seed + trial
        folder = output / f"trial_{trial:03d}_seed_{seed}"
        folder.mkdir()
        poses = random_poses(cfg, seed, geometry)
        (folder / "initial_poses.json").write_text(json.dumps(poses, indent=2))
        # Initialization only. No fruit pose/velocity writes after the trial begins.
        for robot in robots.values():
            zeros = torch.zeros_like(robot.data.default_joint_pos)
            robot.write_joint_state_to_sim(zeros, zeros)
            robot.reset()
            robot.set_joint_position_target(zeros)
            robot.write_data_to_sim()
        for fruit, pose in zip(fruits, poses):
            state = fruit.data.default_root_state.clone()
            state[0, :3] = torch.tensor(pose["position"])
            state[0, 3:7] = torch.tensor(pose["rotation_wxyz"])
            state[0, 7:] = 0
            fruit.write_root_state_to_sim(state)
            fruit.reset()
        ctl = TransferMonitor(cfg)
        sim_time, steps = 0.0, 0
        prior = "LOADING"
        events = [dict(phase=prior, sim_time=0.0)]
        snapshot(folder, "00_initial")
        next_log = 0.0
        last_pace = time.monotonic()
        with (folder / "trace.jsonl").open("w") as trace:
            while app.is_running() and not ctl.finished:
                for name, robot in robots.items():
                    target = ctl.harvest_angle if name == "harvest" else ctl.transport_angle
                    robot.set_joint_position_target(torch.tensor([[target]]),
                        joint_ids=[robot.joint_names.index(lid_spec(name)["motor"])])
                    robot.write_data_to_sim()
                context.step(render=(steps % 8 == 0 and (not args.headless or camera is not None)))
                steps += 1
                sim_time = steps * cfg.physics_dt
                for obj in [*robots.values(), *fruits]:
                    obj.update(cfg.physics_dt)
                lid_contacts.update(cfg.physics_dt)
                state = read_state(cfg, geometry, fruits, hulls, robots)
                state["transport_lid_contact_with_harvest_N"] = (
                    torch.linalg.vector_norm(lid_contacts.data.force_matrix_w[0], dim=-1).cpu().tolist())
                ctl.advance(cfg.physics_dt, loaded=state["loaded"], received=state["received"],
                    escaped=state["escaped"], finite=state["finite"],
                    harvest_open=state["lids"]["harvest"]["open"],
                    transport_open=state["lids"]["transport"]["open"])
                if args.max_sim_seconds and sim_time >= args.max_sim_seconds and not ctl.finished:
                    ctl.fail("SIM_TIME_LIMIT")
                if sim_time >= next_log or ctl.phase != prior:
                    row = dict(sim_time=sim_time, phase=ctl.phase, dwell_s=ctl.dwell,
                        commanded_angles=dict(harvest=ctl.harvest_angle, transport=ctl.transport_angle), **state)
                    trace.write(json.dumps(row, allow_nan=False) + "\n")
                    trace.flush()
                    next_log = sim_time + .1
                if ctl.phase != prior:
                    events.append(dict(phase=ctl.phase, sim_time=sim_time))
                    print(f"seed={seed} t={sim_time:.2f}s {ctl.phase} "
                          f"loaded={state['loaded']}/8 received={state['received']}/8 reason={ctl.reason}", flush=True)
                    snapshot(folder, f"{len(events)-1:02d}_{ctl.phase.lower()}")
                    prior = ctl.phase
                if not args.headless and not args.fast and steps % 8 == 0:
                    wait = cfg.physics_dt * 8 - (time.monotonic() - last_pace)
                    if wait > 0:
                        time.sleep(wait)
                    last_pace = time.monotonic()
            if not ctl.finished:
                ctl.fail("GUI_CLOSED")
        final = read_state(cfg, geometry, fruits, hulls, robots)
        final["transport_lid_contact_with_harvest_N"] = state.get("transport_lid_contact_with_harvest_N")
        report = dict(seed=seed, phase=ctl.phase, success=ctl.phase == "SUCCESS", reason=ctl.reason,
            sim_time_s=sim_time, physics_steps=steps, events=events, **final)
        (folder / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
        if args.export_scene:
            stage.GetRootLayer().Export(str(folder / "final_scene.usda"))
        reports.append(report)
        summary = dict(trials_requested=args.trials, trials_completed=len(reports),
            successes=sum(r["success"] for r in reports), all_success=bool(
                len(reports) == args.trials and all(r["success"] for r in reports)), trials=reports)
        (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
        if not app.is_running():
            break
    print(f"TRANSFER RESULT {summary['successes']}/{len(reports)}; {output / 'summary.json'}", flush=True)
    if args.keep_open:
        while app.is_running():
            context.render()
            time.sleep(.03)
    return 0 if summary["all_success"] else 2


if __name__ == "__main__":
    sys.exit(main())
