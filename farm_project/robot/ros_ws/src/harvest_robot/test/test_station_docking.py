"""도킹 측정 기하·설정 분리·FSM 종료 계약 및 승인 허용치를 확인한다."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import threading
import math
import tempfile
import unittest
import yaml
import numpy as np
from farm_navigation.wall_observation import DockWallTracker, docking_target, rotated_sectors
from farm_navigation.configuration import load_nav2_parameters
from farm_navigation.path_builder import build_path
from farm_navigation.navigation_types import RoutePlan
from builtin_interfaces.msg import Time
from harvest_robot.station_docking import StationDocking, load_config, server_config, target_error
from harvest_robot.station_return_states import ReturnController
from harvest_robot.station_return_mission import StationReturnMission
from farm_common.action_handoff import ActionInterrupted

ROOT = Path(__file__).resolve().parents[5]
CONFIG = ROOT/'robot/config/robots/vicpinky/station_docking.yaml'


def fixture() -> dict:
    """기하 시험용 5mm/1도 설정 사본을 반환한다."""
    value = yaml.safe_load(CONFIG.read_text())
    value['controller'].update(distance_tolerance=.005, lateral_tolerance=.005, angle_tolerance=math.radians(1))
    with tempfile.NamedTemporaryFile(mode='w',suffix='.yaml') as f:
        yaml.safe_dump(value,f);f.flush()
        return load_config(ROOT,f.name)


class DockingTests(unittest.TestCase):
    def test_wait_clock_only_counts_owned_fresh_zero_output_wait(self) -> None:
        docking = StationDocking.__new__(StationDocking)
        docking._lock = threading.RLock()
        docking._node = Mock()
        docking._node.get_clock.return_value.now.return_value.nanoseconds = 10**9
        docking._pause_clock = Mock()
        docking._pause_clock.update.return_value = 1.
        docking._pause_publisher = Mock()
        docking._pause_session, docking._pause_sequence = 1, 0
        docking._wait_topic = '/test/controller_wait'
        # 대기 아님·오래된 상태·움직이는 출력·소유권 없음에는 시간 공제를 하지 않는다.
        for enabled, owner, stamp, waiting, command_stamp, zero, publishers, expected in (
            (True, True, 10., True, 10., True, 1, True),
            (True, True, 10., False, 10., True, 1, False),
            (True, True, 9., True, 10., True, 1, False),
            (True, True, 10., True, 9., True, 1, False),
            (True, True, 10., True, 10., False, 1, False),
            (True, False, 10., True, 10., True, 1, False),
            (False, True, 10., True, 10., True, 1, False),
            (True, True, 10., True, 10., True, 2, False),
        ):
            docking._enabled = enabled
            docking._owns_output = Mock(return_value=owner)
            docking._controller_wait = (stamp, waiting)
            docking._last_command = (command_stamp, zero)
            docking._node.get_publishers_info_by_topic.return_value = [None]*publishers
            with patch('harvest_robot.station_docking.time.monotonic', return_value=10.1):
                docking._publish_pause_clock()
            docking._pause_clock.update.assert_called_with(expected)

    def test_unconfirmed_tolerances_not_silently_inherited(self) -> None:
        for key in ('distance_tolerance', 'lateral_tolerance', 'angle_tolerance'):
            value = yaml.safe_load(CONFIG.read_text())
            value['controller'][key] = None
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as f:
                yaml.safe_dump(value, f)
                f.flush()
                with self.assertRaisesRegex(ValueError,'허용치 미확정'):
                    load_config(ROOT, f.name)

    def test_approved_tolerances(self) -> None:
        controller = load_config(ROOT, str(CONFIG))['controller']
        self.assertEqual(controller['distance_tolerance'], .005)
        self.assertEqual(controller['lateral_tolerance'], .005)
        self.assertAlmostEqual(controller['angle_tolerance'], math.radians(1))

    def test_rotated_rear_sectors_preserve_width(self) -> None:
        for shift in (-170., -35., 0., 35., 170.):
            ranges = rotated_sectors([[150.,180.],[-180.,-150.]], shift)
            self.assertAlmostEqual(sum(hi-lo for lo,hi in ranges),60.)
            self.assertTrue(all(-180<=lo<hi<=180 for lo,hi in ranges))

    def test_nonorthogonal_three_walls_recover_reference_pose(self) -> None:
        ref=fixture()['reference']['walls']
        for x,y,yaw in ((.09,.02,.15),(.09,-.02,-.15),(.0,0.,0.),(.15,.04,-.2)):
            matrix=np.eye(4);c,s=math.cos(yaw),math.sin(yaw)
            matrix[:2,:2]=[[c,-s],[s,c]];matrix[:2,3]=[x,y]
            walls={}
            for name,r in ref.items():
                a=r['normal_angle_rad'];n=np.array([math.cos(a),math.sin(a)])
                walls[name]=dict(angle_rad=a-yaw,distance_m=r['distance_m']-n@np.array([x,y]))
            target=docking_target(walls,ref,matrix)
            np.testing.assert_allclose([target['x'],target['y'],target['yaw']],0.,atol=1e-12)

    def test_two_walls_recover_pose_and_default_keeps_three(self) -> None:
        config = fixture()
        self.assertEqual(set(DockWallTracker(config)._references), {'rear', 'left'})
        legacy = deepcopy(config)
        legacy.pop('observation_walls')
        self.assertEqual(set(DockWallTracker(legacy)._references), {'rear', 'left', 'right'})
        refs = config['reference']['walls']
        for x, y, yaw in ((.09, .02, .15), (.09, -.04, -.15), (0., 0., 0.)):
            matrix = np.eye(4)
            matrix[:2, :2] = [[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]]
            matrix[:2, 3] = [x, y]
            walls = {name: dict(angle_rad=refs[name]['normal_angle_rad']-yaw,
                distance_m=refs[name]['distance_m']-np.array([math.cos(refs[name]['normal_angle_rad']),
                    math.sin(refs[name]['normal_angle_rad'])]) @ np.array([x, y])) for name in ('rear', 'left')}
            target = docking_target(walls, refs, matrix)
            np.testing.assert_allclose([target['x'], target['y'], target['yaw']], 0., atol=1e-12)

    def test_server_does_not_mutate_existing_navigation(self) -> None:
        nav=load_nav2_parameters(ROOT/'robot/config/robots/vicpinky/nav2.yaml',ROOT)
        before=deepcopy(nav);values=server_config(nav,'harvest_01',fixture())
        self.assertEqual(nav,before)
        self.assertTrue(all(k.startswith('/harvest_01/station_docking/') for k in values))
        c=values['/harvest_01/station_docking/controller_server']['ros__parameters']
        self.assertTrue(c['wall_alignment.station_docking']);self.assertTrue(c['WallAlign.use_collision_detection'])

    def test_four_completion_axes(self) -> None:
        c=fixture()['controller'];p=np.eye(4)
        target=dict(x=0.,y=0.,yaw=0.)
        self.assertTrue(target_error(target,p,c)['accepted'])
        for key,value in [('x',.006),('y',.006),('yaw',.02)]:
            self.assertFalse(target_error(dict(target,**{key:value}),p,c)['accepted'])

    def test_docking_success_and_failure_always_cleanup(self) -> None:
        for error in (None,RuntimeError('collision'),ActionInterrupted('cancel')):
            order=[]
            def dock() -> None:
                order.append('dock')
                if error:raise error
            m=NS(docking_enabled=True,prepare=lambda:order.append('prepare'),
                 navigate=lambda:order.append('navigate'),dock=dock,cleanup=lambda:order.append('cleanup'))
            if error:
                with self.assertRaises(type(error)):ReturnController(m).run()
            else:ReturnController(m).run()
            self.assertEqual(order,['prepare','navigate','dock','cleanup'])

    def test_tag_session_closed_before_dock(self) -> None:
        order=[];docking=Mock();docking.execute.side_effect=lambda:order.append('dock')
        tag=Mock();tag.end.side_effect=lambda:order.append('tag_end')
        m=StationReturnMission(prepare=lambda:None,check=lambda:None,navigator=Mock(),graph=None,
            station=None,poses=None,settings=None,tag_control=tag,corridors={},docking=docking)
        m._tag_active=True;m._navigating=True;m.dock()
        self.assertEqual(order,['tag_end','dock']);self.assertTrue(m.docked);self.assertFalse(m._navigating)
        m.cleanup();docking.cleanup.assert_called_once()

    def test_explicit_path_is_valid_even_at_reference(self) -> None:
        plan=RoutePlan('test','','odom',((0.,0.),(0.,0.)),(),0.,(0.,0.))
        self.assertEqual(len(build_path(plan,0.,Time()).poses),2)


if __name__=='__main__':unittest.main()
