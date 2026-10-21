"""기존 Nav2는 유지하고 곡선 서버만 임시 실행한다. 기본 check는 이동하지 않는다."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]
from farm_navigation.arc_isolation import isolated_parameters
from arc_return_support import RETURN_CHECKER


def main() -> None:
    import rclpy
    import yaml
    from rcl_interfaces.srv import ListParameters, GetParameters
    from rclpy.parameter import parameter_value_to_python
    from lifecycle_msgs.srv import GetState, ChangeState
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['check','plan','execute'])
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--return-from',type=Path,help='성공한 신규 후진 실행 JSON; 복귀 모드 명시')
    parser.add_argument('--retreat-from',type=Path)
    parser.add_argument('--align-from',type=Path)
    parser.add_argument('--after',type=Path)
    parser.add_argument('--cycle-id',default='')
    parser.add_argument('--exclusive',action='store_true')
    parser.add_argument('--input-trace',action='store_true')
    args=parser.parse_args()
    if args.input_trace and (args.mode!='plan' or not args.align_from):parser.error('input-trace는 무이동 align 진단만 허용합니다.')
    if sum(x is not None for x in (args.return_from,args.retreat_from,args.align_from))>1:parser.error('단계 중복')
    if (args.retreat_from or args.align_from) and not (args.after and args.cycle_id):parser.error('복귀 단계에는 cycle/직전 성공 기록 필요')
    if args.mode=='execute' and (not args.exclusive or not args.reference):
        parser.error('execute에는 --exclusive --reference PLAN.json 필요')
    lock=open('/tmp/manyfarm_arc_isolated.lock','w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ns='/harvest_01'
    prefix=ns+'/arc_trial_'+uuid.uuid4().hex[:8]
    folder=Path.home()/'Downloads/transfer_arc_isolated'/str(time.time_ns());folder.mkdir(parents=True)
    print('기록:',folder,flush=True)
    rclpy.init();node=rclpy.create_node('arc_isolated_supervisor',namespace=ns)
    behavior_process=None;behavior_log=None
    process=None;log=None;before=None;report={'ok':False,'mode':args.mode,'prefix':prefix}

    def call(typ, name, req, timeout=8):
        c=node.create_client(typ,name)
        try:
            if not c.wait_for_service(timeout_sec=timeout):raise RuntimeError('서비스 없음: '+name)
            f=c.call_async(req);rclpy.spin_until_future_complete(node,f,timeout_sec=timeout)
            if not f.done() or f.exception():raise RuntimeError('서비스 응답 실패: '+name)
            return f.result()
        finally:node.destroy_client(c)

    def params(name):
        names=call(ListParameters,name+'/list_parameters',ListParameters.Request(depth=0)).result.names
        values=call(GetParameters,name+'/get_parameters',GetParameters.Request(names=names)).values
        return dict(zip(names,map(parameter_value_to_python,values)))

    def snapshot():
        return {name:params(ns+'/'+name) for name in ('controller_server','local_costmap/local_costmap','velocity_smoother')}

    def transition(number, name='controller_server'):
        req=ChangeState.Request();req.transition.id=number
        if not call(ChangeState,prefix+'/'+name+'/change_state',req,20).success:
            raise RuntimeError('독립 서버 lifecycle 실패: '+str(number))

    try:
        before=snapshot();(folder/'baseline_before.json').write_text(json.dumps(before,indent=2))
        cp=before['controller_server'];cm=before['local_costmap/local_costmap']
        if 'TransferArc' in cp.get('controller_plugins',[]):raise RuntimeError('기존 기본 런치에서만 실행하세요. 기존 서버에 TransferArc가 있습니다.')
        if call(GetState,ns+'/controller_server/get_state',GetState.Request()).current_state.id!=3:
            raise RuntimeError('기존 주행 서버가 active가 아닙니다.')
        # 파일의 상대 토픽을 추측하지 않고 실제 costmap 구독에서 가져온다.
        subscriptions=node.get_subscriber_names_and_types_by_node('local_costmap',ns+'/local_costmap')
        scans=[name for name,types in subscriptions if 'sensor_msgs/msg/LaserScan' in types]
        if len(scans)!=1:raise RuntimeError('기존 costmap의 LaserScan 구독을 하나로 확인할 수 없습니다: '+str(scans))
        conf=isolated_parameters(cp,cm,prefix,scans[0],ns+'/odom')
        if args.return_from:
            conf[prefix+'/controller_server']['ros__parameters']['transfer_arc_goal.yaw_goal_tolerance']=RETURN_CHECKER
        if args.retreat_from:
            from harvest_robot.transfer_retreat import retreat_profile
            station={k.split('.',1)[1]:v for k,v in cp.items() if k.startswith('StationReverse.')}
            profile=retreat_profile(station)
            server=conf[prefix+'/controller_server']['ros__parameters']
            for key in list(server):
                if key.startswith(('TransferArc.','transfer_arc_goal.','transfer_arc_progress.')):del server[key]
            server.update(controller_plugins=['Retreat'],goal_checker_plugins=['retreat_goal'],progress_checker_plugins=['retreat_progress'])
            for plugin,values in profile.items():server.update({plugin+'.'+key:value for key,value in values.items()})
        if args.align_from:
            from harvest_robot.transfer_retreat import alignment_parameters
            behavior=alignment_parameters(prefix,cm['robot_base_frame'],use_sim_time=cp.get('use_sim_time',False),transform_tolerance=cm.get('transform_tolerance',.5))
            conf[prefix+'/behavior_server']={'ros__parameters':behavior}
        config=folder/'parameters.yaml';config.write_text(yaml.safe_dump(conf,sort_keys=False))
        baseline_hash=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()
        report['baseline_hash']=baseline_hash;report['scan_topic']=scans[0]
        log=open(folder/'controller.log','w')
        command=['ros2','run','nav2_controller','controller_server','--ros-args',
                 '-r','__ns:='+prefix,'--params-file',str(config),
                 '-r','/tf:='+ns+'/tf','-r','/tf_static:='+ns+'/tf_static',
                 '-r','cmd_vel:='+prefix+'/raw_cmd_vel','-r','odom:='+ns+'/odom']
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        transition(1)
        state=call(GetState,prefix+'/controller_server/get_state',GetState.Request()).current_state.id
        if state!=2:raise RuntimeError('configure 후 inactive 확인 실패')
        # 실제로 적용된 주요 설정 및 기존 서버 불변을 이동 전에 검증한다.
        actual=params(prefix+'/controller_server');actual_cm=params(prefix+'/local_costmap/local_costmap')
        expected=conf[prefix+'/controller_server']['ros__parameters']
        differences={k:[v,actual.get(k)] for k,v in expected.items() if actual.get(k)!=v}
        for k,v in conf[prefix+'/local_costmap/local_costmap']['ros__parameters'].items():
            if k not in actual_cm: continue  # 비활성 layer의 과거 선언값은 로드되지 않을 수 있다.
            if actual_cm[k]!=v:differences['costmap.'+k]=[v,actual_cm[k]]
        if differences:raise RuntimeError('독립 설정 불일치: '+json.dumps(differences))
        if snapshot()!=before:raise RuntimeError('기존 실행 파라미터가 달라졌습니다.')
        # 출력은 시험 전용 토픽으로만 향해야 한다. 실제 cmd_vel 연결은 execute의 gate뿐이다.
        deadline=time.monotonic()+3
        pubs=[]
        while time.monotonic()<deadline:
            pubs=node.get_publisher_names_and_types_by_node('controller_server',prefix)
            if any(name==prefix+'/raw_cmd_vel' for name,types in pubs):break
            rclpy.spin_once(node,timeout_sec=.1)
        velocity_topics=[name for name,types in pubs if any(t in ('geometry_msgs/msg/Twist','geometry_msgs/msg/TwistStamped') for t in types)]
        if velocity_topics != [prefix+'/raw_cmd_vel']:
            raise RuntimeError('곡선 서버 출력 분리 확인 실패: '+str(velocity_topics))
        smoother_subs=node.get_subscriber_names_and_types_by_node('velocity_smoother',ns)
        if (ns+'/cmd_vel_nav') not in [name for name,types in smoother_subs if 'geometry_msgs/msg/Twist' in types]:
            raise RuntimeError('기존 smoother Twist 입력 연결 확인 실패')
        report['configured']=True
        report['isolated_velocity_topic']=velocity_topics[0]
        if args.mode!='check':
            transition(3)
            if call(GetState,prefix+'/controller_server/get_state',GetState.Request()).current_state.id!=3:
                raise RuntimeError('독립 서버 active 확인 실패')
            if args.align_from:
                behavior_log=open(folder/'behavior.log','w')
                behavior_process=subprocess.Popen(['ros2','run','nav2_behaviors','behavior_server','--ros-args',
                    '-r','__ns:='+prefix,'--params-file',str(config),'-r','/tf:='+ns+'/tf',
                    '-r','/tf_static:='+ns+'/tf_static','-r','cmd_vel:='+prefix+'/raw_cmd_vel'],
                    stdout=behavior_log,stderr=subprocess.STDOUT,start_new_session=True)
                transition(1,'behavior_server')
                actual_behavior=params(prefix+'/behavior_server')
                if any(actual_behavior.get(k)!=v for k,v in behavior.items()):raise RuntimeError('방향 맞춤 실제 설정 불일치')
                transition(3,'behavior_server')
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    bp=node.get_publisher_names_and_types_by_node('behavior_server',prefix)
                    outputs=[n for n,ts in bp if any(t in ('geometry_msgs/msg/Twist','geometry_msgs/msg/TwistStamped') for t in ts)]
                    if outputs:break
                    rclpy.spin_once(node,timeout_sec=.1)
                if outputs!=[prefix+'/raw_cmd_vel']:raise RuntimeError('방향 맞춤 출력 격리 실패')
            command=[sys.executable,str(Path(__file__).with_name('arc_trial.py')),'trial',
                     '--isolated-prefix',prefix,'--baseline-hash',baseline_hash,'--output',str(folder)]
            if args.input_trace:command+=['--input-trace']
            if args.retreat_from:command+=['--retreat-from',str(args.retreat_from.resolve())]
            if args.align_from:command+=['--align-from',str(args.align_from.resolve())]
            if args.after:command+=['--after',str(args.after.resolve())]
            if args.cycle_id:command+=['--cycle-id',args.cycle_id]
            if args.return_from:command+=['--return-from',str(args.return_from.resolve())]
            if args.mode=='execute':command+=['--execute','--exclusive','--reference',str(args.reference.resolve())]
            subprocess.run(command,check=True)
        report['ok']=True
        if args.mode in ('plan','execute'):
            plans=list(folder.glob('*_arc.json'))
            if len(plans)!=1:raise RuntimeError('계획 기록을 하나로 확인하지 못했습니다.')
            record=json.loads(plans[0].read_text())
            expected_phase='INPUT_DIAGNOSTIC' if args.input_trace else ('PLAN_ONLY' if args.mode=='plan' else 'SUCCEEDED')
            if not record.get('ok') or record.get('phase')!=expected_phase:raise RuntimeError('곡선 기록 검증 실패')
            report['diagnostic_file' if args.input_trace else ('plan_file' if args.mode=='plan' else 'execution_file')]=str(plans[0])
    except BaseException as error:
        report['ok']=False
        report['error']=str(error) or type(error).__name__
    finally:
        if behavior_process is not None and behavior_process.poll() is None:
            os.killpg(behavior_process.pid,signal.SIGINT)
            try:behavior_process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(behavior_process.pid,signal.SIGKILL);behavior_process.wait();report['ok']=False
        if behavior_log:behavior_log.close()
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGINT)
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        if log:log.close()
        for child in (behavior_process,process):
            if child is not None and child.returncode not in (0,-signal.SIGINT,130):
                report['ok']=False;report['cleanup_error']='하위 ROS 프로세스 비정상 종료'
        for name in ('controller.log','behavior.log'):
            child_log=folder/name
            if child_log.exists() and any(x in child_log.read_text(errors='replace') for x in
                ('cannot use Destroyable','Traceback (most recent call last)','terminate called','SEVERE WARNING!!!')):
                report['ok']=False;report['cleanup_error']='하위 ROS 로그 예외: '+name
        try:
            if before is not None:
                after=snapshot();(folder/'baseline_after.json').write_text(json.dumps(after,indent=2))
                report['baseline_unchanged']=before==after
                if before!=after:report['ok']=False
        except BaseException as error:report['ok']=False;report['verification_error']=str(error)
        if report.get('ok'):
            if report.get('plan_file'):
                (folder.parent/'latest_plan.txt').write_text(report['plan_file']+'\n')
            if report.get('execution_file') and not (args.return_from or args.retreat_from or args.align_from):
                (folder.parent/'latest_departure.txt').write_text(report['execution_file']+'\n')
        if report.get('ok') and report.get('plan_file'):
            Path('/tmp/harvest_arc_isolated_plan').write_text(report['plan_file']+'\n')
        (folder/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        node.destroy_node();rclpy.shutdown()
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        if not report['ok'] and (folder/'controller.log').exists():
            print('\n'.join((folder/'controller.log').read_text(errors='replace').splitlines()[-30:]))
    if not report['ok']:raise SystemExit(1)


if __name__=='__main__':main()
