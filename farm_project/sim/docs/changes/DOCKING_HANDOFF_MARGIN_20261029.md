# 도킹 전환 여유 및 초기 재탐색 시계 수정 — 2026-10-29

## 승인·범위

사용자 “조치하고 재시험해” 승인. 기준 main/18d0e00 및 기존 미커밋 작업을 보존한다. 직전 attempt03은 전환 시 목표거리 약1.186m였으나 정차 후1.208~1.225m로 관측되어 1.2m 범위에서 거절됐다. 초기 재탐색30초도 실제시간으로 계산했다. 관측 변동 원인을 물리 이동으로 단정하지 않는다.

## 변경

- 공통 `robot/ros_ws/src/farm_docking/farm_docking/precision_server.py`: 경로→도킹 readiness에 선택적인 `route_handoff.approach_margin_m`을 적용. 기본0으로 실물 기존 전환 보존. 유한값/0 이상/허용거리 미만 검증, 잘못된 값은 ready=false. 시뮬은0.1m를 적용해1.1m 이내에서 전환한다. 실제 도킹 허용1.2m·정차 후8개 새 샘플·속도·성공 판정은 보존.
- 같은 공통 파일: 초기 마커복구 및 거리/방향 취득의 시작·경과 시계를 `motion_time/motion_elapsed`로 통일. sim은ROS /clock, real은기존monotonic. 대기3초/관측검증2초/복구30초 수치는 유지. /clock 역행은 실패로 처리. 센서 단절/통신/제어권 watchdog은 실제시간 유지.
- `sim/ros_ws/src/farm_sim_config/config/docking/transport_profiles.yaml`: 전환 여유0.1m 명시. 직전 관측변동약4cm 대비 보수적 여유이며 실물 검증값은 아니다.
- `sim/tools/prepare_pickup_trial.py`: 원본9686aca 프로파일 조립 후 승인된 여유만 시뮬 override에 추가하고 `pickup_adaptations.json`에 전후값 기록. 실물 원본 YAML 변경 없음.
- 회귀검사: `sim/tests/test_harvest_route_envelope.py`, `sim/tests/test_docking_motion_clock.py`.

## 검증

- 두 시험 파일 합계29개 PASS. 느린/일시정지 시계, 시계역행, 실물monotonic 보존, 초기복구30초, 검증대기2초, 거리취득시계 일치, 경계전환/설정누락/잘못된 여유 등을 검사.
- farm_docking 및 farm_sim_config 빌드 PASS, py_compile/diff 검사 PASS.
- 실행 조립 결과: 여유0.1m, 도킹최대1.2m, 초기복구30초. Domain13/SUBNET, CPU물리60/render30.
- 실제 attempt04 완료: `sim/runs/transport_docking_retest_20261029_attempt04/`. 수확 완료 데이터 및 실제과실10개 재사용, 도착전용 재검증 후 운송 출발→42→수확차체인계자세→41 DOCK_STABLE까지만 시험. 새 예찰/수확·배출·선별은 범위 밖. 운송 출발→최종 DOCK_STABLE 성공. 상세 실측은 아래 참조.

## 복원·전달

이번 margin 조회/검증 및 초기복구·거리취득 시계 부분만 되돌린다. 이전 라이다/상위 시계 수정과 다른 미커밋 수정은 보존한다. 시뮬 margin을0으로 설정하면 이전 경계전환 동작이 된다. 실물 직접시험은 미실행. 미커밋·미푸시.

변경 파일 ZIP은 `sim/runs/docking_handoff_margin_20261029_changes.zip`으로 제공한다. 현재 미커밋 파일 전체가 포함되므로 덮어쓰기 전 다른 환경 수정과 비교해야 한다.

```bash
cd /home/ysy/main/farm_project
unzip -o sim/runs/docking_handoff_margin_20261029_changes.zip
```

## 실제 재시험 결과 — attempt04

| 단계 | 한국시간 | 결과 |
| --- | --- | --- |
| 윈도우 도착 재검증 | 20:53:59 | SUCCESS, 팔 실행 생략 |
| 운송 출발 | 20:53:59 | MOVING_STARTED |
| 주행→42 정밀접근 전환 | 20:59:13 | 목표거리1.09769m, 전환한계1.1m 이내 |
| 42 목표 확보 | 20:59:17 | MARKER_ACQUIRED, 초기 후진/탐색 없이 확보 |
| 42 접근 완료 | 20:59:58 | DONE / WAITING_FOR_TRANSFER |
| 수확로봇 인계 자세 완료 | 21:01:04 | DOCK_READY |
| 41 최종 도킹 시작 | 21:01:05 | DOCKING_STARTED |
| 라이다 접근 완료 | 21:01:32 | DONE, 마지막거리0.203m |
| 운송 도킹 확인 | 21:01:32 | DOCK_STABLE |

운송 출발→DOCK_STABLE **452.96초(7분33초)**. 마지막 라이다 접근은 실제25.83초/시뮬약14.37초(가까운 basket proof의 sim시간, 표본시차36ms 이내). 목표20cm±0.5cm 그대로, 마지막거리20.3cm에서 정지확인까지 통과했다. 직전에는 같은 구간의 실제시간 예산으로 실패했으며 이번에는 시뮬 시간으로 정상완료했다.

이번 단일 시험에서 초기 재탐색 소진·라이다 시간초과·주행105는 관측되지 않았다. 수확 차체 움직임 중 벽관측/코스트맵 입력 지연 대기가 있었지만 복구 후 DOCK_READY를 보냈다. 반복 안정성 및 실물 동등 성공을 입증한 것은 아니다.

`--stop-after-docking` 정책에 따라 DOCK_STABLE을 받은 뒤 배출 허가 전에 두 액션을 취소/정리했다. 최종 ledger의 CANCELED는 시험 종료 처리이며 도킹 실패가 아니다. TransportPickup 전체 SUCCESS/인계/선별/복귀는 이번 검증 범위가 아니다. 종료 시 gate의 context-invalid 발행 오류와 precision/post_sorter SIGINT 흔적이 남았으며 시험 중 실패와 구분한다. probe/runner/observer exit0, 자식프로세스 종료코드는 process_exit.json에 보존했다.

재사용 수확집계7/실제적재10 불일치는 별도 집계 검증 과제로 남긴다. 이번 시험에서 새 수확량으로 계산하지 않았다.

- 원본: `sim/runs/transport_docking_retest_20261029_attempt04/` (events/route_observations/freshness/source 포함).
- 보고용: `sim/docs/test_results/20261029_docking_handoff_margin/summary.json`, `result.json`, 정밀주행·수확·운송·종료 로그.
- 다음: 현재 성공 설정으로 인계→선별장→복귀 후속 시퀀스 검증. 현재 실행은 종료, 미커밋·미푸시.
