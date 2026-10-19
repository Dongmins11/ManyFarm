"""Derive the printed SO100 mount pose from its large hole and the SO101 holder.

Geometry is read from the unchanged STL meshes. SI units; no hand-eye fit or
assumption that the surrounding five screw holes match the SO101 holder.
"""
import collections
import copy
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from model_geometry import origin, stl, transform


def boundary_loops(triangles):
    vertices, indices = np.unique(
        triangles.reshape(-1, 3).round(8), axis=0, return_inverse=True)
    faces = indices.reshape(-1, 3)
    edges = np.sort(np.vstack((faces[:, [0, 1]], faces[:, [1, 2]],
                              faces[:, [2, 0]])), axis=1)
    edges, counts = np.unique(edges, axis=0, return_counts=True)
    adjacent = collections.defaultdict(set)
    for a, b in edges[counts == 1]:
        adjacent[a].add(b)
        adjacent[b].add(a)
    loops = []
    while adjacent:
        pending = [next(iter(adjacent))]
        component = set()
        while pending:
            vertex = pending.pop()
            if vertex in component:
                continue
            component.add(vertex)
            pending.extend(adjacent[vertex] - component)
        if any(len(adjacent[v]) != 2 for v in component):
            raise ValueError('Open or branched face boundary')
        for vertex in component:
            adjacent.pop(vertex)
        loops.append(vertices[sorted(component)])
    return loops


def circular_hole(triangles, axis, plane, radius):
    """Fit a circular face boundary; reject an absent or ambiguous hole."""
    on_face = (np.abs(triangles[:, :, axis] - plane) < 2e-6).all(axis=1)
    axes = [a for a in range(3) if a != axis]
    matches = []
    for points in boundary_loops(triangles[on_face]):
        if len(points) < 12:
            continue
        xy = points[:, axes]
        solution = np.linalg.lstsq(
            np.c_[2 * xy, np.ones(len(xy))], (xy * xy).sum(axis=1),
            rcond=None)[0]
        center = solution[:2]
        fitted_radius = np.sqrt(max(0., solution[2] + center @ center))
        residual = np.abs(np.linalg.norm(xy - center, axis=1) - fitted_radius).max()
        if abs(fitted_radius - radius) < 2e-6 and residual < 2e-6:
            center_3d = points.mean(axis=0)
            center_3d[axes] = center
            matches.append(dict(center=center_3d, radius=float(fitted_radius),
                                max_residual=float(residual), vertices=len(points)))
    if len(matches) != 1:
        raise ValueError(f'Expected one radius {radius} hole, found {len(matches)}')
    return matches[0]


def derive_hole_alignment(root, package, reference):
    package = Path(package)
    normalization = reference['normalized_stl_transform']
    t = transform(normalization['xyz'], normalization['rpy'])
    triangles = stl(package / 'meshes/mounts/d435_wrist_mount.stl') * normalization['scale']
    triangles = triangles @ t[:3, :3].T + t[:3, 3]
    plate_axes = np.array(reference['five_hole_plate_axes'])
    plate_origin = np.array(reference['five_hole_plate_center'])
    plate_local = (triangles - plate_origin) @ plate_axes
    outer = circular_hole(plate_local, 2, 0., .0075)
    inner = circular_hole(plate_local, 2, -.003, .0075)
    thickness = float(outer['center'][2] - inner['center'][2])
    mount_center = plate_origin + plate_axes @ outer['center']
    mount_inner = plate_origin + plate_axes @ inner['center']

    holder_visual = next(v for v in root.find("link[@name='arm_1/gripper_link']").findall('visual')
                         if 'wrist_roll_follower' in v.find('geometry/mesh').get('filename', ''))
    mesh = holder_visual.find('geometry/mesh')
    filename = mesh.get('filename')
    path = (package / filename.split('package://smartfarm_description/', 1)[1]
            if filename.startswith('package://smartfarm_description/')
            else package / 'urdf' / filename)
    holder = stl(path) * np.fromstring(mesh.get('scale', '1 1 1'), sep=' ')
    t = origin(holder_visual.find('origin'))
    holder = holder @ t[:3, :3].T + t[:3, 3]
    bore = circular_hole(holder, 0, float(holder[:, :, 0].min()), .005)
    holder_center = bore['center']
    outward = np.array([-1., 0., 0.])

    # Plate outer normal is -X. Its in-plane +X follows gripper +Z and
    # in-plane +Y follows gripper +Y: camera above that side looks into the jaws.
    target_axes = np.array([[0., 0., -1.], [0., 1., 0.], [1., 0., 0.]])
    rotation = target_axes @ plate_axes.T
    mount_xyz = holder_center - rotation @ mount_inner
    mount = np.eye(4)
    mount[:3, :3] = rotation
    mount[:3, 3] = mount_xyz
    camera = mount @ transform(reference['config']['wrist_camera_xyz'],
                               reference['config']['wrist_camera_rpy'])

    result = copy.deepcopy(reference)
    result['schema'] = 'd435_wrist_large_hole_alignment_v1'
    result['installation_basis'] = '2026-10-12 user-confirmed printed SO100 mount; large holes coaxial on SO101 fixed holder outer -X face'
    result['large_hole_alignment'] = dict(
        mount_outer_center=mount_center.tolist(), mount_inner_center=mount_inner.tolist(),
        mount_axis=plate_axes[:, 2].tolist(), mount_radius_m=outer['radius'],
        mount_plate_thickness_m=thickness,
        holder_center_gripper=holder_center.tolist(), holder_axis_gripper=outward.tolist(),
        holder_radius_m=bore['radius'], mount_fit_residual_m=outer['max_residual'],
        holder_fit_residual_m=bore['max_residual'],
        in_plane_axes_gripper=target_axes.tolist())
    result['five_hole_plate_gripper_anchor'] = (mount @ np.r_[plate_origin, 1.])[:3].tolist()
    result['config']['wrist_mount_xyz'] = mount_xyz.tolist()
    result['config']['wrist_mount_rpy'] = Rotation.from_matrix(rotation).as_euler('xyz').tolist()
    result['camera_center_gripper_m'] = camera[:3, 3].tolist()
    result['camera_forward_gripper'] = camera[:3, 0].tolist()
    result['note'] = ('User confirmed the SO100 print is installed with the large holes aligned. '
                      'The inner mount face rests on the actual SO101 holder outer -X face; '
                      'hole diameters remain 15/10 mm. Roll about that axis keeps the camera '
                      'on +Y looking inward and along gripper -Z. Screw fastening, print '
                      'tolerances and hand-eye calibration are not inferred. The previous '
                      'd435_wrist_attachment.json remains the frozen historical reference.')
    return result
