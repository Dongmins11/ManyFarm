import importlib.util
import math
from pathlib import Path
import unittest
import numpy as np
source=Path(__file__).resolve().parents[1]/'farm_navigation/arc_clearance.py'
spec=importlib.util.spec_from_file_location('checked_clearance',source)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def grid(cells=()):
 data=np.zeros((100,100),dtype=int)
 for x,y,value in cells:data[int(round((y+1.98)/.04)),int(round((x+1.98)/.04))]=value
 return {'metadata':{'resolution':.04,'size_x':100,'size_y':100,'origin':{'position':{'x':-2.,'y':-2.},'orientation':{'x':0.,'y':0.,'z':0.,'w':1.}}},'data':data.ravel().tolist()}
FP=[[-.3,-.25],[-.3,.25],[.3,.25],[.3,-.25]]
class Tests(unittest.TestCase):
 def test_empty(self):self.assertGreater(m.check_grid([[0,0,0],[.1,0,0]],FP,(0,0,0),grid()),0)
 def test_lethal(self):
  with self.assertRaises(RuntimeError):m.check_grid([[0,0,0],[.1,0,0]],FP,(0,0,0),grid([(0.02,0.02,254)]))
 def test_unknown(self):
  with self.assertRaises(RuntimeError):m.check_grid([[0,0,0],[.1,0,0]],FP,(0,0,0),grid([(0.02,0.02,255)]))
 def test_touch(self):self.assertEqual(m._cell_distance([0,0,0],np.array([.3,.25]),np.array([[.32,0]]),.04),0)
 def test_exact_gap(self):self.assertAlmostEqual(m._cell_distance([0,0,0],np.array([.3,.25]),np.array([[.332,0]]),.04),.012)
 def test_between_translation(self):
  tiny=[[-.01,-.01],[-.01,.01],[.01,.01],[.01,-.01]]
  with self.assertRaises(RuntimeError):m.check_grid([[-.3,0,0],[.3,0,0]],tiny,(0,0,0),grid([(.02,.02,254)]))
 def test_between_rotation(self):
  narrow=[[-.4,-.04],[-.4,.04],[.4,.04],[.4,-.04]]
  with self.assertRaises(RuntimeError):m.check_grid([[0,0,0],[0,0,math.pi/2]],narrow,(0,0,0),grid([(.26,.26,254)]))
 def test_boundary(self):
  with self.assertRaises(RuntimeError):m.check_grid([[0,0,0],[1.8,0,0]],FP,(0,0,0),grid())
 def test_nan(self):
  with self.assertRaises(ValueError):m.check_grid([[0,0,0],[float('nan'),0,0]],FP,(0,0,0),grid())
 def test_duplicate(self):
  with self.assertRaises(ValueError):m.check_grid([[0,0,0],[.1,0,0]],[FP[0]]*4,(0,0,0),grid())
 def test_limit_closed(self):
  old=m._MAX_EVALUATIONS;m._MAX_EVALUATIONS=1
  try:
   with self.assertRaises(RuntimeError):m.check_grid([[0,0,0],[.1,0,0]],FP,(0,0,0),grid())
  finally:m._MAX_EVALUATIONS=old
 def test_circle_midpoint(self):
  for sign in [-1,1]:
   a=np.array([0.,0.,0.]);theta=sign*.7;b=np.array([-.1*math.sin(theta),-.1*(1-math.cos(theta)),theta])
   expected=[-.1*math.sin(theta/2),-.1*(1-math.cos(theta/2)),theta/2]
   np.testing.assert_allclose(m._midpoint(a,b),expected,atol=1e-14)
if __name__=='__main__':unittest.main()
