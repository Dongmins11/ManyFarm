import unittest
from scout_robot.fruit_association import match_observations

def fruit(x, color='Red', id='f'):
    return dict(id=id,position_map_m=[x,0,.9],class_name=color)

def match(d,f):
    return match_observations(d,f,max_distance_m=.10,ambiguity_margin_m=.02)[0]

class AssociationTests(unittest.TestCase):
    def test_eight_cm_drift(self):
        self.assertEqual(match([fruit(.08)],[fruit(0)]),{0:0})
    def test_color_mismatch(self):
        self.assertEqual(match([fruit(0,'Yellow')],[fruit(0)]),{})
    def test_ambiguous_neighbours(self):
        self.assertEqual(match([fruit(.04)],[fruit(0),fruit(.08,id='g')]),{})
    def test_one_to_one(self):
        self.assertEqual(match([fruit(.01),fruit(.08)],[fruit(0)]),{0:0})
    def test_latest_coordinate(self):
        f=fruit(0);f['position_latest_map_m']=[.05,0,.9]
        self.assertEqual(match([fruit(.13)],[f]),{0:0})
    def test_distant_not_merged(self):
        self.assertEqual(match([fruit(.11)],[fruit(0)]),{})
