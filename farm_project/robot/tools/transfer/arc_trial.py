"""공통 후진 곡선 시험. 기본은 계획만 생성, --execute --exclusive일 때만 이동한다."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from collections.abc import Callable
from dataclasses import asdict
from arc_return_support import (session_identity, load_departure, check_reentry,
    check_return_complete, require_plan, RETURN_CHECKER)

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
    retreating = args.retreat_from is not None
    aligning = args.align_from is not None
    returning = args.return_from is not None
    source = args.return_from or args.retreat_from or args.align_from
    if sum((retreating,aligning,returning))>1:raise ValueError('복귀 단계는 하나만 선택하세요.')
    from harvest_robot.transfer_retreat import retreat_plan, retreat_error, retreat_profile, alignment_path, alignment_clearance, alignment_footprint
    from farm_navigation.spin_client import SpinClient
    from farm_navigation.pose_provider import PoseProvider
    from sequence_support import verify_predecessor, pose_error, matrix_pose
    direction = 'retreat' if retreating else ('align' if aligning else ('forward_right' if returning else 'reverse_left'))
    # 기존 측정 감시의 부호만 반전: 복귀 중 후진은 기존 전진 한도와 같게 차단한다.
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
    node = rclpy.create_node('transfer_arc_trial',namespace=ns,cli_args=['--ros-args','-r','/tf:='+ns+'/tf','-r','/tf_static:='+ns+'/tf_static'])
    executor = SingleThreadedExecutor(); executor.add_node(node)
    worker = start_spin(executor)
    poses=PoseProvider(node,NavigationSettings())
    spin=SpinClient(node,prefix+'/spin',NavigationSettings(response_timeout_s=5.,cancel_timeout_s=5.)) if aligning else None
    service_clients=[]
    guard = threading.Lock(); latest = {}; statuses = {}; samples = []
    def receive(key,msg):
        with guard:
            latest[key] = (time.monotonic(),msg,node.get_clock().now().nanoseconds)
            if key == 'odom':
                samples.append(message_to_ordereddict(msg))
                if speed_active:
                    stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
                    try:speed_guard.observe(stamp,(-1 if returning else 1)*msg.twist.twist.linear.x,
                                            (-1 if returning else 1)*msg.twist.twist.angular.z)
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
        controller_node=server,mode='follow_path', map_frame='odom', controller_id='Retreat' if retreating else 'TransferArc',
        goal_checker_id='retreat_goal' if retreating else 'transfer_arc_goal',progress_checker_id='retreat_progress' if retreating else 'transfer_arc_progress',
        goal_timeout_s=arc.timeout,response_timeout_s=5.,cancel_timeout_s=5.,
        arrival_tolerance_m=.008,heading_tolerance_rad=math.radians(15) if retreating else .12)
    client=Nav2Client(node,settings,ReentrantCallbackGroup())
    stop_settings=NavigationSettings.from_mapping(policy['stationary'])
    motion=MotionMonitor(node,stop_settings,ReentrantCallbackGroup())
    report={'ok':False,'execute':args.execute,'radius':arc.radius,'samples':samples,
            'direction':direction,'arc_spec':asdict(arc),'cycle_id':args.cycle_id,
            'measured_velocity_sign':-1 if returning else 1,'monitor_policy':policy,'velocity_events':speed_guard.events,'stop_checks':[]}
    output_dir=Path(args.output).expanduser();output_dir.mkdir(parents=True,exist_ok=True)
    output=output_dir/(str(time.time_ns())+'_arc.json')
    owned=False
    navigator=None
    gate=None;relay=None
    clearance_worker=None
    relay_guard=threading.RLock()
    if prefix:
        from farm_navigation.arc_isolation import CommandGate
        gate=CommandGate(direction=direction)
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
                    axes=(msg.linear.x,msg.linear.y,msg.linear.z,msg.angular.x,msg.angular.y,msg.angular.z)
                    if not all(math.isfinite(v) for v in axes):
                        raise RuntimeError('비유한 속도 명령')
                    if any(abs(v)>1e-9 for v in (msg.linear.y,msg.linear.z,msg.angular.x,msg.angular.y)):
                        raise RuntimeError('곡선 외 축의 속도 명령')
                    if aligning and abs(msg.angular.z)>1e-9:require_clearance()
                    if gate.accept(msg.linear.x,msg.angular.z,time.monotonic()):relay.publish(msg)
                    else:relay.publish(Twist())
                except BaseException as error:block(error)
            subscriptions.append(node.create_subscription(Twist,prefix+'/raw_cmd_vel',forward,1))
            def watchdog():
                with relay_guard:
                    if gate.expired(time.monotonic()):relay.publish(Twist())
                    if aligning and gate.enabled:
                        try:require_clearance()
                        except BaseException as error:block(error)
            node.create_timer(.05,watchdog)
    input_trace=[]
    report['input_trace']=input_trace
    def read(key):
        worker.check()
        with guard:
            pair=latest.get(key)
        from input_timing import timing
        now_ns=node.get_clock().now().nanoseconds
        if pair is None:raise RuntimeError('최신 데이터 없음: '+key)
        msg=pair[1]
        detail=timing(key,msg.header.stamp.sec*10**9+msg.header.stamp.nanosec,
                      pair[2],now_ns,time.monotonic()-pair[0])
        if len(input_trace)<10000:input_trace.append(detail)
        if detail['reason']:
            raise RuntimeError('입력 시각 검사: '+json.dumps(detail,ensure_ascii=False))
        return msg
    def pose():
        m=read('odom');p=m.pose.pose.position;q=m.pose.pose.orientation
        if m.header.frame_id != 'odom' or m.child_frame_id not in ('base_link','base_footprint'):
            raise RuntimeError('odom frame 불일치')
        return (p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
    def check_alignment_clearance():
        current=pose();cm=read('costmap');fp=read('footprint')
        if math.dist(current[:2],origin[:2])>.005:raise RuntimeError('방향 맞춤 중 위치 이탈')
        if cm.header.frame_id!='odom' or fp.header.frame_id!='odom':
            raise RuntimeError('회전 충돌 검사 frame 불일치')
        return alignment_clearance(current,target[2],[(p.x,p.y) for p in fp.polygon.points],message_to_ordereddict(cm),body_footprint=body_footprint)
    def current_grid_key(cm):
        from async_clearance import grid_key
        meta=message_to_ordereddict(cm.metadata)
        # 지도 갱신 시각을 제외하고 좌표·크기·셀 내용은 모두 비교한다.
        extent=max(math.hypot(x,y) for x,y in body_footprint)+.005
        return grid_key({'frame':cm.header.frame_id,**meta},bytes(cm.data),
                        (origin[0],origin[1],extent))
    def clearance_snapshot():
        with guard:pairs=[latest[k] for k in ('odom','costmap','footprint')]
        od,cm,fp=[p[1] for p in pairs]
        if cm.header.frame_id!='odom' or fp.header.frame_id!='odom' or od.header.frame_id!='odom':
            raise RuntimeError('회전 충돌 검사 frame 불일치')
        pos=od.pose.pose.position;q=od.pose.pose.orientation
        current=(pos.x,pos.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
        stamps=[m.header.stamp.sec*10**9+m.header.stamp.nanosec for m in (od,cm,fp)]
        now=time.monotonic();now_ns=node.get_clock().now().nanoseconds
        if any(not -.1<=(now_ns-t)/1e9<=.5 for t in stamps) or any(not 0<=now-p[0]<=.5 for p in pairs):
            raise RuntimeError('충돌 검사 입력 시각 만료')
        certificate={'pose':current,'grid_key':current_grid_key(cm),'stamps':stamps,
                     'receipts':[p[0] for p in pairs]}
        return {'pose':current,'target_yaw':target[2],
                'footprint':[(p.x,p.y) for p in fp.polygon.points],
                'grid':message_to_ordereddict(cm),'body_footprint':body_footprint,
                'certificate':certificate}
    def clearance_ready():
        current=pose();cm=read('costmap');fp=read('footprint')
        if math.dist(current[:2],origin[:2])>.005:raise RuntimeError('방향 맞춤 중 위치 이탈')
        if cm.header.frame_id!='odom' or fp.header.frame_id!='odom':raise RuntimeError('회전 입력 frame 변경')
        points=[(p.x,p.y) for p in fp.polygon.points]
        if len(points)!=4 or not all(math.isfinite(v) for point in points for v in point):raise RuntimeError('footprint 형상 오류')
        lengths=lambda ps:sorted(math.dist(ps[i],ps[j]) for i in range(4) for j in range(i))
        if any(abs(a-b)>2e-5 for a,b in zip(lengths(points),lengths(body_footprint))):raise RuntimeError('footprint 형상 변경')
        if clearance_worker is None:return False,'충돌 계산 준비 안 됨'
        radius=max(math.hypot(x,y) for x,y in body_footprint)
        return clearance_worker.check(current,current_grid_key(cm),node.get_clock().now().nanoseconds,
                                      time.monotonic(),radius)
    def require_clearance():
        ready,reason=clearance_ready()
        if not ready:raise RuntimeError(reason)
    def start_clearance():
        nonlocal clearance_worker
        from async_clearance import AsyncClearance
        clearance_worker=AsyncClearance(clearance_snapshot)
        deadline=time.monotonic()+3.
        while True:
            no_other_actions()
            if not motion.stationary_now():raise RuntimeError('충돌 계산 준비 중 정지 확인 실패')
            ready,reason=clearance_ready()
            if ready:return
            if time.monotonic()>deadline:raise RuntimeError('충돌 계산 준비 시간 초과: '+reason)
            time.sleep(.01)
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
    def odom_session():
        return session_identity(Path('/proc/sys/kernel/random/boot_id').read_text(),
            node.get_publishers_info_by_topic(ns+'/odom'))
    try:
        if source and not prefix:raise RuntimeError('복귀 단독 시험은 격리 서버에서만 실행합니다.')
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            with guard:ready=all(k in latest for k in ('odom','costmap','footprint'))
            if ready:break
            time.sleep(.05)
        stopped();no_other_actions()
        stop_stamp=report['stop_checks'][-1]['stamp_ns']
        origin=pose();session=odom_session();report['odom_session']=session
        source_hash=None;departure_origin=origin
        if source:
            departure_origin,path,source_hash=load_departure(source,session=session,
                baseline_hash=args.baseline_hash,spec=arc)
            target=tuple(path[0])
            if returning or aligning:report['reentry']=check_reentry(origin,path,arc) if returning else pose_error(origin,target)
            if aligning and math.dist(origin[:2],target[:2])>.008:raise RuntimeError('방향 맞춤 전 위치 오차 초과')
            report['departure_sha256']=source_hash
            report['departure_file']=str(source.resolve())
            if args.cycle_id:
                departure=json.loads(source.read_text())
                if departure.get('cycle_id')!=args.cycle_id:raise RuntimeError('출발 cycle ID 불일치')
                if not args.input_trace:
                    report['predecessor_sha256']=verify_predecessor(args.after,direction,args.cycle_id,session,source_hash,origin)
                else:report['diagnostic_only']=True
            if retreating:
                retreat=retreat_plan(origin,target);path=list(retreat.path)
                report['retreat_target']=target
            elif aligning:
                path=list(alignment_path(origin,target[2]));report['alignment_angle']=math.atan2(math.sin(target[2]-origin[2]),math.cos(target[2]-origin[2]))
        else:
            path=arc_path(origin,arc)
            if args.cycle_id:
                def check_capture():
                    no_other_actions()
                    read('odom')
                    if not rclpy.ok() or not motion.stationary_now():
                        raise RuntimeError('출발 기준 저장 중 정지 상태 상실')
                def capture_stamp():
                    message=read('odom')
                    return message.header.stamp.sec*10**9+message.header.stamp.nanosec
                stamp,transforms=poses.lookup_available_pair(
                    ('map','odom'),'base_footprint',capture_stamp,check_capture)
                report['capture_stamp_ns']=stamp
                report['start_map_pose']=matrix_pose(transforms[0])
                report['start_odom_pose']=matrix_pose(transforms[1])
                captured=report['start_odom_pose']
                if math.dist(origin[:2],captured[:2])>.005 or abs(math.atan2(math.sin(origin[2]-captured[2]),math.cos(origin[2]-captured[2])))>.02:
                    raise RuntimeError('기준 저장 중 자세 변경')
                origin=tuple(captured);departure_origin=origin;path=arc_path(origin,arc)
        report['origin']=origin;report['path']=path
        cm=read('costmap'); fp=read('footprint')
        if cm.header.frame_id!='odom' or fp.header.frame_id!='odom':raise RuntimeError('costmap/footprint frame 불일치')
        if aligning:
            footprint_config=parameters(costmap_prefix+'local_costmap/local_costmap',
                ['footprint','footprint_padding','robot_base_frame'])
            body_footprint=alignment_footprint(footprint_config)
            odom_frame=read('odom').child_frame_id
            if odom_frame!=footprint_config['robot_base_frame']:
                transform=poses.lookup(odom_frame,footprint_config['robot_base_frame'],0,no_other_actions)
                # 제자리 회전 중심이 다른 frame을 같은 중심이라고 가정하지 않는다.
                if (abs(transform[0,3])+abs(transform[1,3])>1e-6 or
                    abs(transform[0,0]-1)+abs(transform[1,1]-1)+abs(transform[0,1])+abs(transform[1,0])>1e-6):
                    raise RuntimeError('odom/footprint 평면 기준 불일치')
            report['alignment_footprint_parameters']=footprint_config
            report['preflight_clearance_m']=check_alignment_clearance()
        else:
            report['preflight_clearance_m']=check_grid(([origin]+path) if returning else path,[(p.x,p.y) for p in fp.polygon.points],origin,message_to_ordereddict(cm))
        # 설정 검증: 미설정/다른 제어기로 조용히 대체하지 않는다.
        expected={prefix+'.'+k:v for prefix,values in trial_profile().items() for k,v in values.items()}
        if returning:expected['transfer_arc_goal.yaw_goal_tolerance']=RETURN_CHECKER
        if retreating:
            station_names=parameters(server,['Retreat.plugin'])
            profile=retreat_profile({'plugin':station_names['Retreat.plugin']})
            expected={plugin+'.'+key:value for plugin,values in profile.items() for key,value in values.items()}
        if aligning:
            behavior=parameters(prefix+'/behavior_server',['max_rotational_vel','min_rotational_vel','enable_stamped_cmd_vel'])
            if behavior!={'max_rotational_vel':.03,'min_rotational_vel':.03,'enable_stamped_cmd_vel':False}:raise RuntimeError('방향 맞춤 프로파일 불일치')
        actual=parameters(server,list(expected))
        if any(actual[k]!=v for k,v in expected.items()):raise RuntimeError('곡선 시험 전용 프로파일 불일치; 시험 launch 필요')
        report['preflight']=client.preflight(no_other_actions)
        smooth=parameters('velocity_smoother',['velocity_timeout'])
        if not isinstance(smooth['velocity_timeout'],(float,int)) or not 0<smooth['velocity_timeout']<=1:
            raise RuntimeError('기존 smoother 명령 만료시간 확인 실패')
        if aligning and (args.execute or args.input_trace):start_clearance()
        if args.input_trace:
            # 진단은 상태 전이를 하지 않고 현재 입력과 동일 충돌 검사 소요시간을 관찰한다.
            report['diagnostic_only']=True
            report['map_comparison']='blocked cells >=254; padded full-rotation square + 5mm translation; unchanged geometry'
            report['trace_errors']=[];report['clearance_check_s']=[]
            trace_end=time.monotonic()+12.
            while time.monotonic()<trace_end:
                no_other_actions()
                if odom_session()!=session:raise RuntimeError('진단 중 odom 세션 변경')
                if not motion.stationary_now():raise RuntimeError('무이동 진단 중 움직임 감지')
                check_started=time.monotonic()
                try:require_clearance()
                except RuntimeError as error:report['trace_errors'].append(str(error))
                report['clearance_check_s'].append(time.monotonic()-check_started)
                time.sleep(.05)
            report['diagnostic_pose']=pose()
            report['diagnostic_reentry']=pose_error(report['diagnostic_pose'],target)
            report['inputs_ok']=not report['trace_errors']
            if not report['inputs_ok']:raise RuntimeError('비동기 충돌 검사 입력/결과 검증 실패')
            report['fast_check_max_s']=max(report['clearance_check_s'],default=0.)
            report['ok']=True;report['phase']='INPUT_DIAGNOSTIC';return
        if not args.execute:
            report['ok']=True;report['phase']='PLAN_ONLY';return
        if not args.exclusive:raise RuntimeError('--exclusive로 관제·다른 Goal 미실행 상태를 명시해야 합니다.')
        if args.reference is None:
            raise RuntimeError('--reference로 검토한 PLAN_ONLY 기록을 지정해야 합니다.')
        reference=json.loads(args.reference.read_text())
        if reference.get('cycle_id')!=args.cycle_id or reference.get('predecessor_sha256')!=report.get('predecessor_sha256'):raise RuntimeError('계획 단계 연결 불일치')
        require_plan(reference,direction=direction,session=session,source_hash=source_hash,
            baseline_hash=args.baseline_hash,radius=arc.radius,origin=origin)
        no_other_actions()
        # 실패한 부분 회전을 같은 계획으로 다시 실행하지 못하게 사용 표시를 남긴다.
        import os
        marker=str(args.reference)+'.used'
        descriptor=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(descriptor)
        start=time.monotonic();last_session_check=[start]
        def check():
            if time.monotonic()-start>arc.timeout:raise TimeoutError('곡선 시험 시간 초과')
            if gate and gate.error:raise RuntimeError(gate.error)
            no_other_actions(not bool(prefix))
            current=pose()
            if retreating:retreat_error(retreat,current)
            elif aligning:
                require_clearance()
                if math.dist(current[:2],origin[:2])>.005:raise RuntimeError('방향 맞춤 중 위치 이탈')
                if abs(math.atan2(math.sin(current[2]-origin[2]),math.cos(current[2]-origin[2])))>math.radians(16):raise RuntimeError('방향 맞춤 각도 범위 초과')
            else:check_motion(departure_origin,current,arc)
            read('costmap');read('footprint')
            if time.monotonic()-last_session_check[0]>=.2:
                if odom_session()!=session:raise RuntimeError('실행 중 odom 세션 변경')
                last_session_check[0]=time.monotonic()
            with guard:
                if speed_guard.error:raise RuntimeError(speed_guard.error)
        route=RoutePlan(str(time.time_ns()),'', 'odom',tuple((x,y) for x,y,_ in path),(),
                        sum(math.dist(a[:2],b[:2]) for a,b in zip(path,path[1:])),
                        tuple(yaw for _,_,yaw in path))
        if retreating:route=retreat.route
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
            if odom_session()!=session:raise RuntimeError('정지 후 odom 세션 변경')
            end=matrix_pose(poses.lookup('odom','base_footprint',stamp,check_input))
            report['final_pose']=end;report['final_stamp_ns']=stamp
            if retreating:
                report['measurement']=retreat_error(retreat,end)
                accepted=report['measurement']['position_error_m']<=.008
            elif aligning:
                report['measurement']=pose_error(end,target)
                accepted=report['measurement']['position_error_m']<=.008 and report['measurement']['heading_error_rad']<=math.radians(1)
            else:
                report['measurement']=pose_error(end,departure_origin if returning else path[-1])
                if returning:check_return_complete(departure_origin,end,arc)
                else:check_complete(origin,end,arc)
                accepted=True
            if returning and args.cycle_id:
                saved=json.loads(source.read_text())
                map_pose=matrix_pose(poses.lookup('map','base_footprint',stamp,check_input))
                report['final_map_pose']=map_pose
                report['map_return_error']=pose_error(map_pose,saved['start_map_pose'])
                accepted=accepted and report['map_return_error']['position_error_m']<=.02 and report['map_return_error']['heading_error_rad']<=math.radians(1)
            return dict(report['measurement'],accepted=accepted)
        navigator=Navigator(node,settings,client,None,motion,check,explicit_routes=True,
            stop_output=stop_output,settling_check=check_stop,arrival_validator=validate_arrival,
            record=lambda entry:report.update(navigation=entry))
        print('실제 실행 단계:',direction,flush=True)
        with guard:speed_active=True
        owned=True
        if gate:gate.arm(time.monotonic())
        if aligning:
            angle=report['alignment_angle']
            if abs(angle)>math.radians(.5):
                require_clearance()
                spin.execute(angle,40.,check)
            stop_output();stopped()
            stamp=report['stop_checks'][-1]['stamp_ns']
            result=validate_arrival(stamp,check_stop)
            if not result['accepted']:raise RuntimeError('정지 후 재진입 방향 오차 초과')
        elif retreating and retreat.distance<=.005:
            stop_output();stopped()
            result=validate_arrival(report['stop_checks'][-1]['stamp_ns'],check_stop)
            if not result['accepted']:raise RuntimeError('정지 후 후진 목표 위치 오차 초과')
        else:navigator.navigate(path[-1][:2],path[-1][2],route_plan=route,reverse=retreating)
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
                if spin:spin.cancel()
                if navigator:navigator.cancel_nav()
                else:client.cancel()
                stopped();report['cleanup_stopped']=True
            except BaseException as error:report['cleanup_error']=str(error);report['ok']=False
        if clearance_worker is not None:
            try:report['async_clearance']=clearance_worker.close()
            except BaseException as error:report['clearance_cleanup_error']=str(error);report['ok']=False
        try:
            drain_then_close(executor,worker,[motion.close,client.close,poses.close,*([spin.close] if spin else []),
                *(lambda c=c:node.destroy_client(c) for c in service_clients),node.destroy_node,rclpy.try_shutdown])
            report['ros_cleanup_complete']=True
        except Exception as error:
            report['ros_cleanup_error']=str(error);report['ok']=False
        from input_timing import summarize
        report['input_timing_summary']=summarize(report.get('input_trace',[]))
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k not in ('samples','path','input_trace','clearance_check_s')},ensure_ascii=False,indent=2))
        print('기록:',output)
    if not report['ok']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','trial'])
    parser.add_argument('--isolated-prefix',default='')
    parser.add_argument('--baseline-hash',default='')
    parser.add_argument('--radius',type=float,default=.10)
    parser.add_argument('--namespace',default='/harvest_01')
    parser.add_argument('--output',default=str(Path.home()/'Downloads/transfer_arc'))
    parser.add_argument('--reference',type=Path,help='같은 출발 자세에서 PLAN_ONLY에 성공한 JSON')
    parser.add_argument('--return-from',type=Path,help='같은 odom 세션의 성공한 후진 곡선 실행 기록')
    parser.add_argument('--retreat-from',type=Path)
    parser.add_argument('--align-from',type=Path)
    parser.add_argument('--after',type=Path)
    parser.add_argument('--cycle-id',default='')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--exclusive',action='store_true')
    parser.add_argument('--input-trace',action='store_true')
    args=parser.parse_args()
    if args.input_trace and (args.execute or not args.align_from):parser.error('input-trace는 무이동 align 진단만 허용합니다.')
    if args.command=='prepare':prepare()
    else:run(args)
