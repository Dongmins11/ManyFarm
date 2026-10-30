# 운송 출발→도킹 재시험 결과 — 2026-10-29

**마커42 접근은 성공. 수확로봇 DockTransfer 접수 거절로 마커41 최종 도킹은 미실행. 전체 시험은 실패로 보존한다.**

- 사용자 요청: “재시험해 운송 출발-도킹까지”. 기준 main18d0e00 + 승인된 공통 전환 수정 및 기존 미커밋 작업.
- 실행: `sim/runs/transport_docking_retest_20261029_attempt01/`, Domain13/SUBNET, headless CPU60Hz/render30Hz. 과거 수확9윈도우/집계7개 재사용, 바구니 실제10개 초기복원 후 안정화 검사 통과. 새 예찰·수확 Goal0건.
- 시험기만 `--stop-after-docking` 선택 옵션 추가. 실제 DOCK_STABLE 피드백을 관측하면 수확측 배출 허가 전달 전에 종료하도록 설정. 이번 실행은 그 지점 이전에 실패. 공통 도킹/성공판정 추가 변경 없음.

## 시간과 결과 (KST)

| 시각 | 관측 |
|---|---|
|20:02:57.801|TransportPickup 출발|
|20:07:43.962|첫 마커42 관측. base 기준 전방2.773m. ready=false로 주행 지속|
|20:08:05.508|도킹 접근 목표 약1.193m에서 ready=true로 전환|
|20:08:07.902|정차 후 초기 마커 취득 시작|
|20:08:09.308|MARKER_ACQUIRED|
|20:08:52.153|정밀 접근 DONE: Marker approach distance reached and stopped|
|20:08:52.376|운송 WAITING_FOR_TRANSFER. 출발부터 약354.6초(5분55초)|
|20:08:53.090|수확 DockTransfer REJECTED|
|20:08:53.748|시험 정리 요청으로 운송 CANCELED. 운송 자체 주행 실패와 구분|

- 거리 초과 때문에 ready=false인 관측76건 확인. 첫 마커 인식부터 약21.5초 더 주행한 뒤 전환. 전환 관측의 marker base좌표 `(1.732637,-0.007940,0.079278)m`, 기존 stand-off0.54m를 뺀 평면거리 약1.192664m. 정확한 제어 판정은 같은 관측시각 TF를 포함하는 공통 추적기가 수행하며 이 수치는 로그에서 평면 근사로 계산했다.
- 105 및 이전 `Initial marker reacquisition exhausted`는 이번 업무 구간에서 관측되지 않음. 최종 마커41 도킹·배출·선별은 미실행. 취소와 프로세스 정리 완료. gate exit1/precision−2/post_sorter−2는 종료 SIGINT 때 기록, 먼저 발생한 업무 중단 원인은 수확 접수 거절이다.

## 수확 요청 거절 원인

직접 로그는 `harvest.log:329`의 `DockTransfer 거절: Goal 형식 또는 장치 연결 확인 필요`다. Goal의 ID/시간/expected_count7은 접수 형식에 맞는다. 구체 원인은 실행 경로에서 확인했다.

1. 새 `HandoffRuntime`은 `window=None`으로 시작한다.
2. 성공한 HarvestTask의 `communication.py`만 `remember_window(goal, controller.outcome)`를 호출한다.
3. 이번 재개 도구는 물리 위치/과실과 과거 결과를 복원하지만, 노드 내부 마지막 윈도우 도착 기록은 복원하지 않는다. 현재 실행의 HarvestTask는0건이다.
4. `handoff_runtime.readiness()`는 이 상태를 `WINDOW_MISSING`으로 거절하며, `ComponentTransferDevices.ready()`→`TransferCommunication.accept()`에서 DockTransfer 접수도 거절된다.

즉 **재개 시험 준비의 상태 복원 누락**이다. 운송 조기 전환 수정의 실패도 아니고, 정상적으로 수확 후 연속 실행할 때 발생한 것으로 볼 근거도 없다. 공통 거절 로그는 세부 실패 목록을 출력하지 않으므로 WINDOW_MISSING을 실제 발행 로그로 관측한 것과 코드상 필수 거절 조건으로 확인한 것을 구분한다. 다른 장치 준비 조건의 동시 실패 여부는 이번 로그만으로 배제하지 않는다.

다음 필요 작업: 현재 세션의 유효한 윈도우 도착 기준을 확보하는 재개 절차 및 출발 전 인계 준비 검사. 과거 odom 세션의 기록을 그대로 주입하거나 판정을 우회해서 성공 처리하면 안 된다. 이 시험에서는 공통 복원 계약이나 성공 조건을 추가 수정하지 않았으며 자동 재시험도 하지 않았다.

## 근거 및 전달

- 원본: 위 실행 폴더의 `precision.log`, `harvest.log`, `result.json`, `events.jsonl`, `route_observations.jsonl`, `process_exit.json`, `source_record.json`, `summary.json`.
- 공유자료: `sim/docs/test_results/20261029_transport_docking_retest/` (핵심 로그·결과·관측, 전체 고빈도 이벤트는 원본 보존).
- 변경: `sim/tools/run_single_cycle.py`, `sim/tools/probe_handoff_window.py` 선택형 종료 옵션. 문법/diff 검사 PASS 및 실제 옵션 전달/실행 확인. 성공 종료 분기는 이번 시험이 앞에서 실패해 아직 실제 미검증.
- 복원: 옵션을 생략하면 기존 시험 흐름. 커밋·푸시 없음.
- 변경 파일 ZIP은 프로젝트 루트에서 다음과 같이 적용한다. 누적 상태 문서는 다른 작업의 기존 변경 기록도 포함한다.

```bash
unzip -o sim/runs/transport_docking_retest_20261029_changes.zip -d /home/ysy/main/farm_project
```
