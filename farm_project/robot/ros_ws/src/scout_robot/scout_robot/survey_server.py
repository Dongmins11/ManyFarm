from scout_robot.graph_harvest_goal import load_harvest_route
"""ScoutArea → B stop/capture/accumulate → one task batch at bed completion."""
import json
import math
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime,timezone
import numpy as np
import rclpy
from rclpy.action import ActionClient,ActionServer,GoalResponse,CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import parameter_value_to_python
from rclpy.signals import SignalHandlerOptions
from rclpy.time import Time
from rcl_interfaces.srv import GetParameters
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker,MarkerArray
from tf2_ros import Buffer,TransformListener
from farm_interfaces.action import ScoutArea
from farm_interfaces.msg import HarvestTask
from .task_messages import tasks_from_windows, task_record
from .route import load_route
from .survey_core import StraightBed,Survey,matrix_from_pose,transform_points
from .arrival import (NavigationConfigurationError,validate_goal_checkers,
                      measure_arrival,arrival_description)
from .segments import plan_segments


def utc():return datetime.now(timezone.utc).isoformat()

def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False));tmp.replace(path)


class MissionCanceled(RuntimeError):pass


class Worker:
    def __init__(self,command,log):
        self.q=queue.Queue();self.serial=0;self.log=Path(log).open('w')
        self.p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,text=True,bufsize=1)
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
    def read(self):
        for line in self.p.stdout:
            self.log.write(line);self.log.flush()
            if line.startswith('FARM_RPC '):
                try:self.q.put(json.loads(line[9:]))
                except ValueError:pass
        self.q.put({'dead':True})
    def receive(self,check,timeout):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            check()
            try:
                v=self.q.get(timeout=.05)
                if v.get('dead'):raise RuntimeError('Vision worker exited; see vision_worker.log')
                return v
            except queue.Empty:pass
        raise RuntimeError('Vision worker timeout; see vision_worker.log')
    def call(self,op,check,**kw):
        self.serial+=1
        self.p.stdin.write(json.dumps(dict(id=self.serial,op=op,**kw),allow_nan=False)+'\n');self.p.stdin.flush()
        v=self.receive(check,30)
        if v.get('id')!=self.serial:raise RuntimeError('Vision response sequence mismatch')
        if not v.get('ok'):raise RuntimeError(v.get('error','Vision failed'))
        return v['result']
    def close(self):
        if self.p.poll() is None:
            try:self.p.stdin.write('{"op":"stop"}\n');self.p.stdin.flush();self.p.wait(timeout=2)
            except (BrokenPipeError,subprocess.TimeoutExpired):
                self.p.terminate()
                try:self.p.wait(timeout=2)
                except subprocess.TimeoutExpired:self.p.kill();self.p.wait()
        self.thread.join(timeout=2);self.log.close()


class SurveyServer(Node):
    def __init__(self):
        super().__init__('scout_survey')
        for key,value in [('project_root',''),('survey_config',''),('vision_python',''),('device','0'),('headless',False)]:
            self.declare_parameter(key,value)
        self.root=Path(self.get_parameter('project_root').value).expanduser().resolve()
        config=Path(self.get_parameter('survey_config').value).expanduser()
        self.cfg=json.loads(config.read_text())
        if self.cfg.get('configured',True) is not True:
            raise ValueError('This survey config is an unconfigured template; fill real bed/device settings first')
        self.vcfg=json.loads((self.root/self.cfg['vision_config']).read_text())
        self.python=Path(self.get_parameter('vision_python').value).expanduser()
        if not self.python.is_file():raise ValueError('vision_python must be the YOLO environment Python path')
        self.beds={}
        for key,c in self.cfg['sections'].items():
            self.beds[key]=StraightBed(load_route(self.root/c['route_file'],c['node_ids']),c, harvest_route=load_harvest_route(self.root, c))
        self.cb=ReentrantCallbackGroup();self.lock=threading.Lock();self.busy=False
        self.shutdown_requested=False;self.active_goal=None;self.nav_handle=None;self.pending_nav=None
        self.odom=None;self.odom_wall=0.;self.odom_lock=threading.Lock()
        self.tf=Buffer(cache_time=Duration(seconds=30));self.listener=TransformListener(self.tf,self)
        self.nav=ActionClient(self,NavigateToPose,'navigate_to_pose',callback_group=self.cb)
        self.controller_node=self.cfg.get('controller_node','controller_server')
        self.nav_parameters=self.create_client(GetParameters,
            self.controller_node.rstrip('/')+'/get_parameters',callback_group=self.cb)
        self.navigation_log=[]
        self.create_subscription(Odometry,'odom',self.on_odom,10,callback_group=self.cb)
        self.markers=self.create_publisher(MarkerArray,'survey_markers',10)
        self.last_markers=None;self.create_timer(1.,self.repeat_markers,callback_group=self.cb)
        self.server=ActionServer(self,ScoutArea,'scout_area',execute_callback=self.execute,
            goal_callback=self.accept,cancel_callback=lambda _:CancelResponse.ACCEPT,callback_group=self.cb)
        self.get_logger().info('ScoutArea 준비. 시작 명령 전에는 주행하지 않습니다. 임시 section: '+','.join(self.beds))

    def on_odom(self,msg):
        with self.odom_lock:self.odom=msg;self.odom_wall=time.monotonic()
    def repeat_markers(self):
        if self.last_markers is not None:self.markers.publish(self.last_markers)
    def accept(self,g):
        valid=(g.robot_id==self.cfg['robot_id'] and g.frame_id=='map' and g.map_id==self.cfg['map_id']
            and g.crop_type=='PAPRIKA' and g.target_ripeness=='RIPE' and bool(g.task_id)
            and bool(g.section_id) and g.section_id in self.beds)
        with self.lock:
            if self.busy or self.shutdown_requested or not valid:
                self.get_logger().error('Goal 거절: 실행 중이거나 robot/map/section/crop 규격 불일치')
                return GoalResponse.REJECT
            self.busy=True
        return GoalResponse.ACCEPT
    def check(self):
        if self.shutdown_requested or not rclpy.ok() or (self.active_goal and self.active_goal.is_cancel_requested):
            raise MissionCanceled('ScoutArea canceled')
    def wait(self,future,timeout,check=True):
        end=time.monotonic()+timeout
        while not future.done() and time.monotonic()<end:
            if check:self.check()
            time.sleep(.02)
        if not future.done():raise RuntimeError('ROS response timeout')
        return future.result()
    def read_nav_parameters(self,names):
        request=GetParameters.Request();request.names=names
        response=self.wait(self.nav_parameters.call_async(request),5)
        if response is None or len(response.values)!=len(names):
            raise RuntimeError('Nav2 parameter response missing values')
        return {name:parameter_value_to_python(value) for name,value in zip(names,response.values)}
    def preflight_navigation(self,report):
        deadline=time.monotonic()+60
        while not self.nav.server_is_ready() or not self.nav_parameters.service_is_ready():
            self.check()
            if time.monotonic()>deadline:
                raise RuntimeError('Nav2/action or controller parameter service unavailable; start navigation first')
            time.sleep(.1)
        parameters=self.read_nav_parameters(['goal_checker_plugins'])
        snapshot={'controller_node':self.controller_node,'checked_at':utc(),
                  'parameters':parameters,'status':'CHECKING'}
        report['navigation_preflight']=snapshot
        ids=parameters.get('goal_checker_plugins')
        if isinstance(ids,list) and ids and all(isinstance(i,str) and i for i in ids):
            parameters.update(self.read_nav_parameters([
                f'{i}.{key}' for i in ids for key in
                ['plugin','xy_goal_tolerance','yaw_goal_tolerance','stateful','symmetric_yaw_tolerance']]))
        try:
            snapshot['checkers']=validate_goal_checkers(parameters,
                self.cfg['arrival_tolerance_m'],self.cfg['heading_tolerance_rad'])
        except NavigationConfigurationError:
            snapshot['status']='FAILED';raise
        snapshot['status']='OK'
        for checker in snapshot['checkers']:
            self.get_logger().info(
                f"Nav2 실제 도착 기준: {checker['id']} "
                f"거리 {checker['xy_goal_tolerance']:.3f}m / 방향 {checker['yaw_goal_tolerance']:.3f}rad "
                f"(예찰 기준 {self.cfg['arrival_tolerance_m']:.3f}m / {self.cfg['heading_tolerance_rad']:.3f}rad)")
    def cancel_nav(self):
        if self.nav_handle is None and self.pending_nav is not None:
            self.nav_handle=self.wait(self.pending_nav,10,False)
        if self.nav_handle and self.nav_handle.accepted:
            result=self.nav_handle.get_result_async()
            self.wait(self.nav_handle.cancel_goal_async(),10,False)
            terminal=self.wait(result,10,False).status
            if terminal not in (GoalStatus.STATUS_CANCELED,GoalStatus.STATUS_ABORTED,GoalStatus.STATUS_SUCCEEDED):
                raise RuntimeError('Nav2 goal termination not confirmed')
        self.nav_handle=self.pending_nav=None
    def navigate(self,xy,yaw):
        self.check()
        entry={'goal_map':{'x':float(xy[0]),'y':float(xy[1]),'yaw':float(yaw)},
               'started_at':utc(),'status':'MOVING'}
        self.navigation_log.append(entry)
        goal=NavigateToPose.Goal();goal.pose.header.frame_id='map';goal.pose.header.stamp=self.get_clock().now().to_msg()
        goal.pose.pose.position.x=float(xy[0]);goal.pose.pose.position.y=float(xy[1])
        goal.pose.pose.orientation.z=math.sin(yaw/2);goal.pose.pose.orientation.w=math.cos(yaw/2)
        self.pending_nav=self.nav.send_goal_async(goal)
        self.nav_handle=self.wait(self.pending_nav,15)
        if not self.nav_handle.accepted:self.pending_nav=None;self.nav_handle=None;raise RuntimeError('Nav2 goal rejected')
        result=self.wait(self.nav_handle.get_result_async(),self.cfg['goal_timeout_s'])
        self.nav_handle=self.pending_nav=None
        entry['nav2_status']=int(result.status)
        if result.status!=GoalStatus.STATUS_SUCCEEDED:raise RuntimeError(f'Nav2 failed: {result.status}')
        # The action may finish before the velocity smoother/robot has stopped.
        # Check the pose at fresh, settled odometry time, not an arbitrary latest TF.
        entry['status']='SETTLING'
        stamp=self.settled()
        actual=self.lookup('map',self.cfg['base_frame'],stamp)
        measured=measure_arrival(actual,xy,yaw,self.cfg['arrival_tolerance_m'],self.cfg['heading_tolerance_rad'])
        entry.update(measured,stamp_ns=int(stamp),finished_at=utc(),
                     status='ARRIVED' if measured['accepted'] else 'OUTSIDE_TOLERANCE')
        message=arrival_description(measured)
        if not measured['accepted']:
            raise RuntimeError('Nav2 succeeded but settled pose is outside survey tolerance: '+message)
        self.get_logger().info('정지 후 도착 확인: '+message)
        return stamp
    def lookup(self,target,source,stamp):
        end=time.monotonic()+3;error=None
        while time.monotonic()<end:
            self.check()
            try:
                v=self.tf.lookup_transform(target,source,Time(nanoseconds=int(stamp))).transform
                return matrix_from_pose([v.translation.x,v.translation.y,v.translation.z],
                    [v.rotation.x,v.rotation.y,v.rotation.z,v.rotation.w])
            except Exception as e:error=e;time.sleep(.02)
        raise RuntimeError(f'TF missing at capture time: {target} <- {source}: {error}')
    def settled(self):
        end=time.monotonic()+20;start=None;prev=None
        while time.monotonic()<end:
            self.check()
            with self.odom_lock:msg=self.odom;age=time.monotonic()-self.odom_wall
            if msg and age<.5:
                ns=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
                twist=msg.twist.twist
                stationary=abs(twist.linear.x)<.005 and abs(twist.linear.y)<.005 and abs(twist.angular.z)<.02
                if prev is not None and ns<prev:raise RuntimeError('Simulation time moved backwards')
                prev=ns
                if stationary:
                    if start is None:start=ns
                    if ns-start>=int(self.cfg['settle_s']*1e9):return ns
                else:start=None
            else:start=None
            time.sleep(.03)
        raise RuntimeError('Robot did not stop / odometry is stale')
    def stationary_now(self):
        with self.odom_lock:m=self.odom;age=time.monotonic()-self.odom_wall
        return bool(m and age<.5 and abs(m.twist.twist.linear.x)<.005 and abs(m.twist.twist.angular.z)<.02)
    def feedback(self,g,section,phase,tasks,completed,segments,segment_id,segment_expected_count):
        f=ScoutArea.Feedback();f.robot_id=g.request.robot_id;f.task_id=g.request.task_id
        f.phase=phase;f.section_id=section;f.segment_id=segment_id
        f.completed_segment_count=segments;f.timestamp=utc();f.harvest_tasks=tasks
        f.segment_expected_count=int(segment_expected_count)
        g.publish_feedback(f)
    def show(self,survey):
        array=MarkerArray();clear=Marker();clear.action=Marker.DELETEALL;array.markers.append(clear)
        for i,f in enumerate(survey.fruits):
            m=Marker();m.header.frame_id='map';m.ns='fruit';m.id=i;m.type=Marker.SPHERE;m.action=Marker.ADD
            m.pose.orientation.w=1.;m.pose.position=Point(x=f['position_map_m'][0],y=f['position_map_m'][1],z=f['position_map_m'][2])
            m.scale.x=m.scale.y=m.scale.z=.04;m.color.r=1.;m.color.g=0. if f['class_name']=='Red' else 1.;m.color.a=1.
            array.markers.append(m)
            t=Marker();t.header.frame_id='map';t.ns='fruit_id';t.id=i;t.type=Marker.TEXT_VIEW_FACING;t.action=Marker.ADD
            t.pose.orientation.w=1.;t.pose.position=Point(x=m.pose.position.x,y=m.pose.position.y,z=m.pose.position.z+.05)
            t.text=f['id'];t.scale.z=.045;t.color.r=t.color.g=t.color.b=t.color.a=1.;array.markers.append(t)
        edges=[(0,1),(0,2),(1,3),(2,3),(4,5),(4,6),(5,7),(6,7),(0,4),(1,5),(2,6),(3,7)]
        for i,w in enumerate(survey.windows()):
            m=Marker();m.header.frame_id='map';m.ns='window';m.id=i;m.type=Marker.LINE_LIST;m.action=Marker.ADD
            m.pose.orientation.w=1.;m.scale.x=.008;m.color.r=m.color.b=m.color.a=1.
            for a,b in edges:
                for j in [a,b]:m.points.append(Point(x=w['corners_map_m'][j][0],y=w['corners_map_m'][j][1],z=w['corners_map_m'][j][2]))
            array.markers.append(m)
            if w.get('range_tolerance_m',0)>0 or w.get('depth_tolerance_m',0)>0:
                outer=Marker();outer.header.frame_id='map';outer.ns='window_tolerance';outer.id=i
                outer.type=Marker.LINE_LIST;outer.action=Marker.ADD;outer.pose.orientation.w=1.
                outer.scale.x=.004;outer.color.g=outer.color.b=outer.color.a=1.
                for a,b in edges:
                    for j in [a,b]:
                        p=w['acceptance_corners_map_m'][j]
                        outer.points.append(Point(x=p[0],y=p[1],z=p[2]))
                array.markers.append(outer)
        self.last_markers=array;self.repeat_markers()

    def execute(self,g):
        self.active_goal=g;worker=None;survey=None;section=None;started_wall=time.monotonic()
        session=uuid.uuid4().hex[:12];folder=self.root/self.cfg['output_dir']/session
        folder.mkdir(parents=True,exist_ok=False)
        report={'session_id':session,'goal':{k:getattr(g.request,k) for k in ['robot_id','task_id','section_id','map_id','frame_id','crop_type','target_ripeness']},
                'config':self.cfg,'vision_config':self.vcfg,'started_at':utc(),'status':'RUNNING','sections':{},'observations':[]}
        self.navigation_log=[];report['navigation']=self.navigation_log
        result=ScoutArea.Result();result.robot_id=g.request.robot_id;result.task_id=g.request.task_id
        completed=[];total_tasks=0;total_fruits=0;completed_segments=0;current_segment=None;stored_tasks=[]
        report['completed_segments']=[];report['completed_segment_count']=0
        try:
            self.preflight_navigation(report)
            write_json(folder/'survey.json',report)
            command=[str(self.python),str(self.root/'scripts/run_scout_survey_worker.py'),'--config',str(self.root/self.cfg['vision_config']),
                     '--device',str(self.get_parameter('device').value)]
            if self.get_parameter('headless').value:command+=['--headless']
            worker=Worker(command,folder/'vision_worker.log')
            if not worker.receive(self.check,120).get('ready'):raise RuntimeError('Vision worker failed to initialize')
            camera_session=None
            for section in [g.request.section_id]:
                bed=self.beds[section];survey=Survey(bed,session+'_'+section,self.cfg['association_distance_m'])
                stamp=self.navigate(bed.origin,bed.yaw)
                info=worker.call('info',self.check,after_stamp_ns=stamp,session=camera_session)
                meta=info['metadata'];camera_session=meta['session']
                B=self.lookup(meta['pose_frame'],self.cfg['base_frame'],meta['stamp_ns'])
                C=np.linalg.inv(B)@np.array(meta['T_odom_camera_optical'])
                design=plan_segments(bed,section,meta['K'],C,info['width'],info['height'],self.vcfg['preprocess'],self.cfg['overlap_fraction'])
                report['sections'][section]={'design':design,'status':'RUNNING','survey':survey.record(),'segments':[]}
                write_json(folder/'survey.json',report)
                for index,segment in enumerate(design['segments']):
                    sid=segment['segment_id'];s=segment['offset_m'];segment_start=time.monotonic()
                    current_segment=dict(segment,status='MOVING',started_at=utc())
                    report['sections'][section]['segments'].append(current_segment)
                    self.get_logger().info(f'{section}/{sid}: 촬영 지점 {index+1}/{len(design["segments"])} 이동 s={s:.2f}m')
                    stamp=self.navigate(bed.world(s,0),bed.yaw)
                    current_segment['navigation_wall_s']=time.monotonic()-segment_start
                    capture_start=time.monotonic();current_segment.update(status='CAPTURING',capture_started_at=utc())
                    response=worker.call('capture',self.check,after_stamp_ns=stamp,session=camera_session)
                    if not self.stationary_now():raise RuntimeError('Robot moved during observation; result rejected')
                    meta=response['metadata'];T=self.lookup('map',meta['pose_frame'],meta['stamp_ns'])
                    accepted=[];labels=[];ignored=[]
                    for d in response['detections']:
                        q=transform_points(T,[d['position_odom_m']])[0].tolist();local=bed.local(q)
                        # Context padding may see outside the requested route or another bed.
                        if not (0<=local[0]<=bed.length and abs(local[1]-bed.bed_n)<=self.cfg['association_band_half_depth_m']):
                            ignored.append(dict(d,position_map_m=q,reason='outside_section_or_bed_band'));continue
                        accepted.append(dict(d,position_map_m=q,stamp_ns=int(meta['stamp_ns'])))
                    ids=survey.ingest(accepted,segment_id=sid)
                    # Count this capture, not cumulative IDs or window/task membership.
                    segment_expected_count=len(set(ids))
                    current_segment['segment_expected_count']=segment_expected_count
                    report['observations'].append({'section':section,'segment_id':sid,'index':index+1,'stamp_ns':int(meta['stamp_ns']),
                        'timings':response['timings'],'valid_depth_detection_count':len(response['detections']),
                        'depth_rejected_count':len(response['rejected']),'section_accepted_count':len(accepted),'segment_expected_count':segment_expected_count,
                        'outside_section_count':len(ignored)})
                    for d,fruit_id in zip(accepted,ids):labels.append({'id':fruit_id,'box':d['mask_box_original_xyxy']})
                    worker.call('annotate',self.check,stamp_ns=int(meta['stamp_ns']),T_map_odom=T.tolist(),labels=labels,
                        windows=survey.windows(),section_id=section,segment_id=sid,
                        directory=str(folder/section/f'observation_{index+1:03d}'))
                    write_json(folder/section/f'observation_{index+1:03d}'/'map_detections.json',
                        {'section_id':section,'segment_id':sid,'accepted':accepted,'ids':ids,'ignored':ignored})
                    current_segment.update(status='COMPLETE',finished_at=utc(),
                        observation_wall_s=time.monotonic()-capture_start,elapsed_wall_s=time.monotonic()-segment_start)
                    completed_segments+=1
                    report['completed_segments'].append({'section_id':section,'segment_id':sid})
                    report['completed_segment_count']=completed_segments
                    report['sections'][section]['survey']=survey.record()
                    pending_tasks=tasks_from_windows(report['sections'][section]['survey']['windows'])
                    report['sections'][section]['batch']=[task_record(t) for t in pending_tasks]
                    write_json(folder/'survey.json',report)
                    stored_tasks=pending_tasks
                    self.show(survey)
                    self.feedback(g,section,'SEGMENT_COMPLETE',[],len(completed),completed_segments,sid,segment_expected_count)
                    self.get_logger().info(f'{sid} 완료: 누적 segment={completed_segments}, 촬영·처리·저장 {current_segment["observation_wall_s"]:.3f}s')
                    current_segment=None
                self.check();batch_start=time.monotonic()
                tasks=list(stored_tasks)
                report['sections'][section]['status']='COMPLETE'
                report['sections'][section]['batch']=[task_record(t) for t in tasks]
                # Durable detail before the one feedback containing this bed's task list.
                write_json(folder/'survey.json',report)
                completed.append(section);total_tasks+=len(tasks);total_fruits+=sum(t.expected_count for t in tasks)
                self.feedback(g,section,'SECTION_COMPLETE',[],len(completed),completed_segments,'',0)
                report['sections'][section]['batch_finalize_wall_s']=time.monotonic()-batch_start
                self.get_logger().info(f'{section} 완료: {len(survey.fruits)} IDs, {len(tasks)} tasks, {len(survey.plan.holds)} holds')
                # Optional transit is after survey completion; no extra feedback.
                tail_start=time.monotonic()
                tail={'finish_at':design['finish_at'],'started_at':utc(),'status':'SKIPPED'}
                report['sections'][section]['post_capture_navigation']=tail
                if design['finish_at']=='route_end' and design['segments'][-1]['offset_m']<bed.length-1e-6:
                    tail['status']='MOVING'
                    self.get_logger().info(f'{section}: 모든 촬영 완료. 경로 끝까지 추가 주행 {bed.length-design["segments"][-1]["offset_m"]:.3f}m')
                    self.navigate(bed.world(bed.length,0),bed.yaw);tail['status']='ARRIVED'
                else:self.get_logger().info(f'{section}: 마지막 segment 촬영 완료. 추가 주행 없이 결과 정리')
                tail.update(finished_at=utc(),elapsed_wall_s=time.monotonic()-tail_start)
            result.result_code='SUCCESS';result.error_code='NONE';report['status']='SUCCESS';g.succeed()
        except Exception as e:
            canceled=isinstance(e,MissionCanceled)
            try:self.cancel_nav()
            except Exception as cancel_error:
                self.get_logger().error(f'Nav2 취소 확인 실패. bringup을 종료하세요: {cancel_error}')
            result.result_code='CANCELED' if canceled else 'FAILED';result.error_code='CANCELED' if canceled else 'SURVEY_FAILED'
            if isinstance(e,NavigationConfigurationError):result.error_code='NAV_CONFIG_MISMATCH'
            result.error_message=str(e);report['status']=result.result_code;report['error']=str(e)
            if current_segment and current_segment['status']!='COMPLETE':
                current_segment.update(status=result.result_code,error=str(e),finished_at=utc())
            if self.navigation_log and self.navigation_log[-1]['status'] in ('MOVING','SETTLING'):
                self.navigation_log[-1].update(status=result.result_code,error=str(e),finished_at=utc())
            if survey and section:
                record=report['sections'].setdefault(section,{})
                record['survey']=survey.record()
                if record.get('status')!='COMPLETE':record['status']=result.result_code
                tail_record=record.get('post_capture_navigation',{})
                if tail_record.get('status')=='MOVING':
                    tail_record.update(status=result.result_code,error=str(e),finished_at=utc(),
                                       elapsed_wall_s=time.monotonic()-tail_start)
            if g.is_cancel_requested:g.canceled()
            else:g.abort()
            self.get_logger().error(str(e))
        finally:
            cleanup_start=time.monotonic()
            if worker:worker.close()
            report['worker_cleanup_wall_s']=time.monotonic()-cleanup_start
            self.get_logger().info(f'추론 프로세스 정리: {report["worker_cleanup_wall_s"]:.3f}s')
            result.section_id=g.request.section_id;result.completed_segment_count=completed_segments
            result.harvest_tasks=list(stored_tasks)
            total_tasks=len(stored_tasks);total_fruits=sum(t.expected_count for t in stored_tasks)
            result.harvest_task_count=total_tasks;result.total_expected_count=total_fruits;result.timestamp=utc()
            report['finished_at']=utc();report['elapsed_wall_s']=time.monotonic()-started_wall;report['completed_section_ids']=completed
            report['harvest_task_count']=total_tasks;report['total_expected_count']=total_fruits
            report['section_id']=g.request.section_id;report['harvest_tasks']=[task_record(t) for t in stored_tasks]
            try:write_json(folder/'survey.json',report)
            finally:
                self.get_logger().info(f'결과 저장: {folder}/survey.json')
                self.active_goal=None
                with self.lock:self.busy=False
        return result


def main(args=None):
    rclpy.init(args=args,signal_handler_options=SignalHandlerOptions.NO)
    node=SurveyServer();executor=MultiThreadedExecutor(num_threads=4);executor.add_node(node)
    def stop(*_):node.shutdown_requested=True
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    try:
        while rclpy.ok() and (not node.shutdown_requested or node.busy):executor.spin_once(timeout_sec=.1)
    finally:
        executor.shutdown();node.destroy_node();rclpy.shutdown()
