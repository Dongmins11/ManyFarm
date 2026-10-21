import ast,json,math,sys,time,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P))
from async_clearance import AsyncClearance,usable,grid_key

def slow(job):time.sleep(.228);return .1
def failure(job):raise ValueError('collision')
def snapshot():
 now=time.monotonic();ns=time.time_ns()
 return {'certificate':{'pose':(0.,0.,0.),'grid_key':'map','stamps':[ns]*3,'receipts':[now]*3}}
def result():return {'job':snapshot()['certificate'],'clearance':.1}
class Tests(unittest.TestCase):
 def test_expiry_future_map_drift(self):
  r=result();ns=time.time_ns();now=time.monotonic()
  self.assertTrue(usable(r,(0,0,0),'map',ns,now,.5)[0])
  self.assertFalse(usable(r,(0,0,0),'new',ns,now,.5)[0])
  self.assertTrue(usable(r,(0,0,0),'map',ns+600000000,now,.5)[0])
  self.assertTrue(usable(r,(0,0,0),'map',ns-200000000,now,.5)[0])
  self.assertTrue(usable(r,(0,0,0),'map',ns,now+60,.5)[0])
  self.assertFalse(usable(r,(.11,0,0),'map',ns,now,.5)[0])
  self.assertFalse(usable(r,(0,0,.21),'map',ns,now,.5)[0])
 def test_nan_and_error(self):
  with self.assertRaises(RuntimeError):usable(result(),(math.nan,0,0),'map',time.time_ns(),time.monotonic(),.5)
  with self.assertRaises(RuntimeError):usable({'error':'collision'},(0,0,0),'map',0,0,.5)
 def test_grid_contents_geometry(self):
  self.assertNotEqual(grid_key({'x':1},b'123'),grid_key({'x':2},b'123'))
  self.assertNotEqual(grid_key({'x':1},b'123'),grid_key({'x':1},b'12'+bytes([254])))
 def test_slow_process_fast_reader_cleanup(self):
  w=AsyncClearance(snapshot,solver=slow);times=[];valid=False
  try:
   deadline=time.monotonic()+2
   while time.monotonic()<deadline:
    start=time.monotonic();ok,_=w.check((0,0,0),'map',time.time_ns(),start,.5)
    times.append(time.monotonic()-start);valid|=ok;time.sleep(.005)
   self.assertTrue(valid);self.assertLess(max(times),.05)
  finally:stats=w.close()
  self.assertTrue(stats['closed']);self.assertGreater(stats['max_s'],.22)
  print('slow calculation / maximum reader seconds:',stats['max_s'],max(times))
 def test_failure_latches(self):
  w=AsyncClearance(snapshot,solver=failure)
  try:
   deadline=time.monotonic()+2
   while time.monotonic()<deadline:
    try:w.check((0,0,0),'map',time.time_ns(),time.monotonic(),.5)
    except RuntimeError:break
    time.sleep(.01)
   else:self.fail('failure not propagated')
   with self.assertRaises(RuntimeError):w.check((0,0,0),'map',time.time_ns(),time.monotonic(),.5)
  finally:w.close()
 def test_worker_death(self):
  w=AsyncClearance(snapshot,solver=slow)
  try:
   w._process.terminate();w._process.join()
   with self.assertRaises(RuntimeError):w.check((0,0,0),'map',time.time_ns(),time.monotonic(),.5)
  finally:w.close()
 def test_runtime_callbacks_do_not_solve(self):
  tree=ast.parse((P/'arc_trial.py').read_text())
  for node in ast.walk(tree):
   if isinstance(node,ast.FunctionDef) and node.name in ('forward_locked','watchdog','check','require_clearance','clearance_ready'):
    calls=[n.func.id for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
    self.assertNotIn('check_alignment_clearance',calls);self.assertNotIn('alignment_clearance',calls)
if __name__=='__main__':unittest.main(verbosity=2)
