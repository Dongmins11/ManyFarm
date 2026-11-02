# 실물·시뮬 판정 한도 및 덮어쓰기 감사 — 2026-10-30

## 결론

**현재 시뮬 한 사이클과 실물 담당 브랜치를 동일한 판정 조건이라고 설명할 수 없다.**
공통 기본 YAML만 비교하면 실제 선택된 실물 환경 프로필의 덮어쓰기를 놓친다.
이번 W005 실패는 그 사례이며, 실물 수확·인계 프로필은 정지 후 각도 6°, 시뮬 시험은 3°다.
예찰 준비/응답 제한, 수확 주행 충돌 재시도, 예찰 TF 복구 및 준비 조건에서도 차이가 확인됐다.
반면 도킹 거리 등 다수 수치는 같고, 과거 사용자 승인으로 의도적으로 달라진 항목도 있다.

이번 작업은 **감사와 자료 저장만** 수행했다. 공통/실물/시뮬 운영 코드·설정, 실행 중 시험은 변경하지 않았다.
실물 장치에서 재현하거나 실물의 실제 실행 인자·동적 파라미터를 조회한 결과는 아니다.

## 비교 기준과 방법

- 로컬 HEAD: `399379087374f9982b177e70d68e11721d5fdaaf` + 기존 미커밋 작업 보존.
- fetch 성공 후 주행/예찰 기준: `origin/feature_dongmin @ 366e0c37164c22afdd2f640624b61eef8f0fa6f7`.
- 실물 수확/인계 기준: `origin/feat/harvest-handoff-real-20261018 @ e135cdef9462276cc25d9fa336f084e2dcac72e4`.
- 실물 선택 프로필: `scout_real.yaml`, `harvest_handoff_real.yaml`, `harvest_handoff_jetson_real.yaml`(수확 브랜치), `transport_docking_trial.yaml`(주행 브랜치).
- 시뮬: `sim/runs/fresh_full_cycle_20261030_114723_after_push/attempt_003/runtime/`의 생성된 실제 입력. 실행 중 attempt_004의 controller 프로세스가 읽은 `/tmp` 파라미터 파일도 별도 저장·대조.
- `NavigationSettings` 기본값 → navigation policy → 환경 navigation 덮어쓰기, survey 설정 선행 병합, `shared_nav2`/bindings/overrides 및 launch `use_sim_time`, 수확 task policy, 인계 전용 서버 생성 함수를 적용했다.
- `prepare_harvest_handoff → prepare_pickup → prepare_sorter → configure_sorting → prepare_cycle` 생성 경로와 launch/Node의 추가 선택을 확인했다. raw 파일 차이와 기본값까지 적용한 값을 구분했다.
- 구성 데이터 4,482개 비교 행: 동일 2,867 / 상이 1,615. **상이 행 수는 결함 개수가 아니다.** 두 실물 기준 중복, 지도·노드·frame·경로, 비활성 프로필, 배열, 추가 필드도 포함한다. 키워드 후보 362행도 같은 이유로 결함 개수가 아니다.
- 실행 중 launch에 물질화된 일반·인계 controller 파라미터 419개를 대조하여 일치 확인(launch 시계 덮어쓰기 포함).
- ROS 파라미터 서비스 직접 조회는 5초 제한 내 응답이 없어 실패 기록을 보존했다. `/tmp` 입력 확인을 동적 parameter dump 성공이라고 표현하지 않는다.

## 1. 직접적인 실패/허용 조건 차이

| 항목 | 실물 선택 프로필 | 시뮬 최종값 | 영향·분류 |
|---|---|---|---|
| 수확 정지 후 방향 허용 | **6°** | **약 3°** | W005의 3.14°는 실물 조건에서 통과, 시뮬에서 불합격. 가장 먼저 정합할 항목 |
| 수확 주행 충돌 재시도 | **5회** | **0회** | 같은 복구 가능한 충돌도 시뮬에서는 즉시 액션 실패 가능. 인계 연결 때 transfer만 가져오고 최상위 task 선택값은 유지되어 차이가 남음 |
| 예찰 영상 준비 제한 | **300 실제초** | **120 실제초** | `vision_runtime`의 `startup_timeout_s` 기본값. 느린 초기화에서 시뮬이 먼저 준비 실패 |
| 예찰 영상 RPC 응답 제한 | **180 실제초** | **30 실제초** | 실물 `RealObserver`와 시뮬 `SurveyObserver`의 선택/기본값 차이. 통신·영상 백엔드는 다르지만 실패 시간도 동일하지 않음 |
| 예찰 TF 복구 | **enabled=true, wait_forever=true** | **enabled=false** | 실물 최신 선택은 취소 가능한 계속 대기, 시뮬은 해당 복구 경로 비활성. 실물 최신 코드 지원이 함께 필요한 미통합 기능 |
| 예찰 Nav2 준비 | **require_active_nav2=true** | **해당 선택 기능 없음** | 실물 최신 공통 client는 필수 lifecycle 노드 활성화를 확인하고 Goal 전송. 시뮬 시험 helper에 초기 활성 대기 300초가 있지만 매 Goal 공통 검사와 동일하지 않음 |
| 작업 윈도우 연결선 각도 | **5° 명시** | **별도 연결선 각도 검사 비활성(None)** | 시뮬은 차체 방향·횡오차·전방 여부를 따로 검사. D-059 짧은 목표 이동 해결을 보존한 의도적 차이이며 단순 누락으로 되돌리면 안 됨 |

근거:

- 실물 환경 `robot/config/environments/harvest_handoff_real.yaml: navigation.heading_tolerance_rad=0.10471975511965978`.
- 실물 `robot/config/harvest/harvest_handoff_real.json`: `navigation_collision_retry_count=5`, `work_path_heading_limit_rad=0.08726646259971647`.
- 시뮬 생성 `harvest_runtime.yaml`에는 방향 덮어쓰기 없음 → 공통 `harvest_navigation.yaml`의 `0.05236` 사용.
- 시뮬 생성 `harvest_task.json`에는 위 두 task 항목 없음. `harvest_robot/node.py`의 재시도 기본 0, `parallel_approach.py`의 연결선 검사 선택 조건 적용.
- `scout_new/vision_runtime.py`, `observer.py`, `real_observer.py`; 실물 `robot/config/vision/scout_real.json`.
- 최신 실물 `scout_real.yaml`, `NavigationSettings`, `Nav2Client._wait_active_nav2`, `tf_recovery.py`. 로컬에는 `require_active_nav2`/`tf_recovery_wait_forever` 지원도 없으므로 YAML만 복사하면 안 된다.
- D-059 보존 근거: `sim/docs/changes/HARVEST_HANDOFF_INTEGRATION_20261028.md` §충돌 해결과 보존 사항.

**3°/6° 차이는 과거 문서에도 이미 기록돼 있었다.** `REAL_BRANCH_UPDATE_20261027.md`와 `COMMON_CODE_MERGE_REVIEW_20261027.md`는 실물 6°를 명시했다. 그 기록과 실제 생성 프로필을 연결하지 못하고 직전 답변에서 동일하다고 한 것은 감사 누락이다.

## 2. 승인된 예외 또는 별도 평가 목적의 차이

| 항목 | 실물 | 시뮬 | 근거/처리 |
|---|---|---|---|
| 인계 벽 정렬 방향 | 0.5° | 0.8° | 사용자 명시 승인. `prepare_harvest_handoff.py`가 wall 파일을 수정하고 전용 서버/최종 검사 둘 다 사용 |
| 일반 수확 RPP/FollowPath 이동·회전 | 0.1m/s·0.1rad/s | 0.15m/s·0.15rad/s | 10/30 속도 시험 승인. HarvestApproach/HarvestWork/StationReverse는 유지 |
| 운송 진행 검사 | SimpleProgressChecker, 병진 0.1m/10초 | PoseProgressChecker, 병진 0.1m **또는 회전 0.5rad**/10초 | D-075. 제자리 회전을 진행으로 인정. 105 발생 조건이 의도적으로 다름 |
| 운송 마커 관측 예산 | 180 실제초 | 900 실제초 | 승인된 느린 시뮬 대응. `harvest_approach_42.route_handoff.observation_timeout_s` |
| 운송 접근→도킹 전환 여유 | 추가 여유 0m | 추가 여유 0.1m | D-078. 실제 도킹 허용거리 1.2m는 같고 전환을 더 안쪽에서 함 |
| 팔 액션 외부 완료 대기 | 180 실제초 | 7,260 실제초 | 기존 승인한 시뮬 외부 watchdog. 개별 과실 60시뮬초/재탐색 1회와 다른 계층 |
| 팔 액션 취소 완료 대기 | 10 실제초 | 20 실제초 | 시뮬 장치 종료 대기 값. action wrapper 제한과 내부 장치 제한 구분 필요 |
| 운송 스테이션 복귀 | 마커 도킹·parking 포함 | navigation_only | 사용자 요청한 시뮬 마커 생략. 실물 도킹 성공 동등성 시험으로 취급하지 않음 |
| 인계·하역 수량/기구 | 실물 장치·이벤트 | 바구니 겹침+가상 과실 인계/레인 투입 | 사용자 승인 범위. 실제 배출 기구 검증 아님 |
| 바구니 겹침 | 동일 실물 판정항목 없음 | 최소 0.6936842105263158, 정지 0.8초·양의 높이 | D-070. 72% 명목과 거리허용 ±5mm를 반영한 시뮬 평가 |

이 값들은 이번 감사에서 임의로 실물 값으로 되돌리지 않았다. 동일 조건 시험을 원하면 사용자 승인 예외 목록을 먼저 확정해야 한다.

## 3. 성능·안정성에 영향을 주는 추가 설정 차이

### 위치 추정 및 센서

- 수확 AMCL `alpha4`: 실물 **0.2**, 시뮬 **0.002**. 10/29 사용자 승인한 시뮬 회전 병진 노이즈 조정.
- 운송 AMCL `update_min_d`: **0.25m → 0.05m**, `update_min_a`: **0.2rad → 0.05rad**. D-074 승인. 관측 갱신 빈도가 달라 위치추정 성능 비교 조건도 다르다.
- 수확 local costmap 발행: **5Hz → 20Hz**. 센서 freshness 만료를 피하기 위한 시뮬 발행 보완. 계산 주기·충돌 여유 수치는 별도로 유지.
- 실물 예찰 태그 프로필은 `configured=false`, model/assets 미등록이다. 시뮬은 별도 등록 모델을 사용한다. 실물 태그 성능과 동등하다고 판정할 수 없다.
- 시뮬 예찰 태그 모델은 공통 기준 대비 최소 투영면적 **10,000→1,600px²**, 관측거리 **0.8~1.4m**, 복수 태그 모델을 사용한다. 실물 적용값으로 복사하면 안 되는 승인된 센서 배치 차이다.
- 수확 태그 관측 모델 수치 자체는 원격 공통 모델과 동일. 실물은 pixel bias 프로필을 사용하고 시뮬에는 해당 실물 보정 프로필이 없다.

### 예찰 윈도우 및 영상

- 최신 실물 SEC01 팔 높이 상대범위 **[-0.10, 0.35]m**, 시뮬 **[0.087, 0.35]m**. 사용자 승인한 시뮬 팔 필터 정합·과실 재배치와 관련된 차이이며 동일 수확 범위가 아니다.
- 실물 `range_tolerance_m=0.02`, 시뮬 `range_tolerance_m=0`, `depth_tolerance_m=0.02`. **둘 다 2cm라고 같은 정책이 아니다.** 실물은 축별 범위 여유, 시뮬은 깊이 방향만 추가한다. 윈도우 누락률 비교 시 구분해야 한다.
- YOLO confidence는 실물 최상위 `.confidence=0.25`, 시뮬 `.inference.confidence=0.25`로 **실제 값은 같음**. 필드 위치 차이를 검출 기준 차이로 세지 않았다. 시뮬은 IoU0.7/max100/마스크 최소6px 및 영상 전처리 설정을 별도로 사용한다. 실물 legacy worker 배포 환경은 이 저장소 자료만으로 전체 동등성을 인증하지 못한다.
- 시뮬 source/모델/센서 백엔드 차이는 `comparison_all.json`에 포함된다. 이 표는 차이 자체를 숨기지 않되 모델·지도 차이를 완료판정 결함과 구분한다.

### 팔 동작 중 시뮬 전용 감시

- Student 세션은 Teacher 안전 프로필의 `base_drift_limit_m=0.02`, `base_yaw_drift_limit_rad=0.05`(약2.865°)를 읽는다. 이는 목표와의 각도오차가 아니라 **팔 시작 위치 대비 차체 움직임**이다. 일반 도착 6°로 맞추더라도 이 별도 한계가 자동으로 바뀌지 않는다.
- 현재 레이저 집계: 비차폐 유지0.05초, 통과 사건 timeout2초. 실제 팔 카메라 기반 바구니 검사와 동등한 판정이 아니다. 사용자 요청한 레이저 집계 정책을 유지했다.
- 과실별 60시뮬초 후 재탐색1회, 실패 과실은 성능지표로 집계하고 다음 대상을 처리하는 시뮬 정책은 기존 사용자 승인이다. 실물 Jetson 실제 모델/서버의 전체 실패 정책을 이번 차체 저장소 비교로 인증하지 않는다.

## 4. 실행 중 사이클에서 쓰이지 않지만 잠재적으로 다른 한계

- 일반 수확 `behavior_server` Spin: 실물 min/max **0.1/0.1rad/s**, 시뮬 **0.4/1.0rad/s**; 가속도 **1.0/3.2rad/s²**.
- 실물 YAML은 이를 차체 단독 Spin 시험 후보로 명시했다. 현재 정상 수확 FollowPath의 목표회전은 RPP이고, 인계 Spin은 별도 생성 서버다. **이번 W005 잔여 회전 원인이라고 단정할 수 없다.** 다른 동작에서 일반 Spin을 호출하면 조건 차이가 생기므로 동등성 점검 대상이다.
- 실물 운송 graph의 blocked connection `[5,12]`, 목적지·이격 노드, 실물 station 도킹 프로필은 시뮬 지도와 직접 일치하지 않는다. 숫자를 그대로 복사하면 안 된다. 선택되지 않은 실물 도킹 프로필을 시뮬의 누락된 활성 프로필로 세지 않았다.
- 원격 주행 브랜치 대비 관련 비시험 소스218개 중45개가 다르다. 따라서 “공통 소스도 전부 동일”이라고 표현하면 안 된다. 승인된 로컬 수정, 미통합 원격 기능, 장치 연결 차이를 포함한 diff를 저장했다.

## 5. 시험 프로그램 자체의 중단 한계

아래는 로봇이 반환하는 실패 기준과 별개로 시험을 중단시킬 수 있는 **실제시간 watchdog**이다.

| 계층 | 현재 제한 | 검토 |
|---|---:|---|
| 예찰 준비 helper | 300초 | 내부 영상 준비120초가 먼저 실패할 수 있음 |
| 전체 윈도우 수확 결과 대기 | 7,500초 | 팔 외부7,260초와 계층 구분 |
| 인계 차체 진입 helper | 300초 | 내부 ROS/정지대기 예산과 달리 wall time |
| 인계 이벤트 feedback 대기 | 180초 | ROS 진행이 느릴 때 로봇 자체 timeout보다 먼저 종료 가능 |
| 선별장 도착·도킹 대기 | 600초 | 경로 길이별 Nav2 예산 및 느린 시뮬에 비례하지 않음 |
| 선별 완료 대기(overlap cycle) | **1,200초** | **선별 서버 batch timeout1,800초보다 짧음**. 정상 진행 중 외부 시험이 먼저 실패할 가능성 |
| 운송 복귀 대기 | 900초 | wall time |
| 선별·운송 결과/출발허가 외부 대기 | 2,400초 | 각 단계별 예산을 포괄하는지 검토 필요 |
| 전체 사이클 watchdog | 28,800초 | wall time, 별도의 Isaac duration14,400시뮬초 |

이번 감사에서 이 한계로 실제 실패가 재현됐다고 주장하지 않는다. 서로 다른 계층·시계를 가진 실제 코드상의 위험이다.

### 선별 서버와 원본

선별 ROS 코어는 통합 소스와 실제 실행 overlay의 `core.py` SHA256이 같다. `Settings`는 camera1초/robot3초/ACK10초/motion120초/ready10초/scene60초/batch1800초, 빈 장면3초/안정0.5초/우선순위ABCD이다. 실행 인자에는 이 Settings 수치를 덮어쓰는 옵션이 없다.
시뮬 선별 ROI Y+5px, 레인 매핑, 기능 근사 팔·보조 파지 등은 별도 시뮬 연결이다. 원격 차체 브랜치에는 완전한 실물 선별 실행 구성이 없어 실물 전체와의 판정 동등성은 확인 불가다. 선별 코어는 현재 `time.monotonic()` 기준이므로 /clock 기반 전체 전환 완료로 설명하지 않는다.

## 6. 이번 범위에서 같음을 확인한 주요 수치

- 수확 Nav2 목표: 4cm / 2.5°. 정지 후 위치5cm는 같고 방향만6°/3° 차이.
- 공통 기본 정지 확인: 0.8초, 선속도0.005m/s·각속도0.02rad/s, 정지 확인 제한20초.
- 예찰/수확/운송의 일반 주행 기본 goal budget300초. 단, 실제 예산은 경로 길이/속도와 코드 선택에 따라 달라지며 원격은 RPP/StationReverse에 제한적으로 적용하는 차이가 있다. 원본 값300만 같다고 최종 모든 주행 timeout이 같다고 보지 않는다.
- 운송 선택 정밀 프로필6개(`harvest_approach_42`, `harvest_dock_41`, `harvest_clear`, `sort_01`, `sort_01_distance_trial`, `sort_departure_distance_trial`)의 공통 대응 필드에서 frame/path/지도 방향을 제외하면 앞서 기술한 관측900초/전환여유0.1m 외 추가 수치 차이는 발견하지 못했다.
- 인계 도킹 거리20cm±0.5cm, 선별장 도킹17cm±0.5cm, 해당 거리 안정0.5초는 원본과 같음.
- 인계 FSM arc/monitor/completion 수치는 같은 원본이며, 복원 위치5cm·방향6°는 양쪽에 반영돼 있다. **일반 수확 윈도우 도착3°와 별개**다.

## 7. 조치 순서 제안

1. 실물 수확·인계 프로필의 일반 도착6°를 시뮬 생성 프로필까지 누락 없이 전달한다. 공통 기본값을 무조건6°로 바꾸면 다른 역할까지 영향이 생기므로, 수확·인계의 공용 정책과 명시적 환경 예외로 범위를 제한한다.
2. 수확 충돌 재시도5회/0회, 예찰 준비·RPC timeout, 최신 예찰 준비/TF복구 기능을 각각 통합 대상으로 검토한다. 반복만 늘려 결함을 감추거나 미지원 YAML만 추가하지 않는다.
3. D-059 작업선각도 예외, 벽0.8°, 레이저, 마커 생략, 느린 시뮬 예산 등 기존 승인 예외는 따로 유지한다. 실물과 다르다는 사실을 시험 메타데이터에 기록한다.
4. 외부 시험 watchdog과 내부 action 예산/시계의 충돌을 해소한다. 특히 선별1,200/1,800초를 우선 정합한다.
5. 이후 실행마다 기본값·덮어쓰기·최종값·승인 예외를 자동 비교하고 미등록 차이를 시작 전에 표시한다. 이번 감사 스크립트는 읽기 전용이며 아직 시험 시작 게이트에 연결하지 않았다.

## 자료

- `real_drive_effective.json`, `real_harvest_effective.json`, `sim_effective.json`: 기본값/상속/생성 서버를 포함한 수집 결과와 입력 SHA256.
- `comparison_all.json` / `.csv`: 전체 비교 행. `threshold_candidates.json`: 검토 후보, 결함 목록 아님.
- `running_launch_parameters.json`, `launch_verification.json`: 실행 중 attempt004의 프로세스 인자로 찾은 파라미터 입력과419개 대조.
- `live_parameters.json`: 직접 ROS 조회 실패 기록. 실패를 숨기거나 입력 파일 확인으로 대체해 성공 표시하지 않음.
- `code_comparison.json`, `code_differences.patch`: 최신 주행 브랜치와 관련 공통 소스 차이.
- `manifest.json`: 기준 커밋/실행 경로.
- `collect.py`, `compare.py`: 읽기 전용 설정 수집/비교 스크립트. 운영 로직 복사본이 아니라 실제 원본 설정 로더를 호출한다.

미실행: 실물 장치 parameter dump·배포 환경 확인, 모든 가지의 실제 동작 재현, 실물 팔/legacy vision의 외부 파일 전체 대조. 커밋·푸시는 수행하지 않았다.


### 재수집 명령

프로젝트 루트에서 아래를 실행한다. 고정 원격 커밋은 보존되지만 sim_effective는 실행 당시 로컬 소스와 지정 runtime을 다시 읽으므로 로컬 소스 변경 후 결과가 달라질 수 있다.

```bash
python3 sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/snapshot_refs.py
python3 sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/collect.py /tmp/farm_threshold_audit_20261030/drive/farm_project real > sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/real_drive_effective.json
python3 sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/collect.py /tmp/farm_threshold_audit_20261030/harvest/farm_project real > sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/real_harvest_effective.json
python3 sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/collect.py "$PWD" sim "$PWD/sim/runs/fresh_full_cycle_20261030_114723_after_push/attempt_003/runtime" > sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/sim_effective.json
python3 sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030/compare.py
```

### 관제 워커 계층 추가 확인

현재 시험에서 사용한 사용자 제공 `Frontend/dashboard/backend/handoff_worker.py`는 요청 응답 대기10초, 취소 종료 대기15초를 실제시간으로 검사한다. 시뮬 runner가 이 수치를 덮어쓰는 지점은 확인되지 않았다. 로봇 동작의 장거리/선별 완료 예산과 구분되는 통신 감시다. 원격 실물 PC에 배포된 관제 파일은 제공되지 않아 동등성 인증 대상에서 제외한다.
