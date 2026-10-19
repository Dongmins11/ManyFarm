#!/usr/bin/env python3
"""Render actual URDF mesh geometry at zero joints, without a simulator."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/manyfarm-matplotlib')
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from model_geometry import fk, visuals

pkg=Path(__file__).resolve().parents[1]
urdf=pkg/'urdf/harvest_robot.urdf'
root=ET.parse(urdf).getroot(); poses=fk(root)
geometry=list(visuals(root,urdf,poses))
fig=plt.figure(figsize=(16,8),facecolor='#edf1f5')
views=[('ASSEMBLY / perspective',23,-48),('FRONT / +X',0,0),('WORKING FACE / -Y',0,-90)]
for n,(title,elev,azim) in enumerate(views,1):
    ax=fig.add_subplot(1,3,n,projection='3d',facecolor='#edf1f5')
    for name,tri,color in geometry:
        # Vertex clustering keeps connected surfaces; never drop arbitrary triangles.
        if len(tri)>5000:
            pitch=0.0008 if name.startswith('arm_') else 0.002
            points=tri.reshape(-1,3)
            _,inv=np.unique(np.round(points/pitch).astype(np.int64),axis=0,return_inverse=True)
            count=np.bincount(inv)
            merged=np.column_stack([np.bincount(inv,weights=points[:,k])/count for k in range(3)])
            indices=inv.reshape(-1,3)
            valid=(indices[:,0]!=indices[:,1])&(indices[:,1]!=indices[:,2])&(indices[:,0]!=indices[:,2])
            indices=indices[valid]
            _,keep=np.unique(np.sort(indices,axis=1),axis=0,return_index=True)
            tri=merged[indices[keep]]
        normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]); norm=np.linalg.norm(normals,axis=1)
        normals=normals/np.maximum(norm[:,None],1e-12)
        light=.57+.43*np.abs(normals@np.array([.35,-.45,.82]))
        colors=np.tile(color,(len(tri),1)); colors[:,:3]*=light[:,None]
        ax.add_collection3d(Poly3DCollection(tri,facecolors=colors,edgecolors='none',rasterized=True))
    ax.set_xlim(-.40,.40); ax.set_ylim(-.72,.36); ax.set_zlim(0,1.30)
    ax.set_box_aspect((.8,1.08,1.30)); ax.view_init(elev,azim)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)'); ax.set_zlabel('Z (m)')
    ax.set_title(title,fontsize=12,fontweight='bold',pad=18)
    ax.tick_params(labelsize=7)
    if n==2: ax.set_xticks([]); ax.set_xlabel('')
    if n==3: ax.set_yticks([]); ax.set_ylabel('')
fig.suptitle('ManyFarm | Dual SO101 + 3 x D435 + fixed paprika box',fontsize=20,fontweight='bold',y=.96)
deck_z=poses['top_deck'][2,3]+float(root.find("link[@name='top_deck']/visual/geometry/box").get('size').split()[2])/2
height=poses['top_camera_link'][2,3]-deck_z if 'top_camera_link' in poses else 0
fig.text(.5,.06,f'Deck {deck_z:.3f} m  |  Central camera center: deck + {height:.3f} m  |  D435 on each wrist',ha='center',fontsize=12)
fig.text(.5,.025,'New rear camera support + wrist mount STLs + simplified D435 housings. Zero joints. Mechanical fit and dynamic collision validation pending.',ha='center',fontsize=10,color='#475569')
fig.subplots_adjust(left=.02,right=.98,bottom=.13,top=.87,wspace=.05)
output=pkg/'preview/assembly.png'; fig.savefig(output,dpi=160);print(output)
for name in ['arm_1/base_link','arm_1/tool0','arm_2/base_link','arm_2/tool0','harvest_box']:
 print(name,poses[name][:3,3].round(4).tolist())
