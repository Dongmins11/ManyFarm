"""ROS 없는 launch 구성 검사. 프로세스/노드를 기록만 하며 실제 구동 시험은 아닙니다."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def package_path(name: str) -> Path:
    for tree in ('robot', 'sim'):
        candidate = ROOT / tree / 'ros_ws/src' / name
        if candidate.is_dir():
            return candidate
    raise ValueError(name)


class Record:
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


class Declare(Record): pass
class Include(Record): pass
class Process(Record): pass
class Node(Record): pass
class Opaque(Record): pass


class Configuration:
    def __init__(self, name: str, default=None): self.name, self.default = name, default
    def perform(self, context: dict) -> str:
        return context[self.name] if self.name in context else self.default


def fake(name: str, **items) -> ModuleType:
    module = ModuleType(name)
    module.__dict__.update(items)
    return module


def load(package: str, filename: str, arguments: dict):
    path = package_path(package) / 'launch' / filename
    spec = importlib.util.spec_from_file_location('launch_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entries = module.generate_launch_description().args[0]
    context = {item.args[0]: item.kwargs.get('default_value', '') for item in entries if isinstance(item, Declare)}
    context.update(arguments)
    result = []
    for item in entries:
        if isinstance(item, Opaque): result.extend(item.kwargs['function'](context))
    return result


def expand(actions: list) -> list:
    result = []
    for action in actions:
        if isinstance(action, Include):
            path = Path(action.args[0].args[0])
            # 실물 하드웨어 드라이버는 실행/대체하지 않고 포함 요청까지만 검사합니다.
            if path.parents[1].name == 'farm_real_devices':
                result.append(action)
            else:
                result.extend(expand(load(path.parents[1].name, path.name,
                                          dict(action.kwargs['launch_arguments']))))
        else: result.append(action)
    return result


class LaunchCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path[:0] = [str(package_path(p)) for p in ('farm_navigation', 'farm_sim_runtime')]
        modules = {
            'launch': fake('launch', LaunchDescription=Record, LaunchContext=dict),
            'launch.action': fake('launch.action', Action=Record),
            'launch.actions': fake('launch.actions', DeclareLaunchArgument=Declare,
                IncludeLaunchDescription=Include, OpaqueFunction=Opaque, ExecuteProcess=Process,
                RegisterEventHandler=Record, EmitEvent=Record, LogInfo=Record),
            'launch.event_handlers': fake('launch.event_handlers', OnProcessExit=Record),
            'launch.events': fake('launch.events', Shutdown=Record),
            'launch.launch_description_sources': fake('launch.launch_description_sources', PythonLaunchDescriptionSource=Record),
            'launch.substitutions': fake('launch.substitutions', LaunchConfiguration=Configuration),
            'launch_ros': fake('launch_ros'),
            'launch_ros.actions': fake('launch_ros.actions', Node=Node),
            'launch_ros.descriptions': fake('launch_ros.descriptions', ParameterFile=Record),
            'nav2_common': fake('nav2_common'),
            'nav2_common.launch': fake('nav2_common.launch', RewrittenYaml=Record),
            'ament_index_python': fake('ament_index_python'),
            'ament_index_python.packages': fake('ament_index_python.packages',
                get_package_share_directory=lambda name: str(package_path(name))),
        }
        for name in ('farm_common', 'farm_sim_devices'):
            modules[name] = fake(name, __file__=str(package_path(name) / name / '__init__.py'))
        cls.patcher = patch.dict(sys.modules, modules)
        cls.patcher.start()
        cls.args = dict(project_root=str(ROOT), isaac_python=sys.executable,
                        vision_python=sys.executable, device='cpu')

    @classmethod
    def tearDownClass(cls) -> None:
        cls.patcher.stop()

    def test_all_has_one_isaac_adapter_server_and_rviz(self) -> None:
        actions = expand(load('farm_sim_runtime', 'all.launch.py', self.args))
        self.assertEqual(sum(isinstance(a, Process) for a in actions), 1)
        names = [a.kwargs.get('executable') for a in actions if isinstance(a, Node)]
        for name in ('ros_adapter', 'scout_node', 'rviz2', 'controller_server', 'amcl'):
            self.assertEqual(names.count(name), 1, name)
        process = next(a for a in actions if isinstance(a, Process))
        self.assertIn('run_sim.py', ' '.join(process.kwargs['cmd']))
        self.assertNotIn('PYTHONPATH', process.kwargs['env'])

    def test_sim_robot_does_not_start_isaac_or_rviz(self) -> None:
        actions = expand(load('farm_sim_runtime', 'scout.launch.py', self.args))
        self.assertFalse(any(isinstance(a, Process) for a in actions))
        names = [a.kwargs.get('executable') for a in actions if isinstance(a, Node)]
        self.assertNotIn('rviz2', names)
        self.assertIn('scout_node', names)
        self.assertIn('ros_adapter', names)

    def test_real_robot_keeps_hardware_nav_and_server(self) -> None:
        actions = expand(load('farm_bringup', 'scout.launch.py', dict(self.args, mode='real')))
        self.assertFalse(any(isinstance(a, Process) for a in actions))
        names = [a.kwargs.get('executable') for a in actions if isinstance(a, Node)]
        self.assertIn('scout_node', names)
        self.assertIn('controller_server', names)
        self.assertNotIn('rviz2', names)
        self.assertNotIn('ros_adapter', names)
        self.assertEqual(sum(isinstance(a, Include) for a in actions), 1)

    def test_isaac_has_no_ros_nodes(self) -> None:
        actions = load('farm_sim_runtime', 'isaac.launch.py', self.args)
        self.assertEqual(sum(isinstance(a, Process) for a in actions), 1)
        self.assertFalse(any(isinstance(a, Node) for a in actions))

    def test_navigation_only_selects_sim_environment(self) -> None:
        actions = expand(load('farm_bringup', 'scout.launch.py', dict(self.args,
                              mode='sim', survey='false', navigation='true')))
        names = [a.kwargs.get('executable') for a in actions if isinstance(a, Node)]
        self.assertNotIn('scout_node', names)
        self.assertIn('controller_server', names)
        map_node = next(a for a in actions if isinstance(a, Node) and a.kwargs['executable'] == 'map_server')
        self.assertTrue(map_node.kwargs['parameters'][1]['yaml_filename'].endswith('count_test_farm_map.yaml'))

    def test_rviz_only_and_clock_tf_selection(self) -> None:
        for mode, environment in [('sim', 'sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml'),
                                  ('real', 'robot/config/environments/scout_real.yaml')]:
            actions = load('farm_bringup', 'rviz.launch.py', dict(self.args, mode=mode, environment_config=environment))
            self.assertEqual(len(actions), 1)
            self.assertEqual(actions[0].kwargs['executable'], 'rviz2')
            self.assertEqual(actions[0].kwargs['parameters'], [{'use_sim_time': mode == 'sim'}])
            self.assertEqual(('/tf', '/scout_01/tf') in actions[0].kwargs['remappings'], mode == 'real')

    def test_component_flags(self) -> None:
        actions = expand(load('farm_sim_runtime', 'all.launch.py', dict(self.args, isaac='false', rviz='false')))
        self.assertFalse(any(isinstance(a, Process) for a in actions))
        self.assertFalse(any(isinstance(a, Node) and a.kwargs['executable'] == 'rviz2' for a in actions))
        self.assertEqual(load('farm_sim_runtime', 'all.launch.py', dict(self.args, isaac='false', scout='false', rviz='false')), [])

    def test_old_combined_flags_rejected(self) -> None:
        for package in ('farm_bringup', 'farm_sim_runtime'):
            for flag in ('rviz', 'start_isaac'):
                with self.assertRaises(RuntimeError):
                    load(package, 'scout.launch.py', dict(self.args, **{flag: 'true'}))

    def test_environment_mismatch_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load('farm_sim_runtime', 'isaac.launch.py', dict(self.args,
                environment_config='robot/config/environments/scout_real.yaml'))
        with self.assertRaises(ValueError):
            load('farm_bringup', 'rviz.launch.py', dict(self.args, mode='sim',
                environment_config='robot/config/environments/scout_real.yaml'))


if __name__ == '__main__':
    unittest.main()
