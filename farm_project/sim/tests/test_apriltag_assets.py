"""태그 배치·패턴·URDF의 좌표 오류를 검출합니다. 주행 검증과는 별개입니다."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'sim/ros_ws/src/farm_sim_config/config'
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_devices'))


class TagTests(unittest.TestCase):
    def test_paper_spacing_centers_and_section_scoped_ids(self) -> None:
        data = json.loads((CONFIG/'apriltag_map.json').read_text())
        self.assertEqual(len(data['tags']), 240)
        self.assertEqual({t['id'] for t in data['tags']},set(range(100,115)))
        self.assertEqual(len({(t['section_id'],t['id']) for t in data['tags']}),240)
        self.assertTrue(data['requires_active_section'])
        for section in {t['section_id'] for t in data['tags']}:
            tags = [t for t in data['tags'] if t['section_id'] == section]
            self.assertEqual(len(tags), 15)
            self.assertEqual([t['id'] for t in tags],list(range(100,115)))
            points = np.array([t['tag_center_map_m'] for t in tags])
            np.testing.assert_allclose(np.linalg.norm(np.diff(points, axis=0),axis=1), .564)
            np.testing.assert_allclose(points[:,2], .264)
            for t in tags:
                self.assertAlmostEqual(t['paper_center_map_m'][2], .2615)
                np.testing.assert_allclose(np.cross(t['right_map'],[0,0,1]),t['normal_map'])

    def test_every_texture_decodes_upright_and_matches_source(self) -> None:
        import cv2
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        data = json.loads((CONFIG/'apriltag_map.json').read_text())
        for tag in data['tags']:
            picture = cv2.imread(str(ROOT/tag['texture']), cv2.IMREAD_GRAYSCALE)
            self.assertEqual(picture.shape, (1380,1280))
            expected = cv2.aruco.drawMarker(dictionary, tag['id'], 1000)
            np.testing.assert_array_equal(picture[140:1140,140:1140], expected)
            cells = np.array(data['pattern_cells'][str(tag['id'])], dtype=np.uint8)
            # 기하 셀의 방향·ID가 기존 인쇄 패턴과 정확히 같아야 한다.
            np.testing.assert_array_equal(np.repeat(np.repeat(cells,125,0),125,1)*255, expected)
            corners, ids, _ = cv2.aruco.detectMarkers(cv2.resize(picture,(640,690)), dictionary)
            self.assertIsNotNone(ids)
            # OpenCV 4.6은 같은 ID의 중첩 후보를 중복 반환할 수 있습니다.
            self.assertEqual(set(ids.flatten().tolist()), {tag['id']})
            self.assertLess(min(np.linalg.norm(c[0][0]-[70,70]) for c in corners), 2.)

    def test_urdf_optical_mount_in_logical_drive_frame(self) -> None:
        cfg = json.loads((CONFIG/'harvest.json').read_text())
        tree = ET.parse(ROOT/'sim/assets/robots/harvest_robot/urdf/harvest_robot.urdf')
        origin = tree.find(".//joint[@name='apriltag_camera_fixed_joint']/origin")
        transform = np.eye(4)
        transform[:3,3] = np.fromstring(origin.attrib['xyz'], sep=' ')
        transform[:3,:3] = Rotation.from_euler('xyz',np.fromstring(origin.attrib['rpy'],sep=' ')).as_matrix()
        from farm_sim_devices.control_frame import asset_from_control
        logical = np.linalg.inv(asset_from_control(cfg['scene_binding']))@transform
        np.testing.assert_allclose(logical, cfg['camera']['T_base_optical'], atol=1e-7)
        self.assertGreater(logical[1,2], .99)


if __name__ == '__main__':
    unittest.main()
