"""Measured Student optical rig. Import only after Isaac AppLauncher.

IR branches are visible-light luminance at distinct factory optical poses.
This is explicitly a geometric approximation, not a simulated IR camera.
"""
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from isaaclab.sensors import Camera, CameraCfg
import isaaclab.sim as sim_utils
from harvest_rl.rgbd_geometry import valid_depth, align_depth_to_color
from .profile import validate, optical_poses, matrix, centred_render_spec, remap_render, AcquisitionGate


class StudentD435Rig:
    def __init__(self, kin, config, world_from_robot=None):
        self.config = validate(config)
        self.cameras = {}; self.local = {}; self.fixed_world = {}; self.gates = {}; self._last = {}
        zero=np.zeros(6); transforms=optical_poses(kin,zero,config,world_from_robot)
        wrist=kin.fk(zero,'arm_2/gripper_link')
        robot=np.eye(4) if world_from_robot is None else np.asarray(world_from_robot)
        wrist=robot@wrist
        for name,view in config['views'].items():
            self.cameras[name]={}; self.local[name]={}; self.fixed_world[name]={}
            rates={spec['fps'] for spec in view['streams'].values()}
            if len(rates)!=1: raise ValueError('This rig requires one acquisition rate per view')
            self.gates[name]=AcquisitionGate(next(iter(rates)))
            for stream,spec in view['streams'].items():
                optical=transforms[name][stream]
                self.local[name][stream]=np.linalg.inv(wrist)@optical
                self.fixed_world[name][stream]=optical
                w,h,k,_,_=centred_render_spec(spec)
                spawn=sim_utils.PinholeCameraCfg.from_intrinsic_matrix(
                    intrinsic_matrix=k.reshape(-1).tolist(),width=w,height=h,
                    clipping_range=(config['render_near_m'],config['render_far_m']))
                quat=Rotation.from_matrix(optical[:3,:3]).as_quat()[[3,0,1,2]]
                self.cameras[name][stream]=Camera(CameraCfg(
                    prim_path=f'/World/StudentD435_{name}_{stream}', update_period=0.,
                    update_latest_camera_pose=True, height=h,width=w,
                    data_types=['distance_to_image_plane'] if stream=='depth' else ['rgb'],
                    spawn=spawn,offset=CameraCfg.OffsetCfg(pos=tuple(optical[:3,3]),rot=tuple(quat),convention='ros')))

    def follow_wrist(self, position_w, quat_wxyz):
        def cpu(x): return x.detach().cpu().numpy() if hasattr(x,'detach') else np.asarray(x)
        wrist=np.eye(4); wrist[:3,3]=cpu(position_w)
        wrist[:3,:3]=Rotation.from_quat(cpu(quat_wxyz)[[1,2,3,0]]).as_matrix()
        for name,pair in self.cameras.items():
            for stream,camera in pair.items():
                world=wrist@self.local[name][stream] if name=='right' else self.fixed_world[name][stream]
                quat=Rotation.from_matrix(world[:3,:3]).as_quat()[[3,0,1,2]]
                camera.set_world_poses(torch.tensor(world[None,:3,3],device=camera.device,dtype=torch.float32),
                    torch.tensor(quat[None],device=camera.device,dtype=torch.float32),convention='ros')

    def update(self, dt):
        for name,pair in self.cameras.items():
            if self.gates[name].update(dt):
                for camera in pair.values(): camera.update(dt,force_recompute=True)
                self._last[name]=self._capture_view(name)

    def _capture_view(self, name):
        view=self.config['views'][name]; poses={}; ks={}; images={}; checks={}
        for stream,camera in self.cameras[name].items():
            data=camera.data; spec=view['streams'][stream]
            w,h,expected,_,_=centred_render_spec(spec)
            actual=data.intrinsic_matrices[0].cpu().numpy()
            if not np.allclose(actual,expected,atol=1e-3):
                raise ValueError(f'Isaac renderer K changed for {name}/{stream}; remap assumptions no longer valid')
            checks[stream]=dict(render_wh=[w,h],render_k=actual.tolist(),native_k=matrix(spec).tolist())
            t=np.eye(4); t[:3,3]=data.pos_w[0].cpu().numpy()
            t[:3,:3]=Rotation.from_quat(data.quat_w_ros[0].cpu().numpy()[[1,2,3,0]]).as_matrix()
            poses[stream]=t; ks[stream]=matrix(spec)
            if stream=='depth':
                array=data.output['distance_to_image_plane'][0,...,0].cpu().numpy()
                images[stream]=remap_render(array,spec,depth=True)
            else:
                array=data.output['rgb'][0,...,:3].cpu().numpy().astype(np.uint8)
                images[stream]=remap_render(array,spec)
                if stream.startswith('ir_'):
                    images[stream]=np.rint(images[stream].astype(float) @ [.299,.587,.114]).astype(np.uint8)
        raw=images['depth']; depth,mask=valid_depth(raw,self.config['depth_min_m'],self.config['depth_max_m'])
        relative=np.linalg.inv(poses['rgb'])@poses['depth']
        aligned=align_depth_to_color(depth,ks['depth'],ks['rgb'],relative,images['rgb'].shape[:2])
        return dict(rgb=images['rgb'],ir={s:images[s] for s in images if s.startswith('ir_')},
                    raw_depth_m=raw,depth_m=depth,depth_valid=mask,aligned_depth_m=aligned,
                    world_from_optical=poses,intrinsics=ks,color_from_depth=relative,
                    renderer_checks=checks,ir_model=self.config['sim_ir_model'],
                    internal_calibration_verified=view['internal_calibration_verified'],
                    mount_calibration_verified=view['mount_calibration_verified'])

    def capture(self):
        if len(self._last)!=len(self.cameras): raise RuntimeError('Call update before capture')
        return {name:dict(data, acquisition_sequence=self.gates[name].sequence,
                         acquisition_time_s=self.gates[name].last, image_age_s=self.gates[name].age,
                         clock_id='simulation', acquisition_hz=1/self.gates[name].period)
                for name,data in self._last.items()}
