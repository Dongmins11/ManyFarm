"""농장 과실의 ID·위치를 유지하면서 Teacher 9g 물리를 세션에 적용한다.

시뮬 초기화 전에 호출한다. 인장 방향은 해당 베드의 중심선에서 통로 쪽으로
정하고, 동적 꼭지 외력/분리 시간 적분은 별도 실행기가 담당한다.
"""
import math
from pathlib import Path
import random

import numpy as np


def _finite_vector(value: object, size: int, name: str) -> np.ndarray:
    """SI 좌표 벡터의 차원과 유한성을 검사한다."""
    vector = np.asarray(value, dtype=float)
    if vector.shape != (size,) or not np.isfinite(vector).all():
        raise ValueError(f'{name}: 유한한 {size}차원 좌표가 필요합니다.')
    return vector


def _bed_axes(survey: dict) -> tuple[dict, np.ndarray]:
    """Section의 베드 중심·경로 접선을 묶고 독립 map/world TF를 검증한다."""
    transform = np.asarray(survey['evaluation']['T_map_world'], dtype=float)
    if (transform.shape != (4, 4) or not np.isfinite(transform).all()
            or not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-9)
            or not np.allclose(transform[:3, :3].T @ transform[:3, :3], np.eye(3), atol=1e-6)
            or not math.isclose(np.linalg.det(transform[:3, :3]), 1., abs_tol=1e-6)):
        raise ValueError('survey.evaluation.T_map_world는 강체 변환이어야 합니다.')
    beds = {}
    for name, section in survey['sections'].items():
        path = section['evaluation_bed_prim']
        center = _finite_vector(section['physical_bed_center_map_m'], 2, name + '.center')
        geometry = section['survey_geometry']
        start = _finite_vector(geometry['start_xy_m'], 2, name + '.start')
        end = _finite_vector(geometry['end_xy_m'], 2, name + '.end')
        tangent = end - start
        if np.linalg.norm(tangent) < 1e-8:
            raise ValueError(f'{name}: 길이가 없는 경로입니다.')
        tangent /= np.linalg.norm(tangent)
        if path in beds:
            old_center, old_tangent = beds[path]
            if (not np.allclose(center, old_center, atol=1e-6)
                    or not math.isclose(abs(np.dot(tangent, old_tangent)), 1., abs_tol=1e-6)):
                raise ValueError(f'{path}: 양쪽 Section의 중심선 설정이 다릅니다.')
        else:
            beds[path] = (center, tangent)
    return beds, transform


def outward_tension_axis_world(position_world: object, bed_path: str, survey: dict) -> np.ndarray:
    """베드 중심선에 수직이고 현재 과실 쪽 통로를 향하는 world 단위벡터다."""
    beds, transform = _bed_axes(survey)
    if bed_path not in beds:
        raise ValueError(f'과실 베드가 survey에 없습니다: {bed_path}')
    point = _finite_vector(position_world, 3, 'position_world')
    return _outward_axis(point, beds[bed_path], transform)


def _outward_axis(point: np.ndarray, bed: tuple, transform: np.ndarray) -> np.ndarray:
    """미리 검증한 베드 설정을 여러 과실에 재사용한다."""
    center, tangent = bed
    point_map = transform[:3, :3] @ point + transform[:3, 3]
    offset = point_map[:2] - center
    perpendicular = offset - np.dot(offset, tangent) * tangent
    distance = np.linalg.norm(perpendicular)
    if distance < 1e-8:
        raise ValueError('베드 중심선 위의 과실은 통로 방향을 결정할 수 없습니다.')
    axis_map = np.r_[perpendicular / distance, 0.]
    return transform[:3, :3].T @ axis_map


def _unscaled_transform(world: np.ndarray) -> np.ndarray:
    """world translation과 회전을 유지하고 축별 스케일만 제거한다."""
    if not np.isfinite(world).all() or np.linalg.det(world[:3, :3]) <= 1e-10:
        raise ValueError('과실 transform의 0 스케일/반사/비정상 값을 지원하지 않습니다.')
    rotation, scale = np.linalg.qr(world[:3, :3])
    # 현재 농장의 R*positive-scale 행렬에서 원래 회전을 정확히 복원한다.
    signs = np.sign(np.diag(scale))
    rotation = rotation @ np.diag(signs)
    if not np.allclose(rotation.T @ world[:3, :3], np.diag(np.abs(np.diag(scale))), atol=1e-6):
        raise ValueError('과실 world transform에 shear가 있어 크기를 보존해 정규화할 수 없습니다.')
    result = np.eye(4)
    result[:3, :3], result[:3, 3] = rotation, world[:3, 3]
    return result


def configure_farm_fruits(stage: object, project_root: Path, config: dict, survey: dict) -> list[dict]:
    """3색 템플릿을 기존 과실 root에 참조하고 줄기 연결용 명세를 반환한다.

    config는 전체 프로파일의 fruit 섹션이다. asset_paths는 project_root
    상대 경로이며, 반환 항목은 prim_path/attachment_local_m/
    tension_axis_world/break_force_N를 포함한다. 원본 stage는 저장하지 않는다.
    """
    from pxr import PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade
    from farm_sim_devices.fruit_pose import set_rigid_local_pose

    if UsdGeom.GetStageUpAxis(stage) != 'Z' or not math.isclose(
            UsdGeom.GetStageMetersPerUnit(stage), 1., abs_tol=1e-9):
        raise ValueError('과실 물성은 metre/Z-up stage에서만 적용합니다.')
    project_root = Path(project_root).resolve()
    beds, map_world = _bed_axes(survey)
    numeric = {}
    for key in ('mass_kg', 'static_friction', 'dynamic_friction', 'restitution',
                'contact_offset_m', 'rest_offset_m', 'linear_damping', 'angular_damping',
                'max_linear_velocity_m_s', 'max_angular_velocity_deg_s'):
        value = float(config[key])
        if not math.isfinite(value) or (key != 'rest_offset_m' and value < 0):
            raise ValueError(f'fruit.{key}: 유효한 SI 값이 필요합니다.')
        numeric[key] = value
    if (numeric['mass_kg'] <= 0 or numeric['contact_offset_m'] <= numeric['rest_offset_m']
            or numeric['contact_offset_m'] <= 0 or numeric['restitution'] > 1):
        raise ValueError('과실 질량·접촉 여유·반발계수를 확인하세요.')
    force_range = _finite_vector(config['break_force_range_N'], 2, 'break_force_range_N')
    if force_range[0] <= 0 or force_range[1] < force_range[0]:
        raise ValueError('과실 분리 힘 범위는 양수이며 오름차순이어야 합니다.')
    assets, attachments = {}, {}
    for color in ('red', 'yellow', 'green'):
        path = (project_root / config['asset_paths'][color]).resolve()
        if not path.is_relative_to(project_root) or not path.is_file():
            raise ValueError(f'프로젝트 내부 과실 자산이 없습니다: {path}')
        template = Usd.Stage.Open(str(path))
        root = template.GetPrimAtPath('/Pepper')
        collider = template.GetPrimAtPath('/Pepper/Collision')
        if not root.IsValid() or not root.HasAPI(UsdPhysics.RigidBodyAPI) or not collider.HasAPI(UsdPhysics.CollisionAPI):
            raise ValueError(f'과실 템플릿 물리 구조가 다릅니다: {path}')
        attachment_config = config.get('attachment_local_m_by_color', config['attachment_local_m'])
        attachment_value = attachment_config[color] if isinstance(attachment_config, dict) else attachment_config
        attachment = _finite_vector(attachment_value, 3, 'attachment_local_m')
        authored = root.GetAttribute('teacher:attachmentLocalM').Get()
        # 3색 원본 꼭지점의 수 nm 차이는 공통 fallback에서도 허용한다.
        if authored is None or not np.allclose(attachment, authored, atol=1e-8, rtol=0):
            raise ValueError(f'{color}: 프로파일 꼭지점과 템플릿 꼭지점이 다릅니다.')
        assets[color], attachments[color] = path, attachment
    fruits = sorted((prim for prim in stage.Traverse()
                     if prim.GetAttribute('crop:color').Get()), key=lambda prim: str(prim.GetPath()))
    if not fruits:
        raise ValueError('crop:color 과실이 없는 stage입니다.')
    transforms = UsdGeom.XformCache()
    rng = random.Random(int(config['seed']))
    prepared = []
    for prim in fruits:
        color = str(prim.GetAttribute('crop:color').Get()).lower()
        if color not in assets:
            raise ValueError(f'지원하지 않는 과실 색상: {prim.GetPath()}, {color}')
        matches = [path for path in beds if prim.GetPath().HasPrefix(Sdf.Path(path))]
        if not matches:
            raise ValueError(f'survey 베드에 속하지 않는 과실: {prim.GetPath()}')
        bed_path = max(matches, key=len)
        original = np.asarray(transforms.GetLocalToWorldTransform(prim)).T
        world = _unscaled_transform(original)
        parent = np.asarray(transforms.GetLocalToWorldTransform(prim.GetParent())).T
        local = np.linalg.inv(parent) @ world
        model = prim.GetChild('Model')
        if not model.IsValid():
            raise ValueError(f'기존 과실 Model이 없습니다: {prim.GetPath()}')
        record = dict(prim_path=str(prim.GetPath()), color=color, bed_prim=bed_path,
                      attachment_local_m=attachments[color].tolist(),
                      tension_axis_world=_outward_axis(world[:3, 3], beds[bed_path], map_world).tolist(),
                      break_force_N=rng.uniform(*force_range), initial_position_world_m=world[:3, 3].tolist())
        prepared.append((prim, model, local, record))
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for prim, model, local, record in prepared:
            prim.GetReferences().AddReference(str(assets[record['color']]), '/Pepper')
            model.SetActive(False)
            set_rigid_local_pose(prim, local)
            UsdPhysics.RigidBodyAPI.Apply(prim).CreateRigidBodyEnabledAttr(True)
            UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(numeric['mass_kg'])
            body = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
            body.CreateEnableCCDAttr(True)
            body.CreateDisableGravityAttr(False)
            body.CreateLinearDampingAttr(numeric['linear_damping'])
            body.CreateAngularDampingAttr(numeric['angular_damping'])
            body.CreateMaxLinearVelocityAttr(numeric['max_linear_velocity_m_s'])
            # IsaacLab RigidBodyPropertiesCfg도 이 항목은 deg/s를 그대로 USD에 쓴다.
            # 전달 env.py의 20.0은 20 rad/s가 아니라 20 deg/s이다.
            body.CreateMaxAngularVelocityAttr(numeric['max_angular_velocity_deg_s'])
            collider = stage.GetPrimAtPath(prim.GetPath().AppendChild('Collision'))
            collision = PhysxSchema.PhysxCollisionAPI.Apply(collider)
            collision.CreateContactOffsetAttr(numeric['contact_offset_m'])
            collision.CreateRestOffsetAttr(numeric['rest_offset_m'])
            material = UsdShade.Material(stage.GetPrimAtPath(prim.GetPath().AppendChild('PhysicsMaterial')))
            physics = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
            physics.CreateStaticFrictionAttr(numeric['static_friction'])
            physics.CreateDynamicFrictionAttr(numeric['dynamic_friction'])
            physics.CreateRestitutionAttr(numeric['restitution'])
            binding = UsdShade.MaterialBindingAPI.Apply(collider)
            binding.Bind(material, materialPurpose='physics', bindingStrength=UsdShade.Tokens.strongerThanDescendants)
            resolved, _ = binding.ComputeBoundMaterial('physics')
            if resolved.GetPath() != material.GetPath():
                raise RuntimeError(f'과실 접촉 재질 바인딩 실패: {prim.GetPath()}')
    return [record for _, _, _, record in prepared]
