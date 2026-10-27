"""同じ描画フレームのRGB/光軸Depthを共有メモリへ出力します。"""
import math
import time
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
        self.active=True
        self.activity_sequence=-1
        self.activity_deadline=-math.inf
        self.activity_requested=False

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
        self.update_activity()

    def accept_activity(self, message: dict, now: float | None = None) -> bool:
        """영상 구독 요구는 현재 세션에서만 수락하고 2초 후 자동 만료한다."""
        now=time.monotonic() if now is None else now
        if not self.config.get('on_demand',False):return False
        if message.get('kind')!='camera_activity' or message.get('session')!=self.session:return False
        seq,sent,active=message.get('seq'),message.get('sent'),message.get('active')
        if type(seq) is not int or seq<=self.activity_sequence or type(active) is not bool:return False
        if type(sent) not in (float,int) or not math.isfinite(sent) or not 0<=now-sent<=2.:return False
        self.activity_sequence,self.activity_deadline,self.activity_requested=seq,sent+2.,active
        return True

    def update_activity(self, now: float | None = None) -> None:
        """구독 종료/어댑터 유실 시 RGB 발행뿐 아니라 Hydra 렌더도 중단한다."""
        now=time.monotonic() if now is None else now
        active=(not self.config.get('on_demand',False)
                or (self.activity_requested and now<=self.activity_deadline))
        if active==self.active:return
        # 재개 직후 이전 렌더 프레임을 새 영상으로 발행하지 않는다.
        stamp=float(self.camera.get_current_frame().get('rendering_time',0.))
        if math.isfinite(stamp):self.last_stamp=max(self.last_stamp,stamp)
        (self.camera.resume if active else self.camera.pause)()
        self.camera._render_product.hydra_texture.set_updates_enabled(active)
        self.active=active
        print('[camera_activity] '+self.config['shm_name']+' active='+str(active),flush=True)

    def publish(self,pose_history,tolerance):
        if not self.active:return False
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
