"""Two physical D435 poses with separate RGB/native-depth optical sensors.

Import after AppLauncher. Pinhole geometry only, not an IR stereo simulator.
"""
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from isaaclab.sensors import Camera, CameraCfg
import isaaclab.sim as sim_utils
from .rgbd_geometry import intrinsics, valid_depth, align_depth_to_color


class DualD435Rig:
    def __new__(cls, kin, config, world_from_robot=None):
        if config.get('schema') == 'd435_deployment_v2':
            from harvest_sensors.deployment_rig import DeploymentD435Rig
            return DeploymentD435Rig(kin, config, world_from_robot)
        return super().__new__(cls)

    def __init__(self, kin, config, world_from_robot=None):
        self.config=config
        world_from_robot=np.eye(4) if world_from_robot is None else np.asarray(world_from_robot)
        self.cameras={}
        self.local={}
        self.fixed_world={}
        zero=np.zeros(6)
        for name,prefix,reference in (
                ('right','arm_2/wrist_camera',kin.fk(zero,'arm_2/gripper_link')),
                ('rear','top_camera',np.eye(4))):
            self.cameras[name]={}
            self.local[name]={}
            self.fixed_world[name]={}
            for stream,frame in (('rgb','color'),('depth','depth')):
                spec=config[stream]
                k=intrinsics(spec['width'],spec['height'],spec['horizontal_fov_deg'])
                optical=kin.fk(zero,f'{prefix}_{frame}_optical_frame')
                local=np.linalg.inv(reference)@optical
                self.local[name][stream]=local
                optical=world_from_robot@optical
                self.fixed_world[name][stream]=optical
                q=Rotation.from_matrix(optical[:3,:3]).as_quat()[[3,0,1,2]]
                spawn=sim_utils.PinholeCameraCfg.from_intrinsic_matrix(
                    intrinsic_matrix=k.reshape(-1).tolist(),width=spec['width'],height=spec['height'],
                    clipping_range=(config['render_near_m'],config['render_far_m']))
                self.cameras[name][stream]=Camera(CameraCfg(
                    prim_path=f'/World/D435_{name}_{stream}',update_period=1/config['fps'],update_latest_camera_pose=True,
                    height=spec['height'],width=spec['width'],
                    data_types=['rgb'] if stream=='rgb' else ['distance_to_image_plane'],
                    spawn=spawn,offset=CameraCfg.OffsetCfg(pos=tuple(optical[:3,3]),rot=tuple(q),convention='ros')))

    def follow_wrist(self, position_w, quat_wxyz):
        # A world-root sensor avoids stale nested camera transforms after a
        # PhysX/Fabric joint teleport. Use measured link pose, never a target pose.
        wrist=np.eye(4)
        wrist[:3,3]=position_w.detach().cpu().numpy()
        q=quat_wxyz.detach().cpu().numpy()
        wrist[:3,:3]=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
        for name,pair in self.cameras.items():
            for stream,camera in pair.items():
                world=wrist@self.local[name][stream] if name=='right' else self.fixed_world[name][stream]
                quat=Rotation.from_matrix(world[:3,:3]).as_quat()[[3,0,1,2]]
                camera.set_world_poses(torch.tensor(world[None,:3,3],device=camera.device,dtype=torch.float32),
                    torch.tensor(quat[None],device=camera.device,dtype=torch.float32),convention='ros')

    def update(self, dt):
        for pair in self.cameras.values():
            for camera in pair.values():camera.update(dt,force_recompute=True)

    def capture(self):
        result={}
        for name,pair in self.cameras.items():
            poses={};ks={}
            for stream,camera in pair.items():
                data=camera.data
                t=np.eye(4)
                t[:3,3]=data.pos_w[0].cpu().numpy()
                q=data.quat_w_ros[0].cpu().numpy()
                t[:3,:3]=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
                poses[stream]=t
                ks[stream]=data.intrinsic_matrices[0].cpu().numpy()
            raw=pair['depth'].data.output['distance_to_image_plane'][0,...,0].cpu().numpy()
            depth,mask=valid_depth(raw,self.config['depth_min_m'],self.config['depth_max_m'])
            rgb=pair['rgb'].data.output['rgb'][0,...,:3].cpu().numpy().astype(np.uint8)
            relative=np.linalg.inv(poses['rgb'])@poses['depth']
            aligned=align_depth_to_color(depth,ks['depth'],ks['rgb'],relative,rgb.shape[:2])
            result[name]=dict(rgb=rgb,raw_depth_m=raw,depth_m=depth,depth_valid=mask,aligned_depth_m=aligned,
                              world_from_optical=poses,intrinsics=ks,color_from_depth=relative)
        return result
