# 터미널 시험 모니터 진행 표시 수정 — 2026-10-29

- 사용자 요청: 기존 터미널 모니터의 진행 상황이 제대로 갱신되도록 수정. 기존 미커밋 변경 보존. 시험/로봇 제어·Frontend·공통/실물 코드는 변경하지 않았다.
- 원인: monitor는 pickup_started만 읽고 접근/도킹/인계를 같은 문구로 표시. 별도 Frontend 워커 ledger의 feedback/result를 읽지 않았고, 내부 마커 재관측은 Action feedback 자체도 MOVING_STARTED여서 누락. 전체 실패 후에도 로봇별 진행중 문구가 남았음.
- 수정: sim/tools/cycle_monitor.py가 control/simul-handoff.json의 최신 작업 feedback/result를 읽고 precision.log의 명시적 단계 로그를 증분 소비. 정차 후 마커 재확인/목표 검증/재확인 후진 표시. 최신 feedback 시각 이후의 내부 로그만 해당 단계 보완에 사용.
- 수령 접근→인계→선별장 하역→복귀의 실제 완료 근거에 따라4단계 바 표시. 접근 완료 전0%는 거리 비율이 아니라 단계 완료수. 선별장 이동/도킹/하역·이격, 선별 phase/수량, 복귀 feedback 표시. 실패/취소/미확정 결과를 마지막 진행 상태보다 우선 표시하고 후속 미실행을 명시.
- 과거 수확 실적 재사용 표기 유지, 완료result와feedback 중복집계 방지. 예찰 생략 시험의 준비 단계도 예찰 이동 중으로 표시하지 않음. 긴 원시 오류JSON 대신 운송 오류코드/이유 표시. 기존1초 갱신/읽기전용/부분줄 보호 유지.
- 검사: test_cycle_monitor.py6개 PASS(증분 내부 단계/부분줄, 실패 즉시 반영·JSON작성중 이전상태 보존, 집계중복, 접근완료, 후속단계/완료, 복귀실패, 준비표시 포함). py_compile/diff PASS. 실제 attempt02의 결과를 읽어 운송실패 DOCK_FAILED / Initial marker reacquisition exhausted, 수확완료·후속중단, 선별미실행 표시 확인.
- 실제 시험은 19:41:46 KST 도킹 마커 재확인 실패로 이미 종료됨. 모니터 수정으로 시험을 정지하거나 재실행하지 않았다. 도킹 실패 원인 수정은 이번 표시 작업 범위 밖이다.
- 사용: 기존 모니터에서 Ctrl+C 후 python3 /home/ysy/main/farm_project/sim/tools/cycle_monitor.py 실행. Python 프로세스에 이미 로드된 코드는 파일 수정만으로 갱신되지 않음. Ctrl+C는 모니터만 종료. 폴더 인자를 지정하면 해당 시험에 고정; 새 시험은 모니터 재실행으로 선택.
- 복원: cycle_monitor.py만 직전 버전으로 되돌림. 보고/회귀검사는 참고 자료. 미커밋·미푸시.
