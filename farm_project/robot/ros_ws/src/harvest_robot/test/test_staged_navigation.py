"""ROS 없이 미션 순서·취소·좌표 의미를 검증한다. 실물 주행 시험은 아니다."""
import sys
from pathlib import Path
from types import SimpleNamespace as S
from dataclasses import dataclass
import unittest
sys.path.insert(0, str(Path(__file__).parents[1]))
from harvest_robot.staged_navigation import StagedNavigation, Section, load_sections
from harvest_robot.contract import validate_task
from harvest_robot.mission import HarvestMission


@dataclass
class Result:
    accepted: bool = True


class Nav:
    def __init__(self, name, calls, position):
        self.name, self.calls, self.position = name, calls, position
        self.failure = None
        self.canceled = False
    def preflight_navigation(self):
        pass
    def navigate(self, xy, yaw):
        self.calls.append((self.name, tuple(xy), yaw))
        if self.failure:
            raise self.failure
        self.position[:] = xy
        return Result()
    def cancel_nav(self):
        self.canceled = True


def setup():
    calls, records, pos = [], [], [0.,0.]
    approach, work = Nav('route',calls,pos), Nav('pose',calls,pos)
    sections = {'A':Section((1.,0.),0.,(1.,0.),3.14), 'B':Section((5.,0.),0.,(5.,0.),3.14)}
    nav = StagedNavigation(approach, work, sections, lambda: tuple(pos), lambda: None, records.append, .1)
    return nav, approach, work, calls, records, pos



def goal(section='A'):
    return S(robot_id='harvest_01',map_id='map1',section_id=section,harvest_task=S(
        task_id='opaque-task',window_id='opaque-window',expected_count=2,
        goal_pose=S(frame_id='map',position=S(x=2.,y=.4,z=0.),yaw=1.2)))


class TestStagedNavigation(unittest.TestCase):
    def test_first_window_routes_then_uses_exact_goal(self):
        setup = globals()["setup"]()
        nav,_,_,calls,records,_=setup
        nav.navigate('A',(2.,.456),1.2)
        assert calls==[('route',(1.,0.),0.),('pose',(2.,.456),1.2)]
        assert [x['phase'] for x in records]==['SECTION_APPROACH','WINDOW_MOVE']
    
    
    def test_same_section_skips_entry(self):
        setup = globals()["setup"]()
        nav,_,_,calls,_,_=setup
        nav.navigate('A',(2.,.456),1.2)
        calls.clear()
        nav.navigate('A',(3.,.456),1.2)
        assert calls==[('pose',(3.,.456),1.2)]
    
    
    def test_section_change_exits_old_before_routing(self):
        setup = globals()["setup"]()
        nav,_,_,calls,_,_=setup
        nav.navigate('A',(2.,.456),1.2)
        calls.clear()
        nav.navigate('B',(6.,.456),1.2)
        assert calls==[('pose',(1.,0.),3.14),('route',(5.,0.),0.),('pose',(6.,.456),1.2)]
    
    
    def test_failure_stops_chain_and_cancels_owner(self, failing="route"):
        setup = globals()["setup"]()
        nav,a,w,calls,_,_=setup
        selected=a if failing=='route' else w
        selected.failure=RuntimeError('failed')
        with self.assertRaises(RuntimeError): nav.navigate('A',(2.,.4),0.)
        assert nav.current_section is None
        nav.cancel_nav()
        assert selected.canceled
        assert len(calls)==(1 if failing=='route' else 2)
    
    
    def test_relocation_invalidates_previous_section(self):
        setup = globals()["setup"]()
        nav,_,_,calls,_,pos=setup
        nav.navigate('A',(2.,.4),0.)
        pos[:]=[0.,0.]
        calls.clear()
        nav.navigate('A',(3.,.4),0.)
        assert calls[0][0]=='route'
    
    
    def test_restart_routes_again(self):
        setup = globals()["setup"]()
        nav,a,w,calls,records,pos=setup
        nav.navigate('A',(2.,.4),0.)
        restored=StagedNavigation(a,w,nav.sections,lambda:tuple(pos),lambda:None,records.append,.1)
        calls.clear()
        restored.navigate('A',(3.,.4),0.)
        assert calls[0][0]=='route'
    
    
    def test_unknown_section_never_moves(self):
        setup = globals()["setup"]()
        nav,_,_,calls,_,_=setup
        with self.assertRaises(ValueError):nav.navigate('X',(2.,0.),0.)
        assert calls==[]
    
    
    def test_cancellation_between_stages_prevents_work(self):
        setup = globals()["setup"]()
        nav,_,_,calls,_,_=setup
        def check():
            if calls:raise RuntimeError('cancel')
        nav.check=check
        with self.assertRaises(RuntimeError):nav.navigate('A',(2.,0.),0.)
        assert len(calls)==1
        nav.cancel_nav()
        assert nav.current_section is None
    
    
    def test_config_reads_graph_not_hardcoded(self):
        cfg={'sections':{'Z':{'entry_node':17,'entry_heading_node':18,'exit_node':18,'exit_heading_node':17}}}
        sections=load_sections(cfg,S(nodes={17:(4.,2.),18:(4.,3.)}))
        assert sections['Z'].entry==(4.,2.)
        self.assertAlmostEqual(sections['Z'].entry_yaw, 1.5707963268)
    
    
    def test_missing_config_rejected(self):
        with self.assertRaises(ValueError):load_sections({},S(nodes={}))
    
    
    def test_contract_does_not_parse_window_id(self):
        validate_task(goal(),dict(robot_id='harvest_01',map_id='map1',movement_mode='route_then_pose',sections={'A':{}}))
    
    
    def test_contract_requires_explicit_section(self):
        with self.assertRaises(ValueError):validate_task(goal(''),dict(robot_id='harvest_01',map_id='map1',movement_mode='route_then_pose',sections={'A':{}}))
    
    
    def test_legacy_contract_stays_compatible(self):
        validate_task(goal(''),dict(robot_id='harvest_01',map_id='map1'))
    
    
    def test_mission_keeps_tag_control_over_both_stages(self):
        setup = globals()["setup"]()
        staged,a,_,calls,_,_=setup
        tags=[]
        n=S(staged_navigation=staged,navigator=a,check=lambda:None,blocked=False,
            tag_control=S(begin=lambda:tags.append('begin'),end=lambda:tags.append('end')))
        assert HarvestMission(n,goal()).run()=={'accepted':True}
        assert tags==['begin','end']
        assert [x[0] for x in calls]==['route','pose']
    
    
    def test_mission_failure_cancels_and_ends_tag(self):
        setup = globals()["setup"]()
        staged,a,w,_,_,_=setup
        w.failure=RuntimeError('blocked path')
        tags=[]
        n=S(staged_navigation=staged,navigator=a,check=lambda:None,blocked=False,
            tag_control=S(begin=lambda:tags.append('begin'),end=lambda:tags.append('end')))
        with self.assertRaises(RuntimeError):HarvestMission(n,goal()).run()
        assert w.canceled and tags==['begin','end']
    
    
    def test_cancel_failure_blocks_next_goal(self):
        setup = globals()["setup"]()
        staged,a,w,_,_,_=setup
        w.failure=RuntimeError('path failed')
        def fail():raise RuntimeError('no response')
        w.cancel_nav=fail
        n=S(staged_navigation=staged,navigator=a,check=lambda:None,blocked=False,tag_control=None)
        with self.assertRaisesRegex(RuntimeError,'CANCEL_UNCONFIRMED'):HarvestMission(n,goal()).run()
        assert n.blocked

    def test_work_failure(self):
        self.test_failure_stops_chain_and_cancels_owner("pose")

if __name__ == "__main__":
    unittest.main()
