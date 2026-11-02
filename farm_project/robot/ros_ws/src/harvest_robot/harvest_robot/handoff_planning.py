"""차체 단계 구성. 기존 경로 계산·정지 시각 완료 판정을 연결한다.

inputs는 최신성/프레임 검사를 수행하는 ROS 관측 어댑터다. guard는 충돌·속도
감시를 준비하고 비차단 check를 반환한다. 둘 다 운영 연결에서 필수 제공한다.
"""
from dataclasses import dataclass, replace
import math
from typing import Any, Callable, Protocol
import uuid

from farm_navigation.navigation_types import RoutePlan
from farm_navigation.transfer_arc import ArcSpec, arc_path, check_complete, check_motion, measure, wrap
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
    # 정지 후 원호 끝점 판정 전용(m). 미지정 프로필은 기존 원호 조건 유지.
    return_endpoint_position: float | None = None

    def __post_init__(self) -> None:
        if any(not math.isfinite(v) or v <= 0 for k, v in vars(self).items()
               if not (k in ('reentry_position', 'return_endpoint_position') and v is None)):
            raise ValueError('완료 설정은 유한한 양수여야 합니다.')
        if self.return_heading > math.radians(6.) or self.alignment_skip > self.alignment_heading:
            raise ValueError('완료 설정 범위 초과')

    @property
    def motion_heading(self) -> float:
        """실행 중 각도 한계(rad)는 완료 허용치 확대와 독립적으로 기존 범위를 유지한다."""
        return min(self.return_heading, math.radians(3.))


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

    def plan_wall_approach(self, reference: RestoreReference, check: Check) -> NavigationStep | None:
        """벽 접근 상한을 3cm 이내 초과할 때 한 번만 최대 4cm 전진한다.

        정상 범위는 기존 wall 단계에 맡긴다. 관측·방향·충돌·실제 정지 조건은
        그대로 요구하며 보정 뒤 같은 벽까지의 거리가 줄었는지 확인한다.
        """
        reference.require_context(*self._inputs.context())
        self._motion.wait_stopped(check)
        distance, angle = self._inputs.wall_error(check)
        c = self._wall
        excess = distance-c['target_distance']-c['max_distance']
        if not all(math.isfinite(v) for v in (distance, angle)):
            raise ValueError('벽 관측 비정상')
        if excess <= 0:
            return None
        if excess > .03 or abs(angle) > .05 or abs(wrap(angle-c['target_angle'])) > c['max_yaw']:
            raise RuntimeError(f'벽 보정 접근 범위 초과: 초과거리={excess:.6f}m, 방향={angle:.6f}rad')
        current = self._inputs.pose(0, check)
        length = (excess+.01)/math.cos(angle)
        if length > .041:
            raise RuntimeError('벽 보정 접근 총거리 초과')
        x, y, yaw = current
        count = max(1, math.ceil(length/.002))
        path = tuple((x+length*i/count*math.cos(yaw),
                      y+length*i/count*math.sin(yaw), yaw) for i in range(count+1))
        live = self._guard('window', path, check)
        def monitor() -> None:
            check()
            reference.require_context(*self._inputs.context())
            live()
            px, py, heading = self._inputs.pose(0, check)
            along = (px-x)*math.cos(yaw)+(py-y)*math.sin(yaw)
            cross = -(px-x)*math.sin(yaw)+(py-y)*math.cos(yaw)
            if not -.003 <= along <= length+.005 or abs(cross) > .005 or abs(wrap(heading-yaw)) > .035:
                raise RuntimeError('벽 보정 접근 경로 이탈')
            observed, normal = self._inputs.wall_error(check)
            if (not all(math.isfinite(v) for v in (observed, normal))
                    or abs(observed-(distance-along*math.cos(angle))) > .015
                    or abs(wrap(heading+normal-yaw-angle)) > .035):
                raise RuntimeError('벽 보정 중 관측 불일치')
        def validate(stamp: int, stopped_check: Check) -> dict:
            stopped_check()
            reference.require_context(*self._inputs.context())
            px, py, heading = self._inputs.pose(stamp, stopped_check)
            remaining, observed_angle = self._inputs.wall_error(stopped_check)
            along = (px-x)*math.cos(yaw)+(py-y)*math.sin(yaw)
            predicted = distance-along*math.cos(angle)
            normal_change = wrap(heading+observed_angle-yaw-angle)
            if (not all(math.isfinite(v) for v in (remaining, observed_angle))
                    or math.dist((px,py),path[-1][:2]) > .008
                    or abs(remaining-predicted) > .015 or abs(normal_change) > .035
                    or not -c['distance_tolerance'] <= remaining-c['target_distance'] <= c['max_distance']):
                raise RuntimeError('벽 보정 후 재관측 불일치 또는 접근 범위 미확보')
            return dict(accepted=True, approach_m=along, wall_distance=remaining)
        route = RoutePlan(uuid.uuid4().hex, '', reference.odom_frame,
                          tuple(p[:2] for p in path), (), length, tuple(p[2] for p in path))
        return NavigationStep(route, yaw, validate, monitor)

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
            if hasattr(self._inputs, 'alignment_pose'):
                limit = reference.arc_spec.endpoint_tolerance if policy.reentry_position is None else policy.reentry_position
                current = self._inputs.alignment_pose(target[:2], limit, check)
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
        if stage == 'align':
            limit = reference.arc_spec.endpoint_tolerance if policy.reentry_position is None else policy.reentry_position
            guard = self._guard(stage, guard_path, check, envelope=(target[:2], limit))
        else:
            guard = self._guard(stage, guard_path, check)

        def monitor() -> None:
            reference.require_context(*self._inputs.context())
            guard()
            if stage == 'align' and hasattr(self._inputs, 'alignment_pose'):
                pose = self._inputs.alignment_pose(target[:2], reference.arc_spec.endpoint_tolerance
                    if policy.reentry_position is None else policy.reentry_position, check, origin=current)
            else:
                pose = self._inputs.pose(0, check)
            if stage in ('departure', 'return'):
                limits = reference.arc_spec
                if stage == 'return':
                    limits = replace(limits, yaw_tolerance=max(limits.yaw_tolerance, policy.motion_heading))
                check_motion(reference.arc_origin_odom, pose, limits)
            elif stage == 'retreat':
                retreat_error(retreat, pose)
            elif stage == 'align':
                # 5mm 증명 재사용 한계는 runtime의 현재 자세 충돌 재검사로 담당한다.
                # 실제 재진입 가능 영역과 회전 범위는 시작 기준에 고정한다.
                limit = reference.arc_spec.endpoint_tolerance if policy.reentry_position is None else policy.reentry_position
                if math.dist(pose[:2], target[:2]) > limit or abs(wrap(pose[2]-current[2])) > math.radians(16):
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
                # 정지 후 방향 잔차만 재보정한다. 위치 이탈·관측 오류는 재시도하지 않는다.
                from farm_navigation.arrival import ArrivalValidationError
                distance=math.dist(pose[:2],target[:2])
                heading=abs(wrap(pose[2]-target[2]))
                limit=(reference.arc_spec.endpoint_tolerance if policy.reentry_position is None
                       else policy.reentry_position)
                if distance <= limit and heading > policy.alignment_heading:
                    raise ArrivalValidationError(dict(position_error_m=distance,
                        heading_error_rad=heading,heading_limit_rad=policy.alignment_heading),stamp)
                result = reference.check_reentry(pose, heading_limit=policy.alignment_heading,
                                                 position_limit=policy.reentry_position)
            elif stage == 'wall':
                distance, angle = self._inputs.wall_error(stopped_check)
                error = wrap(angle-self._wall['target_angle'])
                return dict(final_distance=distance, final_angle_error=error,
                    accepted=abs(distance-self._wall['target_distance']) <= self._wall['distance_tolerance']
                        and abs(error) <= self._wall['angle_tolerance'])
            else:
                limits = replace(reference.arc_spec, yaw_tolerance=max(reference.arc_spec.yaw_tolerance, policy.motion_heading))
                # 실행 중 경로 검사는 monitor가 담당한다. 정지 후 판정에서는
                # 명시 선택한 완료 허용치를 더 엄격한 경로 한계로 다시 덮어쓰지 않는다.
                stopped_check()
                result = (check_motion(reference.arc_origin_odom, pose, limits)
                          if policy.return_endpoint_position is None else
                          measure(reference.arc_origin_odom, pose, limits))
                endpoint_limit = (limits.endpoint_tolerance if policy.return_endpoint_position is None
                                  else policy.return_endpoint_position)
                result.update(endpoint_error=math.dist(pose[:2], reference.arc_origin_odom[:2]),
                              yaw_error=abs(wrap(pose[2]-reference.arc_origin_odom[2])))
                if result['endpoint_error'] > endpoint_limit or result['yaw_error'] > policy.return_heading:
                    raise RuntimeError('복귀 종료 위치·방향 오차 초과 '
                        f"(위치={result['endpoint_error']:.6f}m/{endpoint_limit:.6f}m, "
                        f"방향={result['yaw_error']:.6f}rad/{policy.return_heading:.6f}rad)")
                if self._window_correction:
                    return dict(result, accepted=True, window_pending=True)
                result['map_arrival'] = reference.arrival_validator(self._poses,
                    map_id=reference.map_id, window_id=reference.window_id, session_id=reference.session_id,
                    position_limit=policy.return_position, heading_limit=policy.return_heading)(stamp, stopped_check)
                result['accepted'] = result['map_arrival']['accepted']
                return result
            return dict(result, accepted=True)

        if stage == 'align':
            current = self._inputs.pose(0, check)
            angle, _ = alignment(reference, current)
            return AlignmentStep(angle, policy.spin_allowance, abs(angle) <= policy.alignment_skip, validate, monitor)
        return NavigationStep(route, path[-1][2], validate, monitor,
            reverse=stage == 'retreat',
            stationary_only=retreat is not None and retreat.distance <= .005,
            wall_parameters=dict(self._wall) if stage == 'wall' else None)
