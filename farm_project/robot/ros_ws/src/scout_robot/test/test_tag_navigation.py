"""공통 보정 권한은 구역 내부 이동에만 열고 실패·취소에도 닫는다."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

SRC = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SRC / 'scout_robot'), str(SRC / 'farm_navigation')]
from scout_new.states.navigation_move_state import NavigationMoveState


class TagNavigationTests(unittest.TestCase):
    def move(self, purpose: str, error: Exception | None = None, enabled: bool = True,
             section: str = 'SEC01', canceled_before: bool = False) -> list:
        events = []
        control = NS(begin=lambda value: events.append(('begin', value)),
                     end=lambda: events.append(('end',))) if enabled else None
        def navigate(xy, yaw):
            events.append(('navigate', xy, yaw))
            if error:
                raise error
            return 'arrived'
        def check():
            if canceled_before:
                raise RuntimeError('canceled')
        context = NS(section=section, segment={'offset_m': 1.0},
            bed=NS(cfg={}, origin=(0., 0.), length=3., yaw=0., world=lambda s,n:(s,n,0.)))
        node = NS(_tag_control=control, _navigator=NS(navigate=navigate), check=check)
        state = NavigationMoveState(NS(context=context,node=node),None,purpose)
        if error or canceled_before:
            with self.assertRaises(RuntimeError):
                state._move()
        else:
            self.assertEqual(state._move(), 'arrived')
        return events

    def test_observation_uses_actual_section_and_closes(self):
        self.assertEqual(self.move('observation',section='SEC16'),
            [('begin','SEC16'),('navigate',(1.,0.),0.),('end',)])

    def test_approach_and_exit_never_enable_repeated_ids(self):
        for purpose in ('section_start','section_exit'):
            with self.subTest(purpose=purpose):
                events=self.move(purpose)
                self.assertFalse(any(e[0]=='begin' for e in events))
                self.assertEqual(events[0],('end',))
                self.assertEqual(events[-1],('end',))

    def test_failure_and_cancel_close_permission(self):
        for reason in ('navigation failed','canceled'):
            with self.subTest(reason=reason):
                events=self.move('observation',RuntimeError(reason))
                self.assertEqual(events[0],('begin','SEC01'))
                self.assertEqual(events[-1],('end',))

    def test_canceled_before_move_does_not_open_permission(self):
        self.assertEqual(self.move('observation',canceled_before=True),[])

    def test_disabled_keeps_existing_move(self):
        self.assertEqual(self.move('observation',enabled=False), [('navigate',(1.,0.),0.)])


if __name__=='__main__':
    unittest.main()
