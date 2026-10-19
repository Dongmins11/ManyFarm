"""Build an opt-in U20 wrist URDF; never replace the current D435 assembly."""
from pathlib import Path
import argparse, copy, hashlib, json, shutil, sys
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial import Delaunay
from scipy.spatial.transform import Rotation
import trimesh
from model_geometry import origin, transform
from wrist_camera_attachment import boundary_loops

PACKAGE=Path(__file__).resolve().parents[1]
ROOT=PACKAGE.parents[1]

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def numbers(a):return ' '.join(f'{v:.12g}' for v in np.asarray(a).reshape(-1))

def board_mesh(c):
    """Delaunay plate with four actual through holes, rather than dark decals."""
    half=np.asarray(c['pcb_wh_m'])/2;pitch=c['pcb_hole_pitch_m']/2;r=c['pcb_hole_diameter_m']/2
    holes=np.array([[x,y] for x in [-pitch,pitch] for y in [-pitch,pitch]])
    theta=np.arange(64)*2*np.pi/64
    points=[[-half[0],-half[1]],[-half[0],half[1]],[half[0],-half[1]],[half[0],half[1]]]
    for center in holes:points.extend(center+np.c_[np.cos(theta),np.sin(theta)]*r)
    points=np.asarray(points);tri=Delaunay(points).simplices
    centers=points[tri].mean(1)
    tri=tri[(np.linalg.norm(centers[:,None]-holes[None],axis=2)>=r*.999).all(1)]
    # Ensure counter-clockwise top winding.
    v=points[tri];cross=np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0]);tri[cross<0]=tri[cross<0][:,::-1]
    vertices=np.vstack([np.c_[points,np.zeros(len(points))],np.c_[points,np.full(len(points),-c['pcb_thickness_m'])]])
    n=len(points);faces=[*tri,*((tri+n)[:,::-1])]
    edges=np.vstack([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]])
    unique,count=np.unique(np.sort(edges,axis=1),axis=0,return_counts=True)
    boundary={tuple(e) for e in unique[count==1]}
    for a,b in edges:
        if tuple(sorted([a,b])) in boundary:faces.extend([[b,a,a+n],[b,a+n,b+n]])
    mesh=trimesh.Trimesh(vertices,np.asarray(faces),process=True)
    assert mesh.is_watertight and mesh.volume>0
    return mesh

def camera_mesh(c):
    pcb=board_mesh(c);items=[pcb]
    # Lens ears follow camera +X and the aperture's long slot (mount Z).
    for size in [(c['lens_holder_ear_span_m'],c['lens_holder_ear_width_m'],c['lens_holder_height_m']),
                 (c['lens_holder_square_m'],c['lens_holder_square_m'],c['lens_holder_height_m'])]:
        m=trimesh.creation.box(size);m.apply_translation([0,0,size[2]/2]);items.append(m)
    bottom=c['lens_holder_height_m'];top=c['lens_front_height_m']
    barrel=trimesh.creation.cylinder(radius=c['lens_thread_diameter_m']/2,height=top-bottom,sections=64)
    barrel.apply_translation([0,0,(bottom+top)/2]);items.append(barrel)
    rim=trimesh.creation.cylinder(radius=c['lens_front_diameter_m']/2,height=.002,sections=64)
    rim.apply_translation([0,0,top-.001]);items.append(rim)
    # Mesh uses REP103 body axes (+X forward); optical axes are a fixed child.
    body_from_optical=transform(rpy=[-np.pi/2,0,-np.pi/2])
    mesh=trimesh.util.concatenate(items);mesh.apply_transform(body_from_optical)
    return mesh

def features(m):
    # Identify planes by normal and find real holes from mesh boundaries.
    front=np.array([np.sin(np.deg2rad(25)),np.cos(np.deg2rad(25)),0.])
    planes=[]
    for i in range(len(m.facets)):
        if abs(m.facets_normal[i]@front)>.9999 and m.facets_area[i]>700:
            loops=boundary_loops(m.triangles[m.facets[i]])
            circles=[v.mean(0) for v in loops if len(v)==36]
            cross=[v for v in loops if len(v)==12]
            if len(circles)==4 and len(cross)==1:planes.append((i,np.asarray(circles),cross[0]))
    assert len(planes)==2
    outer=min(planes,key=lambda p:p[1].mean(0)@front)
    inner=max(planes,key=lambda p:p[1].mean(0)@front)
    return front,outer,inner

def derive(c):
    mount=trimesh.load(PACKAGE/c['mount_mesh'],force='mesh')
    front,outer,inner=features(mount)
    source=np.array([[0,-8.15,10],[0,-8.15,18.1]])*.001
    # Actual old wrist STL hole centers and outer wall; no arbitrary eye aiming.
    holder=trimesh.load(PACKAGE/'meshes/so101/wrist_roll_follower_so101_v1.stl',force='mesh')
    hole_loops=[]
    tri=holder.triangles
    plane=-.0174182146758
    for loop in boundary_loops(tri[(np.abs(tri[:,:,1]-plane)<1e-7).all(1)]):
        if len(loop)==6 and np.ptp(loop,axis=0).max()<.007:hole_loops.append(loop.mean(0))
    holes=np.asarray(sorted(hole_loops,key=lambda p:p[0]));assert holes.shape==(2,3)
    outer_y=float(holder.bounds[0,1]);target=holes.copy();target[:,1]=outer_y
    R=np.array([[0.,0.,1.],[1.,0.,0.],[0.,1.,0.]])
    fit=np.eye(4);fit[:3,:3]=R;fit[:3,3]=target[0]-R@source[0]
    assert np.linalg.norm((source@R.T+fit[:3,3])-target,axis=1).max()<1e-6
    # Rear PCB front is just behind the original outer plate; lens goes THROUGH.
    optical_R=np.column_stack(([0,0,1],np.cross(front,[0,0,1]),front))
    camera_optical_mount=np.eye(4);camera_optical_mount[:3,:3]=optical_R
    camera_optical_mount[:3,3]=outer[1].mean(0)*.001-front*c['pcb_front_gap_m']
    body_from_optical=transform(rpy=[-np.pi/2,0,-np.pi/2])
    camera_body_mount=camera_optical_mount@np.linalg.inv(body_from_optical)
    return dict(fit=fit,camera=camera_body_mount,front=front,outer=outer,inner=inner,
                holder_holes=holes,source_holes=source,target_holes=target)

def fixed(root,name,parent,child,T):
    j=ET.SubElement(root,'joint',name=name,type='fixed')
    ET.SubElement(j,'origin',xyz=numbers(T[:3,3]),rpy=numbers(Rotation.from_matrix(T[:3,:3]).as_euler('xyz')))
    ET.SubElement(j,'parent',link=parent);ET.SubElement(j,'child',link=child)

def physical_link(root,name,file,scale,mass,rgba,mesh):
    link=ET.SubElement(root,'link',name=name)
    for kind in ['visual','collision']:
        v=ET.SubElement(link,kind)
        ET.SubElement(v,'geometry').append(ET.Element('mesh',filename='../'+file,scale=scale))
        if kind=='visual':
            mat=ET.SubElement(v,'material',name=name+'_material');ET.SubElement(mat,'color',rgba=rgba)
    inertial=ET.SubElement(link,'inertial');ET.SubElement(inertial,'origin',xyz=numbers(mesh.center_mass))
    ET.SubElement(inertial,'mass',value=str(mass))
    # Unmeasured mass; conservative bounding-box inertia, explicitly documented.
    d=mesh.extents;diag=mass*np.array([d[1]**2+d[2]**2,d[0]**2+d[2]**2,d[0]**2+d[1]**2])/12
    ET.SubElement(inertial,'inertia',ixx=str(diag[0]),iyy=str(diag[1]),izz=str(diag[2]),ixy='0',ixz='0',iyz='0')
    return link

def build(config=PACKAGE/'config/u20_wrist_v1.json'):
    c=json.loads(Path(config).read_text())
    mount=PACKAGE/c['mount_mesh'];mount.parent.mkdir(parents=True,exist_ok=True)
    if not mount.exists():
        source=ROOT/'output/u20cam_wrist_mount_20261015/SO-ARM101_camera_wrist_mount.stl'
        if digest(source)!=c['mount_sha256']:raise ValueError('Unexpected original mount STL')
        shutil.copy2(source,mount)
    if digest(mount)!=c['mount_sha256']:raise ValueError('Original mount STL changed')
    camera=camera_mesh(c);camera_path=PACKAGE/c['camera_mesh'];camera_path.parent.mkdir(parents=True,exist_ok=True);camera.export(camera_path)
    f=derive(c);source=PACKAGE/c['base_urdf'];before=digest(source)
    if before!=c['base_urdf_sha256']:raise ValueError('Base URDF changed; preserve v1 and create a new explicit variant')
    root=ET.parse(source).getroot()
    root.set('name','harvest_robot_u20_wrist_v1')
    appearance=json.loads((ROOT/'src/harvest_robot/config/arm_appearance.json').read_text())
    for material in root.findall('material'):
        if material.get('name') in appearance['materials']:
            material.find('color').set('rgba',numbers(appearance['rgba']))
    transforms={};removed=[]
    for arm in c['arms']:
        prefix=f'arm_{arm}/'
        holder_visual=next(v for v in root.find(f"link[@name='{prefix}gripper_link']").findall('visual') if 'wrist_roll_follower' in v.find('geometry/mesh').get('filename',''))
        T=origin(holder_visual.find('origin'))@f['fit'];transforms[str(arm)]=T.tolist()
        names={e.get('name') for e in root.findall('link') if e.get('name').startswith(prefix+'wrist_camera')}
        for e in list(root):
            if (e.tag=='link' and e.get('name') in names) or (e.tag=='joint' and (e.find('child').get('link') in names or e.find('parent').get('link') in names)):
                removed.append(e.get('name'));root.remove(e)
        mount_name=prefix+'wrist_camera_mount_link';camera_name=prefix+'wrist_camera_link'
        m=trimesh.load(mount,force='mesh');m.apply_scale(.001)
        physical_link(root,mount_name,c['mount_mesh'],'0.001 0.001 0.001',c['mount_mass_kg'],numbers(c['mount_rgba']),m)
        fixed(root,prefix+'wrist_camera_mount_joint',prefix+'gripper_link',mount_name,T)
        physical_link(root,camera_name,c['camera_mesh'],'1 1 1',c['camera_mass_kg'],numbers(c['camera_rgba']),camera)
        # Small front glass visual makes the actual lens face recognisable.
        v=ET.SubElement(root.find(f"link[@name='{camera_name}']"),'visual')
        ET.SubElement(v,'origin',xyz=f"{c['lens_front_height_m']+.00015} 0 0",rpy=f'0 {np.pi/2} 0')
        ET.SubElement(v,'geometry').append(ET.Element('cylinder',radius='.0052',length='.0002'))
        mat=ET.SubElement(v,'material',name='u20_lens_glass');ET.SubElement(mat,'color',rgba='.06 .19 .23 1')
        fixed(root,prefix+'wrist_camera_joint',mount_name,camera_name,f['camera'])
        optical=prefix+'wrist_camera_color_optical_frame';ET.SubElement(root,'link',name=optical)
        fixed(root,prefix+'wrist_camera_color_optical_joint',camera_name,optical,
              transform([c['optical_origin_height_m'],0,0],[-np.pi/2,0,-np.pi/2]))
    output=PACKAGE/c['output_urdf'];ET.indent(root);ET.ElementTree(root).write(output,encoding='utf-8',xml_declaration=True)
    assert digest(source)==before
    report=dict(version=c['version'],source_urdf=str(source.relative_to(ROOT)),source_sha256=before,
        urdf=str(output.relative_to(ROOT)),urdf_sha256=digest(output),mount_sha256=digest(mount),camera_sha256=digest(camera_path),
        mount_pose_gripper=transforms,camera_pose_mount=f['camera'].tolist(),
        mounting_hole_axes_holder_m=f['target_holes'].tolist(),
        registration_boss_axis_holder_m=(f['fit']@np.r_[np.array([2,-18.4,6.3])*.001,1])[:3].tolist(),
        registration_boss_length_m=.002,registration_boss_radius_m=.0017,
        camera_hole_centres_mount_m=(f['outer'][1]*.001).tolist(),
        aperture_thickness_m=float((f['inner'][1].mean(0)-f['outer'][1].mean(0))@f['front']*.001),
        arms=c['arms'],mount_rgba=c['mount_rgba'],camera_rgba=c['camera_rgba'],
        pcb_on_rear_face=True,lens_through_cross_aperture=True,removed_camera_items=removed,
        calibration_verified=False,estimated_dimensions=c['estimated_not_real_calibration'])
    (PACKAGE/'config/u20_wrist_v1_attachment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=PACKAGE/'config/u20_wrist_v1.json');build(p.parse_args().config)
