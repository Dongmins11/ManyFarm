"""Conservative camera/frame convex-hull screen for edited HOME/stow routes.

URDF collision geometry, not rendered pixels. Mount/gripper assembly interfaces
are excluded. This samples the route and does not certify continuous collision
freedom, movable left-arm clearance or real hand-eye geometry.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))


def main():
    import numpy as np
    import trimesh
    from scipy.spatial import ConvexHull
    from scipy.optimize import linprog
    from harvest_rl.kinematics import ArmKinematics,origin
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'src/harvest_robot/config/student60_mission_v1.json')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();config=json.loads(a.config.read_text());result={}
    for variant,filename in [('d435','harvest_robot.urdf'),('u20','harvest_robot_u20_wrist_v1.urdf')]:
        path=ROOT/'src/smartfarm_description/urdf'/filename;kin=ArmKinematics(path)
        meshes=[]
        for link in kin.root.findall('link'):
            name=link.get('name')
            if name.startswith('arm_1/') or name in ('arm_2/gripper_link','arm_2/wrist_link','arm_2/moving_jaw_so101_v1_link'):
                continue
            for i,node in enumerate(link.findall('collision')):
                geometry=list(node.find('geometry'))[0]
                if geometry.tag=='mesh':
                    file=geometry.get('filename')
                    file=ROOT/'src/smartfarm_description'/file.split('package://smartfarm_description/',1)[1] if file.startswith('package://smartfarm_description/') else path.parent/file
                    mesh=trimesh.load(file,force='mesh',process=False)
                    mesh.apply_scale(np.fromstring(geometry.get('scale','1 1 1'),sep=' '))
                elif geometry.tag=='box':mesh=trimesh.creation.box(np.fromstring(geometry.get('size'),sep=' '))
                elif geometry.tag=='cylinder':mesh=trimesh.creation.cylinder(float(geometry.get('radius')),float(geometry.get('length')),sections=16)
                elif geometry.tag=='sphere':mesh=trimesh.creation.icosphere(subdivisions=1,radius=float(geometry.get('radius')))
                else:raise ValueError(geometry.tag)
                mesh.apply_transform(origin(node.find('origin')))
                hull=mesh.convex_hull
                meshes.append((name,i,np.asarray(hull.vertices)))
        poses=[config['home_rad']]+config['home_to_stow_via_rad']+[config['stow_rad']]
        route=[]
        for start,end in zip(poses,poses[1:]):
            count=max(2,int(np.ceil(np.max(abs(np.asarray(end)-start))/.025))+1)
            route.extend(np.linspace(start,end,count))
        overlaps=[];checks=0
        for step,q in enumerate(route):
            world=[]
            for name,i,vertices in meshes:
                matrix=kin.fk(q,name);v=vertices@matrix[:3,:3].T+matrix[:3,3]
                world.append((name,i,v,np.array([v.min(0),v.max(0)])))
            cameras=[row for row in world if row[0] in ('arm_2/wrist_camera_link','arm_2/wrist_camera_mount_link')]
            for camera in cameras:
                for obstacle in world:
                    if obstacle[0] in ('arm_2/wrist_camera_link','arm_2/wrist_camera_mount_link'):continue
                    if np.any(camera[3][0]>obstacle[3][1]) or np.any(obstacle[3][0]>camera[3][1]):continue
                    equations=np.vstack((ConvexHull(camera[2]).equations,ConvexHull(obstacle[2]).equations))
                    solved=linprog([0.,0.,0.],A_ub=equations[:,:3],b_ub=-equations[:,3],bounds=[(None,None)]*3,method='highs')
                    checks+=1
                    if solved.success:overlaps.append(dict(sample=step,camera=camera[0],obstacle=obstacle[0],collision_index=obstacle[1]))
        result[variant]=dict(sampled_poses=len(route),narrow_checks=checks,convex_overlaps=overlaps,
            sampled_camera_frame_screen_passed=not overlaps,
            excludes=['mounted gripper/wrist interfaces','moving jaw interface','left-arm moving links'],
            continuous_collision_or_hardware_certificate=False)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
