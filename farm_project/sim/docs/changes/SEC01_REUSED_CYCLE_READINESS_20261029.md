# SEC01 예찰 재사용 사이클 준비 검토 — 2026-10-29

기준: main `18d0e00` 및 기존 미커밋 변경. 사용자 요청: 먼저 코드/데이터로 가능 여부를 판단하고 가능하면 예찰을 생략해 한 사이클 실행. 원격 조회/커밋/푸시는 이번 작업 범위에 없음.

## 정적 검토 결론

이번 저장 결과(9윈도우, expected13개) 기준 실행 가능한 연결 상태다. 실제 물리·위치 추정·팔 성능과 전체 완주는 실행으로 확인해야 한다. 정적 검토 중 시뮬레이션을 실행하지 않았다.

| 확인 항목 | 근거/결과 |
|---|---|
| 예찰 성공 데이터 | sec01_cycle_scout_sec02_20261028_attempt02/scout_result.json, SUCCESS/status4, 9개 고유 윈도우/expected 합계13 |
| 좌표/순서 | map 좌표 유한값, SEC01 진행 방향 Y 내림차순, 태스크 좌표 보존 |
| 지도/예찰 설정 | 저장 시점과 현재 지도 YAML/image SHA 일치, SEC01 예찰 설정 차이 없음, HCR 지도 manifest 검증 통과 |
| 경로 연결 | 공통 RouteGraph로 수확 station→9윈도우/최종→station, 운송 station→인계→선별장/이격→station 총13계획 성공. 동적 충돌 없는 주행을 증명하는 것은 아님 |
| 운송 장치 | 직전 실제 접수 검증에서 덮개/UNLOAD/STOP 연결과 접수/취소 성공. 현재 동일한 시작 순서, 인계 전 하역 거절 유지 |
| 선별 연결 | 실제 인계 과실 manifest→가상 레인 투입→기존 SortBatch→운송 복귀→수확 복귀. 선별 프로세스는 인계 허가 전 명령 대기 |
| 레인 배치 | 기존 고정 x≤0.65m 제한이 13번째 x=0.66m를 잘못 거절. 원본 경사판 수평 끝0.706514m−과실반경0.045m=중심 상한0.661514m로 계산하도록 수정 |

## 이번 변경

- `sim/tools/run_single_cycle.py`: `--scout-result` 옵션. 성공 여부/수량/좌표/순서/지도 일치 검증 후 결과 사본과 해시 저장. 예찰 ROS 실행 생략.
- `sim/tools/single_cycle_steps.py`, `probe_handoff_window.py`: 저장 태스크를 기존 수확 흐름에 전달하며 ScoutArea/SEC02 예찰을 호출하지 않음.
- `sim/tools/cycle_monitor.py`: 재사용 예찰 상태와9개 윈도우 진행 표시.
- `sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/sorter_runtime.py`: 원본 레인 형상과 과실 크기로 배치 상한 계산. 배치 간격/모델 형상/공통 성공 판정은 그대로다.
- `sim/tests/test_sorter_deposit_capacity.py`: 실제 deposit 함수에13/16개 허용,17개 이동 전 거절 및 과실 전체가 레인 안인지 검사.

승인 근거: 사용자 데이터 검토 후 가능하면 예찰 생략 실행 요청. 시뮬 시험 준비/배치 경계 수정이며 실물·공통 소스 변경 없음. 초기 과실은 새 농장 씬이며 이전 수확8개를 성공으로 재사용하지 않는다. 예찰 로봇 모델은 스테이션에 그대로 존재한다.

## 이번 오프라인 검증

- 레인 용량/인계 가드/과실 이동/지도/시험 씬 관련16검사 PASS.
- ROS 노드/클라이언트 없이 재사용 함수 실행:9윈도우/expected13, 다음 예찰 액션 없음, 인계 허가 없음 확인.
- `--prepare-only` 성공. 문법/diff 검사 통과.
- `farm_sim_runtime` 빌드 성공, 설치본과 소스 sorter_runtime SHA 동일.
- 정적 근거: `sim/runs/cycle_static_review_20261029/audit.json`.

## 실제 실행

2026-10-29 18:25 KST 실행 시작. Domain13/SUBNET, headless, CPU 물리60Hz/렌더30Hz. 예찰 생략→SEC01 전체 수확→운송 호출/도킹/인계→선별장 이동/도킹/선별→운송 복귀→수확 복귀. 한 시도이며 실패 후 자동 재실행 없음.

실행 폴더: `sim/runs/sec01_reuse_cycle_20261029_attempt01/`. 원본 재사용 결과/fixture/runtime/source_hashes/events/각 프로세스 로그 보존. 실제 진행·최종 결과는 이 폴더 result.json과 events.jsonl이 기준이며 아직 전체 성공은 미확정이다.

잔여 한계: 원본 선별 기능 근사/보조 파지, 임시 마커 장착 위치 및 승인된 시뮬 인계·스테이션 정책 유지. 원본 레인 동시 배치 용량은16개이고 운송 바구니27개와 다르며 일반 대량 배치는 별도 작업이다. 이번 예상13개는 레인 용량 안이다. 이전 선별 노랑 잔류 문제 및 전체 연속 인계 성공은 이번 실행에서 확인한다.

되돌림: 새 `--scout-result`를 생략하면 기존 새 예찰 흐름. 레인 상한 계산을 이전0.65m로 복원하면13번째 거절이 재발한다. 기존 사용자 미커밋 변경은 보존했다.

실행 확인: 운송 장치4서비스 준비, scout_reused 기록, W001 HarvestTask 전송 및 실제 이동 확인. ScoutArea/SEC02 명령0건. 시작 근거는 `sim/docs/test_results/20261029_reused_cycle_readiness/`. 전체 완료는 아직 미확정.
