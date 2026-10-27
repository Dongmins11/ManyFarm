"""Removable trial client; reuses CheckRoute and PrecisionMotion servers."""
import argparse
import fcntl
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import uuid


def sequence(mode):
    return [('route', None), ('precision', ('sort_01', 'DOCK'))] if mode == 'dock' else [('precision', ('sort_departure', 'CLEAR'))]


def completed(stage, status, result):
    return status == 4 and ((result.result_code == "SUCCESS" and result.arrived)
                           if stage == "route" else (result.success and result.stopped))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['dock', 'undock'])
    parser.add_argument('--check', action='store_true', help='설정만 검사; Goal 전송 없음')
    parser.add_argument('--project-root', default=str(Path.home() / 'transport_docking_20261013'))
    args = parser.parse_args()
    lock = open(Path.home() / '.sorter-test.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('다른 sorter-test가 실행 중입니다.')
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.signals import SignalHandlerOptions
    from farm_interfaces.action import CheckRoute, PrecisionMotion
    from farm_navigation.route import RouteGraph
    from transport_robot.configuration import load_profile, destination, require_execution
    root = Path(args.project_root)
    profile = load_profile(root, 'robot/config/environments/transport_docking_trial.yaml', 'real')
    require_execution(profile)
    graph = RouteGraph(profile['route_graph'])
    registry = profile['registry']['destinations']['SORT_01']
    if registry['approach_node_id'] != 17:
        raise RuntimeError('SORT_01 접근점이 17번이 아닙니다. 설정을 확인하세요.')
    xy, yaw = destination(profile, graph, 'SORT_01')
    for stage, values in sequence(args.mode):
        if stage == 'precision':
            item = profile['precision_registry']['profiles'][values[0]]
            if not item.get('configured') or values[1] not in item.get('allowed_operations', []):
                raise RuntimeError('시험 프로필/operation 비활성: ' + values[0])
            if item['target_marker_id'] != 40 or item['docking_marker_id'] != 40:
                raise RuntimeError('마커40 설정 불일치')
    if args.check:
        print('설정 검사 통과:', sequence(args.mode), 'node17=', xy, 'yaw=', yaw)
        return
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('sorter_repeat_trial_' + str(os.getpid()), cli_args=['--ros-args', '-r', '/tf:=/transport_01/tf', '-r', '/tf_static:=/transport_01/tf_static'])
    client = handle = pending = None
    observer = None
    try:
        if args.mode == 'dock':
            from farm_docking.route_observer import RouteObserver
            observer = RouteObserver(node, root, profile['precision_registry']['profiles']['sort_01'])
            observer.enable(True)
        for stage, values in sequence(args.mode):
            if stage == 'route':
                action, endpoint = CheckRoute, 'internal/check_route'
                goal = action.Goal()
                goal.robot_id, goal.map_id = profile['robot_id'], profile['map_id']
                goal.task_id = 'SORT_TRIAL_' + uuid.uuid4().hex
                goal.timestamp = datetime.now(timezone.utc).isoformat()
                goal.goal_pose.frame_id = 'map'
                goal.goal_pose.position.x, goal.goal_pose.position.y = map(float, xy)
                goal.goal_pose.yaw = float(yaw)
            else:
                action, endpoint = PrecisionMotion, 'precision_motion'
                goal = action.Goal()
                goal.session_id = 'SORT_TRIAL_' + uuid.uuid4().hex
                goal.profile_id, goal.operation = values
                goal.target_marker_id = goal.docking_marker_id = 40
            handle = pending = None
            client = ActionClient(node, action, '/' + profile['robot_id'] + '/' + endpoint)
            if not client.wait_for_server(timeout_sec=5):
                raise RuntimeError(endpoint + ' 서버가 없습니다.')
            print('START:', endpoint, values or ('node17', xy, yaw), flush=True)
            pending = client.send_goal_async(goal, feedback_callback=lambda m: print(m.feedback, flush=True))
            rclpy.spin_until_future_complete(node, pending)
            handle = pending.result()
            if not handle.accepted:
                raise RuntimeError('Goal 거절: ' + endpoint)
            result = handle.get_result_async()
            transfer = False
            cancel = None
            deadline = None
            while not result.done():
                rclpy.spin_once(node, timeout_sec=0.05)
                if stage == 'route':observer.status()
                if stage == 'route' and observer.ready() and cancel is None and not result.done():
                    print('마커 목표 확보: 경로 취소 후 정지 확인', flush=True)
                    cancel = handle.cancel_goal_async()
                    deadline = time.monotonic() + 30.
                if deadline is not None and time.monotonic() > deadline:
                    raise RuntimeError('경로 취소 완료 미확인. 도킹을 시작하지 않습니다.')
            reply = result.result()
            if cancel is not None:
                rclpy.spin_until_future_complete(node, cancel, timeout_sec=5)
                transfer = bool(cancel.done() and cancel.result().goals_canceling and
                                reply.status == 5 and reply.result.result_code == 'CANCELED')
            print(reply.result, flush=True)
            ok = completed(stage, reply.status, reply.result) or transfer
            if not ok:
                raise RuntimeError(endpoint + ' 실패. 다음 단계는 실행하지 않습니다.')
            if stage == 'route':
                deadline = time.monotonic() + 5.
                while not observer.stopped():
                    if time.monotonic() > deadline:
                        raise RuntimeError('로봇 정지 확인 실패. 도킹을 시작하지 않습니다.')
                    rclpy.spin_once(node, timeout_sec=0.05)
            client.destroy()
            client = handle = pending = None
        print('완료: ' + args.mode, flush=True)
    except KeyboardInterrupt:
        if handle is None and pending is not None:
            rclpy.spin_until_future_complete(node, pending, timeout_sec=5)
            if pending.done():
                handle = pending.result()
        if handle is not None and handle.accepted:
            cancel = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(node, cancel, timeout_sec=5)
            result = handle.get_result_async()
            rclpy.spin_until_future_complete(node, result, timeout_sec=30)
            print('취소 결과:', result.result() if result.done() else '정지 결과 미확인. 서버를 확인하세요.')
        else:
            print('접수/정지 상태를 서버에서 확인하세요.')
        raise SystemExit(130)
    finally:
        if observer is not None:
            try:
                observer.enable(False)
            except Exception as exc:
                print('관측 종료 확인:', exc, flush=True)
        if client is not None:
            client.destroy()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
