"""읽기 전용: 보존된 작업 이벤트와 실제 ROS 파라미터 수집. Goal/설정 변경 없음."""
from pathlib import Path
import json
import time
import tempfile
import tarfile
import yaml
import rclpy
from rcl_interfaces.srv import GetParameters, ListParameters
from rclpy.parameter import parameter_value_to_python
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String

ROOT=Path('/home/vic/vmany/main/farm_project')

def flatten(value,prefix=''):
    result={}
    for key,item in value.items():
        name=prefix+'.'+key if prefix else key
        if isinstance(item,dict):result.update(flatten(item,name))
        else:result[name]=item
    return result

def main():
    out=Path(tempfile.mkdtemp(prefix='harvest_arc_runtime_'))
    report={'read_only':True,'task_events':[],'parameters':{},'errors':{},'comparison':{}}
    rclpy.init();node=rclpy.create_node('harvest_arc_readonly_audit')
    qos=QoSProfile(depth=100,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL)
    def event(msg):
        try:report['task_events'].append(json.loads(msg.data))
        except ValueError:report['task_events'].append({'raw':msg.data})
    sub=node.create_subscription(String,'/harvest_01/task_events',event,qos)
    requests=[];clients=[]
    targets=['controller_server','local_costmap/local_costmap','velocity_smoother','bt_navigator']
    try:
        # 이벤트를 받으면서 파라미터 목록 요청은 병렬로 시작한다.
        for name in targets:
            client=node.create_client(ListParameters,'/harvest_01/'+name+'/list_parameters');clients.append(client)
            if not client.wait_for_service(timeout_sec=1.0):
                report['errors'][name]='파라미터 서비스 없음';continue
            req=ListParameters.Request();req.depth=0
            requests.append((name,client.call_async(req)))
        deadline=time.monotonic()+8
        while time.monotonic()<deadline and not all(f.done() for _,f in requests):
            rclpy.spin_once(node,timeout_sec=.05)
        values=[]
        for name,future in requests:
            if not future.done():report['errors'][name]='파라미터 목록 응답 없음';continue
            try:
                names=list(future.result().result.names)
                client=node.create_client(GetParameters,'/harvest_01/'+name+'/get_parameters');clients.append(client)
                if not client.wait_for_service(timeout_sec=1.0):
                    raise TimeoutError('파라미터 조회 서비스 없음')
                req=GetParameters.Request();req.names=names
                values.append((name,names,client.call_async(req)))
            except Exception as exc:report['errors'][name]=str(exc)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline and not all(f.done() for _,_,f in values):
            rclpy.spin_once(node,timeout_sec=.05)
        for name,names,future in values:
            try:
                if not future.done():raise TimeoutError('파라미터 값 응답 없음')
                report['parameters'][name]={k:parameter_value_to_python(v) for k,v in zip(names,future.result().values)}
            except Exception as exc:report['errors'][name]=str(exc)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.05)
        marker=Path('/tmp/harvest_bias_trial_path')
        if marker.exists():
            folder=Path(marker.read_text().strip()).resolve()
            if folder.is_relative_to(ROOT/'runs/tag_bias_trial') and folder.is_dir():
                report['run_folder']=str(folder)
                nav=folder/'arc_nav2.yaml'
                if nav.exists():
                    expected=yaml.safe_load(nav.read_text())
                    for name,actual in report['parameters'].items():
                        subtree=expected
                        for part in name.split('/'):subtree=subtree.get(part,{})
                        flat=flatten(subtree.get('ros__parameters',{}))
                        report['comparison'][name]={k:{'expected':v,'actual':actual.get(k),'missing':k not in actual}
                            for k,v in flat.items() if k not in actual or actual[k]!=v}
    finally:
        node.destroy_node();rclpy.shutdown()
        (out/'runtime.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str))
        archive=out.with_suffix('.tar.gz')
        with tarfile.open(archive,'w:gz') as tar:
            tar.add(out/'runtime.json',arcname='runtime.json')
            if report.get('run_folder'):
                folder=Path(report['run_folder'])
                for p in folder.rglob('*'):
                    if p.is_file() and p.suffix in {'.json','.yaml','.xml','.log'} and 'bag' not in p.relative_to(folder).parts:
                        tar.add(p,arcname='run/'+str(p.relative_to(folder)))
        print(json.dumps({'archive':str(archive),'events':len(report['task_events']),
            'parameter_nodes':list(report['parameters']),'differences':report['comparison'],'errors':report['errors']},indent=2,ensure_ascii=False))
        Path('/tmp/harvest_arc_runtime_archive').write_text(str(archive)+'\n')

if __name__=='__main__':main()
