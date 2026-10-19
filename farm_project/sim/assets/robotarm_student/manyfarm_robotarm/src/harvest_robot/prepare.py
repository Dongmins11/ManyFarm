"""Generate simulator-only derivative URDF, full robot USD and reachable seed bank."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from harvest_rl.settings import CACHE, URDF, ASSETS, TaskSettings
from harvest_rl.kinematics import ArmKinematics


def prepare_data(args):
    cfg = TaskSettings(diameter=args.diameter,length=args.diameter*.075/.070).validate()
    CACHE.mkdir(parents=True, exist_ok=True)
    kin = ArmKinematics()
    qs, points = kin.candidates(cfg)
    # Rotate only the reset wrist by +90 degrees from the previous HOME.
    # This is an initial pose, not a constraint on policy-selected grasp orientation.
    home = np.array([0.0, -1.39, .77, .62, -1.522 + np.pi / 2, 1.1])
    if not np.all((home > kin.lower) & (home < kin.upper)):
        raise ValueError("Nominal home violates updated URDF joint limits")
    np.savez(CACHE / "workspace.npz", q=qs, points=points, home=home,
             lower=kin.lower, upper=kin.upper, diameter=cfg.diameter)
    root = ET.parse(URDF)
    for mesh in root.findall(".//mesh"):
        mesh.set("filename", str((URDF.parent / mesh.get("filename")).resolve()))
    # Keep every link/visual/collider, but lock wheels, left arm and box floor closed.
    for joint in root.findall("joint"):
        if joint.get("type") != "fixed" and not joint.get("name", "").startswith("arm_2/"):
            joint.set("type", "fixed")
            for tag in ("axis", "limit", "dynamics", "mimic"):
                for child in joint.findall(tag):
                    joint.remove(child)
    root.write(CACHE / "harvest_training.urdf", encoding="utf-8", xml_declaration=True)
    meta = json.loads((ASSETS / "manifest.json").read_text())["Pepper_Red"]
    size = np.diff(meta["bounds"], axis=0)[0]
    scale = [cfg.diameter / max(size[:2])] * 2 + [cfg.length / size[2]]
    report = dict(source_urdf=str(URDF), sha256=hashlib.sha256(URDF.read_bytes()).hexdigest(),
                  workspace_sha256=hashlib.sha256(qs.tobytes()+points.tobytes()+home.tobytes()).hexdigest(),
                  points=len(points), reachable_min=points.min(0).tolist(), reachable_max=points.max(0).tolist(),
                  home=home.tolist(), original_pepper_size=size.tolist(), pepper_scale=scale,
                  home_grasp_position=kin.grasp_fk(home,cfg.diameter)[:3,3].tolist(),
                  note="FK and coarse clearance screening only; not swept-volume collision certification")
    (CACHE / "preparation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-only", action="store_true")
    parser.add_argument("--diameter", type=float, default=.070)
    args, rest = parser.parse_known_args()
    prepare_data(args)
    if args.data_only:
        return
    from isaaclab.app import AppLauncher
    sim_parser = argparse.ArgumentParser()
    AppLauncher.add_app_launcher_args(sim_parser)
    sim_args = sim_parser.parse_args(rest)
    app = AppLauncher(sim_args).app
    failed = False
    try:
        from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg
        converter = UrdfConverter(UrdfConverterCfg(
            asset_path=str(CACHE / "harvest_training.urdf"), usd_dir=str(CACHE),
            usd_file_name="harvest_robot.usd", force_usd_conversion=True,
            fix_base=True, merge_fixed_joints=True, self_collision=True,
            make_instanceable=False, collider_type="convex_decomposition",
            joint_drive=UrdfConverterCfg.JointDriveCfg(
                gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=25.0, damping=1.5))))
        print("ROBOT_USD", converter.usd_path)
    except Exception:
        import traceback
        traceback.print_exc()
        failed = True
        raise
    finally:
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app,failed=failed)


if __name__ == "__main__":
    main()
