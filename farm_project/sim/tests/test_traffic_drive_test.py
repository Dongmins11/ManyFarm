"""실제 ROS 타입과 공통 소유권을 사용한 시험 서버 경계 검사. 물리 주행은 아니다."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import threading
import unittest
import numpy as np
from rclpy.action import GoalResponse, CancelResponse
from farm_interfaces.action import NavigateToNode
from farm_interfaces.msg import TrafficControlState, TrafficRegistration
from farm_common.action_handoff import ActionHandoff
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from farm_sim_runtime.traffic_drive_test import TrafficDriveTest


class DriveTests(unittest.TestCase):
    def setUp(self):
        regs = [TrafficRegistration(robot_id=r, boot_id='b', sync_id='s',
                    registration_state='REGISTERED', accepted_status_sequence=1)
                for r in ('scout_01', 'harvest_01')]
        self.traffic = NS(lock=threading.RLock(), ready=True, moving=False,
            control=TrafficControlState(phase='READY', robots=regs),
            registry=NS(nodes={'9004': 9004}, graph=NS(nodes={9004:(1., 0.)})),
            settings=NavigationSettings(), begin_task=Mock(), check_work=Mock(), finish_task=Mock(), wait_position_report=Mock())
        self.node = NS(_traffic=self.traffic, create_timer=Mock(), destroy_timer=Mock(), get_logger=Mock())
        self.block = Mock()
        self.handoff = ActionHandoff()
        self.nav = Mock()
        self.nav.navigate.return_value = NS(stamp_ns=1, measurement={'accepted':True})
        self.nav.plan.return_value = RoutePlan('p', 'r', 'map', ((0., 0.),(1., 0.)), ('e',), 1.)
        with patch('farm_sim_runtime.traffic_drive_test.ActionServer'), patch(
                'farm_sim_runtime.traffic_drive_test.Navigator', return_value=self.nav):
            self.server = TrafficDriveTest(self.node, {'mode':'sim','map_id':'farm_map_v1'},
                NavigationSettings(), Mock(), NS(current=lambda _:np.eye(4)), Mock(), self.handoff,
                unavailable=lambda:False, block=self.block, record=lambda _:None)
        self.ok = patch('farm_sim_runtime.traffic_drive_test.rclpy.ok', return_value=True)
        self.ok.start(); self.addCleanup(self.ok.stop)
        self.goal = NS(request=NavigateToNode.Goal(task_id='test_1',map_id='farm_map_v1',target_node_id='9004'),
            is_cancel_requested=False, is_active=True, publish_feedback=Mock(), succeed=Mock(),
            abort=Mock(), canceled=Mock())

    def accept(self):
        self.assertEqual(self.server.accept(self.goal.request), GoalResponse.ACCEPT)

    def test_ready_both_robots_required(self):
        self.traffic.control.robots.pop()
        self.assertEqual(self.server.accept(self.goal.request), GoalResponse.REJECT)
        self.assertFalse(self.handoff.busy)

    def test_same_work_lock_blocks_both_directions(self):
        self.handoff.reserve('work', 'normal')
        self.assertEqual(self.server.accept(self.goal.request), GoalResponse.REJECT)
        self.handoff.release('work', 'normal')
        self.accept()
        self.assertFalse(self.handoff.reserve('return', 'station'))
        self.assertFalse(self.handoff.reserve('work', 'normal'))

    def test_success_and_task_id_retained_during_navigation(self):
        self.accept()
        def navigate(*a, **k):
            self.assertEqual(self.handoff.current, ('traffic_test','test_1'))
            return NS(stamp_ns=1, measurement={'accepted':True})
        self.nav.navigate.side_effect = navigate
        result = self.server.execute(self.goal)
        self.assertEqual((result.result_code,result.error_code), ('SUCCESS','NONE'))
        self.goal.succeed.assert_called_once()
        self.traffic.finish_task.assert_called_once_with('test_1', 10.)
        self.assertFalse(self.handoff.busy)

    def test_cancel_cleans_before_terminal(self):
        self.accept()
        self.assertEqual(self.server.cancel(self.goal), CancelResponse.ACCEPT)
        self.goal.canceled.side_effect = lambda:self.traffic.finish_task.assert_called_once()
        result = self.server.execute(self.goal)
        self.assertEqual(result.result_code, 'CANCELED')
        self.nav.cancel_nav.assert_called_once()
        self.goal.canceled.assert_called_once()
        self.nav.navigate.assert_not_called()

    def test_cancel_cleanup_failure_aborts_and_blocks(self):
        self.accept(); self.server.cancel(self.goal)
        self.nav.cancel_nav.side_effect = RuntimeError('goal unresolved')
        result = self.server.execute(self.goal)
        self.assertEqual((result.result_code,result.error_code), ('FAILED','CANCEL_UNCONFIRMED'))
        self.goal.abort.assert_called_once(); self.block.assert_called_once()
        self.goal.canceled.assert_not_called()

    def test_move_failure_aborts_and_retains_error(self):
        self.accept(); self.nav.navigate.side_effect = RuntimeError('105')
        result = self.server.execute(self.goal)
        self.assertEqual(result.result_code,'FAILED')
        self.assertIn('105', result.error_message)
        self.goal.abort.assert_called_once()

    def test_feedback_only_marks_moving_after_grant(self):
        self.server.goal = self.goal; self.server.phase='PLANNING'
        self.server.feedback(); self.goal.publish_feedback.assert_not_called()
        self.traffic.moving=True; self.server.feedback()
        self.assertEqual(self.goal.publish_feedback.call_args.args[0].phase,'MOVING')

class DetourGeometryTests(unittest.TestCase):
    def test_actual_graph_uses_full_47_5m_detour_and_reserves_exits(self):
        from farm_navigation.route import RouteGraph
        from farm_navigation.traffic_contract import TrafficRegistry
        root = Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_config'
        registry = root/'config/traffic/traffic_zones.yaml'
        scout = TrafficRegistry(registry, RouteGraph(root/'maps/graph.geojson'), 'scout_01')
        harvest = TrafficRegistry(registry, RouteGraph(root/'maps/harvest_graph.geojson'), 'harvest_01')
        x, y = scout.graph.nodes[9004]
        occupied = scout.occupied(x, y, 0.)
        def overlaps(a, b):
            return a[0]<=b[2] and b[0]<=a[2] and a[1]<=b[3] and b[1]<=a[3]
        # 관제 계약의 보수적 구역 겹침으로 시험용 차단 입력을 만든다. 운영 권한 판단은 하지 않는다.
        blocked = {z for z,data in harvest.zones.items() if any(
            overlaps(data['bounds_m'], harvest.zones[o]['bounds_m']) for o in occupied)}
        mapping = harvest.data['graph_mappings'][harvest.graph_id]
        nodes = tuple(n for n,z in mapping['node_to_zone'].items() if z in blocked)
        edges = tuple(e for e,z in mapping['edge_to_zone'].items() if z in blocked)
        self.assertIn('9004', nodes)
        graph = harvest.graph
        plan = graph.plan(graph.nodes[9010], graph.nodes[10103],
            blocked_nodes=frozenset(nodes), blocked_edges=harvest.blocked_work_edges(nodes, edges))
        self.assertAlmostEqual(plan.distance_m, 47.5)
        route = harvest.route(list(plan.points), .1)
        self.assertEqual((route.nodes[0], route.nodes[-1]), ('9010','10103'))
        self.assertIn('9053', route.nodes)
        self.assertFalse(set(route.nodes)&set(nodes))
        self.assertFalse(set(route.edges)&set(edges))
        resources = {mapping['node_to_zone'][n] for n in route.nodes}
        resources.update(mapping['edge_to_zone'][e] for e in route.edges)
        resources.update(route.hold)
        self.assertFalse(resources & blocked)
