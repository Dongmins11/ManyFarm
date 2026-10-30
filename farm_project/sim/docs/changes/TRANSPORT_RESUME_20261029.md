# 수확 완료 상태에서 운송 재개 — 2026-10-29

사용자 요청: 수확 완료 상태로 두고 운송부터 재개. 기준 main 18d0e00 및 기존 미커밋 변경. 공통·실물 코드는 변경하지 않음.

## 복원 범위와 근거

- 원본 시험 `sim/runs/sec01_reuse_cycle_20261029_attempt01/`: 수확9/9 SUCCESS, 집계7개. 이후 운송 마커 관측180초 만료 실패, 인계 전 종료.
- 원본 Isaac session `4efc9bf857ac41a3957285d7a45b8702` 마지막 harvest_scene.json과 같은 세션 basket_alignment의 실제 바구니 모서리를 대조. 바구니 안 빨강·노랑 과실10개. 레이저 수확 집계7과 실제 적재10의 불일치를 보존하며 원인을 확정하지 않음.
- 원본 스냅샷을 `sim/runs/transport_resume_inputs_20261029/`에 보존. 새 실행에 사본/해시/실제prim목록/수확 결과 사본 포함. 성공 target_id는 실제 레이저 통과 물체 신원 확정이 아니므로 복원 물체 선택에 쓰지 않음.
- 수확로봇 초기XY/yaw를 마지막 실제 위치로 설정하고 AMCL 초기pose를 동일하게 설정. 정상 station 복귀 목적지는 기존값 유지. 운송은 기존 station에서 재출발. 실시간 정답좌표를 제어에 주입하지 않음.
- 해당 기존10개 과실만 원래 농장 prim을 사용해 저장된 bbox 중심으로 초기 배치. 원본 자산 자세/속도0 사용, 과실 원래 위치에 복제본을 남기지 않음. 과거 세션의 물리엔진/과실 자세·속도/공통 미션 메모리 전체를 복원하는 체크포인트 아님. 다른 과실과 환경은 새 씬.
- 실제 물리5sim초 안정화 후10개 모두 바구니에 있는지 검사. 누락이면 운송 전 실패. 현재 세션의 새 HarvestTask/ScoutArea는 보내지 않으며 과거 수확9건과 집계7은 `harvest_reused`로 분리 기록. 이후 인계는 현재 물리 위치/정렬/정지 조건으로 새로 확인.

## 변경 및 검증

- prepare_transport_resume.py: 이전 수확성공/같은 세션 스냅샷 검증, 복원 manifest/초기배치 생성.
- run_single_cycle.py: --resume-harvest/--resume-scene 분기 및 수확 초기배치 선택.
- sorter_runtime.py: 명시적 초기 적재 복원; 성공 결과 생성 안 함.
- single_cycle_steps.py/probe_handoff_window.py: 안정화·적재검사 후 예찰·수확 생략하고 운송부터 기존 순서 수행.
- cycle_monitor.py: 재사용 수확9건/7개를 완료된 과거 실적으로 표시.
- 준비 전용 실행 성공, 수량7/10 분리·AMCL/초기배치 일치·관측900초·문법/diff 확인. 관련 기존11검사 통과, farm_sim_runtime 빌드 성공. 복원 물리와 전체완주는 실행 결과로 별도 확인.

## 실제 실행

19:34 KST `sim/runs/transport_resume_20261029_attempt01/` 시작. ROS Domain13/SUBNET, CPU60/render30, headless. 운송→도킹/인계→선별장 이동/선별→운송·수확 복귀. 작업 실패 후 자동 재시도 없음. 현재 최종 결과 미확정.

복원 방법: 재개 옵션을 생략하면 기존 예찰/수확 흐름. 새 초기 적재는 manifest가 명시된 시험에서만 실행. 이전 실패 폴더는 수정하지 않음. 미커밋·미푸시.

## 실제 재개 확인

- attempt01은 과실 복원 준비 검사에서 실패: 비활성 selective rigid view 좌표를 읽어10개가 잘못 배치됨. 운송/수확 Goal0건. 원시 로그 보존. 비활성 과실의 보존 좌표/원본 자세를 사용하도록 수정하고 해당 회귀 검사1개 PASS.
- attempt02: 실제 물리 안정화 후10/10개 바구니 안 확인, TransportPickup 수락/출발. 예찰/수확 Goal0건, 과거 수확9건·7개 재사용. source session의 PHYSICAL_DETACH 로그에도 복원10개 모두 존재함을 확인.
- 현재 실행은 sim/runs/transport_resume_20261029_attempt02/. 앞의 attempt01은 준비실패이며 업무 재시도와 구분. 최종 인계/선별/복귀 결과는 아직 미확정. 근거 sim/docs/test_results/20261029_transport_resume/. 웹 관제의 별도 작업목록 연결은 이번 변경에 포함하지 않음.
