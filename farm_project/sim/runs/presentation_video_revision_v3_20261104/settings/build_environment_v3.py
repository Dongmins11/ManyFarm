"""V3 촬영 01/02/07 설정 생성. USD를 읽고 메모리에서만 측정하며 GUI는 실행하지 않는다.

Isaac Python + omni.usd.libs/PhysxSchema Python/library 경로에서 실행한다.
원본 USD, 공통 코드, 앞선 촬영 설정은 저장하거나 변경하지 않는다.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
import types
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from pxr import Gf, Usd, UsdGeom

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = ROOT / 'sim/runs/presentation_video_retake_20261104'
FIRST = ROOT / 'sim/runs/presentation_video_20261104'
FRUIT = '/World/Vegetation/Bed_02/Fruits/Pepper_0003_red'


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(name: str, value: object) -> None:
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def pose(xyz: list[float], yaw: float = 0.0) -> np.ndarray:
    result = np.eye(4)
    result[:3, :3] = Rotation.from_euler('z', yaw).as_matrix()
    result[:3, 3] = xyz
    return result


def matrix(prim: object) -> np.ndarray:
    return np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T


def set_matrix(prim: object, value: np.ndarray) -> None:
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    xform.AddTransformOp().Set(Gf.Matrix4d(*map(float, value.T.flat)))


def bbox(stage: object, path: str) -> list[list[float]]:
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    box = cache.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
    return [list(box.GetMin()), list(box.GetMax())]


def restore_house(request: dict, house_paths: list[str]) -> None:
    """촬영 설정의 숨김을 제거하고 원본 온실 전체를 명시적으로 표시한다."""
    for state in [request['base'], *[k.get('state', {}) for k in request['keyframes']]]:
        if 'hide' in state:
            state['hide'] = [p for p in state['hide'] if not p.startswith('/World/farm_framechanged') and p != '/World/AprilTags']
    request['base']['show'] = list(dict.fromkeys(request['base'].get('show', []) + house_paths + ['/World/AprilTags']))
    request['preview_only'] = False
    request['preview_warmup_frames'] = 48


def create_station_for_measurement(stage: object, source: Path, cfg: dict) -> None:
    """원래 생성 함수에 메모리 stage만 제공하는 오프라인 측정용 어댑터."""
    # upstream 함수가 sim에서 사용하는 것은 get_current_stage() 한 개뿐이다.
    saved = {name: sys.modules.get(name) for name in ('isaaclab', 'isaaclab.sim')}
    package = types.ModuleType('isaaclab')
    module = types.ModuleType('isaaclab.sim')
    module.get_current_stage = lambda: stage
    package.sim = module
    sys.modules.update({'isaaclab': package, 'isaaclab.sim': module})
    try:
        spec = importlib.util.spec_from_file_location('v3_measure_station', source)
        env = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(env)
        env.create_station(cfg)
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def main() -> None:
    import pxr
    from pxr import Plug
    for package in Path(sys.prefix).glob('lib/python*/site-packages/isaacsim/extscache/omni.usd.schema.physx-*/pxr'):
        if str(package) not in pxr.__path__:
            pxr.__path__.append(str(package))
        for info in package.parent.rglob('plugInfo.json'):
            Plug.Registry().RegisterPlugins(str(info))
    scout = read(HERE / 'scout.json')
    stage = Usd.Stage.Open(str(ROOT / 'sim/assets' / scout['scene']))
    stage.SetEditTarget(stage.GetSessionLayer())
    house_paths = ['/World/farm_framechanged'] + [str(p.GetPath()) for p in stage.GetPrimAtPath('/World/farm_framechanged').GetChildren() if p.IsA(UsdGeom.Imageable)]
    geometry = {'source_scene': scout['scene'], 'scope': 'USD geometry inspection only; no GUI or physics execution',
                'beds': {f'Bed_{n:02d}': bbox(stage, f'/World/Vegetation/Bed_{n:02d}') for n in range(1, 9)},
                'house': {p: bbox(stage, p) for p in house_paths if any(s in p for s in ('Cover_', 'Entry_', 'Rail_02'))}}

    # 북쪽 네 베드: 실제 월드 Y가 양수인 Bed_02/04/06/08, 중앙 X=0 통로.
    overview = read(FIRST / 'settings/01_overview.json')
    restore_house(overview, house_paths)
    overview.update(easing='linear', preview_frames=[0, 30, 75, 119, 149])
    eye = np.array([0.0, 11.0, 3.8])
    target = np.array([0.0, 7.2, 0.6])
    overview['base'].update(eye=eye.tolist(), target=target.tolist(), focal_mm=22, fill_intensity=65)
    overview['keyframes'] = []
    # 처음/끝 0.12초만 속도를 완화하고 나머지는 일정속도. 총 2.4m = 베드 길이 30%.
    ramp = .12
    speed = 2.4 / (3.0 - ramp)
    for frame in range(151):
        t = frame / 30
        u = min(3.0, max(0.0, t - 1.0))
        if u < ramp:
            distance = speed * u * u / (2 * ramp)
        elif u > 3.0 - ramp:
            distance = 2.4 - speed * (3.0 - u) ** 2 / (2 * ramp)
        else:
            distance = speed * (u - ramp / 2)
        delta = np.array([0., -distance, 0.])
        overview['keyframes'].append({'time': t, 'state': {'eye': (eye + delta).tolist(), 'target': (target + delta).tolist()}})
    overview['v3_evidence'] = dict(beds=['Bed_02', 'Bed_04', 'Bed_06', 'Bed_08'], long_axis='Y', corridor_center_x=0,
                                 eye_height_m=3.8, crop_max_height_m=max(v[1][2] for v in geometry['beds'].values()),
                                 center_roof_height_m=5.012, travel_m=2.4, pitch_deg=math.degrees(math.atan2(3.2, 3.8)),
                                 source_reference='../01_drone_camera_reference.jpg', greenhouse_hidden=False, visual_review='pending GUI')
    overview['name'] = '01_overview_narrow'
    write('01_overview_narrow.json', overview)
    wide = copy.deepcopy(overview)
    wide['name'] = '01_overview_wide'
    wide['base']['focal_mm'] = 14
    for state in [wide['base'], *[item['state'] for item in wide['keyframes']]]:
        state['target'] = [state['eye'][0], state['eye'][1]-3.2/math.tan(math.radians(35)), .6]
    wide['v3_evidence'].update(pitch_deg=35, camera_revision='Initial GUI lacked greenhouse; 14mm/35deg wide candidate, pending GUI')
    write('01_overview_wide.json', wide)
    selected = copy.deepcopy(wide)
    selected['name'] = '01_overview'
    selected['v3_evidence']['visual_review'] = 'GUI start/end inspected: greenhouse arches/film and central corridor visible; approved final camera'
    write('01_overview.json', selected)

    scout_clip = read(OLD / 'settings/02_scout.json')
    restore_house(scout_clip, house_paths)
    scout_clip['preview_frames'] = [0, 75, 149]
    scout_clip['v3_evidence'] = dict(camera='D refined camera and original 0.4 m route / 70% tracking preserved', greenhouse_hidden=False, visual_review='pending GUI')
    write('02_scout.json', scout_clip)

    sorter = read(HERE / 'sorter.json')
    vendor = ROOT / sorter['source_workspace']
    cfg = read(vendor / sorter['source_config'])
    create_station_for_measurement(stage, vendor / 'src/smartfarm_description/scripts/hcr3a_environment.py', cfg)
    old_station = pose(sorter['station_pose_world_m'], sorter['station_yaw_rad'])
    new_station = pose([-5.4, 13.1, 0.0], sorter['station_yaw_rad'])
    relocation = new_station @ np.linalg.inv(old_station)
    arm_local = pose([0., 0., cfg['base_z']])
    roots = {'/World/HCRStation': {'matrix': new_station.tolist()}, '/World/HCRRobot': {'matrix': (new_station @ arm_local).tolist()}}
    station_local_bounds = bbox(stage, '/World/HCRStation')
    set_matrix(stage.GetPrimAtPath('/World/HCRStation'), new_station)
    transform_record = dict(scope='User-authorized filming session relocation only; operational map and station config unchanged',
                            old_station_world=old_station.tolist(), new_station_world=new_station.tolist(),
                            world_rigid_transform=relocation.tolist(), placements=roots,
                            station_local_bounds_m=station_local_bounds, station_world_bounds_m=bbox(stage, '/World/HCRStation'),
                            geometry_source=str((vendor / 'src/smartfarm_description/scripts/hcr3a_environment.py').relative_to(ROOT)),
                            constraint='Station and camera inside greenhouse x(-8,8), y(-15,15), north of beds ending at y≈10.26')
    write('station_transform.json', transform_record)

    sorting = read(OLD / 'settings/07_sorting.json')
    restore_house(sorting, house_paths)
    sorting.update(duration_s=7, easing='linear', preview_frames=[0, 30, 69, 78, 84, 90, 99, 111, 120, 150, 179, 209])
    base = sorting['base']
    base['placements'].update(roots)
    for key in ('eye', 'target'):
        base[key] = (relocation @ np.r_[base[key], 1.])[:3].tolist()
        base['side_key'][key] = (relocation @ np.r_[base['side_key'][key], 1.])[:3].tolist()
    base['placements'][FRUIT]['matrix'] = (relocation @ np.asarray(base['placements'][FRUIT]['matrix'])).tolist()
    base['inspect'] += ['/World/HCRStation', '/World/HCRRobot', '/World/HCRStation/RedStorageSlope', '/World/HCRStation/YellowBinFloor']

    fruit_prim = stage.GetPrimAtPath(FRUIT)
    original_root = matrix(fruit_prim)
    pieces = []
    for prim in Usd.PrimRange(fruit_prim, Usd.TraverseInstanceProxies()):
        if prim.IsA(UsdGeom.Mesh):
            points = np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get())
            relative = np.linalg.inv(original_root) @ matrix(prim)
            pieces.append((relative @ np.c_[points, np.ones(len(points))].T).T[:, :3])
    mesh = np.concatenate(pieces)
    old_keyframes = sorting['keyframes']
    release_world = np.asarray(next(k['state']['placements'][FRUIT]['matrix'] for k in old_keyframes if k['time'] == 2.6))
    release_local = np.linalg.inv(old_station) @ release_world
    scale = np.linalg.norm(release_local[:3, :3], axis=0)
    orientation = release_local[:3, :3] / scale
    mesh *= scale
    local_release = release_local[:3, 3]
    storage = cfg['storage']
    slope_run = math.sqrt(storage['ramp_length'] ** 2 - storage['ramp_rise'] ** 2)
    slope_angle = math.asin(storage['ramp_rise'] / storage['ramp_length'])
    high_x, low_x = storage['drop_x'], storage['drop_x'] - slope_run
    floor_z = storage['drop_z'] - storage['ramp_rise']
    # 5mm 큐브 판은 중심 Z에서 2.5mm 하향 배치 후 -30° 회전한다.
    top_correction = .0025 / math.cos(slope_angle) - .0025

    def floor_height(x: np.ndarray) -> np.ndarray:
        return np.where(x >= low_x, storage['drop_z'] + (x - high_x) * math.tan(slope_angle) + top_correction, floor_z)

    def support_z(x: float, rotation: np.ndarray) -> float:
        points = mesh @ rotation.T
        return float(np.max(floor_height(x + points[:, 0]) - points[:, 2])) + .0005

    effective_radius = float((np.ptp(mesh[:, 0]) + np.ptp(mesh[:, 2])) / 4)
    release_t = 2.6
    gravity = 9.81

    def air_rotation(dt: float) -> np.ndarray:
        return Rotation.from_rotvec([.20 * dt, 0, .12 * dt]).as_matrix() @ orientation

    lo, hi = 0., .4
    for _ in range(60):
        dt = (lo + hi) / 2
        if local_release[2] - gravity * dt * dt / 2 > support_z(local_release[0], air_rotation(dt)):
            lo = dt
        else:
            hi = dt
    fall_s = (lo + hi) / 2
    contact_t = release_t + fall_s
    contact_rotation = air_rotation(fall_s)
    ramp_distance = (local_release[0] - low_x) / math.cos(slope_angle)
    # 짧은 촬영 구간의 감쇠 구름. 이동량과 회전량을 항상 s/r로 연결한다.
    ramp_s = .70
    terminal_speed = 2 * ramp_distance / ramp_s
    flat_distance = .12
    flat_s = 2 * flat_distance / terminal_speed
    stable_t = contact_t + ramp_s + flat_s
    assert stable_t < 4.0
    q0 = dict(base['joints'])
    q1 = next(k['state']['joints'] for k in old_keyframes if k['time'] == 2.3)
    ledger = []
    sorting['keyframes'] = []
    for frame in range(211):
        t = frame / 30
        u = min(1., max(0., (t - 1.) / 1.3)); u = u*u*(3-2*u)
        joints = {k: q0.get(k, v) * (1-u) + v*u for k, v in q1.items()}
        jaw_u = min(1., max(0., (t - 2.3) / .25)); jaw_u = jaw_u*jaw_u*(3-2*jaw_u)
        joints.update(left_jaw=.004+.006*jaw_u, right_jaw=.004+.006*jaw_u)
        state = {'joints': joints}
        phase = 'attached_transfer'
        if t >= release_t:
            dt = t-release_t
            state['attach_fruits'] = []
            center = local_release.copy()
            distance = 0.
            if dt < fall_s:
                phase = 'gravity_fall'
                rotation = air_rotation(dt)
                center[2] -= gravity * dt * dt / 2
            else:
                roll_t = t-contact_t
                if roll_t < ramp_s:
                    phase = 'slope_roll'
                    distance = ramp_distance * (roll_t/ramp_s)**2
                    center[0] -= distance * math.cos(slope_angle)
                else:
                    phase = 'bin_deceleration' if roll_t < ramp_s+flat_s else 'stable'
                    fraction = min(1., max(0., (roll_t-ramp_s)/flat_s))
                    flat = flat_distance * (2*fraction-fraction*fraction)
                    distance = ramp_distance+flat
                    center[0] = low_x-flat
                theta = distance/effective_radius
                wobble = .025 * math.sin(theta*2.3) * max(0., 1-(roll_t/(ramp_s+flat_s)))
                rotation = Rotation.from_rotvec([0, -theta, 0]).as_matrix() @ Rotation.from_rotvec([wobble, 0, 0]).as_matrix() @ contact_rotation
                center[2] = support_z(center[0], rotation)
            fruit_pose = np.eye(4)
            fruit_pose[:3, :3] = rotation * scale
            fruit_pose[:3, 3] = center
            world_pose = new_station @ fruit_pose
            state['placements'] = {FRUIT: {'matrix': world_pose.tolist()}}
            points = mesh @ rotation.T + center
            clearance = float(np.min(points[:, 2]-floor_height(points[:, 0])))
            ledger.append(dict(frame=frame,time_s=t,phase=phase,station_local_center=center.tolist(),world_matrix=world_pose.tolist(),
                               travel_since_contact_m=distance,rolling_angle_rad=distance/effective_radius,minimum_surface_clearance_m=clearance))
        sorting['keyframes'].append(dict(time=t, state=state))
    sorting['v3_evidence'] = dict(station_transform='station_transform.json', motion='07_motion_evidence.json',
                                source='existing HCR storage slope cubes and actual Pepper_0003_red mesh',
                                greenhouse_hidden=False, stable_from_s=stable_t, stable_interval_s=[4,7], visual_review='pending GUI')
    sorting['name'] = '07_sorting_high'
    write('07_sorting_high.json', sorting)
    low = copy.deepcopy(sorting)
    low['name'] = '07_sorting_low'
    direction = np.asarray(base['eye'][:2])-np.asarray(base['target'][:2])
    direction /= np.linalg.norm(direction)
    low['base']['eye'] = [*(np.asarray(base['target'][:2])+direction*2.5), 1.43]
    low['base']['focal_mm'] = 32
    low['v3_evidence']['camera_revision'] = dict(reason='Initial GUI lacked greenhouse; lower/wider same front angle', xy_distance_m=2.5,
                                               pitch_deg=math.degrees(math.atan2(.83,2.5)), visual_review='pending GUI')
    write('07_sorting_low.json', low)
    refined = copy.deepcopy(low)
    refined['name'] = '07_sorting_low_refined'
    refined['base']['focal_mm'] = 28.5
    refined['preview_frames'] = [0, 78, 90, 120, 209]
    refined['v3_evidence']['camera_revision'].update(focal_mm=28.5, reason='Low-view GUI cropped wall bottom; focal-only correction',
                                                   station_bounds_projection_px=[510,303,1472,1053], visual_review='pending GUI')
    write('07_sorting_low_refined.json', refined)
    selected_sorting = copy.deepcopy(refined)
    selected_sorting['name'] = '07_sorting'
    selected_sorting['v3_evidence']['visual_review'] = 'GUI frames 0/78/90/120/209 inspected: station/arm in frame; greenhouse posts/film and bed tags visible; fruit rolls/settles with final partial bin-lip occlusion'
    selected_sorting['v3_evidence']['camera_revision']['visual_review'] = 'approved final GUI camera'
    write('07_sorting.json', selected_sorting)
    write('07_motion_evidence.json', dict(scope='Deterministic staged kinematic bake, not autonomous or contact-solver success',
          fruit=FRUIT, mesh_vertices=len(mesh), scaled_mesh_bounds_m=[mesh.min(0).tolist(),mesh.max(0).tolist()],
          gravity_m_s2=gravity, release_time_s=release_t, first_contact_time_s=contact_t, stable_from_s=stable_t,
          slope_angle_deg=math.degrees(slope_angle), actual_slope_length_m=storage['ramp_length'],
          effective_radius_m=effective_radius, ramp_roll_distance_m=ramp_distance, bin_roll_distance_m=flat_distance,
          rolling_model='angle=distance/effective_radius; bounded damped wobble; vertex-based support height on actual piecewise slope/floor',
          no_mesh_penetration_in_baked_surface_samples=all(row['minimum_surface_clearance_m'] >= 0 for row in ledger), samples=ledger))
    geometry['station'] = transform_record
    write('environment_geometry_evidence.json', geometry)
    print(json.dumps({'generated':['01_overview.json','02_scout.json','07_sorting.json','station_transform.json','07_motion_evidence.json','environment_geometry_evidence.json'],
                      'contact_s':contact_t,'stable_s':stable_t,'station_bounds':transform_record['station_world_bounds_m']},ensure_ascii=False))


if __name__ == '__main__':
    main()
