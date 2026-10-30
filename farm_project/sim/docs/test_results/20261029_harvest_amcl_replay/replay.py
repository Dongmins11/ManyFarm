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
    args=parser.parse_args();root=Path.cwd()
    if not math.isfinite(args.rate) or args.rate<=0:raise ValueError('양의 재생 속도 필요')
    if os.environ.get('ROS_DOMAIN_ID')!='13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE')!='SUBNET':
        raise ValueError('Domain13/SUBNET 필요')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    trial=args.trial.resolve()
    events=[json.loads(l) for l in (trial/'events.jsonl').read_text().splitlines()]
    records=[dict(e,kind={'harvest_scan':'scan','harvest_odom':'odom'}[e['kind']]) for e in events if e['kind'] in ('harvest_scan','harvest_odom')]
    from farm_navigation.configuration import load_nav2_parameters
    params=load_nav2_parameters(trial/'runtime/nav2_harvest.yaml',root)['amcl']['ros__parameters']
    params.update(use_sim_time=True,tag_robot_id='amcl_harvest_diagnostic',tag_map_id='farm_map_v1')
    if args.amcl_overrides:params.update(json.loads(args.amcl_overrides.read_text()))
    profile=yaml.safe_load((trial/'runtime/harvest_runtime.yaml').read_text())
    ns='amcl_harvest_diagnostic';paramfile=out/'params.yaml'
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
        start('farm_tag_amcl','amcl',['--params-file',str(paramfile)])
        clock.publish(Clock());spin(.5)
        for name in ('map_server','amcl'):
            client=node.create_client(ChangeState,'/'+ns+'/'+name+'/change_state')
            if not client.wait_for_service(timeout_sec=20):raise TimeoutError(name+' lifecycle')
            for transition in (1,3):
                req=ChangeState.Request();req.transition.id=transition;future=client.call_async(req)
                end=time.monotonic()+20
                while not future.done() and time.monotonic()<end:spin(.02)
                if not future.done() or not future.result().success:raise RuntimeError(name+' lifecycle failed')
        # 기록된 수확 로봇 정적 TF(라이다 yaw π 포함)를 그대로 재생한다.
        transforms=[]
        for e in events:
            if e['kind']=='harvest_tf_static':
                trans=TransformStamped();set_message_fields(trans,e['data']);transforms.append(trans)
        static.publish(TFMessage(transforms=transforms));spin(.5)
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
