"""base_scan 위치에서 PhysX 충돌체를 측정하는 순간 360도 2D LiDAR.
반사율/빔 발산/회전 중 왜곡은 아직 모델링하지 않습니다. 미검출은 None→ROS inf.
"""
import math
import numpy as np


def hit_value(hit,name,legacy):
    if hasattr(hit,name):return getattr(hit,name)
    return hit.get(legacy,'')


class LidarSim:
    def __init__(self,config,robot_path,T_base_scan):
        from omni.physx import get_physx_scene_query_interface
        self.query=get_physx_scene_query_interface()
        self.config=config
        self.robot_path=robot_path.rstrip('/')
        self.transform=T_base_scan
        self.angles=np.linspace(-math.pi,math.pi,config['samples'],endpoint=False)

    def sample(self,T_world_base):
        import carb
        transform=T_world_base@self.transform
        origin=carb.Float3(*map(float,transform[:3,3]))
        ranges=[]
        diagnostic=[]
        for angle in self.angles:
            direction=transform[:3,:3]@np.array([math.cos(angle),math.sin(angle),0.0])
            nearest=[None]
            nearest_path=['']
            def report(hit):
                collision=str(hit_value(hit,'collision','collision'))
                body=str(hit_value(hit,'rigid_body','rigidBody'))
                if any(p==self.robot_path or p.startswith(self.robot_path+'/') for p in (collision,body)):
                    return True
                d=float(hit_value(hit,'distance','distance'))
                if self.config['range_min_m']<=d<=self.config['range_max_m']:
                    if nearest[0] is None or d<nearest[0]:
                        nearest[0]=d
                        nearest_path[0]=collision
                elif 0<=d<self.config['range_min_m']:
                    nearest[0]=0.0  # minより近い遮蔽物は有効距離として使わない
                return True
            self.query.raycast_all(origin,carb.Float3(*map(float,direction)),self.config['range_max_m'],report)
            ranges.append(nearest[0])
            if self.config.get('diagnostic_front_hits') and abs(angle)<=math.radians(5.1):
                diagnostic.append(dict(angle_rad=float(angle),distance=nearest[0],collision=nearest_path[0]))
        self.front_diagnostic=dict(origin=list(map(float,origin)),hits=diagnostic)
        return ranges
