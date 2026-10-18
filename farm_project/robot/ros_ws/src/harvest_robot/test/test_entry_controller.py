"""수확 진입 제어기 격리와 실제 공통 Action 전달·준비 검사 회귀 검증."""
from dataclasses import asdict
import unittest
from unittest.mock import patch
from test_follow_work import ROOT, Parameters, construct, request, HarvestMission, read_mapping
from farm_navigation.configuration import load_nav2_parameters


class EntryController(unittest.TestCase):
    def test_entry_and_work_select_different_controllers(self) -> None:
        node = construct()
        HarvestMission(node, request()).run()
        self.assertEqual([g.controller_id for _, g in node.sent], ['HarvestApproach', 'HarvestWork'])
        self.assertEqual([g.goal_checker_id for _, g in node.sent], ['general_goal_checker'] * 2)
        for _, goal in node.sent:
            self.assertEqual(goal.progress_checker_id, 'progress_checker')
        entry = asdict(node.client._settings)
        work = asdict(node.work_client._settings)
        self.assertEqual({k for k in entry if entry[k] != work[k]}, {'controller_id', 'max_start_distance_m'})

    def test_exit_and_same_section_keep_work_controller(self) -> None:
        node = construct()
        HarvestMission(node, request((1.188, -2.3))).run()
        HarvestMission(node, request((1.188, -2.7))).run()
        self.assertEqual(node.sent[-1][1].controller_id, 'HarvestWork')
        node.staged_navigation.sections['SECOND'] = node.staged_navigation.sections['SEC_01']
        node.config['sections']['SECOND'] = node.config['sections']['SEC_01']
        HarvestMission(node, request((1.188, -3.0), 'SECOND')).run()
        self.assertEqual([g.controller_id for _, g in node.sent[-3:]],
                         ['RPP', 'HarvestApproach', 'HarvestWork'])
        self.assertEqual([g.goal_checker_id for _, g in node.sent[-3:]],
                         ['general_goal_checker'] * 3)

    def test_absent_option_preserves_legacy_controller(self) -> None:
        node = construct(config_overrides={'approach_controller_id': None, 'work_controller_id': None,
                                           'approach_goal_checker_id': None})
        HarvestMission(node, request()).run()
        self.assertEqual([g.controller_id for _, g in node.sent], ['RPP', 'RPP'])
        self.assertEqual([g.goal_checker_id for _, g in node.sent], ['general_goal_checker'] * 2)

    def test_absent_entry_checker_preserves_controller_selection(self) -> None:
        node = construct(config_overrides={'approach_goal_checker_id': None})
        HarvestMission(node, request()).run()
        self.assertEqual([g.controller_id for _, g in node.sent], ['HarvestApproach', 'HarvestWork'])
        self.assertEqual([g.goal_checker_id for _, g in node.sent], ['general_goal_checker'] * 2)

    def test_graph_only_ignores_entry_option(self) -> None:
        node = construct('graph_only')
        HarvestMission(node, request()).run()
        self.assertEqual([g.controller_id for _, g in node.sent], ['RPP'])
        self.assertEqual(node.sent[0][1].goal_checker_id, 'general_goal_checker')

    def test_route_server_approach_also_selects_entry_controller(self) -> None:
        node = construct(approach='route_server')
        HarvestMission(node, request()).run()
        self.assertEqual(len(node.route_planner.calls), 1)
        self.assertEqual([g.controller_id for _, g in node.sent], ['HarvestApproach', 'HarvestWork'])
        self.assertEqual([g.goal_checker_id for _, g in node.sent], ['general_goal_checker'] * 2)

    def test_missing_entry_checker_fails_before_motion(self) -> None:
        with patch.object(Parameters, 'checkers', ('general_goal_checker',)):
            node = construct(config_overrides={'approach_goal_checker_id': 'approach_goal_checker'})
            with self.assertRaisesRegex(RuntimeError, 'goal_checker_plugins'):
                HarvestMission(node, request()).run()
            self.assertEqual(node.sent, [])

    def test_explicit_legacy_entry_checker_is_preserved(self) -> None:
        node = construct(config_overrides={'approach_goal_checker_id': 'approach_goal_checker'})
        HarvestMission(node, request()).run()
        self.assertEqual([g.goal_checker_id for _, g in node.sent],
                         ['approach_goal_checker', 'general_goal_checker'])

    def test_invalid_entry_checker_is_rejected(self) -> None:
        for value in ('', ' ', 1, False, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'approach_goal_checker_id'):
                construct(config_overrides={'approach_goal_checker_id': value})

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

    def test_close_consecutive_work_goals_keep_exact_pose(self) -> None:
        node = construct()
        for y in (-2.3, -2.38, -2.7):
            result = HarvestMission(node, request((1.188, y))).run()
            goal = node.sent[-1][1]
            self.assertEqual(goal.controller_id, 'HarvestWork')
            self.assertEqual(goal.goal_checker_id, 'general_goal_checker')
            self.assertAlmostEqual(goal.path.poses[-1].pose.position.y, y)
            self.assertEqual(result['stamp_ns'], 123)
        self.assertEqual(len(node.sent), 4)

    def test_missing_work_plugin_never_sends_work_goal(self) -> None:
        with patch.object(Parameters, 'controllers', ('RPP', 'HarvestApproach')):
            node = construct()
            with self.assertRaises(RuntimeError):
                HarvestMission(node, request()).run()
            self.assertEqual([g.controller_id for _, g in node.sent], ['HarvestApproach'])
            self.assertIsNone(node.staged_navigation.current_section)

    def test_invalid_work_option_is_rejected(self) -> None:
        for value in ('', ' ', 1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                construct(config_overrides={'work_controller_id': value})

    def test_work_profile_preserves_all_other_parameters(self) -> None:
        data = load_nav2_parameters(ROOT/'robot/config/robots/vicpinky/nav2.yaml', ROOT)
        params = data['controller_server']['ros__parameters']
        expected = dict(params['RPP'], use_fixed_curvature_lookahead=True,
                        curvature_lookahead_dist=0.4, interpolate_curvature_after_goal=True)
        self.assertEqual(params['HarvestWork'], expected)
        node = construct()
        self.assertEqual(node.exit_client._settings.controller_id, 'RPP')

    def test_entry_profile_retains_real_override_and_common_checker(self) -> None:
        data = load_nav2_parameters(ROOT/'robot/config/robots/vicpinky/nav2.yaml', ROOT)
        params = data['controller_server']['ros__parameters']
        self.assertIn('HarvestApproach', params['controller_plugins'])
        expected = dict(params['RPP'], use_fixed_curvature_lookahead=True,
                        lookahead_dist=0.1, curvature_lookahead_dist=0.1, interpolate_curvature_after_goal=True)
        self.assertEqual(params['HarvestApproach'], expected)
        self.assertTrue(expected['use_collision_detection'])
        checker = params['general_goal_checker']
        self.assertEqual(checker['plugin'], 'nav2_controller::SimpleGoalChecker')
        self.assertIs(checker['stateful'], True)
        self.assertEqual(checker['xy_goal_tolerance'], .04)
        self.assertAlmostEqual(checker['yaw_goal_tolerance'], .04363323129985824)
        self.assertEqual(params['goal_checker_plugins'], ['general_goal_checker'])
        self.assertEqual(params['HarvestApproach']['plugin'],
                         'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController')


if __name__ == '__main__':
    unittest.main()
