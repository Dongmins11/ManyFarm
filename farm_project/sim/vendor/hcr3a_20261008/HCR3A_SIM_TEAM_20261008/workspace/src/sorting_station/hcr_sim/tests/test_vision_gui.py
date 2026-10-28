"""ROI/key protocol regression: same ordered events as the separate GUI."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

from hcr_sim import vision
from hcr_sim.model import load_config


class Window:
    def __init__(self, *_):
        self.events = []
        self.closed = False

    def poll(self):
        events, self.events = self.events, []
        return events

    def show(self, frame):
        self.frame = frame

    def close(self):
        self.closed = True


class VisionGuiTests(unittest.TestCase):
    def test_ordered_keyboard_drag_save_and_start(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(vision, "OUT", Path(folder)), \
                patch("hcr_sim.cv_window.CameraWindow", Window):
            cfg = load_config()
            view = vision.Vision(cfg, gui=True)
            # Multiple events can arrive between simulation frames. A key
            # must select its lane before the following mouse events are used.
            for i, lane in enumerate("abcd"):
                x = 20 + i * 100
                view.window.events.extend([
                    dict(kind="key", key=ord(lane)),
                    dict(kind="mouse", event=view.cv.EVENT_LBUTTONDOWN, x=x, y=20, flags=1),
                    dict(kind="mouse", event=view.cv.EVENT_LBUTTONUP, x=x+30, y=50, flags=0),
                ])
            view.window.events.extend([dict(kind="key", key=ord("s")),
                                       dict(kind="key", key=ord("g"))])
            self.assertEqual(view.key(), ord("g"))
            self.assertEqual(view.key(), 255)
            self.assertEqual(list(view.rois), list("ABCD"))
            self.assertEqual(view.edit, None)
            saved = json.loads(view.file.read_text())
            self.assertEqual(saved["rois"]["C"], [220, 20, 30, 30])
            rgb = np.zeros((cfg["camera"]["height"], cfg["camera"]["width"], 3), dtype=np.uint8)
            rgb[20:50, 20:50] = [255, 0, 0]
            view.update(rgb, 0, "IDLE", [0, 0])
            ready, zone, color = view.update(rgb, 1, "IDLE", [0, 0])
            self.assertEqual((ready, zone, color), (True, 1, 1))
            self.assertEqual(view.window.frame.shape[0], cfg["camera"]["height"]+191)
            view.close()
            self.assertTrue(view.window.closed)
            self.assertFalse(json.loads((Path(folder)/"state.json").read_text())["ready"])

    def test_manual_left_to_right_labels_map_to_actual_lanes(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(vision, "OUT", Path(folder)):
            view = vision.Vision(load_config(), gui=False)
            view.guides = {"A": [438, 145], "B": [359, 145], "C": [280, 145], "D": [201, 145]}
            view.rois = {"A": [185,143,24,10], "B": [271,143,15,11],
                         "C": [349,142,18,11], "D": [435,143,18,12]}
            self.assertTrue(view.map_lanes())
            self.assertEqual(view.lane_map, dict(zip("ABCD", "DCBA")))
            view.rois["B"] = view.rois["A"]
            self.assertFalse(view.map_lanes())
            view.rois["B"] = [270,40,20,10]
            self.assertFalse(view.map_lanes())

    def test_unloading_does_not_publish_empty_batch(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(vision, "OUT", Path(folder)):
            view = vision.Vision(load_config(), gui=False)
            view.rois = {n:[10+i*100,20,20,20] for i,n in enumerate("ABCD")}
            rgb = np.zeros((480,640,3), dtype=np.uint8)
            rgb[20:40,10:30] = [255,0,0]
            view.update(rgb,0,"SCANNING",[0,0],supply="APPROACH")
            view.update(rgb,4,"SCANNING",[0,0],supply="APPROACH")
            state = json.loads((Path(folder)/"state.json").read_text())
            self.assertTrue(state['ready'])
            self.assertEqual(set(state['zone_states'].values()), {'WAIT'})
            self.assertEqual((state['zone'],state['color'],state['valid']), (0,0,False))

    def test_c_edit_differs_from_C_cancel_and_close_quits(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(vision, "OUT", Path(folder)), \
                patch("hcr_sim.cv_window.CameraWindow", Window):
            view = vision.Vision(load_config(), gui=True)
            view.window.events = [dict(kind="key", key=ord("c")), dict(kind="key", key=ord("C"))]
            self.assertEqual(view.key(), ord("C"))
            self.assertEqual(view.edit, "C")
            view.window.events = [dict(kind="key", key=ord("x"))]
            self.assertEqual(view.key(), ord("C"))
            view.window.events = [dict(kind="closed", returncode=0)]
            self.assertEqual(view.key(), ord("q"))
            view.close()


if __name__ == "__main__":
    unittest.main()
