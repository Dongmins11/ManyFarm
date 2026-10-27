"""설정·기존 주행 자원·운송 객체를 조립한다. 속도를 직접 발행하지 않는다."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import math
import signal
import time
import uuid
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, BatteryState
from farm_interfaces.msg import RobotStatus
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.route import RouteGraph
from farm_navigation.pose_provider import PoseProvider
from farm_navigation.motion_monitor import MotionMonitor
from farm_navigation.nav2_client import Nav2Client
from .navigation_adapter import TransportNavigator as Navigator
from .configuration import load_profile, require_execution
from .docking_port import UnavailableDocking
from .device_port import UnavailableDevice
from .device_bridge import DeviceBridge
from .trigger_device import TriggerDevice
from farm_docking.clients import PrecisionClient, LeaseClient, ExclusiveNavigator
from .transport_mission import TransportMission
from .transport_state_controller import TransportStateController
from .transport_communication import TransportCommunication
from .mission_types import utc


class TransportNode(Node):
    def __init__(self) -> None:
        super().__init__('transport_node')
        for name,value in [('project_root',''),('environment_config',''),('mode','real'),
                           ('allow_route_checks',False),('journal_dir','')]:
            self.declare_parameter(name,value)
        root = Path(self.get_parameter('project_root').value).expanduser().resolve()
        mode = self.get_parameter('mode').value
        self.profile = load_profile(root,self.get_parameter('environment_config').value,mode)
        require_execution(self.profile)
        if self.get_namespace() != '/'+self.profile['robot_id']:
            raise ValueError('Node namespace와 robot_id가 다릅니다.')
        if self.get_parameter('use_sim_time').value != (mode == 'sim'):
            raise ValueError('mode/use_sim_time 불일치')
        journal_dir = self.get_parameter('journal_dir').value
        journal = Path(journal_dir).expanduser() if journal_dir else root/('sim/runs/transport' if mode=='sim' else 'runs/transport')
        journal = journal.resolve()
        if not journal.is_relative_to(root) or journal.is_relative_to(root/'sim') != (mode=='sim'):
            raise ValueError('작업 기록도 해당 환경의 프로젝트 경로 안에 저장해야 합니다.')
        self.callbacks = ReentrantCallbackGroup()
        self.stopping = False
        self.settings = NavigationSettings.from_mapping(self.profile['navigation'])
        self.graph = RouteGraph(self.profile['route_graph'],self.settings.map_frame)
        from .route_policy import apply_route_policy
        apply_route_policy(self.graph, self.profile.get('route_policy', {}))
        self.poses = PoseProvider(self,self.settings)
        self.motion = MotionMonitor(self,self.settings,self.callbacks)
        self.client = Nav2Client(self,self.settings,self.callbacks)
        self.navigator = Navigator(self,self.settings,self.client,self.poses,self.motion,
                                   self.check_motion,self.graph)
        self.mission = TransportMission(journal/(self.profile['robot_id']+'_tasks.json'))
        self.lease = None
        self.docking = UnavailableDocking()
        self.device = UnavailableDevice()
        if self.profile.get('precision_enabled',False):
            self.lease = LeaseClient(self,self.callbacks,'nav')
            self.navigator = ExclusiveNavigator(self.navigator,self.lease)
            self.docking = PrecisionClient(self,self.callbacks,self.check_precision)
            device_config = self.profile.get('mechanical_device', {})
            backend = device_config.get('backend', 'action')
            if backend == 'trigger':
                self.device = TriggerDevice(self, self.callbacks, device_config)
            elif backend == 'action':
                self.device = DeviceBridge(self,self.callbacks)
            else:
                raise ValueError('Unknown mechanical device backend: ' + backend)
        self.controller = TransportStateController(self.navigator,self.mission,self.docking,self.device)
        self.controller.station_return_mode = self.profile.get('station_return_mode', 'marker_docking')
        self.controller.pickup_workflow = self.profile.get('pickup_workflow', {})
        self.controller.unload_workflows = self.profile.get('unload_workflows', {})
        self.controller.parking_profiles = {name for name,p in self.profile.get("precision_registry",{}).get("profiles",{}).items() if p.get("parking",{}).get("enabled") and p["parking"].get("next_mission") == "direct"}
        self.sorter_approach = None
        if self.profile.get('sorter_distance_handoff',{}).get('enabled'):
            from .sorter_approach import SorterApproach
            self.sorter_approach = SorterApproach(self)
        self.controller.sorter_approach = self.sorter_approach
        self.harvest_approach=None
        if self.profile.get('pickup_workflow',{}).get('route_handoff',{}).get('enabled'):
            from .harvest_approach import HarvestApproach
            self.harvest_approach=HarvestApproach(self)
        self.controller.harvest_approach=self.harvest_approach
        self.communication = TransportCommunication(self)
        self._scan_at = 0.
        self._pose = None
        self._pose_at = 0.
        self._battery = float('nan')
        self._battery_at = 0.
        self._boot = uuid.uuid4().hex
        self._sequence = 0
        self._status = self.create_publisher(RobotStatus,'status',10)
        self.create_subscription(LaserScan,self.profile.get('scan_topic','scan'),self._scan,qos_profile_sensor_data,callback_group=self.callbacks)
        self.create_subscription(BatteryState,self.profile.get('battery_topic','battery_state'),self._on_battery,qos_profile_sensor_data,callback_group=self.callbacks)
        self._telemetry_pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix='transport_pose')
        self._pose_future = None
        self.create_timer(.02,self.communication.update,callback_group=MutuallyExclusiveCallbackGroup())
        self.create_timer(.2,self._observe,callback_group=MutuallyExclusiveCallbackGroup())
        self.create_timer(1.,self._publish_status,callback_group=MutuallyExclusiveCallbackGroup())

    def _scan(self, message: LaserScan) -> None:
        stamp = message.header.stamp.sec*10**9+message.header.stamp.nanosec
        age = (self.get_clock().now().nanoseconds-stamp)/1e9
        if message.header.frame_id and message.ranges and 0 <= age <= 1.0 and any(v == float("inf") or (math.isfinite(v) and message.range_min <= v <= message.range_max) for v in message.ranges):
            self._scan_at = time.monotonic()

    def _on_battery(self, message: BatteryState) -> None:
        if math.isfinite(message.percentage) and 0 <= message.percentage <= 1:
            self._battery = message.percentage*100.
            self._battery_at = time.monotonic()

    def _observe(self) -> None:
        if self._pose_future is not None and self._pose_future.done():
            try:
                self._pose = self._pose_future.result()
                self._pose_at = time.monotonic()
            except Exception:
                self._pose = None
            self._pose_future = None
        if self._pose_future is None and not self.stopping:
            self._pose_future = self._telemetry_pool.submit(self.poses.current,lambda:None)

    def check_precision(self) -> None:
        # 정밀 서버가 단계별 odom/scan/TF 최신성과 재측정을 소유한다.
        self.controller.check()
        if isinstance(self.device,DeviceBridge) and self.device.state and self.device.state.estop:
            raise RuntimeError('기구 비상정지')

    def check_motion(self) -> None:
        self.check_precision()
        if self.lease and self.lease.token:self.lease.check()
        if time.monotonic()-self._scan_at > 1.0:
            raise RuntimeError('라이다 데이터 단절: 이동 중단')
        if self._pose is None or time.monotonic()-self._pose_at > self.settings.tf_max_age_s:
            raise RuntimeError('위치 TF 단절: 이동 중단')
        if self.sorter_approach is not None:self.sorter_approach.check_handoff()
        if self.harvest_approach is not None:self.harvest_approach.check_handoff()

    def route_ready(self) -> bool:
        now = time.monotonic()
        return (not self.stopping and not self.controller.blocked and self._pose is not None
                and now-self._pose_at < self.settings.tf_max_age_s
                and now-self._scan_at < 1.0 and self.motion.stationary_now())

    def _publish_status(self) -> None:
        message = RobotStatus()
        message.robot_id,message.map_id = self.profile['robot_id'],self.profile['map_id']
        message.current_task_id = self.controller.request.task_id if self.controller.busy else ''
        # Parking/contact context remains internal; protocol has IDLE, not DOCKED.
        message.state = self.controller.state.name if self.controller.state else 'IDLE'
        # 외부 업무는 정밀주행 프로파일과 실제 장치 준비가 모두 필요하다.
        message.ready = (self.route_ready() and self.docking.available() and self.device.available() and not self.communication.busy
            and any(p.get('configured') and p.get('clearance_corridor_verified') for p in self.profile.get('precision_registry',{}).get('profiles',{}).values()))
        message.pose.frame_id = self.settings.map_frame
        fresh = self._pose is not None and time.monotonic()-self._pose_at < self.settings.tf_max_age_s
        message.pose.position.x = float(self._pose[0,3]) if fresh else float('nan')
        message.pose.position.y = float(self._pose[1,3]) if fresh else float('nan')
        message.pose.yaw = math.atan2(self._pose[1,0],self._pose[0,0]) if fresh else float('nan')
        message.battery_percent = self._battery if time.monotonic()-self._battery_at < 5 else float('nan')
        device_state=self.device.state if isinstance(self.device,DeviceBridge) and time.monotonic()-self.device.received<1. else None
        count=device_state.loaded_count if device_state and device_state.count_valid else None
        message.transfer_required=False
        # 내부 주행 시험은 기존 빈 적재 제한. 업무 모드의 미측정 수량은 -1로 구분한다.
        message.loaded_count=count if count is not None else (-1 if self.profile.get('precision_enabled') else 0)
        if self.profile.get('precision_enabled') and count is None:message.ready=False
        if self.profile.get('station_return_trial_enabled') and not isinstance(self.device, TriggerDevice):
            station=self.profile.get('precision_registry',{}).get('profiles',{}).get('station_transport_01',{})
            message.ready=bool(self.route_ready() and self.docking.available() and not self.communication.busy and not self.controller.blocked and self.controller.docked_request is None and station.get('configured'))
        if isinstance(self.device, TriggerDevice):
            # ready advertises the enabled unload workflow, not unsupported pickup.
            # Unknown count remains -1 until its source is agreed with control.
            message.ready = bool(self.route_ready() and self.docking.available()
                and self.device.available() and not self.communication.busy
                and self.controller.docked_request is None)
        message.error_code = 'RECOVERY_REQUIRED' if self.controller.blocked else ('NONE' if fresh else 'LOCALIZATION_LOST')
        message.error_message = '작업 기록 또는 정지 상태 확인 필요' if self.controller.blocked else ('' if fresh else '최신 map TF 없음')
        outcome = self.controller.last_outcome
        if not self.controller.busy and outcome and outcome.error_code != 'NONE':
            message.error_code,message.error_message = outcome.error_code,outcome.error_message
        if self.controller.blocked:
            message.state = 'ERROR'
        self._sequence += 1
        message.boot_id,message.sequence,message.timestamp = self._boot,self._sequence,utc()
        self._status.publish(message)

    def close(self) -> None:
        self.controller.close()
        if self.lease is not None:self.lease.close()
        self._telemetry_pool.shutdown(wait=True)
        self.communication.close()
        self.client.close()
        self.motion.close()
        self.poses.close()


def main(args=None) -> None:
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO)
    node = TransportNode()
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    def stop(*unused) -> None:
        node.stopping = True
        node.controller.cancel()
    signal.signal(signal.SIGINT,stop)
    signal.signal(signal.SIGTERM,stop)
    try:
        while rclpy.ok() and (not node.stopping or node.communication.busy):
            executor.spin_once(timeout_sec=.1)
    finally:
        node.close()
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
