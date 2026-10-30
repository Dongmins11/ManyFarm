"""운송 원본 URDF와 실행 USD의 뚜껑 관절 범위를 읽기 전용 비교한다. USD Python 필요."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from pxr import Usd, UsdGeom
root=Path(__file__).resolve().parents[2]
asset=root/'sim/assets/robots/transport_robot/urdf/transport_robot.portable/transport_robot.sim.usda'
urdf=root/'sim/assets/robots/transport_robot/urdf/transport_robot.urdf'
asset_stage=Usd.Stage.Open(str(asset))
s=Usd.Stage.CreateInMemory()
UsdGeom.SetStageMetersPerUnit(s,1.0)
UsdGeom.Xform.Define(s,'/manyfarm_transport_robot').GetPrim().GetReferences().AddReference(str(asset))
xml=ET.parse(urdf).getroot();rows=[]
for name in ('top_lid_left_joint','top_lid_right_joint','lid_pinion_joint','wheel_left_joint','wheel_right_joint'):
 p=s.GetPrimAtPath('/manyfarm_transport_robot/joints/'+name)
 u=xml.find("joint[@name='"+name+"']");limit=u.find('limit');mimic=u.find('mimic')
 rows.append(dict(name=name,usd_type=p.GetTypeName(),urdf_type=u.attrib['type'],
  urdf_limit=dict(limit.attrib) if limit is not None else None,
  urdf_mimic=dict(mimic.attrib) if mimic is not None else None,
  usd_attributes={a.GetName():str(a.Get()) for a in p.GetAttributes() if a.HasAuthoredValueOpinion()},
  usd_api_metadata=str(p.GetMetadata('apiSchemas')),
  authoring_layers=[str(x.layer.identifier) for x in p.GetPrimStack()]))
report=dict(asset=str(asset),urdf=str(urdf),asset_stage_meters_per_unit=asset_stage.GetMetadata('metersPerUnit'),
 composed_stage_meters_per_unit=s.GetMetadata('metersPerUnit'),
 composition='run_fleet와 같은 1m stage에 AddReference; 원본 자산은 읽기 전용',joints=rows)
Path(sys.argv[1]).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
