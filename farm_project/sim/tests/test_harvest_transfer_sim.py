"""가상 수확 인계의 실제 증거/취소 경계와 교통 자료 정합 검사."""
from pathlib import Path
import sys
import time
import unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import hashlib
import json
import yaml

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_sim_devices',):
    sys.path.insert(0,str(ROOT/'sim/ros_ws/src'/package))
for package in ('farm_navigation','harvest_robot'):
    sys.path.insert(0,str(ROOT/'robot/ros_ws/src'/package))
from farm_sim_devices.harvest_transfer_ros import TransferObservation, HarvestTransferServer


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.obs = TransferObservation()
        self.arm = dict(status='IDLE',safe_stopped=True,busy=False,
                        travel_ready=True,travel_ready_measured=True)
        self.obs.observe('session',self.arm,dict(hold_pass=True,sim_time_s=10.),10.)

    def test_complete_measured_evidence_accepts(self):
        self.assertTrue(self.obs.prepared(10.1));self.assertTrue(self.obs.aligned(10.1))

    def test_each_missing_evidence_rejects(self):
        for key, value in [('busy',True),('safe_stopped',False),('travel_ready',False),
                           ('travel_ready_measured',False),('status','RUNNING')]:
            with self.subTest(key=key):
                arm = dict(self.arm);arm[key] = value
                self.obs.observe('session',arm,dict(hold_pass=True,sim_time_s=10.),10.)
                self.assertFalse(self.obs.aligned(10.1))

    def test_stale_or_future_clock_rejects(self):
        self.assertFalse(self.obs.aligned(9.99));self.assertFalse(self.obs.aligned(10.6))
        self.obs.received = time.monotonic()-1.
        self.assertFalse(self.obs.aligned(10.1))

    def test_missing_or_stale_alignment_rejects_without_blocking_prepare(self):
        for proof in (None,{},dict(hold_pass=False,sim_time_s=10.),dict(hold_pass=True,sim_time_s=9.)):
            self.obs.proof = proof
            self.assertTrue(self.obs.prepared(10.1));self.assertFalse(self.obs.aligned(10.1))

    def server(self):
        import threading
        obj = HarvestTransferServer.__new__(HarvestTransferServer)
        obj.observation=self.obs;obj.lock=threading.RLock();obj.busy=False;obj.stopping=False
        obj.completed=set();obj.now=lambda:10.1;obj.goal_response=S(ACCEPT='accept',REJECT='reject')
        obj.node=S(get_logger=lambda:S(info=lambda message:None))
        obj.action=S(Result=lambda **kw:S(error_codes=[],error_message='',**kw),Feedback=lambda **kw:S(**kw))
        return obj

    def handle(self):
        h=S(request=S(transfer_id='T1'),is_cancel_requested=False,status='',phases=[])
        h.succeed=lambda:setattr(h,'status','success');h.abort=lambda:setattr(h,'status','failed')
        h.canceled=lambda:setattr(h,'status','canceled')
        h.publish_feedback=lambda feedback:h.phases.append(feedback.phase)
        return h

    def test_action_success_and_duplicate_rejection(self):
        s=self.server();h=self.handle()
        self.assertEqual(s.goal(h.request),'accept')
        self.assertEqual(s.goal(S(transfer_id='T2')),'reject')
        result=s.execute(h)
        self.assertEqual(h.status,'success');self.assertEqual(result.error_codes,[])
        self.assertEqual(h.phases,['OPENING','DISCHARGING','CLOSING'])
        self.assertEqual(s.goal(h.request),'reject')

    def test_cancel_session_change_or_expired_evidence_cannot_succeed(self):
        for reason in ('cancel','session','expired','stop'):
            with self.subTest(reason=reason):
                self.setUp();s=self.server();h=self.handle();s.goal(h.request)
                def feedback(_):
                    if reason=='cancel':h.is_cancel_requested=True
                    elif reason=='session':self.obs.session='new'
                    elif reason=='expired':self.obs.received-=1.
                    else:s.stop(None,S())
                h.publish_feedback=feedback
                result=s.execute(h)
                self.assertIn(h.status,('canceled','failed'));self.assertTrue(result.error_codes)
                self.assertNotIn('T1',s.completed);self.assertFalse(s.busy)

    def test_stop_does_not_claim_unobserved_arm_stop(self):
        s=self.server();self.arm['busy']=True
        self.assertFalse(s.stop(None,S()).success)
        self.assertFalse(s.prepare(None,S()).success)


class FrameBindingTests(unittest.TestCase):
    def test_sim_uses_configured_odom_in_costmap_spin_and_all_paths(self):
        from farm_navigation.configuration import load_environment, load_nav2_parameters, read_mapping
        from farm_navigation.navigation_types import NavigationSettings
        from harvest_robot.handoff_server_config import build_server_config
        profile=load_environment(ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml', ROOT,
                                 'sim', require_survey=False)
        nav=load_nav2_parameters(profile['nav_params'],ROOT)
        wall=read_mapping(ROOT/'robot/config/robots/vicpinky/transfer/wall_alignment_wait_v2.json')
        bundle=build_server_config(nav,profile['robot_id'],wall,
                                  NavigationSettings.from_mapping(profile['navigation']),True)
        self.assertEqual(bundle['costmap']['global_frame'],'harvest_01/odom')
        self.assertEqual(bundle['spin']['local_frame'],'harvest_01/odom')
        self.assertEqual(bundle['spin']['global_frame'],'harvest_01/odom')
        self.assertTrue(bundle['spin']['use_sim_time'])
        for parameters in bundle['profile']['navigation'].values():
            self.assertEqual(parameters['map_frame'],'harvest_01/odom')
        nav['local_costmap']['local_costmap']['ros__parameters']['global_frame']='map'
        with self.assertRaises(ValueError):
            build_server_config(nav,profile['robot_id'],wall,
                                NavigationSettings.from_mapping(profile['navigation']),True)


class RegistryTests(unittest.TestCase):
    def test_operational_graphs_and_manifest_match(self):
        config=ROOT/'sim/ros_ws/src/farm_sim_config'
        directory=config/'config/traffic'
        raw=(directory/'traffic_zones.yaml').read_bytes();z=yaml.safe_load(raw)
        manifest=json.loads((directory/'source_manifest.json').read_text())
        self.assertEqual(z['zone_revision'],manifest['zone_revision'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['revision_catalog']['zones']['file_sha256'])
        for gid, spec in z['graphs'].items():
            b=(directory/spec['source_file']).read_bytes()
            self.assertEqual(b,(config/'maps'/Path(spec['source_file']).name).read_bytes())
            self.assertEqual(hashlib.sha256(b).hexdigest(),manifest['revision_catalog']['graphs'][gid]['source_sha256'])
            features={str(f['properties']['id']):f for f in json.loads(b)['features']}
            for fid in ('30514','30515'):
                zone=z['zones'][z['graph_mappings'][gid]['edge_to_zone'][fid]]
                f=features[fid];ref=next(v for v in zone['graph_refs'] if v['graph_id']==gid and v['edge_id']==fid)
                self.assertEqual(ref['coordinates_m'],f['geometry']['coordinates'])
                for x,y in ref['coordinates_m']:
                    a,b,c,d=zone['bounds_m'];self.assertTrue(a<=x<=c and b<=y<=d)
        self.assertNotIn('sim:E:8004:9019',z['zones'])


if __name__=='__main__':unittest.main()
