"""Export the actual validated plant's robot, current wrist visuals and sensors.

Camera prims are reparented to their physical mount bodies in this derivative
USD so the inspection prefab follows the wrist without a Python follow hook.
The validation runtime continues to use its original, unchanged sensor rig.
"""
import json
from pathlib import Path


def export_robot(rig, directory):
    import numpy as np
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf
    stage = rig.env.sim.stage
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / 'robot_with_d435.usdc'
    if destination.exists():
        raise FileExistsError(destination)
    flat = stage.Flatten()
    out = Usd.Stage.CreateNew(str(destination))
    out.GetRootLayer().TransferContent(flat)
    robot = '/World/envs/env_0/Robot'
    # Keep only the robot and the current appearance/camera branches. Retain
    # original ancestor paths to preserve all joint/body relationship targets.
    allowed = [robot, '/World/StudentWristVisuals', '/World/StudentArmAppearance']
    allowed += [str(camera.cfg.prim_path) for pair in rig.cameras.values() for camera in pair.values()]
    # Physics materials are authored outside the articulation. Copy their
    # relationship closure, otherwise the imported fingers silently lose the
    # validated friction even though their collision meshes remain present.
    for prim in out.Traverse():
        if str(prim.GetPath()).startswith(robot + '/'):
            for rel in prim.GetRelationships():
                for target in rel.GetTargets():
                    linked = out.GetPrimAtPath(target.GetPrimPath())
                    if linked and linked.IsA(UsdShade.Material):
                        allowed.append(str(linked.GetPath()))
    def wanted(path):
        return any(path == keep or path.startswith(keep + '/') or keep.startswith(path + '/') for keep in allowed)
    for prim in list(out.Traverse()):
        path = str(prim.GetPath())
        if not wanted(path):
            out.RemovePrim(path)
    out.SetDefaultPrim(out.GetPrimAtPath('/World'))
    UsdGeom.SetStageUpAxis(out, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(out, 1.)
    # Bake each camera's current world pose as a local transform relative to
    # the corresponding mount. CopySpec alone would retain a world transform.
    gripper = robot + '/arm_2_gripper_link'
    if not out.GetPrimAtPath(gripper):
        matches = [str(p.GetPath()) for p in out.Traverse() if p.GetName() == 'arm_2_gripper_link' and p.HasAPI(UsdPhysics.RigidBodyAPI)]
        if len(matches) != 1:
            raise ValueError('Cannot identify right wrist body: ' + str(matches))
        gripper = matches[0]
    reparented = []
    for view, pair in rig.cameras.items():
        for stream, camera in pair.items():
            old = str(camera.cfg.prim_path)
            # Rear sensor stays fixed to the prefab's root; wrist follows body.
            parent = gripper if view == 'right' else '/World'
            new = parent + '/D435_' + view + '_' + stream
            # USD cameras use -Z forward/+Y up; rig.local is ROS optical.
            local_ros = rig.local[view][stream] if view == 'right' else rig.fixed_world[view][stream]
            local = Gf.Matrix4d((local_ros @ np.diag([1., -1., -1., 1.])).T)
            Sdf.CopySpec(out.GetRootLayer(), old, out.GetRootLayer(), new)
            xf = UsdGeom.Xformable(out.GetPrimAtPath(new))
            xf.ClearXformOpOrder()
            xf.AddTransformOp(opSuffix='portableMount').Set(Gf.Matrix4d(local))
            out.RemovePrim(old)
            reparented.append(dict(view=view, stream=stream, prim_path=new))
    old = '/World/StudentWristVisuals'
    new = gripper + '/CurrentD435Visuals'
    Sdf.CopySpec(out.GetRootLayer(), old, out.GetRootLayer(), new)
    xf = UsdGeom.Xformable(out.GetPrimAtPath(new)); xf.ClearXformOpOrder()
    xf.AddTransformOp(opSuffix='portableMount').Set(Gf.Matrix4d(1.))
    out.RemovePrim(old)
    # A farm owns its physicsScene and render products. Camera prims and
    # calibration are supplied here; RTX annotators are attached by its runtime.
    out.GetRootLayer().Save()
    missing = []
    for prim in out.Traverse():
        for rel in prim.GetRelationships():
            for target in rel.GetTargets():
                if not out.GetPrimAtPath(target.GetPrimPath()):
                    missing.append(str(rel.GetPath()) + ' -> ' + str(target))
    if missing:
        raise ValueError('Dangling prefab relationships: ' + str(missing[:20]))
    physical_attributes = 0
    for prim in out.Traverse():
        if str(prim.GetPath()).startswith(robot + '/'):
            original = stage.GetPrimAtPath(prim.GetPath())
            for attr in prim.GetAttributes():
                if attr.GetName().startswith(('physics:', 'physx', 'drive:')):
                    if str(attr.Get()) != str(original.GetAttribute(attr.GetName()).Get()):
                        raise ValueError('Robot physics changed during export: ' + str(attr.GetPath()))
                    physical_attributes += 1
    external_assets = list(out.GetRootLayer().GetExternalReferences())
    if any(path for path in external_assets):
        raise ValueError('Prefab requires external assets: ' + str(external_assets))
    audit = dict(passed=True, file=destination.name, default_prim='/World',
        cameras=reparented, camera_count=len(reparented),
        root_to_policy_world=rig.world_from_robot.tolist(),
        frozen_rigid_physics_preserved=True, current_wrist_visuals_only=True,
        physics_attributes_verified=physical_attributes, external_asset_dependencies=external_assets,
        sensor_mounts_parented=True, dangling_relationships=missing,
        render_products_included=False,
        note='Robot prefab only; farm physicsScene/RTX annotators are owned by receiver. Reference runtime uses the original validated rig.')
    (directory / 'export_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print('STUDENT60_ROBOT_EXPORTED', destination, flush=True)


def install_export_hook(directory):
    # prepare_deployment_robot is first called after AppLauncher. Importing the
    # Camera/Isaac modules before that would make the standalone launcher fail.
    from harvest_sensors import deployment_asset
    prepare = deployment_asset.prepare_deployment_robot
    def after_launcher(previous, config):
        from harvest_sensors.deployment_rig import DeploymentD435Rig
        original = DeploymentD435Rig.begin_episode
        exported = False
        def begin(self, recorder):
            nonlocal exported
            original(self, recorder)
            if not exported:
                export_robot(self, directory)
                exported = True
        DeploymentD435Rig.begin_episode = begin
        return prepare(previous, config)
    deployment_asset.prepare_deployment_robot = after_launcher
