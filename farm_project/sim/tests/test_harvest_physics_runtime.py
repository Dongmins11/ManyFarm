"""Isaac 없이 실제 시간 분주 helper와 장치별 물리 프로파일 계약을 검사합니다."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.harvest_physics import PhysicsTicks, load_physics_profile


class WorldFixture:
    """물리 step과 render의 시간 진행을 독립 제어하는 최소 World 대역입니다."""

    def __init__(self, dt: float, *, start: float = 0.0, render_dt: float = 0.0) -> None:
        self.dt = dt
        self.current_time = start
        self.render_dt = render_dt
        self.events: list[tuple] = []

    def step(self, render: bool) -> None:
        self.events.append(('step', self.current_time, render))
        self.current_time += self.dt

    def render(self) -> None:
        self.events.append(('render', self.current_time))
        self.current_time += self.render_dt


class AttachmentFixture:
    """같은 event 배열에 외력 갱신 순서와 dt를 기록합니다."""

    def __init__(self, world: WorldFixture) -> None:
        self.world = world

    def update(self, dt_s: float, sim_time_s: float) -> None:
        self.world.events.append(('force', sim_time_s, dt_s))


class PhysicsTicksTests(unittest.TestCase):
    def test_480hz_force_before_every_tick_and_60hz_render(self) -> None:
        ticks = PhysicsTicks(480, 60)
        world = WorldFixture(1 / 480)
        attachment = AttachmentFixture(world)
        for _ in range(960):
            ticks.step(world, attachment)
        self.assertAlmostEqual(world.current_time, 2.0)
        self.assertEqual(ticks.tick, 960)
        force = [event for event in world.events if event[0] == 'force']
        steps = [event for event in world.events if event[0] == 'step']
        rendered = [event for event in world.events if event[0] == 'render']
        self.assertEqual((len(force), len(steps), len(rendered)), (960, 960, 120))
        for index, event in enumerate(world.events):
            if event[0] == 'step':
                previous = world.events[index - 1]
                self.assertEqual(previous, ('force', event[1], 1 / 480))
                self.assertIs(event[2], False)
        for index, event in enumerate(rendered, 1):
            self.assertAlmostEqual(event[1], index / 60)

    def test_legacy_60hz_without_attachments_stays_one_tick_per_render(self) -> None:
        ticks = PhysicsTicks(60, 60)
        world = WorldFixture(1 / 60)
        for _ in range(60):
            ticks.step(world)
        self.assertAlmostEqual(world.current_time, 1.0)
        self.assertEqual([event[0] for event in world.events], ['step', 'render'] * 60)
        self.assertTrue(all(event[2] is False for event in world.events if event[0] == 'step'))

    def test_invalid_or_nonintegral_rates_are_rejected(self) -> None:
        for physics, render in [(0, 60), (480, 0), (-480, 60), (60, 480),
                                (480, 59), (float('inf'), 60), (480, float('nan'))]:
            with self.subTest(physics=physics, render=render):
                with self.assertRaises(ValueError):
                    PhysicsTicks(physics, render)

    def test_wrong_physics_dt_is_rejected_before_render(self) -> None:
        for actual_dt in [0, 1 / 240, -1 / 480]:
            with self.subTest(actual_dt=actual_dt):
                ticks = PhysicsTicks(480, 60)
                world = WorldFixture(actual_dt)
                with self.assertRaisesRegex(RuntimeError, '물리 tick'):
                    ticks.step(world, AttachmentFixture(world))
                self.assertEqual(ticks.tick, 0)
                self.assertEqual([event[0] for event in world.events], ['force', 'step'])

    def test_render_cannot_advance_time_even_at_large_sim_time(self) -> None:
        for start in [0.0, 10_000_000.0]:
            with self.subTest(start=start):
                ticks = PhysicsTicks(480, 60)
                world = WorldFixture(1 / 480, start=start, render_dt=1 / 480)
                for _ in range(7):
                    ticks.step(world)
                with self.assertRaisesRegex(RuntimeError, '렌더 중'):
                    ticks.step(world)

    def test_force_update_error_does_not_step_physics(self) -> None:
        class FailedAttachment:
            def update(self, dt_s: float, sim_time_s: float) -> None:
                raise RuntimeError('force failed')

        world = WorldFixture(1 / 480)
        ticks = PhysicsTicks(480, 60)
        with self.assertRaisesRegex(RuntimeError, 'force failed'):
            ticks.step(world, FailedAttachment())
        self.assertEqual(world.events, [])
        self.assertEqual(world.current_time, 0)


class ProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        (self.root / 'sim').mkdir()
        self.path = self.root / 'sim/physics.json'
        self.profile = dict(enabled=True, physics_hz=60, render_hz=30, control_hz=20,
                            stem=dict(stem_response_version=6))
        self.path.write_text(json.dumps(self.profile))
        self.devices = [dict(robot_id=name, runtime=dict(physics_hz=60, render_hz=30,
                        robotarm_physics_config='sim/physics.json')) for name in ('scout_01', 'harvest_01')]

    def test_all_deployed_devices_load_the_same_profile(self) -> None:
        config = ROOT / 'sim/ros_ws/src/farm_sim_config/config'
        devices = [json.loads((config / f'{name}.json').read_text()) for name in ('scout', 'scout_fleet', 'harvest')]
        profile = load_physics_profile(ROOT, devices)
        self.assertTrue(profile['enabled'])
        self.assertEqual((profile['physics_hz'], profile['render_hz']), (60, 30))
        self.assertEqual(profile['fruit']['mass_kg'], profile['stem']['mass'])

    def test_mismatched_device_physics_or_render_rate_is_rejected(self) -> None:
        for key, value in [('physics_hz', 480), ('render_hz', 60)]:
            with self.subTest(key=key):
                devices = deepcopy(self.devices)
                devices[1]['runtime'][key] = value
                with self.assertRaisesRegex(ValueError, key):
                    load_physics_profile(self.root, devices)

    def test_legacy_profile_is_rejected_even_when_all_devices_match(self) -> None:
        self.profile['physics_hz'] = 480
        self.path.write_text(json.dumps(self.profile))
        for device in self.devices:
            device['runtime']['physics_hz'] = 480
        with self.assertRaisesRegex(ValueError, 'physics_hz'):
            load_physics_profile(self.root, self.devices)

    def test_mixed_or_missing_profile_is_rejected(self) -> None:
        for replacement in ['sim/other.json', None]:
            with self.subTest(profile=replacement):
                devices = deepcopy(self.devices)
                devices[1]['runtime']['harvest_arm'] = dict(enabled=True)
                devices[1]['runtime']['robotarm_physics_config'] = replacement
                with self.assertRaisesRegex(ValueError, '같은 robotarm'):
                    load_physics_profile(self.root, devices)

    def test_non_arm_transport_shares_world_physics_without_own_profile(self) -> None:
        devices = deepcopy(self.devices)
        devices.append(dict(robot_id='transport_01', runtime=dict(physics_hz=60, render_hz=30)))
        self.assertEqual(load_physics_profile(self.root, devices), self.profile)
        self.assertIsNone(load_physics_profile(self.root, devices[-1:]))

    def test_profile_outside_sim_is_rejected_before_read(self) -> None:
        for path in ['outside.json', 'sim/../outside.json']:
            with self.subTest(path=path):
                devices = deepcopy(self.devices)
                for device in devices:
                    device['runtime']['robotarm_physics_config'] = path
                with self.assertRaisesRegex(ValueError, 'sim 안'):
                    load_physics_profile(self.root, devices)

    def test_absent_and_explicitly_disabled_profile_preserve_legacy_mode(self) -> None:
        devices = deepcopy(self.devices)
        for device in devices:
            del device['runtime']['robotarm_physics_config']
        self.assertIsNone(load_physics_profile(self.root, devices))
        self.profile['enabled'] = False
        self.path.write_text(json.dumps(self.profile))
        self.assertIsNone(load_physics_profile(self.root, self.devices))


if __name__ == '__main__':
    unittest.main()
