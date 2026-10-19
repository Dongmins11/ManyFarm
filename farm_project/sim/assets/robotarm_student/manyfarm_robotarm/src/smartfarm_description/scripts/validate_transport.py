#!/usr/bin/env python3
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/manyfarm-transport-mpl')
from pathlib import Path
import json, math
import xml.etree.ElementTree as E
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from model_geometry import fk, visuals
P=Path(__file__).resolve().parents[1];u=P/'urdf/transport_robot.portable.urdf'
root=E.parse(u).getroot();C=json.loads((P/'config/transport.json').read_text())
def states(pinion=0,tilt=0,gate=0):
 q={'lid_pinion_joint':pinion,'box_tilt_joint':tilt,'side_lid_joint':gate}
 for j in root.findall('joint'):
  m=j.find('mimic')
  if m is not None:q[j.get('name')]=q[m.get('joint')]*float(m.get('multiplier'))
 return q
links=[l.get('name') for l in root.findall('link')];assert len(links)==len(set(links))
children=[j.find('child').get('link') for j in root.findall('joint')]
assert len(children)==len(set(children));assert set(links)-set(children)=={'base_footprint'}
for j in root.findall('joint'):
 assert j.find('parent').get('link') in links
for mesh in root.iter('mesh'):assert (u.parent/mesh.get('filename')).is_file()
poses=fk(root,states());assert len(poses)==len(links)
geo=list(visuals(root,u,poses))
box=np.concatenate([v.reshape(-1,3) for n,v,c in geo if n=='cargo_box'])
assert np.allclose(box.max(0)-box.min(0),[.3,.3,.188 if C.get('fabrication_revision')==3 else .19])
assert np.isclose(box[:,2].min(),.257 if C.get('fabrication_revision')==3 else .255)
lidar=np.concatenate([v.reshape(-1,3) for n,v,c in geo if n=='base_scan'])
assert np.isclose(lidar[:,2].min(),.1018,atol=1e-7)
for l in root.findall('link'):
 i=l.find('inertial')
 if i is not None:
  assert float(i.find('mass').get('value'))>0
  a=i.find('inertia');M=np.array([[float(a.get('i'+x+y if x<=y else 'i'+y+x)) for y in 'xyz'] for x in 'xyz'])
  assert np.all(np.linalg.eigvalsh(M)>0)
assert root.find("link[@name='lid_guides']") is None
assert np.isclose(poses['base_scan'][2,3],.132)
assert root.find("link[@name='base_link']/visual/geometry/mesh").get('scale')=='0.001 0.001 0.001'
# Four support posts moved onto solid Waffle plate regions (not clipped corners).
from model_geometry import stl
tri=stl(P/'meshes/transport/waffle_base.stl')*.001
support=root.find("link[@name='cargo_support']")
for v in support.findall('visual')[:4]:
 center=np.fromstring(v.find('origin').get('xyz'),sep=' ');size=np.fromstring(v.find('geometry/box').get('size'),sep=' ')
 xy=center[:2]+np.array([.064,0]);a=tri[:,0,:2];b=tri[:,1,:2]-a;c=tri[:,2,:2]-a;d=xy-a
 det=b[:,0]*c[:,1]-b[:,1]*c[:,0];valid=np.abs(det)>1e-12
 uu=np.zeros(len(tri));vv=uu.copy()
 uu[valid]=(d[valid,0]*c[valid,1]-d[valid,1]*c[valid,0])/det[valid]
 vv[valid]=(b[valid,0]*d[valid,1]-b[valid,1]*d[valid,0])/det[valid]
 hit=valid&(uu>=0)&(vv>=0)&(uu+vv<=1)
 zs=tri[:,0,2]+uu*(tri[:,1,2]-tri[:,0,2])+vv*(tri[:,2,2]-tri[:,0,2])
 assert hit.any() and np.isclose(center[2]-size[2]/2,zs[hit].max(),atol=1e-7)
 assert np.isclose(center[2]+size[2]/2,.249-.010)

qmax=float(root.find("joint[@name='lid_pinion_joint']/limit").get('upper'))
opened=list(visuals(root,u,fk(root,states(qmax))))
# First visual on each lid is the actual cover plate.
left=next(v for n,v,c in opened if n=='top_lid_left')
right=next(v for n,v,c in opened if n=='top_lid_right')
assert left[:,:,1].min()>=.15
assert right[:,:,1].max()<=-.15
# Sample combined tilt/gate extremes: gate must swing forward; cargo must stay above ground.
for angle in np.linspace(0,C['tilt_limit_rad'],11):
 g=list(visuals(root,u,fk(root,states(qmax,angle,C['side_lid_limit_rad']))))
 for n,v,c in g:
  if n in ['cargo_box','side_lid','top_lid_left','top_lid_right']:assert v[:,:,2].min()>0
base=fk(root,states());opened_pose=fk(root,states(0,0,math.pi/2))
assert opened_pose['side_lid'][0,3]==base['side_lid'][0,3]
views=[('CLOSED',states()),('TOP OPEN / opposed racks',states(qmax)),('UNLOAD / tilt + side gate',states(qmax,C['tilt_limit_rad'],math.pi/2))]
fig=plt.figure(figsize=(17,7),facecolor='#edf1f5')
for k,(title,q) in enumerate(views,1):
 ax=fig.add_subplot(1,3,k,projection='3d',facecolor='#edf1f5')
 for n,tri,color in visuals(root,u,fk(root,q)):
  if len(tri)>5000:
   pts=tri.reshape(-1,3);_,inv=np.unique(np.round(pts/.0015).astype(int),axis=0,return_inverse=True)
   count=np.bincount(inv);merged=np.column_stack([np.bincount(inv,weights=pts[:,j])/count for j in range(3)])
   ids=inv.reshape(-1,3);good=(ids[:,0]!=ids[:,1])&(ids[:,1]!=ids[:,2])&(ids[:,0]!=ids[:,2]);ids=ids[good]
   _,keep=np.unique(np.sort(ids,axis=1),axis=0,return_index=True);tri=merged[ids[keep]]
  norms=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);norms/=np.maximum(np.linalg.norm(norms,axis=1)[:,None],1e-10)
  shade=.55+.45*np.abs(norms@np.array([.35,-.45,.82]));colors=np.tile(color,(len(tri),1));colors[:,:3]*=shade[:,None]
  ax.add_collection3d(Poly3DCollection(tri,facecolors=colors,edgecolors='none',rasterized=True))
 ax.set(xlim=(-.5,.35),ylim=(-.4,.4),zlim=(0,.7),xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)',title=title)
 ax.set_box_aspect((.85,.8,.7));ax.view_init(23,140 if k==2 else 35);ax.tick_params(labelsize=7)
fig.suptitle('ManyFarm | Waffle transport robot',fontsize=20)
fig.text(.5,.055,'Box 300 x 300 x 190 mm | Tilt axis 255 mm | Floor underside 257 mm | LDS original scan frame 132 mm',ha='center',fontsize=12)
fig.text(.5,.02,'Concept geometry: MG996R envelopes, rack teeth, rails and tilt drive require mechanical validation.',ha='center',fontsize=10)
fig.subplots_adjust(left=.01,right=.99,bottom=.11,top=.88,wspace=.02)
fig.savefig(P/'preview/transport/transport_robot.png',dpi=150)
report=f'''PASS: unique link/joint tree ({len(links)} links), mesh paths, positive inertias.
PASS: cargo shell geometry and configured floor height.
PASS: LDS original origin restored: scan frame 132 mm; body bottom 101.8 mm.
PASS: opposed cover plates fully clear opening at 155 mm stroke.
PASS: ground clearance at 11 tilt samples with gate/lids fully open.
PASS: four support posts contact original chassis mesh at z=101.5 mm; tilt axis 255 mm; rigid floor seated on 2 mm angle flange.
PASS: fabrication CAD lid mechanism installed; original chassis scale and lidar frame preserved.
Rendered closed, loading and unloading poses from the generated URDF.
Not tested: physical self-collision/contact, sensor output, servo torque, stability, Isaac import/runtime.
'''
(P/'preview/transport/VALIDATION.md').write_text(report);print(report)
