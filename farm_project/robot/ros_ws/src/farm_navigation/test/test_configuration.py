"""환경 선택과 지도 혼합 방지. 실제 장치·기존 파일을 변경하지 않습니다."""
import tempfile
import unittest
import json
from pathlib import Path
from farm_navigation.configuration import load_environment


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name in ('map.yaml','nav.yaml','graph.json','vision.json'):
            (self.root/name).write_text('{}')
        self.survey={'robot_id':'robot_7','map_id':'map_real', 'vision_config':'vision.json',
                     'sections':{'BED_OTHER':{'route_file':'graph.json','node_ids':[900,901]}}}
        self.device={'robot_id':'robot_7','map_id':'map_real'}
        self.profile={'schema_version':1,'mode':'real','robot_id':'robot_7','map_id':'map_real',
                      'map_yaml':'map.yaml','nav_params':'nav.yaml','route_graph':'graph.json',
                      'survey_config':'survey.json','device_config':'device.json','navigation':{'mode':'follow_path'}}

    def save(self):
        for name,data in [('survey.json',self.survey),('device.json',self.device),('env.json',self.profile)]:
            (self.root/name).write_text(json.dumps(data))
        return self.root/'env.json'

    def test_real_uses_same_loader_with_different_data(self):
        env=load_environment(self.save(),self.root,'real')
        self.assertEqual(env['robot_id'],'robot_7')
        self.assertEqual(Path(env['route_graph']),self.root/'graph.json')

    def test_mode_and_map_mismatch_rejected(self):
        with self.assertRaises(ValueError):load_environment(self.save(),self.root,'sim')
        self.device['map_id']='sim_map'
        with self.assertRaises(ValueError):load_environment(self.save(),self.root,'real')

    def test_mixed_graph_rejected(self):
        (self.root/'other.json').write_text('{}')
        self.survey['sections']['BED_OTHER']['route_file']='other.json'
        with self.assertRaises(ValueError):load_environment(self.save(),self.root,'real')

    def test_unconfigured_and_missing_file_rejected(self):
        self.profile['configured']=False
        with self.assertRaises(ValueError):load_environment(self.save(),self.root,'real')
        self.profile['configured']=True;self.profile['nav_params']='missing.yaml'
        with self.assertRaises(FileNotFoundError):load_environment(self.save(),self.root,'real')


if __name__=='__main__':unittest.main(verbosity=2)
