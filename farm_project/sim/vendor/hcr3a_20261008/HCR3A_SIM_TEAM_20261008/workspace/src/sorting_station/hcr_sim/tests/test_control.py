import unittest
import numpy as np
from types import SimpleNamespace
from hcr_sim.control import Sorter
from hcr_sim.model import load_config


class Tensor:
    def __init__(self, values):
        self.values = np.asarray(values)

    def __getitem__(self, key):
        return Tensor(self.values[key])

    def cpu(self):
        return self

    def numpy(self):
        return self.values

    def __array__(self, dtype=None):
        return np.asarray(self.values, dtype=dtype)


class ControlTests(unittest.TestCase):
    def make(self):
        robot = SimpleNamespace(data=SimpleNamespace(joint_pos=Tensor([np.zeros(6)])))
        sorter = Sorter(load_config(), robot, [])
        sorter.arm_ids = list(range(6))
        return sorter

    def test_roi_fault_recovery_only_before_motion(self):
        sorter = self.make()
        sorter.fail("VISION_PICK_COLOR_MISMATCH")
        self.assertTrue(sorter.recover())
        sorter.start()
        self.assertEqual(sorter.phase, "SCANNING")
        sorter.fail("VISION_PICK_COLOR_MISMATCH")
        sorter.current = {"path": "fruit"}
        self.assertFalse(sorter.recover())
        sorter.current = None
        sorter.error = "JOINT_TRACKING_TIMEOUT"
        self.assertFalse(sorter.recover())

    def test_roi_label_commands_its_mapped_physical_lane(self):
        sorter = self.make()
        sorter.fruits = [dict(lane=n, color=color, sorted=False,
            object=SimpleNamespace(data=SimpleNamespace(root_pos_w=Tensor([[.296,y,.116]]))))
            for n,y,color in [("A",.1875,"RED"),("D",-.1875,"YELLOW")]]
        sorter.lane_map = dict(zip("ABCD", "DCBA"))
        sorter.exclude_robot_contacts = lambda: None
        sorter.start()
        self.assertTrue(sorter.choose("A", "YELLOW", 0))
        self.assertEqual(sorter.current["lane"], "D")
        self.assertEqual(sorter.command_lane, "A")
        self.assertEqual(sorter.events[-1]["lane"], "A")

    def test_empty_requires_ready_and_four_clear_zones(self):
        sorter = self.make()
        sorter.start()
        for t in range(10):
            sorter.tick(t, False, dict.fromkeys("ABCD", "NO_COLOR"))
        self.assertEqual(sorter.phase, "SCANNING")
        for value in ["WAIT", "MIXED"]:
            states = dict.fromkeys("ABCD", "NO_COLOR")
            states["B"] = value
            for t in range(10, 20):
                sorter.tick(t, True, states)
            self.assertEqual(sorter.phase, "SCANNING")
        sorter.tick(20, True, dict.fromkeys("ABCD", "NO_COLOR"))
        sorter.tick(23, True, dict.fromkeys("ABCD", "NO_COLOR"))
        self.assertEqual(sorter.phase, "SUCCESS")

    def test_new_selection_only_in_scanning_and_by_priority(self):
        sorter = self.make()
        calls = []
        sorter.choose = lambda lane, color, now: calls.append((lane, color))
        states = {"A": "NO_COLOR", "B": "YELLOW", "C": "RED", "D": "RED"}
        sorter.start()
        sorter.tick(0, True, states)
        self.assertEqual(calls, [("B", "YELLOW")])
        sorter.phase = "DONE"
        sorter.tick(1, True, states)
        self.assertEqual(len(calls), 1)

    def test_bin_verification_counts_once_and_cancel_drains(self):
        sorter = self.make()
        fruit = dict(
            color="RED",
            sorted=False,
            object=SimpleNamespace(
                data=SimpleNamespace(root_pos_w=Tensor([[-0.65, 0.10, 0.51]]))
            ),
        )
        sorter.current = fruit
        sorter.q = np.zeros(6)
        sorter.target = sorter.q.copy()
        sorter.from_q = sorter.q.copy()
        sorter.phase = "VERIFY_BIN"
        sorter.duration = 1
        sorter.step_start = 0
        sorter.job = 7
        sorter.cancel()
        self.assertEqual(sorter.phase, "VERIFY_BIN")
        sorter.tick(2, True, {})
        sorter.tick(3, True, {})
        self.assertEqual(sorter.counts, [1, 0])
        self.assertEqual(sorter.completed, [7])
        sorter.ready_again(3)
        self.assertEqual(sorter.phase, "CANCELED")

    def test_storage_chute_queue_requires_correct_side_and_height(self):
        sorter = self.make()
        fruit = dict(color="RED", object=SimpleNamespace(
            data=SimpleNamespace(root_pos_w=Tensor([[-0.55, .12, .54]]))))
        self.assertTrue(sorter.in_bin(fruit))
        fruit["color"] = "YELLOW"
        self.assertFalse(sorter.in_bin(fruit))
        fruit["color"] = "RED"
        for point in [[-.55, .12, .1], [-.2, .12, .6], [-.55, .3, .54], [-.55, .12, .9]]:
            fruit["object"].data.root_pos_w = Tensor([point])
            self.assertFalse(sorter.in_bin(fruit), point)


if __name__ == "__main__":
    unittest.main()
