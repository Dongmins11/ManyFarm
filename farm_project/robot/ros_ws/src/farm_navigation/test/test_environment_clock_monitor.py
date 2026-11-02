"""환경별 동작 시계: 정지 구간과 lifecycle 대기의 pause/만료 회귀."""
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
from nav_msgs.msg import Odometry
from farm_navigation.motion_monitor import MotionMonitor
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.nav2_client import Nav2Client


def node_clock(sim):
    clock = NS(ros_time_is_active=sim, seconds=10.)
    clock.now = lambda: NS(nanoseconds=int(clock.seconds*1e9))
    node = Mock()
    node.get_clock.return_value = clock
    return node, clock


@pytest.mark.parametrize('sim', [True, False])
def test_stationary_epoch_uses_only_environment_clock(sim):
    node, clock = node_clock(sim)
    wall = [1000.]
    with patch('farm_navigation.operation_clock.time.monotonic', side_effect=lambda: wall[0]):
        monitor = MotionMonitor(node, NavigationSettings(), None)
        msg = Odometry()
        monitor._on_odom(msg)
        epoch = monitor.stationary_epoch()
        # 환경 외 시계 진행은 신선한 정지 구간을 무효화하지 않는다.
        if sim: wall[0] += 100
        else: clock.seconds += 100
        monitor._on_odom(msg)
        assert monitor.stationary_epoch() == epoch
        if sim: clock.seconds += 2
        else: wall[0] += 2
        assert monitor.stationary_now() is False
        monitor._on_odom(msg)
        assert monitor.stationary_epoch() == epoch + 1
        msg.twist.twist.linear.x = .1
        monitor._on_odom(msg)
        assert monitor.stationary_epoch() is None


def test_sim_clock_rewind_invalidates_stationary_epoch():
    node, clock = node_clock(True)
    monitor = MotionMonitor(node, NavigationSettings(), None)
    monitor._on_odom(Odometry())
    epoch = monitor.stationary_epoch()
    clock.seconds = 1.
    monitor._on_odom(Odometry())
    assert monitor.stationary_epoch() == epoch + 1


@pytest.mark.parametrize('sim', [True, False])
def test_lifecycle_deadline_uses_environment_clock_and_can_cancel(sim):
    node, clock = node_clock(sim)
    client = Nav2Client.__new__(Nav2Client)
    client._node = node
    service = Mock()
    pending = Mock()
    pending.done.return_value = False
    service.call_async.return_value = pending
    client._lifecycle_clients = [service]
    wall = [1000.]
    ticks = [0]
    def sleep(_):
        ticks[0] += 1
        if ticks[0] <= 3:
            if sim: wall[0] += 100
            else: clock.seconds += 100
            assert service.remove_pending_request.call_count == 0
        else:
            if sim: clock.seconds += 1
            else: wall[0] += 1
    def check():
        if service.remove_pending_request.called:
            raise RuntimeError('cancelled')
        assert ticks[0] < 12, '동작 시계가 진행해도 만료하지 않음'
    with patch('farm_navigation.operation_clock.time.monotonic', side_effect=lambda: wall[0]), patch('farm_navigation.nav2_client.time.sleep', side_effect=sleep):
        with pytest.raises(RuntimeError, match='cancelled'):
            client._wait_active_nav2(check)
    service.remove_pending_request.assert_called_once_with(pending)
    assert ticks[0] >= 5
