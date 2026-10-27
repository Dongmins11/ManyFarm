"""격리 namespace의 DDS 운송 Action 시험. 대역 주행이며 cmd_vel을 발행하지 않는다."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace as NS

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from farm_interfaces.action import ReturnToStation
from transport_robot.docking_port import UnavailableDocking
from transport_robot.device_port import UnavailableDevice
from transport_robot.mission_types import utc
from transport_robot.transport_mission import TransportMission
from transport_robot.transport_state_controller import TransportStateController
from transport_robot.transport_communication import TransportCommunication


def main() -> None:
    if (os.environ.get('ROS_DOMAIN_ID') != '13'
            or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE') != 'SUBNET'):
        raise RuntimeError('시험은 ROS_DOMAIN_ID=13 / SUBNET에서 실행하세요.')
    rclpy.init()
    node = Node('transport_contract_probe', namespace=f'transport_contract_probe_{os.getpid()}')
    temporary = tempfile.TemporaryDirectory(prefix='transport_contract_')
    node.callbacks = ReentrantCallbackGroup()
    node.stopping = False
    node.profile = dict(robot_id=node.get_namespace()[1:], map_id='probe_map',
        mode='sim', station_return_mode='navigation_only', registry={'destinations':{
            'PROBE_STATION':dict(configured=True, approach_node_id=1, approach_yaw_rad=0.)}})
    node.graph = NS(nodes={1:(0.,0.)})
    node.docking, node.device = UnavailableDocking(), UnavailableDevice()
    node.mission = TransportMission(Path(temporary.name)/'journal.json')
    scenario, started = ['success'], threading.Event()

    def navigate(*unused) -> None:
        started.set()
        if scenario[0] == 'failure':
            raise RuntimeError('probe FollowPath 105')
        if scenario[0] == 'cancel':
            deadline = time.monotonic()+10.
            while time.monotonic() < deadline:
                node.controller.check()
                time.sleep(.01)
            raise TimeoutError('probe cancel was not received')

    node.navigator = NS(preflight_navigation=lambda: None, navigate=navigate, cancel_nav=lambda: None)
    node.controller = TransportStateController(node.navigator, node.mission, node.docking, node.device)
    node.controller.station_return_mode = 'navigation_only'
    node.route_ready = lambda: True
    node.communication = TransportCommunication(node)
    timer = node.create_timer(.01, node.communication.update,
                              callback_group=MutuallyExclusiveCallbackGroup())
    client = ActionClient(node, ReturnToStation, 'return_to_station')
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()

    def wait(future, seconds=10.):
        deadline = time.monotonic()+seconds
        while not future.done() and time.monotonic() < deadline:
            time.sleep(.01)
        if not future.done():
            raise TimeoutError('DDS Future timeout')
        return future.result()

    cases = []
    try:
        assert client.wait_for_server(timeout_sec=10.)
        for name, status, result_code in [('success',4,'SUCCESS'), ('failure',6,'FAILED'), ('cancel',5,'CANCELED')]:
            scenario[0] = name
            started.clear()
            goal = ReturnToStation.Goal(robot_id=node.profile['robot_id'], task_id='probe_'+name,
                station_id='PROBE_STATION', map_id='probe_map', timestamp=utc())
            handle = wait(client.send_goal_async(goal))
            assert handle.accepted
            if name == 'cancel':
                assert started.wait(5.)
                assert wait(handle.cancel_goal_async()).goals_canceling
            reply = wait(handle.get_result_async())
            assert reply.status == status and reply.result.result_code == result_code
            assert reply.result.docked == (name == 'success')
            again = wait(handle.get_result_async())
            assert again.status == status and again.result.result_code == result_code
            duplicate = wait(client.send_goal_async(goal))
            assert not duplicate.accepted
            cases.append(dict(scenario=name, status=reply.status, result_code=reply.result.result_code,
                docked=reply.result.docked, same_uuid_query='PASS', duplicate_task_rejected=True))
        print(json.dumps(dict(result='PASS', scope='DDS Action / simulated navigation double / no physical motion',
            domain=13, discovery='SUBNET', namespace=node.get_namespace(), cases=cases), ensure_ascii=False))
    finally:
        node.controller.cancel()
        deadline = time.monotonic()+12.
        while node.controller.busy and time.monotonic() < deadline:
            time.sleep(.02)
        client.destroy()
        node.controller.close()
        executor.shutdown()
        thread.join(5.)
        node.communication.close()
        node.destroy_timer(timer)
        node.destroy_node()
        rclpy.try_shutdown()
        temporary.cleanup()


if __name__ == '__main__':
    main()
