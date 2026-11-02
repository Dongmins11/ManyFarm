"""차체 단계와 기존 Navigator/SpinClient의 연결. 서버 생성과 설정 변경은 하지 않는다.

경로·완료 판정·실시간 감시는 기존 계산 함수를 사용하는 planner가 제공한다.
출력 소유권과 차단은 운영 구성에서 공급해야 하며 기본 무동작 구현은 없다.
"""
from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Callable, Mapping
from farm_navigation.arrival import ArrivalValidationError

Check = Callable[[], None]


@dataclass(frozen=True)
class NavigationStep:
    route: Any
    yaw: float
    validate: Callable[[int, Check], dict]
    monitor: Check
    reverse: bool = False
    stationary_only: bool = False
    wall_parameters: dict | None = None


@dataclass(frozen=True)
class AlignmentStep:
    angle: float
    allowance_s: float
    skip: bool
    validate: Callable[[int, Check], dict]
    monitor: Check


@dataclass(frozen=True)
class NavigationBinding:
    """호출자가 선택한 전용 ID 설정. 기존 settings 객체를 변경하지 않는다."""
    settings: Any
    client: Any


class HandoffNavigationSteps:
    """단일 작업 스레드에서 호출한다. 실패 시 실행 객체를 보존하여 stop에서 회수한다."""

    def __init__(self, *, node: Any, motion: Any, spin: Any,
                 bindings: Mapping[str, NavigationBinding],
                 capture: Callable[[Check], Any],
                 plan: Callable[[str, Any, Check], NavigationStep | AlignmentStep],
                 check: Check, settling_check: Check,
                 arm_output: Callable[[str], None], stop_output: Check,
                 record: Callable[[dict], None], navigator_factory: Any = None,
                 wall_approach: Callable | None = None) -> None:
        if set(bindings) not in ({'departure', 'wall', 'retreat', 'return'}, {'departure', 'wall', 'retreat', 'return', 'window'}):
            raise ValueError('차체 주행 4단계 연결 필요')
        if navigator_factory is None:
            from farm_navigation.navigator import Navigator
            navigator_factory = Navigator
        self._factory = navigator_factory
        self._node, self._motion, self._spin = node, motion, spin
        self._bindings = {name: NavigationBinding(deepcopy(binding.settings), binding.client)
                          for name, binding in bindings.items()}
        self._capture, self._plan = capture, plan
        self._check, self._settling_check = check, settling_check
        self._arm_output, self._stop_output, self._record = arm_output, stop_output, record
        self._active = None
        self._wall_approach = wall_approach
        self._owns_output = False
        from .handoff_components import PathMotion, SpinMotion, ComponentSteps, SequenceMotion
        actions = {
            name: PathMotion(name, binding, plan, self._navigate_step)
            for name, binding in self._bindings.items()
        }
        if 'window' in actions:
            actions['return'] = SequenceMotion((actions['return'], actions.pop('window')))
        actions['align'] = SpinMotion('align', plan, self._align)
        self.components = ComponentSteps(capture=self._capture_checked,
                                         actions=actions, stop=self.stop)

    def _checked(self, cancel: Check, monitor: Check | None = None) -> Check:
        def check() -> None:
            cancel()
            self._check()
            if monitor is not None:
                monitor()
        return check

    def _capture_checked(self, check: Check) -> Any:
        return self._capture(self._checked(check))

    def capture(self, check: Check) -> Any:
        return self.components.capture(check)

    def execute(self, stage: str, reference: Any, check: Check) -> Any:
        if self._active is not None or self._owns_output:
            raise RuntimeError('이전 차체 동작 정리 필요')
        if stage == 'wall' and self._wall_approach is not None and 'window' in self._bindings:
            checked = self._checked(check)
            step = self._wall_approach(reference, checked)
            if step is not None:
                self._record(dict(stage='wall', event='BOUNDED_APPROACH_START',
                                  distance_m=step.route.distance_m))
                # 기존 0.01m/s 전진 제어기·충돌 검사·정지 확인을 재사용한다.
                result = self._navigate_step('window', self._bindings['window'], step, checked)
                self._record(dict(stage='wall', event='BOUNDED_APPROACH_STOPPED', result=result))
        # 벽/재진입 회전의 정지 후 오차만 최대 2회 재보정한다. 원호는 재실행하지 않는다.
        for attempt in range(3):
            self._checked(check)()
            try:
                return self.components.execute(stage, reference, self._checked(check))
            except ArrivalValidationError as error:
                if stage not in ('wall', 'align'):
                    raise
                self._record(dict(stage=stage, event='STOPPED_ARRIVAL_REJECTED',
                    attempt=attempt+1, measurement=error.measurement, stamp_ns=error.stamp_ns,
                    retry=attempt < 2))
                # 종료/출력 차단 확인이 실패하면 재시도하지 않는다.
                self.stop()
                self._checked(check)()
                if attempt == 2:
                    raise
                self._node.get_logger().warning(
                    f'{stage.upper()}_REALIGN_RETRY: {attempt+1}/2; stopped={error.measurement}')
                # components가 현재 관측으로 새 계획·충돌 검사를 수행한다.

    def _navigate_step(self, stage: str, binding: NavigationBinding,
                       step: NavigationStep, check: Check) -> Any:
        checked = self._checked(check)
        monitored = self._checked(check, step.monitor)
        monitored()
        navigator = self._factory(self._node, binding.settings, binding.client,
            None, self._motion, monitored, explicit_routes=True,
            stop_output=self._stop_output, settling_check=self._settling_check,
            arrival_validator=step.validate, record=self._record)
        self._active = navigator
        if step.wall_parameters is not None:
            binding.client.preflight(monitored, wall_parameters=step.wall_parameters)
        else:
            navigator.preflight_navigation()
        # 발행 경로 활성화 중 예외가 나도 stop에서 차단을 시도한다.
        self._owns_output = True
        self._arm_output(stage)
        monitored()
        if step.stationary_only:
            self._stop_output()
            stamp = self._motion.wait_stopped(self._settling_check)
            result = step.validate(stamp, self._settling_check)
            self._accepted(result)
        else:
            result = navigator.navigate(step.route.points[-1], step.yaw,
                route_plan=step.route, reverse=step.reverse)
        # Navigator가 반환한 뒤에도 이 시점의 취소를 완료로 바꾸지 않는다.
        checked()
        self._stop_output()
        self._owns_output = False
        self._active = None
        return result

    @staticmethod
    def _accepted(result: dict) -> None:
        if result.get('accepted') is not True:
            raise RuntimeError('정지 후 차체 완료 판정 실패')

    def _align(self, step: AlignmentStep, check: Check) -> dict:
        monitored = self._checked(check, step.monitor)
        monitored()
        self._active = self._spin
        if not step.skip and not self._spin.ready():
            raise RuntimeError('Spin 서버 미연결')
        self._owns_output = True
        self._arm_output('align')
        monitored()
        if not step.skip:
            self._spin.execute(step.angle, step.allowance_s, monitored)
        self._stop_output()
        stamp = self._motion.wait_stopped(self._settling_check)
        result = step.validate(stamp, self._settling_check)
        self._accepted(result)
        self._checked(check)()
        self._owns_output = False
        self._active = None
        return result

    def stop(self) -> None:
        """다른 단계·일반 주행의 클라이언트는 취소하지 않는다. 차단 실패도 보고한다."""
        active = self._active
        if active is None and not self._owns_output:
            return
        errors = []
        try:
            if self._owns_output:
                self._stop_output()
        except Exception as error:
            errors.append(str(error))
        try:
            if active is self._spin:
                active.cancel()
            elif active is not None:
                active.cancel_nav()
        except Exception as error:
            errors.append(str(error))
        try:
            self._motion.wait_stopped(self._settling_check)
        except Exception as error:
            errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))
        self._active = None
        self._owns_output = False
