"""USD Python: 고정 캐스터의 접촉을 자유롭게 구르는 지지점으로 근사한다. 기본은 확인만."""
import argparse,json,shutil
from pathlib import Path
from pxr import Usd,UsdPhysics,UsdShade,PhysxSchema

ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'sim/assets/robots/scout_robot/urdf/scout_robot_camera_fixed.usd'


def configure(apply: bool, backup: Path) -> dict:
    """바퀴/질량/형상은 보존하고 캐스터 접촉 마찰 및 결합 방식만 변경한다."""
    stage=Usd.Stage.Open(str(ASSET))
    root=stage.GetDefaultPrim()
    casters=[p for p in Usd.PrimRange(root)
             if 'caster' in str(p.GetPath()) and p.HasAPI(UsdPhysics.CollisionAPI)]
    if not casters:
        raise ValueError('캐스터 충돌체가 없습니다.')
    result=dict(asset=str(ASSET),collision_paths=[str(p.GetPath()) for p in casters],
                static_friction=0.,dynamic_friction=0.,friction_combine='min',applied=apply)
    if not apply:
        return result
    if not backup.resolve().is_relative_to(ROOT/'sim'):
        raise ValueError('백업은 sim 안에 보존하세요.')
    if backup.exists():
        raise FileExistsError('기존 백업을 덮어쓰지 않습니다: '+str(backup))
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ASSET,backup)
    material=UsdShade.Material.Define(stage,str(root.GetPath())+'/PhysicsMaterials/PassiveCaster')
    contact=UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    contact.CreateStaticFrictionAttr(0.)
    contact.CreateDynamicFrictionAttr(0.)
    contact.CreateRestitutionAttr(0.)
    PhysxSchema.PhysxMaterialAPI.Apply(material.GetPrim()).CreateFrictionCombineModeAttr('min')
    for prim in casters:
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material,materialPurpose='physics')
    stage.GetRootLayer().Save()
    result['backup']=str(backup)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--backup',type=Path,default=ROOT/'sim/runs/localization_motion_20261023/scout_before_caster_fix.usd')
    args=parser.parse_args()
    print(json.dumps(configure(args.apply,args.backup),ensure_ascii=False,indent=2))
