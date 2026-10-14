"""同じ描画フレームのRGB/光軸Depthを共有メモリへ出力します。"""
import math
import numpy as np
from farm_common.rgbd_shm import RgbdWriter


class CameraSim:
    def __init__(self,prim_path,config,session,optical_frame,T_base_optical):
        from isaacsim.sensors.camera import Camera
        self.config=config
        self.camera=Camera(prim_path=prim_path,name=config['shm_name'],frequency=config['fps'],
                           resolution=(config['width'],config['height']))
        self.session,self.optical_frame=session,optical_frame
        self.T_base_optical=T_base_optical
        self.last_stamp=-1.0
        self.writer=None

    def initialize(self):
        self.camera.initialize()
        calibration = self.config.get('camera_info')
        if calibration:
            k = calibration['k']
            # Isaac 5.1 OpenCV 렌즈 모델로 K와 실제 왜곡 D를 함께 재현합니다.
            self.camera.set_opencv_pinhole_properties(
                cx=k[2], cy=k[5], fx=k[0], fy=k[4], pinhole=calibration['d'])
        if not self.config.get('render_rgb_only', False):
            self.camera.add_distance_to_image_plane_to_frame()
        self.writer=RgbdWriter(self.config['shm_name'],self.config['width'],self.config['height'])

    def publish(self,pose_history,tolerance):
        frame=self.camera.get_current_frame()
        stamp=float(frame.get('rendering_time',0.0))
        if not math.isfinite(stamp) or stamp<=self.last_stamp:return False
        rgb=frame.get('rgb')
        depth=frame.get('distance_to_image_plane')
        rgb_only=self.config.get('render_rgb_only',False)
        if rgb_only:
            # writer가 기존 RGB-D 규격의 NaN 영역을 재사용한다.
            depth=None
        if rgb is None or (depth is None and not rgb_only):return False
        rgb=np.asarray(rgb)
        h,w=self.config['height'],self.config['width']
        if rgb.ndim!=3 or rgb.shape[:2]!=(h,w) or rgb.shape[2]<3:return False
        if not rgb_only and np.shape(depth)!=(h,w):return False
        if not pose_history:return False
        sample=min(pose_history,key=lambda p:abs(p[0]-stamp))
        if abs(sample[0]-stamp)>tolerance:return False  # 현재 시각으로 대체하지 않음
        x,y,yaw=sample[1][:3]
        c,s=math.cos(yaw),math.sin(yaw)
        T_odom_base=np.array([[c,-s,0,x],[s,c,0,y],[0,0,1,0],[0,0,0,1]],dtype=float)
        if not rgb_only:
            depth=np.array(depth,dtype=np.float32,copy=True)
            valid=np.isfinite(depth)&(depth>=self.config['depth_min_m'])&(depth<=self.config['depth_max_m'])
            depth[~valid]=np.nan
        meta=dict(session=self.session,stamp_ns=round(stamp*1e9),frame_id=self.optical_frame,
                  pose_stamp_ns=round(sample[0]*1e9),pose_frame=self.config['odom_frame'],
                  T_odom_camera_optical=(T_odom_base@self.T_base_optical).tolist(),
                  K=(np.asarray(self.config['camera_info']['k']).reshape(3,3).tolist()
                     if 'camera_info' in self.config else np.asarray(self.camera.get_intrinsics_matrix()).tolist()),
                  aligned_depth=not rgb_only,depth_definition='unavailable' if rgb_only else 'distance_to_image_plane',
                  note='map 변환은 촬영 시각의 map->odom TF를 사용하는 소비자 책임')
        done=self.writer.write(rgb[:,:,:3],depth,meta)
        self.last_stamp=stamp
        return done

    def close(self):
        self.camera.pause()
        if self.writer:self.writer.close()
