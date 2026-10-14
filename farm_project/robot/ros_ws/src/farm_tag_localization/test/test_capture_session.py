"""ROS 없이 실행 소유·폴더 선택·실물 파일 연결을 검사한다. 하드웨어 검증 아님."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
import yaml
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/farm_navigation'))
from farm_tag_localization.capture_session import capture_directory, capture_environment, capture_command, adapter_command, stop_owned
from farm_tag_localization.runtime import validate_binding, load_observer
from farm_navigation.configuration import load_environment, read_mapping, load_nav2_parameters
from farm_navigation.route import RouteGraph
from farm_navigation.arrival import validate_goal_checkers
from farm_navigation.navigation_types import NavigationSettings

class CaptureSession(unittest.TestCase):
    def test_camera_environment_isolated_from_navigation(self):
        original={'ROS_DOMAIN_ID':'156','RMW_IMPLEMENTATION':'rmw_fastrtps_cpp','CYCLONEDDS_URI':'fleet','PATH':'/bin'}
        camera=capture_environment(original)
        self.assertNotIn('CYCLONEDDS_URI',camera)
        self.assertEqual(original['CYCLONEDDS_URI'],'fleet')
        self.assertEqual(camera['PATH'],'/bin')

    def test_only_current_session_and_complete_journal_selected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);old=root/'old';old.mkdir();(old/'settings.json').write_text('{}');(old/'detections.jsonl').touch()
            session=root/'new';session.mkdir();self.assertIsNone(capture_directory(session))
            output=session/'capture';output.mkdir();(output/'settings.json').write_text('{}')
            self.assertIsNone(capture_directory(session))
            (output/'detections.jsonl').touch();self.assertEqual(capture_directory(session),output)

    def test_paths_with_spaces_are_argv_not_shell(self):
        with tempfile.TemporaryDirectory(prefix='capture space ') as t:
            root=Path(t);script=root/'capture.py';script.touch()
            cfg=dict(script=str(script),workspace=str(root),device='/dev/video0',trial_label='manual_2ms')
            cmd=capture_command(root,cfg,root/'output')
            self.assertEqual(cmd[2],str(script));self.assertEqual(cmd[-1],str(root/'output'))
            cmd=adapter_command(root,root/'config.yaml',root/'output','harvest_01')
            self.assertIn('/tf:=/harvest_01/tf',cmd)
            self.assertIn('capture_directory:='+str(root/'output'),cmd)

    def test_shutdown_only_own_child(self):
        child = 'import signal,time,sys; signal.signal(signal.SIGINT,lambda *a:sys.exit(0)); print("ready",flush=True); time.sleep(30)'
        process=subprocess.Popen([sys.executable,'-S','-c',child],start_new_session=True,stdout=subprocess.PIPE,text=True)
        unrelated=subprocess.Popen([sys.executable,'-S','-c',child],start_new_session=True,stdout=subprocess.PIPE,text=True)
        self.assertEqual(process.stdout.readline().strip(),'ready')
        self.assertEqual(unrelated.stdout.readline().strip(),'ready')
        try:
            self.assertEqual(stop_owned(process,1.),0)
            self.assertIsNone(unrelated.poll())
        finally:
            stop_owned(process,1.);stop_owned(unrelated,1.)
            process.stdout.close();unrelated.stdout.close()

    def test_map_model_route_and_checker_match(self):
        env=load_environment(ROOT/'robot/config/environments/harvest_real.yaml',ROOT,'real',require_survey=False)
        cfg=read_mapping(ROOT/env['tag_localization_config'])
        validate_binding(cfg,env,ROOT)
        load_observer(str(ROOT/env['tag_localization_config']),str(ROOT),'test')
        graph=RouteGraph(env['route_graph']);plan=graph.plan(graph.nodes[10],graph.nodes[13])
        self.assertEqual(plan.points[-1],graph.nodes[13])
        self.assertNotIn(graph.nodes.get(14),plan.points)
        settings=NavigationSettings.from_mapping(env['navigation'])
        params=load_nav2_parameters(env['nav_params'],ROOT)['controller_server']['ros__parameters']
        self.assertIn(settings.goal_checker_id,params['goal_checker_plugins'])
        self.assertIn(settings.controller_id,params['controller_plugins'])
        flattened = dict(params)
        for checker in params['goal_checker_plugins']:
            flattened.update({checker + '.' + k: v for k, v in params[checker].items()})
        validate_goal_checkers(flattened, settings.arrival_tolerance_m, settings.heading_tolerance_rad)
