"""Render closed/open sliding floor directly from exported URDF geometry."""
from pathlib import Path
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from model_geometry import fk, visuals

pkg=Path(__file__).resolve().parents[1]
urdf=pkg/'urdf/harvest_robot.urdf'
root=ET.parse(urdf).getroot()
stroke=float(root.find("joint[@name='box_bottom_left_joint']/limit").get('upper'))
# Keep only box visuals, avoiding unnecessary upstream mesh loading.
for link in root.findall('link'):
    if not link.get('name').startswith('box_'):
        for visual in link.findall('visual'):
            link.remove(visual)
fig=plt.figure(figsize=(12,5))
for index,q in enumerate([0,stroke]):
    ax=fig.add_subplot(1,2,index+1,projection='3d')
    poses=fk(root,{f'box_bottom_{side}_joint':q for side in ['left','right']})
    for name,faces,color in visuals(root,urdf,poses):
        bottom=name.startswith('box_bottom_')
        ax.add_collection3d(Poly3DCollection(faces,facecolors=color[:3],
            alpha=1 if bottom else .15,edgecolors='black',linewidths=.3))
    ax.set(xlim=(.28,.52),ylim=(-.23,.23),zlim=(.48,.72),
           xlabel='x: forward (m)',ylabel='y: left (m)',zlabel='z: up (m)',
           title=f'{"CLOSED" if q==0 else "OPEN"} | each joint = {q:.3f} m')
    ax.set_box_aspect((.24,.46,.24))
    ax.view_init(elev=28,azim=35)
fig.tight_layout()
fig.savefig(pkg/'preview/box_sliding_bottom.png',dpi=160)
