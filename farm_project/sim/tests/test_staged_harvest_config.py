"""16개 시뮬 구역이 실제 공통 단계별 주행/관제 pose 계약으로 선택되는지 검사한다."""
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
import yaml
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for package in ('harvest_robot', 'farm_navigation'):
    sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
sys.path.insert(0, str(ROOT / 'sim/tools'))
from farm_navigation.route import RouteGraph
from farm_navigation.configuration import load_environment
from harvest_robot.configuration import load_harvest_config
from harvest_robot.contract import resolve_section
from harvest_robot.corridor_navigation import load_corridors, CorridorNavigator, contains
from farm_navigation.navigation_types import NavigationSettings
from harvest_robot.staged_navigation import load_sections
from rebuild_route_data import build


class StagedConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = ROOT / 'sim/ros_ws/src/farm_sim_config/config'
        cls.task = load_harvest_config(config / 'harvest_task.json', ROOT)
        cls.environment = load_environment(config / 'harvest_runtime.yaml', ROOT, 'sim', require_survey=False)
        cls.graph = RouteGraph(str(ROOT / cls.environment['route_graph']))
        cls.corridors = load_corridors(cls.task, cls.graph)

    def test_all_sections_select_from_goal_geometry_and_keep_arm(self) -> None:
        self.assertEqual(self.task['completion_policy'], 'ARRIVAL_THEN_ARM')
        self.assertEqual(self.task['movement_mode'], 'route_then_follow')
        self.assertFalse(self.environment['navigation'].get('parallel_approach', False))
        sections = load_sections(self.task, self.graph)
        self.assertEqual(len(sections), 16)
        for section, corridor in self.corridors.items():
            for fraction in (.1, .5, .9):
                a, b = corridor['entry'], corridor['exit']
                pose = NS(position=NS(x=a[0]+fraction*(b[0]-a[0]), y=a[1]+fraction*(b[1]-a[1])), yaw=corridor['yaw'])
                self.assertEqual(resolve_section(None, self.task, pose, corridors=self.corridors), section)
                pose.yaw += math.pi
                with self.assertRaises(ValueError):
                    resolve_section(None, self.task, pose, corridors=self.corridors)
            self.assertAlmostEqual(math.remainder(sections[section].exit_yaw-corridor['yaw'], 2*math.pi), 0.)

    def test_invalid_or_ambiguous_goal_is_rejected(self) -> None:
        pose = NS(position=NS(x=100., y=100.), yaw=0.)
        with self.assertRaises(ValueError):
            resolve_section(None, self.task, pose, corridors=self.corridors)
        corridor = self.corridors['SEC01']
        pose = NS(position=NS(x=corridor['entry'][0], y=corridor['entry'][1]), yaw=corridor['yaw'])
        with self.assertRaises(ValueError):
            resolve_section(None, self.task, pose, corridors=dict(self.corridors, duplicate=corridor))

    def navigator(self, corridor: dict, xy: tuple, yaw: float) -> CorridorNavigator:
        pose = np.eye(4)
        pose[:2,:2] = [[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]]
        pose[:2,3] = xy
        settings = NavigationSettings.from_mapping(self.environment['navigation'])
        return CorridorNavigator(None, settings, None, NS(current=lambda _:pose), None,
            lambda:None, self.graph, corridors={'SEC01':corridor})

    def test_entry_is_inside_existing_connected_straight_corridor(self) -> None:
        for section, corridor in self.corridors.items():
            with self.subTest(section=section):
                ids = self.task['sections'][section]
                entry = self.graph.nodes[ids['entry_node']]
                self.assertGreater(math.dist(entry,corridor['entry']),.02)
                self.assertTrue(contains(corridor,entry,1e-8))
                direction = np.array([math.cos(corridor['yaw']),math.sin(corridor['yaw'])])
                xy = tuple(np.asarray(entry)-.01*direction)
                self.assertTrue(contains(corridor,xy,.02))
                goal = tuple(np.asarray(entry)+.5*direction)
                self.assertEqual(self.navigator(corridor,xy,corridor['yaw']).plan(goal).points[0],xy)

    def test_reported_arrivals_pass_original_navigation_with_new_sim_definition(self) -> None:
        corridor = self.corridors['SEC01']
        previous = dict(corridor,entry=self.graph.nodes[self.task['sections']['SEC01']['entry_node']])
        for xy,yaw in [((-6.017673561045134,10.710188125977503),-1.5699956492595593),
                       ((-6.021030022223122,10.70598499663028),-1.5821068099414715)]:
            with self.subTest(xy=xy):
                with self.assertRaisesRegex(RuntimeError,'WORK_CORRIDOR_INVALID'):
                    self.navigator(previous,xy,yaw).plan((-6.015,7.7578))
                self.assertEqual(self.navigator(corridor,xy,yaw).plan((-6.015,7.7578)).points[0],xy)

    def test_lateral_heading_forward_and_outer_boundary_checks_remain(self) -> None:
        corridor = self.corridors['SEC01']
        entry = self.graph.nodes[self.task['sections']['SEC01']['entry_node']]
        goal = (entry[0],entry[1]-.5)
        for xy,yaw in [((entry[0]+.06,entry[1]),corridor['yaw']),
                       (entry,corridor['yaw']+.06)]:
            with self.subTest(xy=xy,yaw=yaw), self.assertRaisesRegex(RuntimeError,'APPROACH_RECOVERY_REQUIRED'):
                self.navigator(corridor,xy,yaw).plan(goal)
        with self.assertRaisesRegex(RuntimeError,'WORK_TARGET_NOT_AHEAD'):
            self.navigator(corridor,(entry[0],entry[1]-1.),corridor['yaw']).plan(goal)
        before = (corridor['entry'][0],corridor['entry'][1]+.01)
        with self.assertRaisesRegex(RuntimeError,'WORK_CORRIDOR_INVALID'):
            self.navigator(corridor,before,corridor['yaw']).plan(goal)

    def test_generated_task_matches_checked_in_config(self) -> None:
        original = json.loads((ROOT / 'sim/ros_ws/src/farm_sim_config/config/harvest_task.json').read_text())
        self.assertEqual(build()['config/harvest_task.json'], original)


if __name__ == '__main__':
    unittest.main()
