"""전달 학습 자산의 오른팔 물리를 세션에 이식하고 출처/적용값을 기록한다."""
from pathlib import Path
import hashlib
import json

BODY_NAMES = ('arm_2_shoulder_link', 'arm_2_upper_arm_link', 'arm_2_lower_arm_link',
              'arm_2_wrist_link', 'arm_2_gripper_link', 'arm_2_moving_jaw_so101_v1_link')


def align_teacher_arm(stage: object, robot: object, config: dict) -> dict:
    """차체의 이동 관절은 유지하고 여섯 팔 몸체를 전달 물리와 일치시킨다."""
    from pxr import PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade
    from .robotarm_asset_setup import _named_prim, _make_editable
    path = Path(config['asset_path'])
    manifest = json.loads(path.with_suffix('.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['asset_sha256']:
        raise ValueError('학습 팔 기준 자산 SHA256 불일치')
    source = Usd.Stage.Open(str(path))
    source_root = source.GetDefaultPrim().GetPath()
    target_root = robot.GetPath()
    report = dict(asset_sha256=manifest['asset_sha256'], bodies=[], disabled=[], colliders=[])
    layer = stage.GetSessionLayer()
    with Usd.EditContext(stage, layer):
        # 원래 집게와 별도 고정 연결된 카메라를 남기면 질량/충돌이 이중 계산된다.
        for name in config['merged_fixed_bodies'] + config['merged_fixed_joints']:
            prim = _named_prim(stage, robot, name)
            report['disabled'].append(str(prim.GetPath()))
            prim.SetActive(False)
        Sdf.CopySpec(source.GetRootLayer(), source_root.AppendChild('Looks'), layer,
                     target_root.AppendChild('TeacherLooks'))
        material = UsdShade.Material.Define(stage, target_root.AppendChild('TeacherArmMaterial'))
        mat = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        mat.CreateStaticFrictionAttr(1.0)
        mat.CreateDynamicFrictionAttr(.8)
        mat.CreateRestitutionAttr(0.0)
        pm = PhysxSchema.PhysxMaterialAPI.Apply(material.GetPrim())
        pm.CreateFrictionCombineModeAttr('average')
        pm.CreateRestitutionCombineModeAttr('average')
        # 학습에서는 차체에 합쳐진 팔 받침은 이동 차체의 기존 구조를 유지한다.
        for name in ('arm_2_mount', 'arm_2_base_link'):
            for prim in _make_editable(_named_prim(stage, robot, name)):
                if prim.IsA(UsdGeom.Mesh):
                    UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr('convexDecomposition')
                UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,
                    bindingStrength=UsdShade.Tokens.strongerThanDescendants, materialPurpose='physics')
        for name in BODY_NAMES:
            body = _named_prim(stage, robot, name)
            reference = source.GetPrimAtPath(source_root.AppendChild(name))
            _make_editable(body)
            for key in ('mass', 'density', 'centerOfMass', 'diagonalInertia', 'principalAxes'):
                attr = reference.GetAttribute('physics:'+key)
                body.CreateAttribute(attr.GetName(), attr.GetTypeName()).Set(attr.Get())
            # 기존 충돌을 비활성화하고 동일 링크 좌표의 기준 메시를 적용한다.
            old = body.GetChild('collisions')
            if old:
                old.SetActive(False)
            destination = body.GetPath().AppendChild('TeacherCollisions')
            Sdf.CopySpec(source.GetRootLayer(), reference.GetPath().AppendChild('collisions'), layer, destination)
            # 합쳐진 카메라 외형도 같은 집게 몸체를 따라 움직이게 한다.
            if name == 'arm_2_gripper_link':
                body.GetChild('visuals').SetActive(False)
                visual = body.GetPath().AppendChild('TeacherVisuals')
                Sdf.CopySpec(source.GetRootLayer(), reference.GetPath().AppendChild('visuals'), layer, visual)
                for prim in Usd.PrimRange(stage.GetPrimAtPath(visual)):
                    for rel in prim.GetRelationships():
                        targets = [p.ReplacePrefix(source_root.AppendChild('Looks'), target_root.AppendChild('TeacherLooks'))
                                   .ReplacePrefix(reference.GetPath().AppendChild('visuals'), visual)
                                   for p in rel.GetTargets()]
                        rel.SetTargets(targets)
            for prim in Usd.PrimRange(stage.GetPrimAtPath(destination)):
                if prim.HasAPI(UsdPhysics.CollisionAPI):
                    UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,
                        bindingStrength=UsdShade.Tokens.strongerThanDescendants, materialPurpose='physics')
                    report['colliders'].append(str(prim.GetPath()))
            report['bodies'].append(dict(name=name, mass_kg=UsdPhysics.MassAPI(body).GetMassAttr().Get()))
        # 회전 관절 한계/armature/마찰을 기준 USD에서 복사한다.
        for source_joint in source.GetPrimAtPath(source_root.AppendChild('joints')).GetChildren():
            if not source_joint.IsA(UsdPhysics.RevoluteJoint):
                continue
            joint = _named_prim(stage, robot, source_joint.GetName())
            PhysxSchema.PhysxJointAPI.Apply(joint)
            for key in ('physics:lowerLimit', 'physics:upperLimit', 'physxJoint:armature',
                        'physxJoint:jointFriction', 'physxJoint:maxJointVelocity'):
                attr = source_joint.GetAttribute(key)
                if attr and attr.Get() is not None:
                    joint.CreateAttribute(key, attr.GetTypeName()).Set(attr.Get())
        roots = [p for p in Usd.PrimRange(robot) if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
        if len(roots) != 1:
            raise ValueError('수확 articulation root는 하나여야 합니다.')
        api = PhysxSchema.PhysxArticulationAPI.Apply(roots[0])
        api.CreateEnabledSelfCollisionsAttr(True)
        api.CreateSolverPositionIterationCountAttr(12)
        api.CreateSolverVelocityIterationCountAttr(4)
        report['articulation_root'] = str(roots[0].GetPath())
        report['solver_position_iterations'], report['solver_velocity_iterations'] = 12, 4
        report['self_collision'] = True
    return report


def align_teacher_scene(world: object) -> dict:
    """학습 접촉 solver와 농장 규모의 GPU 버퍼를 World 생성 후 reset 전에 적용한다."""
    from pxr import PhysxSchema, Sdf, Usd
    context = world.get_physics_context()
    scene = PhysxSchema.PhysxSceneAPI.Apply(context.get_current_physics_scene_prim())
    values = dict(SolverType='TGS', EnableCCD=False, EnableStabilization=False,
        EnableExternalForcesEveryIteration=False, EnableEnhancedDeterminism=False,
        SolveArticulationContactLast=False, BounceThreshold=.5,
        FrictionOffsetThreshold=.04, FrictionCorrelationDistance=.025,
        MinPositionIterationCount=1, MaxPositionIterationCount=255,
        MinVelocityIterationCount=0, MaxVelocityIterationCount=255,
        GpuMaxRigidContactCount=8388608, GpuMaxRigidPatchCount=163840,
        # 농장 초기 충돌쌍 요구량 최대 4,048,988개를 담는 최소 2의 거듭제곱이다.
        # 학습 소형 장면의 2,097,152개 버퍼 부족으로 접촉쌍이 유실되지 않게 한다.
        GpuFoundLostPairsCapacity=4194304, GpuFoundLostAggregatePairsCapacity=33554432,
        GpuTotalAggregatePairsCapacity=2097152)
    stage = scene.GetPrim().GetStage()
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        for name, value in values.items():
            creator = getattr(scene, 'Create'+name+'Attr', None)
            if creator is not None:
                creator(value)
            else:
                # IsaacLab 5.1의 확장 속성은 USD 기본 schema 메서드에 없을 수 있다.
                types = {bool: Sdf.ValueTypeNames.Bool, int: Sdf.ValueTypeNames.Int,
                         float: Sdf.ValueTypeNames.Float, str: Sdf.ValueTypeNames.Token}
                scene.GetPrim().CreateAttribute('physxScene:'+name[0].lower()+name[1:],
                                                types[type(value)]).Set(value)
        context.enable_gpu_dynamics(True)
        context.set_broadphase_type('GPU')
    return values
