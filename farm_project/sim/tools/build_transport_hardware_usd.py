"""USD Python으로 원본 보존 운송 접촉 레이어를 생성한다. 바퀴 구동/질량은 보존."""
import hashlib
import json
from pathlib import Path
from pxr import Sdf, Usd, UsdPhysics, UsdShade
from rebuild_harvest_tire_collisions import rebuild

ROOT=Path(__file__).resolve().parents[2]
DIRECTORY=ROOT/'sim/assets/robots/transport_robot/urdf/transport_robot.portable'
SOURCE=DIRECTORY/'transport_robot.portable.usd'
OUTPUT=DIRECTORY/'transport_robot.sim.usda'

def main() -> None:
    # 같은 디렉터리의 원본을 sublayer로 참조하므로 내부 상대 경로가 유지된다.
    layer=Sdf.Layer.CreateNew(str(OUTPUT))
    layer.subLayerPaths=[SOURCE.name]
    stage=Usd.Stage.Open(layer)
    source_stage=Usd.Stage.Open(str(SOURCE))
    stage.SetDefaultPrim(stage.GetPrimAtPath(source_stage.GetDefaultPrim().GetPath()))
    root=stage.GetDefaultPrim()
    wheels=rebuild(stage, ('wheel_left_link','wheel_right_link'))
    # 카메라 재개 때 중첩 visual instance의 Hydra protoPath 유실을 피한다.
    # 형상/재질/충돌은 그대로 두고 이 운송 자산의 렌더 인스턴스만 풀어 쓴다.
    visual_instances=[]
    while True:
        instances=[p for p in Usd.PrimRange(root) if p.IsInstance() and '/visuals' in str(p.GetPath())]
        if not instances:break
        for p in instances:
            visual_instances.append(str(p.GetPath()))
            p.SetInstanceable(False)
    reports=[]
    for name,friction,links in [
        ('PassiveCaster',0.,('caster_back_left_link','caster_back_right_link')),
        ('DriveTire',.8,('wheel_left_link','wheel_right_link'))]:
        material=UsdShade.Material.Define(stage,str(root.GetPath())+'/SimPhysicsMaterials/'+name)
        api=UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        api.CreateStaticFrictionAttr(friction);api.CreateDynamicFrictionAttr(friction)
        api.CreateRestitutionAttr(0.)
        if name=='PassiveCaster':
            material.GetPrim().AddAppliedSchema('PhysxMaterialAPI')
            material.GetPrim().CreateAttribute('physxMaterial:frictionCombineMode',Sdf.ValueTypeNames.Token).Set('min')
        paths=[]
        for link in links:
            prim=stage.GetPrimAtPath(root.GetPath().AppendChild(link))
            while True:
                instances=[p for p in Usd.PrimRange(prim) if p.IsInstance()]
                if not instances:break
                for p in instances:p.SetInstanceable(False)
            for p in Usd.PrimRange(prim):
                if p.HasAPI(UsdPhysics.CollisionAPI) and UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get():
                    UsdShade.MaterialBindingAPI.Apply(p).Bind(material,materialPurpose='physics')
                    paths.append(str(p.GetPath()))
        if not paths:raise ValueError('접촉 형상 없음: '+name)
        reports.append(dict(material=name,friction=friction,paths=paths))
    layer.Save()
    report=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                output=str(OUTPUT.relative_to(ROOT)),output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                wheels=wheels,materials=reports,visual_instances_expanded=visual_instances,
                note='실물 마찰 측정값이 아닌 sim 접촉 근사. 과실 배출/덮개/틸트 작동은 추가하지 않는다.')
    OUTPUT.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
