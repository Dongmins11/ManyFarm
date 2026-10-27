#!/usr/bin/env python3
"""실제 운송 가상 장치의 ROS 센서/구동 시험. 별도 Isaac 실행 필요; 대역 없음."""
import argparse
import json
import math
import time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Image, CameraInfo, JointState
from tf2_msgs.msg import TFMessage
from rosgraph_msgs.msg import Clock


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rclpy.init()
    node = Node('transport_hardware_smoke')
    data, counts, transforms, images, infos = {}, {}, {}, {}, {}
    result = dict(kind='actual_isaac_ros_hardware', checks={}, phases={})
    pub = node.create_publisher(Twist, '/transport_01/cmd_vel', 10)
    def receive(key, msg):
        data[key] = msg
        counts[key] = counts.get(key, 0)+1
    for typ, key, topic, qos in [
        (Odometry,'odom','/transport_01/odom',10),
        (LaserScan,'scan','/transport_01/scan',qos_profile_sensor_data),
        (JointState,'joints','/transport_01/joint_states',10),
        (Clock,'clock','/clock',10)]:
        node.create_subscription(typ,topic,lambda m,k=key:receive(k,m),qos)
    def tf(msg):
        for t in msg.transforms:transforms[(t.header.frame_id,t.child_frame_id)]=t
    node.create_subscription(TFMessage,'/tf_static',tf,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    node.create_subscription(TFMessage,'/tf',tf,10)
    def spin(seconds, linear=None, angular=0.):
        end=time.monotonic()+seconds
        next_command=0.
        while time.monotonic()<end:
            if linear is not None and time.monotonic()>=next_command:
                msg=Twist();msg.linear.x=linear;msg.angular.z=angular;pub.publish(msg)
                next_command=time.monotonic()+.05
            rclpy.spin_once(node,timeout_sec=.05)
    def pose():
        m=data['odom'];q=m.pose.pose.orientation
        return [m.pose.pose.position.x,m.pose.pose.position.y,2*math.atan2(q.z,q.w)]
    try:
        deadline=time.monotonic()+360
        while not all(k in data for k in ('odom','scan','joints','clock')):
            if time.monotonic()>deadline:raise TimeoutError('센서 준비 360초 초과')
            rclpy.spin_once(node,timeout_sec=.1)
        spin(3.,0.)
        result['phases']['initial']=pose()
        print('READY '+json.dumps(counts),flush=True)
        spin(4.,.05)
        result['phases']['forward']=pose()
        # 정지 명령을 보내지 않아 cmd_vel watchdog의 자동 정지를 확인한다.
        spin(3.)
        m=data['odom'];result['checks']['watchdog_stop']=abs(m.twist.twist.linear.x)<.01 and abs(m.twist.twist.angular.z)<.03
        result['phases']['watchdog']=pose()
        spin(3.,0.,.2)
        result['phases']['turn']=pose()
        spin(2.,0.)
        def image(msg):
            stamp=(msg.header.stamp.sec,msg.header.stamp.nanosec)
            # 영상은 저장하지 않고 형식·밝기 범위·동일 시각 보정 정보만 검사한다.
            images[stamp]=dict(frame=msg.header.frame_id,size=[msg.width,msg.height],encoding=msg.encoding,
                               low=min(msg.data),high=max(msg.data))
        def info(msg):
            infos[(msg.header.stamp.sec,msg.header.stamp.nanosec)]=dict(frame=msg.header.frame_id,k=list(msg.k))
        sub=node.create_subscription(Image,'/transport_01/camera/image_raw',image,qos_profile_sensor_data)
        info_sub=node.create_subscription(CameraInfo,'/transport_01/camera/camera_info',info,qos_profile_sensor_data)
        spin(12.,0.)
        node.destroy_subscription(sub);node.destroy_subscription(info_sub)
        spin(3.,0.)
        # 다시 켤 때 새 촬영 시각의 프레임이 나오는지도 확인한다.
        old=max(images,default=(-1,-1))
        sub=node.create_subscription(Image,'/transport_01/camera/image_raw',image,qos_profile_sensor_data)
        spin(6.,0.)
        node.destroy_subscription(sub)
        spin(3.,0.)
        a,b,c,d=[result['phases'][k] for k in ('initial','forward','watchdog','turn')]
        result['checks'].update(
            forward_odom=b[0]-a[0]>.02 and abs(b[1]-a[1])<.03,
            positive_yaw=d[2]-c[2]>.04,
            lidar=len(data['scan'].ranges)==360 and any(math.isfinite(v) and v>0 for v in data['scan'].ranges),
            wheel_names=data['joints'].name==['wheel_left_joint','wheel_right_joint'],
            tf=all(('transport_01/'+x,'transport_01/'+y) in transforms for x,y in
                   [('odom','base_footprint'),('base_footprint','base_link'),('base_link','base_scan'),('base_link','camera_optical_frame')]),
            image_info_sync=any(k in infos and v['frame']==infos[k]['frame'] and v['high']>v['low']
                                and v['size']==[1280,720] and v['encoding']=='rgb8' for k,v in images.items()),
            camera_restart=max(images,default=(-1,-1))>old)
        result.update(counts=counts,image_count=len(images),info_count=len(infos),
                      image_sample=next(iter(images.values()),None),tf_pairs=list(transforms))
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        if not all(result['checks'].values()):raise AssertionError('하드웨어 검사 실패')
    except Exception as error:
        result['error']=str(error)
        raise
    finally:
        pub.publish(Twist())
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
