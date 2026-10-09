"""수확 진입 제어기 격리와 실제 공통 Action 전달·준비 검사 회귀 검증."""
from dataclasses import asdict
import unittest
from unittest.mock import patch
from test_follow_work import ROOT, Parameters, construct, request, HarvestMission, read_mapping


class EntryController(unittest.TestCase):
    def test_entry_and_work_select_different_controllers(self) -> None:
        node = construct()
        HarvestMission(node, request()).run()
        self.assertEqual([g.controller_id for _, g in node.sent], ['HarvestApproach', 'RPP'])
        for _, goal in node.sent:
            self.assertEqual(goal.goal_checker_id, 'general_goal_checker')
            self.assertEqual(goal.progress_checker_id, 'progress_checker')
        entry = asdict(node.client._settings)
        work = asdict(node.work_client._settings)
        self.assertEqual({k for k in entry if entry[k] != work[k]}, {'controller_id'})

    def test_exit_and_same_section_keep_work_controller(self) -> None:
        node = construct()
        HarvestMission(node, request((1.188, -2.3))).run()
        HarvestMission(node, request((1.188, -2.7))).run()
        self.assertEqual(node.sent[-1][1].controller_id, 'RPP')
        node.staged_navigation.sections['SECOND'] = node.staged_navigation.sections['SEC_01']
        node.config['sections']['SECOND'] = node.config['sections']['SEC_01']
        HarvestMission(node, request((1.188, -3.0), 'SECOND')).run()
        self.assertEqual([g.controller_id for _, g in node.sent[-3:]],
                         ['RPP', 'HarvestApproach', 'RPP'])

    def test_absent_option_preserves_legacy_controller(self) -> None:
        node = construct(config_overrides={'approach_controller_id': None})
        HarvestMission(node, request()).run()
        self.assertEqual([g.controller_id for _, g in node.sent], ['RPP', 'RPP'])

    def test_graph_only_ignores_entry_option(self) -> None:
        node = construct('graph_only')
        HarvestMission(node, request()).run()
        self.assertEqual([g.controller_id for _, g in node.sent], ['RPP'])

    def test_route_server_approach_also_selects_entry_controller(self) -> None:
        node = construct(approach='route_server')
        HarvestMission(node, request()).run()
        self.assertEqual(len(node.route_planner.calls), 1)
        self.assertEqual([g.controller_id for _, g in node.sent], ['HarvestApproach', 'RPP'])

    def test_missing_installed_plugin_fails_before_motion(self) -> None:
        with patch.object(Parameters, 'controllers', ('RPP',)):
            node = construct()
            with self.assertRaises(RuntimeError):
                HarvestMission(node, request()).run()
            self.assertEqual(node.sent, [])

    def test_invalid_option_fails_at_construction(self) -> None:
        for value in ('', ' ', 1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                construct(config_overrides={'approach_controller_id': value})

    def test_profile_changes_only_curvature_reference(self) -> None:
        data = read_mapping(ROOT/'robot/config/robots/vicpinky/nav2.yaml')
        params = data['controller_server']['ros__parameters']
        self.assertIn('HarvestApproach', params['controller_plugins'])
        expected = dict(params['RPP'], use_fixed_curvature_lookahead=True,
                        curvature_lookahead_dist=0.4, interpolate_curvature_after_goal=True)
        self.assertEqual(params['HarvestApproach'], expected)
        self.assertTrue(expected['use_collision_detection'])
        checker = params['general_goal_checker']
        self.assertEqual(checker['xy_goal_tolerance'], .04)
        self.assertAlmostEqual(checker['yaw_goal_tolerance'], .04363323129985824)


if __name__ == '__main__':
    unittest.main()
