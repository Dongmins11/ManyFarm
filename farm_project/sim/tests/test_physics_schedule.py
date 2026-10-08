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

    def test_ui_rate_preserves_render_interval(self) -> None:
        schedule, world = AdaptivePhysicsTicks(60, 60), WorldFixture(60)
        schedule.allow_rate(180)
        schedule.step_frame(world, physics_hz=180)
        self.assertEqual(schedule.total_ticks, 3)
        self.assertAlmostEqual(world.current_time, 1/60)
        self.assertEqual(set(schedule.frame_timings),
                         {'forces_s', 'simulation_s', 'contacts_s', 'render_s'})
        with self.assertRaises(ValueError):
            schedule.allow_rate(100)

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

    def test_batched_writeback_preserves_ticks_contacts_and_frame_boundary(self) -> None:
        for hz in (120, 240, 480):
            with self.subTest(hz=hz):
                schedule, world = AdaptivePhysicsTicks(hz, 60, batch_usd_writeback=True), WorldFixture(hz)
                contacts = []
                def observe(dt: float, now: float) -> None:
                    contacts.append((dt, now, world.context.writeback))
                schedule.step_frame(world, AttachmentFixture(world), post_step=observe)
                expected = [(False, False, False)] * (hz // 60 - 1) + [(True, True, False)]
                self.assertEqual(world.step_writeback, expected)
                self.assertEqual([sample[2] for sample in contacts], expected)
                self.assertEqual(world.render_writeback, [(True, True, False)])
                self.assertEqual((schedule.total_ticks, schedule.frame_count), (hz // 60, 1))
                self.assertAlmostEqual(world.current_time, 1 / 60)
                self.assertEqual(len([event for event in world.events if event[0] == 'force']), hz // 60)

    def test_writeback_opt_in_and_single_tick_never_access_settings(self) -> None:
        for hz, enabled in ((480, False), (60, False), (60, True)):
            with self.subTest(hz=hz, enabled=enabled):
                schedule = AdaptivePhysicsTicks(hz, 60, batch_usd_writeback=enabled)
                world = WorldFixture(hz)
                schedule.step_frame(world)
                self.assertEqual(world.context.writeback_reads, 0)
                self.assertEqual(world.context.writeback_calls, [])
                self.assertEqual(world.step_writeback, [(True, True, False)] * (hz // 60))

    def test_batched_writeback_preserves_original_flags_and_rate_changes(self) -> None:
        schedule, world = AdaptivePhysicsTicks(60, 60, batch_usd_writeback=True), WorldFixture(60)
        world.context.writeback = (True, False, True)
        for rate in (60, 480, 60):
            schedule.step_frame(world, physics_hz=rate)
        self.assertEqual(world.context.writeback_reads, 1)
        self.assertEqual(world.step_writeback, [(True, False, True)] +
                         [(False, False, True)] * 7 + [(True, False, True)] * 2)
        self.assertEqual(world.render_writeback, [(True, False, True)] * 3)
        self.assertEqual(world.context.writeback, (True, False, True))
        self.assertAlmostEqual(world.current_time, 3 / 60)

    def test_batched_writeback_restores_after_tick_or_callback_failure(self) -> None:
        for failure in ('force', 'step', 'contact'):
            with self.subTest(failure=failure):
                schedule, world = AdaptivePhysicsTicks(480, 60, batch_usd_writeback=True), WorldFixture(480)
                class FailedAttachment:
                    def update(self, dt_s: float, sim_time_s: float) -> None:
                        if failure == 'force' and sim_time_s > 0:
                            raise RuntimeError('force failed')
                def observe(dt: float, now: float) -> None:
                    if failure == 'contact':
                        raise RuntimeError('contact failed')
                if failure == 'step':
                    world.step_multiplier = 0.
                with self.assertRaises(RuntimeError):
                    schedule.step_frame(world, FailedAttachment(), post_step=observe)
                self.assertEqual(world.context.writeback, (True, True, False))
                self.assertEqual(world.context.writeback_calls[-1], (True, True, False))
                self.assertEqual(world.render_writeback, [])

    def test_invalid_writeback_settings_fail_before_stepping(self) -> None:
        schedule, world = AdaptivePhysicsTicks(480, 60, batch_usd_writeback=True), WorldFixture(480)
        world.context.writeback = (True, True)
        with self.assertRaisesRegex(RuntimeError, 'bool 세 값'):
            schedule.step_frame(world)
        self.assertEqual(world.events, [])
        self.assertEqual(world.context.writeback_calls, [])


if __name__ == '__main__':
    unittest.main()
