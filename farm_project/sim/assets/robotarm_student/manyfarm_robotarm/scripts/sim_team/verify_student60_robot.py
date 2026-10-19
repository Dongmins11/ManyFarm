"""Inspect exported USD composition, moving wrist mounts and camera optics."""
import argparse
import json
from pathlib import Path
from student60_bundle import ROOT, deployment


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    from isaaclab.app import AppLauncher
    app = AppLauncher(headless=True, enable_cameras=False, device='cuda:0',
                      kit_args='--/plugins/carb.tasking.plugin/threadCount=4').app
    failed = True
    try:
        import numpy as np
        from pxr import Usd, UsdGeom, Sdf, Gf
        from harvest_rl.kinematics import ArmKinematics
        from harvest_rl.settings import URDF
        from harvest_sensors.deployment import expected_poses
        from harvest_sensors.profile import centred_render_spec, matrix
        d = deployment(); c = d['contract']
        stage = Usd.Stage.Open(str(ROOT / d['robot_with_cameras']))
        audit = json.loads((ROOT / 'handoff/robot/export_audit.json').read_text())
        cameras = audit['cameras']
        kin = ArmKinematics(URDF); world = np.asarray(d['robot_root_to_policy_world'])
        poses = expected_poses(kin, np.zeros(6), c['camera_config'], world)
        wrist = world @ kin.fk(np.zeros(6), 'arm_2/gripper_link')
        ros_from_gl = np.diag([1., -1., -1., 1.])
        max_error = 0.; contracts = []
        for item in cameras:
            prim = stage.GetPrimAtPath(item['prim_path'])
            if not prim.IsA(UsdGeom.Camera):
                raise ValueError('Missing camera: ' + item['prim_path'])
            local_gl = np.asarray(UsdGeom.Xformable(prim).GetLocalTransformation()).T
            actual = local_gl @ ros_from_gl
            expected = np.linalg.inv(wrist) @ poses[item['view']][item['stream']] if item['view'] == 'right' else poses[item['view']][item['stream']]
            error = float(np.abs(actual - expected).max()); max_error = max(max_error, error)
            if error > 1e-9:
                raise ValueError('Camera mount transform changed: ' + str(item))
            spec = c['camera_config']['views'][item['view']]['streams'][item['stream']]
            width, height, render_k, _, _ = centred_render_spec(spec)
            contracts.append(dict(item, native_wh=[spec['width'], spec['height']],
                                  render_wh=[width, height], native_k=matrix(spec).tolist(),
                                  render_k=render_k.tolist(), parent_from_ros_optical=actual.tolist()))
        # Reference under another namespace: all joint/material relationships
        # must resolve there, with no residual /World paths outside the prefab.
        nested = Usd.Stage.CreateInMemory()
        root = UsdGeom.Xform.Define(nested, '/Farm/Harvest01')
        root.GetPrim().GetReferences().AddReference(str(ROOT / d['robot_with_cameras']), '/World')
        root.AddTranslateOp().Set(Gf.Vec3d(2., -1., .25))
        bad = []
        for prim in nested.Traverse():
            for rel in prim.GetRelationships():
                for target in rel.GetTargets():
                    if not nested.GetPrimAtPath(target.GetPrimPath()):
                        bad.append(str(rel.GetPath()) + ' -> ' + str(target))
        if bad:
            raise ValueError('Re-referenced relationship does not resolve: ' + str(bad[:10]))
        camera_path = cameras[0]['prim_path'].replace('/World', '/Farm/Harvest01', 1)
        parent = nested.GetPrimAtPath(Sdf.Path(camera_path).GetParentPath())
        camera = nested.GetPrimAtPath(camera_path)
        before = np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(camera))[3, :3]
        xf = UsdGeom.Xformable(parent)
        xf.AddTranslateOp(opSuffix='verificationOnly').Set(Gf.Vec3d(.01, 0., 0.))
        after = np.asarray(UsdGeom.XformCache().GetLocalToWorldTransform(camera))[3, :3]
        if abs(np.linalg.norm(after - before) - .01) > 1e-6:
            raise ValueError('Wrist camera does not follow its parent')
        result = dict(passed=True, cameras=len(cameras), max_mount_matrix_error=max_error,
                      relocated_reference_relationships_valid=True, moving_wrist_camera_follows=True,
                      camera_contracts=contracts,
                      external_dependencies=[p for p in stage.GetRootLayer().GetExternalReferences() if p],
                      note='USD composition/geometry check; no physics stepping or harvest evaluation')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print('STUDENT60_USD_VERIFIED', args.output, flush=True)
        failed = False
    finally:
        from harvest_rl.lifecycle import close_simulator
        close_simulator(app, None, failed)


if __name__ == '__main__':
    main()
