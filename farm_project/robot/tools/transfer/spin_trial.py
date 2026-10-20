"""차체 단독 시험. 공통 SpinClient 재사용; 팔/배출/관제 인계는 호출하지 않는다."""
import argparse
import fcntl
import json
import math
from pathlib import Path
import threading
import time
from types import SimpleNamespace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('direction', choices=['left', 'right'])
    parser.add_argument('--reference', type=Path, help='right에 필요한 성공한 left 결과 JSON')
    parser.add_argument('--execute', action='store_true', help='실제 회전 명시 승인')
    args = parser.parse_args()
    if not args.execute:
        parser.error('실제 회전에는 --execute가 필요합니다.')
    reference = None
    if args.direction == 'right':
        if args.reference is None:
            parser.error('right에는 --reference가 필요합니다.')
        reference = json.loads(args.reference.read_text())
        if reference.get('direction') != 'left' or not reference.get('ok'):
            parser.error('정상 종료하고 정지를 확인한 left 기록만 사용할 수 있습니다.')
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import qos_profile_sensor_data
    from nav_msgs.msg import Odometry
    from lifecycle_msgs.srv import GetState
    from rcl_interfaces.srv import GetParameters
    from farm_navigation.spin_client import SpinClient

    # 동일 도구의 중복 실행 방지. 다른 미션과의 배타성은 운영자가 별도로 확보한다.
    lock = open('/tmp/harvest_spin_trial.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    rclpy.init()
    node = rclpy.create_node('harvest_spin_trial')
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    guard = threading.Lock()
    samples = []

    def odom(msg: Odometry) -> None:
        p, q, v = msg.pose.pose.position, msg.pose.pose.orientation, msg.twist.twist
        yaw = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        with guard:
            samples.append(dict(t=time.monotonic(), x=p.x, y=p.y, yaw=yaw,
                                linear=math.hypot(v.linear.x,v.linear.y), angular=abs(v.angular.z)))
    node.create_subscription(Odometry, '/harvest_01/odom', odom, qos_profile_sensor_data)
    spin = SpinClient(node, '/harvest_01/spin', SimpleNamespace(response_timeout_s=5., cancel_timeout_s=5.))
    report = dict(direction=args.direction, ok=False, samples=samples)
    folder = Path('/home/vic/vmany/main/farm_project/runs/transfer_spin')
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / (time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns())+'_'+args.direction+'.json')

    def current() -> dict:
        with guard:
            if not samples or time.monotonic()-samples[-1]['t'] > 1.:
                raise RuntimeError('최신 odom 미수신')
            return dict(samples[-1])

    def stopped() -> dict:
        deadline = time.monotonic()+5.
        since = None
        while time.monotonic() < deadline:
            s = current()
            if s['linear'] <= .005 and s['angular'] <= .01:
                since = since if since is not None else time.monotonic()
                if time.monotonic()-since >= 1.:
                    return s
            else:
                since = None
            time.sleep(.02)
        raise RuntimeError('정지 확인 실패: 1초 연속 linear<=0.005m/s, angular<=0.01rad/s 필요')

    def call(srv_type: object, name: str, request: object) -> object:
        client = node.create_client(srv_type, name)
        try:
            if not client.wait_for_service(timeout_sec=5.):
                raise RuntimeError('서비스 없음: '+name)
            future = client.call_async(request)
            deadline = time.monotonic()+5.
            while not future.done() and time.monotonic() < deadline:
                time.sleep(.02)
            if not future.done():
                raise RuntimeError('서비스 응답 시간 초과: '+name)
            return future.result()
        finally:
            node.destroy_client(client)
    try:
        state = call(GetState, '/harvest_01/behavior_server/get_state', GetState.Request())
        if state.current_state.id != 3:
            raise RuntimeError('behavior_server active 아님')
        names = ['min_rotational_vel', 'max_rotational_vel', 'rotational_acc_lim']
        params = call(GetParameters, '/harvest_01/behavior_server/get_parameters', GetParameters.Request(names=names))
        values = [v.double_value for v in params.values]
        report['behavior_parameters'] = dict(zip(names, values))
        if len(values) != 3 or any(abs(a-b)>1e-8 for a,b in zip(values,[.1,.1,1.])):
            raise RuntimeError('시험 속도 override 미적용: '+str(values))
        deadline = time.monotonic()+5.
        while not spin.ready() and time.monotonic()<deadline:
            time.sleep(.05)
        start = stopped()
        report['start'] = start
        if reference:
            end = reference['end']
            if math.hypot(start['x']-end['x'],start['y']-end['y']) > .05 or abs(math.atan2(math.sin(start['yaw']-end['yaw']),math.cos(start['yaw']-end['yaw']))) > .1:
                raise RuntimeError('left 종료 자세와 다름: 재시작/이동 여부 확인. 복원 요청 없음')
        angle = math.pi/2 if args.direction == 'left' else -math.pi/2
        if reference:
            # 같은 좌회전 기록으로 복원을 반복 요청하지 않는다. 실패 시 현장 확인 필요.
            with args.reference.with_suffix('.restore_requested').open('x') as marker:
                marker.write(str(output)+'\n')
        print('실제 회전 요청:', args.direction, '90도', flush=True)
        spin.execute(angle, 40., lambda: current())
        end = stopped()
        report['end'] = end
        report['delta_yaw_deg'] = math.degrees(math.atan2(math.sin(end['yaw']-start['yaw']),math.cos(end['yaw']-start['yaw'])))
        report['displacement_m'] = math.hypot(end['x']-start['x'],end['y']-start['y'])
        if reference:
            origin = reference['start']
            report['restore_position_error_m'] = math.hypot(end['x']-origin['x'],end['y']-origin['y'])
            report['restore_yaw_error_deg'] = math.degrees(math.atan2(math.sin(end['yaw']-origin['yaw']), math.cos(end['yaw']-origin['yaw'])))
        report['ok'] = True  # Action 성공+정지 확인. 정밀도 합격 판정은 별도.
    except BaseException as error:
        report['error'] = str(error) or type(error).__name__
        try:
            spin.cancel()
            stopped()
            report['cleanup_stopped'] = True
        except BaseException as cleanup:
            report['cleanup_error'] = str(cleanup)
    finally:
        executor.shutdown()
        thread.join(timeout=2.)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=False,indent=2))
        print('기록:', output)
        spin.close()
        node.destroy_node()
        rclpy.shutdown()
        lock.close()
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
