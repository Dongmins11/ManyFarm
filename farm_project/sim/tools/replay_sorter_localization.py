"""저장된 센서/바퀴 odom을 원본 AMCL에 재생하는 격리 진단. 제어 노드를 실행하지 않는다."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import yaml


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trial',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--rate',type=float,default=4.)
    parser.add_argument('--amcl-overrides',type=Path,help='격리 진단 전용. 운영 설정은 수정하지 않는다.')
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    if not math.isfinite(args.rate) or args.rate<=0:raise ValueError('양의 재생 속도 필요')
    if os.environ.get('ROS_DOMAIN_ID')!='13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE')!='SUBNET':
        raise ValueError('Domain13/SUBNET 필요')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    trial=args.trial.resolve();records=[json.loads(l) for l in (trial/'localization.jsonl').read_text().splitlines()]
    params=json.loads((trial/'runtime/nav2_transport.json').read_text())['amcl']['ros__parameters']
    if args.amcl_overrides:params.update(json.loads(args.amcl_overrides.read_text()))
    profile=json.loads((trial/'runtime/transport_runtime.json').read_text())
    ns='amcl_diagnostic';paramfile=out/'params.yaml'
    paramfile.write_text(yaml.safe_dump({'/**':{'ros__parameters':params}}))
    processes=[];logs=[]
    def start(package: str,name: str,extra: list) -> None:
        stream=(out/(name+'.log')).open('w');logs.append(stream)
        command=['ros2','run',package,name,'--ros-args','-r','__ns:=/'+ns,
                 '-r','/tf:=/'+ns+'/tf','-r','/tf_static:=/'+ns+'/tf_static','-r','/clock:=/'+ns+'/clock',*extra]
        processes.append(subprocess.Popen(command,cwd=root,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True))
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data,QoSProfile,DurabilityPolicy
    from rosidl_runtime_py.set_message import set_message_fields
    from rosidl_runtime_py.convert import message_to_ordereddict
    from rosgraph_msgs.msg import Clock
    from geometry_msgs.msg import TransformStamped,PoseWithCovarianceStamped
    from sensor_msgs.msg import LaserScan
    from tf2_msgs.msg import TFMessage
    from lifecycle_msgs.srv import ChangeState
    from nav2_msgs.msg import ParticleCloud
    rclpy.init();node=Node('amcl_sensor_replay')
    clock=node.create_publisher(Clock,'/'+ns+'/clock',10)
    tf=node.create_publisher(TFMessage,'/'+ns+'/tf',100)
    static=node.create_publisher(TFMessage,'/'+ns+'/tf_static',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    scanpub=node.create_publisher(LaserScan,'/'+ns+'/scan',qos_profile_sensor_data)
    poses=[];clouds=[]
    node.create_subscription(PoseWithCovarianceStamped,'/'+ns+'/amcl_pose',lambda m:poses.append(message_to_ordereddict(m)),10)
    node.create_subscription(ParticleCloud,'/'+ns+'/particle_cloud',lambda m:clouds.append(message_to_ordereddict(m)),qos_profile_sensor_data)
    def spin(seconds: float) -> None:
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=min(.01,max(0,end-time.monotonic())))
    def stamp(msg: dict) -> float:
        t=msg['header']['stamp'];return t['sec']+t['nanosec']/1e9
    try:
        start('nav2_map_server','map_server',['-p','use_sim_time:=true','-p','yaml_filename:='+str(root/profile['map_yaml'])])
        start('nav2_amcl','amcl',['--params-file',str(paramfile)])
        clock.publish(Clock());spin(.5)
        for name in ('map_server','amcl'):
            client=node.create_client(ChangeState,'/'+ns+'/'+name+'/change_state')
            if not client.wait_for_service(timeout_sec=20):raise TimeoutError(name+' lifecycle')
            for transition in (1,3):
                req=ChangeState.Request();req.transition.id=transition;future=client.call_async(req)
                end=time.monotonic()+20
                while not future.done() and time.monotonic()<end:spin(.02)
                if not future.done() or not future.result().success:raise RuntimeError(name+' lifecycle failed')
        # USD의 운송 base_footprint→base_scan 정적 변환. 원본 scan/odom의 frame ID 보존.
        trans=TransformStamped();trans.header.frame_id=params['base_frame_id'];trans.child_frame_id='transport_01/base_scan'
        device=json.loads((trial/'runtime/transport.json').read_text())
        import xml.etree.ElementTree as ET
        urdf=root/'sim/assets/robots/transport_robot/urdf/transport_robot.portable.urdf'
        model=ET.parse(urdf).getroot()
        chain={j.find('child').get('link'):j for j in model.findall('joint')}
        child=device['scene_binding']['lidar_relative'];base=device['scene_binding']['articulation_relative'];xyz=[0.,0.,0.]
        while child!=base:
            joint=chain[child];origin=joint.find('origin')
            if origin is not None:
                if any(abs(float(v))>1e-10 for v in origin.get('rpy','0 0 0').split()):raise ValueError('회전 장착은 별도 TF 추출 필요')
                xyz=[a+float(b) for a,b in zip(xyz,origin.get('xyz','0 0 0').split())]
            child=joint.find('parent').get('link')
        trans.transform.translation.x,trans.transform.translation.y,trans.transform.translation.z=xyz
        trans.transform.rotation.w=1.
        static.publish(TFMessage(transforms=[trans]));spin(.5)
        odoms=sorted([r['data'] for r in records if r['kind']=='odom'],key=stamp)
        scans=sorted([r['data'] for r in records if r['kind']=='scan'],key=stamp)
        index=0;begin=time.monotonic();scan_start=stamp(scans[0])
        for data in scans:
            st=stamp(data);message=Clock();set_message_fields(message.clock,data['header']['stamp']);clock.publish(message)
            batch=[]
            while index<len(odoms) and stamp(odoms[index])<=st+1e-8:
                odom=odoms[index];t=TransformStamped();set_message_fields(t.header,odom['header']);t.child_frame_id=odom['child_frame_id'];set_message_fields(t.transform.translation,odom['pose']['pose']['position']);set_message_fields(t.transform.rotation,odom['pose']['pose']['orientation']);batch.append(t);index+=1
            if batch:tf.publish(TFMessage(transforms=batch))
            spin(.006)
            scan=LaserScan();set_message_fields(scan,data);scanpub.publish(scan)
            spin(max(.008,begin+(st-scan_start)/args.rate-time.monotonic()))
        spin(1.)
        (out/'poses.json').write_text(json.dumps(poses,indent=2)+'\n')
        (out/'clouds.json').write_text(json.dumps(clouds)+'\n')
        (out/'provenance.json').write_text(json.dumps(dict(trial=str(trial),rate=args.rate,namespace=ns,source='recorded scan + wheel odom; no truth injected',scan_count=len(scans),pose_count=len(poses)),indent=2)+'\n')
        print('poses',len(poses),'last',poses[-1] if poses else None,flush=True)
    finally:
        for p in processes:
            if p.poll() is None:os.killpg(p.pid,signal.SIGINT)
        for p in processes:
            try:p.wait(timeout=8)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        for stream in logs:stream.close()
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
