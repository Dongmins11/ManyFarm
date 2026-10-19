import unittest
from harvest_runtime.sequence_eval import target_order
class SequenceOrder(unittest.TestCase):
    def test_height_not_color(self):
        p=[[0,0,2],[0,0,1]]
        self.assertEqual(target_order(p,'lowest-first','red'),['yellow','red'])
        self.assertEqual(target_order(p,'color','red'),['red','yellow'])
        self.assertEqual(p,[[0,0,2],[0,0,1]])
    def test_tie_is_stable(self):
        self.assertEqual(target_order([[0,0,1],[0,0,1]],'lowest-first','yellow'),['red','yellow'])
