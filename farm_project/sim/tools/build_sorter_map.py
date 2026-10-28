"""원본 HCR 고정 충돌체의 수평 단면으로 시뮬 선별장 점유지도를 갱신한다.

Isaac Python으로 실행한다. 기존 지도에서 지정한 이전 선별장 영역만 지우며
나머지 지도/해상도/원점을 보존한다. 팔·과실·로봇의 동적 위치는 사용하지 않는다.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'sim/ros_ws/src/farm_sim_config/config/sorter_integration.json'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(settings: dict) -> dict:
    """배치/원본 형상/기존 지도 변경 때 재생성이 필요하도록 입력을 고정한다."""
    cfg = settings['occupancy_map']
    workspace = ROOT/settings['source_workspace']
    paths = [ROOT/cfg['base_yaml'], ROOT/cfg['base_yaml'].replace('.yaml', '.png'),
             workspace/settings['source_config'],
             workspace/'src/smartfarm_description/scripts/hcr3a_environment.py']
    return dict(station_pose_world_m=settings['station_pose_world_m'],
                station_yaw_rad=settings['station_yaw_rad'], occupancy_map=cfg,
                source_hashes={str(p.relative_to(ROOT)): digest(p) for p in paths})


def validate(settings: dict) -> str:
    """실행 배치와 지도 생성 입력이 다르면 오래된 지도를 사용하지 않는다."""
    cfg = settings['occupancy_map']
    record = json.loads((ROOT/cfg['manifest']).read_text())
    if inputs(settings) != record['inputs']:
        raise ValueError('HCR 배치/형상/지도 변경: build_sorter_map.py 재실행 필요')
    for path, sha in record['output_hashes'].items():
        if digest(ROOT/path) != sha:
            raise ValueError('생성 지도 해시 불일치: '+path)
    return cfg['yaml']


def cube_slice(prim: object, height: float) -> list:
    """USD cube의 실제 world 변환과 수평면의 교차 다각형(m)을 계산한다."""
    import numpy as np
    from scipy.spatial import ConvexHull
    from pxr import Gf, Usd, UsdGeom
    size = float(UsdGeom.Cube(prim).GetSizeAttr().Get())/2
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    signs = list(itertools.product((-1, 1), repeat=3))
    corners = [np.array(matrix.Transform(Gf.Vec3d(*(size*v for v in s)))) for s in signs]
    points = []
    for i, a in enumerate(corners):
        for j, b in enumerate(corners[i+1:], i+1):
            if sum(x != y for x, y in zip(signs[i], signs[j])) != 1:
                continue
            if min(a[2], b[2])-1e-9 <= height <= max(a[2], b[2])+1e-9:
                if abs(b[2]-a[2]) < 1e-9:
                    points.extend([a[:2], b[:2]])
                else:
                    points.append((a+(b-a)*(height-a[2])/(b[2]-a[2]))[:2])
    points = np.unique(np.round(points, 10), axis=0)
    if len(points) < 3:
        return []
    return points[ConvexHull(points).vertices].tolist()


def cell_overlaps(polygon: list, x: float, y: float, resolution: float) -> bool:
    """볼록 단면과 지도 셀의 교차: 얇은 벽도 셀 중심 밖이라는 이유로 누락하지 않는다."""
    axes = [(1., 0.), (0., 1.)]
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        axes.append((a[1]-b[1], b[0]-a[0]))
    square = [(x,y), (x+resolution,y), (x+resolution,y+resolution), (x,y+resolution)]
    for dx, dy in axes:
        a = [px*dx+py*dy for px, py in polygon]
        b = [px*dx+py*dy for px, py in square]
        if max(a) < min(b)-1e-10 or max(b) < min(a)-1e-10:
            return False
    return True


def rasterize(settings: dict, polygons: list) -> dict:
    import numpy as np
    import yaml
    from PIL import Image
    cfg = settings['occupancy_map']
    base = ROOT/cfg['base_yaml']
    metadata = yaml.safe_load(base.read_text())
    if metadata['origin'][2] != 0 or metadata['negate'] != 0:
        raise ValueError('회전 없는 negate0 지도 필요')
    old = np.array(Image.open(base.parent/metadata['image']).convert('L'))
    new = old.copy()
    h, w = old.shape
    res = metadata['resolution']; ox, oy = metadata['origin'][:2]
    xmin, ymin, xmax, ymax = cfg['replace_bounds_xy_m']
    cols = ox+(np.arange(w)+.5)*res
    rows = oy+(h-np.arange(h)-.5)*res
    clear = ((rows[:, None] >= ymin) & (rows[:, None] <= ymax)
             & (cols[None, :] >= xmin) & (cols[None, :] <= xmax))
    # 이전 모델 내부의 unknown127도 함께 제거한다. ROI 밖의 unknown은 보존한다.
    new[clear] = 255
    added = np.zeros(old.shape, dtype=bool)
    for item in polygons:
        polygon = item['polygon_xy_m']
        px, py = zip(*polygon)
        for col in range(max(0, math.floor((min(px)-ox)/res)), min(w, math.floor((max(px)-ox)/res)+1)):
            for row_y in range(max(0, math.floor((min(py)-oy)/res)), min(h, math.floor((max(py)-oy)/res)+1)):
                if cell_overlaps(polygon, ox+col*res, oy+row_y*res, res):
                    added[h-1-row_y, col] = True
    new[added] = 0
    if not np.array_equal(new[~(clear | added)], old[~(clear | added)]):
        raise AssertionError('선별장 이외 지도 변경')
    target = ROOT/cfg['yaml']; image = target.with_suffix('.png')
    Image.fromarray(new).save(image)
    metadata['image'] = image.name
    target.write_text(yaml.safe_dump(metadata, sort_keys=False))
    changed = np.argwhere(old != new)
    return dict(inputs=inputs(settings), polygons=polygons, scan_height_m=cfg['scan_height_m'],
        method='USD static collision cube / horizontal slice / cell intersection; original map outside sorter preserved',
        image_size=[w,h], changed_cells=len(changed), removed_cells=int(((old==0)&(new==255)).sum()),
        added_cells=int(((old==255)&(new==0)).sum()),
        changed_cell_centers_bounds=[float(cols[changed[:,1]].min()),float(rows[changed[:,0]].min()),
                                    float(cols[changed[:,1]].max()),float(rows[changed[:,0]].max())],
        output_hashes={str(p.relative_to(ROOT)):digest(p) for p in (target,image)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=CONFIG)
    args = parser.parse_args()
    settings = json.loads(args.config.read_text())
    from isaacsim import SimulationApp
    sys.argv = [sys.argv[0]]
    app = SimulationApp(dict(headless=True, disable_viewport_updates=True))
    try:
        import omni.usd
        from pxr import Gf, UsdGeom, UsdPhysics
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()
        UsdGeom.SetStageMetersPerUnit(stage, 1.); UsdGeom.SetStageUpAxis(stage, 'Z')
        workspace = ROOT/settings['source_workspace']
        sys.path.insert(0, str(workspace/'src/sorting_station'))
        from hcr_sim.scene import create_station
        create_station(json.loads((workspace/settings['source_config']).read_text()))
        station = UsdGeom.Xformable(stage.GetPrimAtPath('/World/HCRStation'))
        station.AddTranslateOp().Set(Gf.Vec3d(*settings['station_pose_world_m']))
        station.AddRotateZOp().Set(math.degrees(settings['station_yaw_rad']))
        polygons = []
        for prim in stage.Traverse():
            if not str(prim.GetPath()).startswith('/World/HCRStation/') or not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            if not prim.IsA(UsdGeom.Cube):
                raise ValueError('지원하지 않는 고정 충돌 형상: '+str(prim.GetPath()))
            polygon = cube_slice(prim, settings['occupancy_map']['scan_height_m'])
            if polygon:
                polygons.append(dict(prim=str(prim.GetPath()), polygon_xy_m=polygon))
        if not polygons:
            raise ValueError('라이다 단면이 비어 있음')
        record = rasterize(settings, polygons)
        (ROOT/settings['occupancy_map']['manifest']).write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({k:v for k,v in record.items() if k not in ('polygons','inputs')}, ensure_ascii=False), flush=True)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        raise
    finally:
        app.close()


if __name__ == '__main__':
    main()
