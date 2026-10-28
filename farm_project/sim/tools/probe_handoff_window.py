"""실제 수확 완료 후 제공된 Frontend 워커로 인계 진입과 취소를 관측한다."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.set_message import set_message_fields
from farm_interfaces.action import HarvestTask
from farm_interfaces.msg import RobotStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from tf2_msgs.msg import TFMessage
from std_srvs.srv import Trigger
from std_msgs.msg import String
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    base = Path(sys.argv[1]).resolve()
    result = dict(passed=False, scope='one actual window + body entry + explicit cancel, not full handoff')
    pickup = (base/'runtime/pickup_goal.json').exists()
    if pickup:
        result['scope'] = 'one actual window + TransportPickup + DockTransfer + restore; not full SEC01'
    events = (base/'events.jsonl').open('w', buffering=1)
    lock = threading.Lock(); latest = {}; acks = {}; statuses = {}
    def record(kind: str, **values: object) -> None:
        with lock:
            events.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),
                mono_ns=time.monotonic_ns(),kind=kind, **values), ensure_ascii=False)+'\n')
    spec = dict(environment='simul', domain_id=13, map_id='farm_map_v1', frame_id='map',
        harvest_robot_id='harvest_01', transport_robot_id='transport_01',
        harvest_action='/harvest_01/dock_transfer', transport_action='/transport_01/transport_pickup',
        transport_event='/transport_01/transfer_event', harvest_status='/harvest_01/status',
        transport_status='/transport_01/status', watched_actions=dict(
            harvest=['/harvest_01/harvest_task','/harvest_01/return_to_station'],
            transport=['/transport_01/navigate_to_node','/transport_01/return_to_station','/transport_01/bucket_unload']))
    worker_path = ROOT.parent/'Frontend/dashboard/backend/handoff_worker.py'
    stderr = (base/'frontend_stderr.log').open('w')
    worker = subprocess.Popen(['/usr/bin/python3','-u',str(worker_path),'--spec',json.dumps(spec),
        '--state',str(base/'control/simul-handoff.json')], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=stderr, text=True)  # probe와 같은 그룹: watchdog 종료 시에도 고아 워커를 남기지 않는다.
    def read_worker() -> None:
        with (base/'frontend_worker.jsonl').open('w', buffering=1) as stream:
            for line in worker.stdout:
                stream.write(line)
                try: item = json.loads(line)
                except ValueError: continue
                if item.get('kind') == 'state': latest['state'] = item['state']
                elif item.get('kind') == 'ack': acks[item['id']] = item
    reader = threading.Thread(target=read_worker, daemon=True); reader.start()
    rclpy.init(); node = Node('handoff_window_probe', parameter_overrides=[Parameter('use_sim_time',value=True)])
    executor = MultiThreadedExecutor(num_threads=2); executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True); spinner.start()
    client = ActionClient(node, HarvestTask, '/harvest_01/harvest_task')
    prepare = node.create_client(Trigger, '/harvest_01/sim/transfer/prepare_arm')
    def on_status(message: RobotStatus) -> None:
        data = dict(message_to_ordereddict(message)); previous = statuses.get('harvest', {})
        statuses['harvest'] = data
        keys = ('state','ready','error_code','error_message','current_task_id')
        if any(previous.get(k) != data.get(k) for k in keys):
            record('harvest_status', data={k:data.get(k) for k in keys})
    node.create_subscription(RobotStatus, '/harvest_01/status', on_status, qos_profile_sensor_data)
    # 정지 전후 벽 관측과 odom을 원문으로 남겨 허용오차 경계 실패를 재계산한다.
    # 제어 입력·판정은 바꾸지 않는다.
    node.create_subscription(PoseStamped, '/harvest_01/handoff/wall_observation',
        lambda msg:record('wall_observation',data=dict(message_to_ordereddict(msg))),10)
    node.create_subscription(Odometry, '/harvest_01/odom',
        lambda msg:record('harvest_odom',data=dict(message_to_ordereddict(msg))),qos_profile_sensor_data)
    node.create_subscription(PoseWithCovarianceStamped, '/harvest_01/amcl_pose',
        lambda msg:record('harvest_amcl',data=dict(message_to_ordereddict(msg))),qos_profile_sensor_data)
    node.create_subscription(LaserScan, '/harvest_01/scan',
        lambda msg:record('harvest_scan',data=dict(message_to_ordereddict(msg))),qos_profile_sensor_data)
    def transforms(message: TFMessage, static: bool = False) -> None:
        for value in message.transforms:
            if (static and value.child_frame_id.startswith('harvest_01/')) or (
                    value.header.frame_id == 'map' and value.child_frame_id == 'harvest_01/odom'):
                record('harvest_tf_static' if static else 'harvest_map_odom',
                       data=dict(message_to_ordereddict(value)))
    node.create_subscription(TFMessage,'/tf',transforms,qos_profile_sensor_data)
    node.create_subscription(TFMessage,'/tf_static',lambda msg:transforms(msg,True),
        QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    if pickup:
        node.create_subscription(String, '/transport_01/sim/basket_alignment',
            lambda msg:record('basket_alignment',data=json.loads(msg.data)),10)
    def wait(predicate, timeout: float, label: str) -> None:
        deadline = time.monotonic()+timeout
        while not predicate():
            if worker.poll() is not None: raise RuntimeError('Frontend 워커 종료')
            if time.monotonic()>deadline: raise TimeoutError(label)
            time.sleep(.05)
    def future(ticket, timeout: float, label: str):
        wait(ticket.done, timeout, label); return ticket.result()
    def command(payload: dict) -> dict:
        rid = uuid4().hex; record('frontend_command', id=rid, command=payload)
        worker.stdin.write(json.dumps(dict(id=rid,command=payload))+'\n'); worker.stdin.flush()
        wait(lambda:rid in acks,15,'관제 명령 접수')
        reply = acks[rid]
        if not reply['ok']: raise RuntimeError('관제 거절: '+reply.get('error',''))
        return reply['result']
    harvest_handle = None; harvest_result = None; job_id = None; pickup_id = None
    terminal = {'FAILED','REJECTED','CANCELED','UNKNOWN','SUCCEEDED'}
    def get_job(identifier: str) -> dict:
        return next((j for j in latest.get('state',{}).get('jobs',[]) if j['id']==identifier), {})
    def job() -> dict:
        return get_job(job_id)
    try:
        wait(lambda:client.server_is_ready() and prepare.service_is_ready() and statuses.get('harvest',{}).get('ready'),
             240, '수확 서버·센서 준비')
        deadline = time.monotonic()+120
        while True:
            reply = future(prepare.call_async(Trigger.Request()),10,'팔 준비 확인')
            if reply.success: break
            if time.monotonic()>deadline: raise TimeoutError(reply.message)
            time.sleep(.5)
        task = json.loads((base/'window.json').read_text()); original_task_id = task['task_id']
        task['task_id'] = 'handoff_window_'+uuid4().hex[:12]
        goal = HarvestTask.Goal()
        set_message_fields(goal, dict(robot_id='harvest_01', map_id='farm_map_v1', harvest_task=task,
            timestamp=datetime.now(timezone.utc).isoformat()))
        record('harvest_goal', original_task_id=original_task_id, goal=dict(message_to_ordereddict(goal)))
        harvest_handle = future(client.send_goal_async(goal, feedback_callback=lambda msg:
            record('harvest_feedback', data=dict(message_to_ordereddict(msg.feedback)))),15,'수확 Goal')
        if not harvest_handle.accepted: raise RuntimeError('수확 Goal 거절')
        harvest_result = harvest_handle.get_result_async()
        reply = future(harvest_result,1200,'실제 수확 결과 (시험 watchdog)')
        result['harvest'] = dict(status=reply.status, result=dict(message_to_ordereddict(reply.result)))
        record('harvest_result', **result['harvest'])
        if reply.status!=4 or reply.result.result_code!='SUCCESS': raise RuntimeError('실제 윈도우 수확 실패')
        wait(lambda:latest.get('state',{}).get('ready',{}).get('harvest') and
             not latest.get('state',{}).get('blocked',{}).get('harvest'),30,'관제 수확 종료·인계서버 확인')
        if pickup:
            wait(lambda:latest.get('state',{}).get('ready',{}).get('transport'),60,'관제 운송 서버 확인')
            response = command(dict(op='start_pickup',
                staging_pose=json.loads((base/'runtime/pickup_goal.json').read_text()),
                target_marker_id=42, docking_marker_id=41))
            pickup_id = response['job_id']
            record('pickup_started', **response)
            wait(lambda:'WAITING_FOR_TRANSFER' in get_job(pickup_id).get('observed_events',{}) or
                 get_job(pickup_id).get('state') in terminal, 480, '실제 42번 접근')
            if 'WAITING_FOR_TRANSFER' not in get_job(pickup_id).get('observed_events',{}):
                raise RuntimeError('42번 접근 실패: '+json.dumps(get_job(pickup_id),ensure_ascii=False))
        response = command(dict(op='start_dock',expected_count=reply.result.harvested_count))
        job_id = response['job_id']
        record('dock_started', **response)
        wait(lambda:'DOCK_READY' in job().get('observed_events',{}) or job().get('state') in terminal,
             300,'인계 차체 진입 (시험 watchdog)')
        result['dock_before_stop'] = job()
        if 'DOCK_READY' not in job().get('observed_events',{}):
            raise RuntimeError('DOCK_READY 이전 인계 종료: '+json.dumps(job(),ensure_ascii=False))
        result['dock_ready'] = True
        if pickup:
            for op in ('dock_ready','dock_stable','transfer_complete','transport_clear'):
                def event_available() -> bool:
                    state = latest.get('state',{})
                    failed = [j for j in state.get('jobs',[]) if j.get('state') in terminal-{'SUCCEEDED'}]
                    if failed: raise RuntimeError('인계 액션 실패: '+json.dumps(failed,ensure_ascii=False))
                    control = state.get('event_controls',{}).get(op,{})
                    return bool(control.get('observed') and control.get('allowed'))
                wait(event_available,180,'실제 피드백 대기: '+op)
                control = latest['state']['event_controls'][op]
                command(dict(op=op,job_id=control['job_id']))
                wait(lambda:latest.get('state',{}).get('event_controls',{}).get(op,{}).get('delivery') in
                     ('ACCEPTED','REJECTED','UNKNOWN'),15,'이벤트 응답: '+op)
                record('event_delivery', op=op, control=latest['state']['event_controls'][op])
                if latest['state']['event_controls'][op]['delivery']!='ACCEPTED':
                    raise RuntimeError('이벤트 서비스 거절: '+op)
            wait(lambda:job().get('state') in terminal and get_job(pickup_id).get('state') in terminal,
                 300,'인계 복원 완료')
            result['dock_final'], result['pickup_final'] = job(), get_job(pickup_id)
            if latest['state'].get('completion',{}).get('state')!='SUCCEEDED':
                raise RuntimeError('양쪽 인계 성공 및 복원 조건 미충족')
        else:
            command(dict(op='stop',job_id=job_id))
            wait(lambda:job().get('state') in terminal,40,'인계 취소 종료')
            result['dock_final'] = job()
            if job().get('state')!='CANCELED': raise RuntimeError('명시적 취소 결과 미확인')
        if (base/'post_handoff.json').exists():
            from probe_handoff_return import run
            run(base,node,wait,future,record,result)
        result['passed'] = True
    except BaseException as error:
        result['error'] = type(error).__name__+': '+str(error)
        record('error',detail=result['error'])
        raise
    finally:
        try:
            if harvest_handle is not None and harvest_handle.accepted and harvest_result is not None and not harvest_result.done():
                future(harvest_handle.cancel_goal_async(),10,'수확 취소')
                future(harvest_result,30,'수확 취소 결과')
            for identifier in (job_id, pickup_id):
                if identifier and get_job(identifier).get('state') in ('SENDING','RUNNING'):
                    command(dict(op='stop',job_id=identifier))
                    wait(lambda:get_job(identifier).get('state') not in ('SENDING','RUNNING','CANCELING'),40,'종료 정지')
        except Exception as error: result['cleanup_error'] = str(error)
        result['frontend_final'] = latest.get('state',{})
        (base/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        executor.shutdown(timeout_sec=3); spinner.join(3); node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
        if worker.poll() is None:
            worker.send_signal(signal.SIGINT)
            try: worker.wait(timeout=10)
            except subprocess.TimeoutExpired: worker.kill(); worker.wait()
        reader.join(3); stderr.close(); events.close()


if __name__ == '__main__': main()
