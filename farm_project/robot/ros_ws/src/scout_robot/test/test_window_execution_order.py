"""추가 관측에서 뒤쪽 창이 생성돼도 수확 태스크는 실제 진행 방향을 따른다."""
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/scout_robot'))
sys.path.insert(0, str(ROOT/'robot/ros_ws/src/farm_navigation'))
from scout_robot.b_planner import Config
from scout_robot.survey_core import Survey


class WindowOrderTests(unittest.TestCase):
    def survey(self, yaw):
        c, s = math.cos(yaw), math.sin(yaw)
        bed = SimpleNamespace(plan_cfg=Config(route_end=5.), harvest_yaw=yaw,
            local=lambda xyz: [c*xyz[0]+s*xyz[1], -s*xyz[0]+c*xyz[1], xyz[2]],
            world=lambda x,y,z=0.: [c*x-s*y, s*x+c*y, z])
        return Survey(bed, 'SEC', .05)

    def test_late_backward_window_is_sent_first_in_all_map_directions(self):
        for yaw in (0., math.pi/2, math.pi, -math.pi/2):
            with self.subTest(yaw=yaw):
                survey = self.survey(yaw)
                def detection(x):
                    return dict(position_map_m=survey.bed.world(x,0.,.5),
                                class_name='Red',confidence=.9,stamp_ns=1)
                survey.ingest([detection(2.)], segment_id='early')
                first = survey.windows()[0]
                survey.ingest([detection(1.)], segment_id='late')
                windows = survey.windows()
                self.assertEqual([w['window_id'] for w in windows], ['SEC_W002','SEC_W001'])
                self.assertEqual(windows[1], first)
                self.assertEqual(windows[0]['segment_id'], 'late')
                self.assertEqual(sum(w['expected_count'] for w in windows), 2)
                self.assertEqual([t.task_id for t in survey.plan.tasks], [1,2])
                direction = [math.cos(yaw),math.sin(yaw)]
                goals = [sum(w['goal_pose']['position'][i]*direction[i] for i in (0,1)) for w in windows]
                self.assertGreater(goals[1],goals[0])


if __name__ == '__main__':
    unittest.main()
