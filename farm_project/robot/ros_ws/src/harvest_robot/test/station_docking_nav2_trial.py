"""PC 전용 실제 Nav2 플러그인 통합 시험. Domain 231에서만 실행하며 실물에 연결하지 않는다.

사용법: python3 station_docking_nav2_trial.py success|offset|collision|cancel|resume|wait_cancel
승인 설정과 가상 센서를 사용하며 실물 도킹 검증이 아니다.
"""
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import json

import numpy as np
import yaml
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from lifecycle_msgs.srv import ChangeState
from tf2_msgs.msg import TFMessage
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from farm_navigation.configuration import load_nav2_parameters
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.pose_provider import PoseProvider
from farm_navigation.motion_monitor import MotionMonitor
from farm_common.action_handoff import ActionInterrupted
from harvest_robot.station_docking import StationDocking, server_config
from test_station_docking import ROOT, CONFIG
from harvest_robot.station_docking import load_config


def main() -> None:
    if os.environ.get('ROS_DOMAIN_ID') != '231' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE') != 'LOCALHOST':
        raise RuntimeError('PC 격리 domain231/LOCALHOST 환경 필요')
    case = sys.argv[1]
    if case not in ('success', 'offset', 'collision', 'cancel', 'resume', 'wait_cancel'):
        raise ValueError('시험 이름 오류')
    config = load_config(ROOT, str(CONFIG))
    values = server_config(load_nav2_parameters(ROOT/'robot/config/robots/vicpinky/nav2.yaml',ROOT),'harvest_01',config)
    folder=Path('/tmp/station_docking_trial')/case;folder.mkdir(parents=True,exist_ok=True)
    params=folder/'server.yaml';params.write_text(yaml.safe_dump(values))
    pose=[.09,-.04,math.radians(10)] if case=='offset' else [.09,.02,0.];command=[0.,0.];begin=[None];samples=[]
    refs=config['reference']['walls']
    normals=np.array([[math.cos(r['normal_angle_rad']),math.sin(r['normal_angle_rad'])] for r in refs.values()])
    distances=np.array([r['distance_m'] for r in refs.values()])
    angles=np.linspace(-math.pi,math.pi,721)
    rclpy.init();node=Node('station_docking_trial',namespace='harvest_01',cli_args=[
        '--ros-args','-r','/tf:=/harvest_01/tf','-r','/tf_static:=/harvest_01/tf_static'])
    group=ReentrantCallbackGroup()
    tf=node.create_publisher(TFMessage,'tf',10);odom=node.create_publisher(Odometry,'odom',10)
    scan=node.create_publisher(LaserScan,'scan_filtered',10)
    def receive(msg: Twist) -> None:
        command[:]=[msg.linear.x,msg.angular.z]
    node.create_subscription(Twist,'cmd_vel_normal',receive,10,callback_group=group)
    def publish() -> None:
        v,w=command
        pose[0]+=v*math.cos(pose[2])*.05;pose[1]+=v*math.sin(pose[2])*.05;pose[2]+=w*.05
        stamp=node.get_clock().now().to_msg()
        t=TransformStamped();t.header.stamp=stamp;t.header.frame_id='odom';t.child_frame_id='base_footprint'
        t.transform.translation.x=pose[0];t.transform.translation.y=pose[1]
        t.transform.rotation.z=math.sin(pose[2]/2);t.transform.rotation.w=math.cos(pose[2]/2)
        b=TransformStamped();b.header.stamp=stamp;b.header.frame_id='base_footprint';b.child_frame_id='base_link'
        b.transform.rotation.w=1.;tf.publish(TFMessage(transforms=[t,b]))
        o=Odometry();o.header.stamp=stamp;o.header.frame_id='odom';o.child_frame_id='base_footprint'
        o.pose.pose.position.x=pose[0];o.pose.pose.position.y=pose[1];o.pose.pose.orientation=t.transform.rotation
        o.twist.twist.linear.x=v;o.twist.twist.angular.z=w;odom.publish(o)
        rays=np.column_stack((np.cos(angles+pose[2]),np.sin(angles+pose[2])))
        denominator=normals@rays.T
        with np.errstate(divide='ignore',invalid='ignore'):
            ranges=(distances-normals@np.array(pose[:2]))[:,None]/denominator
        ranges=np.where(ranges>.05,ranges,np.inf).min(axis=0)
        if case=='collision':
            # 뒤쪽 36cm 장애물: 벽의 다수 직선점은 유지하면서 예측 footprint를 막는다.
            ranges[:3]=.36;ranges[-3:]=.36
        msg=LaserScan();msg.header.stamp=stamp;msg.header.frame_id='base_footprint'
        msg.angle_min=-math.pi;msg.angle_max=math.pi;msg.angle_increment=float(angles[1]-angles[0])
        msg.range_min=.05;msg.range_max=8.;msg.ranges=ranges.astype(float).tolist();
        elapsed = time.monotonic()-begin[0] if begin[0] is not None else 0.
        # 진행 제한10초보다 긴 관측 단절 후 같은 Goal의 재개/대기 중 취소를 확인한다.
        if not (case in ('resume', 'wait_cancel') and 3 < elapsed < 18):
            scan.publish(msg)
        if begin[0] is not None:samples.append([time.monotonic()-begin[0],*pose,*command])
    node.create_timer(.05,publish,callback_group=group)
    executor=MultiThreadedExecutor(num_threads=4);executor.add_node(node)
    thread=threading.Thread(target=executor.spin);thread.start()
    proc=None;component=None;motion=None;poses=None
    log=open(folder/'server.log','w')
    try:
        proc=subprocess.Popen(['/opt/ros/jazzy/lib/nav2_controller/controller_server','--ros-args',
            '-r','__ns:=/harvest_01/station_docking','--params-file',str(params),
            '-r','/tf:=/harvest_01/tf','-r','/tf_static:=/harvest_01/tf_static','-r','cmd_vel:=raw_nav'],
            stdout=log,stderr=subprocess.STDOUT)
        client=node.create_client(ChangeState,'/harvest_01/station_docking/controller_server/change_state',callback_group=group)
        assert client.wait_for_service(timeout_sec=15)
        for state in (1,3):
            req=ChangeState.Request();req.transition.id=state;future=client.call_async(req);deadline=time.monotonic()+25
            while not future.done() and time.monotonic()<deadline:time.sleep(.05)
            assert future.done() and future.result().success
        settings=NavigationSettings(mode='follow_path',map_frame='odom',goal_timeout_s=20. if case=='resume' else 60.,readiness_timeout_s=10.)
        poses=PoseProvider(node,settings);motion=MotionMonitor(node,settings,group)
        def check() -> None:
            if begin[0] is not None and ((case=='cancel' and time.monotonic()-begin[0]>3)
                    or (case=='wait_cancel' and time.monotonic()-begin[0]>15)):
                raise ActionInterrupted('시험 취소')
        component=StationDocking(node,config=config,settings=settings,robot_id='harvest_01',poses=poses,
            motion=motion,callbacks=group,check=check,owns_output=lambda:True)
        begin[0]=time.monotonic();error=None
        try:component.execute()
        except Exception as e:error=e
        finally:
            print('DIAGNOSTIC',pose,component._error,component._latest,flush=True)
            np.save(folder/'trace.npy',samples)
            component.cleanup()
        if case in ('success','offset','resume'):assert error is None,str(error)
        if case in ('resume','wait_cancel'):
            waiting = np.array([s for s in samples if 4 < s[0] < 17])
            assert len(waiting)>100
            assert np.max(np.abs(waiting[:,-2:])) < 1e-9
        if case=='resume':
            assert time.monotonic()-begin[0] > settings.goal_timeout_s
            assert any(s[0]>18 and max(abs(v) for v in s[-2:])>0 for s in samples)
        elif case in ('cancel','wait_cancel'):assert isinstance(error,ActionInterrupted),str(error)
        elif case=='collision':
            assert error is not None
            assert 'collision' in (folder/'server.log').read_text().lower(),str(error)
        time.sleep(.3)
        assert max(abs(v) for v in command)<1e-9
        result=dict(case=case,error=str(error) if error else None,final_pose=pose,final_command=command,
                    seconds=time.monotonic()-begin[0],samples=len(samples))
        (folder/'result.json').write_text(json.dumps(result,indent=2));np.save(folder/'trace.npy',samples)
        print('PASS',json.dumps(result),flush=True)
    finally:
        if component:component.close()
        if motion:motion.close()
        if poses:poses.close()
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close();executor.shutdown();thread.join();node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
