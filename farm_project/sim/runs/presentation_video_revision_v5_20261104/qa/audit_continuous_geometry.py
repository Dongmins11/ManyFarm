"""V5 연속 영상의 독립 기하 검산. 설정/구현은 읽고 qa 결과만 쓴다.

pxr Python: --export-usd; numpy/scipy Python: 인자 없이 검사.
원본 Cube OBB와 과실 convex hull의 교차는 보수적 검사다.
"""
from __future__ import annotations
import ast
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
ROOT = RUN.parents[2]
SETTINGS = RUN / 'settings'
V3 = ROOT / 'sim/runs/presentation_video_revision_v3_20261104/settings'
VENDOR = ROOT / 'sim/vendor/hcr3a_20261008/HCR3A_SIM_TEAM_20261008/workspace/src/smartfarm_description'


def read(p: Path) -> dict:
    return json.loads(p.read_text())


def write(p: Path, data: dict) -> None:
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def export_usd() -> None:
    from pxr import Usd, UsdGeom, UsdPhysics, Gf
    result = {}; joint_result = {}
    for role, asset in [('transport', ROOT / 'sim/assets/robots/transport_robot/urdf/transport_robot.portable/transport_robot.sim.usda'),
                        ('arm', ROOT / 'sim/assets/props/HCR3A/hcr3a.usd')]:
        stage = Usd.Stage.Open(str(asset)); root = stage.GetDefaultPrim()
        initial = {}; cubes = []
        for child in root.GetChildren():
            if child.IsA(UsdGeom.Xformable):
                initial[str(child.GetPath())] = np.asarray(UsdGeom.Xformable(child).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T.tolist()
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
            path = str(prim.GetPath())
            if not prim.IsA(UsdGeom.Cube) or '/visuals/' not in path:
                continue
            body = '/'.join(path.split('/')[:3]); b = np.asarray(initial[body])
            world = np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
            relative = np.linalg.inv(b) @ world
            cubes.append({'path': path, 'body': body, 'size': UsdGeom.Cube(prim).GetSizeAttr().Get(), 'body_relative_matrix': relative.tolist()})
        result[role] = {'source': str(asset.relative_to(ROOT)), 'source_sha256': hashlib.sha256(asset.read_bytes()).hexdigest(), 'initial_links': initial, 'visual_cubes': cubes}
        joint_result[role] = {}
        for prim in stage.Traverse():
            if not prim.IsA(UsdPhysics.Joint):
                continue
            joint = UsdPhysics.Joint(prim)
            a = joint.GetBody0Rel().GetTargets(); b = joint.GetBody1Rel().GetTargets()
            if not a or not b:
                continue
            frames = []
            for i in (0, 1):
                q = getattr(joint, f'GetLocalRot{i}Attr')().Get()
                frame = np.eye(4)
                frame[:3, :3] = np.asarray(Gf.Matrix3d(Gf.Rotation(q))).T
                frame[:3, 3] = getattr(joint, f'GetLocalPos{i}Attr')().Get()
                frames.append(frame.tolist())
            joint_result[role][prim.GetName()] = {
                'a': str(a[0]), 'b': str(b[0]), 'f0': frames[0], 'f1': frames[1],
                'axis': 'XYZ'.index(prim.GetAttribute('physics:axis').Get() or 'X'),
                'kind': prim.GetTypeName(), 'lower': prim.GetAttribute('physics:lowerLimit').Get(),
                'upper': prim.GetAttribute('physics:upperLimit').Get()}
    write(HERE / '06_07_actual_robot_cubes.json', result)
    write(SETTINGS / '06_07_source_joint_geometry.json', joint_result)


def station_cubes(cfg: dict) -> list:
    """원본 create_station의 box 배치 식을 그대로 평가하되 USD/물리 생성은 하지 않는다."""
    source = VENDOR / 'scripts/hcr3a_environment.py'
    tree = ast.parse(source.read_text()); function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_station')
    start = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'panel')
    # visual-only PlateGroove loop와 최종 반환을 제외한다. 원본 box 호출/배치 식은 보존한다.
    body = [n for n in function.body[start:] if not isinstance(n, ast.Return) and 'UsdGeom' not in ast.unparse(n)]
    cubes = []
    def box(name: str, size: list, center: list, rot_y: float = 0., **kwargs: dict) -> None:
        a = math.radians(rot_y); r = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
        m = np.eye(4); m[:3, :3] = r * size; m[:3, 3] = center
        cubes.append({'path': '/World/HCRStation/' + name, 'size': 1., 'matrix': m.tolist()})
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(source), 'exec'), {'cfg': cfg, 'math': math, 'box': box})
    return cubes


def check() -> None:
    from scipy.spatial import ConvexHull
    from scipy.spatial.transform import Rotation
    from scipy.optimize import linprog
    request_path = SETTINGS / '06_07_transport_sorting.json'
    request_bytes = request_path.read_bytes()
    req = json.loads(request_bytes); evidence = read(SETTINGS / '06_07_motion_evidence.json')
    assert len(req['keyframes']) == len(evidence['frames']) == 361
    assert all(abs(k['time']-f['time_s']) < 1e-9 and f['frame']==i
               for i,(k,f) in enumerate(zip(req['keyframes'],evidence['frames'])))
    input_paths = [request_path, SETTINGS / '06_07_motion_evidence.json', SETTINGS / '06_07_source_joint_geometry.json',
        HERE / '06_07_actual_robot_cubes.json', V3 / 'handoff_mesh_points.json',
        VENDOR / 'config/hcr3a_random8_validation.json', VENDOR / 'scripts/hcr3a_environment.py']
    source_hashes = {os.path.relpath(p, RUN): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
    joints = read(SETTINGS / '06_07_source_joint_geometry.json'); geometry = read(HERE / '06_07_actual_robot_cubes.json')
    cfg = read(VENDOR / 'config/hcr3a_random8_validation.json'); station = station_cubes(cfg)
    write(HERE / '06_07_actual_station_boxes.json', {'source': 'original hcr3a_environment.py box expressions; physics/visual-only grooves omitted', 'boxes': station})
    meshes = {x['source']: np.asarray(x['root_local_points']) for x in read(V3 / 'handoff_mesh_points.json')}
    fruits = evidence['fruits']; local_points = [meshes[x['source']] for x in fruits]
    hulls = [ConvexHull(x) for x in local_points]
    T = np.asarray(evidence['station_transform']); invT = np.linalg.inv(T)
    base_arm = invT @ np.asarray(req['base']['placements']['/World/HCRRobot']['matrix'])
    identity = np.eye(4)
    def frames(role: str, q: dict) -> dict:
        data = joints[role]; initial = geometry[role]['initial_links']; by_child = {j['b']: (n, j) for n, j in data.items()}; cache = {}
        def rec(path: str) -> np.ndarray:
            if path in cache: return cache[path]
            if path not in by_child: return np.asarray(initial.get(path, identity))
            name, j = by_child[path]; d = np.eye(4); value = q.get(name, 0.)
            if j['kind'] == 'PhysicsRevoluteJoint': d[:3, :3] = Rotation.from_rotvec(np.eye(3)[j['axis']] * value).as_matrix()
            elif j['kind'] == 'PhysicsPrismaticJoint': d[j['axis'], 3] = value
            cache[path] = rec(j['a']) @ np.asarray(j['f0']) @ d @ np.linalg.inv(np.asarray(j['f1']))
            return cache[path]
        for path in by_child: rec(path)
        return {**{p: np.asarray(x) for p, x in initial.items()}, **cache}
    signs = np.asarray(list(itertools.product([-.5, .5], repeat=3)))
    stats = {}; actual_stats = {}; events = []; jaw = []; blocking = []; hull_only = []; tcp_markers = []
    arm_station = {}; limits = []; minimum_surface = 1.; minimum_surface_event = None
    def intersect(points: np.ndarray, planes: np.ndarray, cube_matrix: np.ndarray, size: float, bounds: tuple | None = None) -> tuple[float, float]:
        corners = signs * size @ cube_matrix[:3, :3].T + cube_matrix[:3, 3]
        lo, hi = (points.min(0), points.max(0)) if bounds is None else bounds
        if np.any(hi <= corners.min(0)) or np.any(lo >= corners.max(0)): return 0., 0.
        inv = np.linalg.inv(cube_matrix); n = np.r_[inv[:3, :3], -inv[:3, :3]]; d = np.r_[inv[:3, 3] - size / 2, -inv[:3, 3] - size / 2]
        norms = np.linalg.norm(n, axis=1); n /= norms[:, None]; d /= norms
        penetration = np.minimum(-(points @ n.T + d), 1e9).min(1).max()
        eq = np.r_[planes, np.c_[n, d]]
        lp = linprog([0., 0., 0., -1.], A_ub=np.c_[eq[:, :3], np.ones(len(eq))], b_ub=-eq[:, 3], bounds=[(None, None)] * 4, method='highs')
        return max(0., float(lp.x[3])) if lp.success else 0., max(0., float(penetration))
    for frame, log in zip(req['keyframes'], evidence['frames']):
        t = frame['time']; q = frame['state']['joints']; arm = frames('arm', q); transport = frames('transport', q)
        base_t = invT @ np.asarray(frame['state']['placements']['/World/transport_robot']['matrix'])
        obstacles = []
        for role, base, links in [('arm', base_arm, arm), ('transport', base_t, transport)]:
            for cube in geometry[role]['visual_cubes']:
                if role == 'transport' and not any('/' + n + '/' in cube['path'] for n in ('cargo_box', 'top_lid_left', 'top_lid_right', 'side_lid')): continue
                obstacles.append((cube['path'], base @ links[cube['body']] @ np.asarray(cube['body_relative_matrix']), cube['size']))
        obstacles += [(c['path'], np.asarray(c['matrix']), c['size']) for c in station]
        if t >= 4.3:
            for path, matrix, size in obstacles:
                if not path.startswith('/hcr3a_functional/') or any('/' + n + '/' in path for n in ('base', 'link1', 'tcp')):
                    continue
                corners = signs * size @ matrix[:3, :3].T + matrix[:3, 3]
                inv = np.linalg.inv(matrix); n = np.r_[inv[:3, :3], -inv[:3, :3]]; d = np.r_[inv[:3, 3] - size / 2, -inv[:3, 3] - size / 2]
                norm = np.linalg.norm(n, axis=1); planes = np.c_[n / norm[:, None], d / norm]
                for obstacle, target, target_size in obstacles:
                    if not obstacle.startswith('/World/HCRStation/'):
                        continue
                    radius, vertex = intersect(corners, planes, target, target_size)
                    key = path + '|' + obstacle
                    if radius > 1e-6 and (key not in arm_station or radius > arm_station[key]['intersection_inscribed_radius_m']):
                        arm_station[key] = {'time_s': t, 'frame': log['frame'], 'arm': path, 'obstacle': obstacle, 'intersection_inscribed_radius_m': radius, 'actual_cube_corner_penetration_m': vertex}
        for role in ('arm', 'transport'):
            for name, j in joints[role].items():
                if name not in q or j['lower'] is None or j['upper'] is None: continue
                value = math.degrees(q[name]) if j['kind'] == 'PhysicsRevoluteJoint' else q[name]
                if value < j['lower'] - 1e-6 or value > j['upper'] + 1e-6: limits.append({'time': t, 'joint': name, 'value': value, 'limits': [j['lower'], j['upper']]})
        for i, fruit in enumerate(fruits):
            state = log['fruit_states'][fruit['id']]; pose = np.asarray(state['station_local_matrix'])
            points = local_points[i] @ pose[:3, :3].T + pose[:3, 3]
            bounds = (points.min(0), points.max(0))
            inv_a = np.linalg.inv(pose[:3, :3]); normals = hulls[i].equations[:, :3] @ inv_a
            offsets = hulls[i].equations[:, 3] - normals @ pose[:3, 3]; norms = np.linalg.norm(normals, axis=1)
            planes = np.c_[normals / norms[:, None], offsets / norms]
            if state['location'] in ('cargo', 'lane'):
                intake = cfg['intake']; run = math.sqrt(intake['slope_length'] ** 2 - intake['rise'] ** 2); slope = intake['rise'] / run
                active = (points[:, 0] >= intake['low_x']) & (points[:, 0] <= intake['low_x'] + run) & (abs(points[:, 1]) < intake['width'] / 2)
                if active.any():
                    plane_z = cfg['base_z'] + (points[active, 0] - intake['low_x']) * slope + intake['board'] / 2 * (math.sqrt(1 + slope * slope) - 1)
                    gap = float(np.min(points[active, 2] - plane_z))
                    if gap < minimum_surface: minimum_surface = gap; minimum_surface_event = {'time_s': t, 'id': fruit['id'], 'phase': state['phase']}
            for path, matrix, size in obstacles:
                radius, vertex_depth = intersect(points, planes, matrix, size, bounds)
                if radius <= 1e-6: continue
                item = {'time_s': t, 'frame': log['frame'], 'fruit': fruit['id'], 'obstacle': path, 'phase': state['phase'], 'convex_intersection_inscribed_radius_m': radius, 'actual_vertex_max_penetration_m': vertex_depth}
                key = fruit['id'] + '|' + path + '|' + state['phase']
                if key not in stats or radius > stats[key]['convex_intersection_inscribed_radius_m']: stats[key] = item
                if key not in actual_stats or vertex_depth > actual_stats[key]['actual_vertex_max_penetration_m']: actual_stats[key] = item
                if ('/left_pad/' in path or '/right_pad/' in path or '/left_finger/' in path or '/right_finger/' in path) and state['location'] == 'gripper': jaw.append(item)
                else: events.append(item)
                pick = next((x for x in evidence['picks'] if x['id'] == fruit['id']), None)
                gripping = pick and pick['attach_time_s'] - .1 <= t < pick['release_time_s']
                if '/tcp/visuals/' in path:
                    tcp_markers.append(item)
                elif gripping and ('/left_pad/' in path or '/right_pad/' in path) and vertex_depth <= .00205:
                    item['contact_class'] = 'allowed_grip_pad_contact'
                elif vertex_depth > .00005:
                    item['contact_class'] = 'blocking_actual_vertex_penetration'; blocking.append(item)
                else:
                    item['contact_class'] = 'conservative_hull_only'; hull_only.append(item)
    result = {'request_sha256': hashlib.sha256(request_bytes).hexdigest(), 'request_unchanged_at_check_end': request_path.read_bytes() == request_bytes, 'frames_checked': len(req['keyframes']),
        'evidence_sha256': source_hashes['settings/06_07_motion_evidence.json'], 'source_hashes': source_hashes,
        'all_sources_unchanged_at_check_end': all(hashlib.sha256((RUN / path).read_bytes()).hexdigest() == value for path, value in source_hashes.items()),
        'method': 'independent original USD Cube OBB + original fruit convex hull feasibility; actual vertex penetration retained; original station box expressions',
        'limits': 'Convex hull can fill pepper concavities; intersection is a conservative alarm, actual vertex inside a cube is stronger evidence. No dynamic solver or continuous-time swept collision.',
        'max_events_by_fruit_and_obstacle': list(stats.values()), 'non_gripper_contact_events': len(events), 'attached_gripper_contact_events': len(jaw),
        'max_actual_vertex_events_by_phase': list(actual_stats.values()),
        'blocking_events': blocking,
        'conservative_hull_only_events': hull_only,
        'allowed_grip_pad_contacts': [x for x in [*jaw, *events] if x.get('contact_class') == 'allowed_grip_pad_contact'],
        'excluded_nonphysical_tcp_marker_contacts': tcp_markers,
        'actual_arm_cube_station_intersections': list(arm_station.values()),
        'blocking_arm_station_events': [x for x in arm_station.values() if x['intersection_inscribed_radius_m'] > .00001],
        'joint_limit_events': limits, 'minimum_intake_mesh_vertical_gap_m': minimum_surface, 'minimum_intake_mesh_gap_at': minimum_surface_event,
        'contact_thresholds_m': {'actual_vertex_blocking': .00005, 'grip_pad_allowed_max': .00205, 'arm_station_inscribed_radius_blocking': .00001},
        'contact_policy': {'actual_vertex_tolerance_m': .00005, 'allowed_grip_pad_penetration_m': .00205, 'pre_attach_contact_window_s': .1, 'arm_station_radius_tolerance_m': .00001},
        'gui_review': 'none by this script', 'automatically_declared_pass': False}
    write(HERE / '06_07_independent_geometry_audit.json', result)
    print(json.dumps({'frames': result['frames_checked'], 'pairs_with_intersection': len(stats), 'non_gripper_contact_events': len(events), 'joint_limit_events': len(limits), 'intake_min_gap': minimum_surface}))


if __name__ == '__main__':
    if '--export-usd' in sys.argv: export_usd()
    else: check()
