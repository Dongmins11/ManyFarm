# 운송 재개 시 마지막 윈도우 도착 문맥 확보 — 2026-10-29

사용자 재시험 지시 후 준비 누락으로 실패했고, 후속 지적에 따라 시험 준비를 보완했다. 기존 main18d0e00 및 미커밋 작업 보존. 공통 소스·실물 설정 추가 변경 없음.

- 원인: 기존 prepare_transport_resume는 물리 위치/과실과 과거 결과만 재사용했다. 새 수확 노드의 HandoffRuntime.window는 None이며 성공한 HarvestTask가 있어야 remember_window가 호출된다. 이를 확인하지 않고 운송부터 출발시켜 수확 DockTransfer가 거절됐다.
- 보완: 과거 accepted 결과를 강제로 주입하지 않는다. 기존 ARRIVAL_ONLY_NO_HARVEST 정책을 이 재개 시험의 생성된 harvest_task.json에만 선택한다. 원래 마지막 윈도우 목표 10cm 전에서 수확로봇/적재10개를 동일한 벡터만큼 초기 이동한다. 원본 snapshot·ID·형상·과거 수확집계7을 보존하고 initial_shift_world_m/실행 정책/fixture 차이를 manifest에 기록한다. 정확한 과거 위치의 복원과 구분한다.
- 현재 세션에서 기존 HarvestTask→FollowPath→도착/정지 검사를 실제 수행한다. 성공한 새 도착 기록만 기존 공통 코드가 저장한다. 그 성공을 확인한 뒤에만 TransportPickup을 전송한다. 실패/취소/거절이면 운송 출발 전 종료. 새 도착 검증 결과는 resume_window_arrival에 별도 저장하며 과거 수확9건/7개에 합산하지 않는다.
- 예상수2/harvested0인 도착 전용 액션은 새 수확 성능시험이 아니다. arm_operation=SKIPPED. 공통 정책 선택 기능을 사용하며 도착거리/방향/속도/인계 ready 조건을 완화하지 않는다.
- 대상: sim/tools/prepare_transport_resume.py, single_cycle_steps.py, probe_handoff_window.py. 옵션을 사용하지 않는 기존 전체 시험에는 영향 없음. 재개 시험에서만 팔 미실행 도착 정책이 적용되므로 이 프로필로 신규 수확을 수행하면 안 된다.
- 준비 검증: prepare-only 성공, 원본10개 과실 모두 동일 위치변환/원래 goal10cm전 초기배치/수량7·10 분리/팔미실행 설정/문법/diff PASS.
- 실제 attempt02: 20:25:21~20:25:29 현재 세션 마지막 W009 도착 검증 SUCCESS. 경로0.09990m, 위치오차0.010637m/허용0.05m, 방향오차0.025561rad/허용0.05236rad. 팔 SKIPPED. 20:25:29 운송 출발. 최종 도킹 결과는 확정 후 아래에 추가한다.
- 실행 원본: sim/runs/transport_docking_retest_20261029_attempt02/. 이전 attempt01 실패는 보존. 되돌리기는 이 재개 보완3개 블록만 제거(도착 문맥 누락 재발). 커밋/푸시 없음.


## 실제 최종 결과: 준비 누락 해결, 최종 도킹 시간 초과

- 20:25:29 운송 출발 →20:30:39 접근목표 약1.196m에서 전환 →20:31:29 마커42 접근 DONE/WAITING_FOR_TRANSFER. 수확 DockTransfer 접수 성공, 실제 인계 자세 진입 후20:32:32 DOCK_READY 전달/운송 DOCKING_STARTED.
- 20:32:34.634 라이다 접근 시작,0.613m에서0.040m/s로 접근. 20:32:59.050 VERIFY_LIDAR_STOP. 20:32:59.954 실제 라이다0.203m/목표0.200m/허용±0.005m,속도명령0. 최종20:33:00.357 `Final lidar approach timed out`,20:33:00.986 TransportPickup FAILED/DOCK_FAILED. 전체 시험 passed=false.
- 확정 원인: precision_server.begin_lidar_approach는 distance_heading_trial 설정 시 `min(설정65초, 남은거리/최대속도×1.5+10초)`로 시간 예산을 축소한다. 시작거리 약0.613m에서 약25.5초가 된다. run_lidar_approach는 time.monotonic 실제시간으로, 그 제한을 정지/완료 검사보다 먼저 확인한다. 이번 구간 실제25.72초/시뮬 약14.03초,약1.83배 지연. 이 단계 계산은 시뮬 지연을 반영하지 않았다.
- 거리 범위 안에 도달했지만 정지 확인까지 완료됐다고 볼 수 없다. DOCK_STABLE 미관측. 시간 여유만으로 전체 성공이 보장된다고 단정하지 않는다. 65초 설정만 높여도 min 계산 때문에 약25.5초가 그대로여서 해결되지 않는다.
- 이전 도착문맥 준비 누락 및 조기 전환은 이번 실제 시험에서 통과. 새 실패는 최종 도킹 접근의 실제시간 예산 문제로 분리. 기존 주행105·재초기 마커 취득 실패 미관측. 배출 허가/가상과실 인계/선별 미실행. 원인 확인 후 추가 재시험 없음.
- 다음 조치 권고: 실물 기본값/거리·속도·정지 성공 기준은 보존하고 시뮬에서 축소된 접근 시간 예산에 지연 여유를 반영할 수 있는 명시적인 설정 계약 검토. 이번에는 공통 계산을 변경하지 않았다.
- 정리 완료: result의 cleanup_error 없음. 운송 실패 뒤 수확 인계는 시험기의 명시적 정지/취소로 종료. gate1/precision−2/post_sorter−2는 SIGINT 정리 시 기록, 초기 실패 원인은 라이다 제한시간. 공유자료 sim/docs/test_results/20261029_transport_resume_window/.

변경 파일 묶음(누적 상태 문서는 기존 다른 작업 기록도 포함):
```bash
unzip -o sim/runs/transport_resume_window_20261029_changes.zip -d /home/ysy/main/farm_project
```
