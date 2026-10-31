"""기존 ArUco 전략을 공통 Action으로 감싼다. 운송의 인계 의미는 모른다."""
from std_srvs.srv import SetBool
from .staged_dock import StagedDockTracker
import math
import cv2
import numpy as np
from .station_entry import StationEntry
from .recovery import Recoverable, RecoveryWait, MarkerSearch, recovery_observation_ready
from .footprint_guard import FootprintGuard
import json
from std_msgs.msg import String
from .pose_control import PoseController
from .target_tracker import FixedTargetTracker
from .departure import DepartureTracker
from .exit_heading import graph_point, heading_command
from .target_surface import surface_points, surface_guard, matching_raw, raw_front_mask, fresh_scan_pairs
from .pose_path import command as pose_path_command
from .lidar_approach import LidarApproach, ScanFreshnessError, select_tf_ready_scan
from .sorter_departure import reverse_point, backout_command
from .lidar_approach import front_distance
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
from .profiles import marker_profile,validate_recovery
from .pose_session import pose_command
from .approach_gate import ApproachGate, near_entry_command, search_evidence
from .marker_geometry import transform_matrix, compose_marker, solve_marker
from .camera_input import Frame, LatestFrame, PicameraInput, load_calibration
import time
from queue import Queue,Empty
from threading import Lock,Event,RLock
from pathlib import Path
import yaml
import rclpy
from rclpy.action import ActionServer,GoalResponse,CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup,MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.duration import Duration
from rclpy.time import Time
from tf2_ros import Buffer,TransformListener,TransformException
from farm_interfaces.action import PrecisionMotion
from .legacy_aruco import Dock,IDLE,DONE,FAILED,SEARCH
from .clients import LeaseClient
from .clearance import reverse_to_pose

class PrecisionServer(Dock):
    def __init__(self):
        self._sensor_group=MutuallyExclusiveCallbackGroup()
        self._sensor_lock=Lock()
        self._last_odom=None;self._last_scan_stamp=None
        self._sensor_max_gap={'odom':0.,'scan':0.}
        self._legacy_odom_stamp=None;self._legacy_scan_stamp=None
        self._loop_max_ms=0.;self._timing_at=time.monotonic()
        self._profile_lock=RLock()
        self._tracking_enabled=False;self._raw_reports=();self._tracking_preview=None
        self._session=None;self._pending=Queue();self._reservation=Lock()
        self._odom_at=0.;self._scan_at=0.;self._image_at=0.;self._stopped_since=None
        self._odom_stamp=None;self._last_scan=None;self._measured_twist=(0.,0.)
        self._header_ages={}
        self._frames=LatestFrame(); self._camera_input=None; self._camera_enabled=False; self._camera_generation=0
        super().__init__()
        self.declare_parameter('profiles_file','')
        self.declare_parameter('log_dir','')
        self.declare_parameter('sensor_ready_timeout_s',3.0)
        for key, default in (('odom_max_age_s', .5), ('scan_max_age_s', .5), ('image_header_max_age_s', .3), ('image_receive_timeout_s', .5)):
            self.declare_parameter(key, default)
            value = self.get_parameter(key).value
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{key}: 양의 유한 시간 필요')
            setattr(self, key, float(value))
        defaults = {
            'camera_input_backend': 'ros', 'camera_calibration_file': '',
            'camera_width': 1280, 'camera_height': 720, 'camera_fps': 10.0,
            'camera_index': 0, 'camera_frame_id': 'camera',
            'camera_sensor_width': 0, 'camera_sensor_height': 0,
            'camera_sensor_bit_depth': 0, 'camera_crop': [0, 0, 0, 0],
            'camera_geometry_verified': False,
            'pose_output_enabled': False, 'pose_control_file': '', 'pose_control_target': '',
            'marker_pose_mode': 'legacy_camera', 'marker_base_frame': 'base_footprint',
            'odom_frame': 'odom',
        }
        for key, default in defaults.items():
            self.declare_parameter(key, default)
        self.pose_mode = self.get_parameter('marker_pose_mode').value
        if self.pose_mode not in ('legacy_camera', 'tf_observe'):
            raise ValueError('marker_pose_mode must be legacy_camera or tf_observe')
        self.marker_base_frame = self.get_parameter('marker_base_frame').value
        self._observations = {}; self._base_camera = None; self._frame_stamp_ns = 0
        self._camera_failure = None;self._detection_max_ms=0.
        self._input_error = ''; self._tf_at = 0.; self._last_observation = None
        self.observation_pub = self.create_publisher(String, 'precision/marker_observations', 1)
        self.pose_output_enabled = self.get_parameter('pose_output_enabled').value
        self._pose_lock=Lock()
        self._pose_controller = None
        control_file = self.get_parameter('pose_control_file').value
        if control_file:
            if self.pose_mode != 'tf_observe':
                raise ValueError('Pose preview requires tf_observe')
            document = yaml.safe_load(Path(control_file).expanduser().read_text())
            target = document['targets'][self.get_parameter('pose_control_target').value]
            if target['base_frame'] != self.marker_base_frame:
                raise ValueError('Target base frame mismatch')
            self._target_extrinsics = np.asarray(target.get('camera_extrinsics_T_base_camera',[]),dtype=float)
            self._pose_controller = PoseController(target, document['shadow_controller'])
        self.control_preview_pub = self.create_publisher(String, 'precision/control_preview', 1)
        self.camera_backend = self.get_parameter('camera_input_backend').value
        if self.camera_backend not in ('ros', 'picamera2'):
            raise ValueError('camera_input_backend must be ros or picamera2')
        # A separate callback group lets ROS receive the latest message while
        # detection runs. State mutation/detection remains in the default group.
        self._image_group = ReentrantCallbackGroup()
        self._image_lock = Lock()
        if self.camera_backend == 'picamera2':
            value = lambda key: self.get_parameter('camera_' + key).value
            if self.get_parameter('use_sim_time').value:
                raise ValueError('Direct camera capture requires use_sim_time=false')
            if not value('geometry_verified'):
                raise ValueError('Verify sensor mode/crop against calibration before direct capture')
            width, height = value('width'), value('height')
            self.K, self.D = load_calibration(value('calibration_file'), width, height)
            self._camera_input = PicameraInput(self._frames,
                lambda: self.get_clock().now().nanoseconds,
                index=value('index'), width=width, height=height, fps=value('fps'),
                frame_id=value('frame_id'),
                sensor_size=(value('sensor_width'), value('sensor_height')),
                sensor_bit_depth=value('sensor_bit_depth'), crop=value('crop'))
        self._detection_group = MutuallyExclusiveCallbackGroup()
        self._image_timer = self.create_timer(0.05, self.consume_image, callback_group=self._detection_group if self.pose_mode == 'tf_observe' else None)
        self.profiles=yaml.safe_load(Path(self.get_parameter('profiles_file').value).read_text())['profiles']
        self._raw_front_scans={};self._raw_front_history={};self._raw_front_subs=[]
        for topic in {p[k]['raw_scan_topic'] for p in self.profiles.values() for k in ('lidar_approach','marker_backout') if p.get(k)}:
            self._raw_front_subs.append(self.create_subscription(LaserScan,topic,
                lambda m,key=topic:self.on_raw_front_scan(key,m),qos_profile_sensor_data,callback_group=self._sensor_group))
        self._footprint_guards={}
        for name,profile in self.profiles.items():
            validate_recovery(profile)
            if profile.get("configured") and profile.get("lidar_approach"):LidarApproach(profile["lidar_approach"])
            if profile.get('pose_control_file'):
                profile['pose_control_file']=str((Path(self.get_parameter('profiles_file').value).parent/Path(profile['pose_control_file']).expanduser()).resolve())
            cfg=profile.get('collision_guard')
            if not cfg:continue
            path=(Path(self.get_parameter('profiles_file').value).parent/cfg['nav2_file']).resolve()
            nav=yaml.safe_load(path.read_text())['local_costmap']['local_costmap']['ros__parameters']
            polygon=nav['footprint']
            if isinstance(polygon,str):polygon=yaml.safe_load(polygon)
            self._footprint_guards[name]=(FootprintGuard(polygon,cfg),nav['robot_base_frame'],cfg)
            self.get_logger().info(f'Docking footprint guard: {name}, frame={nav["robot_base_frame"]}, polygon={polygon}')
        if self.base['autostart'] or not self.base['skip_staging'] or self.base['cam_auto']:
            raise ValueError('공통 서버는 autostart=false, skip_staging=true, cam_auto=false 필요')
        self.group=ReentrantCallbackGroup()
        self.lease=LeaseClient(self,self.group,'precision')
        self.tf=Buffer();self.listener=TransformListener(self.tf,self)
        self._observe_service=self.create_service(SetBool,'precision/observe_sorter',self.observe_sorter)
        self._harvest_route=None
        self._harvest_observe_service=self.create_service(SetBool,'precision/observe_harvest',self.observe_harvest)
        self._harvest_ready_pub=self.create_publisher(String,'precision/harvest_route_target',1)
        self.server=ActionServer(self,PrecisionMotion,'precision_motion',goal_callback=self.goal,
            cancel_callback=lambda h:CancelResponse.ACCEPT,execute_callback=self.execute,callback_group=self.group)

    def observe_sorter(self,request,response):
        # Observation only: never acquire a motion lease or publish a velocity.
        if not self._reservation.acquire(False):
            response.success=False;response.message='Precision motion is active';return response
        try:
            if self._session is not None:raise RuntimeError('Precision session active')
            if request.data:
                enabled=[p for p in self.profiles.values() if p.get('route_observation',{}).get('enabled')]
                if len(enabled)!=1:raise RuntimeError('Exactly one route observation profile required')
                self.activate_profile(enabled[0]);self.cam_on()
            else:self.cam_off()
            response.success=True;response.message='Observation enabled' if request.data else 'Observation disabled'
        except Exception as exc:
            response.success=False;response.message=str(exc)
        finally:self._reservation.release()
        return response

    def observe_harvest(self,request,response):
        if not self._reservation.acquire(False):
            response.success=False;response.message='Precision motion active';return response
        try:
            if self._session is not None:raise RuntimeError('Precision session active')
            self._harvest_route=None
            if request.data:
                candidates=[(name,p) for name,p in self.profiles.items() if p.get('route_handoff',{}).get('enabled')]
                if len(candidates)!=1:raise RuntimeError('Exactly one harvest route profile required')
                name,p=candidates[0]
                self.activate_profile(p);self.cam_on()
                self._harvest_route={'profile':name,'observation_start_ns':self.get_clock().now().nanoseconds,'observer_id':str(time.monotonic_ns()),'expires_at':self.motion_time()+p['route_handoff']['observation_timeout_s']}
            else:self.cam_off()
            response.success=True;response.message=self._harvest_route['observer_id'] if request.data else 'Harvest observation disabled'
        except Exception as exc:
            self._harvest_route=None;response.success=False;response.message=str(exc)
        finally:self._reservation.release()
        return response

    def update_harvest_route(self):
        route=self._harvest_route
        if route is None:return
        if self.motion_time()>route['expires_at']:
            self._harvest_ready_pub.publish(String(data=json.dumps(dict(
                observer_id=route['observer_id'],profile=route['profile'],
                stamp_ns=self.get_clock().now().nanoseconds,ready=False,expired=True,
                reason='Harvest route observation timed out'))))
            return  # 만료 상태를 상위가 정리할 때까지 반복 전달한다.
        p=self.profiles[route['profile']]
        now=self.get_clock().now().nanoseconds
        report=self._raw_reports[-1] if self._raw_reports else {}
        stamp=report.get('stamp_ns',0)
        age=(now-stamp)/1e9
        ready=(stamp>=route['observation_start_ns'] and
               0<=age<=p['route_handoff']['recognition_max_age_s'] and
               any(m.get('marker_id')==p['target_marker_id'] for m in report.get('markers',[])))
        reason='waiting for fresh target marker'
        if ready:
            # 도킹과 같은 입력 시각·최종 설정·거리 판정으로 전환 가능 여부만 확인한다.
            # 일회용 검사기의 목표/샘플은 버리고, 실제 목표는 정차 후 새로 취득한다.
            ready=False
            try:
                frame=p.get('entry',{}).get('odom_frame',self.get_parameter('odom_frame').value)
                captured=self.tf.lookup_transform(frame,p.get('base_frame',self.marker_base_frame),
                    Time(nanoseconds=stamp),timeout=Duration(seconds=0.))
                v,q=captured.transform.translation,captured.transform.rotation
                odom_base=transform_matrix((v.x,v.y,v.z),(q.x,q.y,q.z,q.w))
                controller=self._pose_controller
                checker=(StagedDockTracker(controller.target,controller.marker_id,p['target_tracking'],p['acquire_then_odom'])
                         if p.get('acquire_then_odom') else
                         FixedTargetTracker(controller.target,controller.marker_id,p['target_tracking']))
                # 정차 후 관측 변동을 위한 전환 여유. 실제 도킹의 허용범위는 변경하지 않는다.
                margin=float(p['route_handoff'].get('approach_margin_m',0.))
                limit=controller.c['max_planar_distance_m']
                if not math.isfinite(margin) or not 0<=margin<limit:
                    raise ValueError('Invalid route approach margin')
                ready=checker.update(report,odom_base,now,limit-margin,controller.c['max_tilt_rad'])
                reason='marker within approach envelope; stop before acquisition' if ready else checker.reason
            except (TransformException,ValueError,KeyError,TypeError) as exc:
                reason='waiting for valid route marker/TF: '+str(exc)
        if ready and not route.get('ready_logged'):
            route['ready_logged']=True
            self.get_logger().info(f"Harvest route marker recognized: id={p['target_marker_id']}; within approach envelope; stop Nav2 before taught target acquisition")
        self._harvest_ready_pub.publish(String(data=json.dumps(dict(
            observer_id=route['observer_id'],profile=route['profile'],stamp_ns=stamp,
            ready=bool(ready),reason=reason))))

    def odom_transit(self,p):
        return bool(p.get('acquire_then_odom') and getattr(self._target_tracker,'phase','') in ('TRANSIT','ALIGN'))

    def open_log(self):
        # 원본의 ~/wmany/logs 암묵적 쓰기를 없애고 명시한 실행 폴더만 사용한다.
        import csv
        folder=self.get_parameter('log_dir').value
        if not folder:return
        if self.log_f:self.log_f.close()
        path=Path(folder);path.mkdir(parents=True,exist_ok=True)
        self.log_path=str(path/f"dock_{self.site}_{time.time_ns()}.csv")
        self.log_f=open(self.log_path,'w');self.log=csv.writer(self.log_f)

    def on_cmd(self,message):
        # 기존 문자열 제어로 세션 검증과 속도 제어권을 우회하지 않는다.
        self.get_logger().warning('문자열 도킹 명령 비활성: precision_motion Action 사용')

    def ensure_K(self):
        # 다른 기종에 Waffle 카메라 보정값을 임의 적용하지 않는다.
        pass

    def fresh(self,message,limit=.5):
        age=(self.get_clock().now().nanoseconds-message.header.stamp.sec*10**9-message.header.stamp.nanosec)/1e9
        return 0<=age<=limit

    def sensor_age(self,name,m):
        self._header_ages[name]=(self.get_clock().now().nanoseconds-m.header.stamp.sec*10**9-m.header.stamp.nanosec)/1e9

    def sensor_inputs(self):
        # ROS messages are treated as immutable after reception. Copy references
        # and related timestamps atomically; never run TF/geometry under this lock.
        with self._sensor_lock:
            return dict(odom_at=self._odom_at,scan_at=self._scan_at,
                odom_stamp=self._odom_stamp,scan_stamp=self._last_scan_stamp,
                stopped_since=self._stopped_since,twist=self._measured_twist,
                odom=self._last_odom,scan=self._last_scan,scan_history=tuple(getattr(self,'_scan_history',())),gaps=dict(self._sensor_max_gap))

    def sensor_status(self):
        inputs=self.sensor_inputs();now=self.motion_time();ros_now=self.get_clock().now().nanoseconds
        parts=[]
        for name in ('odom','scan'):
            stamp=inputs[name+'_stamp']
            age=float('inf') if stamp is None else (ros_now-stamp)/1e9
            parts.append(f'{name}: accepted_age={now-inputs[name+"_at"]:.3f}s current_header_age={age:.3f}s')
        parts.append(f'image: accepted_age={now-self._image_at:.3f}s')
        return 'input_error='+self._input_error+'; '+', '.join(parts)

    def on_odom(self,m):
        if not self.fresh(m,self.odom_max_age_s):return
        stamp=m.header.stamp.sec*10**9+m.header.stamp.nanosec
        now=self.motion_time();v=m.twist.twist
        stopped=math.hypot(v.linear.x,v.linear.y)<.005 and abs(v.angular.z)<.02
        with self._sensor_lock:
            if self._odom_stamp is not None and stamp<=self._odom_stamp:return
            if self._odom_at:self._sensor_max_gap['odom']=max(self._sensor_max_gap['odom'],now-self._odom_at)
            self._odom_stamp=stamp;self._odom_at=now;self._last_odom=m
            self._measured_twist=(v.linear.x,v.angular.z)
            self._stopped_since=(self._stopped_since if self._stopped_since is not None else stamp) if stopped else None

    def on_scan(self,m):
        if not self.fresh(m,self.scan_max_age_s):return
        if not any(math.isfinite(x) and m.range_min<=x<=m.range_max or x==float('inf') for x in m.ranges):return
        stamp=m.header.stamp.sec*10**9+m.header.stamp.nanosec;now=self.motion_time()
        with self._sensor_lock:
            if self._last_scan_stamp is not None and stamp<=self._last_scan_stamp:return
            if self._scan_at:self._sensor_max_gap['scan']=max(self._sensor_max_gap['scan'],now-self._scan_at)
            self._scan_at=now;self._last_scan=m;self._last_scan_stamp=stamp
            self._scan_history=(*getattr(self,'_scan_history',()),m)[-8:]

    def update_legacy_sensors(self,inputs):
        # Legacy filtering/RANSAC stays in the control group, not the receive path.
        if inputs['odom'] is not None and inputs['odom_stamp']!=self._legacy_odom_stamp:
            super().on_odom(inputs['odom']);self._legacy_odom_stamp=inputs['odom_stamp']
        if inputs['scan'] is not None and inputs['scan_stamp']!=self._legacy_scan_stamp:
            super().on_scan(inputs['scan']);self._legacy_scan_stamp=inputs['scan_stamp']

    def on_info(self, message):
        if getattr(self, 'camera_backend', 'ros') == 'ros':
            super().on_info(message)

    def cam_on(self):
        if self._camera_enabled:
            return
        self._frames.clear()
        if self.camera_backend == 'picamera2':
            self._camera_input.start()
        else:
            from sensor_msgs.msg import Image
            self.img_sub = self.create_subscription(Image, self.base['image_topic'],
                self.on_image, self.img_qos, callback_group=self._image_group)
        with self._image_lock:
            self._camera_generation += 1
            self._camera_enabled = True

    def cam_off(self):
        if self.teach_buf is not None:
            return
        with self._image_lock:
            self._camera_generation += 1
            self._camera_enabled = False
            self._frames.clear()
        if self.img_sub is not None:
            self.destroy_subscription(self.img_sub)
            self.img_sub = None
        if self._camera_input is not None:
            self._camera_input.stop()
        self._frames.clear()
        self.meas = {}
        self._last_observation = None

    def on_image(self, message):
        # No conversion or detection in the ROS receive callback.
        with self._image_lock:
            if self._camera_enabled:
                stamp = message.header.stamp.sec * 10**9 + message.header.stamp.nanosec
                self._frames.put(Frame(message, stamp, message.header.frame_id, self.motion_time()))

    def consume_image(self):
        begin=time.monotonic()
        try:
            with self._profile_lock:self._consume_image_locked()
        finally:self._detection_max_ms=max(self._detection_max_ms,(time.monotonic()-begin)*1000.)

    def _consume_image_locked(self):
        if not self._camera_enabled or (self._session and 'lidar_stage' in self._session):
            return
        if self._camera_input is not None and self._camera_input.error:
            self._last_observation = None
            self.meas = {}; self.last_near = None; self.near_streak = 0
            if self._session and 'ending_at' not in self._session:
                self._camera_failure=(self._camera_generation,'Camera capture failed: '+self._camera_input.error)
            return
        generation = self._camera_generation
        frame = self._frames.take()
        if frame is None:
            return
        age = (self.get_clock().now().nanoseconds - frame.stamp_ns) / 1e9
        self._header_ages['image'] = age
        if not 0 <= age <= self.image_header_max_age_s:
            self._last_observation = None
            self.meas = {}; self.last_near = None; self.near_streak = 0
            return
        try:
            self._observations = {}
            self._frame_stamp_ns = frame.stamp_ns
            if self.pose_mode == 'tf_observe':
                if frame.frame_id != self.get_parameter('camera_frame_id').value:
                    raise ValueError('Image frame differs from configured optical camera frame')
                transform = self.tf.lookup_transform(self.marker_base_frame, frame.frame_id,
                    Time(nanoseconds=frame.stamp_ns), timeout=Duration(seconds=0.02))
                t=transform.transform.translation; q=transform.transform.rotation
                self._base_camera=transform_matrix((t.x,t.y,t.z),(q.x,q.y,q.z,q.w))
                self._tf_at=self.motion_time()
            if self.camera_backend == 'ros':
                gray = self.bridge.imgmsg_to_cv2(frame.pixels, desired_encoding='mono8')
            else:
                gray = cv2.cvtColor(frame.pixels, cv2.COLOR_BGR2GRAY)
            if self.pose_mode=='tf_observe':self.process_pose_image(gray)
            else:self.process_image(gray)
            # Do not mark an old frame fresh just because detection completed.
            age = (self.get_clock().now().nanoseconds - frame.stamp_ns) / 1e9
            if age > self.image_header_max_age_s or age < 0:
                self._last_observation = None
                self.meas = {}; self.last_near = None; self.near_streak = 0
                return
            if not self._camera_enabled or generation != self._camera_generation:
                return
            self._image_at = frame.received_at
            self._input_error = ''
            if self.pose_mode == 'tf_observe':
                report=dict(stamp_ns=frame.stamp_ns, source_frame=frame.frame_id,
                    frame_id=self.marker_base_frame, mode='observe_only',
                    processing_age_s=age, markers=list(self._observations.values()))
                if self._pose_controller is not None and not self._tracking_enabled:
                    with self._pose_lock:
                        preview = self._pose_controller.step(report, self.get_clock().now().nanoseconds)
                    preview.update(stamp_ns=frame.stamp_ns, command_sent=False)
                    report['control_preview'] = preview
                # Publish one complete immutable-by-convention snapshot, never a partial report.
                self._last_observation=report
                if self._tracking_enabled or getattr(self, '_observation_only', False):self._raw_reports=(*self._raw_reports,report)[-8:]
                self.observation_pub.publish(String(data=json.dumps(report)))
                if 'control_preview' in report:
                    self.control_preview_pub.publish(String(data=json.dumps(report['control_preview'])))
        except Exception as exc:
            self._input_error = str(exc)
            self._last_observation = None
            self.meas = {}; self.last_near = None; self.near_streak = 0
            if self._session and 'ending_at' not in self._session and not isinstance(exc,TransformException):
                self._camera_failure=(generation,'Camera processing failed: '+str(exc))

    def process_pose_image(self,gray):
        # Detection has no dependency on the motion FSM, including IDLE route observation.
        if hasattr(self,'detector'):corners,ids,_=self.detector.detectMarkers(gray)
        else:corners,ids,_=cv2.aruco.detectMarkers(gray,self.dict,parameters=self.params)
        if ids is None:return
        for points,marker in zip(corners,ids.flatten()):
            marker=int(marker)
            if marker not in self.obj:continue
            raw=self.solve(self.obj[marker],points.reshape(4,2).astype(np.float64),marker_id=marker)
            if raw is not None:self.meas[marker]=(raw,self.motion_time())

    def solve(self, obj, pixels, marker_id=None):
        if self.pose_mode != 'tf_observe':
            return super().solve(obj, pixels, marker_id=marker_id)
        if self._base_camera is None:
            raise RuntimeError('Camera TF is unavailable')
        if self._pose_controller is not None and marker_id == self._pose_controller.marker_id:
            # Refuse a target taught at a different physical marker size.
            import numpy as np
            if not math.isclose(float(np.linalg.norm(obj[1]-obj[0])), self._pose_controller.size, rel_tol=1e-5):
                raise ValueError('Target marker size differs from detector profile')
        solution=solve_marker(obj,pixels,self.K,self.D)
        if solution is None:return None
        error,rv,tv,p,rotation=solution
        observation=compose_marker(self._base_camera,rv,tv)
        observation.update(marker_id=marker_id,reprojection_error_px=error,
            camera_range_m=float((tv.reshape(3)**2).sum()**0.5))
        self._observations[marker_id]=observation
        # Legacy-shaped measurements are retained only for TAG detection.
        # Marker-pose DOCK uses the selected base-frame target, not these
        # camera-axis measurements retained for legacy TAG detection.
        return dict(dist=float(p[2]),lat=float(p[0]),
            psi=math.atan2(rotation[2,0],-rotation[2,2]))

    def destroy_node(self):
        self.teach_buf = None
        self.cam_off()
        self.lease.close()
        super().destroy_node()

    def goal(self,q):
        p=self.profiles.get(q.profile_id,{})
        if not p.get('configured'):return GoalResponse.REJECT
        independent = p.get('observation_only') or p.get('relative_backout')
        if independent:
            try:
                from .harvest_motion import validate_independent_profile
                validate_independent_profile(p, q.operation)
                if p.get('observation_only'):LidarApproach(p['lidar_approach'])
            except (ValueError, KeyError, TypeError) as exc:
                self.get_logger().warning('Harvest profile invalid: '+str(exc))
                return GoalResponse.REJECT
        pose_dock=p.get('strategy')=='marker_pose' and q.operation in ('DOCK','CLEAR')
        if pose_dock and not independent:
            try:
                target,controller=marker_profile(p,self.get_parameter('pose_control_file').value,self.marker_base_frame)
                if p.get('departure') and (q.operation!='CLEAR' or not p.get('target_tracking',{}).get('enabled')):raise ValueError('departure requires tracked CLEAR')
                if q.operation not in p.get('allowed_operations',['DOCK']):raise ValueError('operation not enabled for this profile')
                if q.operation=='CLEAR':
                    if target.get('status')!='taught':raise ValueError('clearance target is not taught')
                    if p.get('entry',{}).get('enabled'):raise ValueError('marker clearance must not run station entry')
                    if not p.get('collision_guard'):raise ValueError('marker clearance requires footprint collision checking')
                if not self.pose_output_enabled or self.pose_mode!='tf_observe':raise ValueError('pose output/mode disabled')
                if not p.get('bounded_trial') and (not p.get('approach_clearance_verified') or not p.get('extrinsics_verified')):
                    raise ValueError('physical approach not configured')
                if not p.get('collision_guard') and (not math.isfinite(p.get('scan_stop_range_m',float('nan'))) or p.get('scan_stop_range_m',0)<=0):
                    raise ValueError('collision check not configured')
            except (KeyError,ValueError,TypeError,OSError) as exc:
                self.get_logger().warning('Marker motion profile invalid: '+str(exc))
                return GoalResponse.REJECT
        if self.pose_mode == 'tf_observe' and q.operation == 'DOCK' and not pose_dock:
            self.get_logger().warning('TF 관측 모드: 로봇 기준 목표 자세 검증 전 DOCK 비활성')
            return GoalResponse.REJECT
        p=self.profiles.get(q.profile_id,{})
        if not p.get('configured') or p.get('strategy') not in ('legacy_aruco','marker_pose'):return GoalResponse.REJECT
        if p.get('strategy')=='marker_pose' and not pose_dock:return GoalResponse.REJECT
        if q.operation not in ('TAG','DOCK','CLEAR') or not q.session_id:return GoalResponse.REJECT
        if self.base['dry_run']:return GoalResponse.REJECT
        if q.operation=='CLEAR' and not pose_dock:
            g=q.clearance_pose
            if g.frame_id!='map' or abs(g.position.z)>1e-6 or not all(math.isfinite(x) for x in (g.position.x,g.position.y,g.yaw)):
                return GoalResponse.REJECT
            if not p.get('clearance_corridor_verified'):return GoalResponse.REJECT
        if q.target_marker_id>=0 and q.target_marker_id!=p['target_marker_id']:return GoalResponse.REJECT
        if q.docking_marker_id>=0 and q.docking_marker_id!=p['docking_marker_id']:return GoalResponse.REJECT
        if p.get('entry',{}).get('enabled'):
            g=q.clearance_pose
            if q.operation!='DOCK' or g.frame_id!='map' or abs(g.position.z)>1e-6 or not all(math.isfinite(v) for v in (g.position.x,g.position.y,g.yaw)):
                return GoalResponse.REJECT
            try:StationEntry(p['entry'])
            except (KeyError,ValueError):return GoalResponse.REJECT
        if not self._reservation.acquire(False):return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def activate_profile(self,p):
        # One physical camera / motion owner, selected per accepted action.
        with self._profile_lock:
            self._camera_failure=None
            self._observation_only=bool(p.get('observation_only'))
            self._tracking_enabled=bool(p.get('target_tracking',{}).get('enabled',False))
            self._raw_reports=();self._tracking_preview=None;self._tracking_last_odom=None
            if p.get('runtime_config') == 'profile':
                # Action owns the movement plan; legacy site files are not execution gates.
                if p.get('strategy') != 'marker_pose':
                    raise ValueError('Independent runtime requires marker_pose strategy')
                self.c=dict(self.base)
                self.c.update(skip_staging=True,autostart=False,cam_auto=False)
                self.site=p.get('runtime_name', 'precision')
                self.site_desc=p.get('note', '')
                self.use_nav=False
                self._pose_controller=None
                self._target_tracker=None
                self._target_extrinsics=None
            elif not self.select_site(p['legacy_site']):
                raise RuntimeError('기존 도킹 프로파일 없음')
            if p.get('observation_only') or p.get('relative_backout'):
                self._tracking_enabled=False
                self._pose_controller=None
                self._target_tracker=None
                marker=p['target_marker_id']
                self.obj={marker:self.square(p['marker_installation']['marker_size_m'])}
                self.c['near_id']=marker
                self._last_observation=None;self._observations={}
            elif p.get('strategy')=='marker_pose':
                target,controller=marker_profile(p,self.get_parameter('pose_control_file').value,self.marker_base_frame)
                with self._pose_lock:
                    self._pose_controller=controller
                    self._target_extrinsics=np.asarray(target.get('camera_extrinsics_T_base_camera',[]),dtype=float)
                # Single-marker geometry comes from the selected taught target,
                # independent of the legacy far/near pair sizes and IDs.
                if self._tracking_enabled:
                    if not p['target_tracking'].get('fixed_target'):raise ValueError('Odom prediction requires a fixed target')
                    self._target_tracker=(DepartureTracker(controller.target,controller.marker_id,p['target_tracking'],p['departure']) if p.get('departure') else FixedTargetTracker(controller.target,controller.marker_id,p['target_tracking']))
                    if p.get('acquire_then_odom'):
                        self._target_tracker=StagedDockTracker(controller.target,controller.marker_id,p['target_tracking'],p['acquire_then_odom'])
                self.obj={controller.marker_id:self.square(controller.size)}
                self.c['near_id']=controller.marker_id
                self._last_observation=None;self._observations={}
                self.get_logger().info(f'Marker profile selected: target={p["pose_target"]}, id={controller.marker_id}, size={controller.size:.3f}m, direction={controller.c["direction"]}')

    def motion_time(self) -> float:
        """동작 예산: 시뮬은 ROS /clock, 실물은 기존 단조 증가 실제시간."""
        if self.get_parameter('use_sim_time').value:
            return self.get_clock().now().nanoseconds/1e9
        return time.monotonic()

    def motion_elapsed(self, started: float) -> float:
        elapsed=self.motion_time()-started
        if elapsed<0:raise RuntimeError('Motion clock moved backwards; restart the action')
        return elapsed

    def execute(self,handle):
        session={'handle':handle,'done':Event(),'error':'','candidate':False,'started':self.motion_time(),'motion_started':self.motion_time()}
        self._pending.put(('start',session))
        while not session['done'].wait(.03):
            if handle.is_cancel_requested or self.motion_time()-session['motion_started']>120:
                self._pending.put(('stop',session))
        result=PrecisionMotion.Result()
        result.stopped=self.stopped()
        result.success=session['candidate'] and not session['error'] and result.stopped and not handle.is_cancel_requested
        result.error_message=session['error']
        # 접근 전 거리 거절만 복구 계약으로 전달한다. 취소/정지/lease 해제 실패는 제외한다.
        if (not result.success and not handle.is_cancel_requested and result.stopped
                and session.get('approach_reentry_error') == session['error']
                and session.get('approach_reentry_error') and session.get('lease_released')):
            from .initial_marker_recovery import ApproachReentryRequired
            result.error_message=ApproachReentryRequired.prefix+result.error_message
        # 명시적인 진입 전 실패 + 정지 확인만 자동 복구 증거로 전달한다.
        elif (not result.success and result.stopped and session.get('entry_controller') is not None
                and not session.get('entry_complete') and not session.get('entry_motion_started')
                and session.get('lease_released')):
            result.error_message='PRE_ENTRY_STOPPED: '+result.error_message
        try:
            if handle.is_cancel_requested and result.stopped:handle.canceled()
            elif result.success:handle.succeed()
            else:handle.abort()
            return result
        finally:self._reservation.release()

    def stopped(self):
        inputs=self.sensor_inputs()
        return (self.motion_time()-inputs['odom_at']<self.odom_max_age_s and inputs['stopped_since'] is not None
            and inputs['odom_stamp']-inputs['stopped_since']>=800000000)

    def finish(self,state,why):
        if self._session is None:return super().finish(state,why)
        if 'ending_at' in self._session:
            if state != DONE:
                self._session['candidate']=False
                self._session['error']=why
            return
        # 원본의 timeout/센서 없음/횟수 초과/Dry-run 성공을 업무 성공으로 승격하지 않는다.
        if state==DONE and any(x in why for x in ('초과','끊김','없음','상한','DRY RUN','생략')):
            state=FAILED
        self.drive(0.,0.,force=True)
        self.state=IDLE
        if state==DONE:self._session['candidate']=True
        else:self._session['error']=why;self._session['candidate']=False
        self.get_logger().info(f'정밀주행 종료: {state} / {why} / {self.sensor_status()}')
        self._session['ending_at']=self.motion_time()

    def complete(self):
        s=self._session
        try:
            self.lease.release()
            s['lease_released']=True
        except Exception as exc:s['error']=str(exc)
        try:self.cam_off()
        except Exception as exc:s['error']='Camera shutdown failed: '+str(exc)
        finally:
            self.state=IDLE;self._session=None;s['done'].set()

    def verify_dock(self,p):
        near=self.get(self.c['near_id'])
        if near is None:return False
        lateral=abs(near['lat']-self.lat_ref)<=self.c['tol_lat']
        distance=abs(near['dist']-self.dist_ref)<=p.get('distance_tolerance_m',.02)
        yaw=abs(near['psi']-self.yaw_ref)<=math.radians(self.c['tol_yaw_deg'])
        if math.isfinite(self.lidar_target):
            yaw=self.lidar_fresh(.5) and abs(self.lidar_buf[-1][1]-self.lidar_target)<=self.c['lidar_tol_deg']
        if math.isfinite(self.c['push_to_dist']):
            distance=self.lidar_fresh(.5) and abs(self.lidar_buf[-1][2]-self.c['push_to_dist'])<=p.get('distance_tolerance_m',.02)
        return lateral and distance and yaw

    def loop(self):
        begin=time.monotonic()
        gap=begin-getattr(self,'_diag_previous_tick',begin)
        self._diag_previous_tick=begin
        if self._session and gap>.2:
            self.get_logger().warning(f'Control scheduling gap: {gap*1000:.1f}ms')
        try:self.control_tick()
        finally:
            now=time.monotonic();self._loop_max_ms=max(self._loop_max_ms,(now-begin)*1000.)
            if now-self._timing_at>=5.:
                inputs=self.sensor_inputs()
                if self._session:
                    self.get_logger().info(f'Control timing: max_tick={self._loop_max_ms:.1f}ms, detection_max={self._detection_max_ms:.1f}ms, odom_max_gap={inputs["gaps"]["odom"]:.3f}s, scan_max_gap={inputs["gaps"]["scan"]:.3f}s')
                with self._sensor_lock:self._sensor_max_gap={'odom':0.,'scan':0.}
                self._loop_max_ms=0.;self._detection_max_ms=0.;self._timing_at=now

    def departure_locked(self,p):
        return bool(p.get('departure') and getattr(self._target_tracker,'locked',False))

    def control_tick(self):
        inputs=self.sensor_inputs()
        self.update_legacy_sensors(inputs)
        try:
            while True:
                command,s=self._pending.get_nowait()
                if command=='start':
                    self._session=s;q=s['handle'].request;p=self.profiles[q.profile_id]
                    route=self._harvest_route
                    self._harvest_route=None
                    # Always discard in-motion frames/estimates. Nav2 cancellation has
                    # already waited for measured stop before this action is dispatched.
                    self.activate_profile(p)
                    if route and route['profile']==q.profile_id:
                        self.get_logger().info('Harvest handoff: acquiring fresh taught target after Nav2 stop')
                    self.lease.acquire()
                    self.meas={};self.last_near=None;self.lidar_buf.clear()
                    self.face_deg=None
                    self._image_at=0.
                    self._last_observation=None
                    s['observation_start_ns']=self.get_clock().now().nanoseconds
                    if self._pose_controller is not None:
                        with self._pose_lock:self._pose_controller.reset()
                    if not (p.get('distance_departure') or p.get('relative_backout')) and (q.operation in ('TAG','DOCK') or p.get('strategy')=='marker_pose'):self.cam_on()
                    s['preparing_at']=self.motion_time()
                    if p.get('entry',{}).get('enabled'):
                        s['entry_controller']=StationEntry(p['entry']);s['entry_started']=self.motion_time()
                    self.state='WAIT_SENSORS'
                    feedback=PrecisionMotion.Feedback();feedback.phase=self.state;s['handle'].publish_feedback(feedback)
                    self.drive(0.,0.,force=True)
                    return
                elif s is self._session:self.finish(FAILED,'취소 또는 제한시간 초과')
        except Empty:pass
        except Exception as exc:
            if self._session:self.finish(FAILED,str(exc))
        s=self._session
        if not s:
            self.update_harvest_route()
            return
        q=s['handle'].request;p=self.profiles[q.profile_id]
        try:
            if 'parking_started' not in s and not (p.get('distance_departure') or p.get('relative_backout')) and not p.get('distance_heading_trial') and 'ending_at' not in s and 'graph_return_stage' not in s and 'lidar_stage' not in s and 'exit_alignment' not in s and self._tracking_enabled and s.get('entry_complete', 'entry_controller' not in s) and 'preparing_at' not in s:
                self.update_target_control(s,p)
            if 'ending_at' in s:
                try:
                    if s.get('candidate') and 'parking_started' in s:
                        _,done=self.parking_status(s,p)
                        if not done:s['candidate']=False;s['error']='Parking heading lost during stop confirmation'
                    self.drive(0.,0.,force=True)
                    if s.get('candidate') and 'exit_alignment' in s:
                        _,done=self.exit_heading_status(s,p)
                        if not done:s['candidate']=False;s['error']='Exit heading lost during stop confirmation'
                    if s.get('candidate') and 'lidar_stage' in s:
                        _,_,done,_=self.lidar_status(s,p)
                        if not done:s['candidate']=False;s['error']='Final lidar distance lost during stop confirmation'
                    if 'parking_started' not in s and not (p.get('distance_departure') or p.get('relative_backout')) and s.get('candidate') and 'lidar_stage' not in s and 'exit_alignment' not in s and p.get('strategy')=='marker_pose':
                        final=(self._tracking_preview or {}) if self._tracking_enabled else (self._last_observation or {}).get('control_preview',{})
                        age=(self.get_clock().now().nanoseconds-final.get('stamp_ns',0))/1e9
                        if not final.get('at_target') or not 0<=age<=self.image_header_max_age_s:
                            s['candidate']=False;s['error']='Pose target lost during stop confirmation'
                except Exception as exc:
                    s['candidate']=False
                    s['error']='Final validation failed: '+str(exc)
                if self.stopped() or self.motion_time()-s['ending_at']>3.:
                    if not self.stopped():s['error']='정지 odom 확인 실패: '+s.get('error','')
                    self.complete()
                return
            if 'parking_started' in s:
                self.lease.check()
                if self.motion_time()-inputs['odom_at']>self.odom_max_age_s or self.motion_time()-inputs['scan_at']>self.scan_max_age_s:raise RuntimeError('Parking odom/scan stale')
                self.run_parking(s,p)
                return
            if not (p.get('distance_departure') or p.get('relative_backout')) and 'lidar_stage' not in s and not self.odom_transit(p) and self._camera_failure and self._camera_failure[0]==self._camera_generation:
                raise RuntimeError(self._camera_failure[1])
            self.lease.check()
            if self.motion_elapsed(s['motion_started'])>p.get('timeout_s',90.):raise TimeoutError('정밀주행 시간 초과')
            if 'recovery_wait' in s:
                self.run_recovery(s,p)
                return
            if 'preparing_at' in s:
                self.drive(0.,0.,force=True)
                now=self.motion_time()
                ready=now-inputs['odom_at']<=self.odom_max_age_s and now-inputs['scan_at']<=self.scan_max_age_s and self.stopped()
                if not (p.get('distance_departure') or p.get('relative_backout')) and (q.operation in ('TAG','DOCK') or p.get('strategy')=='marker_pose'):ready=ready and self.K is not None and now-self._image_at<=self.image_receive_timeout_s
                if not ready:
                    if now-s['preparing_at']>self.get_parameter('sensor_ready_timeout_s').value:
                        raise Recoverable('SENSORS',f'센서 준비 대기 (CameraInfo={self.K is not None}): {self.sensor_status()}')
                    return
                del s['preparing_at']
                if q.operation=='DOCK' or p.get('strategy')=='marker_pose':
                    if p.get('strategy')=='marker_pose':self.state='POSE_ALIGN'
                    else:self.start()
                elif q.operation=='TAG':self.state=SEARCH
                else:self.state='CLEAR'
            if self.motion_time()-inputs['odom_at']>self.odom_max_age_s or self.motion_time()-inputs['scan_at']>self.scan_max_age_s:raise Recoverable('SENSORS','odom/scan 최신성 상실: '+self.sensor_status())
            if not (p.get('distance_departure') or p.get('relative_backout')) and (q.operation in ('DOCK','TAG') or p.get('strategy')=='marker_pose') and self.K is None:raise RuntimeError('CameraInfo 보정값 필요')
            if not (p.get('distance_departure') or p.get('relative_backout')) and 'lidar_stage' not in s and not self.departure_locked(p) and not self.odom_transit(p) and (q.operation in ('TAG','DOCK') or p.get('strategy')=='marker_pose') and self.motion_time()-s['started']>3. and self.motion_time()-self._image_at>(p['target_tracking']['max_prediction_s'] if self._tracking_enabled else self.image_receive_timeout_s):
                raise Recoverable('CAMERA','카메라 영상 단절: '+self.sensor_status())
            if self.run_initial_marker_recovery(s, p):
                return
            if p.get('distance_departure'):
                self.run_distance_departure(s,p)
                return
            if p.get('relative_backout'):
                self.run_relative_backout(s,p)
                return
            if p.get('distance_heading_trial') and 'lidar_stage' not in s:
                self.run_distance_heading_trial(s,p)
                return
            if 'graph_return_stage' in s and 'exit_alignment' not in s:
                self.run_graph_return(s,p)
                return
            if p.get('marker_backout') and not self.departure_locked(p):
                self.run_marker_backout(s,p)
                return
            if 'lidar_stage' in s:
                self.run_lidar_approach(s,p)
                return
            if 'exit_alignment' in s:
                self.run_exit_heading(s,p)
                return
            if q.operation=='TAG':
                self.drive(0.,0.,force=True)
                if self.get(p['target_marker_id']) is not None:
                    s['candidate']=True;s['ending_at']=self.motion_time()
            elif q.operation=='CLEAR' and p.get('strategy')!='marker_pose':
                t=self.tf.lookup_transform('map',p.get('base_frame','base_footprint'),Time(),timeout=Duration(seconds=.02))
                if not self.fresh(t):raise RuntimeError('이격 map TF 만료')
                v=t.transform.translation;r=t.transform.rotation
                yaw=math.atan2(2*(r.w*r.z+r.x*r.y),1-2*(r.y*r.y+r.z*r.z))
                g=q.clearance_pose
                linear,angular,done=reverse_to_pose((v.x,v.y,yaw),(g.position.x,g.position.y,g.yaw))
                # 이격 통로의 실제 후방 물체가 있으면 정지. 원본의 20cm 무시 조건을 쓰지 않는다.
                scan=inputs['scan']
                if any(math.isfinite(rng) and scan.range_min<=rng<p['rear_stop_m'] and
                       abs(math.atan2(math.sin(scan.angle_min+i*scan.angle_increment-math.pi),math.cos(scan.angle_min+i*scan.angle_increment-math.pi)))<.6
                       for i,rng in enumerate(scan.ranges)):
                    raise RuntimeError('이격 후방 장애물')
                self.drive(linear,angular)
                if done:s['candidate']=True;s['ending_at']=self.motion_time()
            elif p.get('strategy')=='marker_pose':
                if self.motion_elapsed(s['motion_started'])>p.get('timeout_s',90.):raise TimeoutError('정밀주행 시간 초과')
                if p.get('bounded_trial'):self.check_trial_extrinsics()
                if 'entry_controller' in s and not s.get('entry_complete'):
                    self.run_entry(s,q,p)
                    return
                if p.get('departure') and not self.departure_locked(p):
                    self.drive(0.,0.,force=True)
                    self.phase_feedback(s,'ACQUIRE_DEPARTURE_TARGET')
                    s.setdefault('departure_acquire_at',self.motion_time())
                    if self.motion_time()-s['departure_acquire_at']>p['departure']['acquire_timeout_s']:
                        raise RuntimeError('stable departure target acquisition timed out')
                    return
                observation=self._last_observation or {}
                preview=self._tracking_preview if self._tracking_enabled else observation.get('control_preview')
                now=self.motion_time()
                if (not preview or preview.get('stamp_ns',0)<s['observation_start_ns'] or
                        not 0<=(self.get_clock().now().nanoseconds-preview.get('stamp_ns',0))/1e9<=(self.odom_max_age_s if p.get('acquire_then_odom') else self.image_header_max_age_s) or
                        preview.get('phase')=='WAIT_OBSERVATION'):
                    self.drive(0.,0.,force=True)
                    if 'approach_gate' in s and s['approach_gate'].phase!='FRESH':
                        s['approach_gate'].phase='STOP'
                    s.setdefault('marker_wait_since',now)
                    self.phase_feedback(s,'ACQUIRE_MARKER')
                    if self.motion_time()-s.get('awaiting_recovery_frame',-1e9)<.5:return
                    reason='MARKER' if preview and preview.get('reason')=='target marker not visible' else 'OBSERVATION'
                    raise Recoverable(reason,'마커 재관측 대기: '+str(dict(reason=(preview or {}).get('reason','missing preview'),phase=(preview or {}).get('phase'),stamp_ns=(preview or {}).get('stamp_ns'),required_after_ns=s['observation_start_ns'])))
                s.pop('marker_wait_since',None)
                s.pop('awaiting_recovery_frame',None)
                gate=s.setdefault('approach_gate',ApproachGate(p.get('approach',{})))
                decision='MOVE' if p.get('acquire_then_odom',{}).get('distance_corridor') else gate.step(preview,self.stopped(),self.get_clock().now().nanoseconds)
                if decision=='STOP':
                    self.drive(0.,0.,force=True)
                    self.phase_feedback(s,'VERIFY_APPROACH_STOP')
                    return
                if decision=='FRESH':
                    self.drive(0.,0.,force=True)
                    with self._pose_lock:self._pose_controller.reset()
                    self._last_observation=None
                    s['awaiting_recovery_frame']=self.motion_time()
                    s['observation_start_ns']=self.get_clock().now().nanoseconds
                    self.phase_feedback(s,'REOBSERVE_TARGET')
                    return
                linear,angular,done=pose_command(preview,self.get_clock().now().nanoseconds,
                    session_start_ns=s['observation_start_ns'],
                    marker_id=self._pose_controller.marker_id,expected_marker_id=p['docking_marker_id'],
                    output_enabled=self.pose_output_enabled,
                    odom_fresh=now-inputs['odom_at']<=self.odom_max_age_s,
                    scan_fresh=now-inputs['scan_at']<=self.scan_max_age_s,
                    lease_ok=bool(self.lease.token) and not self.lease.failed,
                    cancelled=s['handle'].is_cancel_requested,
                    clearance_verified=p.get('approach_clearance_verified',False) or p.get('bounded_trial',False),
                    max_age=self.odom_max_age_s if p.get('acquire_then_odom') else self.image_header_max_age_s)
                # No blind continuation. Missing marker/TF aborts above.
                if decision=='ALIGN_HEADING':
                    # Sorter opt-in: taught orientation before translating toward the pose.
                    # pose_command above still enforces freshness, lease and cancellation.
                    linear=0.
                    c=self._pose_controller.c
                    angular=max(-c['max_angular_rps'],min(c['max_angular_rps'],
                        c['angular_pid']['kp']*preview['error_yaw_rad']))
                    if angular:angular=math.copysign(max(abs(angular),c.get('min_angular_rps',0.)),angular)
                    done=False
                    self.state='ALIGN_TAUGHT_HEADING'
                elif decision=='ALIGN':
                    linear=0.
                    self.state='ALIGN_TARGET'
                else:self.state=preview['phase']
                if linear or angular:
                    self.scan_clearance(p)
                self.drive(linear,angular)
                if done and self.stopped():
                    if q.operation=='DOCK' and p.get('parking',{}).get('enabled'):
                        self.begin_parking(s,p)
                    elif p.get('lidar_approach'):
                        self.begin_lidar_approach(s,p)
                    elif p.get('graph_return'):
                        self.prepare_graph_return(s,p)
                        s['graph_return_stage']=True;s['graph_return_started']=self.motion_time()
                        self.phase_feedback(s,'REVERSE_TO_EXIT_NODE')
                    elif p.get('departure',{}).get('alignment_mode')=='face_graph_node':
                        s['exit_alignment']=True;s['exit_started']=self.motion_time()
                        self.phase_feedback(s,'ALIGN_EXIT_NODE')
                    else:self.finish(DONE,('Marker approach distance reached and stopped' if p.get('acquire_then_odom',{}).get('distance_corridor') else ('Marker clearance' if q.operation=='CLEAR' else 'Marker pose')+' within tolerance and stopped'))
            else:
                super().loop()
                if s.get('candidate') and not self.verify_dock(p):
                    s['candidate']=False;s['error']='최종 거리/정렬 실측 검증 실패'
            if s.get('last_phase')!=self.state:
                feedback=PrecisionMotion.Feedback();feedback.phase=self.state;s['handle'].publish_feedback(feedback);s['last_phase']=self.state
            if self.motion_elapsed(s['motion_started'])>p.get('timeout_s',90.):raise TimeoutError('정밀주행 시간 초과')
        except (Recoverable,TransformException) as exc:
            if 'parking_started' in s:
                self.finish(FAILED,'Parking rotation: '+str(exc));return
            if self.wait_lidar_inputs(s,p,exc):return
            if 'lidar_stage' in s or (p.get('marker_backout') and not self.departure_locked(p)):self.finish(FAILED,str(exc))
            elif p.get('recovery') and (q.operation=='DOCK' or p.get('strategy')=='marker_pose'):self.pause_recovery(s,p,exc)
            else:self.finish(FAILED,str(exc))
        except Exception as exc:
            if self.wait_lidar_inputs(s,p,exc):return
            self.finish(FAILED,str(exc))

    def wait_lidar_inputs(self,s,p,exc):
        if 'lidar_stage' not in s:return False
        transient=(isinstance(exc,(TransformException,ScanFreshnessError))
            or (isinstance(exc,Recoverable) and exc.reason in ('TF','SENSORS'))
            or str(exc) in ('Final approach odom TF stale','Surface tracking odom stale','No raw front scan')
            or any(tag in str(exc) for tag in ('TARGET_SURFACE_NO_MATCHED_SCAN','COLLISION_PAIR_SCAN_STALE')))
        if not transient:return False
        self.drive(0.,0.,force=True)
        s['lidar_controller'].good_since=None
        started=s.setdefault('lidar_input_wait_since',self.motion_time())
        s.setdefault('lidar_input_wait_motion',self.motion_time())
        self.log_scan_delay(s,exc)
        self.phase_feedback(s,'WAIT_LIDAR_INPUTS')
        if self.motion_time()-started>p['lidar_approach'].get('stale_wait_s',1.):
            self.finish(FAILED,'Lidar input wait timeout: '+str(exc))
        return True

    def update_target_control(self,s,p):
        now_ns=self.get_clock().now().nanoseconds
        frame=p.get('entry',{}).get('odom_frame',self.get_parameter('odom_frame').value)
        base=p.get('base_frame',self.marker_base_frame)
        def matrix(t):
            v,q=t.transform.translation,t.transform.rotation
            return transform_matrix((v.x,v.y,v.z),(q.x,q.y,q.z,q.w))
        tracker=self._target_tracker
        for report in (() if self.departure_locked(p) or (p.get('acquire_then_odom',{}).get('odom_only_after_acquire') and self.odom_transit(p) and not (p['acquire_then_odom'].get('visual_correction_during_transit') and tracker.phase=='TRANSIT')) else reversed(self._raw_reports)):
            if p.get('acquire_then_odom') and self._target_tracker.phase in ('ACQUIRE','VERIFY') and not self.stopped():continue
            if report['stamp_ns']<s['observation_start_ns']:continue
            if tracker.last_attempt is not None and report['stamp_ns']<=tracker.last_attempt:continue
            try:
                captured=self.tf.lookup_transform(frame,base,Time(nanoseconds=report['stamp_ns']),timeout=Duration(seconds=0.))
            except TransformException:continue
            tracker.update(report,matrix(captured),self.get_clock().now().nanoseconds,self._pose_controller.c['max_planar_distance_m'],self._pose_controller.c['max_tilt_rad'])
            # One newest transformable report per tick; do not replay the camera backlog.
            break
        if self.departure_locked(p) and not s.get('departure_lock_logged'):
            s['departure_lock_logged']=True
            self.get_logger().info(f'Departure target locked in odom: x={tracker.goal[0,3]:.3f}, y={tracker.goal[1,3]:.3f}; arrival radius={self._pose_controller.c["position_tolerance_m"]:.3f}m; no final yaw alignment')
        try:
            current=self.tf.lookup_transform(frame,base,Time(),timeout=Duration(seconds=0.))
            if not self.fresh(current,self.odom_max_age_s):raise Recoverable('TF','target tracking odom stale')
            stamp=current.header.stamp.sec*10**9+current.header.stamp.nanosec
            now_ns=self.get_clock().now().nanoseconds
            estimated,reason=tracker.observation(matrix(current),stamp,now_ns)
        except (TransformException,Recoverable) as exc:
            estimated=None;reason=str(exc)
        if estimated is None:
            self._tracking_preview=dict(phase='WAIT_OBSERVATION',reason=reason,stamp_ns=now_ns)
            self.log_target_control(s,self._tracking_preview,tracker)
            return
        if p.get('acquire_then_odom',{}).get('odom_only_after_acquire') and self.odom_transit(p) and not s.get('frozen_goal_logged'):
            s['frozen_goal_logged']=True
            policy=('marker translation stand-off; bounded steering; odom continuation without search' if p['acquire_then_odom'].get('distance_corridor') else 'bounded visual correction during transit; freeze for terminal alignment' if p['acquire_then_odom'].get('visual_correction_during_transit') else 'no visual correction or final reacquisition')
            self.get_logger().info(f'Dock goal acquired in odom: x={tracker.goal[0,3]:.4f}, y={tracker.goal[1,3]:.4f}; {policy}')
        if getattr(self,'_tracking_last_odom',None)==stamp and self._tracking_preview and self._tracking_preview.get('phase')!='WAIT_OBSERVATION':return
        self._tracking_last_odom=stamp
        distance_cfg=p.get('acquire_then_odom',{}).get('distance_corridor')
        with self._pose_lock:
            now_ns=self.get_clock().now().nanoseconds
            if distance_cfg:
                marker=estimated['markers'][0]
                matrix_marker=np.eye(4)
                matrix_marker[:3,:3]=marker['marker_rotation_in_base']
                matrix_marker[:3,3]=marker['marker_position_in_base_m']
                relative=matrix_marker@self._pose_controller.target
                preview=dict(error_x_m=float(relative[0,3]),error_y_m=float(relative[1,3]),
                    error_yaw_rad=math.atan2(relative[1,0],relative[0,0]),at_target=False)
                from .staged_dock import distance_corridor_command
                preview.update(distance_corridor_command(preview,distance_cfg))
            else:
                preview=self._pose_controller.step(estimated,now_ns, **({'max_age':self.odom_max_age_s} if p.get('acquire_then_odom') else {}))
        continuous=p.get('acquire_then_odom',{}).get('continuous_visual_handoff',False)
        if continuous and self.odom_transit(p) and preview.get('phase')!='WAIT_OBSERVATION':
            from .staged_dock import visual_line_command
            preview.update(visual_line_command(preview,p['pose_path'],p['lidar_entry_alignment']))
        elif not distance_cfg and self.odom_transit(p) and preview.get('phase')!='WAIT_OBSERVATION':
            from .staged_dock import transit_command, frozen_alignment
            preview.update(frozen_alignment(preview,self._pose_controller.c) if tracker.phase=='ALIGN' else transit_command(preview,p['pose_path']))
        elif not distance_cfg and p.get('pose_path'):
            path_command=pose_path_command(preview,p['pose_path'])
            if path_command:preview.update(path_command)
        if p.get('acquire_then_odom',{}).get('hybrid_relative_control') and preview.get('phase')!='WAIT_OBSERVATION':
            source=estimated.get('tracking_source','FINAL_ALIGNMENT')
            scale=estimated.get('tracking_speed_scale',1.)
            if tracker.phase=='TRANSIT':
                # Scale both velocities to preserve the commanded curvature.
                preview['linear_x']*=scale;preview['angular_z']*=scale
            else:source='FINAL_ALIGNMENT'
            preview.update(tracking_source=source,tracking_speed_scale=scale)
        entry_preview=preview
        if continuous and preview.get('phase')!='WAIT_OBSERVATION':
            x,y,a=(preview[k] for k in ('error_x_m','error_y_m','error_yaw_rad'))
            entry_preview=dict(preview,error_x_m=math.cos(a)*x+math.sin(a)*y,
                error_y_m=-math.sin(a)*x+math.cos(a)*y)
        near=near_entry_command(entry_preview,p.get('lidar_entry_alignment'),self._pose_controller.c)
        if self.odom_transit(p) and not continuous:near=None
        elif p.get('acquire_then_odom') and preview.get('phase')!='WAIT_OBSERVATION':
            if near:s['terminal_alignment_latched']=True
            elif s.get('terminal_alignment_latched'):
                c=dict(p['lidar_entry_alignment'])
                c['lateral_tolerance_m']*=2
                c['forward_tolerance_m']*=1.5
                near=near_entry_command(entry_preview,c,self._pose_controller.c)
                if near is None:
                    s.pop('terminal_alignment_latched',None)
                    s['visual_settled']=0
                else:near['aligned']=False  # Hysteresis holds phase; does not widen completion tolerance.
        if near:
            preview.update({k:v for k,v in near.items() if k!='aligned'})
        if p.get('acquire_then_odom',{}).get('odom_only_after_acquire') and self.odom_transit(p):
            # Distinct current odom samples establish completion, not visual freshness.
            at_pose=(math.hypot(preview.get('error_x_m',float('inf')),preview.get('error_y_m',float('inf')))<=self._pose_controller.c['position_tolerance_m'] and
                     abs(preview.get('error_yaw_rad',float('inf')))<=self._pose_controller.c['yaw_tolerance_rad'])
            if distance_cfg:at_pose=preview.get('distance_reached',False)
            s['visual_settled']=s.get('visual_settled',0)+1 if at_pose else 0
            preview['at_target']=at_pose and s['visual_settled']>=self._pose_controller.c['settle_samples']
            if at_pose:preview.update(linear_x=0.,angular_z=0.)
        elif p.get('departure'):
            # The fixed odom target is already acquired; final yaw and new images are not arrival conditions.
            s['visual_settled']=self._pose_controller.settled
        else:
            # Completion needs distinct recent visual observations, not repeated predictions.
            at_pose=(abs(preview.get('error_yaw_rad',float('inf')))<=self._pose_controller.c['yaw_tolerance_rad'] and
                     math.hypot(preview.get('error_x_m',float('inf')),preview.get('error_y_m',float('inf')))<=self._pose_controller.c['position_tolerance_m'])
            if near is not None:at_pose=near['aligned']
            if p.get('acquire_then_odom') and tracker.phase!='FINAL' and not continuous:at_pose=False
            recent=(now_ns-tracker.stamp)/1e9<=min(self.image_header_max_age_s,p['target_tracking']['max_input_age_s'])
            if not at_pose or not recent:s['visual_settled']=0
            elif s.get('settled_observation')!=tracker.stamp:
                s['visual_settled']=s.get('visual_settled',0)+1;s['settled_observation']=tracker.stamp
            preview['at_target']=bool(at_pose and recent and s.get('visual_settled',0)>=self._pose_controller.c['settle_samples'])
        preview.update(stamp_ns=stamp,source_observation_stamp_ns=tracker.stamp,
            prediction_age_s=(now_ns-tracker.stamp)/1e9,odom_age_s=(now_ns-stamp)/1e9,
            visual_settled=s.get('visual_settled',0),estimate=True,command_sent=False)
        if not distance_cfg and not continuous and self.odom_transit(p) and preview.get('phase')!='WAIT_OBSERVATION':preview['phase']='ALIGN_FIXED_TARGET' if tracker.phase=='ALIGN' else 'MOVE_TO_FIXED_TARGET'
        self._tracking_preview=preview
        self.log_target_control(s,preview,tracker)
        self.control_preview_pub.publish(String(data=json.dumps(preview)))

    def log_target_control(self,s,preview,tracker):
        now=self.motion_time()
        if now-s.get('target_log_at',-1e9)<1.:return
        s['target_log_at']=now
        def value(key,scale=1.):
            v=preview.get(key)
            return 'n/a' if v is None else f'{v*scale:.3f}'
        self.get_logger().info(
            f"Dock target: phase={preview.get('phase')} "
            f"forward_cm={value('error_x_m',100.)} lateral_cm={value('error_y_m',100.)} "
            f"yaw_deg={value('error_yaw_rad',180./math.pi)} "
            f"visual_age_s={value('prediction_age_s')} odom_age_s={value('odom_age_s')} "
            f"source={preview.get('tracking_source','default')} speed_scale={value('tracking_speed_scale')} "
            f"along_cm={value('remaining_along_m',100.)} cross_cm={value('lateral_offset_m',100.)} heading_offset_deg={value('heading_from_anchor_rad',180./math.pi)} "
            f"accepted_observations={tracker.accepted_count} "
            f"settled={s.get('visual_settled',0)}/{self._pose_controller.c['settle_samples']} "
            f"at_target={preview.get('at_target',False)} "
            f"reason={preview.get('reason','')} last_rejection={tracker.reason}")

    def pause_recovery(self,s,p,exc):
        self.drive(0.,0.,force=True)
        reason=exc.reason if isinstance(exc,Recoverable) else 'TF'
        cfg=p['recovery']
        if 'recovery_wait' not in s:
            planned=(p.get('acquire_then_odom') and getattr(self._target_tracker,'phase','') in ('ACQUIRE','VERIFY') and reason in ('MARKER','OBSERVATION'))
            s['recovery_count']=s.get('recovery_count',0)+(0 if planned else 1)
            if s['recovery_count']>cfg['max_episodes']:
                self.finish(FAILED,'복구 횟수 초과: '+str(exc));return
            timeout=cfg['marker_timeout_s'] if reason in ('MARKER','OBSERVATION') else cfg['wait_timeout_s']
            s['recovery_wait']=RecoveryWait(reason,self.motion_time(),timeout,cfg['stable_s'])
            s['recovery_visual_after_ns']=self.get_clock().now().nanoseconds
            if planned:self.get_logger().info(f'Docking observation stage: {self._target_tracker.phase}; waiting for stopped fresh samples')
            else:self.get_logger().warn(f'Docking paused: {reason}: {exc}')
        else:s['recovery_wait'].good_since=None
        self.phase_feedback(s,'WAIT_'+reason)

    def run_recovery(self,s,p):
        inputs=self.sensor_inputs()
        wait=s['recovery_wait'];cfg=p['recovery'];now=self.motion_time()
        wait.check_deadline(now)
        visual_recovery=bool((p.get('acquire_then_odom',{}).get('continuous_visual_handoff') or
            (p.get('acquire_then_odom',{}).get('visual_correction_during_transit') and getattr(self._target_tracker,'phase','')=='TRANSIT' and not p['acquire_then_odom'].get('distance_corridor')))
            and 'lidar_stage' not in s and not self.departure_locked(p))
        # No search motion without live sensors, camera and odometry TF.
        if now-inputs['odom_at']>self.odom_max_age_s or now-inputs['scan_at']>self.scan_max_age_s:
            self.drive(0.,0.,force=True)
            wait.update(False,False,now);self.phase_feedback(s,'WAIT_SENSORS');return
        if (visual_recovery or (not self.departure_locked(p) and not self.odom_transit(p))) and now-self._image_at>(p['target_tracking']['max_prediction_s'] if self._tracking_enabled else self.image_receive_timeout_s):
            self.drive(0.,0.,force=True)
            wait.update(False,False,now);self.phase_feedback(s,'WAIT_CAMERA');return
        t=self.tf.lookup_transform(p.get('entry',{}).get('odom_frame',self.get_parameter('odom_frame').value),p.get('base_frame','base_footprint'),Time(),timeout=Duration(seconds=.02))
        if not self.fresh(t):raise Recoverable('TF','recovery odom TF stale')
        marker_required=not p.get('distance_heading_trial') and (visual_recovery or (not self.departure_locked(p) and not self.odom_transit(p))) and 'preparing_at' not in s and (s.get('entry_complete',False) or 'entry_controller' not in s)
        if marker_required:
            preview=(self._tracking_preview or {}) if self._tracking_enabled else (self._last_observation or {}).get('control_preview',{})
            age=(self.get_clock().now().nanoseconds-preview.get('stamp_ns',0))/1e9
            usable=bool(preview) and preview.get('stamp_ns',0)>=s['observation_start_ns'] and 0<=age<=self.image_header_max_age_s
            visual_transit=bool(p.get('acquire_then_odom',{}).get('visual_correction_during_transit') and getattr(self._target_tracker,'phase','')=='TRANSIT')
            marker_ok=recovery_observation_ready(preview,self.get_clock().now().nanoseconds,
                s['observation_start_ns'],s.get('recovery_visual_after_ns',0),
                self.image_header_max_age_s,self.odom_max_age_s,p['target_tracking'],
                visual_recovery,visual_transit)
            if not marker_ok:
                wait.update(False,False,now)
                missing=usable and preview.get('reason')=='target marker not visible'
                if self._tracking_enabled:
                    raw=self._last_observation or {}
                    raw_age=(self.get_clock().now().nanoseconds-raw.get('stamp_ns',0))/1e9
                    missing=bool(raw) and 0<=raw_age<=self.image_header_max_age_s and not any(m['marker_id']==self._pose_controller.marker_id for m in raw.get('markers',[]))
                # A processing delay is not evidence that the marker left the image.
                # Require distinct, fresh frames actually missing the requested ID.
                search_ready=search_evidence(s,self._last_observation or {},self._pose_controller.marker_id,
                    self.get_clock().now().nanoseconds,
                    p.get('target_tracking',{}).get('max_input_age_s',self.image_header_max_age_s))
                if search_ready and cfg.get('search_enabled'):
                    r=t.transform.rotation
                    yaw=math.atan2(2*(r.w*r.z+r.x*r.y),1-2*(r.y*r.y+r.z*r.z))
                    if 'marker_search' not in s:
                        if not self.stopped():
                            self.drive(0.,0.,force=True);return
                        s['marker_search']=MarkerSearch(yaw,now,cfg['search_angle_rad'],cfg['search_speed_rps'],cfg['search_dwell_s'])
                    w,done=s['marker_search'].step(yaw,self.stopped(),now)
                    self.phase_feedback(s,'SEARCH_MARKER' if not done else 'WAIT_MARKER')
                    self.drive(0.,w,force=not bool(w))  # The same swept-footprint check applies.
                else:
                    self.drive(0.,0.,force=True)
                    self.phase_feedback(s,'WAIT_OBSERVATION')
                return
        self.drive(0.,0.,force=True)
        # Re-check the blocked command while stationary; this does not publish motion.
        probe=s.get('resume_command',(0.,0.)) if wait.reason=='OBSTACLE' and 'marker_search' not in s else (0.,0.)
        self.check_footprint_motion(*probe)
        if not wait.update(True,self.stopped(),now):
            self.phase_feedback(s,'VERIFY_RECOVERY');return
        s.pop('missing_frame_count',None);s.pop('missing_frame_stamp',None)
        s.pop('marker_search',None);s.pop('recovery_visual_after_ns',None)
        elapsed=now-wait.started
        s.pop('recovery_wait');s.pop('marker_wait_since',None)
        if p.get('distance_heading_trial'):
            s.pop('heading_capture',None);s.pop('distance_heading_sample',None)
            s['distance_acquire_started']=self.motion_time()
        if 'preparing_at' in s:
            s['preparing_at']=self.motion_time()
        elif 'entry_controller' in s and not s.get('entry_complete'):
            s['entry_started']+=elapsed
            s['entry_controller'].replan();s.pop('entry_alignment_stopped',None)
        else:
            with self._pose_lock:self._pose_controller.reset()
            s['awaiting_recovery_frame']=self.motion_time()
            # Preserve the completed initial heading gate across observation recovery.
            # The resumed pose controller still corrects current position and final yaw.
        self.get_logger().info('Docking resumed after stable sensors and measured stop')
        self.phase_feedback(s,'RESUME_ALIGNMENT')

    def phase_feedback(self,s,phase):
        self.state=phase
        if s.get('last_phase')!=phase:
            feedback=PrecisionMotion.Feedback();feedback.phase=phase
            s['handle'].publish_feedback(feedback);s['last_phase']=phase
            self.get_logger().info('Station docking phase: '+phase)

    def scan_clearance(self,p):
        inputs=self.sensor_inputs()
        scan=inputs['scan']
        if scan is None or self.motion_time()-inputs['scan_at']>self.scan_max_age_s:raise Recoverable('SENSORS','filtered scan stale')
        if p.get('collision_guard'):return  # Checked with the actual command in drive().
        valid=[r for r in scan.ranges if math.isfinite(r) and scan.range_min<=r<=scan.range_max]
        if len(valid)<15 or min(valid)<=p['scan_stop_range_m']:
            raise RuntimeError('필터 scan 장애물 거리/유효 관측 부족')

    def check_footprint_motion(self,linear,angular):
        diag_start=time.monotonic();diag_marks={}
        def mark(name):diag_marks[name]=round((time.monotonic()-diag_start)*1000,2)
        inputs=self.sensor_inputs()
        name=self._session['handle'].request.profile_id
        profile=self.profiles[name]
        if profile.get('distance_departure') and self._session.get('distance_departure_active'):
            c=profile['marker_backout']
            if linear<0 and abs(linear)<=c['max_linear_mps']+1e-9 and abs(angular)<=c['max_angular_rps']+1e-9:
                self.check_departure_rear(profile)
                return
        rotation=profile.get('distance_departure',{}).get('exit_rotation',{})
        if (rotation.get('skip_footprint_check',False)
                and 'distance_exit_started' in self._session
                and linear==0. and abs(angular)<=rotation['alignment_max_angular_rps']+1e-9):
            if not self._session.get('rotation_guard_notice'):
                self.get_logger().warning('Distance departure trial: exit rotation footprint check disabled by configuration')
                self._session['rotation_guard_notice']=True
            return
        trial=profile.get('distance_heading_trial',{})
        if trial.get('front_scan_only',False) and 'lidar_stage' in self._session:
            c=profile['lidar_approach']
            # Explicit standalone straight-approach trial. No side footprint test.
            # Reverse and in-place rotation never use this exception.
            if (linear>0 or (linear==0 and profile.get('observation_only'))) and linear<=c['max_linear_mps']+1e-9 and abs(angular)<=c['max_angular_rps']+1e-9:
                self.lidar_status(self._session,profile)
                if not self._session.get('front_only_logged'):
                    self.get_logger().warning('Distance trial: FRONT_SCAN_ONLY; side footprint checks excluded during forward lidar approach')
                    self._session['front_only_logged']=True
                return
        if name not in self._footprint_guards:return
        guard,frame,cfg=self._footprint_guards[name]
        scan=inputs['scan']
        if scan is None or self.motion_time()-inputs['scan_at']>self.scan_max_age_s or not self.fresh(scan,self.scan_max_age_s):
            raise Recoverable('SENSORS','FOOTPRINT_SCAN_STALE')
        profile=self.profiles[name]
        surface=profile.get('target_surface') if 'lidar_stage' in self._session and linear>=0 else None
        raw=None
        if surface:
            with self._sensor_lock:
                raw_history=tuple(self._raw_front_history.get(profile['lidar_approach']['raw_scan_topic'],()))
        selected=None
        candidates=inputs['scan_history'] or (scan,)
        pairs=(fresh_scan_pairs(candidates,raw_history,self.get_clock().now().nanoseconds,
                min(self.scan_max_age_s,profile['lidar_approach']['max_age_s'])) if surface
               else ((m,None) for m in reversed(candidates)))
        for candidate,paired in pairs:
            if not self.fresh(candidate,self.scan_max_age_s):continue
            try:
                aligned=self.tf.lookup_transform(cfg['odom_frame'],candidate.header.frame_id,Time.from_msg(candidate.header.stamp),timeout=Duration(seconds=0.))
            except TransformException:continue
            selected=(candidate,aligned)
            if surface:raw=paired
            break
        if selected is None:
            detail='TARGET_SURFACE_NO_MATCHED_SCAN' if surface else 'FOOTPRINT_NO_TIME_ALIGNED_SCAN'
            if surface:
                raw_stamp=raw_history[-1].header.stamp if raw_history else None
                detail+=f': filtered={scan.header.frame_id}@{scan.header.stamp.sec}.{scan.header.stamp.nanosec:09d}, raw_latest={raw_stamp}, history={len(raw_history)}'
            raise Recoverable('TF',detail)
        mark("select_tf_ms")
        scan,aligned=selected
        ranges=np.asarray(scan.ranges,dtype=float)
        valid=np.isfinite(ranges)&(ranges>=scan.range_min)&(ranges<=scan.range_max)
        count=int(valid.sum())
        if count<cfg['min_valid_points']:
            raise Recoverable('SENSORS',f'FOOTPRINT_SCAN_INSUFFICIENT: valid={count}, required={cfg["min_valid_points"]}')
        angles=scan.angle_min+np.flatnonzero(valid)*scan.angle_increment
        points=np.stack((ranges[valid]*np.cos(angles),ranges[valid]*np.sin(angles),np.zeros(count),np.ones(count)),axis=1)
        # Compensate motion since acquisition, using odom as the continuous frame.
        current=self.tf.lookup_transform(frame,cfg['odom_frame'],Time(),timeout=Duration(seconds=.02))
        if not self.fresh(current):raise Recoverable('TF','FOOTPRINT_ODOM_TF_STALE')
        def matrix(t):
            v,q=t.transform.translation,t.transform.rotation
            return transform_matrix((v.x,v.y,v.z),(q.x,q.y,q.z,q.w))
        stamp_ns=scan.header.stamp.sec*10**9+scan.header.stamp.nanosec
        scan_age=(self.get_clock().now().nanoseconds-stamp_ns)/1e9
        if not 0<=scan_age<=self.scan_max_age_s:
            raise Recoverable('TF','FOOTPRINT_TIME_ALIGNED_SCAN_STALE')
        transform=matrix(current)@matrix(aligned)
        xy=(points@transform.T)[:,:2]
        mark("transform_ms")
        target_xy=None
        # Only the final, forward lidar stage may use the target's reduced padding.
        if surface and 'lidar_stage' in self._session and linear>=0:
            c=profile['lidar_approach']
            if raw is None:raise Recoverable('SENSORS','TARGET_SURFACE_RAW_SCAN_MISSING')
            now_ns=self.get_clock().now().nanoseconds
            try:distance=front_distance(raw,now_ns,c,context='COLLISION_PAIR_SCAN_STALE')
            except ScanFreshnessError as exc:raise Recoverable('TF',str(exc)) from exc
            raw_stamp=raw.header.stamp.sec*10**9+raw.header.stamp.nanosec
            if raw.header.frame_id!=scan.header.frame_id or raw_stamp!=stamp_ns:
                raise RuntimeError('Internal scan pair mismatch')
            target_mask=surface_points(points[:,:2],distance,surface)
            target_xy=xy[target_mask]
            xy=xy[~target_mask]
            # Only restore the narrow distance-measurement cone (<22 cm).
            # Everything outside it stays on the filtered-scan collision path.
            rr=np.asarray(raw.ranges,dtype=float)
            aa=raw.angle_min+np.arange(len(rr))*raw.angle_increment
            front=raw_front_mask(rr,aa,raw.range_min,raw.range_max,c['sector_half_angle_rad'])
            rp=np.stack((rr[front]*np.cos(aa[front]),rr[front]*np.sin(aa[front]),
                         np.zeros(int(front.sum())),np.ones(int(front.sum()))),axis=1)
            raw_tf=self.tf.lookup_transform(cfg['odom_frame'],raw.header.frame_id,
                Time.from_msg(raw.header.stamp),timeout=Duration(seconds=0.))
            raw_xy=(rp@(matrix(current)@matrix(raw_tf)).T)[:,:2]
            mask=surface_points(rp[:,:2],distance,surface)
            target_xy=np.concatenate((target_xy,raw_xy[mask]))
            xy=np.concatenate((xy,raw_xy[~mask]))
            if 'target_surface_guard' not in self._session:
                self._session['target_surface_guard']=surface_guard(guard,surface)
            close_guard=self._session['target_surface_guard']
            if not self._session.get('target_surface_logged'):
                self.get_logger().info(f"Target surface: raw front cone +/-{math.degrees(c['sector_half_angle_rad']):.1f}deg; remaining points use filtered scan; physical footprint checks retained")
                self._session['target_surface_logged']=True
        # Check both the requested motion and the still-measured motion when braking.
        mark("surface_ms")
        motions=[('command',(linear,angular))]
        if inputs['twist']!=(linear,angular):motions.append(('measured',inputs['twist']))
        for label,(v,w) in motions:
            hit=guard.check(xy,v,w,scan_age)
            if hit is None and target_xy is not None:
                hit=close_guard.check(target_xy,v,w,scan_age)
                if hit is not None:label='target_physical_'+label
            mark('check_'+label+'_ms')
            if hit is not None:
                px,py=hit['point']
                sensor_point=np.linalg.inv(transform)@np.array([px,py,0.,1.])
                self.get_logger().warning(f'Collision audit: class={label} sensor_xy={sensor_point[:2].tolist()} sensor_range={math.hypot(*sensor_point[:2]):.4f} sensor_angle_deg={math.degrees(math.atan2(sensor_point[1],sensor_point[0])):.2f} requested={(linear,angular)} measured={inputs["twist"]} scan_age={scan_age:.3f} stages_cumulative_ms={diag_marks} target_points={len(target_xy) if target_xy is not None else 0}')
                raise Recoverable('OBSTACLE',f'FOOTPRINT_COLLISION: {label}, point=({px:.3f},{py:.3f})m, predicted={hit["time_s"]:.3f}s, valid={count}')

        if self.motion_time()-getattr(self,'_guard_diag_at',0.)>1.:
            self._guard_diag_at=self.motion_time()
            self.get_logger().info(f'Guard timing cumulative_ms={diag_marks} points={count}')

    def check_trial_extrinsics(self):
        t=self.tf.lookup_transform(self.marker_base_frame,self.get_parameter('camera_frame_id').value,Time(),timeout=Duration(seconds=.02))
        v,q=t.transform.translation,t.transform.rotation
        current=transform_matrix((v.x,v.y,v.z),(q.x,q.y,q.z,q.w))
        taught=self._target_extrinsics
        if taught.shape!=(4,4) or not np.isfinite(taught).all():raise RuntimeError('저장 목표의 카메라 TF 없음')
        angle=math.acos(max(-1.,min(1.,(np.trace(taught[:3,:3].T@current[:3,:3])-1)/2)))
        if np.linalg.norm(taught[:3,3]-current[:3,3])>.005 or angle>.035:
            raise RuntimeError('현재 카메라 TF가 도킹 목표 저장 당시와 다릅니다.')

    def prepare_graph_return(self,s,p):
        if 'graph_return_goal' in s:return
        c=p['graph_return'];cfg=p['departure']
        path=Path(self.get_parameter('profiles_file').value).parent/cfg['graph_file']
        gx,gy=graph_point(path,c['node_id'])
        sx,sy=graph_point(path,cfg['exit_heading_from_node_id']);ex,ey=graph_point(path,cfg['exit_heading_node_id'])
        if math.hypot(ex-sx,ey-sy)<.05:raise RuntimeError('Exit graph edge too short')
        t=self.tf.lookup_transform(self.get_parameter('odom_frame').value,p.get('base_frame','base_footprint'),Time(),timeout=Duration(seconds=.02))
        if not self.fresh(t):raise Recoverable('TF','Graph return odom stale')
        tm=self.tf.lookup_transform(self.get_parameter('odom_frame').value,'map',Time.from_msg(t.header.stamp),timeout=Duration(seconds=.02))
        v,q=tm.transform.translation,tm.transform.rotation
        a=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        s['graph_return_goal']=(v.x+math.cos(a)*gx-math.sin(a)*gy,v.y+math.sin(a)*gx+math.cos(a)*gy)
        s['exit_goal_yaw']=math.atan2(math.sin(a+math.atan2(ey-sy,ex-sx)),math.cos(a+math.atan2(ey-sy,ex-sx)))
        self.get_logger().info(f"Sorter exit locked: node={c['node_id']}, edge={cfg['exit_heading_from_node_id']}->{cfg['exit_heading_node_id']}")

    def check_departure_rear(self,p):
        from .lidar_approach import require_scan_fresh
        c=p['distance_departure'];scan=self.sensor_inputs()['scan']
        if scan is None:raise RuntimeError('Departure rear scan missing')
        if scan.header.frame_id!=p['marker_backout']['scan']['scan_frame']:raise RuntimeError('Departure rear scan frame mismatch')
        require_scan_fresh(scan,self.get_clock().now().nanoseconds,.3,'DEPARTURE_REAR_STALE')
        values=[]
        for i,r in enumerate(scan.ranges):
            a=scan.angle_min+i*scan.angle_increment-math.pi
            if abs(math.atan2(math.sin(a),math.cos(a)))<=c['rear_half_angle_rad']:
                if r==float('inf') or (math.isfinite(r) and scan.range_min<=r<=scan.range_max):values.append(r)
        if len(values)<5:raise RuntimeError('Departure rear scan insufficient')
        if min(values)<c['rear_stop_m']:raise RuntimeError('Departure rear obstacle')

    def run_distance_departure(self,s,p):
        from .lidar_approach import front_distance
        c=p['marker_backout'];cfg=p['distance_departure'];now=self.motion_time()
        if 'distance_exit_started' in s:
            self.run_distance_exit(s,p)
            return
        pose=self.lidar_odom(p)
        if 'distance_departure_active' not in s:
            self.drive(0.,0.,force=True)
            if not self.stopped():return
            t=self.tf.lookup_transform(self.get_parameter('odom_frame').value,p.get('base_frame','base_footprint'),Time(),timeout=Duration(seconds=.02))
            if not self.fresh(t):raise Recoverable('TF','Departure odom stale')
            tm=self.tf.lookup_transform(self.get_parameter('odom_frame').value,'map',Time.from_msg(t.header.stamp),timeout=Duration(seconds=.02))
            q=tm.transform.rotation
            a=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
            goal=a+cfg['map_yaw_rad']
            error=math.atan2(math.sin(goal-pose[2]),math.cos(goal-pose[2]))
            if abs(error)>c['max_heading_error_rad']:raise RuntimeError('Departure taught heading difference too large')
            s.update(distance_departure_active=True,distance_departure_started=now,distance_departure_origin=pose,distance_departure_yaw=goal)
            self.get_logger().info(f'Distance departure: map_yaw={cfg["map_yaw_rad"]:.6f}, front_target={c["reference_front_distance_m"]:.3f}m; no marker/XY return')
        if now-s['distance_departure_started']>c['timeout_s']:raise RuntimeError('Distance departure timeout')
        origin=s['distance_departure_origin']
        if math.hypot(pose[0]-origin[0],pose[1]-origin[1])>c['max_travel_m']:raise RuntimeError('Distance departure travel limit')
        with self._sensor_lock:scan=self._raw_front_scans.get(c['raw_scan_topic'])
        if scan is None:raise RuntimeError('Departure front scan missing')
        distance=front_distance(scan,self.get_clock().now().nanoseconds,c['scan'])
        error=math.atan2(math.sin(s['distance_departure_yaw']-pose[2]),math.cos(s['distance_departure_yaw']-pose[2]))
        v,w=backout_command(distance,error,c)
        self.phase_feedback(s,'REVERSE_DISTANCE' if v else 'VERIFY_DISTANCE_STOP')
        self.drive(v,w,force=not v)
        if not v:
            since=s.setdefault('distance_departure_settle',now)
            if now-since>=.5 and self.stopped():
                if cfg.get('exit_rotation',{}).get('enabled'):
                    self.prepare_distance_exit(s,p)
                else:self.finish(DONE,'Distance departure reached and stopped')
        else:s.pop('distance_departure_settle',None)
        if now-s.get('distance_departure_log',0)>1:
            s['distance_departure_log']=now
            self.get_logger().info(f'Distance departure: front={distance:.3f}m yaw_error={math.degrees(error):.2f}deg v={v:.3f} w={w:.3f}')

    def prepare_distance_exit(self,s,p):
        c=p['distance_departure']['exit_rotation']
        path=Path(self.get_parameter('profiles_file').value).parent/c['graph_file']
        ax,ay=graph_point(path,c['from_node_id']);bx,by=graph_point(path,c['to_node_id'])
        if math.hypot(bx-ax,by-ay)<.05:raise RuntimeError('Departure exit graph edge too short')
        odom=self.get_parameter('odom_frame').value
        t=self.tf.lookup_transform(odom,p.get('base_frame','base_footprint'),Time(),timeout=Duration(seconds=.02))
        if not self.fresh(t):raise Recoverable('TF','Departure exit odom stale')
        tm=self.tf.lookup_transform(odom,'map',Time.from_msg(t.header.stamp),timeout=Duration(seconds=.02))
        q=tm.transform.rotation
        a=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        goal=a+math.atan2(by-ay,bx-ax)
        s.update(distance_exit_started=self.motion_time(),distance_exit_yaw=goal,
                 distance_exit_origin=(t.transform.translation.x,t.transform.translation.y))
        self.get_logger().info(f'Distance exit rotation: edge={c["from_node_id"]}->{c["to_node_id"]}, odom_yaw={goal:.4f}')
        self.phase_feedback(s,'ALIGN_EXIT_DIRECTION')

    def run_distance_exit(self,s,p):
        c=p['distance_departure']['exit_rotation'];now=self.motion_time()
        if now-s['distance_exit_started']>c['timeout_s']:raise RuntimeError('Distance exit rotation timeout')
        x,y,yaw=self.lidar_odom(p);ox,oy=s['distance_exit_origin']
        if math.hypot(x-ox,y-oy)>c['max_translation_m']:raise RuntimeError('Distance exit rotation position drift')
        angular,done=heading_command(yaw,s['distance_exit_yaw'],c)
        self.phase_feedback(s,'VERIFY_EXIT_DIRECTION_STOP' if done else 'ALIGN_EXIT_DIRECTION')
        self.drive(0.,angular,force=done)  # Rotation guard policy is scoped in check_footprint_motion.
        if done:
            since=s.setdefault('distance_exit_settle',now)
            if now-since>=.5 and self.stopped():self.finish(DONE,'Distance departure and graph exit heading completed')
        else:s.pop('distance_exit_settle',None)

    def begin_parking(self,s,p):
        c=p['parking'];path=Path(self.get_parameter('profiles_file').value).parent/c['graph_file']
        ax,ay=graph_point(path,c['from_node_id']);bx,by=graph_point(path,c['to_node_id'])
        if math.hypot(bx-ax,by-ay)<.05:raise ValueError('Parking heading nodes too close')
        odom=self.get_parameter('odom_frame').value
        t=self.tf.lookup_transform(odom,p.get('base_frame','base_footprint'),Time(),timeout=Duration(seconds=.02))
        if not self.fresh(t):raise RuntimeError('Parking odom TF stale')
        tm=self.tf.lookup_transform(odom,'map',Time.from_msg(t.header.stamp),timeout=Duration(seconds=.02))
        q=tm.transform.rotation
        a=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        s.update(parking_started=self.motion_time(),parking_yaw=a+math.atan2(by-ay,bx-ax),
                 parking_origin=(t.transform.translation.x,t.transform.translation.y))
        self.phase_feedback(s,'ALIGN_PARKING_EXIT')

    def parking_status(self,s,p):
        c=p['parking'];x,y,yaw=self.lidar_odom(p);ox,oy=s['parking_origin']
        if math.hypot(x-ox,y-oy)>c['max_translation_m']:raise RuntimeError('Parking rotation position drift')
        return heading_command(yaw,s['parking_yaw'],c)

    def run_parking(self,s,p):
        c=p['parking'];now=self.motion_time()
        if now-s['parking_started']>c['timeout_s']:raise RuntimeError('Parking rotation timeout')
        angular,done=self.parking_status(s,p)
        self.phase_feedback(s,'VERIFY_PARKING_STOP' if done else 'ALIGN_PARKING_EXIT')
        self.drive(0.,angular,force=done)
        if done:
            since=s.setdefault('parking_settle',now)
            if now-since>=c['settle_s'] and self.stopped():self.finish(DONE,'Station parked facing exit and stopped')
        else:s.pop('parking_settle',None)

    def run_marker_backout(self,s,p):
        self.prepare_graph_return(s,p)  # Check localization before any departure motion.
        c=p['marker_backout'];pose=self.lidar_odom(p);now=self.motion_time()
        s.setdefault('backout_started',now);s.setdefault('backout_origin',pose)
        ox,oy,heading=s['backout_origin']
        if now-s['backout_started']>c['timeout_s']:raise RuntimeError('Marker40 not acquired during return')
        if math.hypot(pose[0]-ox,pose[1]-oy)>c['max_travel_m']:raise RuntimeError('Marker return observation limit reached')
        # Once observations are accepted, stop to acquire a stable taught-pose target.
        stamp=getattr(self._target_tracker,'stamp',None)
        if stamp is not None and 0<=(self.get_clock().now().nanoseconds-stamp)/1e9<.3:
            self.drive(0.,0.,force=True);self.phase_feedback(s,'ACQUIRE_DEPARTURE_TARGET');return
        with self._sensor_lock:scan=self._raw_front_scans.get(c['raw_scan_topic'])
        if scan is None:raise RuntimeError('No raw front scan for marker return')
        # Distance validates the retreat envelope; only marker teaching can complete return.
        distance=front_distance(scan,self.get_clock().now().nanoseconds,c['scan'])
        error=math.atan2(math.sin(heading-pose[2]),math.cos(heading-pose[2]))
        v,w=backout_command(distance,error,c)
        self.phase_feedback(s,'BACKOUT_TO_MARKER' if v else 'ACQUIRE_DEPARTURE_TARGET')
        self.drive(v,w)

    def run_graph_return(self,s,p):
        if self.motion_time()-s['graph_return_started']>p['graph_return']['timeout_s']:raise TimeoutError('Graph reverse return timed out')
        v,w,done=reverse_point(self.lidar_odom(p),s['graph_return_goal'],p['graph_return'])
        self.phase_feedback(s,'VERIFY_EXIT_NODE_STOP' if done else 'REVERSE_TO_EXIT_NODE')
        self.drive(v,w)
        if done and self.stopped():
            s['exit_alignment']=True;s['exit_started']=self.motion_time()
            self.phase_feedback(s,'ALIGN_EXIT_NODE')

    def log_scan_delay(self,s,exc):
        now=self.motion_time()
        if now-s.get('scan_delay_log_at',-1e9)<.5:return
        s['scan_delay_log_at']=now
        with self._sensor_lock:
            raw=dict(self._raw_front_scans)
        stamp=lambda m:m.header.stamp.sec*10**9+m.header.stamp.nanosec
        now_ns=self.get_clock().now().nanoseconds
        ages={k:round((now_ns-stamp(m))/1e9,4) for k,m in raw.items()}
        self.get_logger().warn(f'Scan timing: {exc}; latest_raw_age_s={ages}; {self.sensor_status()}')

    def on_raw_front_scan(self,key,m):
        if not self.fresh(m,.5):return
        with self._sensor_lock:
            prev=self._raw_front_scans.get(key)
            stamp=lambda x:x.header.stamp.sec*10**9+x.header.stamp.nanosec
            if prev is None or stamp(m)>stamp(prev):
                self._raw_front_scans[key]=m
                self._raw_front_history[key]=(*self._raw_front_history.get(key,()),m)[-16:]

    def lidar_odom(self,p):
        t=self.tf.lookup_transform(self.get_parameter('odom_frame').value,p.get('base_frame','base_footprint'),Time(),timeout=Duration(seconds=.02))
        if not self.fresh(t):raise RuntimeError('Final approach odom TF stale')
        v,q=t.transform.translation,t.transform.rotation
        return v.x,v.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))

    def run_initial_marker_recovery(self, s, p):
        """프로파일 opt-in. 목표 확보 이후에는 재탐색을 끼워 넣지 않는다."""
        c = p.get('initial_marker_recovery', {})
        if not c.get('enabled') or s.get('initial_marker_confirmed'):
            return False
        if s['handle'].request.operation != 'DOCK':
            return False
        from .initial_marker_recovery import InitialMarkerRecovery
        now = self.motion_time()
        if 'initial_marker_policy' not in s:s['initial_marker_policy']=InitialMarkerRecovery(c,now)
        policy = s['initial_marker_policy']
        self.motion_elapsed(policy.started)  # /clock 역행은 새 액션으로 재시작해야 한다.
        stamp_now = self.get_clock().now().nanoseconds
        marker_id = p['target_marker_id']
        visible = any(report.get('stamp_ns', 0) >= s['observation_start_ns']
            and 0 <= (stamp_now-report.get('stamp_ns', 0))/1e9 <= self.image_header_max_age_s
            and any(m.get('marker_id') == marker_id for m in report.get('markers', []))
            for report in self._raw_reports)
        stopped=self.stopped()
        rejection=getattr(self._target_tracker,'envelope_rejection',None)
        if (p.get('route_handoff',{}).get('enabled') and stopped
                and getattr(self._target_tracker,'phase','') == 'ACQUIRE'
                and policy.origin is None and not s.get('entry_motion_started') and rejection
                and rejection['stamp_ns'] >= s['observation_start_ns']
                and 0 <= (stamp_now-rejection['stamp_ns'])/1e9 <= p['target_tracking']['max_input_age_s']):
            # 마커가 보이지만 너무 먼 경우 후진 탐색을 시작하지 않는다.
            # 현재 정밀 액션을 정지·해제한 뒤 상위에서 기존 Nav2 경로로 재접근한다.
            why=f'Stopped approach target outside envelope: {rejection}'
            s['approach_reentry_error']=why
            self.finish(FAILED,why)
            return True
        acquired=False
        if stopped:
            if p.get('distance_heading_trial'):
                acquired=self.capture_distance_heading(s,p) is not None
            else:
                acquired=getattr(self._target_tracker,'phase','') in ('TRANSIT','ALIGN')
        v, w, done, phase = policy.step(now, self.lidar_odom(p), stopped, visible, acquired)
        self.phase_feedback(s, phase)
        self.drive(v, w, force=not (v or w))
        if done:
            s['initial_marker_confirmed'] = True
            s['initial_marker_wait_elapsed'] = now - policy.started
            s['distance_acquire_started']=now
        return not done

    def capture_distance_heading(self,s,p):
        from .distance_heading import HeadingCapture
        c=p['distance_heading_trial']
        cached=s.get('distance_heading_sample')
        now_ns=self.get_clock().now().nanoseconds
        if cached and 0<=(now_ns-cached[1]['stamp_ns'])/1e9<=c['max_age_s']:return cached
        if 'heading_capture' not in s:s['heading_capture']=HeadingCapture(c)
        now_ns=self.get_clock().now().nanoseconds
        heading=None
        # A newer camera stamp can precede the corresponding TF publication.
        # Use a fresh, transformable frame; never substitute a latest-time TF.
        for report in reversed(self._raw_reports):
            stamp=report.get('stamp_ns',0)
            if stamp<s['observation_start_ns'] or stamp<=s['heading_capture'].last_stamp or not 0<=(now_ns-stamp)/1e9<=c['max_age_s']:continue
            try:
                captured=self.tf.lookup_transform(self.get_parameter('odom_frame').value,
                    p.get('base_frame','base_footprint'),Time(nanoseconds=stamp),timeout=Duration(seconds=0.))
            except TransformException:continue
            q=captured.transform.rotation
            yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
            heading=s['heading_capture'].add(report,yaw,now_ns)
            break
        if heading is None:return None
        s['distance_heading_sample']=(heading,report)
        return heading,report

    def run_distance_heading_trial(self,s,p):
        from .distance_heading import HeadingCapture
        c=p['distance_heading_trial']
        if 'lidar_initial_wait_since' in s:
            try:self.begin_lidar_approach(s,p)
            except (TransformException,ScanFreshnessError):self.drive(0.,0.,force=True)
            return
        if 'harvest_locked_heading' in s:
            self.run_harvest_heading(s,p)
            return
        self.drive(0.,0.,force=True)
        self.phase_feedback(s,'ACQUIRE_DISTANCE_HEADING')
        if self.motion_elapsed(s.get('distance_acquire_started',s['motion_started']))>c['acquire_timeout_s']:
            raise TimeoutError('Distance trial: stable front marker not acquired; no search motion')
        if not self.stopped():return
        captured=self.capture_distance_heading(s,p)
        if captured is None:return
        heading,report=captured
        if p['lidar_approach'].get('marker_surface_selection'):
            marker=next(m for m in report['markers'] if m['marker_id']==c['marker_id'])
            mt=self.tf.lookup_transform(self.get_parameter('odom_frame').value,report['frame_id'],
                Time(nanoseconds=report['stamp_ns']),timeout=Duration(seconds=0.))
            v,q=mt.transform.translation,mt.transform.rotation
            matrix=transform_matrix((v.x,v.y,v.z),(q.x,q.y,q.z,q.w))
            point=matrix@np.array([*marker['marker_position_in_base_m'],1.])
            s['lidar_marker_target']=(float(point[0]),float(point[1]))
            self.get_logger().info(f"Lidar target from marker {c['marker_id']}: odom_xy={s['lidar_marker_target']}; heading unchanged")
        if c.get('align_before_lidar'):
            s['harvest_locked_heading']=heading
            self.run_harvest_heading(s,p)
            return
        try:
            if self.begin_lidar_approach(s,p) is False:return
        except (TransformException,ScanFreshnessError):
            # Stay in acquisition, with zero command and the original deadline.
            return
        except Recoverable as exc:
            if exc.reason=='TF':return
            raise
        if c.get('heading_source') != 'odom_current':
            x,y,_=s['lidar_origin'];s['lidar_origin']=(x,y,heading)
        heading=s['lidar_origin'][2]
        self.get_logger().info(f'Distance trial heading locked: odom_yaw={heading:.4f}; taught XY unused; marker reacquisition disabled during lidar approach')

    def run_harvest_heading(self,s,p):
        c=p['distance_heading_trial']
        if self.motion_elapsed(s.get('distance_acquire_started',s['motion_started']))>c['acquire_timeout_s']:
            raise TimeoutError('Marker42 heading alignment timeout')
        _,_,yaw=self.lidar_odom(p)
        error=math.atan2(math.sin(s['harvest_locked_heading']-yaw),math.cos(s['harvest_locked_heading']-yaw))
        if abs(error)>c['max_bearing_rad']:
            raise RuntimeError('Confirmation marker heading correction exceeds configured small-angle limit')
        if abs(error)>c['alignment_tolerance_rad']:
            self.phase_feedback(s,'ALIGN_CONFIRMED_HEADING')
            w=max(-c['alignment_max_angular_rps'],min(c['alignment_max_angular_rps'],c['alignment_kp']*error))
            self.drive(0.,w)
            return
        self.drive(0.,0.,force=True)
        if not self.stopped():return
        if self.begin_lidar_approach(s,p) is False:return
        x,y,_=s['lidar_origin']
        s['lidar_origin']=(x,y,s['harvest_locked_heading'])

    def run_relative_backout(self,s,p):
        from .harvest_motion import backout_command
        now=self.motion_time();pose=self.lidar_odom(p)
        if 'backout_origin' not in s:
            self.drive(0.,0.,force=True)
            if not self.stopped():return
            s['backout_origin']=pose;s['backout_started']=now
        v,w,done=backout_command(p['relative_backout'],s['backout_origin'],pose,now-s['backout_started'])
        self.phase_feedback(s,'VERIFY_BACKOUT_STOP' if done else 'REVERSE_DISTANCE')
        self.drive(v,w,force=done)
        if done and self.stopped():self.finish(DONE,'Harvest clearance distance reached and stopped')

    def run_initial_surface_creep(self,s,p):
        from .lidar_approach import initial_creep_command
        c=p['lidar_approach'];pose=self.lidar_odom(p)
        origin=s.setdefault('lidar_creep_origin',pose)
        with self._sensor_lock:scan=self._raw_front_scans.get(c['raw_scan_topic'])
        v,w=initial_creep_command(scan,self.get_clock().now().nanoseconds,c,origin,pose)
        self.phase_feedback(s,'CREEP_ACQUIRE_SURFACE')
        self.drive(v,w,force=(v==0. and w==0.))

    def begin_lidar_approach(self,s,p):
        # Marker target reached and measured stop confirmed by the caller.
        c=p['lidar_approach']
        if 'lidar_initial_wait_since' in s:
            elapsed=self.motion_elapsed(s['lidar_initial_wait_since'])
            if elapsed>=c.get('initial_acquire_wait_s',3.)+c.get('initial_creep_s',0.):
                raise TimeoutError('Initial lidar surface acquisition timeout: '+s.get('lidar_initial_error',''))
        candidate=dict(s)
        candidate['lidar_origin']=self.lidar_odom(p)
        candidate['lidar_controller']=LidarApproach(p['lidar_approach'],marker_target=s.get('lidar_marker_target'))
        # Require the configured laser front to agree with robot forward.
        t=self.tf.lookup_transform(p.get('base_frame','base_footprint'),p['lidar_approach']['scan_frame'],Time(),timeout=Duration(seconds=.02))
        q=t.transform.rotation
        forward=np.array([1-2*(q.y*q.y+q.z*q.z),2*(q.x*q.y+q.w*q.z),2*(q.x*q.z-q.w*q.y)])
        if np.linalg.norm(forward-np.array([1.,0.,0.]))>.035:raise RuntimeError('Front lidar axis not aligned with robot forward')
        try:
            _,_,_,distance=self.lidar_status(candidate,p)
        except RuntimeError as exc:
            retryable=str(exc).startswith(('Raw front scan insufficient','Raw front center missing',
                'Raw front center cluster insufficient','Raw front surface inconsistent',
                'Marker surface not matched','Marker surface ambiguous'))
            if not retryable or not p['lidar_approach'].get('initial_acquire_wait_s'):raise
            s.setdefault('lidar_initial_wait_since',self.motion_time())
            s['lidar_initial_error']=str(exc)
            if self.motion_elapsed(s['lidar_initial_wait_since'])>=c['initial_acquire_wait_s'] and c.get('initial_creep_s',0.)>0:
                self.run_initial_surface_creep(s,p)
            else:
                self.drive(0.,0.,force=True)
                self.phase_feedback(s,'WAIT_INITIAL_SURFACE')
            self.log_scan_delay(s,exc)
            return False
        s.pop('lidar_initial_wait_since',None);s.pop('lidar_initial_error',None)
        s.pop('lidar_creep_origin',None)
        limits=dict(p['lidar_approach'])
        if p.get('distance_heading_trial'):
            remaining=max(0.,distance-limits['target_distance_m'])
            limits['max_travel_m']=min(limits['max_travel_m'],remaining+.10)
            limits['timeout_s']=min(limits['timeout_s'],remaining/limits['max_linear_mps']*1.5+10.)
        s.update(lidar_stage=True,lidar_started=self.motion_time(),
                 lidar_origin=candidate['lidar_origin'],lidar_controller=candidate['lidar_controller'],lidar_limits=limits)
        self.phase_feedback(s,'LIDAR_APPROACH')

    def lidar_status(self,s,p):
        c=s.get('lidar_limits',p['lidar_approach']);x,y,yaw=self.lidar_odom(p);ox,oy,heading=s['lidar_origin']
        if math.hypot(x-ox,y-oy)>c['max_travel_m']:raise RuntimeError('Final approach travel limit')
        with self._sensor_lock:scan=self._raw_front_scans.get(c['raw_scan_topic'])
        if scan is None:raise RuntimeError('No raw front scan')
        error=math.atan2(math.sin(heading-yaw),math.cos(heading-yaw))
        poses={}
        if c.get('surface_tracking'):
            odom=self.get_parameter('odom_frame').value
            # Keep incoming scans in the existing bounded history. A scan can
            # arrive before its odom TF; use the newest ready pair, not Time(0)
            # for capture pose and not a blocking wait in the control callback.
            with self._sensor_lock:history=tuple(self._raw_front_history.get(c['raw_scan_topic'],()))
            surface=s['lidar_controller'].surface
            scan=select_tf_ready_scan(history,self.get_clock().now().nanoseconds,
                min(c['max_age_s'],.25),
                lambda msg:self.tf.can_transform(odom,c['scan_frame'],Time.from_msg(msg.header.stamp),timeout=Duration(seconds=0.)),
                surface.last_scan)
            def laser_pose(at, check_fresh=False):
                tf=self.tf.lookup_transform(odom,c['scan_frame'],at,timeout=Duration(seconds=0.))
                v,q=tf.transform.translation,tf.transform.rotation
                if check_fresh and not self.fresh(tf):raise RuntimeError('Surface tracking odom stale')
                return (v.x,v.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
            poses=dict(scan_pose=laser_pose(Time.from_msg(scan.header.stamp)),current_pose=laser_pose(Time(), check_fresh=True))
        return s['lidar_controller'].step(scan,self.get_clock().now().nanoseconds,error,**poses)

    def run_lidar_approach(self,s,p):
        elapsed=self.motion_elapsed(s['lidar_started'])
        if 'lidar_input_wait_motion' in s:
            elapsed-=self.motion_elapsed(s['lidar_input_wait_motion'])
        if elapsed>s.get('lidar_limits',p['lidar_approach'])['timeout_s']:raise TimeoutError('Final lidar approach timed out')
        v,w,done,d=self.lidar_status(s,p)
        self.phase_feedback(s,'VERIFY_LIDAR_STOP' if v==0. else 'LIDAR_APPROACH')
        self.drive(v,w)  # Retains existing filtered-scan swept-footprint check.
        waited=s.pop('lidar_input_wait_since',None)
        if waited is not None:
            duration=self.motion_time()-waited
            motion_duration=self.motion_elapsed(s.pop('lidar_input_wait_motion'))
            s['lidar_started']+=motion_duration;s['motion_started']+=motion_duration
            s['started']+=duration
            self.get_logger().info(f'Lidar inputs recovered after {duration:.3f}s; continuing retained target')
        if self.motion_time()-s.get('lidar_log_at',-1e9)>1.:
            s['lidar_log_at']=self.motion_time()
            surface=s['lidar_controller'].surface
            self.get_logger().info(f"Front lidar: distance={d:.3f}m target={p['lidar_approach']['target_distance_m']:.3f}m v={v:.3f} surface={surface.mode if surface else 'legacy'} matched={surface.count if surface else 'n/a'}")
        if done and self.stopped():self.finish(DONE,'Marker alignment and front lidar target reached and stopped')

    def exit_heading_status(self,s,p):
        cfg=p['departure'];base=p.get('base_frame','base_footprint')
        odom=self.get_parameter('odom_frame').value
        t=self.tf.lookup_transform(odom,base,Time(),timeout=Duration(seconds=.02))
        if not self.fresh(t):raise Recoverable('TF','Exit odom TF stale')
        v,r=t.transform.translation,t.transform.rotation
        yaw=math.atan2(2*(r.w*r.z+r.x*r.y),1-2*(r.y*r.y+r.z*r.z))
        if 'exit_goal_yaw' not in s:
            path=Path(self.get_parameter('profiles_file').value).parent/cfg['graph_file']
            sx,sy=graph_point(path,cfg['exit_heading_from_node_id'])
            gx,gy=graph_point(path,cfg['exit_heading_node_id'])
            # Transform the graph edge direction into odom; robot/map translation is irrelevant.
            tm=self.tf.lookup_transform(odom,'map',Time.from_msg(t.header.stamp),timeout=Duration(seconds=.02))
            mv,mr=tm.transform.translation,tm.transform.rotation
            a=math.atan2(2*(mr.w*mr.z+mr.x*mr.y),1-2*(mr.y*mr.y+mr.z*mr.z))
            dx=math.cos(a)*(gx-sx)-math.sin(a)*(gy-sy)
            dy=math.sin(a)*(gx-sx)+math.cos(a)*(gy-sy)
            if math.hypot(dx,dy)<.05:raise RuntimeError('Exit heading graph nodes too close to determine direction')
            s['exit_goal_yaw']=math.atan2(dy,dx)
            self.get_logger().info(f"Exit heading locked: edge={cfg['exit_heading_from_node_id']}->{cfg['exit_heading_node_id']}, odom_yaw={s['exit_goal_yaw']:.3f}")
        goal=self._target_tracker.goal
        gx,gy=s.get('graph_return_goal',(goal[0,3],goal[1,3]))
        tolerance=p['graph_return']['position_tolerance_m'] if 'graph_return_goal' in s else self._pose_controller.c['position_tolerance_m']
        if math.hypot(v.x-gx,v.y-gy)>tolerance:
            raise RuntimeError('Exit rotation moved outside departure arrival radius')
        return heading_command(yaw,s['exit_goal_yaw'],cfg)

    def run_exit_heading(self,s,p):
        if self.motion_time()-s['exit_started']>p['departure']['alignment_timeout_s']:
            raise TimeoutError('Exit heading alignment timed out')
        angular,done=self.exit_heading_status(s,p)
        self.phase_feedback(s,'VERIFY_EXIT_STOP' if done else 'ALIGN_EXIT_NODE')
        if angular:self.scan_clearance(p)
        self.drive(0.,angular)
        if done and self.stopped():self.finish(DONE,'Departure and exit node heading aligned and stopped')

    def run_entry(self,s,q,p):
        if self.motion_time()-s['entry_started']>p['entry']['timeout_s']:raise TimeoutError('A→B 진입 제한시간 초과')
        base=p.get('base_frame','base_footprint')
        odom_frame=p.get('entry',{}).get('odom_frame',self.get_parameter('odom_frame').value)
        t=self.tf.lookup_transform(odom_frame,base,Time(),timeout=Duration(seconds=.02))
        if not self.fresh(t):raise Recoverable('TF','진입 odom TF 만료')
        v,r=t.transform.translation,t.transform.rotation
        yaw=math.atan2(2*(r.w*r.z+r.x*r.y),1-2*(r.y*r.y+r.z*r.z))
        if 'entry_odom_goal' not in s:
            self.drive(0.,0.,force=True)
            if not self.stopped():return
            g=q.clearance_pose
            if g.frame_id not in ('','map'):raise RuntimeError('entry goal must use map frame')
            # Freeze the map target in odom at the same timestamp as the start pose.
            tm=self.tf.lookup_transform(odom_frame,'map',Time.from_msg(t.header.stamp),timeout=Duration(seconds=.1))
            mv,mr=tm.transform.translation,tm.transform.rotation
            angle=math.atan2(2*(mr.w*mr.z+mr.x*mr.y),1-2*(mr.y*mr.y+mr.z*mr.z))
            gx=mv.x+math.cos(angle)*g.position.x-math.sin(angle)*g.position.y
            gy=mv.y+math.sin(angle)*g.position.x+math.cos(angle)*g.position.y
            s['entry_odom_goal']=(gx,gy,math.atan2(math.sin(angle+g.yaw),math.cos(angle+g.yaw)))
            self.get_logger().info(f'Entry odom path: start=({v.x:.3f}, {v.y:.3f}), goal=({gx:.3f}, {gy:.3f})')
        linear,angular,done=s['entry_controller'].step((v.x,v.y,yaw),s['entry_odom_goal'])
        self.phase_feedback(s,s['entry_controller'].phase)
        if s['entry_controller'].needs_replan:
            self.drive(0.,0.,force=True)
            if self.stopped():
                s['entry_controller'].replan()
                s.pop('entry_alignment_stopped',None)
            return
        if linear or angular:self.scan_clearance(p)
        self.drive(linear,angular)
        if done and self.stopped():
            s['entry_complete']=True
            with self._pose_lock:self._pose_controller.reset()
            self._last_observation=None
            s['observation_start_ns']=self.get_clock().now().nanoseconds
            s['marker_wait_since']=self.motion_time()
            s['visual_settled']=0;s['settled_observation']=None
            self.phase_feedback(s,'ACQUIRE_MARKER')

    def drive(self,v,w,force=False):
        requested=(v,w)
        if v or w:
            allowed=self._session is not None and not self.lease.failed
            if allowed and self.pose_mode=='tf_observe':
                q=self._session['handle'].request
                p=self.profiles[q.profile_id]
                if p.get('strategy')=='marker_pose':
                    allowed=self.pose_output_enabled and q.operation in p.get('allowed_operations',['DOCK'])
                else:allowed=q.operation=='CLEAR'
            if not allowed:v,w=0.,0.
        now=self.motion_time()
        if v or w:
            last=getattr(self,'_smooth_output',(now,0.,0.))
            dt=min(.1,max(0.,now-last[0]))
            # Limit command acceleration; explicit stop always remains immediate.
            v=max(last[1]-.2*dt,min(last[1]+.2*dt,v))
            w=max(last[2]-.4*dt,min(last[2]+.4*dt,w))
        self._smooth_output=(now,v,w)
        if (v or w) and self._session is not None:
            if 'recovery_wait' not in self._session:self._session['resume_command']=(v,w)
            self.check_footprint_motion(v,w)
        # 진입 전 회전만 제외. 첫 병진 명령 전부터 보수적으로 진입으로 기록한다.
        if self._session is not None and v:
            self._session['entry_motion_started']=True
        super().drive(v,w,force)
        if self._session and self.motion_time()-self._session.get('speed_log_at',-1e9)>=1.:
            self._session['speed_log_at']=self.motion_time()
            measured=self.sensor_inputs()['twist']
            self.get_logger().info(f'Dock speed: requested_v={requested[0]:.4f} requested_w={requested[1]:.4f} command_v={self._v:.4f} command_w={self._w:.4f} measured_v={measured[0]:.4f} measured_w={measured[1]:.4f} dry_run={self.c["dry_run"]}')

def main(args=None):
    rclpy.init(args=args);node=PrecisionServer();executor=MultiThreadedExecutor(num_threads=4);executor.add_node(node)
    try:executor.spin()
    finally:node.stop_robot();executor.shutdown();node.destroy_node();rclpy.try_shutdown()
