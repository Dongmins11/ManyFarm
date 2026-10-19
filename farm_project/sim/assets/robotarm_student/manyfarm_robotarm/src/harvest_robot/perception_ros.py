"""Read-only dual-camera ROS adapter. No robot action publishers.

Input RGB and aligned optical-Z depth MUST both be rectified to CameraInfo.P.
TF supplies arm <- optical at acquisition time, including measured wrist joints.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np
from harvest_vision.geometry import Frame
from harvest_vision.client import Detector
from harvest_vision.pipeline import process
from harvest_vision.tracking import TrackManager

def main():
    p=argparse.ArgumentParser()
    for camera in ('right','rear'):
        for stream in ('rgb','depth','info'):p.add_argument(f'--{camera}-{stream}',required=True)
    p.add_argument('--track-provisional',action='store_true',help='Diagnostic IDs only for uncalibrated centres; never motion permission')
    p.add_argument('--rectified-inputs',action='store_true',required=True)
    p.add_argument('--arm-frame',default='arm_2/base_link')
    p.add_argument('--model',required=True);p.add_argument('--vision-python',required=True)
    p.add_argument('--centre-offset-m',type=float);p.add_argument('--calibration-verified',action='store_true')
    args,ros_args=p.parse_known_args()
    import rclpy
    from rclpy.node import Node
    from rclpy.duration import Duration
    from rclpy.time import Time
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image,CameraInfo
    from std_msgs.msg import String
    from cv_bridge import CvBridge
    from tf2_ros import Buffer,TransformListener
    import message_filters
    from scipy.spatial.transform import Rotation
    rclpy.init(args=ros_args)
    node=Node('harvest_perception_check');bridge=CvBridge()
    buffer=Buffer();listener=TransformListener(buffer,node)
    detector=Detector(args.vision_python,args.model)
    pub=node.create_publisher(String,'harvest/perception_debug',10)
    subscriptions=[];synchronizers=[]
    tracker=TrackManager(frame_id=args.arm_frame,clock_id='ros',allow_provisional=args.track_provisional)
    def callback(name,rgb,depth,info):
        try:
            stamp=rgb.header.stamp.sec+rgb.header.stamp.nanosec*1e-9
            ds=depth.header.stamp.sec+depth.header.stamp.nanosec*1e-9
            now=node.get_clock().now().nanoseconds*1e-9
            if abs(ds-stamp)>.05:raise ValueError('RGB/depth not synchronised')
            if rgb.header.frame_id!=info.header.frame_id or depth.header.frame_id!=rgb.header.frame_id:raise ValueError('Aligned RGB/depth/CameraInfo require same optical frame')
            transform=buffer.lookup_transform(args.arm_frame,rgb.header.frame_id,Time.from_msg(rgb.header.stamp),timeout=Duration(seconds=0))
            v=transform.transform;t=np.eye(4)
            t[:3,:3]=Rotation.from_quat([v.rotation.x,v.rotation.y,v.rotation.z,v.rotation.w]).as_matrix()
            t[:3,3]=[v.translation.x,v.translation.y,v.translation.z]
            z=bridge.imgmsg_to_cv2(depth,desired_encoding='passthrough')
            if depth.encoding=='16UC1':z=z.astype(np.float32)*.001
            elif depth.encoding=='32FC1':z=z.astype(np.float32)
            else:raise ValueError('Require ROS depth 16UC1 millimetres or 32FC1 metres')
            frame=Frame(bridge.imgmsg_to_cv2(rgb,desired_encoding='rgb8'),z,np.array(info.p).reshape(3,4)[:,:3],t,
                stamp,stamp,name,frame_id=args.arm_frame,clock_id='ros',calibration_verified=args.calibration_verified)
            records,_=process(frame,detector,now,args.centre_offset_m)
            # Include inference latency; stale outputs are never represented as fresh.
            age=node.get_clock().now().nanoseconds*1e-9-stamp
            for r in records:
                r['age_s']=age
                if not 0<=age<=.3:r.update(valid=False,candidate_valid=False,control_valid=False,reason='stale_after_inference')
            tracks=tracker.update(records,node.get_clock().now().nanoseconds*1e-9)
            message=String();message.data=json.dumps(dict(camera_id=name,stamp_s=stamp,detections=records,tracks=tracks,diagnostic_only=True));pub.publish(message)
        except Exception as exc:
            node.get_logger().warning(f'{name}: {exc}')
            msg=String();msg.data=json.dumps(dict(camera_id=name,valid=False,reason=str(exc)));pub.publish(msg)
    for camera in ('right','rear'):
        subs=[message_filters.Subscriber(node,kind,getattr(args,f'{camera}_{stream}'),qos_profile=qos_profile_sensor_data)
              for stream,kind in [('rgb',Image),('depth',Image),('info',CameraInfo)]]
        sync=message_filters.ApproximateTimeSynchronizer(subs,queue_size=3,slop=.05)
        sync.registerCallback(lambda rgb,depth,info,name=camera:callback(name,rgb,depth,info))
        subscriptions.extend(subs);synchronizers.append(sync)
    try:rclpy.spin(node)
    finally:detector.close();node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
