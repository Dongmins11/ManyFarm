# 새 예찰부터 전 로봇 복귀·선별 완료까지 전체 반복 시험

## 실행 상태

2026-10-30 01:08:48 KST 반복시험 시작. 본 기록 시점에는attempt_001 진행 중이며 전체 성공은 아직 확인하지 않았다. SEC01예찰5/5완료(9윈도우/예상14개), SEC02예찰5/5완료, SEC01수확 진행 중이다. 최신 상태는 아래status.json/현재시도로그가 기준이다.

- 상태/실패이력: sim/runs/fresh_full_cycle_20261030/status.json
- 시도별 로그: sim/runs/fresh_full_cycle_20261030/attempt_NNN/
- 상위 실행로그: sim/runs/fresh_full_cycle_20261030/attempt_NNN_runner.log
- 기준 소스/해시: sim/runs/fresh_full_cycle_20261030/source/ 및 source_manifest.json

## 요청과 실행 순서

1. 매 시도 새 시뮬레이션·초기 과실·스테이션에서 SEC01 예찰 시작. 과거 예찰/수확 결과 재사용 금지.
2. SEC01예찰 성공 뒤 SEC02예찰 접수와 SEC01수확 시작. 새예찰의 모든 윈도우를 순서대로 수확.
3. SEC01수확 완료 뒤 운송 호출/도킹/실제바구니과실 가상인계/이격 및 수확window복원.
4. 인계 양쪽성공 뒤 운송선별장이동과 수확스테이션복귀 병행.
5. 선별장도킹·과실투입·차체이격 완료 뒤 선별과 운송스테이션복귀 병행.
6. SEC02예찰을 마친 예찰로봇은 대기 후 다른 두 로봇 복귀가 끝나면 스테이션복귀. 기존 통로의 역방향 병목을 피하는 시험 순서다.
7. 모든필수결과 및 전량선별 성공에서 종료. 실패하면 해당시도로그/영상을 남기고 모든시험프로세스 정리 뒤 새시뮬로1번부터 반복. 시도상한/부분성공 종료 없음.

## 성공 기준

- SEC01/SEC02 ScoutArea, 새로생성된 모든SEC01 HarvestTask, TransportPickup, DockTransfer, BucketUnload, SortBatch, 세로봇 ReturnToStation 성공.
- transfer_complete/transport_clear/restore_complete 모두true.
- 실제투입배치가 비어있지 않고, 물리/ROS선별수량 일치, 실제투입과실목록 전부sorted, 잔류0.
- 수확 expected와harvested 차이는 기존정책대로 성능지표이며 액션실패로 바꾸지 않는다.
- 모든원본완료판정/수치/태그인계미사용/실물코드유지. 선별노드의미검출완료규칙은 그대로이고 시험전체의통과조건만 전량선별을요구한다.

## 적용과 확인

시뮬도구 run_single_cycle/probe_handoff_window/single_cycle_steps/probe_sorter_cycle에 --overlap-cycle 선택경로, run_fresh_cycle_until_success 반복실행기, capture_sorter_cycle 관측기 추가. cycle_monitor에예찰복귀표시추가. 기존기본순차시험방식은유지. 선별 병행시험의 바깥 결과대기 watchdog만600→1200실시간초로 여유를주고 로봇액션제한시간은변경하지않았다.

단위검사23개·문법·diff검사 통과. prepare-only로새예찰/빈초기적재/동시진행/전량선별설정 검증. 현재실제시험진행중이므로 병행전체동작검증완료를의미하지않는다.

Domain13/SUBNET, CPU물리60/render30, 수확AMCL alpha4=.002, 시뮬선별ROI Y+5px 유지. 직접액션시험기로 호출하며 관제HTTP/교통관제전체연동검증과는구분한다.

영상은선별단계/수량/검출상태변화시원본PNG와상태를각시도camera_history/에보존. RGB저장과상태기록은약1sim초이내차이가있을수있으며하드웨어동기촬영을주장하지않는다.

커밋/푸시미실행. 자동실행은독립프로세스에서계속되며최초완전성공을기록할때까지반복한다. 변경복원은새옵션/반복실행기미사용으로기존순차시험경로를사용한다.
