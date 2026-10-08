"""렌더 프레임 경계에서 물리 주기만 전환하는 시뮬 전용 스케줄러입니다.

정책·ROS·센서 주기를 실행하거나 임무 상태를 판정하지 않습니다. 호출자는 매번
같은 frame_dt만큼 진행한 실제 world.current_time을 공통 시간 기준으로 사용합니다.
"""
from collections.abc import Callable, Iterable
import math
import time
from typing import Any


class AdaptivePhysicsTicks:
    """한 렌더 프레임 동안 같은 dt로 외력→물리 tick을 반복합니다.

World는 최초 physics_hz와 render_hz로 초기화되어 있어야 합니다. 주기 변경은
공개 PhysicsContext.set_physics_dt API만 사용하며 stop/reset을 호출하지 않습니다.
batch_usd_writeback을 켜면 중간 tick의 USD 쓰기를 생략하므로 외력·접촉
콜백은 PhysX tensor를 읽어야 합니다. USD 조회는 프레임 경계에서만 합니다.
    """

    def __init__(self, physics_hz: float, render_hz: float,
                 allowed_hz: Iterable[float] = (60, 120, 240, 480), *,
                 batch_usd_writeback: bool = False) -> None:
        if type(batch_usd_writeback) is not bool:
            raise ValueError('USD 쓰기 일괄 처리 여부는 bool이어야 합니다.')
        self.batch_usd_writeback = batch_usd_writeback
        self.render_hz = self._positive_rate(render_hz, '렌더')
        self.frame_dt = 1. / self.render_hz
        self.allowed_hz = tuple(sorted(set(self._positive_rate(value, '허용 물리') for value in allowed_hz)))
        if not self.allowed_hz:
            raise ValueError('허용 물리 주기는 하나 이상이어야 합니다.')
        for rate in self.allowed_hz:
            if not rate.is_integer():
                raise ValueError('SDK 물리 주파수는 정수 Hz여야 합니다.')
            ratio = rate / self.render_hz
            if ratio < 1 or not math.isclose(ratio, round(ratio), rel_tol=0., abs_tol=1e-10):
                raise ValueError('허용 물리 주기는 렌더 주기의 정수 배여야 합니다.')
        self.physics_hz = self._requested_rate(physics_hz)
        self.dt = 1. / self.physics_hz
        self.frame_count = 0
        self.total_ticks = 0
        self._last_frame_time: float | None = None
        self.frame_timings: dict[str, float] = {}

    def allow_rate(self, value: float) -> None:
        """시험 UI에서 검증한 렌더 정수 배의 물리 주기를 등록한다."""
        rate = self._positive_rate(value, '시험 물리')
        ratio = rate / self.render_hz
        if not rate.is_integer() or ratio < 1 or not math.isclose(ratio, round(ratio)):
            raise ValueError('시험 물리 주기는 렌더 주기의 정수 배여야 합니다.')
        if rate not in self.allowed_hz:
            self.allowed_hz = tuple(sorted((*self.allowed_hz, rate)))

    @staticmethod
    def _positive_rate(value: float, label: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(label + ' 주기는 유한한 양수여야 합니다.') from error
        if not math.isfinite(result) or result <= 0:
            raise ValueError(label + ' 주기는 유한한 양수여야 합니다.')
        return result

    def _requested_rate(self, value: float) -> float:
        result = self._positive_rate(value, '요청 물리')
        if result not in self.allowed_hz:
            raise ValueError(f'허용되지 않은 물리 주파수입니다: {result}; 허용값={self.allowed_hz}')
        return result

    @staticmethod
    def _time(world: Any) -> float:
        result = float(world.current_time)
        if not math.isfinite(result) or result < 0:
            raise RuntimeError('시뮬레이션 시간은 유한한 음수 아닌 값이어야 합니다.')
        return result

    def step_frame(self, world: Any, physics: Any = None, *, physics_hz: float | None = None,
                   post_step: Callable[[float, float], None] | None = None) -> None:
        """요청 주기로 한 frame_dt 진행하고 렌더합니다. 전환은 첫 tick 전에만 합니다."""
        requested = self.physics_hz if physics_hz is None else self._requested_rate(physics_hz)
        before_frame = self._time(world)
        if self._last_frame_time is not None and not math.isclose(
                before_frame, self._last_frame_time, rel_tol=0., abs_tol=1e-10):
            raise RuntimeError('프레임 사이 시뮬레이션 시간 변경/reset을 감지했습니다.')
        context = world.get_physics_context()
        if requested != self.physics_hz:
            context.set_physics_dt(1. / requested, substeps=round(requested / self.render_hz))
            if not math.isclose(self._time(world), before_frame, rel_tol=0., abs_tol=1e-10):
                raise RuntimeError('물리 주기 전환 중 시뮬레이션 시간이 변경됐습니다.')
            self.physics_hz = requested
            self.dt = 1. / requested
        # 공개 getter가 있는 World에서는 외부의 dt 변경도 첫 외력 적용 전에 감지합니다.
        get_dt = getattr(context, 'get_physics_dt', None)
        if callable(get_dt) and not math.isclose(float(get_dt()), self.dt, rel_tol=1e-9, abs_tol=1e-12):
            raise RuntimeError(
                f'Isaac 물리 dt와 스케줄러 주기가 다릅니다: actual={get_dt()!r}, '
                f'expected={self.dt!r}, frame={self.frame_count}, requested_hz={requested}')
        forces_s = simulation_s = contacts_s = 0.
        tick_count = round(self.physics_hz / self.render_hz)
        writeback = (tuple(context.get_physx_update_transformations_settings())
                     if self.batch_usd_writeback and tick_count > 1 else None)
        if writeback is not None and (len(writeback) != 3 or any(type(value) is not bool for value in writeback)):
            raise RuntimeError(f'PhysX USD 쓰기 설정은 bool 세 값이어야 합니다: actual={writeback}')
        try:
            for tick in range(tick_count):
                before = self._time(world)
                started = time.perf_counter()
                if physics is not None:
                    physics.update(self.dt, before)
                forces_s += time.perf_counter() - started
                started = time.perf_counter()
                if writeback is not None:
                    if tick == 0:
                        context.set_physx_update_transformations_settings(False, False, writeback[2])
                    elif tick == tick_count - 1:
                        context.set_physx_update_transformations_settings(*writeback)
                world.step(render=False)
                simulation_s += time.perf_counter() - started
                elapsed = self._time(world) - before
                if not math.isclose(elapsed, self.dt, rel_tol=1e-5, abs_tol=1e-8):
                    raise RuntimeError('Isaac 물리 tick이 설정 간격과 다릅니다.')
                if post_step is not None:
                    started = time.perf_counter()
                    post_step(self.dt, self._time(world))
                    contacts_s += time.perf_counter() - started
                self.total_ticks += 1
        finally:
            if writeback is not None:
                context.set_physx_update_transformations_settings(*writeback)
        after_physics = self._time(world)
        if not math.isclose(after_physics - before_frame, self.frame_dt, rel_tol=1e-5, abs_tol=1e-8):
            raise RuntimeError('한 렌더 프레임의 물리 진행 시간이 다릅니다.')
        started = time.perf_counter()
        world.render()
        self.frame_timings = dict(forces_s=forces_s, simulation_s=simulation_s,
                                  contacts_s=contacts_s, render_s=time.perf_counter()-started)
        after_render = self._time(world)
        if not math.isclose(after_render, after_physics, rel_tol=0., abs_tol=1e-10):
            raise RuntimeError('렌더 중 물리 시간이 추가로 진행됐습니다.')
        self.frame_count += 1
        self._last_frame_time = after_render
