"""복귀 기준·좌표계·엄격한 완료 판정. ROS·실물 동작 없는 검사."""
from dataclasses import replace
import math
import unittest
from types import SimpleNamespace as NS
import numpy as np
from harvest_robot.transfer_restore import RestoreReference
from farm_navigation.transfer_arc import ArcSpec, arc_path
from farm_navigation.arc_clearance import check_grid


def matrix(x=0., y=0., yaw=0.):
    m = np.eye(4)
    m[:2, :2] = [[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]]
    m[0, 3], m[1, 3] = x, y
    return m


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.ref = RestoreReference('farm', 'window12', 'odom-session', 'map', 'odom',
                                    'base_footprint', 10, (2., 3.), (1., 0.), (0., 0., 0.), ArcSpec())

    def validator(self, pose):
        self.lookups = []
        def lookup(*args):
            self.lookups.append(args[:3]); return pose
        return self.ref.arrival_validator(NS(lookup=lookup), map_id='farm', window_id='window12', session_id='odom-session')

    def test_capture_same_stop_stamp_distinct_frames(self):
        calls = []
        def lookup(target, source, stamp, check):
            calls.append((target, source, stamp));return matrix(8., 9., .5) if target == 'map' else matrix(1., 2., -.7)
        ref = RestoreReference.capture(NS(lookup=lookup), map_id='farm', window_id='w',
             session_id='s', window_xy=(2., 3.), stamp_ns=100, arc_spec=ArcSpec(), check=lambda:None)
        self.assertEqual(calls, [('map', 'base_footprint', 100), ('odom', 'base_footprint', 100)])
        self.assertEqual(ref.window_xy, (2., 3.))
        np.testing.assert_allclose(ref.arc_origin_odom, (1., 2., -.7))
        np.testing.assert_allclose(ref.heading_map, (math.cos(.5), math.sin(.5)))

    def test_capture_rejects_latest_lookup(self):
        with self.assertRaises(ValueError):
            RestoreReference.capture(NS(), map_id='farm', window_id='w', session_id='s',
              window_xy=(2., 3.), stamp_ns=0, arc_spec=ArcSpec(), check=lambda:None)

    def test_inverse_retains_body_headings(self):
        path = arc_path(self.ref.arc_origin_odom, self.ref.arc_spec)
        route = self.ref.return_arc()
        self.assertEqual(route.points, tuple(p[:2] for p in reversed(path)))
        self.assertEqual(route.headings, tuple(p[2] for p in reversed(path)))
        self.assertEqual(route.frame_id, 'odom')
        self.assertEqual(route.points[-1], (0., 0.))

    def test_reentry_pose(self):
        end = arc_path(self.ref.arc_origin_odom, self.ref.arc_spec)[-1]
        self.assertEqual(self.ref.check_reentry(end)['position_error_m'], 0.)
        for pose in ((end[0]+.02, end[1], end[2]), (end[0], end[1], end[2]+math.radians(2))):
            with self.assertRaises(RuntimeError):self.ref.check_reentry(pose)

    def test_window_position_not_odom_origin(self):
        self.assertFalse(self.validator(matrix(0., 0.))(11, lambda:None)['accepted'])
        self.assertTrue(self.validator(matrix(2., 3.))(11, lambda:None)['accepted'])
        self.assertEqual(self.lookups, [('map', 'base_footprint', 11)])

    def test_distance_boundary(self):
        for error, accepted in ((.019, True), (.021, False)):
            self.assertEqual(self.validator(matrix(2.+error, 3.))(11, lambda:None)['accepted'], accepted)

    def test_heading_boundary_and_sign(self):
        for degrees, accepted in ((.99, True), (-.99, True), (1.01, False), (-1.01, False)):
            r = self.validator(matrix(2., 3., math.radians(degrees)))(11, lambda:None)
            self.assertEqual(r['accepted'], accepted)
            self.assertAlmostEqual(r['heading_correction_rad'], -math.radians(degrees))

    def test_wrap_boundary(self):
        self.ref = replace(self.ref, heading_map=(math.cos(math.radians(179.8)), math.sin(math.radians(179.8))))
        r = self.validator(matrix(2., 3., math.radians(-179.8)))(11, lambda:None)
        self.assertTrue(r['accepted']);self.assertAlmostEqual(r['heading_correction_rad'], math.radians(-.4))

    def test_context(self):
        for values in (('other', 'window12', 'odom-session'), ('farm', 'other', 'odom-session'), ('farm', 'window12', 'reboot')):
            with self.assertRaises(ValueError):self.ref.require_context(*values)

    def test_stale_stamp(self):
        for stamp in (0, 9, 10, True):
            with self.assertRaises(RuntimeError):self.validator(matrix(2., 3.))(stamp, lambda:None)

    def test_invalid_reference(self):
        for change in ({'heading_map': (0., 0.)}, {'window_xy': (math.nan, 0.)}, {'map_frame': 'odom'},
                       {'session_id': ''}, {'stamp_ns': True}, {'arc_spec': None}):
            with self.assertRaises(ValueError):replace(self.ref, **change)

    def test_invalid_tf(self):
        for m in (np.zeros((4,4)), np.full((4,4), math.nan), np.eye(3), np.diag([-1.,1.,1.,1.])):
            with self.assertRaises(ValueError):self.validator(m)(11, lambda:None)

    def test_cancellation(self):
        def canceled():raise RuntimeError('cancel')
        with self.assertRaisesRegex(RuntimeError, 'cancel'):self.validator(matrix(2.,3.))(11,canceled)

    def test_missing_tf(self):
        def lookup(*args):raise RuntimeError('TF unavailable')
        validate=self.ref.arrival_validator(NS(lookup=lookup),map_id='farm',window_id='window12',session_id='odom-session')
        with self.assertRaisesRegex(RuntimeError,'TF unavailable'):validate(11,lambda:None)

    def test_inverse_clearance_uses_same_footprint(self):
        route=self.ref.return_arc();path=[(*xy,yaw) for xy,yaw in zip(route.points,route.headings)]
        current=path[0];c,s=math.cos(current[2]),math.sin(current[2])
        footprint=[(current[0]+c*x-s*y,current[1]+s*x+c*y) for x,y in ((-.3,-.25),(-.3,.25),(.3,.25),(.3,-.25))]
        grid={'metadata':{'resolution':.04,'size_x':100,'size_y':100,
            'origin':{'position':{'x':-2.,'y':-2.},'orientation':{'x':0.,'y':0.,'z':0.,'w':1.}}},'data':[0]*10000}
        self.assertGreater(check_grid(path,footprint,current,grid),0)
        for value in (254,255):
            grid['data'][50*100+50]=value
            with self.assertRaises(RuntimeError):check_grid(path,footprint,current,grid)


if __name__ == '__main__':unittest.main()
