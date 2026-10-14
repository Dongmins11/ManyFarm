"""구역 전환 시 이전 보정 권한을 종료한 후 새 token을 발행하는지 검사한다."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


class TagControlTests(unittest.TestCase):
    def test_section_switch_ends_old_lease_before_starting_new_one(self) -> None:
        spec=importlib.util.spec_from_file_location('tag_control_test',
            Path(__file__).parents[2]/'farm_navigation/farm_navigation/tag_control.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules',{'std_msgs.msg':NS(String=lambda:NS())}):
            spec.loader.exec_module(module)
        sent=[]
        node=NS(create_publisher=lambda *args:NS(publish=lambda message:sent.append(json.loads(message.data))),
            create_timer=lambda *args:None,get_clock=lambda:NS(now=lambda:NS(nanoseconds=123)))
        control=module.TagControl(node,'harvest_01','farm_map_v1')
        control.begin()
        control.begin('SEC01')
        control._heartbeat()
        control.begin()
        control.end()
        self.assertEqual([x['enabled'] for x in sent],[True,False,True,True,False,True,False])
        self.assertNotIn('section_id',sent[0])
        self.assertEqual([sent[i]['section_id'] for i in (2,3,4)],['SEC01']*3)
        self.assertNotIn('section_id',sent[5])
        self.assertEqual(sent[0]['token'],sent[1]['token'])
        self.assertEqual(sent[2]['token'],sent[4]['token'])
        self.assertNotEqual(sent[0]['token'],sent[2]['token'])
        self.assertNotEqual(sent[2]['token'],sent[5]['token'])
        self.assertEqual([sent[i]['sequence'] for i in (2,3,4)],[1,2,3])


if __name__=='__main__':
    unittest.main()
