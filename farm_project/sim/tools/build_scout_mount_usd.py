"""기구/센서 visual 및 TF를 URDF에서 생성. 질량 추정이나 본체 재임포트 없음."""
from pathlib import Path
import xml.etree.ElementTree as ET
import math,numpy as np
from pxr import Usd,UsdGeom,UsdPhysics,Gf
import argparse
parser=argparse.ArgumentParser(description='수정된 scout URDF에서 장착 USD 레이어 생성')
parser.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[2])
r=parser.parse_args().project_root.resolve()
u=ET.parse(r/'sim/assets/robots/scout_robot/urdf/turtlebot3_burger.portable.urdf').getroot()
# 기존 Burger 본체 프레임은 기존 USD에 남겨 둡니다.
names={'base_footprint','base_link','wheel_left_link','wheel_right_link','caster_back_link','imu_link','base_scan'}
links={x.get('name'):x for x in u.findall('link')}
joints={j.find('child').get('link'):j for j in u.findall('joint')}
def matrix(n):
 if n=='base_footprint':return np.eye(4)
 j=joints[n];o=j.find('origin');x,y,z=map(float,o.get('xyz','0 0 0').split());a,b,c=map(float,o.get('rpy','0 0 0').split())
 ca,sa,cb,sb,cc,sc=math.cos(a),math.sin(a),math.cos(b),math.sin(b),math.cos(c),math.sin(c)
 m=np.eye(4);m[:3,:3]=[[cc*cb,cc*sb*sa-sc*ca,cc*sb*ca+sc*sa],[sc*cb,sc*sb*sa+cc*ca,sc*sb*ca-cc*sa],[-sb,cb*sa,cb*ca]];m[:3,3]=[x,y,z]
 return matrix(j.find('parent').get('link'))@m
out=r/'sim/assets/robots/scout_robot/scout_mount_20261013.usda'
st=Usd.Stage.CreateNew(str(out));root=UsdGeom.Xform.Define(st,'/ScoutMount');st.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(st,'Z');UsdGeom.SetStageMetersPerUnit(st,1.)
colors={m.get('name'):list(map(float,m.find('color').get('rgba').split()))[:3] for m in u.findall('material')}
for name,link in links.items():
 if name in names:continue
 p='/ScoutMount/'+name;xf=UsdGeom.Xform.Define(st,p);xf.AddTransformOp().Set(Gf.Matrix4d(*matrix(name).T.flatten().tolist()))
 for i,v in enumerate(link.findall('visual')):
  geom=v.find('geometry');box=geom.find('box');cyl=geom.find('cylinder');path=p+'/visual_'+str(i)
  if box is not None:
   g=UsdGeom.Cube.Define(st,path);g.CreateSizeAttr(1.);scale=list(map(float,box.get('size').split()))
  else:
   g=UsdGeom.Cylinder.Define(st,path);g.CreateRadiusAttr(float(cyl.get('radius')));g.CreateHeightAttr(float(cyl.get('length')));g.CreateAxisAttr('Z');scale=None
  o=v.find('origin');xyz=list(map(float,o.get('xyz','0 0 0').split())) if o is not None else [0,0,0]
  g.AddTranslateOp().Set(Gf.Vec3d(*xyz))
  if scale:g.AddScaleOp().Set(Gf.Vec3f(*scale))
  g.CreateDisplayColorAttr([Gf.Vec3f(*colors[v.find('material').get('name')])])
  if name=='scout_mast_link':UsdPhysics.CollisionAPI.Apply(g.GetPrim())
st.GetRootLayer().Save()
print(out)
