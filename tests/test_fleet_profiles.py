"""합친 실행 구성이 각 실물 설정·그래프를 유지하는지 검증한다."""
from pathlib import Path
import hashlib,json,sys,unittest,yaml
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'farm_project'; C=P/'robot/config'
for pkg in ('transport_robot','farm_navigation','farm_docking'):
 sys.path.insert(0,str(P/'robot/ros_ws/src'/pkg))
from transport_robot.configuration import load_profile,destination
from transport_robot.route_policy import apply_route_policy
from farm_navigation.route import RouteGraph
class Profiles(unittest.TestCase):
 def test_graphs_match_remote_baselines(self):
  for key,expected in json.loads((ROOT/'tests/data/robot_baseline_hashes.json').read_text()).items():
   role,_,name=key.split('/')
   self.assertEqual(hashlib.sha256((C/f'maps/{role}_real'/name).read_bytes()).hexdigest(),expected)
 def test_scout_all_graph_consumers(self):
  env=yaml.safe_load((C/'environments/scout_real.yaml').read_text())
  expected='robot/config/maps/scout_real/graph.geojson'
  self.assertEqual(env['route_graph'],expected)
  patrol=json.loads((C/'patrol/scout_real_sections.json').read_text())
  self.assertEqual(patrol['route_graph'],expected)
  self.assertEqual([x['observation_node_id'] for x in patrol['sections']['SEC01']['segments']],[4,8,9])
  survey=json.loads((C/'survey/scout_real.json').read_text())['sections']['SEC01']
  self.assertEqual(survey['route_file'],expected);self.assertEqual(survey['harvest_goal']['route_file'],expected)
  g=RouteGraph(P/expected)
  self.assertTrue(g.plan(g.nodes[22],g.nodes[4],.15,.02).points)
 def test_transport_choices_preserve_routes(self):
  for f in ('transport_current','transport_docking_trial'):
   p=load_profile(P,f'robot/config/environments/{f}.yaml','real'); g=RouteGraph(p['route_graph'])
   apply_route_policy(g,p['route_policy'])
   self.assertFalse(any({e.start,e.end}=={5,12} for e in g.edges))
   self.assertAlmostEqual(g.nodes[15][0],2.251)
   self.assertEqual(destination(p,g,'SORT_01')[0],g.nodes[17])
   self.assertTrue(g.plan(g.nodes[20],g.nodes[17],.15,.02).points)
   def walk(x):
    if isinstance(x,dict):
     for k,v in x.items():
      if k=='graph_file':self.assertEqual((C/'docking'/v).resolve(),Path(p['route_graph']))
      else:walk(v)
    elif isinstance(x,list):
     for v in x:walk(v)
   walk(p['precision_registry'])
 def test_current_and_candidate_are_explicit(self):
  get=lambda n:load_profile(P,f'robot/config/environments/{n}.yaml','real')['precision_registry']['profiles']
  cur=get('transport_current'); new=get('transport_docking_trial')
  self.assertFalse(any(v.get('initial_marker_recovery',{}).get('enabled') for v in cur.values()))
  self.assertTrue(new['harvest_approach_42']['initial_marker_recovery']['enabled'])
  self.assertAlmostEqual(cur['sort_departure_distance_trial']['distance_departure']['map_yaw_rad'],0.05940237485379369)
  self.assertEqual(new['sort_departure_distance_trial']['distance_departure']['map_yaw_rad'],0.)
if __name__=='__main__':unittest.main()
