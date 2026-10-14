"""시뮬 검출 Journal의 광학 프레임/보정/품질 계약 검사. DDS 시험은 별도다."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_devices'))
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_tag_localization'))
from farm_sim_devices.tag_capture import check_camera_info, detection_record, prepare_capture


class CaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assets = json.loads((ROOT / 'sim/ros_ws/src/farm_sim_config/config/tag_localization/assets.json').read_text())
        self.camera = self.assets['camera_info']

    def test_journal_ready_before_adapter_and_no_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'session'
            prepare_capture(folder, self.assets)
            self.assertEqual(json.loads((folder / 'settings.json').read_text())['calibration_sha256'],
                             self.assets['calibration_version'].split(':')[-1])
            self.assertEqual((folder / 'detections.jsonl').read_text(), '')
            with self.assertRaises(FileExistsError):
                prepare_capture(folder, self.assets)

    def test_raw_camera_info_matches_and_wrong_distortion_is_rejected(self) -> None:
        camera = NS(**{key: value for key, value in self.camera.items() if key != 'frame_id'},
                    header=NS(frame_id=self.camera['frame_id']))
        check_camera_info(camera, self.camera)
        camera.d = [0.] * len(camera.d)
        with self.assertRaisesRegex(ValueError, 'camera_info_mismatch:d'):
            check_camera_info(camera, self.camera)

    def test_detector_quality_and_sim_stamp_are_preserved(self) -> None:
        detection = NS(id=104, family='36h11', hamming=1, decision_margin=92.5,
                       corners=[NS(x=x, y=y) for x, y in [(100, 100), (100, 200), (200, 200), (200, 100)]])
        message = NS(header=NS(frame_id=self.camera['frame_id'], stamp=NS(sec=5, nanosec=7)),
                     detections=[detection])
        record = detection_record(message, self.camera['frame_id'])
        self.assertEqual(record['source_stamp_ns'], 5_000_000_007)
        self.assertEqual(record['detections'][0]['decision_margin'], 92.5)
        self.assertEqual(record['detections'][0]['hamming'], 1)
        self.assertEqual(record['detections'][0]['family'], 'tag36h11')
        self.assertNotIn('section_id', record)
        detection.decision_margin = float('nan')
        with self.assertRaises(ValueError):
            detection_record(message, self.camera['frame_id'])
        message.header.frame_id = 'other_camera'
        with self.assertRaisesRegex(ValueError, 'optical_frame_mismatch'):
            detection_record(message, self.camera['frame_id'])


if __name__ == '__main__':
    unittest.main()
