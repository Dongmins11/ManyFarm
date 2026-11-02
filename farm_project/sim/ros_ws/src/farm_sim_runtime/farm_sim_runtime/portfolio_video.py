"""실제 시험을 외부 카메라로 촬영한다. 영상 시각은 시뮬레이션 시각이다."""
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .portfolio_capture import PortfolioCapture


def frame_count(elapsed: float, fps: int, duration: float) -> int:
    """첫 표본을 0초에 둔다. 느린 벽시계가 영상 재생 길이에 영향을 주지 않는다."""
    return min(round(duration*fps), max(0, math.floor((elapsed+1e-7)*fps)+1))


class PortfolioVideo(PortfolioCapture):
    def __init__(self, output: Path, session: str, config: dict) -> None:
        super().__init__(output, session)
        self.config = config
        self.fps = int(config.get('fps', 15))
        self.duration = float(config.get('duration_sim_s', 30))
        self.resolution = tuple(config.get('resolution', [1920, 1080]))
        if self.fps not in (10, 15, 30) or not 10 <= self.duration <= 60:
            raise ValueError('촬영 fps/길이 설정 오류')
        self.counts = {}; self.last = {}; self.clip = None
        self.source_camera = None
        # 재시도에서도 같은 각도만 반복하지 않는다. 선택 결과는 클립에 기록한다.
        self.view_seed = int(output.parent.name.rsplit('_',1)[-1])-1 if output.parent.name.startswith('attempt_') else 0
        self.output.joinpath('capture_config.json').write_text(json.dumps(config, indent=2)+'\n')

    def candidates(self, robots: list, sorter: object, monitor: object) -> dict:
        values = super().candidates(robots, sorter, monitor)
        values.pop('handoff', None)
        by_id = {r['cfg']['robot_id']: r for r in robots}
        h,t = by_id.get('harvest_01'), by_id.get('transport_01')
        if h is not None and t is not None:
            distance = np.linalg.norm(h['T_world_base'][:2,3]-t['T_world_base'][:2,3])
            moving = max(abs(v) for v in t.get('applied_cmd', (0,0))) > .015
            if distance < 2.2 and (moving or (monitor and monitor.latest and monitor.latest.get('hold_pass'))):
                values['docking'] = dict(transform=h['T_world_base'].tolist(),
                    transport_transform=t['T_world_base'].tolist(), distance_m=float(distance),
                    alignment=monitor.latest if monitor else None,
                    meaning='live approach/docking; cargo transfer uses the existing virtual mechanism')
        for rid, r in by_id.items():
            if max(abs(v) for v in r.get('applied_cmd', (0,0))) > .025:
                values['travel_'+rid] = dict(transform=r['T_world_base'].tolist(),
                    command=list(r['applied_cmd']), robot_id=rid)
                sensor=r.get('tag_camera')
                if sensor is not None and sensor.active:
                    values['apriltag_'+rid] = dict(transform=r['T_world_base'].tolist(),robot_id=rid,
                        frame_id=sensor.optical_frame,camera_config=sensor.config,
                        meaning='original AprilTag sensor RGB; native intrinsics and resolution')
        return values

    def view_mode(self, kind: str, index: int) -> str:
        if kind.startswith('apriltag_'):return 'sensor_original'
        modes=(['fixed_route_wide','low_oblique','fixed_route_long','follow_drone']
               if kind.startswith('travel_') else
               ['closeup','fixed_side_wide','high_oblique','low_oblique'])
        return modes[(index+getattr(self,'view_seed',0))%len(modes)]

    def view(self, kind: str, evidence: dict, index: int) -> tuple:
        """검수한 근접 구도의 로봇 상대 좌표를 사용해 베드 양면에 동일 적용한다."""
        t = np.asarray(evidence['transform']); rotation=t[:3,:3]; center=t[:3,3]
        mode=self.view_mode(kind,index)
        if kind.startswith('travel_') and mode.startswith('fixed_route'):
            # 카메라를 시작 지점 뒤가 아닌 진행 방향 앞에 둔다. 클립 중 위치/방향 고정.
            # 긴 구도는 약 7~10m의 통로가 보이는 14mm, 사선 고정은 18mm.
            eye=[4.6,-.30,2.45] if mode=='fixed_route_long' else [3.5,-.65,2.35]
            target=[1.5,0.,.25];focal=14. if mode=='fixed_route_long' else 18.
        elif kind.startswith('travel_') and mode=='low_oblique':
            eye=[1.35,-.7,1.05];target=[.15,0.,.35];focal=25.
        elif kind == 'harvest':
            eye = [.82, -.05, 1.22] if index%2 == 0 else [.95, -.35, 1.42]
            target = [.21, .38, .98]; focal=32. if index%2 == 0 else 28.
            if mode=='fixed_side_wide':eye=[1.3,-.65,1.55];target=[.1,.20,.65];focal=22.
            elif mode=='high_oblique':eye=[.65,-.35,2.15];target=[.2,.35,.85];focal=29.
            elif mode=='low_oblique':eye=[.85,-.3,.95];target=[.2,.4,.98];focal=28.
        elif kind == 'sorting':
            eye = [1.1,-.68,1.15] if index%2 == 0 else [.75,-.5,1.32]
            target = [.17,0.,.30] if index%2 == 0 else [-.15,0.,.48]; focal=29.
            if mode=='fixed_side_wide':eye=[1.25,-1.,1.25];target=[.1,0.,.35];focal=22.
            elif mode=='high_oblique':eye=[.4,-.4,1.8];target=[.1,0.,.3];focal=26.
            elif mode=='low_oblique':eye=[1.,-.7,.8];target=[.1,0.,.4];focal=24.
        elif kind == 'docking':
            other=np.asarray(evidence['transport_transform'])
            center=(center+other[:3,3])/2
            eye=[-.8,-.8,1.5] if index%2 == 0 else [-1.1,.7,1.65]
            target=[0.,0.,.58]; focal=30.
            if mode=='fixed_side_wide':eye=[-1.4,-1.,1.6];focal=22.
            elif mode=='high_oblique':eye=[-1.,-.7,2.35];focal=25.
            elif mode=='low_oblique':eye=[-1.1,-.9,.9];focal=25.
        else:
            # 지붕 아래 높이에서 비스듬한 드론뷰. 각 로봇을 따라가며 통로를 보여준다.
            eye=[-1.25,-.35,2.5] if index%2 == 0 else [.65,-1.25,2.5]
            target=[.25,0.,.25]; focal=23.
        return center+rotation@np.asarray(eye), center+rotation@np.asarray(target), focal

    def _pose(self, kind: str, evidence: dict, index: int) -> dict:
        from scipy.spatial.transform import Rotation
        eye,target,focal=self.view(kind,evidence,index)
        forward=target-eye;forward/=np.linalg.norm(forward)
        right=np.cross(forward,[0.,0.,1.]);right/=np.linalg.norm(right)
        up=np.cross(right,forward)
        q=Rotation.from_matrix(np.column_stack((right,up,-forward))).as_quat()[[3,0,1,2]]
        self.camera.set_world_pose(eye,q,camera_axes='usd')
        self.camera.set_focal_length(focal)
        return dict(eye_world_m=eye.tolist(),target_world_m=target.tolist(),focal_mm=focal)

    def _start(self, now: float, kind: str, evidence: dict, robots: list) -> None:
        native=kind.startswith('apriltag_')
        if self.camera is None and not native:
            from isaacsim.sensors.camera import Camera
            self.camera=Camera('/World/PortfolioVideoCamera',name='portfolio_video',
                               frequency=self.fps,resolution=self.resolution)
            self.camera.initialize();self.camera.set_horizontal_aperture(36.)
            self.camera.set_clipping_range(.03,100.)
        index=self.counts.get(kind,0)
        mode=self.view_mode(kind,index)
        if native:
            sensor=next(r for r in robots if r['cfg']['robot_id']==evidence['robot_id'])['tag_camera']
            self.source_camera=sensor.camera
            resolution=(sensor.config['width'],sensor.config['height']);fps=int(sensor.config['fps'])
            pose=dict(frame_id=sensor.optical_frame,intrinsics=sensor.config.get('camera_info'),
                      T_base_optical=sensor.T_base_optical.tolist())
            self.active(False)  # 센서 카메라는 재설정하거나 일시정지하지 않는다.
        else:
            pose=self._pose(kind,evidence,index);self.source_camera=self.camera
            resolution=self.resolution;fps=self.fps
            self.active(True)
        self.clip=dict(kind=kind,index=index,name=f'{kind}-{index+1:02d}-{mode}',view_mode=mode,
                       fps=fps,resolution=resolution,
                       requested_sim_s=now,start_sim_s=None,frames=0,duplicates=0,
                       last_render=None,last_rgb=None,pose=pose,evidence=evidence,process=None,
                       started_at=datetime.now(timezone.utc).isoformat())

    def _open_encoder(self) -> None:
        c=self.clip; w,h=c['resolution']
        c['stderr']=(self.output/(c['name']+'-ffmpeg.log')).open('w')
        c['ledger']=(self.output/(c['name']+'-frames.jsonl')).open('w',buffering=1)
        c['process']=subprocess.Popen(['ffmpeg','-nostdin','-y','-loglevel','error',
            '-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(c['fps']),'-i','pipe:0',
            '-an','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2',
            '-pix_fmt','yuv420p','-movflags','+faststart',str(self.output/(c['name']+'.mp4'))],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=c['stderr'])

    def _finish(self, reason: str, now: float) -> None:
        if self.clip is None:return
        c=self.clip; self.clip=None
        code=None
        if c['process'] is not None:
            c['process'].stdin.close()
            try:code=c['process'].wait(timeout=15)
            except subprocess.TimeoutExpired:
                c['process'].kill();code=c['process'].wait()
            c['ledger'].close();c['stderr'].close()
        self.active(False)
        metadata={k:v for k,v in c.items() if k not in ('process','ledger','stderr','last_rgb')}
        metadata.update(session=self.session,scope='live simulation; no staged robot poses',
            duration_video_s=c['frames']/c['fps'],
            end_sim_s=now,reason=reason,encoder_exit=code,
            complete=reason=='duration_reached' and code==0 and c['frames']==round(self.duration*c['fps']))
        (self.output/(c['name']+'.json')).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        self.counts[c['kind']]=c['index']+1;self.last[c['kind']]=now
        with (self.output/'clips.jsonl').open('a') as stream:
            stream.write(json.dumps(metadata,ensure_ascii=False)+'\n')
        print('[portfolio_video] '+c['name']+' '+reason+f" frames={c['frames']}",flush=True)

    def update(self, now: float, robots: list, sorter: object, monitor: object) -> None:
        if self.failed:return
        try:self._update_video(now,robots,sorter,monitor)
        except Exception as exc:
            self.failed=True
            try:self._finish('capture_error',now)
            except Exception:pass
            (self.output/'capture_error.json').write_text(json.dumps(dict(error=repr(exc),sim_time_s=now))+'\n')
            print('[portfolio_video] disabled: '+repr(exc),flush=True)

    def _update_video(self, now: float, robots: list, sorter: object, monitor: object) -> None:
        from PIL import Image
        candidates=self.candidates(robots,sorter,monitor)
        if self.clip is None:
            order=['docking','harvest','sorting','travel_scout_01','travel_transport_01','travel_harvest_01',
                   'apriltag_scout_01','apriltag_harvest_01']
            for kind in order:
                cooldown=120. if kind.startswith('travel_') else 5.
                limit=4 if kind=='harvest' or kind.startswith('travel_') else 2
                if kind in candidates and self.counts.get(kind,0)<limit and now-self.last.get(kind,-1e6)>=cooldown:
                    self._start(now,kind,candidates[kind],robots);break
            return
        c=self.clip;kind=c['kind']
        # 짧은 파지/도킹 동작이 끝나도 전후 동작을 포함해 30초를 기록한다.
        evidence=candidates.get(kind)
        if evidence is None and kind.startswith('travel_'):
            rid=kind.removeprefix('travel_')
            robot=next(r for r in robots if r['cfg']['robot_id']==rid)
            evidence=dict(transform=robot['T_world_base'].tolist(),robot_id=rid,command=list(robot['applied_cmd']))
        frame=self.source_camera.get_current_frame(); stamp=float(frame.get('rendering_time',0))
        if stamp>c['requested_sim_s']+.15 and stamp!=c['last_render']:
            rgb=self.source_camera.get_rgb()
            if rgb is not None and rgb.shape==(*c['resolution'][::-1],3) and np.std(rgb)>1.:
                if c['start_sim_s'] is None:
                    c['start_sim_s']=stamp;self._open_encoder()
                    Image.fromarray(rgb.astype(np.uint8)).save(self.output/(c['name']+'-first.png'))
                count=frame_count(stamp-c['start_sim_s'],c['fps'],self.duration)
                while c['frames']<count:
                    # 표본 간격이 벌어지면 직전 실제 프레임을 유지한다. 합성 모션은 생성하지 않는다.
                    duplicate=c['frames']<count-1 and c['last_rgb'] is not None
                    selected=c['last_rgb'] if duplicate else rgb
                    c['process'].stdin.write(np.asarray(selected,dtype=np.uint8).tobytes())
                    c['ledger'].write(json.dumps(dict(frame=c['frames'],video_s=c['frames']/c['fps'],
                        source_sim_s=c['last_render'] if duplicate else stamp,held_frame=duplicate,
                        camera=c['pose']))+'\n')
                    c['frames']+=1;c['duplicates']+=int(duplicate)
                c['last_rgb']=rgb.copy();c['last_render']=stamp
                if c['frames']==round(self.duration*c['fps']):
                    Image.fromarray(rgb.astype(np.uint8)).save(self.output/(c['name']+'-last.png'))
                    self._finish('duration_reached',now);return
        if evidence is not None:
            c['evidence']=evidence
            if c['view_mode'] not in ('sensor_original','fixed_route_wide','fixed_route_long','fixed_side_wide'):
                c['pose']=self._pose(kind,evidence,c['index'])
        if c['start_sim_s'] is None and now-c['requested_sim_s']>10.:
            raise RuntimeError('외부 카메라 렌더 표본이 10 시뮬초 동안 없음')
        if c['last_render'] is not None and now-c['last_render']>10.:
            self._finish('source_frames_stopped',now)

    def close(self) -> None:
        self._finish('simulation_ended',self.clip['last_render'] or 0. if self.clip else 0.)
