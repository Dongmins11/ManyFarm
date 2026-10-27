"""벽 정렬 독립 시험 실행기. 기본 check에는 Goal·로봇 속도 발행이 없다."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable


def main() -> None:
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from .wall_shutdown import drain_then_close, start_spin
    import yaml
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.parameter import parameter_value_to_python, Parameter
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
    from rcl_interfaces.srv import ListParameters, GetParameters
    from lifecycle_msgs.srv import ChangeState, GetState
    from action_msgs.msg import GoalStatusArray
    from geometry_msgs.msg import PoseStamped, Twist
    from nav_msgs.msg import Odometry
    from .navigation_types import NavigationSettings, RoutePlan
    from .navigator import Navigator
    from .configuration import read_mapping
    from .motion_monitor import MotionMonitor
    from .nav2_client import Nav2Client
    from .wall_trial_support import isolated_parameters, WallCommandGate
    from .measured_velocity_guard import MeasuredVelocityGuard, MeasuredVelocityLimits
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['check','plan','execute'])
    parser.add_argument('--namespace',required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--exclusive',action='store_true')
    parser.add_argument('--observe-seconds',type=float,default=0.)
    parser.add_argument('--use-sim-time',action='store_true')
    args=parser.parse_args()
    if not math.isfinite(args.observe_seconds) or not 0<=args.observe_seconds<=60:parser.error('관측 시간은 0~60초')
    if args.observe_seconds and args.mode!='plan':parser.error('--observe-seconds는 plan 전용')
    if args.mode=='execute' and (not args.exclusive or not args.reference):parser.error('execute에는 --exclusive --reference 필요')
    ns=args.namespace.rstrip('/');prefix=ns+'/wall_trial_'+uuid.uuid4().hex[:8]
    if not ns.startswith('/'):parser.error('namespace는 절대 이름이어야 합니다')
    config=read_mapping(args.config);c=config['controller']
    target_angle=float(c.get('target_angle',0.))
    if not math.isfinite(target_angle) or abs(target_angle)+c['angle_tolerance']>=c['max_yaw']:
        raise ValueError('벽 목표 각도 범위 오류')
    def angle_error(raw):return math.atan2(math.sin(raw-target_angle),math.cos(raw-target_angle))
    folder=args.output/str(time.time_ns());folder.mkdir(parents=True,exist_ok=False)
    lock=open('/tmp/manyfarm_arc_isolated.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO);node=rclpy.create_node('wall_trial_supervisor',namespace=ns,
        parameter_overrides=[Parameter('use_sim_time',value=args.use_sim_time)])
    executor=SingleThreadedExecutor();executor.add_node(node)
    thread=start_spin(executor)
    guard=threading.RLock();latest={};statuses={};processes=[];logs=[];subscriptions=[];service_clients=[]
    gate=WallCommandGate(c['max_linear'],c['max_angular']);relay=None;owned=False;before=None;client=None;motion=None;navigator=None
    speed_guard=MeasuredVelocityGuard(MeasuredVelocityLimits(**config['measured_velocity']))
    telemetry=[]
    command_trace=[]
    report={'command_trace':command_trace,'timing_samples':[],'velocity_events':speed_guard.events,'samples':telemetry,'ok':False,'mode':args.mode,'prefix':prefix,'config':config,'motion_requested':False}
    def trace_command(stage: str, msg: object) -> None:
        # 메모리 기록만 수행. 속도·판정·발행 순서는 바꾸지 않는다.
        with guard:
            if len(command_trace)<10000:
                command_trace.append({'stage':stage,'receive_ns':node.get_clock().now().nanoseconds,
                                      'monotonic_s':time.monotonic(),
                                      'linear':msg.linear.x,'angular':msg.angular.z})
    def wait(future: object, timeout: float=10.) -> object:
        end=time.monotonic()+timeout
        while not future.done():
            thread.check()
            if time.monotonic()>end or not rclpy.ok():raise TimeoutError('ROS 응답 시간 초과')
            time.sleep(.02)
        return future.result()
    def call(typ: object, name: str, request: object) -> object:
        service=node.create_client(typ,name);service_clients.append(service)
        try:
            if not service.wait_for_service(timeout_sec=5.):raise RuntimeError('서비스 없음: '+name)
            return wait(service.call_async(request),20.)
        finally:pass  # executor 종료 후 서비스 클라이언트를 일괄 제거한다.
    def params(name: str) -> dict:
        names=call(ListParameters,name+'/list_parameters',ListParameters.Request(depth=0)).result.names
        values=call(GetParameters,name+'/get_parameters',GetParameters.Request(names=names)).values
        return dict(zip(names,map(parameter_value_to_python,values)))
    def snapshot() -> dict:
        return {key:params(ns+'/'+key) for key in ('controller_server','local_costmap/local_costmap','velocity_smoother')}
    def transition(number: int) -> None:
        req=ChangeState.Request();req.transition.id=number
        if not call(ChangeState,prefix+'/controller_server/change_state',req).success:raise RuntimeError('lifecycle 실패')
    def start(command: list, name: str) -> None:
        log=open(folder/(name+'.log'),'w');logs.append(log)
        processes.append(subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True))
    def receive(key: str, msg: object) -> None:
        with guard:
            latest[key]=(time.monotonic(),msg,node.get_clock().now().nanoseconds)
            if key=='odom' and owned:
                stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
                v=msg.twist.twist.linear.x;w=msg.twist.twist.angular.z
                telemetry.append({'stamp_ns':stamp,'linear':v,'angular':w})
                try:speed_guard.observe(stamp,v,w)
                except RuntimeError as error:
                    gate.fail(str(error))
                    if relay:relay.publish(Twist())
    def fresh(key: str) -> object:
        with guard:entry=latest.get(key)
        if entry is None:raise RuntimeError('최신 입력 없음: '+key)
        msg=entry[1];stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
        now_ns=node.get_clock().now().nanoseconds
        detail={'key':key,'stamp_ns':stamp,'receive_ns':entry[2],'check_ns':now_ns,
                'age_at_receive_s':(entry[2]-stamp)*1e-9,
                'receipt_age_s':time.monotonic()-entry[0],
                'measurement_age_s':(now_ns-stamp)*1e-9}
        if len(report['timing_samples'])<10000:report['timing_samples'].append(detail)
        if detail['receipt_age_s']>.3:raise RuntimeError('수신 만료: '+json.dumps(detail))
        if stamp<=0 or not 0<=now_ns-stamp<=round(c['observation_age']*1e9):
            raise RuntimeError('입력 시각 오류: '+json.dumps(detail))
        return msg
    def position() -> tuple:
        msg=fresh('odom')
        if msg.header.frame_id!='odom':raise RuntimeError('odom 프레임 불일치')
        p=msg.pose.pose.position;q=msg.pose.pose.orientation
        out=(p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
        if not all(math.isfinite(v) for v in out):raise RuntimeError('odom 값 오류')
        return out
    def wall_error() -> tuple:
        wall=fresh('wall');p=position();q=wall.pose.orientation
        angle=math.atan2(2*q.w*q.z,1-2*q.z*q.z)
        values=(wall.pose.position.x,wall.pose.position.y,q.z,q.w)
        if wall.header.frame_id!='odom' or not all(math.isfinite(v) for v in values) or abs(q.z*q.z+q.w*q.w-1)>.001:
            raise RuntimeError('벽 관측 오류')
        distance=(values[0]-p[0])*math.cos(angle)+(values[1]-p[1])*math.sin(angle)
        return distance,math.atan2(math.sin(angle-p[2]),math.cos(angle-p[2]))
    def no_conflict() -> None:
        with guard:
            active=[k for k,v in statuses.items() if any(s in (1,2,3) for s in v)]
        if active:raise RuntimeError('다른 Action 실행 중: '+','.join(active))
    def check() -> None:
        thread.check()
        if not rclpy.ok():raise RuntimeError('ROS 종료')
        if any(p.poll() is not None for p in processes):raise RuntimeError('독립 시험 프로세스 종료')
        if gate.error:raise RuntimeError(gate.error)
        no_conflict();wall_error()
    try:
        import importlib
        modules={}
        for name in ('navigator','path_builder','arrival','navigation_types','motion_monitor','nav2_client','pose_provider','wall_reference','measured_velocity_guard','wall_observation','wall_trial_support'):
            actual_file=Path(importlib.import_module('farm_navigation.'+name).__file__).resolve()
            source_file=Path(__file__).resolve().parent/(name+'.py')
            digest=lambda file:hashlib.sha256((file.read_text().rstrip()+'\n').encode()).hexdigest()
            if digest(actual_file)!=digest(source_file):raise RuntimeError('설치/소스 공통 모듈 불일치: '+name)
            modules[name]={'path':str(actual_file),'sha256':digest(actual_file)}
        report['common_modules']=modules
        before=snapshot();report['baseline_hash']=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()
        (folder/'baseline_before.json').write_text(json.dumps(before,indent=2))
        if bool(before['controller_server'].get('use_sim_time',False))!=args.use_sim_time:raise RuntimeError('시계 설정 불일치')
        if call(GetState,ns+'/controller_server/get_state',GetState.Request()).current_state.id!=3:raise RuntimeError('기존 주행 서버 비활성')
        sources=node.get_subscriber_names_and_types_by_node('local_costmap',ns+'/local_costmap')
        scans=[name for name,types in sources if 'sensor_msgs/msg/LaserScan' in types]
        if len(scans)!=1:raise RuntimeError('실제 라이다 구독을 하나로 확인하지 못함')
        conf=isolated_parameters(before['controller_server'],before['local_costmap/local_costmap'],prefix,scans[0],ns+'/odom',config)
        path=folder/'parameters.yaml';path.write_text(yaml.safe_dump(conf,sort_keys=False))
        start(['ros2','run','nav2_controller','controller_server','--ros-args','-r','__ns:='+prefix,
            '--params-file',str(path),'-r','/tf:='+ns+'/tf','-r','/tf_static:='+ns+'/tf_static',
            '-r','cmd_vel:='+prefix+'/raw_cmd_vel'],'controller')
        transition(1)
        actual=params(prefix+'/controller_server')
        for k,v in conf[prefix+'/controller_server']['ros__parameters'].items():
            if actual.get(k)!=v:raise RuntimeError('제어기 적용값 불일치: '+k)
        actual_cm=params(prefix+'/local_costmap/local_costmap')
        for k,v in conf[prefix+'/local_costmap/local_costmap']['ros__parameters'].items():
            if k in actual_cm and actual_cm[k]!=v:raise RuntimeError('costmap 적용값 불일치: '+k)
        publishers=node.get_publisher_names_and_types_by_node('controller_server',prefix)
        outputs=[name for name,types in publishers if any(t in ('geometry_msgs/msg/Twist','geometry_msgs/msg/TwistStamped') for t in types)]
        if outputs != [prefix+'/raw_cmd_vel']:raise RuntimeError('독립 속도 출력 분리 확인 실패')
        if call(GetState,prefix+'/controller_server/get_state',GetState.Request()).current_state.id!=2:raise RuntimeError('configure 후 inactive 확인 실패')
        report['configured']=True
        if args.mode=='check':report['ok']=True;return
        # 빌드된 동일 패키지에서 관측 노드를 실행한다.
        cmd=[sys.executable,'-m','farm_navigation.wall_observer_node','--config',str(args.config.resolve()),'--namespace',prefix,'--scan',scans[0],
             '--timing-output',str(folder/'observer_timing.jsonl'),'--ros-args','-r','/tf:='+ns+'/tf','-r','/tf_static:='+ns+'/tf_static']
        if args.use_sim_time:cmd.insert(3,'--use-sim-time')
        start(cmd,'observer')
        subscriptions.append(node.create_subscription(PoseStamped,prefix+'/wall_observation',lambda m:receive('wall',m),1))
        subscriptions.append(node.create_subscription(Odometry,ns+'/odom',lambda m:receive('odom',m),qos_profile_sensor_data))
        qos=QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        for action in ('harvest_task','return_to_station','dock_transfer','navigate_to_pose','navigate_through_poses',
                       'follow_path','spin','backup','drive_on_heading','assisted_teleop'):
            def status(msg: object,key: str=action) -> None:
                with guard:statuses[key]=[s.status for s in msg.status_list]
            subscriptions.append(node.create_subscription(GoalStatusArray,ns+'/'+action+'/_action/status',status,qos))
        motion=MotionMonitor(node,NavigationSettings(odom_topic=ns+'/odom',settle_s=.8,settle_timeout_s=5.),ReentrantCallbackGroup())
        transition(3)
        if call(GetState,prefix+'/controller_server/get_state',GetState.Request()).current_state.id!=3:raise RuntimeError('activate 후 active 확인 실패')
        deadline=time.monotonic()+10
        while True:
            try:check();break
            except RuntimeError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        motion.wait_stopped(check)
        origin=position();distance,angle=wall_error()
        if distance<c['target_distance']-c['distance_tolerance'] or distance-c['target_distance']>c['max_distance']:
            raise RuntimeError('목표 거리와 시작 거리 범위 불일치')
        if abs(angle)>c['max_yaw'] or abs(angle_error(angle))>c['max_yaw']:raise RuntimeError('시작 각도 범위 초과')
        if snapshot()!=before:raise RuntimeError('시험 준비 중 기존 설정 변경')
        report.update(origin=origin,wall_distance=distance,wall_angle=angle,wall_angle_error=angle_error(angle),target_angle=target_angle,phase='PLAN_ONLY')
        if args.mode=='plan':
            until=time.monotonic()+args.observe_seconds
            while time.monotonic()<until:
                check();time.sleep(.02)
            report['ok']=True
            return
        reference=json.loads(args.reference.read_text())
        if not reference.get('ok') or reference.get('phase')!='PLAN_ONLY' or reference['config']!=config or reference['baseline_hash']!=report['baseline_hash']:
            raise RuntimeError('계획 설정 불일치')
        ref=reference['origin']
        if math.hypot(origin[0]-ref[0],origin[1]-ref[1])>.005 or abs(math.atan2(math.sin(origin[2]-ref[2]),math.cos(origin[2]-ref[2])))>.02:
            raise RuntimeError('계획 이후 출발 자세 변경')
        if abs(reference['wall_distance']-distance)>.005 or abs(reference['wall_angle']-angle)>.02:raise RuntimeError('계획 이후 벽 관측 변경')
        smooth=before['velocity_smoother']
        if not 0<smooth.get('velocity_timeout',0)<=1:raise RuntimeError('smoother 만료시간 부적합')
        links=node.get_subscriber_names_and_types_by_node('velocity_smoother',ns)
        if (ns+'/cmd_vel_nav') not in [name for name,types in links if 'geometry_msgs/msg/Twist' in types]:raise RuntimeError('smoother 연결 불일치')
        report['velocity_connections']={}
        for topic in (ns+'/cmd_vel_nav',ns+'/cmd_vel'):
            report['velocity_connections'][topic]={
                'publishers':[{'node':info.node_namespace.rstrip('/')+'/'+info.node_name,'type':info.topic_type}
                              for info in node.get_publishers_info_by_topic(topic)],
                'subscribers':[{'node':info.node_namespace.rstrip('/')+'/'+info.node_name,'type':info.topic_type}
                               for info in node.get_subscriptions_info_by_topic(topic)]}
        subscriptions.append(node.create_subscription(Twist,ns+'/cmd_vel_nav',lambda m:trace_command('cmd_vel_nav_observed',m),qos_profile_sensor_data))
        subscriptions.append(node.create_subscription(Twist,ns+'/cmd_vel',lambda m:trace_command('cmd_vel_observed',m),qos_profile_sensor_data))
        relay=node.create_publisher(Twist,ns+'/cmd_vel_nav',1)
        def forward(msg: Twist) -> None:
            trace_command('controller_raw',msg)
            with guard:
                if not gate.enabled:return
                try:
                    check()
                    if any(not math.isfinite(v) or abs(v)>1e-9 for v in (msg.linear.y,msg.linear.z,msg.angular.x,msg.angular.y)):
                        raise RuntimeError('차체 평면 외 명령')
                    if gate.accept(msg.linear.x,msg.angular.z,time.monotonic()):
                        relay.publish(msg);trace_command('gate_forwarded',msg)
                    else:relay.publish(Twist())
                except Exception as error:gate.fail(str(error));relay.publish(Twist())
        subscriptions.append(node.create_subscription(Twist,prefix+'/raw_cmd_vel',forward,1))
        def watchdog() -> None:
            with guard:
                if gate.expired(time.monotonic()):relay.publish(Twist())
        node.create_timer(.05,watchdog)
        settings=NavigationSettings(mode='follow_path',map_frame='odom',follow_action=prefix+'/follow_path',
            controller_node=prefix+'/controller_server',controller_id='WallAlign',goal_checker_id='wall_goal',
            progress_checker_id='wall_progress',goal_timeout_s=c['timeout'],response_timeout_s=5.,cancel_timeout_s=5.,
            arrival_tolerance_m=c['distance_tolerance'],heading_tolerance_rad=c['angle_tolerance'])
        client=Nav2Client(node,settings,ReentrantCallbackGroup())
        client.preflight(check, wall_parameters=c)
        # 기존 두 점·차체 방향을 그대로 공통 경로 생성기에 전달한다.
        yaw=origin[2]+angle-target_angle
        points=tuple((origin[0]+offset*math.cos(origin[2]+angle),
                      origin[1]+offset*math.sin(origin[2]+angle))
                     for offset in (0.,max(.001,distance-c['target_distance'])))
        route=RoutePlan(uuid.uuid4().hex,'', 'odom',points,(),math.dist(*points),(yaw,yaw))
        def stop_output() -> None:
            with guard:gate.close();relay.publish(Twist())
        def validate_arrival(stamp: int, check_input: Callable[[], None]) -> dict:
            check_input()
            d,a=wall_error()
            measured=dict(final_distance=d,final_angle=a,final_angle_error=angle_error(a),
                accepted=abs(d-c['target_distance'])<=c['distance_tolerance'] and abs(angle_error(a))<=c['angle_tolerance'])
            report.update(measured)
            return measured
        check();fd=os.open(str(args.reference)+'.used',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        owned=True;report['motion_requested']=True;report['phase']='EXECUTING';gate.arm(time.monotonic())
        print('실제 벽 접근 실행',flush=True)
        start_time=time.monotonic()
        def running_check() -> None:
            check()
            if time.monotonic()-start_time>c['timeout']:raise TimeoutError('벽 시험 실시간 제한 초과')
        navigator=Navigator(node,settings,client,None,motion,running_check,explicit_routes=True,
            stop_output=stop_output,settling_check=check,arrival_validator=validate_arrival,
            record=lambda entry:report.update(navigation=entry))
        navigator.navigate(points[-1],yaw,route_plan=route)
        report.update(ok=True,phase='SUCCEEDED')
    except BaseException as error:report['error']=str(error) or type(error).__name__
    finally:
        with guard:
            gate.close()
            if owned and relay:relay.publish(Twist())
        if owned:
            try:
                if navigator:navigator.cancel_nav()
                elif client:client.cancel()
                motion.wait_stopped(lambda: None);report['cleanup_stopped']=True
            except BaseException as error:report['cleanup_error']=str(error);report['ok']=False
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGINT)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        for log in logs:log.close()
        if before:
            try:
                after=snapshot();report['baseline_unchanged']=before==after
                (folder/'baseline_after.json').write_text(json.dumps(after,indent=2))
                if before!=after:report['ok']=False;report['baseline_error']='기존 설정 변경 감지'
            except Exception as error:report['ok']=False;report['baseline_error']=str(error)
        closers=[]
        if client:closers.append(client.close)
        if motion:closers.append(motion.close)
        closers.extend(lambda service=service:node.destroy_client(service) for service in service_clients)
        closers.extend([node.destroy_node,rclpy.try_shutdown])
        try:
            drain_then_close(executor,thread,closers)
            report['ros_cleanup_complete']=True
        except Exception as error:
            report['ros_cleanup_error']=str(error);report['ok']=False
        report['command_summary']={}
        for stage in ('controller_raw','gate_forwarded','cmd_vel_nav_observed','cmd_vel_observed'):
            rows=[r for r in command_trace if r['stage']==stage]
            report['command_summary'][stage]={
                'count':len(rows),'nonzero_count':sum(abs(r['linear'])>1e-6 or abs(r['angular'])>1e-6 for r in rows),
                'max_abs_linear':max([abs(r['linear']) for r in rows] or [0.]),
                'max_abs_angular':max([abs(r['angular']) for r in rows] or [0.])}
        report['odom_velocity_summary']={'count':len(telemetry),
            'max_abs_linear':max([abs(r['linear']) for r in telemetry] or [0.]),
            'max_abs_angular':max([abs(r['angular']) for r in telemetry] or [0.])}
        report['timing_summary']={} 
        for key in ('wall','odom'):
            rows=[r for r in report['timing_samples'] if r['key']==key]
            if rows:report['timing_summary'][key]={
                'count':len(rows),
                'max_measurement_age_s':max(r['measurement_age_s'] for r in rows),
                'max_age_at_receive_s':max(r['age_at_receive_s'] for r in rows),
                'max_receipt_age_s':max(r['receipt_age_s'] for r in rows)}
        timing_path=folder/'observer_timing.jsonl'
        if timing_path.exists():
            rows=[]
            for line in timing_path.read_text().splitlines():
                try:rows.append(json.loads(line))
                except ValueError:pass
            report['observer_timing_summary']={'frames':len(rows)}
            for key in ('arrival_age_s','queue_s','tf_s','fit_s','publish_age_s'):
                values=[r[key] for r in rows if key in r]
                if values:report['observer_timing_summary'][key]={'min':min(values),'max':max(values)}
            report['observer_timing_summary']['errors']=[r for r in rows if 'error' in r][-3:]
        (folder/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k not in ('samples','timing_samples','command_trace')},ensure_ascii=False,indent=2));print('기록:',folder/'result.json')
        if not report['ok']:raise SystemExit(1)

if __name__=='__main__':main()
