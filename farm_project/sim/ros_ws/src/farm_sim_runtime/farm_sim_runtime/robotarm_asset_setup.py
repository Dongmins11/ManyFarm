"""받은 오른팔 물성과 박스 바닥을 세션 레이어에만 적용한다.

주행 USD의 바퀴·캐스터를 보존하며 양팔 주행 자세는 별도로 적용한다. 학습 정렬 시 오른팔의 고정 카메라
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


def expand_box_visual_instances(stage: object, robot: object) -> list[str]:
    """Hydra가 Cube prototype을 누락하는 외형 그룹만 세션에서 인스턴스를 푼다.

    기하·재질·변환과 별도 collisions 그룹은 그대로 둔다. 원본 USD는 저장하지 않는다.
    """
    from pxr import Usd, UsdGeom
    groups = [prim for prim in Usd.PrimRange(robot)
              if prim.GetName() == 'visuals' and prim.IsInstance()
              and any(child.IsA(UsdGeom.Cube)
                      for child in Usd.PrimRange(prim, Usd.TraverseInstanceProxies()))]
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for prim in groups:
            prim.SetInstanceable(False)
    return [str(prim.GetPath()) for prim in groups]


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
    if floor.get('enabled') and floor.get('mode') != 'teacher60_unified':
        raise ValueError('60Hz 단일 박스 바닥만 지원합니다.')

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
        finger_material = UsdShade.Material.Define(stage, robot.GetPath().AppendChild('Teacher60FingerMaterial'))
        finger_api = UsdPhysics.MaterialAPI.Apply(finger_material.GetPrim())
        finger_api.CreateStaticFrictionAttr(float(contact['finger_friction']))
        finger_api.CreateDynamicFrictionAttr(float(contact['finger_friction']))
        finger_api.CreateRestitutionAttr(restitution)
        PhysxSchema.PhysxMaterialAPI.Apply(finger_material.GetPrim()).CreateFrictionCombineModeAttr('average')
        for body in grip_bodies:
            token = ('wrist_roll_follower_so101_v1' if body.GetName() == 'arm_2_gripper_link'
                     else 'moving_jaw_so101_v1')
            for prim in _make_editable(body):
                # 합성 카메라/모터는 baseline1.0, 손가락 충돌 메시만2.2다.
                selected_material = finger_material if token in str(prim.GetPath()) else material
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(selected_material,
                    bindingStrength=UsdShade.Tokens.strongerThanDescendants, materialPurpose='physics')
                if alignment is None:
                    collision = PhysxSchema.PhysxCollisionAPI.Apply(prim)
                    collision.CreateContactOffsetAttr(offset)
                    collision.CreateRestOffsetAttr(rest)
                grip_paths.append(str(prim.GetPath()))
        if floor.get('enabled'):
            from pxr import Gf
            import numpy as np
            bodies = [_named_prim(stage, robot, n) for n in ('box_bottom_left', 'box_bottom_right')]
            for body in bodies:
                for prim in _make_editable(body):
                    UsdPhysics.CollisionAPI(prim).CreateCollisionEnabledAttr(False)
            body = bodies[0]
            mount = stage.GetPrimAtPath(joints[0].GetRelationship('physics:body0').GetTargets()[0])
            cache = UsdGeom.XformCache()
            policy_world = np.asarray(cache.GetLocalToWorldTransform(mount)).T.copy()
            policy_world[:3, 3] -= policy_world[:3, :3] @ np.array([.235, -.19, .713])
            lo, hi = np.asarray(floor['policy_lower_m']), np.asarray(floor['policy_upper_m'])
            shape = np.eye(4); shape[:3, :3] = np.diag(hi-lo); shape[:3, 3] = (lo+hi)/2
            local = np.linalg.inv(np.asarray(cache.GetLocalToWorldTransform(body)).T) @ policy_world @ shape
            cube = UsdGeom.Cube.Define(stage, body.GetPath().AppendChild('Teacher60ClosedFloor'))
            cube.CreateSizeAttr(1.)
            xform = UsdGeom.Xformable(cube)
            xform.ClearXformOpOrder()
            xform.AddTransformOp().Set(Gf.Matrix4d(local.T.tolist()))
            cube.CreateVisibilityAttr('invisible')
            UsdPhysics.CollisionAPI.Apply(cube.GetPrim()).CreateCollisionEnabledAttr(True)
            collision = PhysxSchema.PhysxCollisionAPI.Apply(cube.GetPrim())
            collision.CreateContactOffsetAttr(float(floor['contact_offset_m']))
            collision.CreateRestOffsetAttr(0.)
            floor_paths.append(str(cube.GetPath()))
    travel = None
    if config.get('travel_pose') is not None:
        travel_names = [n.replace('arm_2_', 'arm_1_', 1) for n in names] + names
        positions = [float(v) for side in ('left', 'right')
                     for v in config['travel_pose'][side+'_positions_rad']]
        if any(len(config['travel_pose'][side+'_positions_rad']) != 6 for side in ('left', 'right')):
            raise ValueError('주행 자세는 좌우 각각 6축이어야 합니다.')
        travel_joints = [_named_prim(stage, robot, name) for name in travel_names]
        for joint, angle in zip(travel_joints, positions):
            if (not math.isfinite(angle) or not joint.GetAttribute('physics:lowerLimit').Get()
                    <= math.degrees(angle) <= joint.GetAttribute('physics:upperLimit').Get()):
                raise ValueError(f'{joint.GetPath()}: 주행 자세가 관절 한계를 벗어납니다.')
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            for index, (joint, angle) in enumerate(zip(travel_joints, positions)):
                drive = UsdPhysics.DriveAPI.Apply(joint, 'angular')
                if index < 6:
                    # 같은 서보의 주행 유지에도 오른팔과 같은 SI drive 한도를 사용한다.
                    row = drives[index]
                    drive.CreateTypeAttr('force')
                    drive.CreateStiffnessAttr(row['stiffness'])
                    drive.CreateDampingAttr(row['damping'])
                    drive.CreateMaxForceAttr(row['max_force'])
                    PhysxSchema.PhysxJointAPI.Apply(joint).CreateMaxJointVelocityAttr(row['max_velocity'])
                drive.CreateTargetPositionAttr(math.degrees(angle))
                drive.CreateTargetVelocityAttr(0.)
            # 왼팔 고정 카메라 마운트는 손목 CAD와 겹친다. 오른팔의 고정 body 합성과
            # 동일하게 직접 인접한 손목 쌍만 제외하고 외부/비인접 접촉은 보존한다.
            mount = _named_prim(stage, robot, 'arm_1_wrist_camera_mount_link')
            wrist = _named_prim(stage, robot, 'arm_1_wrist_link')
            UsdPhysics.FilteredPairsAPI.Apply(mount).CreateFilteredPairsRel().AddTarget(wrist.GetPath())
        travel = dict(joint_names=travel_names, positions_rad=positions,
                      filtered_pairs=[[str(mount.GetPath()), str(wrist.GetPath())]])
    return dict(travel_pose=travel, joint_paths=[row['path'] for row in drives], joint_names=names,
                home_positions_rad=None if home_arm is None else [float(v) for v in homes],
                usd_drives=drives, grip_colliders=grip_paths, floor_colliders=floor_paths,
                grip_material=str(material_path), edit_layer='session', teacher_alignment=alignment)
