"""실제 공통 발행/소비 경로에서 먼 마커로 Nav2가 조기 취소되지 않는지 검사한다."""
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace as NS

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_docking', 'transport_robot'):
    sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
from farm_docking.precision_server import PrecisionServer
from farm_docking.staged_dock import StagedDockTracker
from tf2_ros import TransformException
from transport_robot.harvest_approach import HarvestApproach
from transport_robot.sorter_approach import MarkerHandoff


def setup_route():
    profile = yaml.safe_load((ROOT / 'sim/ros_ws/src/farm_sim_config/config/docking/transport_profiles.yaml').read_text())['profiles']['harvest_approach_42']
    now = 10_000_000_000
    clock = NS(now=lambda: NS(nanoseconds=now))
    controller = NS(target=np.eye(4), marker_id=42,
                    c=dict(max_planar_distance_m=profile['pose_controller']['max_planar_distance_m'], max_tilt_rad=.3))
    captured = NS(transform=NS(translation=NS(x=4., y=5., z=0.),
                              rotation=NS(x=0., y=0., z=0., w=1.)))
    calls, messages = [], []
    def lookup(frame, base, stamp, timeout):
        calls.append((frame, base, stamp.nanoseconds))
        return captured
    tracker = StagedDockTracker(controller.target, 42, profile['target_tracking'], profile['acquire_then_odom'])
    server = NS(_harvest_route=dict(profile='pickup', observation_start_ns=9_000_000_000,
                observer_id='current', expires_at=time.monotonic()+900), profiles={'pickup': profile},
                _raw_reports=(), _pose_controller=controller, _target_tracker=tracker,
                marker_base_frame=profile['base_frame'], tf=NS(lookup_transform=lookup),
                get_parameter=lambda _: NS(value='transport_01/odom'), get_clock=lambda: clock,
                get_logger=lambda: NS(info=lambda _: None),
                _harvest_ready_pub=NS(publish=lambda msg: messages.append(json.loads(msg.data))))
    consumer = NS(lock=threading.Lock(), armed=True, ready=None, profile='pickup',
                  node=NS(get_clock=lambda: clock), c={'max_ready_age_s': .5})
    return server, consumer, calls, messages


def report(x, y=0., stamp=9_900_000_000, marker_id=42):
    return dict(stamp_ns=stamp, markers=[dict(marker_id=marker_id,
                marker_position_in_base_m=[x, y, .08], marker_rotation_in_base=np.eye(3).tolist())])


@pytest.mark.parametrize('x,y,ready', [(3.84, 0., False), (1.741, 0., False),
                                     (1.739, 0., False), (1.639, 0., True), (1.5, 1., False)])
def test_distance_gate_controls_actual_route_handoff(x, y, ready):
    server, consumer, calls, messages = setup_route()
    server._raw_reports = [report(x, y)]
    PrecisionServer.update_harvest_route(server)
    assert messages[-1]['ready'] is ready
    assert calls[-1][2] == 9_900_000_000
    consumer.ready = messages[-1]
    if ready:
        with pytest.raises(MarkerHandoff):
            HarvestApproach.check_handoff(consumer)
    else:
        HarvestApproach.check_handoff(consumer)
        assert 'outside approach envelope' in messages[-1]['reason']
    assert server._target_tracker.goal is None
    assert server._target_tracker.samples == []


@pytest.mark.parametrize('stamp,marker_id', [(9_400_000_000, 42), (10_100_000_000, 42),
                                          (8_900_000_000, 42), (9_900_000_000, 41)])
def test_stale_future_old_session_or_wrong_marker_does_not_stop_navigation(stamp, marker_id):
    server, consumer, calls, messages = setup_route()
    server._raw_reports = [report(1., stamp=stamp, marker_id=marker_id)]
    PrecisionServer.update_harvest_route(server)
    assert messages[-1]['ready'] is False
    assert calls == []
    consumer.ready = messages[-1]
    HarvestApproach.check_handoff(consumer)


def test_missing_capture_tf_keeps_navigation_then_recovers():
    server, _, _, messages = setup_route()
    lookup = server.tf.lookup_transform
    def missing(*args, **kwargs):
        raise TransformException('capture TF unavailable')
    server.tf.lookup_transform = missing
    server._raw_reports = [report(1.)]
    PrecisionServer.update_harvest_route(server)
    assert messages[-1]['ready'] is False
    assert 'capture TF unavailable' in messages[-1]['reason']
    server.tf.lookup_transform = lookup
    PrecisionServer.update_harvest_route(server)
    assert messages[-1]['ready'] is True


def test_range_uses_active_controller_limit_and_does_not_latch_ready():
    server, _, _, messages = setup_route()
    server._pose_controller.c['max_planar_distance_m'] = .8
    for x, ready in [(1.5, False), (1.2, True), (3.84, False)]:
        server._raw_reports = [report(x)]
        PrecisionServer.update_harvest_route(server)
        assert messages[-1]['ready'] is ready


def test_expiration_still_stops_route_with_failure():
    server, consumer, _, messages = setup_route()
    server._harvest_route['expires_at'] = time.monotonic()-1
    PrecisionServer.update_harvest_route(server)
    consumer.ready = messages[-1]
    with pytest.raises(RuntimeError, match='observation expired'):
        HarvestApproach.check_handoff(consumer)


def test_real_profile_without_margin_retains_original_envelope():
    server, _, _, messages = setup_route()
    server.profiles['pickup']['route_handoff'].pop('approach_margin_m')
    server._raw_reports = [report(1.739)]
    PrecisionServer.update_harvest_route(server)
    assert messages[-1]['ready'] is True


@pytest.mark.parametrize('margin', [-.1, 1.2, float('nan')])
def test_invalid_margin_never_enlarges_envelope(margin):
    server, _, _, messages = setup_route()
    server.profiles['pickup']['route_handoff']['approach_margin_m'] = margin
    server._raw_reports = [report(1.)]
    PrecisionServer.update_harvest_route(server)
    assert messages[-1]['ready'] is False
    assert 'Invalid route approach margin' in messages[-1]['reason']
