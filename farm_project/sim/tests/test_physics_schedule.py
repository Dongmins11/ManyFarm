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

    def set_physics_dt(self, dt: float, substeps: int = 1) -> None:
        self.world.events.append(('rate', self.world.current_time, dt, substeps))
        self.world.dt = dt
        self.world.current_time += self.world.switch_time_error

    def get_physics_dt(self) -> float:
        return self.world.dt


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

    def get_physics_context(self) -> ContextFixture:
        return self.context

    def step(self, render: bool) -> None:
        self.events.append(('step', self.current_time, render))
        self.current_time += self.dt * self.step_multiplier

    def render(self) -> None:
        self.events.append(('render', self.current_time))
        self.current_time += self.render_time_error


class AttachmentFixture:
    def __init__(self, world: WorldFixture) -> None:
        self.world = world

    def update(self, dt_s: float, sim_time_s: float) -> None:
        self.world.events.append(('force', sim_time_s, dt_s))


class AdaptivePhysicsTicksTests(unittest.TestCase):
    def test_60_480_60_keep_two_seconds_and_force_before_every_tick(self) -> None:
        world = WorldFixture(60, start=3.25)
        schedule = AdaptivePhysicsTicks(60, 60)
        attachment = AttachmentFixture(world)
        for rate, frames in ((60, 30), (480, 60), (60, 30)):
            for _ in range(frames):
                schedule.step_frame(world, attachment, physics_hz=rate)
        self.assertEqual((schedule.frame_count, schedule.total_ticks), (120, 540))
        self.assertAlmostEqual(world.current_time, 5.25)
        self.assertEqual((schedule.physics_hz, schedule.dt, schedule.frame_dt), (60, 1/60, 1/60))
        renders = [event for event in world.events if event[0] == 'render']
        changes = [event for event in world.events if event[0] == 'rate']
        self.assertEqual(len(renders), 120)
        self.assertEqual([(event[2], event[3]) for event in changes], [(1/480, 8), (1/60, 1)])
        self.assertAlmostEqual(changes[0][1], 3.75)
        self.assertAlmostEqual(changes[1][1], 4.75)
        for frame, event in enumerate(renders, 1):
            self.assertAlmostEqual(event[1], 3.25+frame/60)
        for index, event in enumerate(world.events):
            if event[0] == 'step':
                previous = world.events[index-1]
                self.assertEqual(previous[:2], ('force', event[1]))
                self.assertIs(event[2], False)
            elif event[0] == 'rate':
                self.assertEqual(world.events[index-1][0], 'render')

    def test_contact_observer_runs_after_every_tick_before_render(self) -> None:
        world = WorldFixture(480)
        schedule = AdaptivePhysicsTicks(480, 60)
        def observe(dt: float, now: float) -> None:
            self.assertEqual(world.events[-1][0], 'step')
            self.assertAlmostEqual(now, world.current_time)
            world.events.append(('contact', now, dt))
        schedule.step_frame(world, AttachmentFixture(world), post_step=observe)
        contacts = [event for event in world.events if event[0] == 'contact']
        self.assertEqual(len(contacts), 8)
        for i, event in enumerate(contacts, 1):
            self.assertAlmostEqual(event[1], i/480)
            self.assertAlmostEqual(event[2], 1/480)
        self.assertEqual(world.events[-1][0], 'render')

    def test_intermediate_rates_and_no_attachment(self) -> None:
        schedule, world = AdaptivePhysicsTicks(60, 60), WorldFixture(60)
        for rate in (120, 240, 480, 60):
            schedule.step_frame(world, physics_hz=rate)
        self.assertEqual((schedule.frame_count, schedule.total_ticks), (4, 15))
        self.assertAlmostEqual(world.current_time, 4/60)
        self.assertNotIn('force', [event[0] for event in world.events])

    def test_invalid_rate_or_noninteger_render_ratio_rejected(self) -> None:
        for physics, render, allowed in ((0, 60, (60,)), (60, 0, (60,)),
                (float('nan'), 60, (60,)), (60, float('inf'), (60,)),
                (60, 59, (60,)), (60, 120, (60,)), (60, 60, ()),
                (60, 60, (60, 90)), (60, 30, (60, 60.5)), (480, 60, (60,))):
            with self.subTest(physics=physics, render=render, allowed=allowed):
                with self.assertRaises(ValueError):
                    AdaptivePhysicsTicks(physics, render, allowed)
        schedule, world = AdaptivePhysicsTicks(60, 60), WorldFixture(60)
        for rate in (0, -60, 90, float('nan'), float('inf')):
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError):
                    schedule.step_frame(world, physics_hz=rate)
        self.assertEqual(world.events, [])

    def test_render_cannot_advance_time_at_large_absolute_time(self) -> None:
        for start in (0., 10_000_000.):
            with self.subTest(start=start):
                schedule, world = AdaptivePhysicsTicks(480, 60), WorldFixture(480, start)
                world.render_time_error = 1/480
                with self.assertRaisesRegex(RuntimeError, '렌더 중'):
                    schedule.step_frame(world)
                self.assertEqual(schedule.frame_count, 0)

    def test_rate_switch_cannot_reset_or_advance_time(self) -> None:
        for error in (-1., 1/480):
            with self.subTest(error=error):
                schedule, world = AdaptivePhysicsTicks(60, 60), WorldFixture(60, 1.)
                world.switch_time_error = error
                with self.assertRaisesRegex(RuntimeError, '주기 전환 중'):
                    schedule.step_frame(world, physics_hz=480)
                self.assertEqual((schedule.total_ticks, schedule.frame_count), (0, 0))
                self.assertEqual(schedule.physics_hz, 60)
                self.assertEqual([event[0] for event in world.events], ['rate'])

    def test_external_reset_or_time_change_between_frames_rejected(self) -> None:
        for value in (0., 3., float('nan'), float('inf'), -1.):
            with self.subTest(value=value):
                schedule, world = AdaptivePhysicsTicks(60, 60), WorldFixture(60, 1.)
                schedule.step_frame(world)
                world.current_time = value
                with self.assertRaises(RuntimeError):
                    schedule.step_frame(world)
                self.assertEqual((schedule.total_ticks, schedule.frame_count), (1, 1))

    def test_incorrect_physics_step_or_external_dt_rejected(self) -> None:
        schedule, world = AdaptivePhysicsTicks(60, 60), WorldFixture(480)
        with self.assertRaisesRegex(RuntimeError, '물리 dt'):
            schedule.step_frame(world, AttachmentFixture(world))
        self.assertEqual(world.events, [])
        for multiplier in (0., -1., 2.):
            with self.subTest(multiplier=multiplier):
                schedule, world = AdaptivePhysicsTicks(60, 60), WorldFixture(60, 1.)
                world.step_multiplier = multiplier
                with self.assertRaisesRegex(RuntimeError, '물리 tick'):
                    schedule.step_frame(world)
                self.assertEqual(schedule.total_ticks, 0)
                self.assertNotIn('render', [event[0] for event in world.events])

    def test_force_failure_never_steps_physics(self) -> None:
        class FailedAttachment:
            def update(self, dt_s: float, sim_time_s: float) -> None:
                raise RuntimeError('force failed')

        schedule, world = AdaptivePhysicsTicks(480, 60), WorldFixture(480)
        with self.assertRaisesRegex(RuntimeError, 'force failed'):
            schedule.step_frame(world, FailedAttachment())
        self.assertEqual(world.events, [])
        self.assertEqual((schedule.frame_count, schedule.total_ticks), (0, 0))


if __name__ == '__main__':
    unittest.main()
