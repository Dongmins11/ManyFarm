"""공통 벽 관측 ROS 어댑터. 속도/Goal을 발행하지 않는다. 연결값은 인자로 받는다."""
from __future__ import annotations
import argparse
import json
import math
import queue
import threading
import time
from dataclasses import replace
import rclpy
from rclpy.signals import SignalHandlerOptions
from .wall_shutdown import drain_then_close, start_spin
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import LaserScan
from .navigation_types import NavigationSettings
from .pose_provider import PoseProvider
from .wall_observation import WallTracker


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--namespace',required=True)
    parser.add_argument('--scan',required=True)
    parser.add_argument('--fixed-frame',default='odom')
    parser.add_argument('--base-frame',default='base_footprint')
    parser.add_argument('--timing-output')
    parser.add_argument('--use-sim-time',action='store_true')
    args,rosargs=parser.parse_known_args()
    config=json.load(open(args.config))
    rclpy.init(args=rosargs,signal_handler_options=SignalHandlerOptions.NO)
    from rclpy.parameter import Parameter
    node=rclpy.create_node('wall_observer',namespace=args.namespace,
                          parameter_overrides=[Parameter('use_sim_time',value=args.use_sim_time)])
    provider=PoseProvider(node,replace(NavigationSettings(),tf_timeout_s=.05))
    tracker=WallTracker(config['observation'])
    publisher=node.create_publisher(PoseStamped,'wall_observation',1)
    pending=queue.Queue(maxsize=1)
    timing=open(args.timing_output,'w') if args.timing_output else None
    def receive(msg: LaserScan) -> None:
        item=(msg,time.monotonic(),node.get_clock().now().nanoseconds)
        try:pending.put_nowait(item)
        except queue.Full:
            try:pending.get_nowait()
            except queue.Empty:pass
            try:pending.put_nowait(item)
            except queue.Full:pass
    subscription=node.create_subscription(LaserScan,args.scan,receive,QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=1,reliability=ReliabilityPolicy.BEST_EFFORT))
    executor=SingleThreadedExecutor();executor.add_node(node)
    worker=start_spin(executor)
    failed=False
    def check() -> None:
        if not rclpy.ok():raise RuntimeError('ROS 종료')
    try:
        while rclpy.ok():
            worker.check()
            try:scan,received_mono,received_ns=pending.get(timeout=.1)
            except queue.Empty:continue
            trace={'stamp_ns':scan.header.stamp.sec*10**9+scan.header.stamp.nanosec,
                   'receive_ns':received_ns,'queue_s':time.monotonic()-received_mono}
            trace['arrival_age_s']=(received_ns-trace['stamp_ns'])*1e-9
            out=PoseStamped();out.header.frame_id=args.fixed_frame;out.header.stamp=scan.header.stamp
            if failed:
                out.pose.position.x=float('nan');publisher.publish(out);continue
            try:
                stamp=scan.header.stamp.sec*10**9+scan.header.stamp.nanosec
                age=(node.get_clock().now().nanoseconds-stamp)*1e-9
                if not 0<=age<=config['controller']['observation_age']:raise ValueError('라이다 시각 만료')
                tf_start=time.monotonic()
                record={'stamp_ns':stamp,'scan':{k:getattr(scan,k) for k in
                    ('ranges','angle_min','angle_increment','range_min','range_max')},
                    'base_from_scan':provider.lookup(args.base_frame,scan.header.frame_id,stamp,check),
                    'odom_from_base':provider.lookup(args.fixed_frame,args.base_frame,stamp,check)}
                trace['tf_s']=time.monotonic()-tf_start
                fit_start=time.monotonic()
                observed=tracker.observe(record)
                trace['fit_s']=time.monotonic()-fit_start
                if not observed['ready']:continue
                out.pose.position.x=observed['x'];out.pose.position.y=observed['y']
                out.pose.orientation.z=math.sin(observed['yaw']/2);out.pose.orientation.w=math.cos(observed['yaw']/2)
                trace['publish_ns']=node.get_clock().now().nanoseconds
                trace['publish_age_s']=(trace['publish_ns']-stamp)*1e-9
                publisher.publish(out)
            except (RuntimeError,ValueError) as error:
                # 시작 TF 버퍼 준비 중에는 미발행. 추적 시작 뒤 오류는 재선택 없이 유지한다.
                if tracker.count:
                    failed=True;out.pose.position.x=float('nan');publisher.publish(out)
                trace['error']=str(error)
                node.get_logger().error(str(error))
            finally:
                if timing:timing.write(json.dumps(trace)+'\n')
    except KeyboardInterrupt:
        pass
    finally:
        try:
            drain_then_close(executor,worker,[provider.close,
                lambda:node.destroy_subscription(subscription),node.destroy_node,rclpy.try_shutdown])
        finally:
            if timing:timing.close()

if __name__=='__main__':main()
