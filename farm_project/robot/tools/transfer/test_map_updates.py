import copy,math,random,sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from async_clearance import grid_key,AsyncClearance
REGION=(0.,0.,math.hypot(.32,.27)+.005)
META={'frame':'odom','resolution':.05,'size_x':80,'size_y':80,
      'origin':{'position':{'x':-2.,'y':-2.,'z':0.},'orientation':{'x':0.,'y':0.,'z':0.,'w':1.}},
      'update_time':0,'map_load_time':0,'layer':'master'}
def key(meta,data):return grid_key(meta,bytes(data),REGION)
def delayed(job):time.sleep(.07);return .17
class Updates(unittest.TestCase):
 def test_changing_inflation_and_timestamps(self):
  data=bytearray(6400);ref=key(META,data);rng=random.Random(77)
  for i in range(200):
   data[:]=bytes(rng.randrange(254) for _ in data)
   meta={**META,'update_time':i,'map_load_time':i+1,'layer':str(i)}
   self.assertEqual(key(meta,data),ref)
 def test_unknown_and_lethal_inside_block(self):
  data=bytearray(6400);ref=key(META,data)
  for v in (254,255):
   data[40*80+40]=v;self.assertNotEqual(key(META,data),ref)
  lethal=key(META,data);data[40*80+40]=254;self.assertEqual(key(META,data),lethal)
 def test_remote_obstacle_does_not_invalidate(self):
  data=bytearray(6400);ref=key(META,data)
  for idx in (0,79,6320,6399):data[idx]=255
  self.assertEqual(key(META,data),ref)
 def test_shape_frame_origin_change(self):
  data=bytearray(6400);ref=key(META,data)
  for name,value in [('frame','map'),('resolution',.051),('size_x',40),('size_y',160)]:
   meta=copy.deepcopy(META);meta[name]=value
   try:changed=key(meta,data)
   except RuntimeError:continue
   self.assertNotEqual(ref,changed)
  meta=copy.deepcopy(META);meta['origin']['position']['x']+=.05
  self.assertNotEqual(key(meta,data),ref)
 def test_every_cell_touching_envelope_is_compared(self):
  data=bytearray(6400);ref=key(META,data);extent=REGION[2]
  for y in range(80):
   for x in range(80):
    lo_x=-2+x*.05;lo_y=-2+y*.05
    if lo_x<=extent and lo_x+.05>=-extent and lo_y<=extent and lo_y+.05>=-extent:
     idx=y*80+x;data[idx]=254
     self.assertNotEqual(key(META,data),ref,(x,y));data[idx]=0
 def test_process_under_continuous_irrelevant_updates(self):
  data=bytearray(6400);counter=[0]
  def snap():
   counter[0]+=1;data[0]=255 if counter[0]%2 else 0
   data[40*80+40]=counter[0]%254
   meta={**META,'update_time':counter[0]}
   now=time.monotonic()
   return {'certificate':{'pose':(0,0,0),'grid_key':key(meta,data),
           'stamps':[time.time_ns()]*3,'receipts':[now]*3}}
  worker=AsyncClearance(snap,solver=delayed)
  try:
   end=time.monotonic()+2;valid=0;started=False
   while time.monotonic()<end:
    ok,reason=worker.check((0,0,0),key(META,data),time.time_ns(),time.monotonic(),REGION[2])
    if started:self.assertTrue(ok,reason)
    if ok:started=True;valid+=1
    time.sleep(.01)
   self.assertGreater(valid,50)
   data[40*80+40]=254
   self.assertFalse(worker.check((0,0,0),key(META,data),time.time_ns(),time.monotonic(),REGION[2])[0])
  finally:worker.close()
if __name__=='__main__':unittest.main(verbosity=2)
