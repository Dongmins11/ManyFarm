#!/usr/bin/env python3
"""Generate portable SI-unit URDF; upstream Waffle file is never modified."""
import copy
import json
import math
from pathlib import Path
import xml.etree.ElementTree as E
P=Path(__file__).resolve().parents[1]
C=json.loads((P/'config/transport.json').read_text())
def vec(v): return ' '.join(f'{x:.10g}' for x in v)
def sub(e,tag,**kw): return E.SubElement(e,tag,{k:str(v) for k,v in kw.items()})
root=E.fromstring((P/'urdf/waffle_upstream.urdf').read_text().replace('${namespace}',''))
root.set('name','manyfarm_transport_robot')
for e in list(root):
    if '}' in e.tag or e.get('name','').startswith('camera'): root.remove(e)
for m in root.iter('mesh'): m.set('filename','package://smartfarm_description/meshes/transport/'+Path(m.get('filename')).name)
# Restore original Waffle chassis and lidar origin without altering upstream asset.
scan_z=.010+.122
for name,color in [('cargo','0.20 0.64 0.43 1'),('lid','0.84 0.91 0.87 1'),('metal','0.55 0.59 0.64 1'),('servo','0.16 0.20 0.28 1'),('gear','0.95 0.62 0.14 1')]:
    sub(sub(root,'material',name=name),'color',rgba=color)
def link(name): return sub(root,'link',name=name)
def box(l,size,xyz=(0,0,0),mat='metal',collision=True,rpy=(0,0,0)):
    for tag in ['visual']+(['collision'] if collision else []):
        v=sub(l,tag);sub(v,'origin',xyz=vec(xyz),rpy=vec(rpy));sub(sub(v,'geometry'),'box',size=vec(size))
        if tag=='visual':sub(v,'material',name=mat)
def cyl(l,r,h,xyz=(0,0,0),mat='metal',rpy=(0,math.pi/2,0),collision=True):
    for tag in ['visual']+(['collision'] if collision else []):
        v=sub(l,tag);sub(v,'origin',xyz=vec(xyz),rpy=vec(rpy));sub(sub(v,'geometry'),'cylinder',radius=r,length=h)
        if tag=='visual':sub(v,'material',name=mat)
def inertia(l,m,size,xyz=(0,0,0)):
    a,b,c=size;i=sub(l,'inertial');sub(i,'origin',xyz=vec(xyz));sub(i,'mass',value=m)
    sub(i,'inertia',ixx=m*(b*b+c*c)/12,iyy=m*(a*a+c*c)/12,izz=m*(a*a+b*b)/12,ixy=0,ixz=0,iyz=0)
def joint(name,parent,child,xyz=(0,0,0),kind='fixed',axis=(0,1,0),upper=0,mimic=None,effort=1,velocity=1):
    j=sub(root,'joint',name=name,type=kind);sub(j,'parent',link=parent);sub(j,'child',link=child);sub(j,'origin',xyz=vec(xyz))
    if kind!='fixed':
        sub(j,'axis',xyz=vec(axis));sub(j,'limit',lower=0,upper=upper,effort=effort,velocity=velocity);sub(j,'dynamics',damping=.05,friction=.01)
    if mimic:sub(j,'mimic',joint=mimic[0],multiplier=mimic[1],offset=0)
    return j
L,W,H,t=C['box_length'],C['box_width'],C['box_height'],C['wall_thickness']
z=C['box_bottom_ground'];cx=-.064
# Four posts plus bearing deck; no solid pillar through lidar.
l=link('cargo_support');joint('cargo_support_joint','base_link','cargo_support')
for x in [cx-.100,cx+.100]:
 for y in [-.100,.100]:box(l,(.016,.016,z-.006-C['support_contact_ground']),(x,y,(z-.006+C['support_contact_ground'])/2-.010))
box(l,(L,W,.006),(cx,0,z-.013));inertia(l,.65,(L,W,z-.1),(cx,0,.17))
# Local cargo origin at front lower edge: positive Y rotation raises rear.
l=link('cargo_box');joint('box_tilt_joint','base_link','cargo_box',(cx+L/2,0,z-.010),'revolute',upper=C['tilt_limit_rad'],effort=C.get('tilt_motor_reference_rated_torque_Nm',20),velocity=.25)
v3=C.get('fabrication_revision')==3
floor_z=.002 if v3 else 0
floor_t=.003 if v3 else t
wall_bottom=floor_z+floor_t
box(l,(L,W,floor_t),(-L/2,0,floor_z+floor_t/2),'cargo')
box(l,(t,W,H-wall_bottom),(-L+t/2,0,(H+wall_bottom)/2),'cargo')
for y in [-W/2+t/2,W/2-t/2]:box(l,(L-t, t,H-wall_bottom),(-(L-t)/2,y,(H+wall_bottom)/2),'cargo')
inertia(l,C.get('cargo_shell_mass_kg',1.0),(L,W,H),(-L/2,0,H/2))
# Front discharge gate: top hinge, negative Y rotation swings outward.
gate_z=H-.026 if v3 else H
if v3:box(root.find("link[@name='cargo_box']"),(t,W-2*t,.026),(-t/2,0,H-.013),'metal')
l=link('side_lid');joint('side_lid_joint','cargo_box','side_lid',(0,0,gate_z),'revolute',(0,-1,0),C['side_lid_limit_rad'])
gate_h=gate_z-wall_bottom
gate_skin_top=.018 if v3 else 0
box(l,(t,W-2*t,gate_h-gate_skin_top),(-t/2,0,-(gate_h+gate_skin_top)/2),'lid');inertia(l,C.get('side_gate_mass_kg',.18),(t,W-2*t,gate_h),(-t/2,0,-gate_h/2))
if not v3:
    l=link('side_mg996r');joint('side_mg996r_joint','cargo_box','side_mg996r',(-.020,-W/2-.015,H-.026))
    box(l,(.0407,.0197,.0429),mat='servo');inertia(l,.055,(.0407,.0197,.0429))
    l=link('tilt_motor_5840_31zy');joint('tilt_motor_mount','cargo_support','tilt_motor_5840_31zy',(cx+L/2,W/2+.035,z-.010))
    cyl(l,.020,.070,rpy=(math.pi/2,0,0),mat='servo');inertia(l,.25,(.040,.070,.040))
else:
    l=link('tilt_fixed_mounts');joint('tilt_fixed_mounts_joint','cargo_support','tilt_fixed_mounts',(cx+L/2,0,z-.010))
    for p in json.loads((P/'cad/sliding_lids/output_v3/transport_motors/parts.json').read_text()):
        n=p['name'];l=link(n)
        joint(n+'_joint','tilt_fixed_mounts' if p['parent']=='tilt_fixed' else p['parent'],n)
        for tag in ['visual','collision']:
            v=sub(l,tag);sub(sub(v,'geometry'),'mesh',filename='package://smartfarm_description/meshes/sliding_lids_v3/transport_motors/'+n+'.stl',scale='.001 .001 .001')
            if tag=='visual':sub(v,'material',name='servo' if p['material']=='hardware' else 'metal')
        inertia(l,p['mass_kg'],[x*.001 for x in p['size_mm']],p['center_m'])
# Fabrication CAD mechanism: rear mounted, carried by the tilting box.
fragment=E.parse(P/'urdf/generated/transport_lid_mechanism.urdf').getroot()
for e in fragment:root.append(copy.deepcopy(e))
root.find("joint[@name='transport_lid_mount']/origin").set('xyz',vec((-L/2,0,H+.005)))
E.indent(root)
(P/'urdf/transport_robot.urdf').write_text('<?xml version="1.0"?>\n'+E.tostring(root,encoding='unicode')+'\n')
portable=copy.deepcopy(root)
for m in portable.iter('mesh'):m.set('filename',m.get('filename').replace('package://smartfarm_description/','../'))
(P/'urdf/transport_robot.portable.urdf').write_text('<?xml version="1.0"?>\n'+E.tostring(portable,encoding='unicode')+'\n')
print(f'Generated {len(root.findall("link"))} links, {len(root.findall("joint"))} joints. LDS frame z={scan_z:.4f} m')
