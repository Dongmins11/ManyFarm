"""기존 관제 wire 형식의 Section 없는 Goal과 단일 구역 경계를 검증한다."""
import copy
import json
from pathlib import Path
import unittest
from test_control_aliases import ControlAliases
from harvest_robot.contract import validate_task, resolve_section


class LegacyControlGoal(ControlAliases):
    def setUp(self):
        super().setUp()
        del self.goal.section_id

    def test_control_and_frozen_ids(self):
        validate_task(self.goal,self.config)
        self.assertEqual(resolve_section(None,self.config),'SEC_01')
        self.goal.map_id='many_farm_v1';validate_task(self.goal,self.config)

    def test_unknown_inputs_rejected(self):
        for name,value in [('map_id','other'),('robot_id','scout_01'),('section_id','SEC02'),('section_id','')]:
            goal=copy.deepcopy(self.goal);setattr(goal,name,value)
            with self.assertRaises(ValueError):validate_task(goal,self.config)

    def test_missing_or_multiple_sections_not_guessed(self):
        cfg=copy.deepcopy(self.config);cfg.pop('default_section_id')
        with self.assertRaises(ValueError):validate_task(self.goal,cfg)
        cfg=copy.deepcopy(self.config);cfg['sections']['SEC_02']={}
        with self.assertRaises(ValueError):validate_task(self.goal,cfg)

    def test_wire_has_no_section(self):
        root=Path(__file__).resolve().parents[5]
        action=(root/'robot/ros_ws/src/farm_interfaces/action/HarvestTask.action').read_text()
        self.assertNotIn('string section_id',action)


if __name__=='__main__':unittest.main()
