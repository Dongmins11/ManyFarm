import unittest
from types import SimpleNamespace as R
from sorter_test import completed, sequence

class TrialTest(unittest.TestCase):
    def test_sequence(self):
        self.assertEqual(sequence('dock'), [('route', None), ('precision', ('sort_01','DOCK'))])
        self.assertEqual(sequence('undock'), [('precision', ('sort_departure','CLEAR'))])
    def test_route_gate(self):
        self.assertTrue(completed('route',4,R(result_code='SUCCESS',arrived=True)))
        for status,code,arrived in [(6,'SUCCESS',True),(4,'FAILED',True),(4,'SUCCESS',False),(5,'CANCELED',False)]:
            self.assertFalse(completed('route',status,R(result_code=code,arrived=arrived)))
    def test_precision_gate(self):
        self.assertTrue(completed('precision',4,R(success=True,stopped=True)))
        for status,success,stopped in [(6,True,True),(4,False,True),(4,True,False)]:
            self.assertFalse(completed('precision',status,R(success=success,stopped=stopped)))

if __name__ == '__main__': unittest.main()
