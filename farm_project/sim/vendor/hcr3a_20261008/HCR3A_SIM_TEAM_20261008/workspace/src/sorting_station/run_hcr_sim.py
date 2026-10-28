#!/usr/bin/env python3
"""Isaac Sim HCR-3A station: storage, approximate 6-axis robot, four intake lanes."""

import argparse
from pathlib import Path
from isaaclab.app import AppLauncher

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path)
p.add_argument(
    "--steps", type=int, default=0, help="Finite physics steps; 0 runs until GUI quit"
)
p.add_argument("--auto-start", action="store_true")
p.add_argument(
    "--auto-roi",
    action="store_true",
    help="Projection-derived ROIs for smoke testing; default manual",
)
p.add_argument("--pepper-per-lane", type=int, default=1,
    help="Transport demo: 1 = 4 peppers, 2 = 8 peppers; preloaded accepts longer queues")
p.add_argument("--payload-layout", choices=("random", "ordered"), default=None,
    help="Cargo loading: random gravity-settled pile (default), or legacy ordered replay")
p.add_argument("--payload-seed", type=int, default=None, help="Reproducible random cargo seed (default 43)")
p.add_argument("--unload-only", action="store_true", help="Start cargo loading/discharge only, without sorting")
p.add_argument("--stop-after-sorted", type=int, default=0,
    help="Standalone verification only: exit after N completed pick/transport cycles (0 = full batch)")
p.add_argument("--preloaded", action="store_true", help="Legacy test: peppers already on intake, no transport")
p.add_argument(
    "--modbus",
    action="store_true",
    help="Simulated HCR client for local ROS server, 127.0.0.1:1502 only",
)
p.add_argument("--camera-fps", type=int, default=15)
p.add_argument("--no-camera-window", action="store_true")
p.add_argument("--debug-contacts", action="store_true")
AppLauncher.add_app_launcher_args(p)
# Single-station physics: CPU supports PhysX kinematic targets for the
# existing URDF mechanisms; rendering still uses the NVIDIA GPU.
p.set_defaults(device="cpu")
args = p.parse_args()
if not args.preloaded and args.device != "cpu":
    p.error("Existing transport URDF requires --device cpu for PhysX kinematic targets (GPU rendering remains enabled)")
if not args.preloaded and args.pepper_per_lane not in (0, 1, 2):
    p.error("Original cargo box presets support 4 or 8 peppers; use --pepper-per-lane 1 or 2, or --preloaded for longer queues")
if args.stop_after_sorted < 0 or (args.stop_after_sorted and args.modbus):
    p.error("--stop-after-sorted requires a non-negative value and standalone mode (without --modbus)")
if args.unload_only and (args.preloaded or args.modbus):
    p.error("--unload-only requires standalone transport mode")
args.enable_cameras = True
app = AppLauncher(args).app

import json, math, hashlib, sys
import cv2
import torch
import numpy as np
import isaaclab.sim as sim
from isaaclab.sensors import Camera, CameraCfg
from hcr_sim.model import ROOT, OUT, load_config, pickup_points, ramp_surface_z
from hcr_sim.scene import create_station, prepare_robot, spawn_robot, spawn_peppers
from hcr_sim.vision import Vision
from hcr_sim.control import Sorter
from pxr import Usd, UsdGeom


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config(args.config) if args.config else load_config()
    cfg['transport'].setdefault('payload_layout', 'random')
    cfg['transport'].setdefault('payload_seed', 43)
    if args.payload_layout is not None:
        cfg['transport']['payload_layout'] = args.payload_layout
    if args.payload_seed is not None:
        cfg['transport']['payload_seed'] = args.payload_seed
    (OUT / "configuration.json").write_text(json.dumps(cfg, indent=2))
    recipe = [
        ROOT / "src/smartfarm_description/scripts/generate_hcr3a.py",
        ROOT / "src/smartfarm_description/scripts/hcr3a_environment.py",
        ROOT / "src/sorting_station/run_hcr_sim.py",
        ROOT / "src/sorting_station/sorting_sim/assets.py",
        *sorted((ROOT / "src/smartfarm_description/meshes/pepper").glob("*.usdc")),
        ROOT / "src/smartfarm_description/meshes/pepper/manifest.json",
        *sorted((ROOT / "src/smartfarm_description/meshes/pepper/textures").glob("*")),
        *sorted((ROOT / "src/sorting_station/hcr_sim").glob("*.py")),
    ]
    if not args.preloaded:
        from hcr_sim.transport_asset import source_paths
        recipe += source_paths()
    metadata = {
        "config_sha256": hashlib.sha256(
            json.dumps(cfg, sort_keys=True).encode()
        ).hexdigest(),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in recipe
        },
        "assisted_grasp": True,
        "robot_model": "functional approximation",
        "device": args.device,
        "physics_dt": 1 / 240,
    }
    (OUT / "metadata.json").write_text(json.dumps(metadata, indent=2))
    physics_dt = 1 / 240
    context = sim.SimulationContext(
        sim.SimulationCfg(dt=physics_dt, device=args.device, use_fabric=args.device != "cpu")
    )
    context.set_camera_view(eye=(2.1, -2.5, 1.8), target=(.45, 0, .25))
    sim.GroundPlaneCfg(color=(0.16, 0.17, 0.18)).func(
        "/World/Ground", sim.GroundPlaneCfg(color=(0.16, 0.17, 0.18))
    )
    light = sim.DomeLightCfg(intensity=2200, color=(1.0, 1.0, 1.0))
    light.func("/World/Light", light)
    create_station(cfg)
    usd = prepare_robot(cfg)
    robot = spawn_robot(usd, cfg, args.debug_contacts)
    fruits = spawn_peppers(cfg, args.pepper_per_lane, in_transport=not args.preloaded)
    transport = None
    if not args.preloaded:
        from hcr_sim.transport import Transport
        transport = Transport(cfg, fruits)
    cc = cfg["camera"]
    cam = Camera(
        CameraCfg(
            prim_path="/World/SortingCamera",
            update_period=1 / args.camera_fps,
            update_latest_camera_pose=True,
            height=cc["height"],
            width=cc["width"],
            data_types=["rgb"],
            spawn=sim.PinholeCameraCfg(
                focal_length=24,
                horizontal_aperture=2
                * 24
                * math.tan(math.radians(cc["horizontal_fov_deg"]) / 2),
                clipping_range=(0.01, 10),
            ),
        )
    )
    overview = Camera(
        CameraCfg(
            prim_path="/World/OverviewCamera",
            update_period=1.0,
            update_latest_camera_pose=True,
            height=640,
            width=960,
            data_types=["rgb"],
            spawn=sim.PinholeCameraCfg(
                focal_length=24, horizontal_aperture=36, clipping_range=(0.01, 10)
            ),
        )
    )
    contact = None
    if args.debug_contacts:
        from isaaclab.sensors import ContactSensor, ContactSensorCfg

        contact = ContactSensor(
            ContactSensorCfg(prim_path="/World/HCRRobot/.*", history_length=1)
        )
    context.reset()
    if args.device == "cpu":
        # AppLauncher rendering experience defaults to Fabric/disabled USD
        # writes. CPU physics needs actual body poses mirrored into USD for RGB.
        context.carb_settings.set_bool("/physics/updateToUsd", True)
    if transport:
        transport.initialize()
    robot.update(physics_dt)
    arm_ids = [robot.joint_names.index("joint" + str(i)) for i in range(1, 7)]
    jaw_ids = [robot.joint_names.index(n) for n in ["left_jaw", "right_jaw"]]
    ctl = Sorter(cfg, robot, fruits)
    ctl.arm_ids = arm_ids
    jp = robot.data.default_joint_pos.clone()
    jp[:, arm_ids] = torch.tensor(ctl.q, device=robot.device, dtype=torch.float32)
    jp[:, jaw_ids] = ctl.open_jaw
    robot.write_joint_state_to_sim(jp, torch.zeros_like(jp))
    robot.set_joint_position_target(jp)
    cam.set_world_poses_from_view(
        torch.tensor([cc["eye"]], device=cam.device),
        torch.tensor([cc["target"]], device=cam.device),
    )
    overview.set_world_poses_from_view(
        torch.tensor([[1.8, -2.3, 1.6]], device=overview.device),
        torch.tensor([[.45, 0, .25]], device=overview.device),
    )
    if transport and transport.phase == 'LOADING':
        cargo_eye = (cfg['transport']['start_front_x'] + .3, -.38, .82)
        cargo_target = (cfg['transport']['start_front_x'] + .15, 0., .33)
        context.set_camera_view(eye=cargo_eye, target=cargo_target)
        overview.set_world_poses_from_view(
            torch.tensor([cargo_eye], device=overview.device),
            torch.tensor([cargo_target], device=overview.device))
    vision = Vision(cfg, gui=not args.headless and not args.no_camera_window)
    # Output is separate from real camera state and production journal.
    (OUT / "teaching.json").write_text(
        json.dumps({"approximate_model": True, "poses": ctl.poses}, indent=2)
    )
    client = None
    remote_state = 1
    ack = done = 0
    remote_command = 0
    previous_batch_active = False
    print("WARMUP camera render", flush=True)
    for _ in range(3):
        context.step()
        robot.update(physics_dt)
        cam.update(physics_dt, force_recompute=True)
        overview.update(physics_dt, force_recompute=True)
    print("WARMUP done", flush=True)
    if args.modbus:
        from hcr_sim.link import SimHCRLink

        client = SimHCRLink()
    # Pickup guides use camera geometry, never object color or segmentation.
    if cam.is_initialized:
        # This does not read object color: pixel colors still go through HSV.
        from scipy.spatial.transform import Rotation

        q = cam.data.quat_w_ros[0].cpu().numpy()
        R = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
        eye = cam.data.pos_w[0].cpu().numpy()
        K = cam.data.intrinsic_matrices[0].cpu().numpy()
        for n, world in pickup_points(cfg).items():
            world = world.copy()
            world[0] = cfg["intake"]["low_x"] + 0.020
            world[2] = (
                ramp_surface_z(cfg, world[0]) + cfg["physics"]["pepper_length"] / 2
            )
            local = R.T @ (world - eye)
            uv = (K @ local)[:2] / local[2]
            # Front-facing body patch avoids stem pixels and the next fruit.
            # Uses camera geometry only; no object color or render segmentation.
            vision.guides[n] = [float(uv[0]), float(uv[1]-19)]
            if args.auto_roi:
                vision.rois[n] = [int(uv[0] - 20), int(uv[1] - 26), 40, 14]
    if args.auto_roi:
        vision.rois = {
            n: [max(0, r[0]), max(0, r[1]), r[2], r[3]] for n, r in vision.rois.items()
        }
        from hcr_sim.vision import real

        real.validate_rois(vision.rois, cc["width"], cc["height"])
        print("AUTO ROI", vision.rois, flush=True)
    if args.unload_only:
        transport.start(0)
    elif args.auto_start and not args.modbus:
        ctl.start()
        if transport:
            transport.start(0)
    ready = False
    states = {}
    count = 0
    last_camera = -1
    last_remote = -1
    scan_after = 1.0
    last_phase = None
    last_supply = None
    validation_limit_reached = False
    try:
        while app.is_running() and (not args.steps or count < args.steps):
            now = count * physics_dt
            if transport:
                transport.tick(now)
                if transport.error:
                    ctl.fail(transport.error)
            if client and client.latest is not None and now - last_remote >= 0.1:
                command, job, request, active, hb = client.latest
                if active and not previous_batch_active:
                    ctl.counts = [0, 0]
                    if transport:
                        transport.start(now)
                previous_batch_active = bool(active)
                last_remote = now
                if client.error:
                    ctl.fail(client.error)
                if ctl.phase == "ERROR":
                    remote_state = 4
                elif (
                    remote_state == 1
                    and active
                    and request
                    and job != done
                    and command in (11, 12, 21, 22, 31, 32, 41, 42)
                    and ready
                    and (not transport or transport.ready)
                ):
                    ack = job
                    remote_command = command
                    remote_state = 2
                    ctl.active = True
                elif (
                    remote_state == 2
                    and ctl.phase in ("IDLE", "SCANNING")
                    and not request
                ):
                    if command != remote_command or not active or job != ack:
                        ctl.fail("REQUEST_CHANGED_AFTER_ACK")
                    else:
                        ctl.choose(
                            "ABCD"[command // 10 - 1],
                            "RED" if command % 10 == 1 else "YELLOW",
                            now,
                            ack,
                        )
                elif ctl.phase == "DONE" and remote_state == 2:
                    remote_state = 3
                    done = ack
                elif remote_state == 3 and command == 0 and request == 0:
                    remote_state = 1
                    ctl.ready_again(now)
                    scan_after = now + 0.5
                client.status(
                    remote_state if ready or remote_state != 1 else 0,
                    ack,
                    done,
                    1 if ctl.error else 0,
                )
            if now - last_camera >= 1 / args.camera_fps:
                key = vision.key()
                rgb = cam.data.output["rgb"][0].cpu().numpy()
                job = (
                    (ctl.job, ctl.command_lane, ctl.current["color"])
                    if ctl.current
                    and ctl.phase not in ("IDLE", "SCANNING", "SUCCESS", "CANCELED")
                    else None
                )
                ready, zone, color = vision.update(rgb, now, ctl.phase, ctl.counts, job,
                    error=ctl.error, supply=transport.phase if transport else "PRELOADED")
                ctl.lane_map = vision.lane_map.copy()
                states = vision.states.copy()
                last_camera = now
                if key in (27, ord("q")):
                    break
                if key == ord("g") and not client:
                    if ready:
                        vision.notice = ""
                        ctl.recover()
                        ctl.start()
                        if transport:
                            transport.start(now)
                    else:
                        vision.notice = vision.roi_error or "Start blocked: draw all 4 ROIs, finish editing, press g"
                if key == ord("t") and transport and ctl.phase == "IDLE":
                    transport.start(now)
                if key == ord("C") and not client:
                    ctl.cancel()
                # No reset in flight. Fresh peppers require restarting scene.
                if key == ord("r") and not client:
                    if ctl.recover():
                        vision.notice = "Recovered before motion. Fix ROIs, press g."
                    elif ctl.phase in ("SUCCESS", "CANCELED") and ready:
                        ctl.start()
            previous_q = ctl.q.copy()
            ctl.tick(now, ready and now >= scan_after and (not transport or transport.ready), states, allow_select=not client)
            validation_limit_reached = bool(args.stop_after_sorted and sum(ctl.counts) >= args.stop_after_sorted and ctl.phase == "DONE")
            if ctl.phase == "DONE" and not client and not validation_limit_reached:
                ctl.ready_again(now)
                scan_after = now + 0.5
            target = robot.data.joint_pos.clone()
            target[:, arm_ids] = torch.tensor(
                ctl.q, dtype=torch.float32, device=robot.device
            )
            target[:, jaw_ids] = ctl.jaw
            robot.set_joint_position_target(target)
            velocity = torch.zeros_like(target)
            velocity[:, arm_ids] = torch.tensor(
                np.clip((ctl.q - previous_q) / physics_dt, -2, 2),
                dtype=torch.float32,
                device=robot.device,
            )
            robot.set_joint_velocity_target(velocity)
            robot.write_data_to_sim()
            context.step(render=(count % 16 == 0))
            robot.update(physics_dt)
            if contact:
                contact.update(physics_dt)
            for f in fruits:
                f["object"].update(physics_dt)
            cam.update(physics_dt)
            overview.update(physics_dt)
            if transport and transport.phase != last_supply:
                cv2.imwrite(str(OUT / ("transport_"+transport.phase.lower()+".png")),
                    overview.data.output["rgb"][0].cpu().numpy()[:, :, :3][:, :, ::-1])
                if transport.phase == 'APPROACH':
                    # The loaded-pile snapshot is captured before restoring the
                    # whole-station view. The intake vision camera never moves.
                    context.set_camera_view(eye=(2.1, -2.5, 1.8), target=(.45, 0, .25))
                    overview.set_world_poses_from_view(
                        torch.tensor([[1.8, -2.3, 1.6]], device=overview.device),
                        torch.tensor([[.45, 0, .25]], device=overview.device))
                last_supply = transport.phase
            if ctl.phase != last_phase:
                print(
                    f"HCR SIM t={now:.2f} {ctl.phase} red/yellow={ctl.counts} {ctl.error}",
                    flush=True,
                )
                last_phase = ctl.phase
            if count % 240 == 0:
                (OUT / "runtime.json").write_text(
                    json.dumps(
                        {
                            "phase": ctl.phase,
                            "counts": ctl.counts,
                            "error": ctl.error,
                            "simulation": True,
                            "assisted_grasp": True,
                            "sim_time": now,
                            "transport": transport.report() if transport else None,
                        }
                    )
                )
            if count % 2400 == 240:
                cv2.imwrite(
                    str(OUT / "overview.png"),
                    overview.data.output["rgb"][0].cpu().numpy()[:, :, :3][:, :, ::-1],
                )
                cv2.imwrite(str(OUT / "camera_preview.png"), vision.last_frame)
            count += 1
            if validation_limit_reached:
                print(f"VALIDATION LIMIT reached: {sum(ctl.counts)} completed cycles", flush=True)
                break
            if args.steps and args.unload_only and transport.ready:
                break
            if args.steps and ctl.phase in ("ERROR", "SUCCESS"):
                break
        # Serialize the initialized scene for inspection; robot/pepper state is runtime data.
        sim.get_current_stage().Export(str(OUT / "hcr_station.usda"))
        cv2.imwrite(
            str(OUT / "overview.png"),
            overview.data.output["rgb"][0].cpu().numpy()[:, :, :3][:, :, ::-1],
        )
        if hasattr(vision, "last_frame"):
            cv2.imwrite(str(OUT / "camera_preview.png"), vision.last_frame)
            cv2.imwrite(
                str(OUT / "camera_rgb.png"), vision.last_rgb[:, :, :3][:, :, ::-1]
            )
        report = {
            "phase": ctl.phase,
            "counts": ctl.counts,
            "error": ctl.error,
            "steps": count,
            "validation_limit_reached": validation_limit_reached,
            "stop_after_sorted": args.stop_after_sorted,
            "batch_complete": ctl.phase == "SUCCESS",
            "assisted_grasp": True,
            "transport": transport.report() if transport else None,
            "lane_map": vision.lane_map,
            "events": ctl.events,
            "camera_zone_states": states,
            "joint_names": robot.joint_names,
            "joint_pos": robot.data.joint_pos[0].cpu().tolist(),
            "body_names": robot.body_names,
            "body_pos": robot.data.body_pos_w[0].cpu().tolist(),
            "fruits": [
                {
                    "lane": f["lane"],
                    "color": f["color"],
                    "sorted": f["sorted"],
                    "xyz": f["object"].data.root_pos_w[0].cpu().tolist(),
                    "quat_wxyz": f["object"].data.root_quat_w[0].cpu().tolist(),
                    "initial_pose": f['initial_pose'],
                }
                for f in fruits
            ],
        }
        (OUT / "report.json").write_text(json.dumps(report, indent=2))
        (OUT / "runtime.json").write_text(json.dumps({
            "phase": ctl.phase, "counts": ctl.counts, "error": ctl.error,
            "simulation": True, "assisted_grasp": True,
            "sim_time": count * physics_dt,
            "transport": transport.report() if transport else None,
        }))
        if contact:
            (OUT / "contacts.json").write_text(
                json.dumps(
                    {
                        "names": contact.body_names,
                        "forces": contact.data.net_forces_w.cpu().tolist(),
                    },
                    indent=2,
                )
            )
        print(
            "REPORT",
            json.dumps({k: report[k] for k in ["phase", "counts", "error", "steps"]}),
            flush=True,
        )
        if args.steps and ctl.phase == "ERROR":
            raise RuntimeError(ctl.error)
    finally:
        ctl.release()
        ctl.restore_collisions()
        vision.close()
        if client:
            client.close()


try:
    main()
except Exception:
    import traceback

    traceback.print_exc()
    sys.stderr.flush()
    raise
finally:
    sim.SimulationContext.clear_instance()
    app.close(wait_for_replicator=False)
