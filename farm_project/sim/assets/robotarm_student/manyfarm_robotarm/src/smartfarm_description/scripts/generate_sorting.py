#!/usr/bin/env python3
"""Deterministic foam-board station generator. SI units, no third-party meshes."""
import copy
import json
import math
from pathlib import Path
import xml.etree.ElementTree as E

from import_omx import build_generated_urdf

P=Path(__file__).resolve().parents[1]
C=json.loads((P/'config/sorting.json').read_text())
R=E.Element('robot',name='manyfarm_sorting_station')
def sub(e,tag,**kw):return E.SubElement(e,tag,{k:str(v) for k,v in kw.items()})
def vec(v):return ' '.join(f'{x:.12g}' for x in v)
sub(R,'link',name='sorting_station')
for name,color in [('foam','0.94 0.945 0.925 1'),('edge','0.85 0.86 0.83 1'),('pedestal','0.76 0.79 0.81 1')]:
 sub(sub(R,'material',name=name),'color',rgba=color)
t=C['board_thickness'];rho=C['foam_density_kg_m3']
def fixed(name,parent='sorting_station',xyz=(0,0,0),rpy=(0,0,0)):
 l=sub(R,'link',name=name);j=sub(R,'joint',name=name+'_joint',type='fixed')
 sub(j,'parent',link=parent);sub(j,'child',link=name);sub(j,'origin',xyz=vec(xyz),rpy=vec(rpy));return l
def inertial(l,size,mass=None):
 a,b,c=size;m=mass if mass is not None else a*b*c*rho
 i=sub(l,'inertial');sub(i,'mass',value=m)
 sub(i,'inertia',ixx=m*(b*b+c*c)/12,iyy=m*(a*a+c*c)/12,izz=m*(a*a+b*b)/12,ixy=0,ixz=0,iyz=0)
def panel(name,size,xyz, rpy=(0,0,0),mat='foam'):
 l=fixed(name,xyz=xyz,rpy=rpy)
 for tag in ['visual','collision']:
  g=sub(l,tag);sub(sub(g,'geometry'),'box',size=vec(size))
  if tag=='visual':sub(g,'material',name=mat)
 inertial(l,size);return l

def convex_panel(name,vertices,faces):
 """Closed convex prism STL. Orient normals outward; inertia is documented bbox estimate."""
 center=[sum(v[k] for v in vertices)/len(vertices) for k in range(3)]
 verts=[[v[k]-center[k] for k in range(3)] for v in vertices]
 out=['solid '+name]
 for face in faces:
  for n in range(1,len(face)-1):
   tri=[verts[i] for i in [face[0],face[n],face[n+1]]]
   a=[tri[1][k]-tri[0][k] for k in range(3)];b=[tri[2][k]-tri[0][k] for k in range(3)]
   normal=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
   if sum(normal[k]*sum(v[k] for v in tri)/3 for k in range(3))<0:
    tri[1],tri[2]=tri[2],tri[1];normal=[-x for x in normal]
   norm=math.sqrt(sum(x*x for x in normal));assert norm>1e-14
   out.append('facet normal '+vec([x/norm for x in normal]));out.append('outer loop')
   out.extend('vertex '+vec(v) for v in tri);out.extend(['endloop','endfacet'])
 out.append('endsolid '+name);(P/'meshes/sorting'/f'{name}.stl').write_text('\n'.join(out)+'\n')
 l=fixed(name,xyz=center)
 for tag in ['visual','collision']:
  g=sub(l,tag);sub(sub(g,'geometry'),'mesh',filename=f'package://smartfarm_description/meshes/sorting/{name}.stl')
  if tag=='visual':sub(g,'material',name='foam')
 size=[max(v[k] for v in verts)-min(v[k] for v in verts) for k in range(3)]
 inertial(l,size)

def prism_xy(name,poly,z0,z1):
 n=len(poly);v=[(x,y,z) for z in [z0,z1] for x,y in poly]
 faces=[list(range(n)),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
 convex_panel(name,v,faces)
def side_prism(name,poly,y):
 n=len(poly);v=[(x,yy,z) for yy in [y-t/2,y+t/2] for x,z in poly]
 faces=[list(range(n)),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
 convex_panel(name,v,faces)

# Intake floor is a horizontal trapezoid, not a funnel slope.
w=C['intake_wide_width'];d=C['intake_depth'];narrow=w-2*d*math.tan(math.radians(C['intake_taper_deg']))
assert narrow>2*t
poly=[(0,-w/2),(0,w/2),(-d,narrow/2),(-d,-narrow/2)]
prism_xy('intake_floor',poly,C['intake_floor_top']-t,C['intake_floor_top'])
# Side walls extend down to ground, matching real foam-board base skirt.
# Wall centers lie inward by half-thickness: specified widths are outer bounds.
for k,(a,b) in enumerate(zip(poly,poly[1:]+poly[:1])):
 dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
 inward=(-dy/length,dx/length)
 panel('intake_wall_'+str(k),(length,t,C['intake_total_height']),
       ((a[0]+b[0])/2+inward[0]*t/2,(a[1]+b[1])/2+inward[1]*t/2,C['intake_total_height']/2),
       (0,0,math.atan2(dy,dx)))

W=C['sorter_width'];lw=C['lane_outer_width'];run=C['ramp_horizontal_run'];z0=C['ramp_start_top'];z1=C['storage_floor_top'];S=C['storage_length']
angle=math.atan2(z0-z1,run);length=math.hypot(run,z0-z1)
# Offset center along negative surface normal so the top endpoints are exact.
for sign,label in [(1,'left'),(-1,'right')]:
 cy=sign*(W-lw)/2
 panel(label+'_ramp',(length,lw-2*t,t),
       (run/2-t*math.sin(angle)/2,cy,(z0+z1)/2-t*math.cos(angle)/2),(0,angle,0))
 for suffix,y in [('outer',sign*(W/2-t/2)),('inner',sign*(W/2-lw+t/2))]:
  depth=C['inlet_tower_depth'];zt=C['inlet_tower_top'];h=C['ramp_guard_height']
  # Split a non-convex side silhouette into convex panels for collision import.
  panel(label+'_'+suffix+'_tower',(depth,t,zt),(depth/2,y,zt/2))
  zend=z0+(z1-z0)*depth/run+h
  side_prism(label+'_'+suffix+'_slope_wall',[(depth,0),(run,0),(run,z1+h),(depth,zend)],y)
 panel(label+'_inlet_crossbar',(t,lw-2*t,C['inlet_crossbar_height']),
       (C['inlet_tower_depth']-t/2,cy,C['inlet_tower_top']-C['inlet_crossbar_height']/2))
 # Floors widen to full storage half-width. No wall at ramp exit.
 sy=sign*W/4
 panel(label+'_storage_floor',(S,W/2,t),(run+S/2,sy,z1-t/2))
 fixed(label+'_drop_frame',xyz=(.045,cy,z0+.08))
 fixed(label+'_storage_frame',xyz=(run+S/2,sy,z1))
h=C['storage_wall_height']
for label,y in [('left',W/2-t/2),('right',-W/2+t/2),('divider',0)]:
 panel('storage_'+label+'_wall',(S,t,h),(run+S/2,y,z1+h/2))
panel('storage_end_wall',(t,W,h),(run+S-t/2,0,z1+h/2))
# Close the central bin rear boundary only, preserve both chute outlets.
panel('storage_center_rear_wall',(t,W-2*lw,h),(run+t/2,0,z1+h/2))
if C['include_omx_pedestal']:
 pd,pw,ph=C['omx_pedestal_depth'],C['omx_pedestal_width'],C['omx_pedestal_height']
 assert pw<W-2*lw
 # Thin board box, with open bottom. Locate between the two inlet lanes.
 panel('omx_pedestal_top',(pd,pw,t),(pd/2,0,ph-t/2),mat='pedestal')
 for label,x in [('rear',t/2),('front',pd-t/2)]:panel('omx_pedestal_'+label,(t,pw,ph-t),(x,0,(ph-t)/2),mat='pedestal')
 for label,y in [('left',(pw-t)/2),('right',-(pw-t)/2)]:panel('omx_pedestal_'+label,(pd-2*t,t,ph-t),(pd/2,y,(ph-t)/2),mat='pedestal')
 fixed('omx_mount_frame',xyz=(pd/2,0,ph))
fixed('intake_pick_frame',xyz=(-d/2,0,C['intake_floor_top']))

# Fixed overhead RealSense D435. User measurements reference the housing BACK
# surface: 0.710 m above the intake floor and 0.058 m into the intake from the
# rear wall x=0. Camera local +X is its viewing direction, rotated to world -Z.
if C.get('include_sorting_camera',False):
    s=C['sorting_camera_body_size'];m=C['sorting_camera_mass']
    back_z=C['intake_floor_top']+C['sorting_camera_back_height_above_intake_floor']
    camera_xyz=(-C['sorting_camera_rear_wall_offset'],C['sorting_camera_y'],back_z-s[0]/2)
    camera_rpy=tuple(C['sorting_camera_rpy'])
    l=fixed('sorting_camera_link',xyz=camera_xyz,rpy=camera_rpy)
    vis=sub(l,'visual');sub(sub(vis,'geometry'),'box',size=vec(s))
    mat=sub(vis,'material',name='sorting_camera_aluminum');sub(mat,'color',rgba='0.75 0.78 0.81 1')
    glass=sub(l,'visual');sub(glass,'origin',xyz=vec((s[0]/2,0,0)))
    sub(sub(glass,'geometry'),'box',size=vec((0.001,0.083,0.020)))
    gmat=sub(glass,'material',name='sorting_camera_glass');sub(gmat,'color',rgba='0.025 0.03 0.04 1')
    col=sub(l,'collision');sub(sub(col,'geometry'),'box',size=vec((s[0]+.002,s[1],s[2])))
    inertial(l,s,m)
    fixed('sorting_camera_back_reference',parent='sorting_camera_link',xyz=(-s[0]/2,0,0))
    fixed('sorting_camera_depth_frame',parent='sorting_camera_link',xyz=(s[0]/2-.0043,.0175,0))
    fixed('sorting_camera_color_frame',parent='sorting_camera_depth_frame',xyz=(0,.015,0))
    fixed('sorting_camera_depth_optical_frame',parent='sorting_camera_depth_frame',rpy=(-math.pi/2,0,-math.pi/2))
    fixed('sorting_camera_color_optical_frame',parent='sorting_camera_color_frame',rpy=(-math.pi/2,0,-math.pi/2))

# Official ROBOTIS OMX-F follower chain, mounted toward the intake (-X).
if C['include_omx_pedestal']:
    arm=E.parse(build_generated_urdf()).getroot()
    for element in arm:
        if element.tag in ('link','joint','material'):
            R.append(copy.deepcopy(element))

    # OMX wrist RGB camera. ROBOTIS' OMX-AI page points to the InnoMaker
    # U20CAM-720P as the compatible camera. The camera is not bundled with OMX,
    # and ROBOTIS does not define a canonical mount extrinsic, so xyz/rpy remain
    # explicit configuration values measured from omx_link5.
    if C.get('include_omx_wrist_camera',False):
        s=C['omx_wrist_camera_board_size']
        cam=fixed('omx_wrist_camera_link',parent='omx_link5',
                  xyz=tuple(C['omx_wrist_camera_xyz']),
                  rpy=tuple(C['omx_wrist_camera_rpy']))
        board=sub(cam,'visual')
        sub(sub(board,'geometry'),'box',size=vec(s))
        bmat=sub(board,'material',name='u20cam_pcb');sub(bmat,'color',rgba='0.08 0.11 0.09 1')
        lens=sub(cam,'visual');sub(lens,'origin',xyz=vec((0.007,0,0)),rpy=vec((0,math.pi/2,0)))
        sub(sub(lens,'geometry'),'cylinder',radius='0.006',length='0.012')
        lmat=sub(lens,'material',name='u20cam_lens');sub(lmat,'color',rgba='0.03 0.03 0.03 1')
        fixed('omx_wrist_camera_optical_frame',parent='omx_wrist_camera_link',
              xyz=tuple(C['omx_wrist_camera_optical_xyz']),
              rpy=(-math.pi/2,0,-math.pi/2))

    j=sub(R,'joint',name='omx_mount_joint',type='fixed')
    sub(j,'parent',link='omx_mount_frame');sub(j,'child',link='omx_link0')
    sub(j,'origin',xyz=vec((0,0,C['omx_base_bottom_offset'])),rpy=vec((0,0,math.pi)))

E.indent(R)
(P/'urdf/sorting_station.urdf').write_text('<?xml version="1.0"?>\n'+E.tostring(R,encoding='unicode')+'\n')
portable=copy.deepcopy(R)
for mesh in portable.iter('mesh'):mesh.set('filename',mesh.get('filename').replace('package://smartfarm_description/','../'))
(P/'urdf/sorting_station.portable.urdf').write_text('<?xml version="1.0"?>\n'+E.tostring(portable,encoding='unicode')+'\n')
print(f'Generated {len(R.findall("link"))} links. Intake narrow width={narrow:.6f} m; ramp={math.degrees(angle):.4f} degrees.')
