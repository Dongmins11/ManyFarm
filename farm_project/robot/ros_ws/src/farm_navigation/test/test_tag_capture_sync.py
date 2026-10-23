"""접근 사용권에는 목표 pose만 추가하며 다음 이동에 게이트를 누출하지 않는다."""
from pathlib import Path
from types import SimpleNamespace as NS
import json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from farm_navigation.tag_control import TagControl
class ApproachControl(unittest.TestCase):
    def test_gate_is_published_and_next_lease_clears_it(self) -> None:
        messages=[]
        node=NS(create_publisher=lambda *a:NS(publish=lambda m:messages.append(json.loads(m.data))),
            create_timer=lambda *a:None,get_clock=lambda:NS(now=lambda:NS(nanoseconds=100)))
        control=TagControl(node,'s','m')
        control.begin('SEC01',approach_pose=[1.,2.,0.])
        self.assertEqual(messages[-1]['approach_pose'],[1.,2.,0.])
        control.end();control.begin('SEC01')
        self.assertNotIn('approach_pose',messages[-1])
