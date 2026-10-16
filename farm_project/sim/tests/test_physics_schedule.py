"""실제 SDK 공개 인터페이스 형태의 대역으로 가변 dt의 시간·외력 순서를 검사합니다."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.physics_schedule import AdaptivePhysicsTicks


class ContextFixture:
    """set_physics_dt는 누적 시각을 바꾸지 않는 SDK 계약을 재현합니다."""

    def __init__(self, world: 'WorldFixture') -> None:
        self.world = world
        self.writeback = (True, True, False)
        self.writeback_reads = 0
        self.writeback_calls: list[tuple[bool, bool, bool]] = []

    def set_physics_dt(self, dt: float, substeps: int = 1) -> None:
        self.world.events.append(('rate', self.world.current_time, dt, substeps))
        self.world.dt = dt
        self.world.current_time += self.world.switch_time_error

    def get_physics_dt(self) -> float:
        return self.world.dt

    def get_physx_update_transformations_settings(self) -> tuple[bool, bool, bool]:
        self.writeback_reads += 1
        return self.writeback

    def set_physx_update_transformations_settings(self, update_to_usd: bool,
                                                 update_velocities_to_usd: bool,
                                                 output_velocities_local_space: bool) -> None:
        self.writeback = (update_to_usd, update_velocities_to_usd, output_velocities_local_space)
        self.writeback_calls.append(self.writeback)


class WorldFixture:
    """reset/stop을 제공하지 않아 스케줄러가 그 API에 의존하면 바로 실패합니다."""

    def __init__(self, hz: float, start: float = 0.) -> None:
        self.dt = 1. / hz
        self.current_time = start
        self.events: list[tuple] = []
        self.context = ContextFixture(self)
        self.render_time_error = 0.
        self.switch_time_error = 0.
        self.step_multiplier = 1.
        self.step_writeback: list[tuple[bool, bool, bool]] = []
        self.render_writeback: list[tuple[bool, bool, bool]] = []

    def get_physics_context(self) -> ContextFixture:
        return self.context

    def step(self, render: bool) -> None:
        self.events.append(('step', self.current_time, render))
        self.step_writeback.append(self.context.writeback)
        self.current_time += self.dt * self.step_multiplier

    def render(self) -> None:
        self.events.append(('render', self.current_time))
        self.render_writeback.append(self.context.writeback)
        self.current_time += self.render_time_error


class AttachmentFixture:
    def __init__(self, world: WorldFixture) -> None:
        self.world = world

    def update(self, dt_s: float, sim_time_s: float) -> None:
        self.world.events.append(('force', sim_time_s, dt_s))


class AdaptivePhysicsTicksTests(unittest.TestCase):
    def test_60_physics_20_policy_30_render_and_force_order(self):
        world = WorldFixture(60, 3.25); schedule = AdaptivePhysicsTicks(60, 30)
        attachment = AttachmentFixture(world); callbacks = []; policy_times = []
        for index in range(120):
            if index % 3 == 0: policy_times.append(world.current_time)
            schedule.step_frame(world, attachment, post_step=lambda dt, now: callbacks.append((dt, now)))
        self.assertAlmostEqual(world.current_time, 5.25)
        self.assertEqual(schedule.total_ticks, 120)
        self.assertEqual(len(callbacks), 120)
        self.assertEqual(len(policy_times), 40)
        self.assertEqual(sum(e[0]=='render' for e in world.events), 60)
        meaningful = [e[0] for e in world.events if e[0] != 'render']
        self.assertEqual(meaningful, ['force', 'step']*120)
        self.assertTrue(all(abs(b-a-.05)<1e-9 for a,b in zip(policy_times,policy_times[1:])))

    def test_legacy_rates_rejected_before_force_or_time_progress(self):
        for hz in (120, 240, 480, 960):
            with self.assertRaises(ValueError): AdaptivePhysicsTicks(hz, 30)
            world = WorldFixture(60); schedule = AdaptivePhysicsTicks(60, 30)
            with self.assertRaises(ValueError): schedule.allow_rate(hz)
            with self.assertRaises(ValueError): schedule.step_frame(world, physics_hz=hz)
            self.assertEqual(world.events, [])

    def test_reset_external_dt_and_bad_step_rejected(self):
        world = WorldFixture(60); schedule = AdaptivePhysicsTicks(60, 30)
        schedule.step_frame(world)
        world.current_time = 0
        with self.assertRaises(RuntimeError): schedule.step_frame(world)
        world = WorldFixture(480); schedule = AdaptivePhysicsTicks(60, 30)
        with self.assertRaises(RuntimeError): schedule.step_frame(world)
        world = WorldFixture(60); world.step_multiplier = 2
        with self.assertRaises(RuntimeError): AdaptivePhysicsTicks(60, 30).step_frame(world)

    def test_render_cannot_advance_physics(self):
        world = WorldFixture(60); world.render_time_error = 1/60
        schedule = AdaptivePhysicsTicks(60, 30); schedule.step_frame(world)
        with self.assertRaises(RuntimeError): schedule.step_frame(world)
