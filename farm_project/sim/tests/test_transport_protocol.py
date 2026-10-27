"""9686aca 운송 회귀: 대역 센서/기구로 FSM 순서·취소·보존 정책을 검증한다."""
import sys,time,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[2]
for rel in ('src/transport_robot','robot/ros_ws/src/transport_robot'):
 if (root/rel).is_dir():sys.path.insert(0,str(root/rel))
from transport_robot.transport_state_controller import TransportStateController
from transport_robot.transport_mission import TransportMission
from transport_robot.mission_types import Request

class Nav:
 def __init__(self,calls):self.calls=calls
 def preflight_navigation(self):pass
 def navigate(self,xy,yaw):self.calls.append('move')
 def cancel_nav(self):self.calls.append('stop_nav')
class Dock:
 def __init__(self,calls):self.calls=calls;self.clear_ok=True;self.dock_ok=True
 def available(self):return True
 def tag(self,r):self.calls.append('tag');return True
 def dock(self,r):self.calls.append('dock');return self.dock_ok
 def clear(self,r):self.calls.append('clear:'+r.task_id);return self.clear_ok
 def stop(self):pass
class Device:
 def __init__(self,calls):self.calls=calls;self.ok=True
 def available(self):return True
 def run(self,r,op,check):
  check();self.calls.append(op)
  return SimpleNamespace(success=self.ok,safe_to_clear=self.ok,count_valid=self.ok,loaded_count=0 if op=='UNLOAD' else 3)
 def stop(self):pass
class Flow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.calls=[];self.events=[]
  self.m=TransportMission(Path(self.tmp.name)/'j.json');self.nav=Nav(self.calls);self.dock=Dock(self.calls);self.dev=Device(self.calls)
  self.c=TransportStateController(self.nav,self.m,self.dock,self.dev)
 def tearDown(self):
  self.c.cancel();self.until(lambda:not self.c.busy);self.c.close();self.tmp.cleanup()
 def until(self,p):
  end=time.monotonic()+2
  while not p() and time.monotonic()<end:self.c.update();time.sleep(.001)
  self.assertTrue(p())
 def start(self,kind='unload',task='U1'):
  self.c.start(Request(task,kind,(0.,0.),0.,'SORT_01','T','H',11,12,'sort_01',(0.,0.),0.),self.events.append)
 def unload_ready(self):
  self.until(lambda:'WAITING_FOR_UNLOAD' in self.events)
  self.c.unload.accept('U1','SORT_01','UNLOAD_READY')
 def finish(self):self.until(lambda:not self.c.busy)
 def test_unload_waits_then_holds(self):
  self.start();self.until(lambda:'WAITING_FOR_UNLOAD' in self.events)
  self.assertEqual(self.calls,['move','dock'])
  self.unload_ready();self.finish()
  self.assertEqual(self.calls,['move','dock','UNLOAD']);self.assertEqual(self.c.last_outcome.result_code,'SUCCESS')
  self.assertIsNotNone(self.c.docked_request);self.assertTrue(self.m._contact.exists())
 def test_next_return_clears_before_move(self):
  self.start();self.unload_ready();self.finish();self.start('return','R2');self.finish()
  self.assertEqual(self.calls,['move','dock','UNLOAD','clear:U1','move','dock'])
 def test_next_pickup_clears_before_move(self):
  self.start();self.unload_ready();self.finish();self.start('pickup','P2')
  self.until(lambda:'WAITING_FOR_TRANSFER' in self.events)
  self.assertEqual(self.calls[:5],['move','dock','UNLOAD','clear:U1','move'])
 def test_no_clear_on_failed_unload(self):
  self.dev.ok=False;self.start();self.unload_ready();self.finish()
  self.assertEqual(self.c.last_outcome.result_code,'FAILED');self.assertTrue(self.c.blocked)
  self.assertNotIn('clear:U1',self.calls)
 def test_failed_departure_no_navigation(self):
  self.start();self.unload_ready();self.finish();self.dock.clear_ok=False;self.start('route','N2');self.finish()
  self.assertEqual(self.calls.count('move'),1);self.assertTrue(self.c.blocked)
 def test_cancel_wait(self):
  self.start();self.until(lambda:'WAITING_FOR_UNLOAD' in self.events);self.c.cancel();self.finish()
  self.assertEqual(self.c.last_outcome.result_code,'CANCELED');self.assertNotIn('UNLOAD',self.calls)
 def test_early_wrong_and_duplicate_events(self):
  self.start()
  with self.assertRaises(ValueError):self.c.unload.accept('U1','SORT_01','UNLOAD_READY')
  self.until(lambda:'WAITING_FOR_UNLOAD' in self.events)
  for t,s,e in [('other','SORT_01','UNLOAD_READY'),('U1','other','UNLOAD_READY'),('U1','SORT_01','WRONG')]:
   with self.assertRaises(ValueError):self.c.unload.accept(t,s,e)
  self.unload_ready();self.c.unload.accept('U1','SORT_01','UNLOAD_READY');self.finish()
  with self.assertRaises(ValueError):self.c.unload.accept('U1','SORT_01','UNLOAD_READY')
 def test_timeout_no_dock(self):
  self.c.unload_workflows={'SORT_01': {'ready_timeout_s': .01}};self.start();self.finish()
  self.assertEqual(self.c.last_outcome.result_code,'FAILED');self.assertNotIn('UNLOAD',self.calls)
 def test_pickup_event_stages(self):
  self.start('pickup','P1')
  with self.assertRaises(ValueError):self.c.transfer.accept('P1','T','H','DOCK_READY')
  self.until(lambda:'WAITING_FOR_TRANSFER' in self.events)
  self.assertEqual(self.c.state.name,'WAIT_DOCK_READY')
  with self.assertRaises(ValueError):self.c.transfer.accept('P1','T','H','TRANSFER_COMPLETE')
  self.c.transfer.accept('P1','T','H','DOCK_READY');self.until(lambda:'DOCK_STABLE' in self.events)
  self.c.transfer.accept('P1','T','H','TRANSFER_COMPLETE');self.finish()
  self.assertEqual(self.calls,['move','tag','dock','CONFIRM_RECEIPT','clear:P1'])
  self.assertEqual(self.events[-2:],['CLEARING_STARTED','TRANSPORT_CLEAR'])
 def test_dock_trial_without_device_holds_until_cancel(self):
  from transport_robot.device_port import UnavailableDevice
  self.c.device=UnavailableDevice()
  r=Request('TRIAL','unload',(0.,0.),0.,station_id='SORT_01',profile_id='sort_01',dock_only_trial=True)
  self.c.start(r,self.events.append)
  self.until(lambda:self.c.state.name=='DOCKING' and self.c.docked_request is not None)
  self.assertEqual(self.calls,['move','dock'])
  self.assertTrue(self.c.busy);self.assertIsNone(self.c.last_outcome)
  self.assertNotIn('UNLOADING_STARTED',self.events)
  self.c.cancel();self.finish()
  self.assertEqual(self.c.last_outcome.result_code,'CANCELED')
  self.assertTrue(self.c.blocked);self.assertTrue(self.m._contact.exists())
 def test_production_unload_still_requires_device(self):
  from transport_robot.device_port import UnavailableDevice
  self.c.device=UnavailableDevice()
  with self.assertRaises(ValueError):self.start()
  self.assertEqual(self.calls,[])
 def test_restart_docked_requires_recovery(self):
  self.start();self.unload_ready();self.finish()
  self.assertTrue(TransportMission(Path(self.tmp.name)/'j.json').recovery_required)
if __name__=='__main__':unittest.main()
