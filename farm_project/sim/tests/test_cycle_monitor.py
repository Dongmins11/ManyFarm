"""진행중/종료 전환을 재생해 마지막 feedback이 실패·후속 단계를 덮지 않는지 검사한다."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cycle_monitor import Monitor, select_run

STAMP='2026-10-29T10:36:31+00:00'

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data))

def event(base,kind,**values):
    with (base/'events.jsonl').open('a') as f:f.write(json.dumps(dict(at=STAMP,kind=kind,**values))+'\n')

def job(state='RUNNING',phase='MOVING_STARTED',**values):
    return dict(role='transport',state=state,feedback=dict(event=phase,timestamp=STAMP),observed_events={},**values)

def test_pickup_detail_incremental_and_failure_overrides(tmp_path):
    event(tmp_path,'scout_reused',status=4,result={})
    event(tmp_path,'pickup_started',job_id='p')
    ledger=tmp_path/'control/simul-handoff.json'
    write(ledger,dict(jobs=[job()]))
    m=Monitor(tmp_path);m.poll();assert '수확로봇으로 주행 중' in m.screen()
    p=tmp_path/'precision.log'
    line='[INFO] [1793270475.442969598] [dock]: Station docking phase: WAIT_INITIAL_MARKER'
    p.write_text(line);m.poll();assert '정차 후 마커 재확인 중' not in m.screen()
    with p.open('a') as f:f.write('\n')
    m.poll();assert '정차 후 마커 재확인 중' in m.screen()
    with p.open('a') as f:f.write('[INFO] [1793270478.51] [dock]: Station docking phase: BACKOUT_FOR_MARKER\n')
    m.poll();assert '마커 재확인을 위해 후진 중' in m.screen()
    write(ledger,dict(jobs=[job('FAILED',result=dict(error_code='DOCK_FAILED',error_message='Initial marker reacquisition exhausted'))]))
    m.poll();screen=m.screen()
    assert '운송  | 실패 · DOCK_FAILED' in screen and ' |  중단' in screen
    assert '오류: DOCK_FAILED / Initial marker reacquisition exhausted' in screen
    assert '후진 중' not in screen
    ledger.write_text('{');m.poll();assert 'DOCK_FAILED' in m.screen()


def test_reused_results_and_feedback_do_not_double_count(tmp_path):
    event(tmp_path,'scout_reused',status=4,result=dict(harvest_task_count=1,total_expected_count=2))
    r=dict(status=4,result=dict(task_id='h',result_code='SUCCESS',harvested_count=2))
    event(tmp_path,'harvest_reused',results=[r])
    event(tmp_path,'harvest_goal',goal=dict(harvest_task=dict(task_id='h')))
    event(tmp_path,'harvest_feedback',data=dict(task_id='h',success_count=2))
    m=Monitor(tmp_path);m.poll();m.poll()
    assert '수확 집계 2개' in m.screen() and '이전 시험 실적 재사용' in m.screen()
    assert len(m.harvested)==1


def test_approach_completion_advances_progress(tmp_path):
    event(tmp_path,'pickup_started',job_id='p')
    j=job(phase='WAITING_FOR_TRANSFER');j['observed_events']={'WAITING_FOR_TRANSFER':STAMP}
    write(tmp_path/'control/simul-handoff.json',dict(jobs=[j]))
    m=Monitor(tmp_path);m.poll()
    assert '수령 접근 완료' in m.screen() and '1/4 단계' in m.screen()


def test_post_sorter_stages_and_success(tmp_path):
    event(tmp_path,'unload_goal',data={})
    event(tmp_path,'unload_feedback',data=dict(event='MOVING_STARTED',timestamp=STAMP))
    m=Monitor(tmp_path);m.poll();assert '선별장으로 주행 중' in m.screen()
    event(tmp_path,'unload_feedback',data=dict(event='DOCKING_STARTED',timestamp=STAMP))
    m.poll();assert '정밀 도킹 중' in m.screen()
    event(tmp_path,'unload_result',status=4,result=dict(result_code='SUCCESS'))
    event(tmp_path,'sort_goal',data={})
    event(tmp_path,'sort_feedback',data=dict(phase='HOME',red_count=1,yellow_count=1))
    write(tmp_path/'cargo_manifest.json',dict(fruit_paths=['a','b']))
    m.poll();assert '선별 중 · HOME' in m.screen() and '2/2 과실' in m.screen()
    event(tmp_path,'sort_result',status=4,result=dict(result_code='SUCCESS',red_count=1,yellow_count=1))
    event(tmp_path,'return_goal',data={})
    event(tmp_path,'return_feedback',data=dict(phase='RETURNING'))
    m.poll();assert '복귀 · 스테이션으로 주행 중' in m.screen()
    event(tmp_path,'return_result',status=4,result=dict(result_code='SUCCESS'))
    write(tmp_path/'result.json',dict(passed=True))
    m.poll();assert '4/4 단계' in m.screen() and ' |  완료' in m.screen()


def test_failed_return_is_not_displayed_as_moving(tmp_path):
    event(tmp_path,'unload_goal',data={})
    event(tmp_path,'return_goal',data={})
    event(tmp_path,'return_result',status=6,result=dict(result_code='FAILED',error_code='NAVIGATION_FAILED'))
    m=Monitor(tmp_path);m.poll()
    assert '운송  | 실패 · NAVIGATION_FAILED' in m.screen()
    assert ' |  중단' in m.screen()


def test_reused_scout_not_shown_as_running_during_setup(tmp_path):
    write(tmp_path/'reused_scout_result.json',dict(scout_result={}))
    m=Monitor(tmp_path);m.poll()
    assert '예찰 생략 · 재사용 준비 중' in m.screen()
    assert '예찰/이동 중' not in m.screen()


def test_auto_follow_retry_clears_previous_progress_and_failure(tmp_path):
    parent=tmp_path/'cycle';first=parent/'attempt_001';second=parent/'attempt_002'
    write(first/'single_cycle.json',{})
    event(first,'harvest_result',status=4,result=dict(task_id='old',harvested_count=3,result_code='SUCCESS'))
    event(first,'error',detail='old failure')
    write(parent/'status.json',dict(state='RESTARTING',current=str(first)))
    m=Monitor(select_run(None,runs_root=tmp_path));m.poll()
    assert 'old failure' in m.screen() and len(m.harvested)==1
    # supervisor는 새 폴더/로그 생성 전 current부터 기록한다.
    write(parent/'status.json',dict(state='RUNNING',current=str(second)))
    target=select_run(None,m.base,runs_root=tmp_path)
    assert target==second
    m=Monitor(target);m.poll()
    assert not m.harvested and 'old failure' not in m.screen()
    second.mkdir()
    event(second,'pickup_started',job_id='new')
    m.poll();assert '운송 접수 대기' in m.screen()


def test_explicit_attempt_stays_fixed_parent_follows_and_partial_status_keeps_current(tmp_path):
    parent=tmp_path/'cycle';first=parent/'attempt_001';second=parent/'attempt_002'
    write(parent/'status.json',dict(state='RUNNING',current=str(second)))
    assert select_run(first)==first
    assert select_run(parent)==second
    (parent/'status.json').write_text('{')
    assert select_run(parent,second)==second
    assert select_run(None,second,runs_root=tmp_path)==second


def test_auto_keeps_latest_success_and_can_follow_new_standalone(tmp_path):
    import os
    old=tmp_path/'old';parent=tmp_path/'cycle';last=parent/'attempt_003'
    write(old/'single_cycle.json',{});event(old,'pickup_started')
    for p in old.iterdir():os.utime(p,(1,1))
    write(parent/'status.json',dict(state='SUCCEEDED',successful_attempt=str(last)))
    assert select_run(None,runs_root=tmp_path)==last
    standalone=tmp_path/'new'
    write(standalone/'single_cycle.json',{})
    os.utime(standalone/'single_cycle.json',((parent/'status.json').stat().st_mtime+1,)*2)
    assert select_run(None,last,runs_root=tmp_path)==standalone
