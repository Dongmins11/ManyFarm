"""공통 후진 곡선 시험. 기본은 계획만 생성, --execute --exclusive일 때만 이동한다."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[3]
from farm_navigation.transfer_arc import ArcSpec, arc_path, add_profile, trial_profile, check_motion, check_complete
from farm_navigation.arc_clearance import check_grid
from farm_navigation.measured_velocity_guard import MeasuredVelocityGuard, MeasuredVelocityLimits


def prepare() -> None:
    import yaml
    from farm_navigation.configuration import load_nav2_parameters, resolve_file
    spec = importlib.util.spec_from_file_location('field_trial', ROOT/'robot/tools/tag_camera/bias_trial/trial.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    folder = module.prepare('on')
    envfile = folder/'environment.yaml'
    env = yaml.safe_load(envfile.read_text())
    nav = load_nav2_parameters(resolve_file(ROOT,env['nav_params']), ROOT)
    from farm_navigation.arc_profile import write_profile, finalize_manifest
    out, generated = write_profile(nav, folder)
    env['nav_params'] = str(out)
    envfile.write_text(yaml.safe_dump(env,sort_keys=False))
    finalize_manifest(folder, [envfile, *generated])
    print(folder)


def run(args) -> None:
    import fcntl
    import threading
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from farm_navigation.wall_shutdown import start_spin, drain_then_close
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from rclpy.callback_groups import ReentrantCallbackGroup
    from nav_msgs.msg import Odometry
    from nav2_msgs.msg import Costmap
    from geometry_msgs.msg import PolygonStamped, Twist
    from action_msgs.msg import GoalStatusArray
    from rosidl_runtime_py.convert import message_to_ordereddict
    from rcl_interfaces.srv import GetParameters
    from rclpy.parameter import parameter_value_to_python
    from farm_navigation.navigation_types import NavigationSettings, RoutePlan
    from farm_navigation.navigator import Navigator
    from farm_navigation.configuration import read_mapping
    from farm_navigation.nav2_client import Nav2Client
    from farm_navigation.motion_monitor import MotionMonitor

    policy_path=ROOT/'robot/config/robots/vicpinky/transfer/arc_monitor_policy.json'
    policy=read_mapping(policy_path)
    speed_guard=MeasuredVelocityGuard(MeasuredVelocityLimits(**policy['measured_velocity']))
    speed_active=False
    arc = ArcSpec(radius=args.radius)
    ns = args.namespace.rstrip('/')
    prefix = getattr(args, 'isolated_prefix', '')
    if prefix:
        import re
        if not re.fullmatch(re.escape(ns)+r'/arc_trial_[0-9a-f]{8}',prefix):
            raise ValueError('격리 서버 namespace 형식 불일치')
        if not args.baseline_hash:raise ValueError('기존 실행 파라미터 해시 필요')
    if not ns.startswith('/') or ns == '':
        raise ValueError('절대 namespace 필요')
    lock = open('/tmp/manyfarm_arc_'+ns.replace('/','_')+'.lock','w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    spin_lock=open('/tmp/harvest_spin_trial.lock','w')
    fcntl.flock(spin_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('transfer_arc_trial',namespace=ns)
    executor = SingleThreadedExecutor(); executor.add_node(node)
    worker = start_spin(executor)
    service_clients=[]
    guard = threading.Lock(); latest = {}; statuses = {}; samples = []
    def receive(key,msg):
        with guard:
            latest[key] = (time.monotonic(),msg)
            if key == 'odom':
                samples.append(message_to_ordereddict(msg))
                if speed_active:
                    stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
                    try:speed_guard.observe(stamp,msg.twist.twist.linear.x,msg.twist.twist.angular.z)
                    except RuntimeError:pass  # 다음 check에서 오류를 전달해 기존 취소 경로로 진입한다.
    subscriptions=[]
    costmap_prefix = prefix+'/' if prefix else ''
    for key,typ,topic in [('odom',Odometry,'odom'),('costmap',Costmap,costmap_prefix+'local_costmap/costmap_raw'),
                          ('footprint',PolygonStamped,costmap_prefix+'local_costmap/published_footprint')]:
        subscriptions.append(node.create_subscription(typ,topic,lambda m,k=key:receive(k,m),qos_profile_sensor_data))
    actions=['harvest_task','return_to_station','dock_transfer','navigate_to_pose',
             'navigate_through_poses','follow_path','spin','backup','drive_on_heading','assisted_teleop']
    def status(key,msg):
        with guard:
            statuses[key]=[item.status for item in msg.status_list]
    status_qos=QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL)
    for action in actions:
        subscriptions.append(node.create_subscription(GoalStatusArray,action+'/_action/status',
            lambda m,k=action:status(k,m),status_qos))
    server=prefix+'/controller_server' if prefix else 'controller_server'
    settings=NavigationSettings(follow_action=prefix+'/follow_path' if prefix else 'follow_path',
        controller_node=server,mode='follow_path', map_frame='odom', controller_id='TransferArc',
        goal_checker_id='transfer_arc_goal',progress_checker_id='transfer_arc_progress',
        goal_timeout_s=arc.timeout,response_timeout_s=5.,cancel_timeout_s=5.)
    client=Nav2Client(node,settings,ReentrantCallbackGroup())
    stop_settings=NavigationSettings.from_mapping(policy['stationary'])
    motion=MotionMonitor(node,stop_settings,ReentrantCallbackGroup())
    report={'ok':False,'execute':args.execute,'radius':arc.radius,'samples':samples,
            'monitor_policy':policy,'velocity_events':speed_guard.events,'stop_checks':[]}
    output_dir=Path(args.output).expanduser();output_dir.mkdir(parents=True,exist_ok=True)
    output=output_dir/(str(time.time_ns())+'_arc.json')
    owned=False
    navigator=None
    gate=None;relay=None
    relay_guard=threading.RLock()
    if prefix:
        from farm_navigation.arc_isolation import CommandGate
        gate=CommandGate()
        report['isolated_prefix']=prefix;report['baseline_hash']=args.baseline_hash
        if args.execute:
            relay=node.create_publisher(Twist,'cmd_vel_nav',10)
            def block(reason):
                gate.error=str(reason);gate.close();relay.publish(Twist())
            def forward(msg):
                with relay_guard:forward_locked(msg)
            def forward_locked(msg):
                if not gate.enabled:return
                try:
                    no_other_actions();read('odom');read('costmap');read('footprint')
                    if any(abs(v)>1e-9 for v in (msg.linear.y,msg.linear.z,msg.angular.x,msg.angular.y)):
                        raise RuntimeError('곡선 외 축의 속도 명령')
                    if gate.accept(msg.linear.x,msg.angular.z,time.monotonic()):relay.publish(msg)
                    else:relay.publish(Twist())
                except BaseException as error:block(error)
            subscriptions.append(node.create_subscription(Twist,prefix+'/raw_cmd_vel',forward,1))
            def watchdog():
                with relay_guard:
                    if gate.expired(time.monotonic()):relay.publish(Twist())
            node.create_timer(.05,watchdog)
    def read(key):
        worker.check()
        with guard:
            pair=latest.get(key)
        if pair is None or time.monotonic()-pair[0]>.5:
            raise RuntimeError('최신 데이터 없음: '+key)
        msg=pair[1]
        age=(node.get_clock().now().nanoseconds-msg.header.stamp.sec*10**9-msg.header.stamp.nanosec)/1e9
        if not -.1 <= age <= .5:
            raise RuntimeError('메시지 시각 오류: '+key)
        return msg
    def pose():
        m=read('odom');p=m.pose.pose.position;q=m.pose.pose.orientation
        if m.header.frame_id != 'odom' or m.child_frame_id not in ('base_link','base_footprint'):
            raise RuntimeError('odom frame 불일치')
        return (p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
    def stopped():
        started=time.monotonic()
        def check_stop():
            if not rclpy.ok():raise RuntimeError('ROS 종료 중 정지 확인 불가')
        try:
            stamp=motion.wait_stopped(check_stop)
            report['stop_checks'].append({'ok':True,'stamp_ns':stamp,'elapsed_s':time.monotonic()-started})
        except BaseException as error:
            report['stop_checks'].append({'ok':False,'reason':str(error),'elapsed_s':time.monotonic()-started})
            raise
    def no_other_actions(allow_follow=False):
        with guard:
            active=[key for key,values in statuses.items() if any(s in (1,2,3) for s in values)
                    and not (allow_follow and key=='follow_path')]
        if active:raise RuntimeError('다른 동작 실행 중: '+','.join(active))
    def parameters(server,names):
        c=node.create_client(GetParameters,server+'/get_parameters');service_clients.append(c)
        try:
            if not c.wait_for_service(timeout_sec=3):raise RuntimeError('파라미터 서비스 없음: '+server)
            f=c.call_async(GetParameters.Request(names=names));end=time.monotonic()+3
            while not f.done() and time.monotonic()<end:time.sleep(.02)
            if not f.done():raise RuntimeError('파라미터 응답 없음')
            return dict(zip(names,[parameter_value_to_python(v) for v in f.result().values]))
        finally:pass  # 콜백 스레드 종료 후 일괄 제거한다.
    try:
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            with guard:ready=all(k in latest for k in ('odom','costmap','footprint'))
            if ready:break
            time.sleep(.05)
        stopped();no_other_actions()
        origin=pose(); path=arc_path(origin,arc); report['origin']=origin;report['path']=path
        cm=read('costmap'); fp=read('footprint')
        if cm.header.frame_id!='odom' or fp.header.frame_id!='odom':raise RuntimeError('costmap/footprint frame 불일치')
        report['preflight_clearance_m']=check_grid(path,[(p.x,p.y) for p in fp.polygon.points],origin,message_to_ordereddict(cm))
        # 설정 검증: 미설정/다른 제어기로 조용히 대체하지 않는다.
        expected={prefix+'.'+k:v for prefix,values in trial_profile().items() for k,v in values.items()}
        actual=parameters(server,list(expected))
        if any(actual[k]!=v for k,v in expected.items()):raise RuntimeError('곡선 시험 전용 프로파일 불일치; 시험 launch 필요')
        report['preflight']=client.preflight(no_other_actions)
        smooth=parameters('velocity_smoother',['velocity_timeout'])
        if not isinstance(smooth['velocity_timeout'],(float,int)) or not 0<smooth['velocity_timeout']<=1:
            raise RuntimeError('기존 smoother 명령 만료시간 확인 실패')
        if not args.execute:
            report['ok']=True;report['phase']='PLAN_ONLY';return
        if not args.exclusive:raise RuntimeError('--exclusive로 관제·다른 Goal 미실행 상태를 명시해야 합니다.')
        if args.reference is None:
            raise RuntimeError('--reference로 검토한 PLAN_ONLY 기록을 지정해야 합니다.')
        reference=json.loads(args.reference.read_text())
        if not reference.get('ok') or reference.get('phase')!='PLAN_ONLY' or reference['radius']!=arc.radius:
            raise RuntimeError('계획 기록이 유효하지 않습니다.')
        if prefix and reference.get('baseline_hash')!=args.baseline_hash:
            raise RuntimeError('계획 이후 기존 실행 설정이 바뀌었습니다.')
        reference_pose=reference['origin']
        from farm_navigation.transfer_arc import wrap
        if math.hypot(origin[0]-reference_pose[0],origin[1]-reference_pose[1])>.005 or abs(wrap(origin[2]-reference_pose[2]))>.02:
            raise RuntimeError('계획 이후 출발 자세가 달라졌습니다.')
        no_other_actions()
        # 실패한 부분 회전을 같은 계획으로 다시 실행하지 못하게 사용 표시를 남긴다.
        import os
        marker=str(args.reference)+'.used'
        descriptor=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(descriptor)
        start=time.monotonic()
        def check():
            if time.monotonic()-start>arc.timeout:raise TimeoutError('곡선 시험 시간 초과')
            if gate and gate.error:raise RuntimeError(gate.error)
            no_other_actions(not bool(prefix));check_motion(origin,pose(),arc);read('costmap');read('footprint')
            with guard:
                if speed_guard.error:raise RuntimeError(speed_guard.error)
        route=RoutePlan(str(time.time_ns()),'', 'odom',tuple((x,y) for x,y,_ in path),(),
                        sum(math.dist(a[:2],b[:2]) for a,b in zip(path,path[1:])),
                        tuple(yaw for _,_,yaw in path))
        def stop_output() -> None:
            nonlocal speed_active
            with relay_guard:
                if gate:gate.close()
                if relay:relay.publish(Twist())
            with guard:speed_active=False
        def check_stop() -> None:
            if not rclpy.ok():raise RuntimeError('ROS 종료 중 정지 확인 불가')
        def validate_arrival(stamp: int, check_input: Callable[[], None]) -> dict:
            check_input()
            if gate and gate.error:raise RuntimeError(gate.error)
            report['measurement']=check_complete(origin,pose(),arc)
            return dict(report['measurement'],accepted=True)
        navigator=Navigator(node,settings,client,None,motion,check,explicit_routes=True,
            stop_output=stop_output,settling_check=check_stop,arrival_validator=validate_arrival,
            record=lambda entry:report.update(navigation=entry))
        print('실제 후진 곡선 요청: 반경',arc.radius,'m / 왼쪽 90도',flush=True)
        with guard:speed_active=True
        owned=True
        if gate:gate.arm(time.monotonic())
        navigator.navigate(path[-1][:2],path[-1][2],route_plan=route)
        report['ok']=True;report['phase']='SUCCEEDED'
    except BaseException as error:
        report['error']=str(error) or type(error).__name__
    finally:
        with guard:speed_active=False
        with relay_guard:
            if gate:gate.close()
            if relay and owned:relay.publish(Twist())
        if owned:
            try:
                if navigator:navigator.cancel_nav()
                else:client.cancel()
                stopped();report['cleanup_stopped']=True
            except BaseException as error:report['cleanup_error']=str(error);report['ok']=False
        try:
            drain_then_close(executor,worker,[motion.close,client.close,
                *(lambda c=c:node.destroy_client(c) for c in service_clients),node.destroy_node,rclpy.try_shutdown])
            report['ros_cleanup_complete']=True
        except Exception as error:
            report['ros_cleanup_error']=str(error);report['ok']=False
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k not in ('samples','path')},ensure_ascii=False,indent=2))
        print('기록:',output)
    if not report['ok']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','trial'])
    parser.add_argument('--isolated-prefix',default='')
    parser.add_argument('--baseline-hash',default='')
    parser.add_argument('--radius',type=float,default=.10)
    parser.add_argument('--namespace',default='/harvest_01')
    parser.add_argument('--output',default=str(ROOT/'runs/transfer_arc'))
    parser.add_argument('--reference',type=Path,help='같은 출발 자세에서 PLAN_ONLY에 성공한 JSON')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--exclusive',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':prepare()
    else:run(args)
