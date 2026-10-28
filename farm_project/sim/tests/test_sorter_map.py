"""선별장 지도 변경 범위와 오래된 지도 사용 방지 회귀 검사."""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('sorter_map', ROOT/'sim/tools/build_sorter_map.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def settings():
    return json.loads(module.CONFIG.read_text())


def test_map_metadata_and_outside_sorter_preserved():
    cfg = settings()['occupancy_map']
    old_meta = yaml.safe_load((ROOT/cfg['base_yaml']).read_text())
    new_meta = yaml.safe_load((ROOT/cfg['yaml']).read_text())
    assert {k:v for k,v in old_meta.items() if k!='image'} == {k:v for k,v in new_meta.items() if k!='image'}
    old = np.array(Image.open((ROOT/cfg['base_yaml']).parent/old_meta['image']).convert('L'))
    new = np.array(Image.open((ROOT/cfg['yaml']).parent/new_meta['image']).convert('L'))
    assert old.shape == new.shape
    h,w = old.shape
    x = old_meta['origin'][0]+(np.arange(w)+.5)*old_meta['resolution']
    y = old_meta['origin'][1]+(h-np.arange(h)-.5)*old_meta['resolution']
    # 베드/동서남 벽/선별장 접근 통로는 byte 단위 보존. 북쪽 벽도 지우지 않는다.
    outside = (x[None,:] < -7.7)|(x[None,:] > -6.4)|(y[:,None] < 13.5)
    assert np.array_equal(old[outside], new[outside])
    north = y > 14.9
    assert np.all(new[north][old[north]==0] == 0)


def test_changed_geometry_rejects_stale_map():
    cfg = settings()
    assert module.validate(cfg) == cfg['occupancy_map']['yaml']
    altered = copy.deepcopy(cfg)
    altered['station_pose_world_m'][1] += .01
    with pytest.raises(ValueError, match='재실행'):
        module.validate(altered)


def test_thin_wall_crossing_cell_is_occupied():
    # 셀 중심은 벽 밖이어도 실제 ray가 맞는 5mm 벽은 누락하면 안 된다.
    wall = [[.001,-1],[.006,-1],[.006,1],[.001,1]]
    assert module.cell_overlaps(wall,0.,0.,.05)
    assert not module.cell_overlaps(wall,.05,0.,.05)


def test_front_support_slice_matches_previous_actual_hits():
    cfg = settings()['occupancy_map']
    record = json.loads((ROOT/cfg['manifest']).read_text())
    support = next(x for x in record['polygons'] if 'IntakeSupport686' in x['prim'])
    ys = [p[1] for p in support['polygon_xy_m']]
    assert min(ys) < 13.60 < max(ys)
    assert not any('HCRRobot' in p['prim'] for p in record['polygons'])
