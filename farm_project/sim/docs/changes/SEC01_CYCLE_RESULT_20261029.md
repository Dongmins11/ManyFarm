# SEC01 한 사이클 시험 결과 — 2026-10-29 보고

실행: 2026-10-28 21:45:40~22:41:17 KST, 약55분37초. Domain13/SUBNET, CPU60/render30. SEC01 예찰 후 예찰로봇은 SEC02로 계속 진행하고 수확로봇은 SEC01 전체 윈도우를 처리했다. 기준18d0e00+미커밋 수정. 본 보고에서 제어 수정/재시험은 하지 않았다.

## 결과

- SEC01 예찰 SUCCESS: 관측5구간, 윈도우9개, expected13개.
- SEC02 예찰 SUCCESS: 관측5구간, 윈도우8개, expected11개. 결과 보존, SEC02 수확은 이번 범위 아님.
- SEC01 수확 액션9/9 SUCCESS. 실제 harvested8/expected13=61.5%, 차이5개. 액션 성공은 주행·팔 처리의 정상 종료를 의미하며 과실 전량 수확과 다르다.
- 수확 접근1회+윈도우 이동9회 진단 모두 ARRIVED/Nav2 status4. 이번 scout/harvest/transport 로그에서 Failed to make progress/105/NAV_FAILED 발견 없음. 이전 북쪽통로 대향 간섭은 이번 순서에서 재현되지 않았다. 교통관제 연결 검증을 의미하지 않는다.
- 운송 호출은 접수 단계 REJECTED. 인계·선별장 이동·선별·양 로봇 복귀 미실행. 전체 passed=false, 자동 업무 재시도 없음. 시험 소유 프로세스 모두 종료 기록 있음.

| 윈도우 | 예찰 예상 | 실제 수확 | 액션 소요(실제시간) |
|---|---:|---:|---:|
| W001 | 1 | 0 | 3분 54초 |
| W002 | 1 | 0 | 0분 37초 |
| W003 | 1 | 1 | 12분 55초 |
| W004 | 2 | 1 | 6분 24초 |
| W005 | 1 | 1 | 3분 59초 |
| W006 | 1 | 1 | 4분 23초 |
| W007 | 2 | 2 | 8분 53초 |
| W008 | 2 | 0 | 0분 39초 |
| W009 | 2 | 2 | 10분 15초 |

수확 전체21:49:16~22:41:16, 약52분, 윈도우당 평균5분47초(첫 진입 주행 포함). W003이12분55초로 가장 길었다. 이번 보고에서는 팔 지연의 세부 원인을 재분석하지 않았다.

수량 차이5개 중 W001/W002/W008의 예상4개는 `student_no_reachable_targets_arms_stowed`로 종료. 팔에서 수확 가능한 대상으로 선정되지 않았다는 결과이며 AI 미검출/필터/IK 중 정확한 원인은 이 메시지만으로 구분할 수 없다. W004는 예상2/수확1로1개 부족. 결과의 failed_count=0을 누락0으로 해석하지 않는다. 61.5%는 예찰 expected 대비 카운터 비율이며 실제 배치 전체 A 대비 회수율은 아니다.

## 운송 요청 거절 원인

실제 transport.log: `Goal 거절: 수령 장치 미연결: LID_OPEN`. 운송 주행/마커 인식/물리 도킹 실패가 아니라 요청 접수 전 장치 준비 확인 실패다.

실행 설정은 pickup_lid_enabled=true로 덮개 기능이 켜져 있다. 하지만 `mechanical_device.unload_service=sim/sorter/unload`, `stop_service=sim/sorter/stop`이다. 공통 TriggerDevice.operation_ready(LID_OPEN)는 덮개 서비스뿐 아니라 available()의 UNLOAD/STOP 서비스 준비도 함께 확인한다. 이 두 서비스는 `probe_sorter_cycle.py`가 만들며, 새 통합 시험기의 `after_handoff()`는 인계 완료 뒤에야 이 프로세스를 실행한다. 따라서 운송 접수 때 필요한 서비스가 아직 존재하지 않아 거절되는 순서상 결함이다.

근거 코드: sim/tools/run_sorter_cycle_trial.py의prepare_sorter, sim/tools/single_cycle_steps.py의after_handoff, sim/tools/probe_sorter_cycle.py의create_service, robot/ros_ws/src/transport_robot/transport_robot/trigger_device.py 및pickup_workflow.py. 정적 호출/실행 설정과 접수 거절 로그가 일치한다. 서비스 시작시점을 수정한 후의 성공 검증은 아직 하지 않았다.

다음 조치: 시뮬 가상 장치 서비스를 운송 접수 전에 준비시키고 동일 서비스 수명 동안 인계→선별장 하역을 연결한다. 실제 도킹/정지/허가 조건은 유지하며 공통 준비 검사를 해제하지 않는다. 수정 전 사전 점검으로 수확을 다시52분 수행한 후 같은 준비 오류를 만나는 상황부터 방지한다.

## 자료

- 실행 원문: sim/runs/sec01_cycle_scout_sec02_20261028_attempt02/
- 공유 근거: sim/docs/test_results/20261029_sec01_cycle_report/ (result, 주요액션/진단, 거절원문, 종료코드)
- attempt01은 앞서 보고한 선별 overlay 누락에 따른 Goal 전 준비실패다. 실제 업무 시험은 attempt02 1회다.
- 원격 반영 없음. 기존 미커밋 코드를 변경하지 않고 결과 문서만 갱신했다.
