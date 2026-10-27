"""기본은 오프라인 경로 미리보기. --execute만 내부 주행 Action을 요청한다."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import uuid
from farm_navigation.route import RouteGraph
from .configuration import load_profile, destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',required=True)
    parser.add_argument('--environment',required=True)
    parser.add_argument('--mode',choices=['real','sim'],required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--destination')
    target.add_argument('--node',type=int)
    target.add_argument('--xy',nargs=2,type=float)
    parser.add_argument('--yaw',type=float,help='node/xy 목표 방향 rad, 필수')
    parser.add_argument('--start-node',type=int,help='오프라인 계획의 시작 노드')
    parser.add_argument('--execute',action='store_true',help='실제 주행 요청')
    args = parser.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    profile = load_profile(root,args.environment,args.mode)
    graph = RouteGraph(profile['route_graph'])
    if args.destination:
        xy,yaw = destination(profile,graph,args.destination)
    else:
        if args.yaw is None:
            parser.error('--node/--xy에는 --yaw가 필요합니다.')
        xy,yaw = (graph.nodes[args.node] if args.node is not None else tuple(args.xy)),args.yaw
    graph._candidates(xy,profile['navigation'].get('max_goal_distance_m',.02))
    if not args.execute:
        if args.start_node is None:
            parser.error('미리보기에는 --start-node가 필요합니다.')
        plan = graph.plan(graph.nodes[args.start_node],xy)
        print(json.dumps(dict(frame=plan.frame_id,points=plan.points,edge_ids=plan.edge_ids,
            distance_m=plan.distance_m,goal_yaw=yaw,graph_revision=plan.graph_revision),ensure_ascii=False,indent=2,allow_nan=False))
        return
    if args.start_node is not None:
        parser.error('실행은 실제 TF를 사용합니다. --start-node를 제거하세요.')
    from .configuration import require_execution
    require_execution(profile)
    import rclpy
    from rclpy.action import ActionClient
    from farm_interfaces.action import CheckRoute
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('transport_route_client')
    client = ActionClient(node,CheckRoute,'/'+profile['robot_id']+'/internal/check_route')
    handle = None
    future = None
    try:
        if not client.wait_for_server(timeout_sec=5):
            raise RuntimeError('운송 서버가 없습니다.')
        goal = CheckRoute.Goal()
        goal.robot_id,goal.map_id = profile['robot_id'],profile['map_id']
        goal.task_id = 'ROUTE_'+uuid.uuid4().hex
        goal.timestamp = datetime.now(timezone.utc).isoformat()
        goal.goal_pose.frame_id = profile['navigation'].get('map_frame','map')
        goal.goal_pose.position.x,goal.goal_pose.position.y = map(float,xy)
        goal.goal_pose.yaw = float(yaw)
        future = client.send_goal_async(goal,feedback_callback=lambda msg:print(msg.feedback.phase))
        rclpy.spin_until_future_complete(node,future)
        handle = future.result()
        if not handle.accepted:
            raise RuntimeError('Goal 거절. 서버의 준비·설정·좌표 로그를 확인하세요.')
        result = handle.get_result_async()
        rclpy.spin_until_future_complete(node,result)
        print(result.result().result)
    except KeyboardInterrupt:
        if handle is None and future is not None:
            rclpy.spin_until_future_complete(node,future,timeout_sec=5)
            if future.done():
                handle = future.result()
            else:
                print('Goal 접수 여부 미확인: 서버 상태를 확인하고 새 작업을 보내지 마세요.')
        if handle and handle.accepted:
            cancel = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(node,cancel,timeout_sec=5)
            result = handle.get_result_async()
            rclpy.spin_until_future_complete(node,result,timeout_sec=30)
            if not result.done():
                print('종료 결과 미확인: 서버 상태와 실제 정지를 확인하세요.')
    finally:
        client.destroy()
        node.destroy_node()
        rclpy.shutdown()
