"""실물 예찰 전용: 벽 분석 스레드와 20Hz 제어/센서 전용 실행기를 분리한다."""
import math
import threading
import time
import numpy as np
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from rclpy.qos import qos_profile_sensor_data
from farm_navigation.wall_reference import scan_points
from .station_wall_runtime import StationWallRuntime
from .station_wall_control import StableWalls,observe_walls,reverse_command,arrival_matches,wrap,ArrivalSettler,forward_command,forward_arrival_matches
from .station_smooth_control import predict_wall,continuation_scale,ramp_command


class StationSmoothWallRuntime:
    _matrix=staticmethod(StationWallRuntime._matrix)
    _stamp=staticmethod(StationWallRuntime._stamp)

    def __init__(self,node,poses,motion,settings,config: dict,group) -> None:
        self.node=node;self.poses=poses;self.settings=settings;self.c=config
        if not 0<config['min_speed_mps']<=config['speed_mps']<=.15:raise ValueError('후진 속도 범위 오류')
        if not 0<config['wall_fresh_s']<config['wall_continuation_s']:raise ValueError('벽 연결 시간 오류')
        self.lock=threading.Lock();self.scan=None;self.odom=None;self.scan_at=self.odom_at=0.
        self.active=False;self.closed=False;self.worker=None;self.worker_stop=threading.Event()
        self.io=Node(node.get_name()+'_wall_control',namespace=node.get_namespace(),context=node.context,
            use_global_arguments=False,enable_rosout=False,start_parameter_services=False,
            parameter_overrides=[Parameter('use_sim_time',value=bool(node.get_parameter('use_sim_time').value))])
        self.pub=self.io.create_publisher(Twist,node.resolve_topic_name(config['command_topic']),10)
        self.scan_sub=self.io.create_subscription(LaserScan,node.resolve_topic_name(config['scan_topic']),self._scan,qos_profile_sensor_data)
        self.odom_sub=self.io.create_subscription(Odometry,node.resolve_topic_name(settings.odom_topic),self._odom,qos_profile_sensor_data)
        self.timer=self.io.create_timer(.05,self._tick)
        self.executor=SingleThreadedExecutor(context=node.context);self.executor.add_node(self.io)
        self.thread=threading.Thread(target=self._spin,name='station_control',daemon=True);self.thread.start()

    def _spin(self) -> None:
        try:self.executor.spin()
        except ExternalShutdownException:pass

    def _scan(self,msg) -> None:
        with self.lock:self.scan=msg;self.scan_at=time.monotonic()

    def _odom(self,msg) -> None:
        with self.lock:self.odom=msg;self.odom_at=time.monotonic()

    def _fresh(self,msg,received: float) -> bool:
        if msg is None:return False
        age=self.io.get_clock().now().nanoseconds/1e9-self._stamp(msg)
        return -.1<=age<=self.c['max_age_s'] and time.monotonic()-received<=self.c['max_age_s']

    def _send(self,v: float=0.,w: float=0.) -> None:
        self.command=(v,w);msg=Twist();msg.linear.x=float(v);msg.angular.z=float(w);self.pub.publish(msg)

    def _wait(self,state: str,reset: bool=False) -> None:
        self.state=state;self._send()
        if reset:self.settler.reset()
        else:self.settler.pause(time.monotonic())

    def _analyze(self) -> None:
        tracker=StableWalls(self.c);last=None
        while not self.worker_stop.wait(.01):
            with self.lock:
                if not self.active:return
                scan,odom,sa,oa,tf=self.scan,self.odom,self.scan_at,self.odom_at,self.transform
            if tf is None or not self._fresh(scan,sa) or not self._fresh(odom,oa):continue
            stamp=self._stamp(scan)
            if last is not None and stamp<=last:continue
            if abs(stamp-self._stamp(odom))>self.c['max_pair_gap_s']:continue
            last=stamp;begin=time.monotonic()
            try:
                pose=self._matrix(odom)
                points=scan_points(dict(scan=dict(ranges=scan.ranges,angle_min=scan.angle_min,
                    angle_increment=scan.angle_increment,range_min=scan.range_min,range_max=scan.range_max),base_from_scan=tf),(-180,180))
                raw=observe_walls(points,self.c);walls=tracker.update(raw,pose,stamp)
                packet=dict(stamp=stamp,at=sa,pose=pose,walls=walls,raw=list(raw),
                            counts=dict(tracker.count),fit_s=time.monotonic()-begin)
                with self.lock:
                    if self.active:self.analysis=packet
            except Exception as error:
                with self.lock:self.error=str(error)
                return

    def _tick(self) -> None:
        # 전용 실행기에서만 호출. 피팅·TF 대기·파일 I/O는 수행하지 않는다.
        with self.lock:
            if not self.active:return
            try:self._control(time.monotonic())
            except Exception as error:
                self.error=str(error);self._wait('WAIT_CONTROL_ERROR',True)

    def _control(self,now: float) -> None:
        if self.done:self._send();return
        c=self.c;front=c.get('direction')=='forward';end='front' if front else 'rear';sign=1 if front else -1
        dt=now-self.last_tick;self.last_tick=now;self.max_tick_gap=max(self.max_tick_gap,dt)
        if self.error:self._wait('WAIT_CONTROL_ERROR',True);return
        if now-self.supervisor_at>c['supervisor_timeout_s']:
            self._wait('WAIT_SUPERVISOR');return
        if dt>c['command_timeout_s']:
            self._wait('WAIT_CONTROL_GAP');return
        scan,odom=self.scan,self.odom
        if not self._fresh(scan,self.scan_at) or not self._fresh(odom,self.odom_at):
            self._wait('WAIT_REVERSE_SENSORS');return
        if self.transform is None:self._wait('WAIT_SCAN_TRANSFORM');return
        if scan.header.frame_id!=self.scan_frame or odom.header.frame_id!=c['odom_frame'] or odom.child_frame_id!=self.settings.base_frame:
            raise ValueError('후진 센서 frame 불일치')
        pose=self._matrix(odom)
        if self.origin is None:self.origin=pose;self.previous=pose[:2,3].copy()
        step=float(np.linalg.norm(pose[:2,3]-self.previous));self.previous=pose[:2,3].copy();self.travel+=step
        if step>c['odom_jump_m'] or self.travel>self.nominal+c['travel_margin_m']:
            self.error='후진 odom 이동 한계 초과';self._wait('WAIT_REVERSE_DISTANCE_LIMIT',True);return
        # 최신 스캔의 원시 근거리 검사는 벽 분석 완료를 기다리지 않는다.
        stamp=self._stamp(scan)
        if stamp!=self.safety_stamp:
            points=scan_points(dict(scan=dict(ranges=scan.ranges,angle_min=scan.angle_min,
                angle_increment=scan.angle_increment,range_min=scan.range_min,range_max=scan.range_max),base_from_scan=self.transform),(-180,180))
            self.safety_stamp=stamp
            self.scan_clear=(len(points)>=c['min_scan_points'] and not np.any(np.linalg.norm(points,axis=1)<c['stop_radius_m']))
        if not self.scan_clear:self._wait('WAIT_NEAR_OBSTACLE',True);return
        packet=self.analysis;new=False
        if packet is not None and packet['stamp']!=self.analysis_stamp:
            self.analysis_stamp=packet['stamp'];new=True
            # 오래 걸린 분석 결과가 새 관측인 것처럼 유효시간을 연장하지 않는다.
            age=now-packet['at']
            if age<=c['wall_continuation_s']:
                for name,wall in packet['walls'].items():self.cache[name]=(wall,packet['pose'],packet['at'])
        walls={};ages=[]
        for name,(wall,observed,at) in self.cache.items():
            age=now-at
            if age<=c['wall_continuation_s']:
                walls[name]=predict_wall(wall,observed,pose,name);ages.append(age)
        if (end in self.cache and end not in walls) or (self.cache and not any(n in walls for n in ('left','right'))):
            self._wait('WAIT_WALL_CONTINUATION_EXPIRED');return
        if self.analysis is None:self._wait('WAIT_FIRST_WALL_ANALYSIS');return
        if now-self.analysis['at']>c['wall_continuation_s']:
            self._wait('WAIT_WALL_ANALYSIS');return
        side=any(n in walls for n in ('left','right'))
        self.blend=min(1.,self.blend+c['blend_step']*dt/.05) if side else 0.
        yaw=wrap(math.atan2(self.origin[1,0],self.origin[0,0])-math.atan2(pose[1,0],pose[0,0]))
        v,w,state=(forward_command if front else reverse_command)(c,walls,yaw,self.blend)
        if state=='VERIFY_WALL_STOP':
            self._send();self.state=state
            if new:
                fresh=(now-packet['at']<=c['max_age_s'])
                twist=odom.twist.twist
                stopped=(math.hypot(twist.linear.x,twist.linear.y)<self.settings.stopped_linear_mps and abs(twist.angular.z)<self.settings.stopped_angular_rps)
                if fresh and end in packet['walls'] and any(n in packet['walls'] for n in ('left','right')):
                    valid=(forward_arrival_matches if front else arrival_matches)(c,packet['walls']) and stopped
                    if self.settler.observe(packet['stamp'],now,valid):self.done=True;self.state='STATION_WALL_STOPPED'
                    elif not valid:self.state='WAIT_FINAL_WALL_ALIGNMENT'
                else:self.settler.pause(now)
            return
        self.settler.reset()
        age=max(ages+[now-self.analysis['at']])
        scale=continuation_scale(age,c['wall_fresh_s'],c['wall_continuation_s'])
        if end in walls:
            remaining=max(0.,walls[end]['distance_m']-c['walls'][end]['target_m']-c['distance_tolerance_m'])
            # 정지 거리와 한 제어주기 여유를 고려한다. 최종 구간은 최소속도 아래도 허용한다.
            braking=max(0.,math.sqrt(2*c['linear_decel_mps2']*remaining)-abs(odom.twist.twist.linear.x)*.1)
            v=sign*min(abs(v),braking)
        target=(v*scale,w*scale)
        command=ramp_command(self.command,target,dt,c['linear_accel_mps2'],c['linear_decel_mps2'],c['angular_accel_rps2'])
        # 거리 제한·관측 만료로 정해진 감속 상한은 ramp 때문에 초과하지 않는다.
        command=(sign*min(abs(command[0]),abs(target[0])),command[1])
        self._send(*command);self.state=('FORWARD' if front else 'REVERSE')+'_ODOM_CONTINUATION' if scale<1 else state

    def execute(self,check,phase,nominal_distance: float) -> None:
        if self.worker is not None and self.worker.is_alive():raise RuntimeError('이전 벽 분석 종료 미확인')
        with self.lock:
            self.transform=None;self.scan_frame=None;self.analysis=None;self.analysis_stamp=None;self.cache={}
            self.origin=None;self.previous=None;self.travel=0.;self.blend=0.;self.nominal=nominal_distance
            self.command=(0.,0.);self.done=False;self.error=None;self.state='WAIT_REVERSE_SENSORS'
            self.safety_stamp=None;self.scan_clear=False;self.max_tick_gap=0.
            self.settler=ArrivalSettler(self.c['settle_s'],self.c['settle_gap_s'],self.c['settle_min_samples'])
            self.last_tick=self.supervisor_at=time.monotonic();self.active=True
        self.worker_stop.clear();self.worker=threading.Thread(target=self._analyze,name='station_wall_fit',daemon=True);self.worker.start()
        last_log=0.
        try:
            while True:
                check()
                with self.lock:
                    self.supervisor_at=time.monotonic();scan=self.scan;need_tf=self.transform is None
                    done=self.done;state=self.state;packet=self.analysis
                    text=f'{state} travel={self.travel:.3f} v={self.command[0]:.3f} w={self.command[1]:.3f} settle={self.settler.elapsed:.3f}/{self.c["settle_s"]:.3f}s control_max_gap={self.max_tick_gap:.3f}s'
                    if packet:text+=f' analysis_age={time.monotonic()-packet["at"]:.3f}s fit={packet["fit_s"]:.3f}s raw={packet["raw"]} counts={packet["counts"]}'
                    if self.error:text+=' error='+self.error
                if done:phase('STATION_WALL_STOPPED');return
                if need_tf and scan is not None:
                    tf=self.poses.lookup(self.settings.base_frame,scan.header.frame_id,0,check)
                    with self.lock:self.transform=tf;self.scan_frame=scan.header.frame_id
                if time.monotonic()-last_log>1:phase(text);last_log=time.monotonic()
                time.sleep(.05)
        finally:self.stop()

    def stop(self) -> None:
        with self.lock:
            if self.active:self.active=False;self._send()
        self.worker_stop.set()
        if self.worker is not None:
            self.worker.join(timeout=3)
            if self.worker.is_alive():raise RuntimeError('벽 분석 스레드 종료 미확인')

    def close(self) -> None:
        if self.closed:return
        self.stop();self.executor.shutdown();self.thread.join(timeout=3)
        self.executor.remove_node(self.io);self.io.destroy_node();self.closed=True
