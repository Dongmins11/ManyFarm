"""실측 전 임시 ArUco를 모델에 부착한다. 위치는 렌더에만 사용한다."""
import json
from pathlib import Path

import numpy as np


def install_docking_markers(stage: object, root: Path, selected: str | None) -> list:
    """배치표의 자산축 좌표를 강체 부모의 로컬 좌표로 바꿔 장착한다."""
    if not selected:
        return []
    from pxr import Gf, Sdf, UsdGeom, UsdShade
    data = json.loads((root / selected).read_text())
    if data['dictionary'] != 'DICT_4X4_50':
        raise ValueError('지원하지 않는 도킹 마커 사전')
    cache = UsdGeom.XformCache()
    records = []
    for item in data['markers']:
        parent = stage.GetPrimAtPath(item['parent_prim'])
        reference = stage.GetPrimAtPath(item['reference_prim'])
        if not parent.IsValid() or not reference.IsValid():
            raise ValueError(f"도킹 마커 장착 모델 없음: {item['id']}")
        right, up = np.asarray(item['right'], float), np.asarray(item['up'], float)
        rotation = np.column_stack((right, up, np.cross(right, up)))
        if not np.allclose(rotation.T @ rotation, np.eye(3)):
            raise ValueError('마커 right/up은 직교 단위 벡터여야 합니다.')
        transform = np.eye(4)
        transform[:3, :3] = rotation
        transform[:3, 3] = item['center_m']
        parent_world = np.asarray(cache.GetLocalToWorldTransform(parent)).T
        reference_world = np.asarray(cache.GetLocalToWorldTransform(reference)).T
        local = np.linalg.inv(parent_world) @ reference_world @ transform
        path = str(parent.GetPath()) + f"/SimDockingMarker_{item['id']}"
        marker = UsdGeom.Xform.Define(stage, path)
        marker.ClearXformOpOrder()
        marker.AddTransformOp().Set(Gf.Matrix4d(*map(float, local.T.flat)))
        marker.GetPrim().CreateAttribute('sim:mountStatus', Sdf.ValueTypeNames.String).Set(item['status'])
        # 6×6 셀을 직접 그려 축소 텍스처 필터에 의한 모서리 이동을 피한다.
        cells = np.asarray(item['pattern_cells'])
        edge, paper = float(item['black_edge_m']), float(item['paper_edge_m'])
        if cells.shape != (6, 6) or not np.isin(cells, [0, 1]).all() or not 0 < edge < paper:
            raise ValueError('마커 셀/물리 크기 오류')
        points, colors = [], []
        def quad(x0: float, y0: float, x1: float, y1: float, z: float, value: float) -> None:
            points.extend([(x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)])
            colors.append(Gf.Vec3f(value, value, value))
        quad(-paper/2, -paper/2, paper/2, paper/2, 0., 1.)
        for row in range(6):
            for col in range(6):
                quad((col/6-.5)*edge, (.5-(row+1)/6)*edge,
                     ((col+1)/6-.5)*edge, (.5-row/6)*edge, .00001, float(cells[row,col]))
        mesh = UsdGeom.Mesh.Define(stage, path+'/Pattern')
        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr([4]*len(colors))
        mesh.CreateFaceVertexIndicesAttr(list(range(len(points))))
        mesh.CreateSubdivisionSchemeAttr('none')
        mesh.CreateDoubleSidedAttr(False)
        mesh.CreateDisplayColorAttr(colors)
        mesh.GetDisplayColorPrimvar().SetInterpolation('uniform')
        material = UsdShade.Material.Define(stage, path+'/Material')
        shader = UsdShade.Shader.Define(stage, path+'/Material/Surface')
        shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(1.)
        reader = UsdShade.Shader.Define(stage, path+'/Material/Color')
        reader.CreateIdAttr('UsdPrimvarReader_float3')
        reader.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('displayColor')
        shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).ConnectToSource(reader.ConnectableAPI(), 'result')
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
        records.append(dict(id=item['id'], path=path, status=item['status']))
    return records
