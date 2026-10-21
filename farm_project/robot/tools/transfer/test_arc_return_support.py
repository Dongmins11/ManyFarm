import copy
from dataclasses import asdict
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from arc_return_support import load_departure,check_reentry,check_return_complete,require_plan,session_identity
from farm_navigation.transfer_arc import ArcSpec,arc_path,check_motion
from farm_navigation.measured_velocity_guard import MeasuredVelocityGuard,MeasuredVelocityLimits

class ReturnTests(unittest.TestCase):
    def setUp(self):
        self.spec=ArcSpec();self.origin=(1.2,-2.1,3.1);self.path=arc_path(self.origin,self.spec)
        self.record=dict(ok=True,execute=True,phase='SUCCEEDED',cleanup_stopped=True,
            ros_cleanup_complete=True,direction='reverse_left',odom_session='session',baseline_hash='baseline',
            arc_spec=asdict(self.spec),origin=self.origin,path=self.path)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'departure.json'
    def load(self,record=None):
        self.file.write_text(json.dumps(self.record if record is None else record))
        return load_departure(self.file,session='session',baseline_hash='baseline',spec=self.spec)
    def test_inverse_exact_no_pi(self):
        origin,path,digest=self.load()
        self.assertEqual(origin,self.origin);self.assertEqual(path,list(reversed(self.path)));self.assertEqual(len(digest),64)
    def test_invalid_execution_records(self):
        for key,value in [('ok',False),('execute',False),('phase','PLAN_ONLY'),('cleanup_stopped',False),
                          ('ros_cleanup_complete',False),('direction','forward_right')]:
            with self.subTest(key=key):
                r=copy.deepcopy(self.record);r[key]=value
                with self.assertRaises(ValueError):self.load(r)
    def test_old_session_and_config_rejected(self):
        for key,value in [('odom_session','new'),('baseline_hash','new'),('arc_spec',{}),('path',[])]:
            r=copy.deepcopy(self.record);r[key]=value
            with self.assertRaises(ValueError):self.load(r)
    def test_bad_path_and_nan(self):
        for value in [9.,float('nan')]:
            r=json.loads(json.dumps(self.record));r['path'][10][0]=value
            with self.assertRaises(ValueError):self.load(r)
    def test_source_hash_binds_bytes(self):
        _,_,a=self.load();r=copy.deepcopy(self.record);r['note']='changed';_,_,b=self.load(r)
        self.assertNotEqual(a,b)
    def test_reentry(self):
        _,p,_=self.load();self.assertEqual(check_reentry(p[0],p,self.spec)['position_error_m'],0)
        for current in [(p[0][0]+.009,p[0][1],p[0][2]),(p[0][0],p[0][1],p[0][2]+math.radians(1.1))]:
            with self.assertRaises(RuntimeError):check_reentry(current,p,self.spec)
    def test_complete_original_origin_only(self):
        self.assertEqual(check_return_complete(self.origin,self.origin,self.spec)['endpoint_error'],0)
        with self.assertRaises(RuntimeError):check_return_complete(self.origin,self.path[-1],self.spec)
    def test_all_return_samples_with_original_monitor(self):
        for p in reversed(self.path):self.assertLess(check_motion(self.origin,p,self.spec)['deviation'],1e-9)
    def test_signed_measured_guard_keeps_limits(self):
        limits=MeasuredVelocityLimits(.025,.005,.18,.2,.1,.5)
        g=MeasuredVelocityGuard(limits);g.observe(1_000_000_000,-.01,.1)
        for actual_v in [-.006,.026]:
            with self.assertRaises(RuntimeError):MeasuredVelocityGuard(limits).observe(1_000_000_000,-actual_v,.1)
    def test_session_publisher_instance(self):
        e=SimpleNamespace(endpoint_gid=bytes([1]*24),node_namespace='/harvest_01',node_name='driver')
        a=session_identity('boot',[e]);self.assertNotEqual(a,session_identity('newboot',[e]))
        e.endpoint_gid=bytes([2]*24);self.assertNotEqual(a,session_identity('boot',[e]))
        for pubs in [[],[e,e]]:
            with self.assertRaises(RuntimeError):session_identity('boot',pubs)
    def test_return_collision_and_unknown_unchanged(self):
        from farm_navigation.arc_clearance import check_grid
        path=list(reversed(arc_path((0.,0.,0.),self.spec)))
        current=path[0];c=math.cos(current[2]);s=math.sin(current[2])
        fp=[(current[0]+c*x-s*y,current[1]+s*x+c*y) for x,y in [(-.3,-.25),(-.3,.25),(.3,.25),(.3,-.25)]]
        grid={'metadata':{'resolution':.04,'size_x':100,'size_y':100,'origin':{'position':{'x':-2.,'y':-2.},'orientation':{'x':0.,'y':0.,'z':0.,'w':1.}}},'data':[0]*10000}
        self.assertGreater(check_grid([current]+path,fp,current,grid),0)
        for value in (254,255):
            grid['data'][50*100+50]=value
            with self.assertRaises(RuntimeError):check_grid([current]+path,fp,current,grid)
    def test_plan_binding(self):
        r=dict(ok=True,phase='PLAN_ONLY',radius=.1,direction='forward_right',odom_session='session',
               departure_sha256='sha',baseline_hash='base',origin=self.origin)
        kw=dict(direction='forward_right',session='session',source_hash='sha',baseline_hash='base',radius=.1,origin=self.origin)
        require_plan(r,**kw)
        for key in ['direction','odom_session','departure_sha256','baseline_hash']:
            bad=dict(r);bad[key]='wrong'
            with self.assertRaises(ValueError):require_plan(bad,**kw)
        kw['origin']=(self.origin[0]+.006,*self.origin[1:])
        with self.assertRaises(RuntimeError):require_plan(r,**kw)

if __name__=='__main__':unittest.main()
