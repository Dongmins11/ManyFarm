"""Small URDF FK/mesh reader for offline geometry validation and preview."""
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation

def transform(xyz=(0,0,0), rpy=(0,0,0)):
    t=np.eye(4); t[:3,:3]=Rotation.from_euler('xyz',rpy).as_matrix(); t[:3,3]=xyz
    return t

def origin(e):
    if e is None: return np.eye(4)
    return transform([float(v) for v in e.get('xyz','0 0 0').split()], [float(v) for v in e.get('rpy','0 0 0').split()])

def fk(root, q=None):
    q=q or {}; joints=root.findall('joint')
    children={j.find('child').get('link') for j in joints}
    base=next(l.get('name') for l in root.findall('link') if l.get('name') not in children)
    poses={base:np.eye(4)}
    remaining=list(joints)
    while remaining:
        progressed=False
        for j in remaining[:]:
            parent=j.find('parent').get('link'); child=j.find('child').get('link')
            if parent not in poses: continue
            motion=np.eye(4)
            if j.get('type') in ('revolute','continuous'):
                axis=np.array([float(x) for x in j.find('axis').get('xyz').split()])
                motion[:3,:3]=Rotation.from_rotvec(axis*q.get(j.get('name'),0.)).as_matrix()
            elif j.get('type') == 'prismatic':
                axis=np.array([float(x) for x in j.find('axis').get('xyz').split()])
                motion[:3,3]=axis*q.get(j.get('name'),0.)
            poses[child]=poses[parent]@origin(j.find('origin'))@motion
            remaining.remove(j); progressed=True
        if not progressed: raise ValueError('Disconnected/cyclic URDF')
    return poses

def stl(path):
    data=path.read_bytes()
    count=struct.unpack_from('<I',data,80)[0] if len(data)>=84 else 0
    if len(data)==84+50*count:
        dt=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')])
        return np.frombuffer(data,dt,count=count,offset=84)['v'].astype(float)
    verts=[]
    for line in data.decode().splitlines():
        fields=line.split()
        if fields and fields[0]=='vertex': verts.append([float(x) for x in fields[1:]])
    return np.array(verts).reshape(-1,3,3)

def box(size):
    x,y,z=np.array(size)/2
    v=np.array([[-x,-y,-z],[x,-y,-z],[x,y,-z],[-x,y,-z],[-x,-y,z],[x,-y,z],[x,y,z],[-x,y,z]])
    f=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    return v[f]

def cylinder(radius, length, segments=32):
    angles=np.arange(segments)*2*np.pi/segments
    lower=np.column_stack([radius*np.cos(angles),radius*np.sin(angles),np.full(segments,-length/2)])
    upper=lower.copy();upper[:,2]=length/2
    faces=[]
    for i in range(segments):
        j=(i+1)%segments
        faces.extend([[lower[i],lower[j],upper[j]],[lower[i],upper[j],upper[i]],
                      [[0,0,-length/2],lower[j],lower[i]],[[0,0,length/2],upper[i],upper[j]]])
    return np.array(faces)

def mesh_path(filename, urdf):
    prefix='package://smartfarm_description/'
    return urdf.parent.parent/filename[len(prefix):] if filename.startswith(prefix) else urdf.parent/filename

def visuals(root, urdf, poses):
    materials={m.get('name'):m.find('color').get('rgba') for m in root.findall('material') if m.find('color') is not None}
    for link in root.findall('link'):
        for visual in link.findall('visual'):
            g=visual.find('geometry'); t=poses[link.get('name')]@origin(visual.find('origin'))
            if g.find('mesh') is not None:
                m=g.find('mesh'); path=mesh_path(m.get('filename'),urdf)
                if path.suffix.lower()=='.dae':
                    # Lidar visual only: use its supplied STL collision counterpart.
                    path=path.parents[1]/'collision/lidar.stl'
                faces=stl(path)*np.array([float(v) for v in m.get('scale','1 1 1').split()])
            elif g.find('box') is not None:
                faces=box([float(v) for v in g.find('box').get('size').split()])
            elif g.find('cylinder') is not None:
                shape=g.find('cylinder')
                faces=cylinder(float(shape.get('radius')),float(shape.get('length')))
            else: continue
            mat=visual.find('material'); color='0.4 0.4 0.4 1'
            if mat is not None:
                color=mat.find('color').get('rgba') if mat.find('color') is not None else materials.get(mat.get('name'),color)
            faces=faces@t[:3,:3].T+t[:3,3]
            yield link.get('name'), faces, np.array([float(v) for v in color.split()])
