"""실물 예찰 opt-in 후진 어댑터. Nav2 종료 후 동일 속도 스무더 입력을 단독 사용한다."""
import math
import threading
import time
import numpy as np
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
from farm_navigation.wall_reference import scan_points
from .station_wall_control import StableWalls, observe_walls, reverse_command, arrival_matches, wrap, ArrivalSettler


class StationWallRuntime:
    def __init__(self, node, poses, motion, settings, config: dict, group) -> None:
        self.node=node; self.poses=poses; self.motion=motion; self.settings=settings; self.c=config
        if not 0 < config['min_speed_mps'] <= config['speed_mps'] <= .15:
            raise ValueError('후진 최소/기본 속도 범위 오류')
        self.lock=threading.Lock(); self.scan=None; self.odom=None
        self.scan_at=self.odom_at=0.; self.active=False; self.command=(0.,0.); self.command_at=0.
        self.pub=node.create_publisher(Twist,config['command_topic'],10)
        self.scan_sub=node.create_subscription(LaserScan,config['scan_topic'],self._scan,qos_profile_sensor_data,callback_group=group)
        self.odom_sub=node.create_subscription(Odometry,settings.odom_topic,self._odom,qos_profile_sensor_data,callback_group=group)
        self.timer=node.create_timer(.05,self._publish,callback_group=group)

    def _scan(self, msg) -> None:
        with self.lock:self.scan=msg;self.scan_at=time.monotonic()

    def _odom(self, msg) -> None:
        with self.lock:self.odom=msg;self.odom_at=time.monotonic()

    @staticmethod
    def _stamp(msg) -> float:
        return msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9

    def _fresh(self, msg, received: float) -> bool:
        if msg is None:return False
        age=self.node.get_clock().now().nanoseconds*1e-9-self._stamp(msg)
        return -.1<=age<=self.c['max_age_s'] and time.monotonic()-received<=self.c['max_age_s']

    def _publish(self) -> None:
        # 목표 계산·TF 조회가 막혀도 이전 속도 명령을 반복하지 않는다.
        with self.lock:
            if not self.active:return
            valid=(time.monotonic()-self.command_at<self.c['command_timeout_s'] and
                   self._fresh(self.scan,self.scan_at) and self._fresh(self.odom,self.odom_at))
            v,w=self.command if valid else (0.,0.)
            msg=Twist();msg.linear.x=float(v);msg.angular.z=float(w);self.pub.publish(msg)

    def _set(self, v: float=0., w: float=0.) -> None:
        with self.lock:self.command=(v,w);self.command_at=time.monotonic()

    def stop(self) -> None:
        with self.lock:
            if not self.active:return
            self.command=(0.,0.);self.active=False;self.pub.publish(Twist())

    def _hold(self, check, phase, reason: str) -> None:
        self._set();phase(reason)
        # 진행 불능은 즉시 FAILED 대신 정지 대기. 취소/새 미션 선점은 계속 확인한다.
        while True:
            check();self._set();time.sleep(.1)

    @staticmethod
    def _matrix(msg) -> np.ndarray:
        p=msg.pose.pose;q=p.orientation
        norm=q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w
        if not math.isfinite(norm) or abs(norm-1)>.05:raise ValueError('odom quaternion 오류')
        yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        m=np.eye(4);m[:2,:2]=[[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]]
        m[0,3]=p.position.x;m[1,3]=p.position.y
        if not np.isfinite(m).all():raise ValueError('odom 위치 오류')
        return m

    def execute(self, check, phase, nominal_distance: float) -> None:
        c=self.c;tracker=StableWalls(c);start=None;previous=None;travel=0.;blend=0.;locked=False
        settler=ArrivalSettler(c['settle_s'],c.get('settle_gap_s',.5),c.get('settle_min_samples',1));last_stamp=None;transform=None;frame=None;last_log=0.;rear_locked=False
        with self.lock:self.active=True;self.command=(0.,0.);self.command_at=time.monotonic()
        try:
            while True:
                check()
                with self.lock:scan=self.scan;odom=self.odom;sa=self.scan_at;oa=self.odom_at
                if not self._fresh(scan,sa) or not self._fresh(odom,oa):
                    self._set();settler.pause(time.monotonic())
                    if time.monotonic()-last_log>2:phase('WAIT_REVERSE_SENSORS');last_log=time.monotonic()
                    time.sleep(.05);continue
                if odom.header.frame_id != c['odom_frame'] or odom.child_frame_id != self.settings.base_frame:
                    raise ValueError('후진 odom frame 불일치')
                if abs(self._stamp(scan)-self._stamp(odom))>c['max_pair_gap_s']:
                    self._set();settler.pause(time.monotonic());time.sleep(.05);continue
                matrix=self._matrix(odom)
                if transform is None:
                    self._set()
                    transform=self.poses.lookup(self.settings.base_frame,scan.header.frame_id,0,check,
                                                on_unavailable=lambda _:self._set())
                    frame=scan.header.frame_id
                    continue
                if frame != scan.header.frame_id:raise ValueError('스캔 frame 변경')
                if start is None:start=matrix.copy();previous=matrix[:2,3].copy()
                step=float(np.linalg.norm(matrix[:2,3]-previous));previous=matrix[:2,3].copy()
                if step>c['odom_jump_m']:self._hold(check,phase,'WAIT_ODOM_DISCONTINUITY')
                travel+=step
                # 이동량은 map 보정에 영향받지 않는다. 기준 벽 미확보 시 거리를 넘겨 밀지 않는다.
                if travel>nominal_distance+c['travel_margin_m']:
                    self._hold(check,phase,'WAIT_REVERSE_DISTANCE_LIMIT')
                stamp=self._stamp(scan)
                if last_stamp is not None and stamp<=last_stamp:
                    time.sleep(.02);continue
                last_stamp=stamp
                record=dict(base_from_scan=transform,scan=dict(ranges=scan.ranges,angle_min=scan.angle_min,
                    angle_increment=scan.angle_increment,range_min=scan.range_min,range_max=scan.range_max))
                points=scan_points(record,(-180,180))
                if len(points)<c['min_scan_points']:
                    self._set();settler.pause(time.monotonic());time.sleep(.05);continue
                # 원시 근거리 점은 벽 필터와 별개로 유지한다.
                if np.any(np.linalg.norm(points,axis=1)<c['stop_radius_m']):
                    self._set();settler.reset()
                    if time.monotonic()-last_log>2:phase('WAIT_NEAR_OBSTACLE');last_log=time.monotonic()
                    time.sleep(.05);continue
                walls=tracker.update(observe_walls(points,c),matrix,stamp)
                if 'rear' in walls:rear_locked=True
                elif rear_locked:
                    self._set();settler.pause(time.monotonic())
                    if time.monotonic()-last_log>2:phase('WAIT_REAR_WALL_REOBSERVATION');last_log=time.monotonic()
                    time.sleep(.05);continue
                side=any(n in walls for n in ('left','right'))
                if side:locked=True;blend=min(1.,blend+c['blend_step'])
                elif locked:
                    self._set();settler.pause(time.monotonic())
                    if time.monotonic()-last_log>2:phase('WAIT_WALL_REOBSERVATION');last_log=time.monotonic()
                    time.sleep(.1);continue
                else:blend=0.
                yaw_error=wrap(math.atan2(start[1,0],start[0,0])-math.atan2(matrix[1,0],matrix[0,0]))
                v,w,state=reverse_command(c,walls,yaw_error,blend)
                if state=='VERIFY_WALL_STOP':
                    self._set()
                    valid=arrival_matches(c,walls) and self.motion.stationary_now()
                    if settler.observe(stamp,time.monotonic(),valid):
                        phase('STATION_WALL_STOPPED');return
                    if not valid:
                        # 남은 거리가 없으면 후진으로 억지 보정하지 않는다.
                        state='WAIT_FINAL_WALL_ALIGNMENT'
                else:
                    settler.reset();self._set(v,w)
                if time.monotonic()-last_log>1:
                    distances={k:round(v['distance_m'],4) for k,v in walls.items()}
                    phase(f'{state} travel={travel:.3f} walls={distances} v={v:.3f} w={w:.3f} settle={settler.elapsed:.3f}/{c["settle_s"]:.3f}s')
                    last_log=time.monotonic()
                time.sleep(.05)
        finally:
            self.stop()

    def close(self) -> None:
        self.stop();self.node.destroy_timer(self.timer)
        self.node.destroy_subscription(self.scan_sub);self.node.destroy_subscription(self.odom_sub)
        self.node.destroy_publisher(self.pub)
