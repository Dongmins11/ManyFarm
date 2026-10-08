#!/usr/bin/env python3
"""MJPEG -> calibrated ROS2 Image + CameraInfo, for the existing AprilTag pipeline.
No detection, rectification, TF or motor commands here. No cv_bridge required.
Stop usb_cam and other camera programs before running this node.
Timestamps are assigned after frame acquisition (not hardware exposure time).
"""
import argparse
from array import array
import json
import math
from pathlib import Path
import time


def load_calibration(path):
    c=json.loads(Path(path).read_text())
    w,h=c['width'],c['height']
    if type(w) is not int or type(h) is not int or min(w,h)<=0:
        raise ValueError('Calibration requires positive integer width/height')
    mat=c['camera_matrix']
    if len(mat)!=3 or any(len(row)!=3 for row in mat):
        raise ValueError('camera_matrix must be 3x3')
    k=[float(x) for row in mat for x in row]
    d=[float(x) for x in c['distortion_coefficients']]
    if len(d)!=5 or not all(math.isfinite(x) for x in k+d):
        raise ValueError('Expected five finite plumb_bob coefficients')
    if k[0]<=0 or k[4]<=0 or any(abs(a-b)>1e-9 for a,b in zip(k[6:],[0,0,1])):
        raise ValueError('Invalid camera intrinsic matrix')
    r=[1.,0.,0.,0.,1.,0.,0.,0.,1.]
    p=[k[0],k[1],k[2],0.,k[3],k[4],k[5],0.,k[6],k[7],k[8],0.]
    return w,h,k,d,r,p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration',type=Path,required=True,help='calibrate_pcweb400.py report.json')
    parser.add_argument('--device',default='/dev/video0')
    parser.add_argument('--fps',type=float,default=30.)
    parser.add_argument('--frame-id',default='apriltag_camera_optical_frame')
    parser.add_argument('--reliability',choices=['reliable','best_effort'],default='reliable')
    parser.add_argument("--trial-label",choices=["auto","manual_2ms"],required=True)
    parser.add_argument("--trial-output",type=Path,required=True)
    args,ros_args=parser.parse_known_args()
    if not math.isfinite(args.fps) or args.fps<=0:parser.error('fps must be positive and finite')
    w,h,k,d,r,p=load_calibration(args.calibration)
    import cv2
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
    from sensor_msgs.msg import Image, CameraInfo
    from rclpy.utilities import get_rmw_implementation_identifier
    from trial_io import TrialIO
    cap=None;node=None;initialized=False;trial=None
    try:
        rclpy.init(args=ros_args);initialized=True
        node=Node('opencv_camera',namespace='/apriltag_camera')
        qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=2,
            reliability=ReliabilityPolicy.RELIABLE if args.reliability=='reliable' else ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE)
        images=node.create_publisher(Image,'image_raw',qos)
        infos=node.create_publisher(CameraInfo,'camera_info',qos)
        info=CameraInfo()
        info.width=w;info.height=h;info.distortion_model='plumb_bob'
        info.k=k;info.d=d;info.r=r;info.p=p
        info.header.frame_id=args.frame_id
        trial=TrialIO(args.trial_output,args.device,args.trial_label)
        cap=cv2.VideoCapture(args.device,cv2.CAP_V4L2)
        if not cap.isOpened():raise RuntimeError('Camera missing/busy: stop usb_cam / OpenCV windows first')
        for prop,value in [(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*'MJPG')),
                           (cv2.CAP_PROP_FRAME_WIDTH,w),(cv2.CAP_PROP_FRAME_HEIGHT,h),
                           (cv2.CAP_PROP_FPS,args.fps)]:
            cap.set(prop,value)
        code=int(cap.get(cv2.CAP_PROP_FOURCC))
        fmt=''.join(chr((code>>(8*i))&255) for i in range(4))
        if fmt!='MJPG':raise RuntimeError('Camera did not accept MJPG: '+fmt)
        node.get_logger().info(f'{w}x{h} {fmt}, requested {args.fps}FPS, reported {cap.get(cv2.CAP_PROP_FPS)}FPS')
        node.get_logger().info('Calibration: '+str(args.calibration.resolve()))
        node.get_logger().info('RMW: '+get_rmw_implementation_identifier()+', QoS: '+args.reliability)
        node.get_logger().info('Publishing '+images.topic_name+' and '+infos.topic_name+' with matching stamps')
        count=0;last=time.monotonic();read_total=publish_total=0.
        read_count=0;next_publish_ns=0
        node.get_logger().info('TRIAL: ROS publication cap 10 Hz; local lossless frames recorded during requested pass')
        ok,_=cap.read()
        if not ok:raise RuntimeError('Camera stream did not start')
        trial.apply_after_camera_open()
        warmup_until=time.monotonic()+2.
        while rclpy.ok():
            tick=time.monotonic()
            ok,frame=cap.read()
            got=time.monotonic();read_total+=got-tick
            read_count+=1
            if not ok:raise RuntimeError('Camera frame read failed; no old frame will be republished')
            if frame.shape!=(h,w,3) or str(frame.dtype)!='uint8':
                raise RuntimeError('Frame size/type differs from calibration; refusing mismatched CameraInfo')
            trial.before_publish()
            if time.monotonic()<warmup_until:
                continue
            now_ns=time.monotonic_ns()
            if now_ns < next_publish_ns:
                rclpy.spin_once(node,timeout_sec=0.)
                continue
            next_publish_ns=now_ns+100_000_000
            stamp=node.get_clock().now().to_msg()
            msg=Image()
            msg.header.stamp=stamp;msg.header.frame_id=args.frame_id
            msg.height=h;msg.width=w;msg.encoding='bgr8';msg.is_bigendian=0;msg.step=w*3
            msg.data=array('B',frame.tobytes(order='C'))
            info.header.stamp=stamp
            before=time.monotonic()
            images.publish(msg);infos.publish(info)
            trial.record_published(frame,int(stamp.sec)*1_000_000_000+int(stamp.nanosec),args.frame_id)
            publish_total+=time.monotonic()-before
            count+=1
            rclpy.spin_once(node,timeout_sec=0.)
            elapsed=time.monotonic()-last
            if elapsed>=5:
                node.get_logger().info(
                    f'Capture {read_count/elapsed:.1f}Hz | ROS publish {count/elapsed:.1f}Hz | avg read {read_total/read_count*1000:.1f}ms '
                    f'| avg publish {publish_total/count*1000:.1f}ms | image subscribers {images.get_subscription_count()} '
                    '(local rate is not receiver rate)')
                count=0;read_count=0;read_total=publish_total=0.;last=time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        if cap is not None:cap.release()
        try:
            if trial is not None:trial.close()
        finally:
            if node is not None:node.destroy_node()
            if initialized and rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
