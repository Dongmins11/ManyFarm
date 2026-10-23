#!/usr/bin/env python3
"""시뮬 빨강/노랑 과실의 실제 물리 모델 외곽을 기존 작업 범위 안으로 재배치한다."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_sim_runtime', 'farm_sim_devices'):
    sys.path.insert(0, str(ROOT/'sim/ros_ws/src'/package))
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/scout_robot'))
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/farm_navigation'))


def main() -> None:
    from pxr import Gf, Usd, UsdGeom, Vt
    from farm_sim_runtime.fruit_asset_setup import configure_farm_fruits
    from scout_robot.survey_core import StraightBed, transform_points
    from scout_robot.route import load_route
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--margin', type=float, default=.001, help='외곽 경계 안쪽 여유(m)')
    args = parser.parse_args()
    if not 0 < args.margin < .02:
        raise ValueError('여유는 0~2cm 사이여야 합니다.')
    scene = ROOT/'sim/assets/envs/output/farm_with_plants_v5.usd'
    survey = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout_survey.json').read_text())
    physics = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json').read_text())['fruit']
    device = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())['device']
    stage = Usd.Stage.Open(str(scene))
    transforms = UsdGeom.XformCache()
    originals = {str(p.GetPath()): np.asarray(transforms.GetLocalToWorldTransform(p)).T.copy()
                 for p in stage.Traverse() if p.GetAttribute('crop:color').Get()}
    records = configure_farm_fruits(stage, ROOT, physics, survey)
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render'], useExtentsHint=False)
    boxes = {}
    for record in records:
        box = cache.ComputeWorldBound(stage.GetPrimAtPath(record['prim_path'])).ComputeAlignedRange()
        boxes[record['prim_path']] = np.array([box.GetMin(), box.GetMax()])
    T = np.array(survey['evaluation']['T_map_world'])
    inverse = np.linalg.inv(T)
    beds = {sec: StraightBed(load_route(ROOT/c['route_file'], c['node_ids']), c)
            for sec, c in survey['sections'].items()}
    changes = []
    checked = []
    for record in records:
        if record['color'] not in ('red', 'yellow'):
            continue
        path = record['prim_path']
        box = boxes[path]
        corners = transform_points(T, list(itertools.product(*zip(*box))))
        center = corners.mean(0)
        options = [(sec, b) for sec, b in beds.items()
                   if survey['sections'][sec]['evaluation_bed_prim'] == record['bed_prim']]
        sec, bed = min(options, key=lambda item: abs(item[1].local(center)[1]-item[1].bed_n))
        local = np.array([bed.local(q) for q in corners])
        lower, upper = local.min(0), local.max(0)
        pc = bed.plan_cfg
        # 계획 상자와 팔 상자의 교집합에 실제 과실 외곽 및 여유를 넣는다.
        nlo, nhi = bed.bed_n-pc.depth/2, bed.bed_n+pc.depth/2
        zlo = pc.mount_z+max(pc.z_min, device['workspace_arm_min_m'][2])
        zhi = pc.mount_z+min(pc.z_max, device['workspace_arm_max_m'][2])
        half = (upper-lower)/2
        if nhi-nlo < 2*(half[1]+args.margin) or zhi-zlo < 2*(half[2]+args.margin):
            raise ValueError(f'과실 크기가 작업 상자를 초과: {path}, half={half.tolist()}')
        target = (lower+upper)/2
        target[1] = np.clip(target[1], nlo+half[1]+args.margin, nhi-half[1]-args.margin)
        target[2] = np.clip(target[2], zlo+half[2]+args.margin, zhi-half[2]-args.margin)
        local_delta = target-(lower+upper)/2
        map_delta = np.r_[local_delta[0]*bed.t+local_delta[1]*bed.n, local_delta[2]]
        delta = inverse[:3, :3]@map_delta
        # 경로상 한 정차점에서 전체 외곽과 HOME 거리 조건이 성립하는지도 검사한다.
        sign = 1 if np.cos(pc.base_yaw) >= 0 else -1
        base_s = target[0]-pc.mount_world_xy[0]+sign*.125
        if not pc.route_start <= base_s <= pc.route_end:
            raise ValueError(f'경로 내 정차 위치 없음: {path}')
        for point in local+local_delta:
            arm = np.array([sign*(point[1]-pc.route_y-pc.mount_world_xy[1]),
                            -sign*(point[0]-base_s-pc.mount_world_xy[0]), point[2]-pc.mount_z])
            distance = np.linalg.norm(arm-np.array(device['home_tcp_arm_m']))
            if ((arm < np.array(device['workspace_arm_min_m'])-1e-8)
                    | (arm > np.array(device['workspace_arm_max_m'])+1e-8)).any():
                raise ValueError(f'팔 상자 밖 외곽: {path}')
            if not device['near_home_min_m'] < distance < device['near_home_max_m']:
                raise ValueError(f'HOME 거리 밖 외곽: {path}')
        checked.append(path)
        if np.linalg.norm(delta) > 1e-9:
            changes.append(dict(path=path, section=sec, delta_world_m=delta.tolist(),
                                old_root_world_m=originals[path][:3, 3].tolist(),
                                new_root_world_m=(originals[path][:3, 3]+delta).tolist()))
    # 다른 과실과 새로 겹치는 재배치는 저장하지 않는다(기존 겹침은 별도 기록).
    def overlaps(bounds: dict) -> set:
        result = set()
        for a, b in itertools.combinations(bounds, 2):
            if np.all(np.minimum(bounds[a][1], bounds[b][1])-np.maximum(bounds[a][0], bounds[b][0]) > 1e-5):
                result.add((a, b))
        return result
    proposed = {k: v.copy() for k, v in boxes.items()}
    for change in changes:
        proposed[change['path']] += np.array(change['delta_world_m'])
    old_pairs, new_pairs = overlaps(boxes), overlaps(proposed)
    # 깊이/높이를 모으면서 생긴 겹침은 같은 관측면의 경로 방향 최소 이동으로 피한다.
    by_path = {change['path']: change for change in changes}
    for _ in range(len(records)):
        conflicts = overlaps(proposed)-old_pairs
        if not conflicts:
            break
        pair = sorted(conflicts)[0]
        moved = False
        for path in reversed(pair):
            if path not in by_path:
                continue
            change = by_path[path];bed = beds[change['section']]
            axis = inverse[:3, :3]@np.r_[bed.t, 0.]
            for step in range(1, 61):
                for direction in (-1, 1):
                    shift = axis*(direction*step*.005)
                    candidate = proposed[path]+shift
                    center_map = transform_points(T, [candidate.mean(0)])[0]
                    sign = 1 if np.cos(bed.plan_cfg.base_yaw) >= 0 else -1
                    stop = bed.local(center_map)[0]-bed.plan_cfg.mount_world_xy[0]+sign*.125
                    if not bed.plan_cfg.route_start <= stop <= bed.plan_cfg.route_end:
                        continue
                    blocked = any(tuple(sorted((path, other))) not in old_pairs
                                  and np.all(np.minimum(candidate[1], box[1])-np.maximum(candidate[0], box[0]) > 1e-5)
                                  for other, box in proposed.items() if other != path)
                    if not blocked:
                        proposed[path] = candidate
                        delta = np.array(change['delta_world_m'])+shift
                        change['delta_world_m'] = delta.tolist()
                        change['new_root_world_m'] = (originals[path][:3, 3]+delta).tolist()
                        change['overlap_avoidance_shift_m'] = direction*step*.005
                        moved = True
                        break
                if moved:
                    break
            if moved:
                break
        if not moved:
            raise ValueError(f'새 과실 겹침을 해소할 수 없음: {pair}')
    new_pairs = overlaps(proposed)
    if new_pairs-old_pairs:
        raise ValueError(f'새 과실 AABB 겹침 발생: {sorted(new_pairs-old_pairs)}')
    report = dict(scene=str(scene.relative_to(ROOT)), applied=args.apply, margin_m=args.margin,
                  total_fruits=len(records), checked_ripe=len(checked), moved_ripe=len(changes),
                  unchanged_green=sum(r['color']=='green' for r in records),
                  old_aabb_overlap_count=len(old_pairs), new_aabb_overlap_count=len(new_pairs),
                  scene_before_sha256=hashlib.sha256(scene.read_bytes()).hexdigest(), changes=changes,
                  validation='실제 runtime 과실 모델의 전체 AABB 외곽이 계획 상자 및 팔 box/HOME 범위 안인 정차 위치 존재. 센서 검출/IK/수확 성공 보장은 아님.')
    if args.apply:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        backup = args.report.parent/'farm_with_plants_v5.before_relocation.usd'
        if backup.exists():
            raise FileExistsError(backup)
        shutil.copy2(scene, backup)
        stage.SetEditTarget(stage.GetRootLayer())
        # 물리 session은 저장하지 않고 원본의 translate/연결 줄기 끝점만 수정한다.
        for change in changes:
            path = change['path'];prim = stage.GetPrimAtPath(path);delta = np.array(change['delta_world_m'])
            parent = np.asarray(transforms.GetLocalToWorldTransform(prim.GetParent())).T
            local_delta = np.linalg.inv(parent[:3, :3])@delta
            attr = prim.GetAttribute('xformOp:translate')
            attr.Set(Gf.Vec3d(*(np.array(attr.Get())+local_delta)))
            number = re.search(r'Pepper_(\d+)_', path)[1]
            stem = stage.GetPrimAtPath(path.split('/Fruits/')[0]+'/Connectors/Stem_'+number)
            if not stem or not stem.IsA(UsdGeom.Mesh):
                raise ValueError(f'연결 줄기 없음: {path}')
            points = np.array(UsdGeom.Mesh(stem).GetPointsAttr().Get())
            if points.shape != (16, 3):
                raise ValueError(f'연결 줄기 구조 변경됨: {stem.GetPath()}')
            matrix = np.asarray(transforms.GetLocalToWorldTransform(stem)).T
            stem_delta = np.linalg.inv(matrix[:3, :3])@delta
            # 식물 쪽 첫 링은 유지하고 과실 쪽 링만 과실 이동량만큼 옮긴다.
            points[8:] += stem_delta
            UsdGeom.Mesh(stem).GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(points.astype(np.float32)))
        stage.GetRootLayer().Save()
        report['scene_after_sha256'] = hashlib.sha256(scene.read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='changes'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
