"""V4 인계 6개와 덮개 닫힘의 촬영 설정·측정 자료를 재현한다.

python3 build_handoff_v4.py
USD 측정은 pxr가 있는 Python으로 --inspect-usd를 먼저 실행한다.
운영 FSM/물리 자산을 저장하지 않으며 V3 원본은 읽기만 한다.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V3 = ROOT / 'sim/runs/presentation_video_revision_v3_20261104/settings'
PATHS = [f'/World/PresentationFruits/Handoff_{i:02d}' for i in range(1, 7)]
UNUSED = '/World/PresentationFruits/Handoff_07'
FPS = 30


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(name: str, value: dict) -> None:
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def smooth(t: float, begin: float, end: float) -> float:
    u = float(np.clip((t - begin) / (end - begin), 0., 1.))
    return u * u * (3. - 2. * u)


def inspect_usd() -> None:
    """원본 USD의 관절 축/한계와 Cube의 실제 꼭짓점을 세션에서 측정한다."""
    from pxr import Usd, UsdGeom, UsdPhysics, Gf
    sys.path.insert(0, str(ROOT / 'sim/tools'))
    from presentation_scene_v3 import install_handoff_assets
    stage = Usd.Stage.Open(str(ROOT / 'sim/assets/envs/output/farm_with_plants_v5.usd'))
    stage.SetEditTarget(stage.GetSessionLayer())
    assets = {
        'harvest_robot': 'robots/harvest_count_test/harvest_robot.usd',
        'transport_robot': 'robots/transport_robot/urdf/transport_robot.portable/transport_robot.sim.usda',
    }
    request = read(V3 / '05_handoff.json')
    for name, asset in assets.items():
        path = '/World/' + name
        prim = UsdGeom.Xform.Define(stage, path).GetPrim()
        prim.GetReferences().AddReference(str(ROOT / 'sim/assets' / asset))
        xf = UsdGeom.Xformable(prim); xf.ClearXformOpOrder()
        matrix = np.asarray(request['base']['placements'][path]['matrix'])
        xf.AddTransformOp().Set(Gf.Matrix4d(matrix.T.tolist()))
    setup = install_handoff_assets(stage, ROOT, '/World/harvest_robot')
    names = {'top_lid_left_joint', 'top_lid_right_joint', 'lid_pinion_joint',
             'side_lid_joint', 'box_tilt_joint', 'box_bottom_left_joint',
             'box_bottom_right_joint', 'harvest_lid_pinion_joint'}
    joints = {}
    for prim in stage.Traverse():
        if prim.GetName() not in names or not prim.IsA(UsdPhysics.Joint):
            continue
        j = UsdPhysics.Joint(prim)
        axis = prim.GetAttribute('physics:axis').Get()
        body = stage.GetPrimAtPath(j.GetBody0Rel().GetTargets()[0])
        parent = UsdGeom.Xformable(body).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        vector = {'X': Gf.Vec3d(1, 0, 0), 'Y': Gf.Vec3d(0, 1, 0), 'Z': Gf.Vec3d(0, 0, 1)}[axis]
        world_axis = parent.TransformDir(Gf.Rotation(j.GetLocalRot0Attr().Get()).TransformDir(vector))
        joints[prim.GetName()] = {
            'path': str(prim.GetPath()), 'type': prim.GetTypeName(),
            'body0': str(j.GetBody0Rel().GetTargets()[0]), 'body1': str(j.GetBody1Rel().GetTargets()[0]),
            'axis_token': axis, 'axis_world': list(world_axis),
            'lower_limit_usd': prim.GetAttribute('physics:lowerLimit').Get(),
            'upper_limit_usd': prim.GetAttribute('physics:upperLimit').Get(),
            'limit_units': 'm' if prim.IsA(UsdPhysics.PrismaticJoint) else 'degrees',
            'closed_value_for_capture': 0.,
        }
    cubes = []
    for name in ('top_lid_left', 'top_lid_right', 'cargo_box'):
        for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/transport_robot/' + name), Usd.TraverseInstanceProxies()):
            if not prim.IsA(UsdGeom.Cube) or '/visuals/' not in str(prim.GetPath()):
                continue
            size = UsdGeom.Cube(prim).GetSizeAttr().Get()
            m = np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
            pts = np.asarray(list(itertools.product([-size / 2, size / 2], repeat=3))) @ m[:3, :3].T + m[:3, 3]
            cubes.append({'path': str(prim.GetPath()), 'actual_world_bounds_closed': [pts.min(0).tolist(), pts.max(0).tolist()]})
    floor_points = []
    for path in setup['floor_paths']:
        for prim in Usd.PrimRange(stage.GetPrimAtPath(path), Usd.TraverseInstanceProxies()):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            m = np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
            pts = np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get(), float) @ m[:3, :3].T + m[:3, 3]
            floor_points.extend(pts.tolist())
    floor = np.asarray(floor_points)
    urdf = ET.parse(ROOT / 'sim/assets/robots/transport_robot/urdf/transport_robot.urdf').getroot()
    urdf_joints = {}
    for joint in urdf.findall('joint'):
        if joint.attrib['name'] not in names:
            continue
        urdf_joints[joint.attrib['name']] = {'type': joint.attrib['type'],
            'axis': joint.find('axis').attrib['xyz'], 'limit': joint.find('limit').attrib,
            'mimic': joint.find('mimic').attrib if joint.find('mimic') is not None else None}
    write('05_mechanism_geometry.json', {
        'status': 'offline USD measurement; GUI not reviewed here',
        'method': 'original joint frames + actual Cube size vertices / Mesh points; no BBoxCache Cube extent',
        'joints': joints, 'urdf_transport_joints': urdf_joints, 'transport_visual_cubes': cubes,
        'simulation_lock_note': 'transport_robot.sim.usda locks top lid prismatic limits to 0. Capture disables all rigid bodies/joints/mimic in session and uses original joint frames for manual FK with URDF 0..0.155m range. Original simulation lock remains unchanged.',
        'restored_harvest_floor_bounds': [floor.min(0).tolist(), floor.max(0).tolist()],
        'original_asset_files_saved': False,
    })


def build() -> None:
    old = read(V3 / '05_handoff.json')
    old_evidence = read(V3 / '05_motion_evidence.json')
    geometry = read(HERE / '05_mechanism_geometry.json')
    sources = old_evidence['clones'][:6]
    meshes = {x['source']: x for x in read(V3 / 'handoff_mesh_points.json')}
    points = [np.asarray(meshes[x['source']]['root_local_points'], float) for x in sources]
    scales = [np.asarray(x['source_scale'], float) for x in sources]
    centers = [((p * s).min(0) + (p * s).max(0)) * .5 for p, s in zip(points, scales)]
    slot = [0, 1, 2, 3, 5, 4]
    req = copy.deepcopy(old)
    req.update(name='05_handoff_continuity', duration_s=5, fps=FPS, easing='linear', preview_only=True,
               preview_frames=[0, 30, 45, 60, 90, 110, 119, 149], preview_warmup_frames=48)
    base = req['base']
    base['show'] = [p for p in base['show'] if p != UNUSED]
    base['hide'] = list(dict.fromkeys([*base['hide'], UNUSED]))
    base['placements'].pop(UNUSED, None)
    base['inspect'] = [*PATHS, '/World/harvest_robot/box_bottom_left', '/World/harvest_robot/box_bottom_right',
                       '/World/transport_robot/cargo_box', '/World/transport_robot/top_lid_left',
                       '/World/transport_robot/top_lid_right', '/World/transport_robot/side_lid']
    bounds = []
    for frame in req['keyframes']:
        t = frame['time']; placements = frame['state']['placements']
        original = copy.deepcopy(placements)
        placements.pop(UNUSED, None)
        frame_bounds = []
        for i, path in enumerate(PATHS):
            j = slot[i]
            pose = np.asarray(original[PATHS[j]]['matrix'], float)
            if i != j:
                rotation = pose[:3, :3] / scales[j]
                center_world = pose[:3, 3] + rotation @ centers[j]
                old_bottom = (points[j] @ pose[:3, :3].T + pose[:3, 3])[:, 2].min()
                pose[:3, :3] = rotation * scales[i]
                pose[:3, 3] = center_world - rotation @ centers[i]
                new_bottom = (points[i] @ pose[:3, :3].T + pose[:3, 3])[:, 2].min()
                pose[2, 3] += old_bottom - new_bottom
            placements[path] = {'matrix': pose.tolist()}
            world = points[i] @ pose[:3, :3].T + pose[:3, 3]
            frame_bounds.append([world.min(0), world.max(0)])
        joints = frame['state']['joints']
        if t >= 2.15:
            gap = .105 * (1. - smooth(t, 2.15, 2.5))
            joints.update(box_bottom_left_joint=gap, box_bottom_right_joint=gap, harvest_lid_pinion_joint=gap * 23.8095238095)
        opening = 1. - smooth(t, 2.65, 3.35)
        joints.update(top_lid_left_joint=.155 * opening, top_lid_right_joint=.155 * opening, lid_pinion_joint=3.1 * opening,
                      side_lid_joint=0., box_tilt_joint=0.)
        bounds.append(frame_bounds)
    base['placements'].update(copy.deepcopy(req['keyframes'][0]['state']['placements']))
    base['joints'].update(req['keyframes'][0]['state']['joints'])
    cargo = np.asarray(old_evidence['cargo_world_at_05_end'])
    final = req['keyframes'][-1]['state']
    clones = []
    for i, path in enumerate(PATHS):
        m = np.asarray(final['placements'][path]['matrix'])
        clones.append({'path': path, 'source': sources[i]['source'], 'color': sources[i]['color'],
            'scale': scales[i].tolist(), 'mesh_local_bounds': [points[i].min(0).tolist(), points[i].max(0).tolist()],
            'trajectory_slot_from_v3': slot[i] + 1,
            'initial_world_matrix': req['keyframes'][0]['state']['placements'][path]['matrix'],
            'final_world_matrix': m.tolist(), 'final_cargo_matrix': (np.linalg.inv(cargo) @ m).tolist(),
            'final_world_mesh_bounds': np.asarray(bounds[-1][i]).tolist()})
    plates = [x for x in geometry['transport_visual_cubes'] if '/top_lid_' in x['path'] and x['actual_world_bounds_closed'][0][2] > .44]
    lid_bottom = min(x['actual_world_bounds_closed'][0][2] for x in plates)
    lid_top = max(x['actual_world_bounds_closed'][1][2] for x in plates)
    closing_bounds = np.asarray([b for k, b in zip(req['keyframes'], bounds) if k['time'] >= 2.65])
    fruit_clearance = float(lid_bottom - closing_bounds[:, :, 1, 2].max())
    panel_clearance = float(geometry['restored_harvest_floor_bounds'][0][2] - lid_top)
    max_overlap = 0.; overlap_frame = None
    for frame, boxes in enumerate(bounds):
        for i in range(6):
            for j in range(i + 1, 6):
                depth = float(np.min(np.minimum(boxes[i][1], boxes[j][1]) - np.maximum(boxes[i][0], boxes[j][0])))
                if depth > max_overlap:
                    max_overlap = depth; overlap_frame = {'frame': frame, 'ids': [PATHS[i], PATHS[j]]}
    lid_cube_overlap = 0.
    for frame, boxes in zip(req['keyframes'], bounds):
        if frame['time'] < 2.65:
            continue
        for cube in geometry['transport_visual_cubes']:
            if '/top_lid_' not in cube['path']:
                continue
            name = cube['path'].split('/')[3] + '_joint'
            offset = np.asarray(geometry['joints'][name]['axis_world']) * frame['state']['joints'][name]
            lo, hi = np.asarray(cube['actual_world_bounds_closed']) + offset
            for fruit_lo, fruit_hi in boxes:
                depth = float(np.min(np.minimum(hi, fruit_hi) - np.maximum(lo, fruit_lo)))
                lid_cube_overlap = max(lid_cube_overlap, depth)
    closed = {k: final['joints'][k] for k in ('top_lid_left_joint', 'top_lid_right_joint', 'lid_pinion_joint', 'side_lid_joint', 'box_tilt_joint')}
    checks = {'six_identical_ids_every_frame': all(set(k['state']['placements']) == set(PATHS) for k in req['keyframes']),
        'red_three_yellow_three': [x['color'] for x in clones].count('red') == 3 and [x['color'] for x in clones].count('yellow') == 3,
        'source_scales_preserved': all(np.allclose(np.linalg.norm(np.asarray(k['state']['placements'][p]['matrix'])[:3, :3], axis=0), scales[i]) for k in req['keyframes'] for i, p in enumerate(PATHS)),
        'closed_by_raw_3_35_s': all(k['state']['joints']['top_lid_left_joint'] == 0. for k in req['keyframes'] if k['time'] >= 3.35),
        'fruit_below_closing_top_lids': fruit_clearance > 0., 'harvest_floor_above_top_lids': panel_clearance > 0.,
        'all_moving_lid_visual_cubes_clear_fruit_aabbs': lid_cube_overlap == 0.,
        'top_lid_pinion_mimic_consistent': all(abs(k['state']['joints']['top_lid_left_joint'] - .05 * k['state']['joints']['lid_pinion_joint']) < 1e-12 and abs(k['state']['joints']['top_lid_right_joint'] - .05 * k['state']['joints']['lid_pinion_joint']) < 1e-12 for k in req['keyframes']),
        'pair_aabb_overlap_below_1mm': max_overlap < .001}
    evidence = {'scope': 'presentation staged animation only; no physical robot/autonomous/PhysX success claim',
        'offline_checks': checks, 'offline_all_pass': all(checks.values()), 'gui_review': 'not performed by this builder',
        'source_trajectory': str((V3 / '05_handoff.json').relative_to(ROOT)),
        'source_sha256': hashlib.sha256((V3 / '05_handoff.json').read_bytes()).hexdigest(),
        'method': 'V3 six baked trajectories reused; slots 5/6 exchanged from first frame with original scales and mesh-bottom height preserved. No new dynamic solver run.',
        'timeline_s': {'harvest_floor_open': [1., 1.65], 'harvest_floor_restore': [2.15, 2.5], 'transport_top_lids_close': [2.65, 3.35], 'hold_closed': [3.35, 5.]},
        'actual_top_lid_bottom_world_z_m': lid_bottom, 'minimum_fruit_top_to_closing_lid_m': fruit_clearance,
        'minimum_harvest_floor_to_transport_lid_m': panel_clearance,
        'max_pair_aabb_overlap_m': max_overlap, 'max_pair_aabb_overlap_at': overlap_frame,
        'max_closing_lid_visual_cube_fruit_aabb_overlap_m': lid_cube_overlap,
        'limits': 'Actual fruit vertex bounds and original USD plate vertices checked. Conservative AABB bounds are not full mesh collision/arm collision or physical dynamics validation. GUI/MP4 review required.',
        'mechanism_measurement': '05_mechanism_geometry.json', 'continuity_state': 'handoff_continuity_state.json'}
    state = {'schema_version': 1, 'fruit_count': 6, 'clones': clones, 'cargo_world_end': cargo.tolist(),
        'closed_joint_values': closed, 'harvest_floor_final_joint_values': {k: final['joints'][k] for k in ('box_bottom_left_joint', 'box_bottom_right_joint', 'harvest_lid_pinion_joint')},
        'source_mesh_points_file': str((V3 / 'handoff_mesh_points.json').relative_to(ROOT)),
        'groups_by_cargo_y': {'positive_RRY': [PATHS[0], PATHS[2], PATHS[5]], 'negative_RYY': [PATHS[1], PATHS[3], PATHS[4]]},
        'top_lid_clearance_m': fruit_clearance, 'gui_review': 'pending'}
    req['provenance'] = {'scope': evidence['scope'], 'fruit_count': 6, 'motion_evidence': '05_handoff_continuity_evidence.json',
        'continuity_state': 'handoff_continuity_state.json', 'house_hidden': False, 'same_asset_scales': True}
    write('05_handoff_continuity.json', req)
    write('05_handoff_continuity_evidence.json', evidence)
    write('handoff_continuity_state.json', state)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if '--inspect-usd' in sys.argv:
        inspect_usd()
    else:
        build()
