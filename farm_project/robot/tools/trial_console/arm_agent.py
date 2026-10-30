"""Pinky에서 SSH 파이프로 사용하는 시험 ROS 클라이언트. 복귀 Action을 지원하며 초기위치/ControlState는 발행하지 않는다.

stdin 요청 → ROS 콜백 → stdout JSONL. 서비스 수락과 Action 최종 결과를 구분한다.
Jetson 프로세스나 저널에는 접근하지 않는다.
"""
import json
import queue
import os
import sys
import threading
import time
from typing import Any


def result_success(action: str, goal: Any, payload: dict, ros_status: int) -> bool:
    """ROS terminal 상태와 업무 결과/식별자를 대조한다. 부분 수량은 원문으로 보존한다."""
    if action == 'move_trial':
        return ros_status == 4 and payload.get('error_code') == 0
    if action == 'station_return':
        if any(payload.get(key) != getattr(goal, key) for key in ('robot_id', 'task_id', 'station_id')):
            raise ValueError('복귀 Result 식별자 불일치')
        expected = {4:('SUCCESS',), 5:('CANCELED',), 6:('FAILED', 'CANCELED')}.get(ros_status, ())
        if payload.get('result_code') not in expected:
            raise ValueError('복귀 Result/ROS 종료 상태 불일치')
        return ros_status == 4 and payload.get('error_code') == 'NONE'
    if action == 'harvest':
        expected = {4:'SUCCESS',5:'CANCELED',6:'FAILED'}.get(ros_status)
        task = goal.harvest_task
        if (expected is None or payload.get('result_code') != expected
                or payload.get('robot_id') != goal.robot_id or payload.get('task_id') != task.task_id
                or payload.get('window_id') != task.window_id or payload.get('expected_count') != task.expected_count):
            raise ValueError('팔 Result 식별자/ROS 종료 상태 불일치')
        from harvest_robot.contract import validate_counts
        validate_counts(payload['harvested_count'],payload['failed_count'])
        return ros_status == 4 and payload.get('error_code') != 'CANCEL_UNCONFIRMED'
    if payload.get('transfer_id') != goal.transfer_id or ros_status not in (4,5,6):
        raise ValueError('Discharge Result 식별자/ROS 종료 상태 불일치')
    return ros_status == 4 and not payload['error_codes']


def main() -> None:
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from rosidl_runtime_py.convert import message_to_ordereddict
    from rosidl_runtime_py.set_message import set_message_fields
    from std_srvs.srv import Trigger, SetBool
    from std_msgs.msg import Bool
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav2_msgs.action import NavigateToPose
    from farm_interfaces.action import HarvestTask, Discharge, ReturnToStation
    from farm_interfaces.msg import RobotStatus
    from jetson_harvest_interfaces.msg import RuntimeStatus, ControlState
    from jetson_harvest_interfaces.srv import GetOperation, Recover
    from harvest_robot.jetson_state import RuntimeTracker, RuntimeSample, JetsonSettings
    from dataclasses import fields

    cfg = json.loads(sys.argv[1])
    rclpy.init(args=[])
    node = rclpy.create_node('trial_console_arm_client')
    requests: queue.Queue = queue.Queue()
    output_lock = threading.Lock()
    quitting = threading.Event()
    state: dict[str, Any] = {'operation': None}
    services: dict[str, Any] = {}
    prefix = '/' + cfg['robot_id']
    settings = JetsonSettings(prefix+'/control_state', prefix+'/arm/runtime_status', runtime_mode='depth_v11')
    tracker = RuntimeTracker(cfg['robot_id'], settings)
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)

    def emit(kind: str, **values: Any) -> None:
        with output_lock:
            print(json.dumps(dict(kind=kind, at=time.time(), **values), ensure_ascii=False), flush=True)

    def convert(message: Any) -> dict:
        return dict(message_to_ordereddict(message))

    def observed(name: str, message: Any) -> None:
        payload = convert(message)
        state[name] = {'at': time.time(), 'payload': payload}
        if name == 'runtime':
            values = {f.name: getattr(message, f.name) for f in fields(RuntimeSample) if f.name != 'stamp_ns'}
            tracker.receive(RuntimeSample(stamp_ns=message.stamp.sec*10**9+message.stamp.nanosec, **values), time.monotonic())
        # 고빈도 ControlState/pose는 최신값으로 합쳐 heartbeat에서 출력한다.

    node.create_subscription(RuntimeStatus, prefix+'/arm/runtime_status', lambda m: observed('runtime', m), qos)
    node.create_subscription(ControlState, prefix+'/control_state', lambda m: observed('control', m), qos)
    node.create_subscription(RobotStatus, prefix+'/status', lambda m: observed('robot', m), 10)
    # AMCL은 정지 중 새 표본이 없을 수 있어 마지막 보존 표본을 받는다.
    pose_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                          durability=DurabilityPolicy.TRANSIENT_LOCAL)
    node.create_subscription(PoseWithCovarianceStamped, prefix+'/amcl_pose', lambda m: observed('pose', m), pose_qos)
    node.create_subscription(Bool, prefix+'/transfer_test_mode/enabled', lambda m: observed('transfer_test', m), qos)
    clients = {'harvest': ActionClient(node, HarvestTask, prefix+'/arm/harvest_task'),
               'discharge': ActionClient(node, Discharge, prefix+'/arm/discharge'),
               'station_return': ActionClient(node, ReturnToStation, prefix+'/return_to_station'),
               'move_trial': ActionClient(node, NavigateToPose, prefix+'/trial/navigate_to_pose')}
    srv_types = {'prepare': Trigger, 'stop': Trigger, 'get_operation': GetOperation, 'recover': Recover, 'transfer_test': SetBool}
    srv_clients = {name: node.create_client(cls, prefix+'/transfer_test_mode/set_enabled' if name=='transfer_test' else prefix+'/arm/'+name) for name, cls in srv_types.items()}

    def terminal(operation: dict, result: Any) -> None:
        try:
            response = result.result()
            payload = convert(response.result)
            success = result_success(operation['action'], operation['goal'], payload, response.status)
            emit('result', id=operation['id'], action=operation['action'], ros_status=response.status,
                 success=success, payload=payload)
            if state['operation'] is operation:
                state['operation'] = None
        except Exception as error:
            operation['phase'] = 'UNKNOWN'
            emit('unknown', id=operation['id'], error=str(error), payload=locals().get('payload'), note='최종 결과 미확인. 자동 재전송 없음')

    def cancel(operation: dict) -> None:
        if not operation['cancel_requested']:
            operation['cancel_deadline'] = time.monotonic()+cfg['cancel_timeout_s']
        operation['cancel_requested'] = True
        if operation['phase'] == 'WAITING_READY':
            emit('canceled_before_send', id=operation['id'])
            state['operation'] = None
            return
        if operation.get('handle') is None or operation.get('cancel_sent'):
            return
        operation['cancel_sent'] = True
        future = operation['handle'].cancel_goal_async()
        def ack(value: Any) -> None:
            try:
                emit('cancel_ack', id=operation['id'], payload=convert(value.result()), note='취소 접수는 최종 완료가 아님')
            except Exception as error:
                emit('cancel_error', id=operation['id'], error=str(error))
        future.add_done_callback(ack)

    def accepted(operation: dict, future: Any) -> None:
        try:
            handle = future.result()
            emit('goal_response', id=operation['id'], accepted=bool(handle and handle.accepted))
            if handle is None or not handle.accepted:
                state['operation'] = None
                return
            operation['handle'], operation['phase'] = handle, 'EXECUTING'
            operation['deadline'] = time.monotonic()+cfg['execution_timeout_s']
            handle.get_result_async().add_done_callback(lambda f: terminal(operation, f))
            if operation['cancel_requested']:
                cancel(operation)
        except Exception as error:
            operation['phase'] = 'UNKNOWN'
            emit('unknown', id=operation['id'], error=str(error))

    def send(operation: dict) -> None:
        operation['phase'] = 'AWAITING_ACCEPTANCE'
        operation['deadline'] = time.monotonic()+cfg['response_timeout_s']
        emit('sent', id=operation['id'], action=operation['action'], payload=convert(operation['goal']))
        try:
            future = clients[operation['action']].send_goal_async(operation['goal'],
                feedback_callback=lambda m: emit('feedback', id=operation['id'], payload=convert(m.feedback)))
            future.add_done_callback(lambda f: accepted(operation, f))
        except Exception as error:
            operation['phase'] = 'UNKNOWN'
            emit('unknown', id=operation['id'], error=str(error))

    def service_done(request_id: str, action: str, future: Any) -> None:
        try:
            emit('service_response', id=request_id, action=action, payload=convert(future.result()))
        except Exception as error:
            emit('service_error', id=request_id, action=action, error=str(error))
        services.pop(request_id, None)

    def handle(req: dict) -> None:
        action, request_id = req['action'], req['id']
        body = req.get('body', {})
        if action == 'disconnect':
            if state['operation'] or services:
                raise ValueError('진행/결과 미확인 요청이 있습니다. 취소·결과 확인 후 연결을 종료하세요.')
            emit('reply', id=request_id, ok=True)
            quitting.set()
            return
        if action in ('cancel', 'station_cancel', 'move_trial_cancel'):
            if not state['operation']:
                raise ValueError('이 콘솔이 보낸 활성 Goal이 없습니다.')
            if action == 'station_cancel' and state['operation']['action'] != 'station_return':
                raise ValueError('이 콘솔의 활성 복귀 요청이 없습니다.')
            if action == 'move_trial_cancel' and state['operation']['action'] != 'move_trial':
                raise ValueError('이 콘솔의 활성 시험 이동 요청이 없습니다.')
            cancel(state['operation'])
        elif action in clients:
            if state['operation']:
                raise ValueError('이 콘솔의 이전 Goal이 아직 종료되지 않았습니다.')
            cls = {'harvest':HarvestTask, 'discharge':Discharge, 'station_return':ReturnToStation, 'move_trial':NavigateToPose}[action]
            goal = cls.Goal()
            set_message_fields(goal, body['goal'])
            if action == 'harvest':
                from harvest_robot.contract import validate_task
                validate_task(goal, {'robot_id': cfg['robot_id'], 'map_id': cfg['map_id'], 'control_aliases':cfg.get('control_aliases',{})})
                if not goal.timestamp:
                    raise ValueError('원본 timestamp가 필요합니다.')
            elif action == 'station_return':
                if goal.robot_id != cfg['robot_id'] or not all((goal.task_id, goal.station_id, goal.map_id, goal.timestamp)):
                    raise ValueError('복귀 요청 식별자 누락/불일치')
            elif action == 'discharge' and not goal.transfer_id.strip():
                raise ValueError('transfer_id가 필요합니다.')
            state['operation'] = dict(id=request_id, action=action, goal=goal, handle=None,
                phase='WAITING_READY', deadline=time.monotonic()+cfg['readiness_timeout_s'], cancel_requested=False)
            emit('queued', id=request_id, action=action, payload=convert(goal))
        elif action in srv_clients:
            if any(item['action']==action for item in services.values()):
                raise ValueError('같은 서비스의 이전 응답이 아직 미확인입니다.')
            client = srv_clients[action]
            if not client.service_is_ready():
                raise ValueError('서비스 미연결: '+action)
            request = srv_types[action].Request()
            if action == 'transfer_test':
                if type(body.get('enabled')) is not bool:
                    raise ValueError('배출 시험 enabled는 bool이어야 합니다.')
                request.data = body['enabled']
            elif action == 'get_operation':
                if body.get('kind') not in ('harvest','discharge') or not body.get('key'):
                    raise ValueError('조회 kind/key가 필요합니다.')
                request.kind, request.key = body['kind'], body['key']
            elif action == 'recover':
                if body.get('acknowledgement') != 'DEVICE_AND_LOAD_RECONCILED':
                    raise ValueError('장치·수량 대조 확인 문구가 필요합니다.')
                request.acknowledgement = body['acknowledgement']
            emit('sent', id=request_id, action=action, payload=convert(request))
            future = client.call_async(request)
            services[request_id] = {'action':action, 'deadline':time.monotonic()+20, 'reported':False}
            future.add_done_callback(lambda f: service_done(request_id, action, f))
        else:
            raise ValueError('지원하지 않는 시험 요청')
        emit('reply', id=request_id, ok=True, note='콘솔 접수. Pinky 시험 모드 응답은 서비스 결과 확인' if action=='transfer_test' else '콘솔 접수. 로봇 응답/결과는 별도 이벤트 확인')

    def tick() -> None:
        while not requests.empty():
            req = requests.get_nowait()
            try:
                handle(req)
            except Exception as error:
                emit('reply', id=req.get('id'), ok=False, error=str(error))
        operation = state['operation']
        now = time.monotonic()
        if operation:
            phase = operation['phase']
            if phase == 'WAITING_READY':
                ready = clients[operation['action']].server_is_ready()
                if operation['action'] == 'harvest':
                    ready = ready and tracker.ready_to_send(node.get_clock().now().nanoseconds, now)
                if ready:
                    send(operation)
                elif now >= operation['deadline']:
                    emit('not_sent', id=operation['id'], error='Action 서버 또는 수확 준비 제한시간 초과')
                    state['operation'] = None
            elif phase in ('AWAITING_ACCEPTANCE','EXECUTING') and now >= operation['deadline']:
                operation['phase'] = 'UNKNOWN'
                emit('unknown', id=operation['id'], error='응답/실행 제한시간 초과. 종료 확인 필요')
                cancel(operation)
        if operation and operation.get('cancel_requested') and now >= operation.get('cancel_deadline', float('inf')) and not operation.get('cancel_timeout_reported'):
            operation['cancel_timeout_reported'] = True
            emit('unknown', id=operation['id'], error='취소 후 terminal 결과 대기 만료. 종료 확인 필요')
        for request_id, item in list(services.items()):
            if now >= item['deadline'] and not item['reported']:
                item['reported'] = True
                emit('service_timeout', id=request_id, action=item['action'], note='결과 미확인; 재전송하지 않음')

    def heartbeat() -> None:
        operation = state['operation']
        emit('snapshot', observations={k:v for k,v in state.items() if k != 'operation'},
             operation=None if operation is None else {k:operation[k] for k in ('id','action','phase','cancel_requested')},
             pending_services=services, servers={k:c.server_is_ready() for k,c in clients.items()},
             services={k:c.service_is_ready() for k,c in srv_clients.items()},
             runtime=tracker.snapshot(time.monotonic()))

    def read() -> None:
        for line in sys.stdin:
            try:
                requests.put(json.loads(line))
            except Exception as error:
                emit('protocol_error', error=str(error))
        quitting.set()
    threading.Thread(target=read, daemon=True).start()
    node.create_timer(.05, tick)
    node.create_timer(.5, heartbeat)
    emit('connected', robot_id=cfg['robot_id'], domain=int(os.environ.get('ROS_DOMAIN_ID','0')), note='구독/클라이언트만 생성. ControlState 발행 없음')
    try:
        while not quitting.is_set():
            rclpy.spin_once(node, timeout_sec=.1)
    finally:
        if state['operation']:
            emit('unknown', id=state['operation']['id'], error='시험 연결 종료. 팔 작업 종료 여부 미확인')
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
