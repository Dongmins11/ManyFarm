"""받은 오른팔 물성과 박스 바닥을 세션 레이어에만 적용한다.

주행 USD의 바퀴·캐스터·왼팔을 보존한다. 학습 정렬 시 오른팔의 고정 카메라
몸체를 집게에 합치고 articulation solver/자기충돌을 맞춘다. 호출은 물리
초기화 전에 한 번 수행하며, 관절 상태 자체의 HOME 배치는 실행기가 담당한다.
"""
import math
from pathlib import Path


def _positive(value: object, name: str, *, allow_zero: bool = False) -> float:
    """SI 설정 숫자의 유효 범위를 검사한다."""
    number = float(value)
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f'{name}: 유한한 양수 설정이 필요합니다.')
    return number


def _named_prim(stage: object, robot: object, name: str) -> object:
    """로봇 하위에서 정확히 한 개의 프림을 이름으로 찾는다."""
    from pxr import Usd
    matches = [prim for prim in Usd.PrimRange(robot) if prim.GetName() == name]
    if len(matches) != 1:
        raise ValueError(f'{robot.GetPath()}: {name} 프림이 {len(matches)}개입니다.')
    return matches[0]


def _colliders(body: object) -> list:
    """인스턴스 프록시를 포함하여 body 하위 충돌체를 조회한다."""
    from pxr import Usd, UsdPhysics
    return [prim for prim in Usd.PrimRange(body, Usd.TraverseInstanceProxies())
            if prim.HasAPI(UsdPhysics.CollisionAPI)]


def _make_editable(body: object) -> list:
    """지정 body의 충돌 인스턴스만 풀어 세션 override를 가능하게 한다."""
    from pxr import Usd
    while True:
        instances = [prim for prim in Usd.PrimRange(body) if prim.IsInstance()]
        if not instances:
            return _colliders(body)
        for prim in instances:
            prim.SetInstanceable(False)


def configure_harvest_arm(stage: object, robot_path: str, config: dict) -> dict:
    """학습 팔 물리·drive·집게 접촉·박스 바닥을 적용하고 적용값을 반환한다.

    config의 arm/gripper 값은 N·m/rad, N·m·s/rad, N·m, rad/s다.
    USD angular drive는 degree 기반이므로 gains는 π/180을 곱하고 속도와
    HOME target은 180/π를 곱한다. effort 한도는 N·m 그대로 설정한다.
    box_floor.asset_path는 실행기가 해석한 절대 경로여야 한다.
    """
    from pxr import PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

    robot = stage.GetPrimAtPath(robot_path)
    if not robot.IsValid():
        raise ValueError(f'수확 로봇 프림이 없습니다: {robot_path}')
    if UsdGeom.GetStageUpAxis(stage) != 'Z' or not math.isclose(
            UsdGeom.GetStageMetersPerUnit(stage), 1.0, abs_tol=1e-9):
        raise ValueError('오른팔 물성은 metre/Z-up stage에서만 적용합니다.')
    alignment = None
    if config.get('teacher_alignment', {}).get('enabled', False):
        from .teacher_arm_alignment import align_teacher_arm
        alignment = align_teacher_arm(stage, robot, config['teacher_alignment'])
    arm, gripper, contact = config['arm'], config['gripper'], config['contact']
    names = list(arm['joint_names']) + [gripper['joint_name']]
    if len(names) != 6 or len(set(names)) != 6 or any(not n.startswith('arm_2_') for n in names):
        raise ValueError('서로 다른 오른팔 5관절과 그리퍼 1관절을 지정해야 합니다.')
    joints = [_named_prim(stage, robot, name) for name in names]
    settings = [arm] * 5 + [gripper]
    home_arm = arm.get('home_positions_rad')
    home_grip = gripper.get('home_position_rad')
    if (home_arm is None) != (home_grip is None):
        raise ValueError('HOME 설정은 오른팔 5개와 그리퍼를 함께 지정해야 합니다.')
    homes = [None] * 6 if home_arm is None else list(home_arm) + [home_grip]
    if len(homes) != 6:
        raise ValueError('오른팔 HOME 배열은 5개여야 합니다.')
    drives = []
    for joint, values, home in zip(joints, settings, homes):
        if not joint.IsA(UsdPhysics.RevoluteJoint):
            raise ValueError(f'회전 관절이 아닙니다: {joint.GetPath()}')
        row = dict(path=str(joint.GetPath()), name=joint.GetName(),
                   stiffness=_positive(values['stiffness_nm_per_rad'], 'stiffness') * math.pi / 180,
                   damping=_positive(values['damping_nm_s_per_rad'], 'damping', allow_zero=True) * math.pi / 180,
                   max_force=_positive(values['effort_limit_nm'], 'effort'),
                   max_velocity=_positive(values['velocity_limit_rad_s'], 'velocity') * 180 / math.pi)
        if home is not None:
            target = float(home) * 180 / math.pi
            lower = joint.GetAttribute('physics:lowerLimit').Get()
            upper = joint.GetAttribute('physics:upperLimit').Get()
            if not math.isfinite(target) or not lower <= target <= upper:
                raise ValueError(f'{joint.GetPath()}: HOME이 관절 한계를 벗어납니다.')
            row['target_position'] = target
        drives.append(row)
    grip_bodies = []
    for name in ('physics:body0', 'physics:body1'):
        targets = joints[-1].GetRelationship(name).GetTargets()
        if len(targets) != 1 or not targets[0].HasPrefix(robot.GetPath()):
            raise ValueError('그리퍼 관절 양쪽 body가 현재 로봇 내부에 있어야 합니다.')
        body = stage.GetPrimAtPath(targets[0])
        if not body.IsValid() or not _colliders(body):
            raise ValueError(f'그리퍼 충돌체가 없습니다: {targets[0]}')
        grip_bodies.append(body)
    static = _positive(contact['static_friction'], 'static_friction', allow_zero=True)
    dynamic = _positive(contact['dynamic_friction'], 'dynamic_friction', allow_zero=True)
    restitution = _positive(contact['restitution'], 'restitution', allow_zero=True)
    offset = _positive(contact['contact_offset_m'], 'contact_offset_m')
    rest = float(contact['rest_offset_m'])
    if restitution > 1 or not math.isfinite(rest) or rest >= offset:
        raise ValueError('반발계수는 0..1, rest offset은 contact offset 미만이어야 합니다.')

    floor = config.get('box_floor', {})
    floors = []
    if floor.get('enabled', False):
        asset = Path(floor['asset_path'])
        if not asset.is_absolute() or not asset.is_file():
            raise ValueError(f'박스 바닥 독립 USD 절대 경로가 필요합니다: {asset}')
        source = Usd.Stage.Open(str(asset))
        bodies = floor['body_names']
        paths = floor['source_prims']
        if len(bodies) != 2 or len(paths) != 2:
            raise ValueError('박스 바닥 좌우 두 body와 두 source prim이 필요합니다.')
        for name, source_path in zip(bodies, paths):
            body = _named_prim(stage, robot, name)
            prim = source.GetPrimAtPath(source_path)
            if not body.HasAPI(UsdPhysics.RigidBodyAPI) or not prim.IsValid() or not _colliders(prim):
                raise ValueError(f'박스 바닥 body/source 충돌체를 확인하세요: {name}, {source_path}')
            child = body.GetPath().AppendChild('RobotarmFloorTiles')
            existing = [p for p in _colliders(body) if not p.GetPath().HasPrefix(child)]
            if existing:
                raise ValueError(f'{name}에 기존 바닥 충돌체가 있어 중복 추가를 중단합니다.')
            floors.append((body, child, source_path))

    material_path = robot.GetPath().AppendChild('RobotarmGripMaterial')
    grip_paths, floor_paths = [], []
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for joint, row in zip(joints, drives):
            drive = UsdPhysics.DriveAPI.Apply(joint, 'angular')
            drive.CreateTypeAttr('force')
            drive.CreateStiffnessAttr(row['stiffness'])
            drive.CreateDampingAttr(row['damping'])
            drive.CreateMaxForceAttr(row['max_force'])
            if 'target_position' in row:
                drive.CreateTargetPositionAttr(row['target_position'])
                drive.CreateTargetVelocityAttr(0.0)
            PhysxSchema.PhysxJointAPI.Apply(joint).CreateMaxJointVelocityAttr(row['max_velocity'])
        material = UsdShade.Material.Define(stage, material_path)
        physics = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        physics.CreateStaticFrictionAttr(static)
        physics.CreateDynamicFrictionAttr(dynamic)
        physics.CreateRestitutionAttr(restitution)
        PhysxSchema.PhysxMaterialAPI.Apply(material.GetPrim()).CreateFrictionCombineModeAttr('average')
        for body in grip_bodies:
            for prim in _make_editable(body):
                binding = UsdShade.MaterialBindingAPI.Apply(prim)
                binding.Bind(material, bindingStrength=UsdShade.Tokens.strongerThanDescendants,
                             materialPurpose='physics')
                resolved, _ = binding.ComputeBoundMaterial('physics')
                if resolved.GetPath() != material_path:
                    raise RuntimeError(f'그리퍼 접촉 재질 바인딩 실패: {prim.GetPath()}')
                if alignment is None:
                    collision = PhysxSchema.PhysxCollisionAPI.Apply(prim)
                    collision.CreateContactOffsetAttr(offset)
                    collision.CreateRestOffsetAttr(rest)
                grip_paths.append(str(prim.GetPath()))
        for body, child, source_path in floors:
            prim = UsdGeom.Xform.Define(stage, child).GetPrim()
            prim.GetReferences().SetReferences([Sdf.Reference(str(asset), source_path)])
            for collider in _colliders(prim):
                collision = PhysxSchema.PhysxCollisionAPI.Apply(collider)
                collision.CreateContactOffsetAttr(offset)
                collision.CreateRestOffsetAttr(rest)
                floor_paths.append(str(collider.GetPath()))
    return dict(joint_paths=[row['path'] for row in drives], joint_names=names,
                home_positions_rad=None if home_arm is None else [float(v) for v in homes],
                usd_drives=drives, grip_colliders=grip_paths, floor_colliders=floor_paths,
                grip_material=str(material_path), edit_layer='session', teacher_alignment=alignment)
