"""CPU CAD review of the separate U20 assembly, not a sensor render."""
import argparse,json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from model_geometry import fk,visuals,origin

PKG=Path(__file__).resolve().parents[1];ROOT=PKG.parents[1]

def plot(ax,parts,elev,azim,alpha=1.):
    points=[];faces=[];colours=[]
    for name,tri,color in parts:
        selected=tri
        normals=np.cross(selected[:,1]-selected[:,0],selected[:,2]-selected[:,0]);normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
        light=np.array([.25,.65,.72]);light/=np.linalg.norm(light)
        shade=.5+.5*np.abs(normals@light)
        rgba=np.c_[np.asarray(color)[None,:]*shade[:,None],np.full(len(selected),alpha if 'mount' in name else 1.)]
        faces.extend(selected);colours.extend(rgba);points.append(tri.reshape(-1,3))
    ax.add_collection3d(Poly3DCollection(np.asarray(faces),facecolors=np.asarray(colours),edgecolors='none'))
    p=np.vstack(points);lo=p.min(0);hi=p.max(0);center=(lo+hi)/2;half=(hi-lo).max()*.55
    ax.set_xlim(center[0]-half,center[0]+half);ax.set_ylim(center[1]-half,center[1]+half);ax.set_zlim(center[2]-half,center[2]+half)
    ax.set_box_aspect([1,1,1]);ax.view_init(elev,azim);ax.set_axis_off()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'reports/u20_wrist_v1_20261015');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    urdf=PKG/'urdf/harvest_robot_u20_wrist_v1.urdf';root=ET.parse(urdf).getroot();poses=fk(root,{'arm_2/gripper':.8})
    g=np.linalg.inv(poses['arm_2/gripper_link']);mount=np.linalg.inv(poses['arm_2/wrist_camera_mount_link'])
    allowed={'arm_2/gripper_link','arm_2/moving_jaw_so101_v1_link'}|{e.get('name') for e in root.findall('link') if e.get('name').startswith('arm_2/wrist_camera')}
    for link in list(root.findall('link')):
        if link.get('name') not in allowed:root.remove(link)
    wrist=[];detail=[];scene=trimesh.Scene()
    for i,(name,tri,rgba) in enumerate(visuals(root,urdf,poses)):
        color=rgba[:3]
        a_tri=(tri@g[:3,:3].T+g[:3,3])*1000
        wrist.append((name,a_tri,color))
        if 'camera' in name:detail.append((name,(tri@mount[:3,:3].T+mount[:3,3])*1000,color))
        mesh=trimesh.Trimesh(a_tri.reshape(-1,3)*.001,np.arange(len(a_tri)*3).reshape(-1,3),process=False)
        mesh.visual.face_colors=np.tile(np.rint(np.r_[color,1]*255).astype(np.uint8),(len(mesh.faces),1));scene.add_geometry(mesh,node_name=f'{name}_{i}')
    scene.export(a.output/'wrist_u20_assembled.glb')
    fig=plt.figure(figsize=(15,5),layout='constrained');axs=[fig.add_subplot(1,3,i+1,projection='3d') for i in range(3)]
    plot(axs[0],wrist,20,-125);axs[0].set_title('Actual assembled wrist\nRight arm; gripper 0.8 rad')
    plot(axs[1],detail,15,65);axs[1].set_title('Camera fitted to original mount\nPCB behind; lens through aperture')
    plot(axs[2],detail,20,115,alpha=.23);axs[2].set_title('Transparent mount inspection\nWhite mount; black U20 camera')
    fig.suptitle('U20 wrist v1 CAD review - estimated lens envelope; no real-fit certification',fontsize=12)
    fig.savefig(a.output/'assembly_review.png',dpi=170);plt.close(fig)
    print(a.output/'assembly_review.png')

if __name__=='__main__':main()
