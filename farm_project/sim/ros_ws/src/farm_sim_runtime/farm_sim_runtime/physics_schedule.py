"""60Hz 물리/제어 호출 프레임과30Hz 렌더 요청을 분리한다.

정책·ROS·센서 주기를 실행하거나 임무 상태를 판정하지 않습니다. 호출자는 매번
같은 frame_dt만큼 진행한 실제 world.current_time을 공통 시간 기준으로 사용합니다.
"""
from collections.abc import Callable, Iterable
import math
import time
from typing import Any


class AdaptivePhysicsTicks:
    """매 호출마다60Hz 물리 한 tick을 진행하고 별도로 렌더를 분주한다.

    기존 호출 인터페이스는 유지하되 실행 중 dt 전환은 지원하지 않는다.
    batch_usd_writeback은 호환 인자이며 단일 tick에서 동작 차이가 없다.
    """

    def __init__(self, physics_hz: float, render_hz: float,
                 allowed_hz: Iterable[float] = (60,), *,
                 batch_usd_writeback: bool = False) -> None:
        if type(batch_usd_writeback) is not bool:
            raise ValueError('USD 쓰기 일괄 처리 여부는 bool이어야 합니다.')
        self.batch_usd_writeback = batch_usd_writeback
        self.render_hz = self._positive_rate(render_hz, '렌더')
        self.frame_dt = 1. / 60
        self.render_every = round(60 / self.render_hz)
        if self.render_hz not in (30., 60.):
            raise ValueError("렌더 요청은 30Hz 또는 60Hz여야 합니다.")
        self.allowed_hz = tuple(sorted(set(self._positive_rate(value, '허용 물리') for value in allowed_hz)))
        if self.allowed_hz != (60.,):
            raise ValueError('물리 주기는 60Hz 고정입니다.')
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
        """시험 UI의 요청이 고정60Hz인지 검사한다."""
        rate = self._positive_rate(value, '시험 물리')
        if rate != 60:
            raise ValueError('480Hz 경로는 폐기했습니다. 물리는60Hz 고정입니다.')

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
        """외력→물리 한 tick→접촉 측정→필요한 렌더 순서로 진행한다."""
        requested = self.physics_hz if physics_hz is None else self._requested_rate(physics_hz)
        before_frame = self._time(world)
        if self._last_frame_time is not None and not math.isclose(
                before_frame, self._last_frame_time, rel_tol=0., abs_tol=1e-10):
            raise RuntimeError('프레임 사이 시뮬레이션 시간 변경/reset을 감지했습니다.')
        context = world.get_physics_context()
        # 공개 getter가 있는 World에서는 외부의 dt 변경도 첫 외력 적용 전에 감지합니다.
        get_dt = getattr(context, 'get_physics_dt', None)
        if callable(get_dt) and not math.isclose(float(get_dt()), self.dt, rel_tol=1e-9, abs_tol=1e-12):
            raise RuntimeError(
                f'Isaac 물리 dt와 스케줄러 주기가 다릅니다: actual={get_dt()!r}, '
                f'expected={self.dt!r}, frame={self.frame_count}, requested_hz={requested}')
        forces_s = simulation_s = contacts_s = 0.
        started = time.perf_counter()
        if physics is not None:
            physics.update(self.dt, before_frame)
        forces_s = time.perf_counter()-started
        started = time.perf_counter()
        world.step(render=False)
        simulation_s = time.perf_counter()-started
        if post_step is not None:
            started = time.perf_counter()
            post_step(self.dt, self._time(world))
            contacts_s = time.perf_counter()-started
        self.total_ticks += 1
        after_physics = self._time(world)
        if not math.isclose(after_physics - before_frame, self.frame_dt, rel_tol=1e-5, abs_tol=1e-8):
            raise RuntimeError('한 렌더 프레임의 물리 진행 시간이 다릅니다.')
        started = time.perf_counter()
        if (self.frame_count+1) % self.render_every == 0:
            world.render()
        self.frame_timings = dict(forces_s=forces_s, simulation_s=simulation_s,
                                  contacts_s=contacts_s, render_s=time.perf_counter()-started)
        after_render = self._time(world)
        if not math.isclose(after_render, after_physics, rel_tol=0., abs_tol=1e-10):
            raise RuntimeError('렌더 중 물리 시간이 추가로 진행됐습니다.')
        self.frame_count += 1
        self._last_frame_time = after_render
