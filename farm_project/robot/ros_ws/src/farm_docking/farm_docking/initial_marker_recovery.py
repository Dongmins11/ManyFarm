"""초기 미관측에만 적용하는 정지→짧은 후진→좌/우/원위치 탐색. ROS 독립."""
import math
from .recovery import MarkerSearch

class ApproachReentryRequired(RuntimeError):
    """접근 전 거리 초과이며 정지·제어권 해제가 확인된 경우에만 전달한다."""
    prefix = 'APPROACH_REENTRY_REQUIRED: '


class InitialMarkerRecovery:
    def __init__(self, config, now):
        self.c = config
        for key in ('wait_s', 'reverse_distance_m', 'reverse_speed_mps',
                    'search_angle_rad', 'search_speed_rps', 'timeout_s'):
            value = config[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Invalid initial marker recovery: ' + key)
        self.started = now
        self.origin = None
        self.search = None
        self.done = False
        self.candidate_at = None
        self.rejected_pose = None

    def step(self, now, pose, stopped, visible, acquired=False):
        if self.done:
            return 0., 0., True, 'MARKER_ACQUIRED'
        if acquired and stopped:
            self.done = True
            return 0., 0., True, 'MARKER_ACQUIRED'
        if now - self.started > self.c['timeout_s']:
            raise TimeoutError('Initial marker reacquisition exhausted')
        if self.rejected_pose is not None:
            x,y,a=self.rejected_pose
            turn=abs(math.atan2(math.sin(pose[2]-a),math.cos(pose[2]-a)))
            if math.hypot(pose[0]-x,pose[1]-y)>=.02 or turn>=.04:
                self.rejected_pose=None
        if visible and self.rejected_pose is None:
            if self.candidate_at is None:self.candidate_at=now
            if now-self.candidate_at<2.:
                return 0.,0.,False,'VERIFY_MARKER_TARGET'
            self.rejected_pose=pose
        self.candidate_at=None
        if now - self.started < self.c['wait_s']:
            return 0., 0., False, 'WAIT_INITIAL_MARKER'
        x, y, yaw = pose
        if self.origin is None:
            if not stopped:
                return 0., 0., False, 'VERIFY_SEARCH_STOP'
            self.origin = pose
        ox, oy, heading = self.origin
        distance = -((x-ox)*math.cos(heading)+(y-oy)*math.sin(heading))
        if self.search is None and distance < self.c['reverse_distance_m']:
            error = math.atan2(math.sin(heading-yaw), math.cos(heading-yaw))
            return -self.c['reverse_speed_mps'], max(-.08, min(.08, .8*error)), False, 'BACKOUT_FOR_MARKER'
        if self.search is None:
            if not stopped:
                return 0., 0., False, 'VERIFY_SEARCH_STOP'
            self.search = MarkerSearch(yaw, now, self.c['search_angle_rad'], self.c['search_speed_rps'], 0.)
        angular, finished = self.search.step(yaw, stopped, now)
        if finished:
            raise TimeoutError('Marker not found after bounded left/right search')
        return 0., angular, False, 'SEARCH_INITIAL_MARKER'
