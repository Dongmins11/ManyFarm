"""실제 PrecisionMotion을 요청하고 센서·피드백·결과를 보존한다. 제어값을 만들지 않는다."""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from farm_interfaces.action import PrecisionMotion, CheckRoute
from farm_interfaces.msg import RobotStatus
from transport_robot.configuration import load_profile, destination
from farm_navigation.route import RouteGraph
from transport_robot.mission_types import utc
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, LaserScan
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--marker', type=int, choices=[41,42], required=True)
    parser.add_argument('--handoff',action='store_true')
    parser.add_argument('--sorter-profile',type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = Node('docking_alignment_probe', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', value=True)])
    client = ActionClient(node, PrecisionMotion, '/transport_01/precision_motion')
    stream = (args.output/'events.jsonl').open('w')
    state = {}
    handle = None;route_handle=None;route_done=False
    result = {'scope':'actual Isaac + common PrecisionMotion; isolated final/approach stage', 'marker':args.marker}
    def log(kind: str, **fields) -> None:
        stream.write(json.dumps(dict(kind=kind,wall=time.time(),sim_ns=node.get_clock().now().nanoseconds,**fields),ensure_ascii=False)+'\n')
        stream.flush()
    def odom(m):
        state['odom']=m
        if time.monotonic()-state.get('odom_log',0)>.2:
            state['odom_log']=time.monotonic()
            log('odom',x=m.pose.pose.position.x,y=m.pose.pose.position.y,
                v=m.twist.twist.linear.x,w=m.twist.twist.angular.z)
    def scan(m):
        state['scan']=m
        if time.monotonic()-state.get('scan_log',0)>.2:
            state['scan_log']=time.monotonic()
            front=[(m.angle_min+i*m.angle_increment, r) for i,r in enumerate(m.ranges)
                   if abs(m.angle_min+i*m.angle_increment)<.15 and math.isfinite(r)]
            log('front_scan',stamp_ns=m.header.stamp.sec*10**9+m.header.stamp.nanosec,points=front)
    def image(m):
        if time.monotonic()-state.get('image_log',0)<1.:return
        state['image_log']=time.monotonic()
        rgb=np.frombuffer(m.data,dtype=np.uint8).reshape(m.height,m.step)[:,:m.width*3].reshape(m.height,m.width,3)
        name=f"image_{m.header.stamp.sec}_{m.header.stamp.nanosec}.jpg"
        bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR) if m.encoding=='rgb8' else rgb
        cv2.imwrite(str(args.output/name),bgr)
        log('image',path=name,encoding=m.encoding)
    def robot_status(m):
        state['robot_status']=m
        log('robot_status',state=m.state,task_id=m.current_task_id,error_code=m.error_code,
            xy=[m.pose.position.x,m.pose.position.y],yaw=m.pose.yaw,loaded_count=m.loaded_count)
    node.create_subscription(RobotStatus,'/transport_01/status',robot_status,10)
    node.create_subscription(Odometry,'/transport_01/odom',odom,qos_profile_sensor_data)
    node.create_subscription(LaserScan,'/transport_01/scan',scan,qos_profile_sensor_data)
    node.create_subscription(String,'/transport_01/precision/marker_observations',lambda m:log('marker',data=json.loads(m.data)),10)
    image_subscription=node.create_subscription(Image,'/transport_01/camera/image_raw',image,qos_profile_sensor_data)
    def tf_message(m):
        for transform in m.transforms:
            if transform.child_frame_id=='transport_01/base_footprint':
                stamp=transform.header.stamp.sec*10**9+transform.header.stamp.nanosec
                log('tf_receive',stamp_ns=stamp,age_s=(node.get_clock().now().nanoseconds-stamp)/1e9)
    node.create_subscription(TFMessage,'/tf',tf_message,100)
    def spin_until(predicate, timeout: float) -> None:
        deadline=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>deadline:raise TimeoutError('시험 대기시간 초과')
            rclpy.spin_once(node,timeout_sec=.05)
    try:
        spin_until(lambda:client.server_is_ready() and 'odom' in state and 'scan' in state,240.)
        until=time.monotonic()+3.
        spin_until(lambda:time.monotonic()>=until,5.)
        request=PrecisionMotion.Goal(session_id=f'sim_alignment_{args.marker}_{time.time_ns()}',
            profile_id='harvest_dock_41' if args.marker==41 else 'harvest_approach_42',
            operation='DOCK',target_marker_id=args.marker,docking_marker_id=args.marker)
        log('goal',profile=request.profile_id,session=request.session_id)
        print('GOAL '+request.profile_id,flush=True)
        future=client.send_goal_async(request,feedback_callback=lambda f:log('feedback',phase=f.feedback.phase))
        spin_until(future.done,15.);handle=future.result()
        if not handle.accepted:raise RuntimeError('PrecisionMotion Goal rejected')
        future=handle.get_result_async();spin_until(future.done,150.)
        response=future.result()
        result.update(status=response.status,success=response.result.success,stopped=response.result.stopped,error_message=response.result.error_message)
        log('result',**result);print('RESULT '+json.dumps(result,ensure_ascii=False),flush=True)
        if args.handoff or args.sorter_profile:
            if not (args.marker==41 and response.status==4 and response.result.success and response.result.stopped):
                raise RuntimeError('도킹 성공/정지 전 인계 금지')
            from probe_sim_handoff import run_handoff
            result['handoff']=run_handoff(log)
        if args.sorter_profile:
            node.destroy_subscription(image_subscription)
            root=Path(__file__).resolve().parents[2]
            profile=load_profile(root,str(args.sorter_profile),'sim')
            graph=RouteGraph(profile['route_graph'])
            xy,yaw=destination(profile,graph,'SORT_01')
            route_client=ActionClient(node,CheckRoute,'/transport_01/internal/check_route')
            spin_until(lambda:route_client.server_is_ready() and 'robot_status' in state and
                state['robot_status'].error_code=='NONE',60.)
            goal=CheckRoute.Goal(robot_id=profile['robot_id'],map_id=profile['map_id'],
                task_id='sorter_'+str(time.time_ns()),timestamp=utc())
            goal.goal_pose.frame_id='map';goal.goal_pose.position.x=float(xy[0]);goal.goal_pose.position.y=float(xy[1]);goal.goal_pose.yaw=yaw
            log('sorter_goal',task_id=goal.task_id,xy=xy,yaw=yaw)
            print('SORTER_GOAL '+json.dumps(dict(xy=xy,yaw=yaw)),flush=True)
            future=route_client.send_goal_async(goal,feedback_callback=lambda f:log('sorter_feedback',phase=f.feedback.phase))
            spin_until(future.done,15.);route_handle=future.result()
            if not route_handle.accepted:raise RuntimeError('선별장 이동 CheckRoute 거절')
            future=route_handle.get_result_async();spin_until(future.done,480.);response=future.result();route_done=True
            result['sorter']=dict(status=response.status,arrived=response.result.arrived,
                result_code=response.result.result_code,error_message=response.result.error_message,goal_xy=xy,goal_yaw=yaw)
            log('sorter_result',**result['sorter']);print('SORTER_RESULT '+json.dumps(result['sorter'],ensure_ascii=False),flush=True)
            if response.status!=4 or response.result.result_code!='SUCCESS' or not response.result.arrived:
                raise RuntimeError('선별장 이동 실패: '+response.result.error_message)
            result['overall_success']=True
        until=time.monotonic()+3.;spin_until(lambda:time.monotonic()>=until,5.)
    except Exception as exc:
        result['overall_success']=False
        result['probe_error']=str(exc);log('probe_error',error=str(exc));raise
    finally:
        if route_handle is not None and not route_done:
            future=route_handle.cancel_goal_async()
            try:spin_until(future.done,5.)
            except TimeoutError:pass
        if handle is not None and 'status' not in result:
            future=handle.cancel_goal_async()
            try:spin_until(future.done,5.)
            except TimeoutError:pass
        (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        stream.close();node.destroy_node();rclpy.try_shutdown()


if __name__=='__main__':main()
