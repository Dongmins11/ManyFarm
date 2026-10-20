#!/usr/bin/env python3
"""기존 설치 공통 TF·정지 판정기를 사용하는 읽기 전용 수집. 속도/Goal 발행 없음."""
from __future__ import annotations
from dataclasses import replace
import argparse
import json
import math
from pathlib import Path
import queue
import threading
import time


def main() -> None:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan
    from geometry_msgs.msg import PolygonStamped
    from nav_msgs.msg import Odometry
    from farm_navigation.navigation_types import NavigationSettings
    from farm_navigation.pose_provider import PoseProvider
    from farm_navigation.motion_monitor import MotionMonitor

    parser = argparse.ArgumentParser(description='정지 상태 라이다 수집. 실제 이동 없음')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scan-topic', required=True)
    parser.add_argument('--odom-topic', required=True)
    parser.add_argument('--footprint-topic', required=True)
    parser.add_argument('--tf-topic', default='/harvest_01/tf')
    parser.add_argument('--tf-static-topic', default='/harvest_01/tf_static')
    parser.add_argument('--base-frame', default='base_footprint')
    parser.add_argument('--odom-frame', default='odom')
    parser.add_argument('--map-frame', default='map')
    parser.add_argument('--seconds', type=float, default=8.)
    parser.add_argument('--use-sim-time', action='store_true')
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 60:
        parser.error('기록 시간은 1~60초')
    args.output.mkdir(parents=True, exist_ok=False)
    rclpy.init(args=['--ros-args','-p',f'use_sim_time:={str(args.use_sim_time).lower()}',
                      '-r', '/tf:='+args.tf_topic, '-r', '/tf_static:='+args.tf_static_topic])
    node = Node('wall_reference_capture')
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    settings = NavigationSettings(base_frame=args.base_frame, map_frame=args.map_frame,
                                  odom_topic=args.odom_topic)
    poses = PoseProvider(node, settings)
    # 선택 입력의 부재가 필수 센서 수집을 수 초간 막지 않게 한다.
    optional_poses = PoseProvider(node, replace(settings, tf_timeout_s=.02))
    monitor = MotionMonitor(node, settings, ReentrantCallbackGroup())
    scans: queue.Queue = queue.Queue(maxsize=1)
    observed = {}
    def receive_scan(message: LaserScan) -> None:
        if scans.full():
            try: scans.get_nowait()
            except queue.Empty: pass
        try: scans.put_nowait(message)
        except queue.Full: pass
    def receive_odom(message: Odometry) -> None:
        observed['odom'] = message
    def receive_footprint(message: PolygonStamped) -> None:
        observed['footprint'] = message
    subscriptions = [node.create_subscription(LaserScan,args.scan_topic,receive_scan,qos_profile_sensor_data),
                     node.create_subscription(Odometry,args.odom_topic,receive_odom,10),
                     node.create_subscription(PolygonStamped,args.footprint_topic,receive_footprint,10)]
    report = {'schema_version':2, 'ok':False, 'arguments':vars(args).copy(),
              'frames':0, 'errors':[], 'motion_requested':False,
              'optional_missing_frames':{'map':0,'footprint':0},
              'reference_pose_confirmed':False,
              'navigation_settings':settings.__dict__,
              'common_modules':{'pose':__import__('inspect').getfile(PoseProvider),
                                'motion':__import__('inspect').getfile(MotionMonitor)}}
    report['arguments']['output'] = str(args.output)
    def check() -> None:
        if not rclpy.ok(): raise RuntimeError('ROS 종료')
    def fresh(stamp: object) -> int:
        ns = stamp.sec*10**9+stamp.nanosec
        age = (node.get_clock().now().nanoseconds-ns)/1e9
        if ns <= 0 or not 0 <= age <= .5:
            raise RuntimeError('센서 시각 만료 또는 미래 시각')
        return ns
    previous = -1
    try:
        print('정지 확인 중 — 초기 위치·Nav2 활성화는 요구하지 않습니다.', flush=True)
        monitor.wait_stopped(check)
        print('라이다 기록 시작 — map/footprint 미수신은 별도로 표시합니다.', flush=True)
        deadline = time.monotonic()+args.seconds
        with (args.output/'scans.jsonl').open('x') as output:
            while time.monotonic()<deadline:
                check()
                if not monitor.stationary_now(): raise RuntimeError('정지/odom 최신성 확인 실패')
                try: scan=scans.get(timeout=.5)
                except queue.Empty: raise RuntimeError('라이다 수신 중단')
                stamp=fresh(scan.header.stamp)
                if stamp <= previous: raise RuntimeError('라이다 시각 중복/역행')
                previous=stamp
                transform=poses.lookup(args.base_frame,scan.header.frame_id,stamp,check)
                odom_pose=poses.lookup(args.odom_frame,args.base_frame,stamp,check)
                record={'stamp_ns':stamp,'scan_frame':scan.header.frame_id,'base_frame':args.base_frame,
                        'base_from_scan':transform.tolist(),'odom_from_base':odom_pose.tolist(),
                        'scan':{name:getattr(scan,name) for name in
                                ('angle_min','angle_max','angle_increment','time_increment','scan_time','range_min','range_max')}}
                record['scan']['ranges']=[float(x) if math.isfinite(x) else None for x in scan.ranges]
                try: record['map_from_base']=optional_poses.lookup(args.map_frame,args.base_frame,stamp,check).tolist()
                except RuntimeError as error:
                    record['map_tf_error']=str(error)
                    report['optional_missing_frames']['map']+=1
                odom=observed.get('odom')
                if odom is None: raise RuntimeError('odom 원본 없음')
                record['odom_stamp_ns']=fresh(odom.header.stamp)
                record['twist']=[odom.twist.twist.linear.x,odom.twist.twist.linear.y,odom.twist.twist.angular.z]
                footprint=observed.get('footprint')
                try:
                    if footprint is None: raise RuntimeError('footprint 미수신')
                    footprint_stamp=fresh(footprint.header.stamp)
                    vertices=[[p.x,p.y,p.z] for p in footprint.polygon.points]
                    if len(vertices)<3 or not all(math.isfinite(x) for p in vertices for x in p):
                        raise RuntimeError('footprint 형상 오류')
                    footprint_tf=optional_poses.lookup(args.base_frame,footprint.header.frame_id,
                                                      footprint_stamp,check).tolist()
                    record.update(footprint_stamp_ns=footprint_stamp,
                                  footprint_frame=footprint.header.frame_id,
                                  footprint_points=vertices,base_from_footprint=footprint_tf)
                except RuntimeError as error:
                    record['footprint_error']=str(error)
                    report['optional_missing_frames']['footprint']+=1
                if not monitor.stationary_now(): raise RuntimeError('수집 중 정지 확인 실패')
                output.write(json.dumps(record,allow_nan=False)+'\n')
                output.flush()
                report['frames']+=1
        if report['frames']<10: raise RuntimeError('유효 프레임 10개 미만')
        report['ok']=True
    except (Exception, KeyboardInterrupt) as error:
        report['errors'].append(str(error) or '사용자 중단')
    finally:
        (args.output/'capture_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        monitor.close();poses.close();optional_poses.close()
        executor.shutdown(timeout_sec=2.)
        node.destroy_node();rclpy.shutdown();thread.join(timeout=2.)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['ok']: raise SystemExit(1)


if __name__=='__main__':
    main()
