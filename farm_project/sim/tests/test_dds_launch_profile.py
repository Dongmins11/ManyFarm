"""전체 시뮬 DDS 프로파일의 자식 전달·환경 복원·외부 설정 보존을 검증한다."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from launch import LaunchContext
from launch.actions import LogInfo

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / 'sim/ros_ws/src/farm_sim_runtime/launch/all.launch.py'
spec = importlib.util.spec_from_file_location('sim_all_dds_test', FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PROFILE = ROOT / 'sim/ros_ws/src/farm_sim_config/config/fastdds_discovery.xml'


class DDSLaunchProfileTests(unittest.TestCase):
    def context(self, root=ROOT):
        context = LaunchContext()
        context.launch_configurations.update(project_root=str(root),
            environment_config='sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml',
            isaac='false', scout='false', harvest='false', rviz='false')
        for name in ('FASTRTPS_DEFAULT_PROFILES_FILE', 'FASTDDS_DEFAULT_PROFILES_FILE'):
            context.environment.pop(name, None)
        context.environment['ROS_DOMAIN_ID'] = '13'
        context.environment['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'SUBNET'
        return context

    def apply_group(self, context):
        group, = module.setup(context)
        children = group.get_sub_entities()
        # 실제 launch의 환경 push/set/pop 동작을 수행한다. ROS 프로세스는 띄우지 않는다.
        for action in children[:-2]:
            if not isinstance(action, LogInfo):
                action.execute(context)
        inside = dict(context.environment)
        for action in children[-2:]:
            action.execute(context)
        return inside

    def test_default_reaches_children_and_restores_caller(self):
        context = self.context()
        before = dict(context.environment)
        inside = self.apply_group(context)
        self.assertEqual(inside['FASTRTPS_DEFAULT_PROFILES_FILE'], str(PROFILE))
        self.assertEqual(inside['ROS_DOMAIN_ID'], '13')
        self.assertEqual(inside['ROS_AUTOMATIC_DISCOVERY_RANGE'], 'SUBNET')
        self.assertEqual(context.environment, before)

    def test_explicit_parent_profile_is_preserved(self):
        for key in ('FASTRTPS_DEFAULT_PROFILES_FILE', 'FASTDDS_DEFAULT_PROFILES_FILE'):
            with self.subTest(key=key):
                context = self.context()
                context.environment[key] = '/explicit/profile.xml'
                before = dict(context.environment)
                inside = self.apply_group(context)
                self.assertEqual(inside, before)
                self.assertEqual(context.environment, before)

    def test_missing_default_profile_fails_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, 'DDS'):
                module.setup(self.context(Path(directory)))

    def test_profile_changes_only_participant_receive_buffer(self):
        ns = {'d': 'http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles'}
        tree = ET.parse(PROFILE)
        participant = tree.find('d:profiles/d:participant', ns)
        self.assertEqual(participant.get('is_default_profile'), 'true')
        rtps = participant.find('d:rtps', ns)
        self.assertEqual(len(rtps), 1)
        self.assertEqual(int(rtps.find('d:listenSocketBufferSize', ns).text), 2097152)


if __name__ == '__main__':
    unittest.main()
