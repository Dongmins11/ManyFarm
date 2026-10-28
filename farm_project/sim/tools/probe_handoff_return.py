"""인계 후 실제 복귀/선별장 정밀주행을 검증한다. 하역 성공이나 수량을 생성하지 않는다."""
import json
from pathlib import Path
from uuid import uuid4

from rclpy.action import ActionClient
from rosidl_runtime_py.convert import message_to_ordereddict
from farm_interfaces.action import CheckRoute, PrecisionMotion, ReturnToStation
from farm_navigation.route import RouteGraph
from transport_robot.configuration import load_profile, destination
from transport_robot.mission_types import utc

ROOT = Path(__file__).resolve().parents[2]


def run(base: Path,node,wait,future,record,result: dict) -> None:
    """기존 Action으로 순차 시험한다. 선별장 정밀 Action은 내부 계약의 분리 검증이다."""
    handles = []
    def action(name: str,kind,endpoint: str,goal,timeout: float) -> dict:
        client = ActionClient(node,kind,endpoint)
        try:
            wait(client.server_is_ready,30,name+' 서버')
            record(name+'_goal',goal=dict(message_to_ordereddict(goal)))
            handle = future(client.send_goal_async(goal,feedback_callback=lambda msg:
                record(name+'_feedback',data=dict(message_to_ordereddict(msg.feedback)))),15,name+' 접수')
            if not handle.accepted:raise RuntimeError(name+' Goal 거절')
            ticket = handle.get_result_async();handles.append((handle,ticket))
            reply = future(ticket,timeout,name+' 결과 (시험 watchdog)')
            data = dict(status=reply.status,result=dict(message_to_ordereddict(reply.result)))
            result[name]=data;record(name+'_result',**data)
            if reply.status!=4 or data['result'].get('result_code','SUCCESS')!='SUCCESS' or data['result'].get('success',True) is not True:
                raise RuntimeError(name+' 실패: '+json.dumps(data,ensure_ascii=False))
            return data
        finally:
            for handle,ticket in handles:
                if not ticket.done():
                    future(handle.cancel_goal_async(),10,name+' 취소')
                    future(ticket,30,name+' 정지 결과')
            client.destroy()

    # CLEAR는 바구니 사이 이격이지 통로 전체 비움이 아니다. 앞쪽 운송로봇을
    # 먼저 내보낸 뒤 수확로봇이 후진 복귀한다. 교통 미연결 시험의 순차 실행이다.
    profile = load_profile(ROOT,str(base/'runtime/transport_runtime.json'),'sim')
    graph = RouteGraph(profile['route_graph']);xy,yaw = destination(profile,graph,'SORT_01')
    goal = CheckRoute.Goal(robot_id='transport_01',task_id='sorter_'+uuid4().hex[:12],
        map_id='farm_map_v1',timestamp=utc())
    goal.goal_pose.frame_id='map';goal.goal_pose.position.x=xy[0];goal.goal_pose.position.y=xy[1];goal.goal_pose.yaw=yaw
    action('sorter_route',CheckRoute,'/transport_01/internal/check_route',goal,600)
    session='sorter_'+uuid4().hex[:12]
    for name,profile_id,operation in [('sorter_dock','sort_01_distance_trial','DOCK'),
                                      ('sorter_clear','sort_departure_distance_trial','CLEAR')]:
        goal = PrecisionMotion.Goal(session_id=session,profile_id=profile_id,operation=operation,
                                    target_marker_id=40,docking_marker_id=40)
        goal.clearance_pose.frame_id='map';goal.clearance_pose.position.x=xy[0]
        goal.clearance_pose.position.y=xy[1];goal.clearance_pose.yaw=yaw
        data=action(name,PrecisionMotion,'/transport_01/precision_motion',goal,180)
        if data['result']['stopped'] is not True:raise RuntimeError(name+' 정지 미확인')
    goal = ReturnToStation.Goal(robot_id='transport_01',task_id='return_'+uuid4().hex[:12],
        station_id='STATION_TRANSPORT_01',map_id='farm_map_v1',timestamp=utc())
    action('transport_return',ReturnToStation,'/transport_01/return_to_station',goal,600)
    goal = ReturnToStation.Goal(robot_id='harvest_01',task_id='return_'+uuid4().hex[:12],
        station_id='STATION_HARVEST_01',map_id='farm_map_v1',timestamp=utc())
    action('harvest_return',ReturnToStation,'/harvest_01/return_to_station',goal,600)
