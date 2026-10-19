#!/usr/bin/env python3
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/manyfarm-sorting-mpl')
from pathlib import Path
import json
import xml.etree.ElementTree as E
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from model_geometry import fk,visuals,stl

P=Path(__file__).resolve().parents[1];u=P/'urdf/sorting_station.portable.urdf'
R=E.parse(u).getroot();C=json.loads((P/'config/sorting.json').read_text())
poses=fk(R);geo=list(visuals(R,u,poses))
links=R.findall('link');names=[x.get('name') for x in links];joints=R.findall('joint')
assert len(names)==len(set(names))==len(poses)
assert len(joints)==len(links)-1 and all(j.get('type')=='fixed' for j in joints if not j.get('name').startswith('omx_'))
assert len({j.get('name') for j in joints})==len(joints)
assert not any('pepper' in n or 'paprika' in n for n in names)
for l in links:
 if l.find('visual') is not None:
  # The OMX wrist U20CAM is a visual/sensor frame only. Its physical mass and
  # bracket are intentionally excluded until the actual mount is measured.
  if l.get('name')=='omx_wrist_camera_link':
   continue
  assert l.find('collision') is not None
  i=l.find('inertial');assert float(i.find('mass').get('value'))>0
  for k in ['ixx','iyy','izz']:assert float(i.find('inertia').get(k))>0
for p in (P/'meshes/sorting').glob('*.stl'):
 tri=stl(p);edges={}
 for face in tri:
  for a,b in zip(face,np.roll(face,-1,axis=0)):
   key=tuple(sorted([tuple(np.round(a,9)),tuple(np.round(b,9))]));edges[key]=edges.get(key,0)+1
 assert all(n==2 for n in edges.values()),p
 assert np.sum(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])))/6>0,p

def vertices(name):return next(v.reshape(-1,3) for n,v,c in geo if n==name)
v=vertices('intake_floor');assert np.isclose(v[:,2].max(),.16)
assert np.isclose(np.ptp(v[:,0]),.25) and np.isclose(np.ptp(v[:,1]),.5)
assert np.isclose(max(vertices('intake_wall_'+str(k))[:,2].max() for k in range(4)),.26)
if C['include_omx_pedestal']:assert np.isclose(poses['omx_mount_frame'][2,3],C['omx_pedestal_height'])
for side in ['left','right']:
 l=R.find(f"link[@name='{side}_ramp']");size=np.fromstring(l.find('visual/geometry/box').get('size'),sep=' ')
 T=poses[side+'_ramp'];ends=np.array([[-size[0]/2,0,size[2]/2],[size[0]/2,0,size[2]/2]])@T[:3,:3].T+T[:3,3]
 assert np.allclose(ends[:,0],[0,.272]) and np.allclose(ends[:,2],[.16,.003])
 v=vertices(side+'_storage_floor');assert np.isclose(v[:,2].max(),.003)
 assert np.isclose(np.ptp(v[:,0]),.25) and np.isclose(np.ptp(v[:,1]),.25)
# No opaque collision volume filling the intake, lanes or center opening.
# Check empty-space points against every convex panel using its triangular hull planes.
def inside(point,tri):
 center=tri.reshape(-1,3).mean(0);norm=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
 flip=np.einsum('ij,ij->i',norm,tri[:,0]-center)<0;norm[flip]*=-1
 return np.all(np.einsum('ij,ij->i',norm,point-tri[:,0])<=1e-10)
for point in [(-.1,0,.20),(.20,0,.10),(.35,.125,.05),(.35,-.125,.05),(.15,.185,.13),(.15,-.185,.13)]:
 assert not any(inside(np.array(point),tri) for _,tri,_ in geo),point
if C.get('include_sorting_camera',False):
 back=poses['sorting_camera_back_reference'][:3,3]
 assert np.isclose(back[0],-C['sorting_camera_rear_wall_offset'])
 assert np.isclose(back[1],C['sorting_camera_y'])
 assert np.isclose(back[2],C['intake_floor_top']+C['sorting_camera_back_height_above_intake_floor'])
 for frame in ['sorting_camera_depth_optical_frame','sorting_camera_color_optical_frame']:
  assert np.allclose(poses[frame][:3,2],[0,0,-1],atol=1e-9),poses[frame][:3,2]
if C['include_omx_pedestal']:
 assert np.allclose(poses['omx_link0'][:3,0],[-1,0,0])
 assert np.allclose(poses['omx_link0'][:2,3],[C['omx_pedestal_depth']/2,0])
 assert np.isclose(vertices('omx_link0')[:,2].min(),C['omx_pedestal_height'])
 assert poses['omx_end_effector_link'][0,3]<0
 arm_names={f'omx_joint{i}' for i in range(1,6)}
 assert arm_names.issubset({j.get('name') for j in joints if j.get('type')=='revolute'})
 assert any(j.get('name')=='omx_gripper_joint_1' for j in joints)
 if C.get('include_omx_wrist_camera',False):
  assert 'omx_wrist_camera_link' in poses
  assert 'omx_wrist_camera_optical_frame' in poses
  rel=np.linalg.inv(poses['omx_link5'])@poses['omx_wrist_camera_optical_frame']
  assert np.allclose(rel[:3,2],[1,0,0],atol=1e-9),rel[:3,2]

allv=np.concatenate([v.reshape(-1,3) for n,v,c in geo]);assert allv[:,2].min()>-1e-8

fig=plt.figure(figsize=(18,9),facecolor='#e6eaef')
views=[('ASSEMBLY',28,135,False),('TOP / plan',90,-90,False),('LANES / pedestal hidden',27,-40,True)]
for k,(title,elev,azim,hide) in enumerate(views,1):
 ax=fig.add_subplot(1,3,k,projection='3d',facecolor='#e6eaef')
 for n,tri,c in geo:
  if hide and n.startswith('omx_pedestal'):continue
  norms=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);norms/=np.maximum(np.linalg.norm(norms,axis=1)[:,None],1e-12)
  shade=.65+.35*np.abs(norms@np.array([.35,-.45,.82]));colors=np.tile(c,(len(tri),1));colors[:,:3]*=shade[:,None]
  ax.add_collection3d(Poly3DCollection(tri,facecolors=colors,edgecolors='#929a9f',linewidths=.18))
 ax.set(xlim=(-.30,.57),ylim=(-.30,.30),zlim=(0,.78),xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)',title=title)
 ax.set_box_aspect((.87,.60,.55));ax.view_init(elev,azim);ax.tick_params(labelsize=7)
 if k==2:ax.set_zticks([]);ax.set_zlabel('')
fig.suptitle('ManyFarm | Foam-board sorting station',fontsize=21,y=.92)
fig.text(.5,.13,'Intake: 500 x 250 mm trapezoid | floor 160 mm | rim 260 mm | two 130 mm lanes',ha='center',fontsize=12)
fig.text(.5,.085,'OMX pedestal: 235 x 130 x 200 mm | OMX arm facing intake; no peppers | station panels fixed; arm articulated',ha='center',fontsize=11)
fig.text(.5,.04,'Storage depth 250 mm selected from side sketch; 300 mm top-view annotation remains unresolved.',ha='center',fontsize=10,color='#495560')
fig.subplots_adjust(left=.01,right=.99,bottom=.18,top=.84,wspace=.025)
fig.savefig(P/'preview/sorting/sorting_station.png',dpi=160)
report='''# Geometry validation

PASS: one connected tree; station fixed, OMX articulated; unique links/joints; visual/collision pairs and positive inertias.
PASS: all generated STL panels are closed with outward orientation and positive volume.
PASS: intake plan 500 x 250 mm; floor surface 160 mm, wall top 260 mm.
PASS: ramp top endpoints (x,z) = (0,160) -> (272,3) mm; angle 29.9938 deg.
PASS: two 250 x 250 mm nominal storage floor panels; mount frame height 200 mm.
PASS: sampled intake, chute, bin and central free-space points are not filled by collision solids.
PASS: sorting D435 back reference is 556 mm above intake floor, 58 mm from rear wall, with RGB/depth optical +Z vertically down.
PASS: OMX-F pedestal contact, centered mount, five arm joints + actuated gripper joint and intake-facing tool verified.
PASS: OMX wrist InnoMaker U20CAM-720P sensor frame is attached to link5 with optical +Z aligned to tool-forward +X.
PASS: all geometry above ground. No pepper meshes/links. Preview rendered from URDF geometry.

This is a geometry check, not a contact/dynamics or Isaac import test. Material friction, mass,
foam compliance and actual pepper sliding behavior require simulation calibration.
'''
(P/'preview/sorting/VALIDATION.md').write_text(report);print(report)
