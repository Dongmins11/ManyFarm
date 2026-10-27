"""단일 요청 ROS 클라이언트. 이동 Action/속도/초기위치를 발행하지 않는다."""
import json
import sys
import time


def main() -> None:
    import rclpy
    from rclpy.parameter import Parameter
    from rcl_interfaces.srv import SetParametersAtomically
    from rosidl_runtime_py.convert import message_to_ordereddict as convert
    from std_srvs.srv import Trigger
    from jetson_harvest_interfaces.msg import RuntimeStatus
    from jetson_harvest_interfaces.srv import Recover
    req = json.loads(sys.argv[1]); prefix = '/' + req['robot_id'] + '/arm/'
    rclpy.init(args=[]); node = rclpy.create_node('trial_console_probe'); samples = []
    node.create_subscription(RuntimeStatus, prefix+'runtime_status', lambda m: samples.append(convert(m)), 10)
    try:
        action = req['action']
        if action == 'status':
            end = time.monotonic() + 2.5
            while time.monotonic() < end:
                rclpy.spin_once(node, timeout_sec=.1)
            result = dict(available=bool(samples), status=samples[-1] if samples else None)
        else:
            if action == 'recover':
                typ, name, request = Recover, prefix+'recover', Recover.Request()
                request.acknowledgement = 'DEVICE_AND_LOAD_RECONCILED'
            elif action in ('prepare', 'stop', 'repeat_last_harvest'):
                typ, name, request = Trigger, prefix+action, Trigger.Request()
            elif action == 'count':
                count = req['count']
                if type(count) is not int or not 0 <= count <= 1000:
                    raise ValueError('수확 개수는 0~1000 정수여야 합니다.')
                typ, name, request = SetParametersAtomically, '/jetson_dummy_pc/set_parameters_atomically', SetParametersAtomically.Request()
                request.parameters = [Parameter('trial_targets', value=count).to_parameter_msg()]
            else:
                raise ValueError('허용하지 않은 작업')
            client = node.create_client(typ, name)
            if not client.wait_for_service(timeout_sec=4):
                raise RuntimeError('서비스 연결 없음: '+name)
            future = client.call_async(request)
            rclpy.spin_until_future_complete(node, future, timeout_sec=8)
            if not future.done() or future.result() is None:
                raise RuntimeError('서비스 결과 미확정. 자동 재시도하지 않습니다.')
            result = convert(future.result())
            ok = result.get('success', result.get('result', {}).get('successful', False))
            if not ok:
                raise RuntimeError(json.dumps(result, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
    finally:
        node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
