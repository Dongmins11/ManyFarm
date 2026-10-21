import os,sys,math,time,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[3]/'robot/ros_ws/src'
sys.path[:0]=[str(R/'farm_navigation'),str(R/'harvest_robot'),str(Path(__file__).parent)]
from async_clearance import solve,usable,AsyncClearance
from harvest_robot.transfer_retreat import alignment_clearance
body=[(.32,-.27),(.32,.27),(-.32,.27),(-.32,-.27)]
def job():
 return dict(pose=(0.,0.,0.),target_yaw=.022,footprint=body,body_footprint=body,
 grid={'metadata':{'resolution':.05,'size_x':60,'size_y':60,'origin':{'position':{'x':-1.5,'y':-1.5},'orientation':{'x':0,'y':0,'z':0,'w':1}}},'data':[0]*3600},
 certificate={'pose':(0.,0.,0.),'grid_key':'map','stamps':[time.time_ns()]*3,'receipts':[time.monotonic()]*3})
class Geometry(unittest.TestCase):
 def test_same_exact_function_and_collision(self):
  j=job();self.assertEqual(solve(j),alignment_clearance(j['pose'],j['target_yaw'],body,j['grid'],body_footprint=body))
  for value in (254,255):
   j['grid']['data'][30*60+30]=value
   with self.assertRaises(RuntimeError):solve(j)
 def test_spawn_actual_solver(self):
  w=AsyncClearance(job)
  try:
   end=time.monotonic()+3
   while time.monotonic()<end:
    if w.check((0,0,0),'map',time.time_ns(),time.monotonic(),.42)[0]:break
    time.sleep(.01)
   else:self.fail('actual solver no valid result')
  finally:self.assertTrue(w.close()['closed'])
if __name__=='__main__':unittest.main(verbosity=2)
