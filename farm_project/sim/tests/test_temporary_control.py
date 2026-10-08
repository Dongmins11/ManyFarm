"""임시 관제가 최종 성공 목록만 전송하고 원본 작업을 보존하는지 검사한다."""
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace

from farm_interfaces.action import ScoutArea
from farm_interfaces.msg import HarvestTask

spec = importlib.util.spec_from_file_location('temporary_control', Path(__file__).resolve().parents[1] / 'tools/temporary_control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class TemporaryControlTests(unittest.TestCase):
    def result(self) -> ScoutArea.Result:
        result = ScoutArea.Result()
        result.result_code = 'SUCCESS'
        task = HarvestTask()
        task.task_id, task.window_id = 'task_original', 'window_original'
        task.expected_count = 3
        task.goal_pose.frame_id = 'map'
        task.goal_pose.position.x, task.goal_pose.yaw = 1.25, -0.8
        result.harvest_tasks = [task]
        result.harvest_task_count = 1
        return result

    def test_failed_partial_list_is_not_dispatched(self) -> None:
        for status, code in [(6, 'FAILED'), (5, 'CANCELED'), (6, 'SUCCESS'), (4, 'FAILED')]:
            result = self.result()
            result.result_code = code
            self.assertEqual(control.dispatchable_tasks(status, result), [])

    def test_success_retains_order_and_identity(self) -> None:
        result = self.result()
        self.assertEqual(control.dispatchable_tasks(4, result), result.harvest_tasks)

    def test_inconsistent_count_is_rejected(self) -> None:
        result = self.result()
        result.harvest_task_count = 2
        with self.assertRaises(RuntimeError):
            control.dispatchable_tasks(4, result)

    def test_duplicate_is_rejected_before_any_dispatch(self) -> None:
        result = self.result()
        result.harvest_tasks = result.harvest_tasks * 2
        result.harvest_task_count = 2
        with self.assertRaises(RuntimeError):
            control.dispatchable_tasks(4, result)

    def test_cycle_sends_scout_then_each_harvest(self) -> None:
        result = self.result()
        task2 = HarvestTask()
        task2.task_id, task2.window_id = 'second', 'second_window'
        result.harvest_tasks.append(task2)
        result.harvest_task_count = 2
        sent = []
        def execute(client, goal, label):
            sent.append((label, goal))
            if label == 'scout':
                result.robot_id, result.task_id, result.section_id = goal.robot_id, goal.task_id, goal.section_id
                return SimpleNamespace(status=4, result=result)
            task = goal.harvest_task
            return SimpleNamespace(status=4, result=SimpleNamespace(
                robot_id=goal.robot_id, task_id=task.task_id, window_id=task.window_id,
                harvested_count=0, failed_count=1, result_code='SUCCESS', error_code='NONE'))
        node = SimpleNamespace(blocked=False, config={'robot_id': 'scout_01', 'map_id': 'farm_map_v1'},
            harvest_robot='harvest_01', scout=object(), harvest=object(), execute=execute)
        control.TemporaryControl.cycle(node, 'SEC01')
        self.assertEqual([label for label, _ in sent], ['scout', 'harvest', 'harvest'])
        self.assertEqual([goal.harvest_task for _, goal in sent[1:]], result.harvest_tasks)

    def test_goal_preserves_original_task(self) -> None:
        task = self.result().harvest_tasks[0]
        goal = control.harvest_goal(task, 'harvest_01', 'farm_map_v1')
        self.assertEqual(goal.harvest_task, task)
        self.assertEqual(goal.robot_id, 'harvest_01')
        self.assertEqual(goal.map_id, 'farm_map_v1')
        self.assertTrue(goal.timestamp)
        goal.harvest_task.expected_count = 0
        self.assertEqual(task.expected_count, 3)


if __name__ == '__main__':
    unittest.main()
