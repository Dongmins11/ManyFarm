# 시뮬 운송 마커 관측 제한시간 조정 — 2026-10-29

- 사용자 승인: “180초는 코드에 박혀있어? 시뮬레이션용으로 여유롭게 적용해야돼”. 기준 main 18d0e00 및 기존 미커밋 변경 보존.
- 원인: 공통 PrecisionServer.observe_harvest에서 출발 시 time.monotonic 기준 관측 만료를 설정. 프로파일 observation_timeout_s=180. 이번 주행 예산419초보다 먼저 만료돼 NAVIGATION_FAILED. 19:18:07 출발→19:21:09 실패. 실제180초 동안 sim103.6초 진행, 운송 라이다 위치(-5.672,11.534)에서 목표(-5.955,3.266)까지 직선8.27m 남음. 수확9/9 성공·7개 수확, 인계 이후 미실행.
- 변경: sim/ros_ws/src/farm_sim_config/config/docking/transport_profiles.yaml의 harvest_approach_42.route_handoff.observation_timeout_s 180→900초(실제시간15분). 공통 코드/실물 프로파일/다른 타임아웃·주행 실패/도킹 판정/센서 최신성 기준 불변.
- 시험 준비기는 Git 원본 실물 프로파일을 조립하므로 sim/tools/prepare_pickup_trial.py에서 이 항목만 시뮬 원본 설정으로 선택하고 pickup_adaptations.json에 원본180/적용900 및 근거 기록. 다른 원본 설정 보존.
- 검증: 전체 시험 --prepare-only 성공. 생성 precision_profiles.json을 실패 당시 실행본과 구조 비교해 해당 항목만 다름을 확인. 문법/diff 및 farm_sim_config 빌드 성공. 실제 시뮬레이션 재실행 없음.
- 새 실행부터 적용. 기존 실패 로그/실행 설정은 변경하지 않음. 주행419초 및 시험 접근대기480초 등 다른 독립 제한은 유지하므로 무제한 주행 허용 아님. 모든 장거리 조건 보증은 아님.
- 근거: sim/runs/sec01_reuse_cycle_20261029_attempt01/{transport.log,transport_journal/transport_01_tasks.json,sorting/integration_events.jsonl}; 준비결과 sim/runs/observation_budget_20261029_prepared/runtime/.
- 복원: 시뮬 설정을180으로 되돌리면 시험 조립기도180 선택. 미커밋·미푸시.
