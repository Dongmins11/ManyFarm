"""반복 태그 ID의 구간 선택·전환을 검사한다. 실물 영상 재생은 기하 회귀에만 사용한다."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import unittest

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from farm_tag_localization.runtime import Lease, load_observer
from farm_tag_localization.tag_adapter import observe


class SectionIdentity(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads((ROOT / 'robot/config/localization/bias_trial_20261010/replay_record.json').read_text())
        self.cfg = yaml.safe_load((ROOT / 'robot/config/localization/harvest_real.yaml').read_text())
        self.assets = json.loads((ROOT / self.cfg['assets_file']).read_text())
        tags = self.assets['tags']
        self.assets['tags'] = []
        for section, dx in (('SEC01', 0.0), ('SEC02', 10.0)):
            for original in tags:
                tag = deepcopy(original)
                tag['section_id'] = section
                tag['t_map_tag'][0][3] += dx
                self.assets['tags'].append(tag)

    def load(self) -> object:
        with tempfile.TemporaryDirectory() as folder:
            assets = Path(folder) / 'assets.json'
            assets.write_text(json.dumps(self.assets))
            config = Path(folder) / 'config.yaml'
            config.write_text(yaml.safe_dump(dict(self.cfg, assets_file=str(assets))))
            return load_observer(str(config), str(ROOT), 'sections')[1]

    def test_repeated_id_uses_only_explicit_active_section(self) -> None:
        observer = self.load()
        first, first_result = observe(observer, dict(self.record, section_id='SEC01'))
        second, second_result = observe(observer, dict(self.record, section_id='SEC02'))
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        np.testing.assert_allclose(np.array(second['q']) - first['q'], [10.0, 0.0, 0.0], atol=1e-10)
        self.assertEqual(first_result['selected']['section_id'], 'SEC01')
        self.assertEqual(second_result['selected']['section_id'], 'SEC02')

    def test_missing_or_unknown_section_has_no_candidate(self) -> None:
        observer = self.load()
        for section in (None, '', 'SEC99', ['SEC01']):
            candidate, result = observe(observer, dict(self.record, section_id=section))
            self.assertIsNone(candidate)
            self.assertEqual(result['excluded'][0]['reason'], 'active_section_required_or_unknown')

    def test_same_section_duplicate_registration_is_rejected(self) -> None:
        self.assets['tags'].append(deepcopy(self.assets['tags'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate_landmark_id'):
            self.load()

    def test_multiple_visible_copies_are_rejected(self) -> None:
        observer = self.load()
        detection = deepcopy(self.record['detections'][0])
        record = dict(self.record, section_id='SEC01', detections=[detection, deepcopy(detection)])
        candidate, result = observe(observer, record)
        self.assertIsNone(candidate)
        self.assertEqual(result['excluded'][0]['reason'], 'duplicate_or_unregistered_tag')

    def test_section_change_requires_end_and_new_token(self) -> None:
        lease = Lease('h', 'm')
        message = dict(robot_id='h', map_id='m', token='task1', sequence=1,
                       stamp_ns=1_000_000_000, begin_ns=1_000_000_000,
                       enabled=True, section_id='SEC01')
        lease.update(message, 1_000_000_000, 0.0)
        lease.update(dict(message, sequence=2, section_id='SEC02'), 1_000_000_000, 0.1)
        self.assertEqual(lease.section_id, 'SEC01')
        lease.update(dict(message, sequence=3, enabled=False, section_id=None), 1_000_000_000, 0.2)
        self.assertFalse(lease.active(0.2))
        lease.update(dict(message, token='task2', section_id='SEC02'), 1_000_000_000, 0.3)
        self.assertEqual(lease.section_id, 'SEC02')
        self.assertFalse(lease.accepts('task1', 1_000_000_000, 0.3))

    def test_solved_previous_section_cannot_publish(self) -> None:
        from test_ros_contract import SendTests
        fixture = SendTests()
        fixture.setUp()
        fixture.adapter._lease.section_id = 'SEC02'
        fixture.adapter._send(fixture.candidate, dict(fixture.record, section_id='SEC01'), 'task', .01)
        self.assertEqual(fixture.sent, [])


if __name__ == '__main__':
    unittest.main()
