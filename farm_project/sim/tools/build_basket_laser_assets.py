"""운영 URDF와 두 USD base layer에 같은 평행 3빔 장착부를 저장한다.

Isaac Python/pxr 환경에서 실행한다. 기존 링크·물성·모델 기준 URDF는 수정하지 않는다.
센서 외형은 임시 12×6×12mm이며 질량/관성은 기존 차체 값을 유지한다.
"""
from pathlib import Path
import json
import re
import sys
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.basket_laser import beam_segments

URDF = ROOT/'sim/assets/robots/harvest_robot/urdf/harvest_robot.urdf'
BASES = [ROOT/f'sim/assets/robots/{p}/configuration/harvest_robot_base.usd'
         for p in ('harvest_robot/urdf/harvest_robot', 'harvest_count_test')]
BEGIN, END = '  <!-- BASKET_LASERS_BEGIN -->', '  <!-- BASKET_LASERS_END -->'


def link_pose(root: ET.Element, link: str, ancestor: str = 'base_link') -> np.ndarray:
    """URDF 원점의 고정 연결을 ancestor 좌표로 합성한다(m)."""
    if link == ancestor:
        return np.eye(4)
    joint = next(j for j in root.findall('joint') if j.find('child').get('link') == link)
    if joint.get('type') != 'fixed':
        raise ValueError('센서 장착 경로에 움직이는 관절이 있습니다: '+link)
    origin = joint.find('origin')
    pose = np.eye(4)
    pose[:3, 3] = np.fromstring(origin.get('xyz', '0 0 0'), sep=' ')
    pose[:3, :3] = Rotation.from_euler('xyz', np.fromstring(origin.get('rpy', '0 0 0'), sep=' ')).as_matrix()
    return link_pose(root, joint.find('parent').get('link'), ancestor) @ pose


def layout(root: ET.Element, settings: dict) -> tuple:
    """벽의 내면으로부터 입구 경계와 광축·헤드 중심을 계산한다."""
    walls = {}
    for name in ('front', 'rear', 'left', 'right'):
        link = root.find(f"link[@name='box_{name}_wall']")
        center = link_pose(root, link.get('name'), 'harvest_box')[:3, 3]
        size = np.fromstring(link.find('visual/geometry/box').get('size'), sep=' ')
        walls[name] = (center-size/2, center+size/2)
    lo = np.array([walls['rear'][1][0], walls['right'][1][1], walls['front'][0][2]])
    hi = np.array([walls['front'][0][0], walls['left'][0][1], walls['front'][1][2]])
    starts, ends = beam_segments(lo, hi, settings)
    size = np.asarray(settings['head_size_m'], float)
    if size.shape != (3,) or not np.isfinite(size).all() or np.any(size <= 0) or size[1] >= settings['end_inset_m']:
        raise ValueError('광축 시작점은 센서 헤드 앞면 바깥에 있어야 합니다.')
    heads = []
    for i, (start, end) in enumerate(zip(starts, ends), 1):
        for side, endpoint, y in (('emitter', start, lo[1]+size[1]/2), ('receiver', end, hi[1]-size[1]/2)):
            center = endpoint.copy(); center[1] = y
            heads.append((f'basket_laser_{i}_{side}', center, endpoint-center))
    return starts, ends, heads, size


def urdf_block(heads: list, size: np.ndarray) -> str:
    """장착 링크와 광축 원점만 생성한다. 광선 자체에는 충돌체를 두지 않는다."""
    fmt = lambda values: ' '.join(f'{float(v):.12g}' for v in values)
    lines = [BEGIN, '  <!-- 입구 아래 5mm, 평행 3빔. optical +Y가 송신→수신 방향(m). -->']
    for name, center, optical in heads:
        lines += [f'  <link name="{name}">',
            f'    <visual><geometry><box size="{fmt(size)}"/></geometry>',
            '      <material name="basket_laser_housing"><color rgba="0.12 0.16 0.20 1"/></material></visual>',
            f'    <collision><geometry><box size="{fmt(size)}"/></geometry></collision>', '  </link>',
            f'  <joint name="{name}_joint" type="fixed"><parent link="harvest_box"/><child link="{name}"/>',
            f'    <origin xyz="{fmt(center)}" rpy="0 0 0"/></joint>',
            f'  <link name="{name}_optical"/>',
            f'  <joint name="{name}_optical_joint" type="fixed"><parent link="{name}"/><child link="{name}_optical"/>',
            f'    <origin xyz="{fmt(optical)}" rpy="0 0 0"/></joint>']
    return '\n'.join(lines+[END])+'\n'


def author_usd(stage: object, path: str, pose: np.ndarray, geometry: tuple) -> None:
    """기존 base_link에 고정 헤드와 광축 표시를 추가한다. 개별 rigid body는 없다."""
    from pxr import Gf, UsdGeom, UsdPhysics
    stage.RemovePrim(path)
    root = UsdGeom.Xform.Define(stage, path)
    root.AddTransformOp().Set(Gf.Matrix4d(pose.T.tolist()))
    starts, ends, heads, size = geometry
    for name, center, optical in heads:
        head = UsdGeom.Xform.Define(stage, path+'/'+name)
        head.AddTranslateOp().Set(Gf.Vec3d(*center))
        cube = UsdGeom.Cube.Define(stage, path+'/'+name+'/housing')
        cube.CreateSizeAttr(1.)
        cube.AddScaleOp().Set(Gf.Vec3f(*size))
        cube.CreateDisplayColorAttr([(.12, .16, .20)])
        UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
        frame = UsdGeom.Xform.Define(stage, path+'/'+name+'/optical')
        frame.AddTranslateOp().Set(Gf.Vec3d(*optical))
    for i, (start, end) in enumerate(zip(starts, ends), 1):
        beam = UsdGeom.BasisCurves.Define(stage, f'{path}/beam_{i}')
        beam.CreateTypeAttr('linear')
        beam.CreateCurveVertexCountsAttr([2])
        beam.CreatePointsAttr([Gf.Vec3f(*start), Gf.Vec3f(*end)])
        beam.CreateWidthsAttr([.0015]); beam.SetWidthsInterpolation('constant')
        beam.CreateDisplayColorAttr([(0., 1., .2)])


def main() -> None:
    from pxr import Usd
    settings = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/student_policy.json').read_text())['basket_lasers']
    text = URDF.read_text()
    root = ET.fromstring(text)
    geometry = layout(root, settings)
    pose = link_pose(root, 'harvest_box')
    text = re.sub(re.escape(BEGIN)+'.*?'+re.escape(END)+'\n', '', text, flags=re.S)
    URDF.write_text(text.replace('</robot>', urdf_block(geometry[2], geometry[3])+'</robot>'))
    for asset in BASES:
        stage = Usd.Stage.Open(str(asset))
        path = str(stage.GetDefaultPrim().GetPath())+'/base_link/BasketLasers'
        author_usd(stage, path, pose, geometry)
        stage.GetRootLayer().Save()
        print(asset.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    main()
