"""Read and import the existing Waffle transport URDF; never regenerate geometry."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from .model import ROOT, OUT

DESCRIPTION = ROOT / 'src/smartfarm_description'
URDF = DESCRIPTION / 'urdf/transport_robot.portable.urdf'


def source_paths():
    root = ET.parse(URDF).getroot()
    return [URDF, DESCRIPTION/'config/transport.json', DESCRIPTION/'scripts/model_geometry.py', *sorted({
        (URDF.parent / mesh.get('filename')).resolve() for mesh in root.iter('mesh')
    })]


def geometry():
    root = ET.parse(URDF).getroot()
    config = json.loads((DESCRIPTION/'config/transport.json').read_text())
    zero = sum((np.fromstring(root.find(f"joint[@name='{name}']/origin").get('xyz'),sep=' ')
                for name in ('base_joint','box_tilt_joint')), np.zeros(3))
    floor = root.find("link[@name='cargo_box']/collision")
    floor_top = float(floor.find('origin').get('xyz').split()[2]) + float(floor.find('geometry/box').get('size').split()[2])/2
    limits = {j.get('name'): float(j.find('limit').get('upper'))
              for j in root.findall('joint') if j.find('limit') is not None}
    return dict(config=config, cargo_zero=zero, floor_top=floor_top, limits=limits)


def payload_positions(cfg, count):
    """Legacy ordered positions for explicit replay of the earlier tests."""
    if not 0 <= count <= 8:
        raise ValueError('Existing cargo box preset supports at most 8 peppers')
    g = geometry()
    height = cfg['physics']['pepper_length']
    gap = .006
    layers = (count + 3) // 4
    layer_gap = .002
    if layers and g['floor_top'] + gap + layers * height + (layers - 1) * layer_gap > g['config']['box_height']:
        raise ValueError('Payload layers exceed the original cargo box height')
    root = np.array([cfg['transport']['start_front_x'] + g['cargo_zero'][0], 0, 0])
    yaw = np.diag([-1., -1., 1.])
    points = []
    for i in range(count):
        slot, layer = i % 4, i // 4
        col, row = slot % 2, slot // 2
        x, y = -.06 - row * .12, (-.0625 if col == 0 else .0625)
        radius = cfg['physics']['pepper_diameter'] / 2
        wall = g['config']['wall_thickness']
        if not (-g['config']['box_length'] + wall < x - radius
                and x + radius < -wall
                and abs(y) + radius < g['config']['box_width'] / 2 - wall):
            raise ValueError('Payload preset exceeds the original cargo box footprint')
        local = np.array([x, y, g['floor_top'] + height / 2 + gap + layer * (height + layer_gap)])
        points.append(root + yaw @ (g['cargo_zero']+local))
    return points


def payload_poses(cfg, count):
    layout = cfg['transport'].get('payload_layout', 'random')
    if layout == 'ordered':
        return [dict(position=p.tolist(), rotation_wxyz=[1., 0., 0., 0.])
                for p in payload_positions(cfg, count)]
    if layout == 'random':
        from .payload import random_payload_poses
        return random_payload_poses(cfg, count, geometry())
    raise ValueError(f'Unknown payload layout: {layout}')


def spawn_transport(cfg):
    """Import original geometry, then prescribe its original FK as kinematic links."""
    import importlib.util
    import isaaclab.sim as sim
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg
    from pxr import UsdPhysics, UsdShade, UsdGeom, Gf, PhysxSchema

    sources = source_paths()
    digest = hashlib.sha256(b''.join(path.read_bytes() for path in sources)+b'kinematic-original-fk-v3').hexdigest()[:16]
    converter = UrdfConverter(UrdfConverterCfg(
        asset_path=str(URDF), usd_dir=str(OUT/'assets/transport'/digest),
        usd_file_name='transport_robot.usd', fix_base=False, merge_fixed_joints=True,
        make_instanceable=False, convert_mimic_joints_to_normal_joints=True,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0., damping=0.)),
    ))
    spawn = sim.UsdFileCfg(usd_path=converter.usd_path)
    spawn.func('/World/Transport', spawn)
    stage = sim.get_current_stage()
    bodies = {}
    visual_ops = {}
    static_frames = {}
    for prim in list(stage.Traverse()):
        if not str(prim.GetPath()).startswith('/World/Transport'):
            continue
        if prim.IsInstance():
            prim.SetInstanceable(False)
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            prim.RemoveAPI(UsdPhysics.ArticulationRootAPI)
        if prim.HasAPI(PhysxSchema.PhysxArticulationAPI):
            prim.RemoveAPI(PhysxSchema.PhysxArticulationAPI)
        if prim.IsA(UsdPhysics.Joint):
            UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr(True)
            PhysxSchema.PhysxRigidBodyAPI.Apply(prim).CreateDisableGravityAttr(True)
            xform = UsdGeom.Xformable(prim)
            xform.ClearXformOpOrder()
            bodies[prim.GetName()] = xform.AddTransformOp()
            # CPU PhysX kinematic targets move collision bodies without writing
            # their poses back to USD. Compensate visuals only; never move or
            # replace the original collision shapes through this display path.
            visuals = prim.GetChild('visuals')
            if visuals.IsValid():
                visual_ops[prim.GetName()] = UsdGeom.Xformable(visuals).AddTransformOp()
    sim.modify_collision_properties('/World/Transport',sim.CollisionPropertiesCfg(contact_offset=.001,rest_offset=0))
    material_path = '/World/HCRMaterials/TransportCargo'
    material_cfg = sim.RigidBodyMaterialCfg(static_friction=.5,dynamic_friction=.4,restitution=0)
    material_cfg.func(material_path, material_cfg)
    cargo = UsdShade.Material.Get(stage,material_path)
    for prim in stage.Traverse():
        if str(prim.GetPath()).startswith('/World/Transport') and prim.HasAPI(UsdPhysics.CollisionAPI):
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(cargo,materialPurpose='physics')
    spec = importlib.util.spec_from_file_location('transport_source_geometry', DESCRIPTION/'scripts/model_geometry.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = ET.parse(URDF).getroot()
    names = [j.get('name') for j in root.findall('joint') if j.get('type') != 'fixed']
    joints = {n: 0. for n in names}
    g = geometry()
    joints['lid_pinion_joint'] = g['limits']['lid_pinion_joint']
    for j in root.findall('joint'):
        mimic = j.find('mimic')
        if mimic is not None:
            joints[j.get('name')] = float(mimic.get('multiplier','1'))*joints[mimic.get('joint')]+float(mimic.get('offset','0'))

    previous_pose = None
    physics = {}

    def initialize():
        import torch
        import omni.physics.tensors as tensors
        physics['simulation'] = tensors.create_simulation_view('torch')
        physics['simulation'].set_subspace_roots('/')
        view = physics['simulation'].create_rigid_body_view('/World/Transport/*')
        physics['view'] = view
        physics['names'] = [Path(p).name for p in view.prim_paths]
        physics['indices'] = torch.arange(view.count,dtype=torch.int32,device=view.get_transforms().device)
        if set(physics['names']) != set(bodies):
            raise RuntimeError('Transport physics links do not match original URDF links')

    def set_pose(front_x, tilt, gate):
        nonlocal previous_pose
        key = (front_x, tilt, gate)
        if key == previous_pose:
            return
        previous_pose = key
        joints['box_tilt_joint'] = tilt
        joints['side_lid_joint'] = gate
        for name in names:
            if name.startswith('wheel_'):
                joints[name] = (cfg['transport']['start_front_x']-front_x)/.033
        poses = module.fk(root, joints)
        base = np.diag([-1.,-1.,1.,1.])
        base[:3,3] = [front_x+g['cargo_zero'][0],0,0]
        if physics:
            import torch
            from scipy.spatial.transform import Rotation
            data = []
            for name in physics['names']:
                pose = base @ poses[name]
                data.append([*pose[:3,3],*Rotation.from_matrix(pose[:3,:3]).as_quat()])
            view = physics['view']
            view.set_kinematic_targets(torch.tensor(np.array(data),dtype=torch.float32,
                device=view.get_transforms().device),physics['indices'])
            for name, op in visual_ops.items():
                op.Set(Gf.Matrix4d((np.linalg.inv(static_frames[name]) @ base @ poses[name]).T.tolist()))
        else:
            for name, op in bodies.items():
                static_frames[name] = base @ poses[name]
                op.Set(Gf.Matrix4d(static_frames[name].T.tolist()))
    set_pose(cfg['transport']['start_front_x'],0.,0.)
    print('EXISTING TRANSPORT URDF',URDF,'KINEMATIC LINKS',list(bodies),flush=True)
    return dict(set_pose=set_pose,initialize=initialize,joints=joints,bodies=list(bodies)), converter.usd_path, g
