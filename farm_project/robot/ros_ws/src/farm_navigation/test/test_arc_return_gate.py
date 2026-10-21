"""기존 gate의 명시적 복귀 선택. 출력 제한·timeout·충돌 latch를 유지한다."""
import math
import unittest
from farm_navigation.arc_isolation import CommandGate

class ReturnGateTests(unittest.TestCase):
    def test_default_rejects_return(self):
        g=CommandGate();g.arm(0.)
        self.assertFalse(g.accept(.01,-.1,.1))

    def test_return_accepts_only_selected_direction(self):
        g=CommandGate(direction='forward_right');g.arm(0.)
        self.assertTrue(g.accept(.01,-.1,.1))
        self.assertFalse(g.accept(-.01,.1,.2))
        self.assertFalse(g.accept(.01,-.1,.21))

    def test_zero(self):
        g=CommandGate(direction='forward_right');g.arm(0.)
        self.assertTrue(g.accept(0.,0.,.1))

    def test_limits(self):
        for v,w in ((.026,-.1),(.01,-.181),(-.01,-.1),(.01,.01),(math.nan,0.),(.01,math.inf)):
            g=CommandGate(direction='forward_right');g.arm(0.)
            self.assertFalse(g.accept(v,w,.1))
            with self.assertRaises(RuntimeError):g.arm(.2)

    def test_timeout_and_close(self):
        g=CommandGate(direction='forward_right');g.arm(0.)
        self.assertTrue(g.accept(.01,-.1,.1));self.assertTrue(g.expired(.401))
        self.assertFalse(g.accept(.01,-.1,.402))
        h=CommandGate(direction='forward_right');h.arm(0.);h.close()
        self.assertFalse(h.accept(.01,-.1,.1))

    def test_other_action(self):
        g=CommandGate(direction='forward_right');g.arm(0.)
        self.assertFalse(g.accept(.01,-.1,.1,conflict=True))

    def test_unknown_direction(self):
        with self.assertRaises(ValueError):CommandGate(direction='both')

    def test_exact_mirror_of_original_limits(self):
        for v in (-.026,-.025,-.01,0.,.000001,.001,.01):
            for w in (-.01,-.001,0.,.1,.18,.181):
                a=CommandGate();b=CommandGate(direction='forward_right')
                a.arm(0.);b.arm(0.)
                self.assertEqual(a.accept(v,w,.1),b.accept(-v,-w,.1))

if __name__=='__main__':unittest.main()
