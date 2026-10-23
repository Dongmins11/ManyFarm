"""차체 단계 구성. 기존 경로 계산·정지 시각 완료 판정을 연결한다.

inputs는 최신성/프레임 검사를 수행하는 ROS 관측 어댑터다. guard는 충돌·속도
감시를 준비하고 비차단 check를 반환한다. 둘 다 운영 연결에서 필수 제공한다.
"""
from dataclasses import dataclass, replace
import math
from typing import Any, Callable, Protocol
import uuid

from farm_navigation.navigation_types import RoutePlan
from farm_navigation.transfer_arc import ArcSpec, arc_path, check_complete, check_motion, wrap
from .handoff_navigation import NavigationStep, AlignmentStep, Check
from .handoff_paths import departure_route, return_route, retreat_route, alignment
from .transfer_retreat import retreat_error
from .transfer_restore import RestoreReference
from .handoff_input_trace import InputTrace, traced


class MotionInputs(Protocol):
    def context(self) -> tuple[str, str, str]: ...
    def odom_stamp(self) -> int: ...
    def pose(self, stamp: int, check: Check) -> tuple[float, float, float]: ...
    def wall_error(self, check: Check) -> tuple[float, float]: ...


@dataclass(frozen=True)
class CompletionPolicy:
    return_heading: float = math.radians(3.)
    return_position: float = .02
    alignment_heading: float = math.radians(1.)
    alignment_skip: float = math.radians(.5)
    spin_allowance: float = 40.
    reentry_position: float | None = None

    def __post_init__(self) -> None:
        if any(not math.isfinite(v) or v <= 0 for k, v in vars(self).items()
               if not (k == 'reentry_position' and v is None)):
            raise ValueError('완료 설정은 유한한 양수여야 합니다.')
        if self.return_heading > math.radians(3.) or self.alignment_skip > self.alignment_heading:
            raise ValueError('완료 설정 범위 초과')


class HandoffPlanner:
    def __init__(self, *, poses: Any, motion: Any, inputs: MotionInputs,
                 guard: Callable[[str, tuple, Check], Check],
                 wall: dict, spec: ArcSpec, window_xy: tuple[float, float],
                 map_frame: str, odom_frame: str, base_frame: str,
                 policy: CompletionPolicy = CompletionPolicy(), window_correction: bool = False) -> None:
        self._poses, self._motion, self._inputs = poses, motion, inputs
        self._guard, self._wall, self._spec = guard, dict(wall), spec
        self._window = window_xy
        self._map, self._odom, self._base = map_frame, odom_frame, base_frame
        self._policy = policy
        self._window_correction = window_correction
        reentry = spec.endpoint_tolerance if policy.reentry_position is None else policy.reentry_position
        if reentry > spec.deviation:
            raise ValueError('재진입 위치 허용오차는 기존 경로 이탈 한계 이하여야 합니다.')

    @traced
    def capture(self, check: Check) -> RestoreReference:
        self._motion.wait_stopped(check)
        context = self._inputs.context()

        def stopped() -> None:
            check()
            if not self._motion.stationary_now():
                raise RuntimeError('출발 기준 저장 중 정지 상실')
            if self._inputs.context() != context:
                raise RuntimeError('출발 기준 저장 중 세션 변경')

        if getattr(self._inputs, '_input_trace', None) is not None: getattr(self._inputs, '_input_trace', None).emit('tf_pair_begin')
        stamp, matrices = self._poses.lookup_available_pair(
            (self._map, self._odom), self._base, self._inputs.odom_stamp, stopped)
        if getattr(self._inputs, '_input_trace', None) is not None: getattr(self._inputs, '_input_trace', None).emit('tf_pair_end')
        stopped()
        values = dict(zip((self._map, self._odom), matrices))

        class CapturedPair:
            def lookup(inner, target: str, source: str, at: int, check: Check) -> Any:
                check()
                if source != self._base or at != stamp:
                    raise ValueError('동일 시각 출발 TF 필요')
                return values[target]

        return RestoreReference.capture(CapturedPair(), map_id=context[0], window_id=context[1],
            session_id=context[2], window_xy=self._window, stamp_ns=stamp, arc_spec=self._spec,
            check=stopped, map_frame=self._map, odom_frame=self._odom, base_frame=self._base)

    @traced
    def plan(self, stage: str, reference: RestoreReference, check: Check) -> NavigationStep | AlignmentStep:
        reference.require_context(*self._inputs.context())
        check()
        if stage == 'window':
            from .handoff_window import plan_window
            return plan_window(reference, self._poses, self._motion, self._inputs,
                               self._guard, self._policy, check)
        current = self._inputs.pose(0, check)
        target = arc_path(reference.arc_origin_odom, reference.arc_spec)[-1]
        policy = self._policy
        retreat = None
        if stage == 'departure':
            route = departure_route(reference)
        elif stage == 'return':
            reference.check_reentry(current, heading_limit=policy.alignment_heading,
                                    position_limit=policy.reentry_position)
            check_motion(reference.arc_origin_odom, current, reference.arc_spec)
            route = return_route(reference)
        elif stage == 'retreat':
            retreat = retreat_route(reference, current)
            route = retreat.route
        elif stage == 'align':
            angle, path = alignment(reference, current)
            if math.dist(current[:2], target[:2]) > (reference.arc_spec.endpoint_tolerance
                    if policy.reentry_position is None else policy.reentry_position):
                raise RuntimeError('방향 조정 위치가 원호 끝점에서 벗어남')
            route = None
        elif stage == 'wall':
            distance, angle = self._inputs.wall_error(check)
            c = self._wall
            if not all(math.isfinite(v) for v in (distance, angle)):
                raise ValueError('벽 관측 비정상')
            if not -c['distance_tolerance'] <= distance-c['target_distance'] <= c['max_distance']:
                raise RuntimeError('벽 접근 거리 범위 초과')
            if max(abs(angle), abs(wrap(angle-c['target_angle']))) > c['max_yaw']:
                raise RuntimeError('벽 접근 방향 범위 초과')
            yaw = wrap(current[2]+angle-c['target_angle'])
            length = max(.001, distance-c['target_distance'])
            endpoint = (current[0]+length*math.cos(current[2]+angle),
                        current[1]+length*math.sin(current[2]+angle))
            route = RoutePlan(uuid.uuid4().hex, '', reference.odom_frame,
                              (current[:2], endpoint), (), length, (yaw, yaw))
        else:
            raise ValueError('알 수 없는 차체 단계: ' + stage)
        if route is not None:
            headings = route.headings or (retreat.travel_heading,) * len(route.points)
            path = tuple((*point, yaw) for point, yaw in zip(route.points, headings))
        # 제어기에 보낼 원호는 보존한다. 실제 자세와 시작점 사이도 충돌 검사한다.
        guard_path = (current,) + path if stage == 'return' else path
        guard = self._guard(stage, guard_path, check)

        def monitor() -> None:
            reference.require_context(*self._inputs.context())
            guard()
            pose = self._inputs.pose(0, check)
            if stage in ('departure', 'return'):
                limits = reference.arc_spec
                if stage == 'return':
                    limits = replace(limits, yaw_tolerance=max(limits.yaw_tolerance, policy.return_heading))
                check_motion(reference.arc_origin_odom, pose, limits)
            elif stage == 'retreat':
                retreat_error(retreat, pose)
            elif stage == 'align':
                if math.dist(pose[:2], current[:2]) > .005 or abs(wrap(pose[2]-current[2])) > math.radians(16):
                    raise RuntimeError('방향 조정 이동 범위 초과')

        def validate(stamp: int, stopped_check: Check) -> dict:
            reference.require_context(*self._inputs.context())
            pose = self._inputs.pose(stamp, stopped_check)
            if stage == 'departure':
                result = check_complete(reference.arc_origin_odom, pose, reference.arc_spec)
            elif stage == 'retreat':
                result = retreat_error(retreat, pose)
                result['accepted'] = result['position_error_m'] <= reference.arc_spec.endpoint_tolerance
                return result
            elif stage == 'align':
                result = reference.check_reentry(pose, heading_limit=policy.alignment_heading,
                                                 position_limit=policy.reentry_position)
            elif stage == 'wall':
                distance, angle = self._inputs.wall_error(stopped_check)
                error = wrap(angle-self._wall['target_angle'])
                return dict(final_distance=distance, final_angle_error=error,
                    accepted=abs(distance-self._wall['target_distance']) <= self._wall['distance_tolerance']
                        and abs(error) <= self._wall['angle_tolerance'])
            else:
                limits = replace(reference.arc_spec, yaw_tolerance=max(reference.arc_spec.yaw_tolerance, policy.return_heading))
                result = check_motion(reference.arc_origin_odom, pose, limits)
                result.update(endpoint_error=math.dist(pose[:2], reference.arc_origin_odom[:2]),
                              yaw_error=abs(wrap(pose[2]-reference.arc_origin_odom[2])))
                if result['endpoint_error'] > limits.endpoint_tolerance or result['yaw_error'] > policy.return_heading:
                    raise RuntimeError('복귀 종료 위치·방향 오차 초과')
                if self._window_correction:
                    return dict(result, accepted=True, window_pending=True)
                result['map_arrival'] = reference.arrival_validator(self._poses,
                    map_id=reference.map_id, window_id=reference.window_id, session_id=reference.session_id,
                    position_limit=policy.return_position, heading_limit=policy.return_heading)(stamp, stopped_check)
                result['accepted'] = result['map_arrival']['accepted']
                return result
            return dict(result, accepted=True)

        if stage == 'align':
            return AlignmentStep(angle, policy.spin_allowance, abs(angle) <= policy.alignment_skip, validate, monitor)
        return NavigationStep(route, path[-1][2], validate, monitor,
            reverse=stage == 'retreat',
            stationary_only=retreat is not None and retreat.distance <= .005,
            wall_parameters=dict(self._wall) if stage == 'wall' else None)
