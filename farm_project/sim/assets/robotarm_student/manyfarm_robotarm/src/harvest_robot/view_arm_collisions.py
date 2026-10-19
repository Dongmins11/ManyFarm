"""Standalone SO101 collision-only viewer. No policy, physics steps or motors.

The mesh surfaces come from PhysX cooking of the current cached robot USD,
including every convex-decomposition piece, not from the visible STL surface.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time

from isaaclab.app import AppLauncher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('right', 'left', 'both'), default='right')
    parser.add_argument('--part', choices=('all', 'gripper', 'wrist', 'camera'), default='all')
    parser.add_argument('--pose', choices=('home', 'zero'), default='home')
    parser.add_argument('--joint-positions', type=float, nargs=6, metavar='RAD')
    parser.add_argument('--frames', type=int, default=0, help='0 keeps the viewer open')
    parser.add_argument('--screenshot', action='store_true', help='Also export collision_view.png')
    parser.add_argument('--output', type=Path)
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if args.frames < 0 or (args.headless and args.frames == 0):
        parser.error('Headless requires --frames > 0')
    args.enable_cameras = args.screenshot
    args.kit_args = (args.kit_args or '') + ' --/plugins/carb.tasking.plugin/threadCount=2'
    app = AppLauncher(args).app
    failed = False
    try:
        build_viewer(args, app)
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        traceback.print_exc()
        failed = True
    finally:
        if failed:
            from harvest_rl.lifecycle import close_simulator
            close_simulator(app, failed=True)
        else:
            app.close(wait_for_replicator=False, skip_cleanup=True)


def build_viewer(args, app):
    import numpy as np
    from pxr import Gf, PhysicsSchemaTools, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdUtils
    import omni.usd
    from omni.physx import get_physx_cooking_interface
    from omni.physx.bindings._physx import PhysxCollisionRepresentationResult
    from harvest_rl.current_robot import CURRENT_CACHE, current_input_sources, prepare_current_robot
    from harvest_rl.kinematics import ArmKinematics, origin
    from harvest_rl.settings import JOINTS, ROOT, URDF

    sources = current_input_sources()
    fingerprint = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    manifest_path = CURRENT_CACHE / fingerprint[:16] / 'manifest.json'
    if manifest_path.exists():
        metadata = json.loads(manifest_path.read_text())
        if metadata['source_files'] != sources:
            raise RuntimeError('Cached robot source fingerprint differs')
        usd = manifest_path.with_name('harvest_current.usd')
    else:
        usd, _, metadata = prepare_current_robot()
    if not usd.is_file():
        raise FileNotFoundError(usd)
    out = (args.output or ROOT / 'outputs/harvest_rl' /
           f'arm_collisions_{datetime.now():%Y%m%d_%H%M%S}_{time.time_ns()%1_000_000_000:09d}').resolve()
    out.mkdir(parents=True, exist_ok=False)

    context = omni.usd.get_context()
    context.new_stage()
    stage = context.get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.)
    stage.SetDefaultPrim(stage.DefinePrim('/World', 'Xform'))
    source_root = stage.DefinePrim('/World/SourceRobot', 'Xform')
    source_root.GetReferences().AddReference(str(usd))
    # URDF import can instance collision groups even with make_instanceable=False.
    # Resolve only this viewer's reference, never edit/save the cached USD.
    for prim in list(stage.Traverse()):
        if prim.IsInstance():
            prim.SetInstanceable(False)
    UsdGeom.Xform.Define(stage, '/World/CollisionView')
    # Rendering is deliberately separate from the untouched collision source.
    UsdGeom.Imageable(source_root).MakeInvisible()
    cooking = get_physx_cooking_interface()
    stage_id = UsdUtils.StageCache.Get().GetId(stage).ToLongInt()
    if stage_id < 0:
        stage_id = UsdUtils.StageCache.Get().Insert(stage).ToLongInt()
    arms = [2, 1] if args.arm == 'both' else [2 if args.arm == 'right' else 1]
    kinematics = {arm: ArmKinematics(URDF) for arm in arms}
    for arm, kin in kinematics.items():
        kin.names = [f'arm_{arm}/{name}' for name in JOINTS]
    tree = next(iter(kinematics.values())).root
    expected_colliders = []
    for arm, kin in kinematics.items():
        for link_node in tree.findall('link'):
            link_name = link_node.get('name')
            if not link_name.startswith(f'arm_{arm}/'):
                continue
            for collision in link_node.findall('collision'):
                geometry = collision.find('geometry')[0]
                expected_colliders.append(dict(arm=arm, link=link_name, kind=geometry.tag,
                    mesh_stem=Path(geometry.get('filename')).stem if geometry.tag == 'mesh' else None,
                    matrix=kin.fk(np.zeros(6), link_name) @ origin(collision.find('origin')), matched=False))
    joints = {joint.get('name'): joint for joint in tree.findall('joint')}
    first_arm = arms[0]
    lower = np.array([float(joints[f'arm_{first_arm}/{name}'].find('limit').get('lower')) for name in JOINTS])
    upper = np.array([float(joints[f'arm_{first_arm}/{name}'].find('limit').get('upper')) for name in JOINTS])
    q = np.array(args.joint_positions if args.joint_positions is not None else
                 ([0., -1.39, .77, .62, -1.522 + np.pi/2, 1.1] if args.pose == 'home' else [0.]*6))
    if not np.all(np.isfinite(q)) or not np.all((q >= lower) & (q <= upper)):
        raise ValueError('Joint positions exceed source URDF limits')
    primitives = ('Cube', 'Sphere', 'Capsule', 'Cylinder', 'Cone')
    colors = [(0.20, .75, .95), (.95, .55, .15), (.35, .82, .40), (.78, .42, .95)]
    proxies = []
    records = []
    cache = UsdGeom.XformCache()
    # Snapshot iteration before adding the display-only geometry.
    colliders = [prim for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.CollisionAPI)
                 and UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()]
    for prim in colliders:
        # Fixed-joint merging loses the link name in collider paths. Match the
        # preserved geometry + zero-pose origin, including base and camera shapes.
        wrapper = prim.GetParent()
        wrapper_matrix = np.asarray(cache.GetLocalToWorldTransform(wrapper)).T
        rotation = wrapper_matrix[:3, :3] / np.linalg.norm(wrapper_matrix[:3, :3], axis=0)
        matched = []
        for item in expected_colliders:
            if item['matched']:
                continue
            if item['kind'] == 'mesh':
                stem = item['mesh_stem']
                if not (wrapper.GetName() == stem or wrapper.GetName().startswith(stem + '_')):
                    continue
            elif prim.GetTypeName().lower() != {'box': 'cube'}.get(item['kind'], item['kind']):
                continue
            position_error = np.max(np.abs(wrapper_matrix[:3, 3] - item['matrix'][:3, 3]))
            rotation_error = np.max(np.abs(rotation - item['matrix'][:3, :3]))
            if position_error < 1e-5 and rotation_error < 1e-4:
                matched.append((item, float(position_error), float(rotation_error)))
        if not matched:
            continue
        if len(matched) != 1:
            raise RuntimeError(f'Ambiguous original link for {prim.GetPath()}')
        item, position_error, rotation_error = matched[0]
        item['matched'] = True
        link, arm = item['link'], item['arm']
        kin = kinematics[arm]
        group = ('camera' if 'camera' in link else 'gripper' if
                 link.endswith(('gripper_link', 'moving_jaw_so101_v1_link')) else
                 'wrist' if link.endswith('wrist_link') else 'arm')
        cook_prim = prim
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI) and not prim.IsA(UsdGeom.Mesh):
            children = [child for child in Usd.PrimRange(prim) if child.IsA(UsdGeom.Mesh)]
            if len(children) != 1:
                raise RuntimeError(f'Expected one geometry mesh below {prim.GetPath()}')
            cook_prim = children[0]
            # The importer authors Collision/MeshCollisionAPI on an STL Xform.
            # PhysX cooking's inspection API requires its actual Mesh child.
            # Material/mesh data stay intact; effective collision settings are
            # copied only into this anonymous viewer stage, never the asset.
            schemas = list(dict.fromkeys(cook_prim.GetAppliedSchemas() + prim.GetAppliedSchemas()))
            cook_prim.SetMetadata('apiSchemas', Sdf.TokenListOp.CreateExplicit(schemas))
            for attribute in prim.GetAttributes():
                if attribute.GetName().startswith(('physics:', 'physx')) and attribute.HasValue():
                    cook_prim.CreateAttribute(attribute.GetName(), attribute.GetTypeName(),
                                              custom=attribute.IsCustom()).Set(attribute.Get())
        source_matrix = np.asarray(cache.GetLocalToWorldTransform(cook_prim)).T
        # The imported zero-pose transform includes collision origin and scale.
        local_matrix = np.linalg.inv(kin.fk(np.zeros(6), link)) @ source_matrix
        target = f'/World/CollisionView/arm_{arm}/Collider_{len(records):03d}'
        view_xform = UsdGeom.Xform.Define(stage, target)
        matrix_op = view_xform.AddTransformOp()
        palette = 1 if 'moving_jaw' in link else 0 if group == 'gripper' else 3 if group == 'camera' else 2
        meshes = []
        approximation = None
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            approximation = UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get()
            if approximation not in ('convexHull', 'convexDecomposition'):
                raise RuntimeError(f'Unsupported collision approximation {approximation}: {prim.GetPath()}')
            result_data = {}

            def on_result(result, convexes):
                result_data.update(result=result, convexes=list(convexes))

            cooking.request_convex_collision_representation(
                stage_id=stage_id, collision_prim_id=PhysicsSchemaTools.sdfPathToInt(str(cook_prim.GetPath())),
                run_asynchronously=False, on_result=on_result)
            if result_data.get('result') != PhysxCollisionRepresentationResult.RESULT_VALID:
                raise RuntimeError(f'PhysX cooking failed: {prim.GetPath()}')
            for index, convex in enumerate(result_data['convexes']):
                mesh = UsdGeom.Mesh.Define(stage, target + f'/Hull_{index:03d}')
                points = [Gf.Vec3f(v.x, v.y, v.z) for v in convex.vertices]
                counts = [polygon.num_vertices for polygon in convex.polygons]
                indices = [vertex for polygon in convex.polygons for vertex in
                           convex.indices[polygon.index_base:polygon.index_base + polygon.num_vertices]]
                mesh.CreatePointsAttr(points)
                mesh.CreateFaceVertexCountsAttr(counts)
                mesh.CreateFaceVertexIndicesAttr(indices)
                mesh.CreateSubdivisionSchemeAttr('none')
                meshes.append(mesh)
        elif prim.GetTypeName() in primitives:
            # Native analytic primitive: copy dimensions, but no physics APIs/xform.
            cls = getattr(UsdGeom, prim.GetTypeName())
            shape = cls.Define(stage, target + '/Primitive')
            for name in ('size', 'radius', 'height', 'axis'):
                attribute = prim.GetAttribute(name)
                if attribute and attribute.HasValue():
                    shape.GetPrim().GetAttribute(name).Set(attribute.Get())
            meshes.append(shape)
        else:
            raise RuntimeError(f'Unsupported collider type: {prim.GetPath()}')
        if not meshes:
            raise RuntimeError(f'Empty cooked collision: {prim.GetPath()}')
        for mesh in meshes:
            UsdGeom.Gprim(mesh).CreateDisplayColorAttr([Gf.Vec3f(*colors[palette])])
            UsdGeom.Gprim(mesh).CreateDoubleSidedAttr(True)
        proxies.append((arm, link, group, view_xform, matrix_op, local_matrix))
        records.append(dict(source_prim=str(prim.GetPath()), urdf_link=link, group=group,
                            cooking_geometry_prim=str(cook_prim.GetPath()),
                            geometry_type=prim.GetTypeName(), approximation=approximation,
                            urdf_origin_position_error_m=position_error, urdf_origin_rotation_max_error=rotation_error,
                            convex_pieces=len(meshes), display_prim=target))

    for arm in arms:
        expected = sum(len(link.findall('collision')) for link in tree.findall('link')
                       if link.get('name', '').startswith(f'arm_{arm}/'))
        actual = sum(record['urdf_link'].startswith(f'arm_{arm}/') for record in records)
        if actual != expected:
            raise RuntimeError(f'Collider selection incomplete for arm_{arm}: {actual} vs URDF {expected}')

    selected = args.part

    def update_view():
        for arm, link, group, xform, operation, local in proxies:
            kin = kinematics[arm]
            base = kin.fk(np.zeros(6), f'arm_{arm}/base_link')
            transform = np.linalg.inv(base) @ kin.fk(q, link) @ local
            if len(arms) > 1:
                transform[1, 3] += .55 * arms.index(arm)
            operation.Set(Gf.Matrix4d(transform.T.tolist()))
            visible = selected == 'all' or group == selected or (selected == 'wrist' and group in ('camera', 'gripper'))
            xform.GetVisibilityAttr().Set('inherited' if visible else 'invisible')

    update_view()
    # Cooking is complete. Discard all source actors/visuals from this viewer;
    # only the reference-free, non-physical collision display remains.
    stage.RemovePrim('/World/SourceRobot')
    light = UsdLux.DomeLight.Define(stage, '/World/Light')
    light.CreateIntensityAttr(250.)
    light.CreateColorAttr(Gf.Vec3f(.9, .95, 1.))
    light.CreateTextureFormatAttr('latlong')
    camera = UsdGeom.Camera.Define(stage, '/World/View')
    camera.CreateFocalLengthAttr(28.)
    camera.CreateHorizontalApertureAttr(36.)
    camera.CreateClippingRangeAttr(Gf.Vec2f(.001, 100.))
    camera_transform = camera.AddTransformOp()

    def frame_view():
        bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render'], useExtentsHint=False)
        bounds = bbox.ComputeWorldBound(stage.GetPrimAtPath('/World/CollisionView')).ComputeAlignedRange()
        center = (bounds.GetMin() + bounds.GetMax()) / 2
        span = max(bounds.GetSize())
        camera_transform.Set(Gf.Matrix4d().SetLookAt(
            center + Gf.Vec3d(.95, .8, .65) * max(span, .10), center, Gf.Vec3d(0, 0, 1)).GetInverse())

    frame_view()
    if not args.headless:
        from omni.kit.viewport.utility import get_active_viewport
        viewport = get_active_viewport()
        if viewport is not None:
            viewport.camera_path = '/World/View'
        import omni.ui as ui
        window = ui.Window('SO101 - Collision shapes only', width=345, height=490)
        with window.frame:
            with ui.VStack(spacing=5):
                ui.Label('PhysX cooked hulls / static virtual joints', height=22)
                ui.Label('Cyan: fixed jaw | Orange: moving jaw', height=22)
                with ui.HStack(height=28):
                    def choose(part):
                        nonlocal selected
                        selected = part
                        update_view()
                        frame_view()
                    for part in ('all', 'gripper', 'wrist', 'camera'):
                        ui.Button(part.title(), clicked_fn=lambda part=part: choose(part))
                for index, name in enumerate(JOINTS):
                    ui.Label(name + ' [rad]', height=18)
                    slider = ui.FloatSlider(min=float(lower[index]), max=float(upper[index]), height=20)
                    slider.model.set_value(float(q[index]))
                    def move(model, index=index):
                        q[index] = model.get_value_as_float()
                        update_view()
                    slider.model.add_value_changed_fn(move)

    # Reference-free export: only displayed cooked geometry, a light and camera.
    export = Usd.Stage.CreateNew(str(out / 'collision_only.usda'))
    export.SetDefaultPrim(export.DefinePrim('/World', 'Xform'))
    UsdGeom.SetStageUpAxis(export, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(export, 1.)
    for path in ('/World/CollisionView', '/World/Light', '/World/View'):
        Sdf.CopySpec(stage.GetRootLayer(), path, export.GetRootLayer(), path)
    export.GetRootLayer().Save()
    if any(prim.HasAPI(UsdPhysics.CollisionAPI) or prim.HasAPI(UsdPhysics.RigidBodyAPI) for prim in export.Traverse()):
        raise RuntimeError('Display-only export accidentally contains physics')
    report = dict(source_asset=metadata, source_usd_sha256=hashlib.sha256(usd.read_bytes()).hexdigest(),
                  arm=args.arm, part=args.part, joint_positions_rad=q.tolist(),
                  units='metres', display_frame='Each arm base frame; both arms separated by .55m for inspection',
                  geometry='PhysX cooked convex pieces and native analytic primitives; contact/rest margins not drawn',
                  collider_count=len(records), convex_piece_count=sum(record['convex_pieces'] for record in records),
                  colliders=records, physics_steps=0, policy_calls=0, hardware_access=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ARM_COLLISION_READY', out, 'colliders', len(records), 'pieces', report['convex_piece_count'], flush=True)
    if args.screenshot:
        import omni.replicator.core as rep
        from PIL import Image
        product = rep.create.render_product('/World/View', (960, 720))
        annotator = rep.AnnotatorRegistry.get_annotator('rgb')
        annotator.attach(product)
        # Direct render updates avoid synchronous Replicator step stalls on
        # this installed Kit build; the stage contains no physics objects.
        started = time.monotonic()
        image = None
        for frame in range(180):
            app.update()
            data = annotator.get_data()
            if frame >= 12 and isinstance(data, np.ndarray) and data.ndim == 3 and data.size:
                image = data
                break
            if time.monotonic() - started > 40:
                break
        if not isinstance(image, np.ndarray) or image.ndim != 3:
            raise RuntimeError('No screenshot returned')
        Image.fromarray(image[:, :, :3]).save(out / 'collision_view.png')
        annotator.detach(product)
        product.destroy()
        rep.orchestrator.stop()
        print('ARM_COLLISION_IMAGE', out / 'collision_view.png', flush=True)
    count = 0
    while app.is_running() and (args.frames == 0 or count < args.frames):
        app.update()
        count += 1
        time.sleep(1/60.)
    # Source files are never saved from the inspection stage.
    if current_input_sources() != sources or hashlib.sha256(usd.read_bytes()).hexdigest() != report['source_usd_sha256']:
        raise RuntimeError('Original robot sources changed during collision inspection')


if __name__ == '__main__':
    main()
