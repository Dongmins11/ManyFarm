"""USD-only wrist display replacement, including a merged inactive left arm.

Import after USD is available. No simulator, GPU, controller or hardware calls.
"""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Vt


def physics_signature(stage):
    """Include instance-proxy collision shapes, drives, masses and relationships."""
    result = {}
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        physical = (any(str(s).startswith(('Physics', 'Physx')) for s in prim.GetAppliedSchemas())
                    or prim.IsA(UsdPhysics.Joint) or '/collisions/' in str(prim.GetPath()))
        if physical:
            result[str(prim.GetPath())] = (
                prim.GetTypeName(), tuple(prim.GetAppliedSchemas()),
                tuple((a.GetName(), str(a.Get())) for a in prim.GetAttributes() if a.GetName() != 'visibility'),
                tuple((r.GetName(), tuple(map(str, r.GetTargets()))) for r in prim.GetRelationships()))
    return result


def install(stage, urdf, frozen_urdf, arms=(1, 2)):
    from harvest_rl.settings import ROOT
    sys.path.insert(0, str(ROOT/'src/smartfarm_description/scripts'))
    from model_geometry import visuals, fk, origin
    before = physics_signature(stage)
    current = ET.parse(urdf).getroot(); poses = fk(current)
    frozen = ET.parse(frozen_urdf).getroot(); old_poses = fk(frozen)
    xcache = UsdGeom.XformCache()
    transforms = {}; static_poses = {}; audit = {}; count = 0
    def rigid_pose(prim):
        t = np.asarray(xcache.GetLocalToWorldTransform(prim)).T.copy()
        t[:3, :3] /= np.linalg.norm(t[:3, :3], axis=0)
        return t
    for arm in arms:
        name = f'arm_{arm}_gripper_link'
        wrists = [p for p in stage.Traverse() if p.GetName() == name]
        if len(wrists) != 1:
            raise ValueError(f'Expected one wrist prim: {name}, found {len(wrists)}')
        wrist = wrists[0]
        visual = wrist.GetChild('visuals')
        hidden = []
        if visual:
            UsdGeom.Imageable(visual).CreateVisibilityAttr().Set('invisible')
            hidden.append(str(visual.GetPath()))
            allowed = {f'arm_{arm}/gripper_link', f'arm_{arm}/gripper_frame_link', f'arm_{arm}/tool0'}
        else:
            # The inactive arm is merged into base_footprint/visuals. Its empty
            # link prims survive, but it is not an Articulation body. Match the
            # old camera visual transforms from the actual frozen source URDF;
            # never hide the whole base, other arm, overhead camera or colliders.
            old_root_pose = wrist
            while old_root_pose and not old_root_pose.GetChild('base_footprint'):
                old_root_pose = old_root_pose.GetParent()
            if not old_root_pose: raise ValueError('Cannot identify preserved robot root')
            asset_world = np.asarray(xcache.GetLocalToWorldTransform(old_root_pose)).T
            groups = [old_root_pose.GetChild('base_footprint').GetChild('visuals')]
            if not all(groups): raise ValueError('Missing merged base visual group')
            for group in groups:
                if group.IsInstance(): group.SetInstanceable(False)
            candidates = [child for group in groups for child in group.GetChildren()]
            for link in frozen.findall('link'):
                if not link.get('name').startswith(f'arm_{arm}/wrist_camera'): continue
                for v in link.findall('visual'):
                    expected = asset_world @ old_poses[link.get('name')] @ origin(v.find('origin'))
                    matches = [p for p in candidates if np.allclose(
                        rigid_pose(p), expected, atol=2e-6, rtol=0)]
                    if len(matches) != 1:
                        raise ValueError(f'Cannot uniquely match merged camera visual {link.get("name")}: {len(matches)}')
                    UsdGeom.Imageable(matches[0]).CreateVisibilityAttr().Set('invisible')
                    hidden.append(str(matches[0].GetPath()))
            if not hidden: raise ValueError('No old merged camera visuals found')
            allowed = set()
        allowed |= {l.get('name') for l in current.findall('link') if l.get('name').startswith(f'arm_{arm}/wrist_camera')}
        root = ET.fromstring(ET.tostring(current))
        for link in list(root.findall('link')):
            if link.get('name') not in allowed: root.remove(link)
        group = '/World/StudentWristVisuals' if arm == 2 else f'/World/StudentWristVisualsArm{arm}'
        op = UsdGeom.Xform.Define(stage, group).AddTransformOp()
        transforms[arm] = op
        wrist_world = np.asarray(xcache.GetLocalToWorldTransform(wrist)).T
        op.Set(Gf.Matrix4d(wrist_world.T))
        if arm != 2: static_poses[arm] = wrist_world
        reference = np.linalg.inv(poses[f'arm_{arm}/gripper_link'])
        for link_name, tri, color in visuals(root, Path(urdf), poses):
            points = tri.reshape(-1, 3) @ reference[:3, :3].T + reference[:3, 3]
            mesh = UsdGeom.Mesh.Define(stage, f'{group}/Mesh_{count}')
            mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points.astype(np.float32)))
            mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(tri), 3, np.int32)))
            mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(np.arange(len(points), dtype=np.int32)))
            mesh.CreateSubdivisionSchemeAttr('none'); mesh.CreateDoubleSidedAttr(True)
            mesh.CreateDisplayColorAttr([Gf.Vec3f(*map(float, color[:3]))])
            mesh.GetPrim().SetCustomDataByKey('u20SourceLink', link_name)
            count += 1
        audit[str(arm)] = dict(wrist_prim=str(wrist.GetPath()), hidden_visuals=hidden,
                              merged_inactive_arm=not bool(visual), replacement_group=group)
    if physics_signature(stage) != before:
        raise ValueError('U20 visual replacement changed preserved physics')
    return transforms, static_poses, dict(arms=audit, meshes=count, physics_properties_checked=len(before),
                                        physics_unchanged=True)
