"""기존 BT 기본 선택, 설정 보존, 최종 실행 기록 회귀 검사."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import yaml
from farm_navigation.arc_profile import explicit_checkers, write_profile, finalize_manifest, BT_KEYS

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.controller = dict(controller_plugins=['FollowPath'],
            goal_checker_plugins=['general_goal_checker'],progress_checker_plugins=['progress_checker'],
            FollowPath={'desired_linear_vel':.1},progress_checker={'movement_time_allowance':20.})
    def test_old_implicit_default_is_preserved(self):
        xml='<root><FollowPath controller_id="FollowPath" goal_checker_id="general_goal_checker"/></root>'
        node=ET.fromstring(explicit_checkers(xml,self.controller)).find('FollowPath')
        self.assertEqual(node.get('progress_checker_id'),'progress_checker')
        self.assertEqual(node.get('goal_checker_id'),'general_goal_checker')
    def test_existing_explicit_and_blackboard_unchanged(self):
        xml='<root><FollowPath progress_checker_id="{selected}" goal_checker_id="general_goal_checker"/></root>'
        self.assertEqual(ET.tostring(ET.fromstring(xml)),ET.tostring(ET.fromstring(explicit_checkers(xml,self.controller))))
    def test_multiple_implicit_rejected(self):
        self.controller['progress_checker_plugins'].append('other')
        with self.assertRaises(ValueError):explicit_checkers('<root><FollowPath/></root>',self.controller)
    def test_unregistered_explicit_rejected(self):
        with self.assertRaises(ValueError):explicit_checkers('<root><FollowPath progress_checker_id="unknown"/></root>',self.controller)
    def test_settings_source_and_bt_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp); source=p/'original.xml';source.write_text('<root><FollowPath/></root>')
            original={'controller_server':{'ros__parameters':self.controller},
                'bt_navigator':{'ros__parameters':dict.fromkeys(BT_KEYS,str(source))},
                'local_costmap':{'resolution':.02,'footprint':'unchanged'}}
            old=copy.deepcopy(original);source_bytes=source.read_bytes()
            nav,files=write_profile(original,p)
            self.assertEqual(old,original);self.assertEqual(source.read_bytes(),source_bytes)
            result=yaml.safe_load(nav.read_text())
            self.assertEqual(result['local_costmap'],original['local_costmap'])
            self.assertEqual(result['controller_server']['ros__parameters']['FollowPath'],self.controller['FollowPath'])
            for key in BT_KEYS:
                node=ET.parse(result['bt_navigator']['ros__parameters'][key]).getroot().find('FollowPath')
                self.assertEqual(node.get('progress_checker_id'),'progress_checker')
    def test_missing_bt_rejected(self):
        with tempfile.TemporaryDirectory() as temp,self.assertRaises(ValueError):
            write_profile({'controller_server':{'ros__parameters':self.controller}},temp)
    def test_manifest_records_final_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);env=p/'environment.yaml';env.write_text('final: true\n')
            old=p/'inputs/environment.yaml';old.parent.mkdir();old.write_text('old: true\n')
            manifest={'files':{str(env):'stale'},'snapshots':{str(env):'inputs/environment.yaml'}}
            (p/'manifest.json').write_text(json.dumps(manifest))
            finalize_manifest(p,[env]);out=json.loads((p/'manifest.json').read_text())
            digest=hashlib.sha256(env.read_bytes()).hexdigest()
            self.assertEqual(out['files'][str(env)],digest)
            self.assertEqual(old.read_bytes(),env.read_bytes())
            record=out['arc_execution_inputs'][str(env)]
            self.assertEqual(record['sha256'],digest)
            self.assertEqual((p/record['snapshot']).read_bytes(),env.read_bytes())
    def test_existing_trial_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);source=p/'old.xml';source.write_text('<root><FollowPath/></root>')
            original={'controller_server':{'ros__parameters':self.controller},
                'bt_navigator':{'ros__parameters':dict.fromkeys(BT_KEYS,str(source))}}
            write_profile(original,p)
            with self.assertRaises(FileExistsError):write_profile(original,p)

if __name__=='__main__':unittest.main()
