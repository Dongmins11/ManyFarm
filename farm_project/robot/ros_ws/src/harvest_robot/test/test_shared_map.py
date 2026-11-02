"""공용 지도 정합·전체 연결성과 14번 시험 목표를 오프라인 검사한다."""
from pathlib import Path
import hashlib
import importlib.util
import math
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_navigation'))
from farm_navigation.route import RouteGraph


class SharedMap(unittest.TestCase):
    def test_role_paths_and_preserved_harvest_hashes(self) -> None:
        scout = yaml.safe_load((ROOT / 'robot/config/environments/scout_real.yaml').read_text())
        harvest = yaml.safe_load((ROOT / 'robot/config/environments/harvest_real.yaml').read_text())
        self.assertEqual(harvest['map_id'], 'many_farm_v1')
        self.assertEqual(harvest['route_graph'], 'robot/config/maps/many_farm/graph.geojson')
        self.assertEqual(scout['map_id'], 'farm_map_v1')
        self.assertEqual(scout['route_graph'], 'robot/config/maps/scout_real/graph.geojson')
        expected = {
            'graph.geojson': 'fc72ffb617c0f756a6eb58477c0e1211dbc3f4cea2ca9855874008b150cfc504',
            'many_farm.yaml': 'bbe46086336b76b5f11611160803260a91339d87c97709a6ffe5114d8d328fac',
            'many_farm.pgm': 'a9f852637490aaff50c7115a543e2780a60ecf654747b3e777319251e151949e',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / 'robot/config/maps/many_farm' / name).read_bytes()).hexdigest(), digest)

    def test_all_node_pairs_and_edge_midpoints(self) -> None:
        graph = RouteGraph(ROOT / 'robot/config/maps/many_farm/graph.geojson')
        self.assertEqual(len(graph.nodes), 21)
        self.assertEqual(len(graph.edges), 46)
        for a in graph.nodes.values():
            for b in graph.nodes.values():
                plan = graph.plan(a, b)
                self.assertEqual(plan.points[0], a)
                self.assertEqual(plan.points[-1], b)
        # 모든 방향 엣지의 중간 지점에서 진입점과 14번으로 연결 가능하다.
        for edge in graph.edges:
            a, b = graph.nodes[edge.start], graph.nodes[edge.end]
            middle = tuple((x+y)/2 for x,y in zip(a,b))
            for goal in (11, 14):
                self.assertEqual(graph.plan(middle, graph.nodes[goal]).points[-1], graph.nodes[goal])

    def test_generated_goal_uses_live_graph_and_ids(self) -> None:
        path = ROOT / 'robot/tools/tag_camera/harvest_graph_goal.py'
        spec = importlib.util.spec_from_file_location('shared_graph_goal', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        goal = module.build_goal(ROOT)
        self.assertEqual(goal['map_id'], 'many_farm_v1')
        pose = goal['harvest_task']['goal_pose']
        self.assertAlmostEqual(pose['position']['x'], 1.188)
        self.assertAlmostEqual(pose['position']['y'], -4.02)
        self.assertAlmostEqual(pose['yaw'], -math.pi/2)
        with self.assertRaises(ValueError):
            module.build_goal(ROOT, heading_from=0)


if __name__ == '__main__':
    unittest.main()
