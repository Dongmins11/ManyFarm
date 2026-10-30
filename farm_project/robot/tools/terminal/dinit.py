"""사용자가 실제 배치한 시험 자세를 AMCL에 지정한다. 주행·복귀 명령은 보내지 않는다."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time


def target(root: Path, config: dict) -> tuple[float, float, float]:
    """실물 그래프에서 목표 좌표(m)와 기준 노드를 등지는 차체 방향(rad)을 계산한다."""
    features = json.loads((root/config['route_graph']).read_text())['features']
    nodes = {f['properties']['id']: f['geometry']['coordinates']
             for f in features if f['geometry']['type'] == 'Point'}
    x, y = nodes[config['node_id']][:2]
    bx, by = nodes[config['face_away_from_node_id']][:2]
    if not all(math.isfinite(v) for v in (x, y, bx, by)) or (x, y) == (bx, by):
        raise ValueError('초기위치와 방향 기준 노드가 유효하지 않습니다.')
    return x, y, math.atan2(y-by, x-bx)


def main() -> None:
    """--check는 ROS 연결 없이 계산만 한다. 실제 발행은 기존 vinit의 IDLE·정지 기준을 따른다."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--config', type=Path, default=Path(__file__).with_suffix('.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    x, y, yaw = target(args.project_root, config)
    print(f"초기 추정: node={config['node_id']}, x={x:.6f}, y={y:.6f}, yaw={math.degrees(yaw):.2f}도", flush=True)
    if args.check:
        return
    print('로봇이 위 실제 위치·방향에 정지해 있을 때만 사용하는 시험 초기위치입니다.', flush=True)
    import rclpy
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry
    from farm_interfaces.msg import RobotStatus
    from lifecycle_msgs.srv import GetState
    from rclpy.qos import qos_profile_sensor_data
    rclpy.init()
    node = rclpy.create_node('dinit_initialpose')
    prefix = '/'+config['robot_id']
    odom, status = [], []
    try:
        node.create_subscription(Odometry, prefix+'/odom',
            lambda m: odom.append((time.monotonic(), m)), qos_profile_sensor_data)
        node.create_subscription(RobotStatus, prefix+'/status',
            lambda m: status.append((time.monotonic(), m)), 10)
        client = node.create_client(GetState, prefix+'/amcl/get_state')
        if not client.wait_for_service(timeout_sec=15):
            raise RuntimeError('AMCL 서비스 연결 안 됨')
        future = client.call_async(GetState.Request())
        rclpy.spin_until_future_complete(node, future, timeout_sec=10)
        if not future.done() or future.result().current_state.id != 3:
            raise RuntimeError('AMCL active 상태 아님')
        publisher = node.create_publisher(PoseWithCovarianceStamped, prefix+'/initialpose', 10)
        deadline = time.monotonic()+10
        while publisher.get_subscription_count() == 0 and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
        if not publisher.get_subscription_count():
            raise RuntimeError('initialpose 구독자 없음')
        # 기존 vinit과 동일한 확인을 발행 직전에 수행한다. ready는 위치 초기화 전 요구하지 않는다.
        deadline = time.monotonic()+2
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
        now = time.monotonic()
        recent = [m for t, m in odom if now-t < 1]
        safe = (len(recent) >= 10 and status and now-status[-1][0] < 2
                and status[-1][1].state == 'IDLE' and not status[-1][1].current_task_id
                and all(abs(m.twist.twist.linear.x)+abs(m.twist.twist.angular.z) < 1e-6 for m in recent))
        if not safe:
            raise RuntimeError('정지/IDLE 미확인: 초기위치 발행 안 함')
        message = PoseWithCovarianceStamped()
        message.header.frame_id = config['frame_id']
        message.header.stamp = node.get_clock().now().to_msg()
        message.pose.pose.position.x, message.pose.pose.position.y = x, y
        message.pose.pose.orientation.z = math.sin(yaw/2)
        message.pose.pose.orientation.w = math.cos(yaw/2)
        message.pose.covariance[0] = message.pose.covariance[7] = config['position_stddev_m']**2
        message.pose.covariance[35] = math.radians(config['yaw_stddev_deg'])**2
        publisher.publish(message)
        deadline = time.monotonic()+1
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
        print('초기 추정 1회 발행 완료. AMCL 위치 수렴이나 주행 성공을 의미하지 않습니다.')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
