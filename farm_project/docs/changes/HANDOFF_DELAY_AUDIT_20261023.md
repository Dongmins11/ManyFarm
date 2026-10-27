# 수확 인계 지연 재조사 — 2026-10-23

## 확인 범위와 기준

사용자 요청: 실제 PC/로봇 차이 확인, 기존 핫픽스 보존, 원인 구분 계측 및 오프라인 검증. PC 프로젝트 `/home/eunbi/vmany/main/farm_project`, Git 루트 `/home/eunbi/vmany/main`, 브랜치 `feat/harvest-handoff-real-20261018`, HEAD `4b5c5b13605216d1b8b163ea988805572a6a908a`. 시작부터 소스·문서에 미커밋 변경이 있었다. 이를 보존했다. 원격 Git fetch/commit/push 없음.

로봇 `vic@192.168.0.12`는 SSH 연결 후 `Permission denied (publickey,password)`로 인증 실패했다. 로봇 현행 소스, 설치본, 실행 중 프로세스, patch state, 재시작 여부는 **미확인**이다. 아래 ZIP은 배포물, audit는 과거 수집본이며 현행 로봇으로 간주하지 않는다.

GitHub 프로필, Slack workspace, Atlassian 접근 resource 조회 성공. Jira/Confluence scopes 확인. 메시지 발송·상태 변경·문서 게시 없음. 계정 연결 확인은 특정 저장소 쓰기 권한 검증과 다르다.

## 실제 대조 결과

| 항목 | 직접 확인 | 판단 |
|---|---|---|
| PC runtime/설치본 | `handoff_runtime.py` 바이트 일치 | 최신 현장본 일치를 뜻하지 않음 |
| PC PoseProvider/설치본 | 바이트 일치, lookup_available_pair 존재 | 전달문의 과거 누락은 PC 현행에는 해당 안 됨 |
| PC 누락 | handoff_body_trial, handoff_entry, handoff_locking, handoff_window, transfer_sequence 없음 | PC를 로봇에 일괄 복사하면 안 됨 |
| PC runtime | 모든 입력 node.callbacks, 일반 RLock, build_body가 poses.current 사용 | 현장 odom callback group/동일 시각 pair 핫픽스와 다름 |
| 최신 수집 | Downloads/handoff_lock_result_tL2TvF.tar.gz: launch.log, status.txt, timing.txt | 소스/state 없음. 모드를 로그만으로 확정 불가 |
| 과거 audit | Downloads/handoff_audit_ncedl_i4.tar.gz에 source/report 존재 | 수집 당시 설치 대조 결과이며 현재 결과 아님 |
| completion ZIP | environment, launch, preflight, 후보 소스 존재 | 로봇 Downloads의 현행 파일은 미확인 |
| preflight 후보 | node 이름에 zenoh 포함 여부로 ZENOH_NOT_RUNNING 판정 | 실제 메시지 왕복 검증 아님. 수정/해결 완료 아님 |
| driver_sources.json | vic_pinky commit aa98a1c3135160335e92f2a1721e9d3b9d6e09b9, bringup hash 6bf63ba62804e2e85f631bd1179a6ed029f9c9cb5ac331da4fa997fe16cf49a8 | 아카이브 출처 기준. URL/branch 필드 없음. 현행 드라이버 확정 불가 |

## 원본 로그 재확인

ROS 시각 기준. 최신 capture를 직접 읽었다.

| 시각 | 이벤트/수치 |
|---|---|
| 1792738137.7406 | AMCL 532×229, 0.010m 맵 재수신 |
| 1792738138.9359 | tf_buffer_age 2.26449655s, runtime hold max 0.000103204s |
| 1792738155.5023 → 1792738211.0574 | 일반 controller goal 수신 → 도착 |
| 1792738212.4410 → 1792738215.6946 | 일반 controller 다음 goal 수신 → 도착 |
| 1792738215.5360 | TAG_CORRECTION_APPLIED |
| 1792738224.5032 | TF age 0.405107702s, lock hold max 0.00070753s |
| 1792738226.3276 | BODY_TRIAL RECOVERY_REQUIRED, 입력 시각 만료: odom, arm_tested=false |
| 1792738229.5378 | TF age 0.048882452s로 회복 |

capture에서 handoff controller 이동 goal 수신 로그는 찾지 못했다. 경로 실행 전 실패 가능성을 지지하나 정확한 단계는 로그가 없어 미확정이다. 큰 TF age와 긴 runtime lock 점유의 단순 인과는 지지되지 않는다. AMCL 재수신/태그 보정은 시간상 상관일 뿐이다. 수신 경과 .5s 초과인지, header age [-.1,.5] 이탈인지 구분할 수 없다.

## 호출과 동시성 (PC 코드 및 completion 후보 구분)

| 경로 | 문맥/잠금 | 잠금 중 비용·주의 |
|---|---|---|
| 일반 work → WINDOW_MOVE 성공 → remember_window | communication / runtime.lock | PC는 window ID와 요청 xy 저장. 실제 도착 기준 hotfix와 차이 |
| BodyTrial.request(enter) → readiness → reserve → pool.submit | completion 후보, node.lock / ROS Reentrant group | readiness의 graph/input 검사가 node.lock 안. 수락은 완료 아님 |
| BodyTrial.run → acquire → build_body | 별도 ThreadPoolExecutor 1 worker | ROS callback 하나를 계속 점유하는 구조 아님 |
| ActionHandoff.acquire → 외부 check | condition 잠금 안 (PC) | check→runtime._read→runtime.lock 경로 |
| runtime._watchdog → _owned | runtime.lock→condition | 위 순서와 역전 가능. 장애 직접 원인 입증 아님 |
| runtime._forward → check/live_guard | PC runtime.lock 안 | graph 조회, 입력검사/충돌 검사가 길어질 수 있음 |
| runtime._receive | PC Reentrant, runtime.lock | 현장 별도 MutuallyExclusive hotfix는 현재 확인 필요 |
| build_body → planner.capture → lookup_available_pair → RestoreReference | body worker → motion worker | 동일 시각 map/odom 저장. 현재 odom과 최신 TF 혼용 금지 |
| planner.plan → guard → NavigationSteps → preflight → arm_output → Navigator.navigate | 동작 worker | guard 실패 시 goal 이전에 종료 가능 |
| 완료 → 정지 시각 검증 → restore | motion/cycle | enter 완료와 restore 완료 별도. body-only 장치 미시험 |
| PoseProvider | harvest MultiThreadedExecutor(PC 4 threads), TF listener | 로컬 Jazzy listener 구현은 자체 Reentrant group. group 분리만으로 CPU/GIL 격리 아님 |

## 이번 변경

운영 공통 코드·로봇 소스·설정·허용시간·controller 목록은 수정하지 않았다. `robot/tools/transfer/handoff_diagnostics/`만 새로 추가했다.

| 파일 | 이전 → 이후 | 적용 상태 |
|---|---|---|
| collect.py | 없음 → 소스/설치본/패치 state 및 참조 백업/driver/최근 launch/프로세스 환경 허용목록 수집 | PC 수집 실행 확인, 로봇 미실행 |
| observe.py | 없음 → 외부 odom/TF callback 시각·header age·간격 JSONL | ROS 타입 import 확인, 실제 DDS 미검증 |
| internal_probe.py | 없음 → 유한 수신 이력 및 단계 시작/종료 계측 | 운영에 연결하지 않은 제안용 helper |
| propose.py | 없음 → 입력 소스 기반 runtime diff/candidate 생성, 원본 불변 | PC/배포 후보에서 생성 검증. fixed/형태 불일치 거부 |
| test_diagnostics.py | 없음 → 실제 _read 경계값·예외 보존·시계 분리 등 검사 | 6개 통과 |

제안 계측은 `_receive` 시작/저장 시각을 기록하고 `_read`가 실패한 **실제 receive age/header age**를 남긴다. build_body/guard 시작·종료를 기록한다. TF callback 진입 및 build_body 내부 세부 단계는 아직 계측하지 않는다. 현장 소스 확인 뒤 해당 줄에 계측해야 하며 현재 제안을 A/B/C 전체 분리 완료로 표현하지 않는다. 실패 때 이력 JSON 출력 비용이 있고, callback 내 짧은 계측 lock도 추가되므로 부하 영향 검증이 필요하다.

lock 패치 apply.py는 소스뿐 아니라 문서도 installed 해시로 추적한다. 상태 파일을 임의 갱신하거나 무시하지 않는다. 현장 적용 전 state·백업·소스를 대조하고 후속 계측을 포함하는 명시적 이행/원복 절차가 필요하다. 기존 apply.py baseline/fixed/rollback을 그대로 실행하면 추가 변경 때문에 거부될 수 있다. 이번 도구는 state를 수정하지 않는다.

## 검증·남은 작업

이번 직접 실행: unittest 6개, PC/배포 completion runtime 제안 생성 및 AST parse, PC evidence 수집, Jazzy rclpy/Odometry/TFMessage import. 로그 `/tmp/handoff_review_20261023/`, PC evidence `pc_evidence/handoff-evidence-0g_d_jrj.tar.gz` (초기 collector판). 과거 20/53/58 통과 기록을 이번 결과로 재사용하지 않았다.

남음: 로봇 인증 → 현행 state/소스/설치본/프로세스 대조 → 세부 내부 계측 완성 및 원복 검증 → 같은 부하에서 외부/내부 기록 비교. 외부 callback도 scheduling 영향을 받으므로 외부 지연만으로 드라이버 원인 확정 불가. serial write 지연은 현행 드라이버 확인 전 가설이다.

실기 이동은 요청하지 않았다. Zenoh ON 전체 진입·정렬·이탈·복귀, 일반 주행 회귀, 다른 로봇 영향 검증은 남았다. `device_services=NOT_TESTED: body-only scope`. 완료 상태로 변경하지 않는다.

복원: 이번 추가 진단 도구를 호출하지 않으면 운영 영향이 없다. 문서의 이번 절과 새 도구만 선택 제거 가능하며 기존 미커밋 변경은 보존한다. commit/push 미수행.


## SSH 인증 후 직접 확인 — 2026-10-23

사용자가 PC 공개키를 등록한 뒤 BatchMode SSH 접속 성공. hostname=vmany, user=vic. 이제 로봇 파일을 직접 읽을 수 있다. 위 인증 대기 기록은 최초 조사 시점의 상태다.

- 현행 lock patch state는 fixed이며 추적 소스 4개와 문서 5개 모두 installed SHA-256에 일치한다. baseline 실패 로그를 fixed 실기 결과로 해석하지 않는다.
- 프로젝트에서 git rev-parse 실패. 확인한 프로젝트/상위 main/vmany 위치에서 .git을 찾지 못했다. 로봇 프로젝트 Git 브랜치를 PC와 동일하다고 주장할 수 없다. git init/clone은 하지 않았다.
- harvest_node, zenoh-bridge-ros2dds, vicpinky_bringup 이름에 해당하는 실행 프로세스가 조회되지 않았다. 실행/이동 요청 없음.
- 현행 environment.bash는 Jazzy→vicpinky_ws→프로젝트 overlay, domain 77, CycloneDDS, LOCALHOST로 확인했다.
- last_trial은 runs/tag_bias_trial/20261023_155236_066966_on. 이전 15:47 로그 이후 실행 기록이 있으므로 이 로그를 추가 대조해야 한다.
- 이번 직접 확인은 읽기 전용이며 로봇 patch state/운영 소스/문서는 수정하지 않았다.

## 직접 수정·비교 시험 — 2026-10-23 후속

사용자가 로봇 직접 수정·백업·빌드·검증을 승인하고, 초기 스테이션에서 기존 시험 경로 이동 가능 상태임을 확인했다. 로봇 Git 저장소 생성 및 PC 소스 일괄 복사는 하지 않았다.

### baseline과 fixed 이력

- baseline 관련 빌드: 15:46:50, farm_common/harvest_robot rc=0. 이전 15:47 launch의 실패는 odom 만료.
- 현행 fixed state mtime: 15:52:21.627712. runtime source mtime도 15:52:21.607712.
- 15:51:56, 15:52:11, 15:52:23 빌드 모두 두 패키지 rc=0. 마지막 빌드 후 15:52:36 새 launch, harvest PID 30355.
- fixed runtime 소스/설치본 SHA-256 `779ca1e98f8cb6e4355d886f87391244f4d03c68a6b67da68747f59a6331b849` 일치.
- 15:52 시험 실제 실패: ROS 1792738501.942930, 동일 시각 TF pair 확보 실패. last odom sample age 약 .11159s, retained samples=25. buffer의 odom→base 최신 시각이 sample보다 약 1.34555s 뒤처짐. handoff goal 수신 기록 없음.
- 시각·현행 hash는 fixed 실행을 지지하지만 당시 메모리 code hash가 없어 바이트 수준의 과거 실행 증명은 불가하다. 다음 계측은 startup 모듈 경로/파일 hash 및 runtime code hash를 남긴다.

### 변경 및 백업

로봇 작업/백업 루트: `/home/vic/Downloads/handoff_input_trace_20261023`.
`fixed_trace_v3/backup`에 변경 전 소스, `install_before.tar.gz`에 기존 harvest 설치본, `manifest.json`에 전후 hash, `applied.json`에 적용 시각과 기존 lock state hash를 보관했다. 테스트와 TF 문맥 후속 변경도 같은 manifest/backup에 추가했다. 원래 `handoff_lock_fix/state_2742f94ff21d.json`은 바꾸지 않았다. 따라서 기존 lock 모드 전환 도구는 이번 계층이 적용된 동안 drift를 감지해 거부하는 것이 정상이다. 이 계층을 먼저 원복·재빌드한 후 기존 도구를 사용한다.

| 로봇 변경 파일 | 변경 |
|---|---|
| handoff_runtime.py | callback 시작/저장, 정확한 freshness 실패값, TF tap/buffer 비교, watchdog 간격 및 단계 계측 |
| handoff_input_trace.py (신규) | 4096행 유한 큐, 별도 파일 기록 스레드, overflow 수치 기록. HANDOFF_INPUT_TRACE 선택 시 활성 |
| handoff_body_trial.py / handoff_planning.py | worker 단계, 동일 시각 pair 전후 계측 |
| package.xml | 직접 사용하는 tf2_msgs 의존성 명시 |
| test_handoff_output/integration/planning.py | fixed 실행 문맥 및 현행 WindowCorrection/departure reverse 계약 반영. retreat의 reverse=True는 유지 |
| handoff_pose_context.py (신규) / node.py | HANDOFF_TF_EXECUTOR=dedicated를 실물 handoff 구성에서만 선택. 별도 node+SingleThreadedExecutor가 공통 PoseProvider를 소유. 부모 node를 두 executor에 넣지 않음 |
| status.py | status buffer 독립 유지, 전용 문맥 선택 시 해당 TF listener만 전용 node에서 수신 |

공통 farm_navigation/farm_common 소스, TF/odom 허용치, 충돌 검사, controller 목록, 실물 설정은 수정하지 않았다. 이 구성은 CPU/GIL/프로세스 격리가 아니라 executor 소유권 분리다. 기본 환경변수 미설정 경로는 기존 구성을 유지한다.

### 이번 직접 증거

- `trace-HcRsYvNN` 정지 시험: ROS 1792741829.232884212 시각의 기존 buffer age=2.954867564s. 같은 시점 직전 내부 TF tap 표본 age=.130018909s, 외부 표본 age=.023442582s. 외부 수신과 내부 tap이 갱신된 상태에서도 기존 buffer는 오래된 값이다. 다른 표본에는 내부 tap 자체도 지연된 구간이 있어 listener 하나만의 문제로 단정하지 않는다.
- 같은 드라이버 소스/설치본 hash는 driver_sources.json의 보존 hash와 일치했다. serial write 이전에 stamp를 확보하고 write 후 TF/odom을 발행하는 순서를 확인했지만, 위 지연 표본은 upstream 정지보다 harvest 내부 갱신 경로를 우선 지목한다.
- 전용 TF 첫 정지 비교 `trace-jY4F9sfZ`: 초기 128 buffer 표본 최대 .127565143s. 짧은 정지 시험 결과이며 부하·반복 안정성 완료 아님.
- 상태 listener도 전용 node로 연결한 뒤 PC→Zenoh 상태 수신에서 IDLE/ready=true, x=.0943719832,y=-1.1244303946,yaw=1.5286313742 확인. 배터리 미측정 오류는 유지.
- 브리지 기동 초기에 pgrep가 자기 셸 명령을 오인해 기동을 거부했다. 실제 프로세스 확인 후 재기동했다. 이후 로그는 파일로 저장하고 실제 PC 상태 수신으로 연결을 확인했다.

### 검증

- 로봇 harvest_robot 빌드 성공, 수정 Python 소스와 설치본 hash 일치 확인.
- 실제 수정 runtime의 동시성/출력 소유권 회귀 20개 통과. 계측 활성화·유한 큐·예외 보존 3개 통과.
- 기존 인계 회귀 최초 64개: 과거 계약 기대값 2개 + AST 테스트의 decorator 누락 10개 실패. 테스트 보완 중 departure용 변경을 retreat에 함께 적용한 실수를 발견해 바로 수정했다. 최종 64개 모두 통과. 실패 기록도 삭제하지 않았다.
- 별도 무동작 ROS namespace에서 전용 node/executor 소유권, TF remap 실제 수신, 동일 시각 pair 조회, 반복 close와 thread 종료 확인. 실기 주행 성공과 별개다.
- PC에서 계측 계층 적용→원복 원본 바이트 보존 검사 통과.
- 전체 실기 인계 완료 여부는 아래 후속 결과로 기록한다. 팔은 `device_services=NOT_TESTED: body-only scope`.

### 이번 window 이동 결과 및 종료 상태

- 사용자가 초기 스테이션/시험 이동 준비를 확인한 뒤 실행. PC Action client가 Zenoh를 통해 사용자 제공 좌표를 포함하는 HarvestTask를 한 번 전송했다. 실제 관제 UI를 조작한 시험은 아니며 동일 관제 Action 계약/Zenoh 통신 경로를 사용했다.
- 목표 파일: `runs/handoff_diagnostics/20261023_review/window_goal.json`. task `TRACE_36f97f03588c_SEC01_TASK001`. 목표 x=1.186,y=-.035,yaw=0. 그래프 번호에 의존하지 않는다.
- 수락: 17:01:35 KST. 일반 controller goal 수신 ROS 1792742495.667433.
- 실패: ROS 1792742530.024545, `RegulatedPurePursuitController detected collision ahead!`. 최종 Action status=6, result_code=FAILED, NAVIGATION_FAILED/error_code=106. 수락을 성공으로 기록하지 않는다.
- 해당 이동 구간의 전용 주행 TF buffer 214개 표본 최대 age=.077354503s. 이전 TF 갱신 지연과 이번 충돌 판정을 동일 원인으로 확정하지 않는다. 충돌 검사/footprint/costmap/속도 변경 없음.
- 실패 후 속도 표본: linear=(0,0,0), angular=(0,0,0). 상태 pose x=.0381172199,y=-.1076113959,yaw=.8143188436. 사용자가 실제 정지를 확인했다.
- window 도착 기준이 없으므로 body enter/restore는 호출하지 않았다. 전체 인계 미완료, 팔 미시험. 재이동·스테이션 초기 좌표 재발행 없음.
- 상태의 IDLE/ready=true는 다음 작업 수락 가능 상태이며 직전 이동 성공을 뜻하지 않는다.
- 현재 실행은 `HANDOFF_TF_EXECUTOR=dedicated`, 내부·외부 계측 ON, 로봇/PC Zenoh ON. 추가 이동 요청은 없다. 새 기본 실행에 영구 적용했다고 간주하지 않는다.
- 최종 실기 계측: 로봇 `runs/handoff_diagnostics/trace-4G8U9aRc`. 일반 trial: `runs/tag_bias_trial/20261023_165950_381707_on` (last_trial.txt 및 capture launch 헤더 대조).
- PC 보존: `runs/handoff_diagnostics/20261023_review/evidence_after.tar.gz` (변경 소스, manifest, 테스트/빌드 로그, captures). PC 운영 소스와 로봇은 자동 동기화하지 않았다. Python 차이 20개는 `pc_robot_differences.json`에 기록했다.

### 원복 및 다음 작업

진행 중인 이동이 없고 launch가 종료된 상태에서만 담당자가 원복한다. 원본 lock state는 보존되어 있으며 이번 계층을 먼저 제거해야 한다. 다음 명령은 기록용이며 이번에는 실행하지 않았다.

```bash
# 로봇 vic 터미널: launch 종료 확인 후
python3 /home/vic/Downloads/handoff_input_trace_20261023/handoff_diagnostics/install_trace_layer.py \
  --root /home/vic/vmany/main/farm_project \
  --bundle /home/vic/Downloads/handoff_input_trace_20261023/fixed_trace_v3 \
  --state /home/vic/Downloads/handoff_lock_fix/state_2742f94ff21d.json --rollback
source /home/vic/Downloads/handoff_completion_fix/environment.bash
cd /home/vic/vmany/main/farm_project/robot/ros_ws
colcon build --packages-select harvest_robot --allow-overriding harvest_robot
```

다음은 충돌 판정 순간 costmap/footprint/경로 증거 및 현장 환경 대조다. 정지 후 costmap만으로 실패 당시 원인을 확정하지 않는다. 일반 주행 정상 도착을 다시 확보하기 전 인계 전체 실기를 진행하지 않는다. 이번에 TF 실행 문맥 개선을 확인했지만 GIL/CPU 격리를 보장하거나 전체 부하 안정성·복귀 성공을 선언하지 않는다. Git commit/push 없음.

### 종료 전 재대조

로봇 manifest의 변경 파일 11개가 모두 적용 후 hash와 일치했다. node.py/status.py/handoff_pose_context.py/handoff_runtime.py 소스와 설치본이 일치하며, 기존 lock state는 lock_state_before.json과 바이트 hash가 동일하다. 로봇의 기존 인계 문서는 lock 패치 추적 대상이므로 덮어쓰지 않고 이번 보고서를 docs/changes에 새로 보관한다. 과거 절의 인증 대기·미적용 설명은 당시 기록이며 후속 직접 수정 절이 현재 상태다.

## 정지 유지 후 충돌 판정 조사 — 2026-10-23 17:26 KST

사용자가 실제 정지를 확인한 뒤 읽기 전용 조사만 수행했다. 이동/initialpose/clear costmap/파라미터 변경/재시작 없음.

- 실패 로그: 17:02:10 (ROS 1792742530.024545), 일반 controller_server의 RPP collision ahead, FollowPath abort. 인계 전용 controller 실패가 아니다.
- 실행 파라미터: local costmap 5×5m, 0.02m/cell, odom frame, base_link; footprint 0.60×0.50m + padding .02m, 실제 published footprint 0.64×0.54m. voxel+inflation, inflation radius .7m. 일반 controller 충돌 검사 true, 예측 상한 1초, failure_tolerance=0.0. 이 값을 수정하지 않았다.
- 17:26:07 정지 후 표본: status IDLE/ready, map pose x=.0379448,y=-.1077967,yaw=.816680; odom 선속도/각속도 모두 0. costmap/footprint/voxel/scan/status 8초 수신 확인.
- 동일 odom frame에서 현재 published footprint와 lethal(254) cell center를 비교했다. 가장 가까운 셀은 차체 좌표 x=-.329856m,y=+.280844m(왼쪽 뒤), padding 포함 외곽과 중심 거리 .014653m. voxel layer에도 같은 lethal 셀이 있어 단순 inflation 셀만의 현상은 아니다. 셀 크기 .02m 및 표본 시차가 있으므로 실물 여유 거리로 해석하지 않는다. footprint 내부에 lethal 셀 중심은 0개였으나 이것만으로 Nav2의 격자 경계 충돌 검사 또는 회전/미래 경로 안전을 보장하지 않는다.
- 이 관측은 멈춘 뒤 약 24분 후이며 실패 순간 자료가 아니다. 회전 시 왼쪽 뒤 모서리 주변 장애물 셀이 영향을 줄 가능성은 있으나, 실물 장애물/센서 잔상/차체 형상·위치 오차 중 무엇인지 미확정.
- received_global_plan/lookahead_collision_arc/lookahead_point/plan은 관측 구간에 수신되지 않았다. 시험 폴더에 rosbag은 없고 launch.log/localization.yaml/environment.yaml/manifest.json만 확인했다. 따라서 당시 충돌 셀·예측 속도·경로를 복원했다고 주장하지 않는다.
- 실패 9.4초 전 handoff local costmap에 laser TF cache drop 기록이 있지만 일반 controller 실패의 인과 증거는 아니다. 이후 일반 costmap에서도 산발적으로 drop 기록이 있어 다음 동시 수집 대상이다. harvest 전용 TF buffer 개선이 Nav2의 별도 buffer까지 개선했다는 뜻은 아니다.

증거: `runs/handoff_diagnostics/20261023_review/post_stop_collision.json`, `post_stop_controller.yaml`, `post_stop_costmap.yaml`, `post_stop_geometry.json`, `post_stop_obstacles.png`. 로봇 원본은 `/home/vic/Downloads/handoff_input_trace_20261023/post_stop_*`.

다음 실기 전에 현장 왼쪽 뒤 주변/차체 실제 외형과 footprint를 대조한다. 재시험을 하게 되면 이동 전에 일반 costmap_raw/voxel_layer_raw/published_footprint/received_global_plan/lookahead_collision_arc/lookahead_point/scan_filtered/odom/TF/속도 출력을 같은 구간에 저장해야 한다. 현재 증거만으로 footprint 축소·충돌 검사 해제·재이동을 하지 않는다. 인계 전체 완료는 여전히 미검증이다.

## 사용자 지적 후 성공 설정 재대조 — 2026-10-23

사용자는 과거 전진·회전을 함께 하며 코너를 통과했고 이를 위해 해상도/footprint를 수정했다고 설명했다. 정지 후 장애물 셀만으로 동작 차이를 설명할 수 없으며 앞선 조사에 성공 실행 대비 검토가 빠져 있었다.

- Git 6f21119edb2ac3bfa25cb3eb45fad8d6dd03018b에서 local resolution .025→.02 변경 및 코너 통과/14번 도착 성공 기록 확인. `HARVEST_LOCAL_RESOLUTION_TRIAL_20261018.md`의 18:56:57 SUCCESS 기록과 일치한다. 앞선 FIELD_PRESERVATION 문서의 .025는 이전 시점 기록이다.
- 로봇 15:52:36 시험은 일반 controller goal 수신2/Reached the goal2/collision0. 이번 16:59:50 시험은 goal1/성공0/collision1. 양 manifest의 vicpinky/nav2.yaml, harvest_nav2.yaml, harvest_navigation.yaml, harvest_task.yaml 및 두 BT XML 해시 모두 동일하다.
- 15:52 시험의 실제 보존 nav2.yaml snapshot에서 .02m, footprint x±.30/y±.25, padding .02 확인. 현재 실행 파라미터도 같은 값. 이번 변경으로 성공 설정을 되돌렸다는 증거 없음. 과거 런타임 동적 변경 여부는 manifest만으로 증명하지 않는다.
- 현재 use_rotate_to_heading=true, min_angle=.104719755rad(6도). 이 설정값만으로 실패 당시 제자리 회전 분기 선택을 확정할 수 없다. 전진+회전 궤적과 그 자리 회전의 swept footprint는 다르므로 정지 상태 외곽 근접만으로 기존 통과 가능성을 부정하지 않는다.
- 이번 내부/외부 계측에는 odom/TF 시각만 있고 twist·transform 좌표가 없으므로 실패 순간 선속도·각속도 및 궤적을 복원할 수 없다. 기존 성공과 동일한 복합 이동을 했다고도, 하지 않았다고도 결론내리지 않는다. 다음 비교 수집은 선속도/각속도·경로·lookahead·costmap을 함께 보존해야 한다.
- 읽기 분석과 문서 추가만 수행. 해상도/footprint/회전 설정, 프로세스 및 로봇 위치 변경 없음.

## 과거 복합 이동 bag 확인 및 현재 경로 회수 — 2026-10-23

읽기 전용 bag 분석을 수행했고 bag play/이동/파라미터 변경은 하지 않았다.

- 로봇 `runs/tag_bias_trial/20261018_185412_684309_on/bag/bag_0.mcap`의 cmd_vel_nav/cmd_vel/odom을 직접 역직렬화했다. 사용자 설명대로 전진과 회전을 함께 하는 구간이 실제로 있었다. 제자리 회전도 섞여 있다.
- 예: 18:55:42.389–50.541은 명령 v=0, w 약 -.1rad/s. 18:55:50.589–51.089는 v=.0532–.0640m/s,w=-.1111rad/s. 이후에도 짧은 전진·회전과 제자리 회전이 교대했다.
- 18:55:50.589–18:56:01.290의 odom 304개 중 v>.005m/s 및 |w|>.01rad/s인 표본183개. 해당 구간 odom 시작/끝 순변위 .254198m, yaw 변화 -.906651rad(약-52도). 명령만이 아니라 실측 odom에서도 복합 이동 확인. 적분 주행거리가 아니라 시작/끝 순변위다.
- 이번 task_events는 TRANSIENT_LOCAL+RELIABLE로 회수했다. task TRACE_36f97f03588c_SEC01_TASK001, 실패 SECTION_APPROACH. 생성된 map 경로: (.094372,-1.124430)→(.046,-1.12)→(.046,-.72)→(.046,-.035)→(1.046,-.035), reverse=false, edges28/26/14. WINDOW_MOVE 진입 전 실패다.
- 실제 생성 경로는 전진 코너 통과를 포함한다. 경로 보존과 속도 제어 분기는 별개이므로 이번에도 같은 속도 조합을 사용했다고 확정하지 않는다. 이번 속도 bag은 없으며 기존 시각 계측만으로 사후 복원 불가.
- 이전 기록 도구 trial.py는 이동 전 rosbag을 시작했지만 이번 send_window_once.py는 내부/외부 시각 계측만 사용했다. 이 차이로 이번 충돌의 속도/예측 경로가 누락됐다. 다음 실기 전 해당 원시 토픽을 함께 기록해야 하며, 이번에는 재이동하지 않았다.
- 추가 발견: 현재 launch의 tag_capture_session이 code1로 종료된 로그가 있다. 정확한 실패 원인 및 충돌과 인과관계는 아직 확인하지 않았다. Zenoh/주행 노드 실행과 태그 보정 정상 동작을 동일하게 취급하지 않는다.

자료: `corner_bag_comparison.json`(과거 두 bag 분석), `latest_task_event.yaml`(현재 실패 경로), 로봇 분석기 `Downloads/handoff_input_trace_20261023/analyze_corner_bag.py`. 임계 v>.005, |w|>.01은 오프라인 구간 분류용이며 제어 설정 변경이 아니다.

태그 오류 추가 확인: 현재 시험 capture.log는 `CAPTURE_ERROR: Camera already in use, PIDs: 49485`다. 후속 ps 조회에서 해당 PID는 존재하지 않았다. 캡처 시작 당시 점유와 현재 점유를 구분한다. 태그 캡처 정상 상태에서 시험했다는 보장은 없으며 충돌의 직접 원인으로 확정하지 않는다.

## 카메라 복구 및 1회 코너 비교 이동 — 2026-10-23 17:53 KST

사용자 승인: “진행해줘”, 이어 “옮기지 않은 상태야. 이동할 수 있어”. 기존 정지 위치를 유지한 상태에서 1회 window 이동만 요청했다. 스테이션 initialpose/해상도/footprint/주행 코드 변경 없음.

- 카메라 /dev/video0 점유 없음 확인 후 기존 tag_capture_session과 동일한 config로 캡처+어댑터만 별도 복구했다. 세션 `runs/harvest_tag/20261023_175124_7kgibqof`. 설치본/소스 capture_session.py SHA 동일. Nav2/harvest/AMCL/Zenoh 재시작 없음.
- detections.jsonl 갱신 및 TAG_ADAPTER_RUNNING 확인. 이동 전 검출은 빈 배열이었고 수신 age 약 .58~.73s 표본이 있었다. 카메라 실행과 태그 검출/보정 성공을 구분한다.
- 수집기 record_corner.bash 추가, bash -n 통과. 기록 폴더 `runs/handoff_diagnostics/corner-qyqditfy`. 원시 속도·odom·TF·경로·예측 arc·costmap/voxel/footprint·scan·task/tag events/rosout 저장.
- PC 첫 실행은 rclpy 초기화 중 ROS 로그 폴더 쓰기 권한 오류로 종료, 요청 미전송. 프로젝트 내부 ROS_LOG_DIR를 지정한 뒤 한 번 전송했다. task `COMPARE_fa31c5a9e826_SEC01_TASK001`.
- 17:53:13 수락 → SECTION_APPROACH ARRIVED → WINDOW_MOVE ARRIVED → 17:53:43.975685 최종 Action status4/SUCCESS/NONE.
- 최종 도착 판정 실제 map=(1.16537004,-.02958166),yaw=.01224030rad. 목표(1.186,-.035,0), 위치오차 .02132964m, 방향오차 .01224030rad, accepted=true. arm_operation=SKIPPED, expected/harvested/failed count0, ARRIVAL_ONLY_NO_HARVEST.
- 현재 위치에서 재생성한 접근 경로 (.0379448,-.1077967)→(.046,-.1077967)→(.046,-.035)→(1.046,-.035), reverse=false. 따라서 이전 스테이션부터 진행한 경로의 연속 실행과 동일 조건이 아니다.
- cmd_vel_nav 실제 기록: v 약 .054~.074m/s와 음의 w를 함께 출력하는 구간, v=0/w≈-.1rad/s인 회전 구간이 교대했다. 초반 ROS1792745593.67~5604.4 odom321개 중 복합 이동 표본182개(v>.005, |w|>.01), 시작/끝 순변위 .286916m, 방향변화 -.849100rad(약-48.7도). 실제 전진·회전 기능이 작동함을 확인했다.
- bag 내 일반 controller goal2/Reached2, collision ahead 없음. 전체 인계 실기 성공이나 최초 충돌 원인 해결로 확대하지 않는다.
- 태그 이벤트63개: inactive_or_task_begin 거절50, lease_renewed 수락13. 태그 correction topic 표본0, 적용 성공 증거 없음. 카메라 복구가 주행 성공 원인이라는 근거 없음. 태그 control barrier와 검출/신선도는 별도 후속 조사 대상.
- 수집 종료 시 SSH PTY 종료로 MCAP message index/metadata가 정상 마무리되지 않았다. 소유 recorder가 남지 않았음을 확인하고 ros2 bag reindex로 metadata를 재구성했다. 순차 오프라인 읽기 성공: 17:52:28.986~17:53:59.061, 13,465메시지. 완료 이벤트보다15초 뒤까지 기록. 인덱스 없는 file-order 읽기 경고를 보존하며 완전한 정상 종료 bag이라고 표현하지 않는다.
- body_trial/status 읽기 결과 IDLE. enter/restore 호출 없음. 현재 window 위치에 있으며 launch/로봇·PC Zenoh/복구 카메라는 유지. 자동 반복 이동 없음.

PC 보존: `runs/handoff_diagnostics/20261023_review/corner-qyqditfy/bag`, `events_summary.json`, `corner_retry_analysis.json`, `corner_window_goal.json`, `corner_window_action_sent.log`. 원시 bag과 분석을 로봇·PC 양쪽에 보존했다. 남은 작업: 성공한 window 기준을 사용한 body-only 인계 진입/정렬/이탈/복귀 실기, 이전 충돌 원인 분리, 태그 보정 제어 상태 검증. Git commit/push 없음.

## body-only 인계 진입 실기 — 2026-10-23 17:59~18:00 KST

사용자 “인계 시험 진행해줘” 승인으로 성공 window 도착 기준을 유지한 채 enter를 한 번 호출했다. 시작 전 phase IDLE 및 현재 window pose를 조회했다. 초기 위치/운영 소스/설정/허용치 변경 없음. Zenoh ON.

- 수집 폴더: 로봇 `runs/handoff_diagnostics/body-93i_ilav`, PC `runs/handoff_diagnostics/20261023_review/body-93i_ilav`. 독립 세션 recorder PID71352를 생성했고 종료 시 소유 pid/cmdline 확인 후 SIGINT로 정상 마감했다. metadata.yaml 생성 확인.
- enter 응답 success=true, ENTERING, request_accepted_only=true. 실제 성공 아님.
- build_body 동일 시각 TF pair 약 .321s, build_body 전체 .417s 완료. planner capture .758s, departure 경로 guard 약2.559s 완료.
- ROS1792745996.193311 인계 전용 controller가 goal 수신. 출력 비영 cmd_vel_nav92개(분석 구간1792745996~6003), 마지막 비영1792746001.96036, v=-.01m/s,w=.109174rad/s. 실제 차체 회전/이동 시작 확인.
- ROS1792746002.401737 controller cancellation successful, 1792746004.667978 BODY_TRIAL RECOVERY_REQUIRED, detail='곡선 속도 입력 시간 초과', arm_tested=false. 정렬 완료/ENTERED에 도달하지 못함. restore/재enter 미호출.
- 사용자 “회전하다가 멈춰있는 상태야” 확인. 실패 후 odom linear/angular 모든 성분0 확인. 최종 status ERROR/ready=false, map pose=(1.10705778,-.04465087),yaw=.62727652rad(약35.9도). CANCEL_UNCONFIRMED는 blocked 상태의 포괄 메시지이며 별도로 controller 취소 성공 및 실측 정지 확인 기록을 함께 본다. 현재 위치는 window 도착 당시 자세와 다르다.
- 이번 오류의 코드상 조건: 공통 arc_isolation.CommandGate.expired는 last_received 이후 .3s 초과 또는 최초5s 초과를 검사한다. fixed runtime은 무거운 검사 및 센서 snapshot identity 검사 통과 후에만 gate.accept로 last_received를 갱신한다. 따라서 메시지의 '입력'은 raw callback 도착 시각 자체가 아니라 최종 gate 승인 시각이다.
- 실행 중 fixed input_changed_drop 기록(5초 구간8회), validation_busy_drop1회 관측. 센서 갱신 때문에 승인 못 한 속도가 누적되는 후보가 있다. 그러나 오류 순간의 원시 raw_nav/forward 세부 판정 기록이 없어 controller 발행 지연과 구분 완료 아님.
- 같은 구간 외부 odom 최대 간격 .059745s, 내부 odom callback header age 최대 .260739s, watchdog 호출 간격 최대 .168118s. 이전 진입 전 TF pair 실패/odom 만료와 다른 실패다. 이 수치만으로 executor 지연 전체를 배제하지 않는다.
- 이번 bag은 handoff/raw_nav/raw_spin을 누락했다. 이 한계를 명시하며 원인 확정하지 않는다. 후속 공용 수집 스크립트 record_corner.bash에 raw_nav/raw_spin/cmd_vel_normal 및 인계 costmap/경로를 추가하고 bash -n 검증했다. 수집기 변경만이며 운영 코드 수정/재빌드 없음. 다음에는 gate.accept/거절 사유/expiry age를 같이 계측해야 한다.
- 운영 manifest11개 hash와 원래 lock state 모두 변경 없음 확인. PC/로봇 백업과 핫픽스 보존. 허용시간 연장이나 fixed 임의 원복 없음.

현재는 RECOVERY_REQUIRED에서 중단. 전체 인계·벽 정렬·이탈·복귀 미완료, device_services=NOT_TESTED: body-only scope. 자동 반복 시험 없음. 다음은 속도 승인 공백 원인 분석 및 원복 가능한 최소 진단/수정 검증이며, 위치·복구 절차 확인 전 새 이동을 하지 않는다. Git commit/push 없음.

## 정지 유지 중 속도 승인 공백 오프라인 재현 — 2026-10-23

사용자 “그대로 유지중이야. 필요한 부분 확인 진행해줘”에 따라 읽기/오프라인 검증/별도 계측 후보 준비만 수행. 운영 소스 수정·빌드·재시작·실기 이동 없음.

- 실제 로봇 HandoffRuntime._forward_control/_watchdog_control/stop_output/_read와 실제 CommandGate 클래스를 AST로 로드한 재현 도구 `test_gate_starvation.py` 추가. ROS init, publisher 생성, 물리 이동 없이 fake monotonic clock과 입력 갱신만 주입한다. DDS graph 검사는 fixture로 대체하므로 ROS scheduling 성능 시험이 아니다.
- 입력을 검사 전에 갱신하면 20Hz 속도 전달이 지속된다. 검증 중 odom/costmap/footprint 중 하나를 새 수신 객체로 매회 교체하면 최신 입력과 20Hz 명령이 있어도 gate.accept에 도달하지 못해 .3초 승인 공백 후 동일 '곡선 속도 입력 시간 초과'가 발생했다. sensor timestamp는 매회 최신이다.
- 내용이 같아도 tuple/msg identity가 달라지면 거절되는 코드 경로다. 실물에서 오류 직전 연속 거절이었는지는 기존 5초 집계로 확정하지 않는다. raw_nav 발행·콜백 지연 후보도 남는다.
- 검사 도중 stop_output 발생 시 늦은 결과가 비영 출력하지 않는 회귀 통과. 수신 시각만 갱신해 timeout을 숨기거나 identity 검사를 그냥 제거하는 변경은 하지 않았다.
- 추가 계측 생성기 `prepare_output_trace.py`: 원시 속도 수신, snapshot, busy/입력 변경 거절, gate commit 시도/승인, 예외, watchdog 만료 당시 gate 마지막 승인/arm 시각 기록 후보를 생성한다. 진단 호출을 제거한 AST가 원본과 동일한지 검사한다. 원본 바이트/전후 SHA manifest 포함.
- 초기 PC 후보에서 WallCommandGate의 last/start와 CommandGate의 last_received/started 필드 차이를 검토하여 v2는 두 계약을 구분해 기록한다. 최초 후보는 미적용 폐기 대상이며 사용할 후보는 output_trace_candidate_v2다.
- 실제 로봇 운영 코드에 재현5개 통과. 최종 계측 v2에는 wall gate 계약 회귀까지 포함6개를 PC/로봇 모두 통과. v2는 `/home/vic/Downloads/handoff_input_trace_20261023/output_trace_candidate_v2`에만 저장했고 운영 경로에 적용하지 않았다. 원래 patch state 변경 없음.
- 이번 결과는 fixed의 승인 고갈 가능성 재현이지 실기 원인 확정/해결이 아니다. 추가 계측은 현재 복구 상태를 잃는 재시작 없이 활성화할 수 없으므로 보관만 했다. 다음 적용은 기존 계측 계층 manifest와 원본을 보존하고, 정지/복구·새 window 기준 확보 순서를 마련한 뒤 진행한다.

자료: PC `runs/handoff_diagnostics/20261023_review/gate_starvation_tests.log`, `output_trace_candidate_v2/{manifest.json,tests.log,handoff_runtime.before.py,handoff_runtime.py}`. 로봇에도 원본 기반 후보/검증 로그 보존. 다음 판단은 raw 명령 공백인지 검증 거절 공백인지 구분하는 것이며, 반복 실기를 먼저 요청하지 않는다. 현재 RECOVERY_REQUIRED/정지 유지, 전체 인계 미완료/팔 미시험. commit/push 없음.


## 성공한 독립 시험과 통합/fixed 구조 대조 — 2026-10-23

사용자 요청 “그거 먼저 추적해서 대조해줘”에 따라 과거 성공 원본, 배포 baseline, fixed 직전 백업, 현장 fixed 캡처와 현재 실행 파라미터를 읽기 비교했다. 기준 Git HEAD는 4b5c5b13605216d1b8b163ea988805572a6a908a, feat/harvest-handoff-real-20261018이며 미커밋 현장 변경은 별도로 보존한다. 이번 비교에서는 운영 코드·설정 수정, 빌드, 재시작, 이동을 하지 않았다.

### 성공 근거와 비교 범위

- 로봇 runs/transfer_arc_isolated/1792515027317166381/1792515032661527268_arc.json: 2026-10-21 01:50:34~49 KST, SUCCEEDED, navigation ARRIVED/nav2_status=4/accepted=true, cleanup_stopped=true. 공통 Navigator를 사용하는 독립 시험도 실제 곡선 완료 기록이 있다. 반경 .1m, 끝점 오차 .00118022m, yaw 오차 .00953801rad.
- 로봇 runs/wall_alignment/1792515109507469094/result.json: 같은 날 01:51:55~01:52:07 KST, SUCCEEDED, navigation ARRIVED/nav2_status=4, 정지 정리 완료. 독립 벽 정렬도 공통 Navigator 사용 후 성공했다.
- 따라서 공통 주행 모듈 재사용 자체가 실패의 충분한 설명은 아니다. 위 기록은 개별 곡선·벽 정렬 성공이며, 현재 window 기반 인계 전체 시퀀스 성공 증거는 아니다. 과거 위치·환경과 현재 시험은 같지 않다.
- 성공 당시 parameters.yaml과 현재 handoff/controller_server 및 handoff/local_costmap/local_costmap의 ros2 param dump를 비교했다. TransferArc.*, transfer_arc_goal.*, transfer_arc_progress.*의 과거 명시 설정 25개 모두 일치. 주요 costmap 8개(footprint, padding, resolution, frame 두 항목, 갱신/발행 주기, plugins)도 일치. .01m/s, .04m lookahead, goal .005m/.04rad, costmap .02m, footprint ±.30/±.25m, padding .02m 유지.
- 전체 설정 동일이라는 뜻은 아니다. 공통 키 전체를 추가 비교하면 controller/goal/progress 목록이 통합용으로 확장됐고 min_x/y/theta_velocity_threshold는 .001/.0001/.0001에서 모두0으로 바뀌었다. costmap map_topic은 /harvest_01/map에서 /harvest_01/handoff/map으로 다르다. voxel+inflation 구성이고 static layer는 목록에 없다. 이 차이가 이번 승인 timeout의 원인이라는 증거는 없다. 과거 YAML에 없는 현재 기본 파라미터와 당시 실행 바이너리까지 동일하다고 주장하지 않는다.

### 실행 및 잠금 비교

| 항목 | 성공 기록이 있는 독립 시험 구조 | 통합 후 fixed 이전 | 현재 fixed |
|---|---|---|---|
| 실행기 | 별도 transfer_arc_trial 노드, SingleThreadedExecutor; 시험 본문과 spin 스레드 분리 | harvest MultiThreadedExecutor 4 threads, Reentrant callbacks; body 본문은 별도 worker | 같은 harvest 실행기, odom 전용 MutuallyExclusive group; 현재 TF는 후속 전용 실행기 구성 |
| 출력 검사 잠금 | relay_guard로 forward/watchdog 직렬화; 단일 executor라 센서 콜백이 forward 도중 실행되지 않음 | runtime RLock 안에서 check/live_guard/gate/publish 수행 | 짧게 snapshot 확보 → 잠금 밖 검사 → 잠금 안 commit |
| 반복 검사 | 캐시된 action status, 입력 age, 속도 축 및 gate 검사 | 소유권/취소/odom 세션, DDS graph 조회, 입력 freshness/형상 검사 추가 | 통합 검사 + 최종 최신 상태 재검사; callback 경쟁 시 nonblocking validation lock 거절 |
| 센서 갱신 처리 | 출력 검사 중 동시 callback 갱신 없음 | 동일 runtime lock으로 수신 저장과 검사 직렬화 | 검사 중 odom/costmap/footprint 수신 객체 하나라도 교체되면 zero 발행 후 거절 |
| gate 승인 시각 | gate.accept 통과 시 갱신 | 동일 | identity 거절 시 gate.accept 미도달, 승인 시각 미갱신 |

소스 근거: PC Downloads/handoff_integration/baseline/farm_project/robot/tools/transfer/arc_trial.py의 forward/no_other_actions; 로봇 /home/vic/vmany/main/handoff-lock-backup-3qrtssz_/robot/ros_ws/src/harvest_robot/harvest_robot/handoff_runtime.py의 _forward; PC 보존 output_trace_candidate_v2/handoff_runtime.before.py의 _forward_control. 배포 baseline은 역사적 코드 비교 자료이며 성공 실행 당시 파일의 바이트 해시는 결과 JSON에 없으므로 정확한 역사적 바이너리 재현으로 간주하지 않는다.

### 현재 실패와 연결되는 부분

1. fixed에서 추가한 `self.latest.get(k) is not snapshot.get(k)`는 시각이 정상이고 값이 같아도 새 수신 객체면 출력을 거절한다. 예전 독립 시험과 fixed 이전 통합 출력 경로에는 없던 조건이다.
2. 공통 gate는 raw callback 도착 자체가 아닌 최종 승인으로 last_received를 갱신한다. 기존 .3초 승인 간격 제한과 새 identity 거절이 결합하면, 입력이 계속 도착해도 timeout이 가능하다. 앞 절 실제 메서드 기반 주입 시험에서 재현했다. 실제 ROS scheduling 재현 또는 실기 원인 확정은 아니다.
3. 실제 18시 실패 구간에도 input_changed_drop이 있었지만 집계 단위는5초다. raw_nav와 세부 승인 기록이 없어 실패 직전 .3초 연속 거절인지, raw 발행/콜백 공백인지 분리할 수 없다.
4. 통합 check는 DDS graph를 조회하며 fixed에서는 최종 check도 추가됐다. 이는 독립 시험의 캐시 status 검사보다 작업이 늘어난 지점이다. departure의 live_guard는 입력 freshness/frame/footprint 형상을 확인하며 매 명령마다 전체 grid 충돌 계산을 하는 것으로 설명하면 부정확하다. 진입 전 경로 충돌검사와 실행 중 검사를 구분한다.
5. baseline 15:47의 odom 만료, fixed 15:52의 TF pair 확보 실패, 이후18시 실제 goal 전송 후 속도 승인 timeout은 별개 실패다. 이번 identity 조건은 현재 timeout의 유력 후보이며 baseline 장애까지 같은 원인으로 소급하지 않는다.

다음 수정 검토 범위는 출력 검사의 동시성·유효성 계약이다. 취소/소유권/단계 변경에 대한 epoch 재검증은 유지하고, 정상 센서 갱신을 무조건 무효화하는 조건과 검사 부하를 검토한다. identity 검사 단순 삭제, freshness 완화, timeout 연장, 과거 프로젝트 전체 원복은 적용하지 않았다. 추가 계측 v2는 여전히 별도 후보이며 미설치다. 현재 현장 RECOVERY_REQUIRED/정지 유지; 전체 인계 및 팔 동작 미검증.

증거 PC 보존: runs/handoff_diagnostics/20261023_review/structure_comparison/parameters.json 및 historical_success.tar.gz. 로봇 비교 원본: /home/vic/Downloads/handoff_input_trace_20261023/structure_comparison.json. 문서 추가만 수행했고 원복은 이 절과 연결 기록만 제거하면 된다. Git commit/push 없음.


## 센서 갱신 후 최신 입력 commit 수정 — 2026-10-23 (격리 빌드 완료, 운영 미적용)

승인 근거: 사용자 “취소·정지 보호는 유지하면서 정상 센서 갱신 때문에 출력이 막히는 부분을 수정하고 오프라인 검증까지 진행해줘. 기존 핫픽스는 보존하고, 실기 이동 전에는 알려줘.” 현재 현장 정지/복구 상태를 보존하기 위해 실제 로봇 원본을 기준으로 별도 복사본을 수정·빌드했다. PC의 오래된 운영 소스를 로봇에 덮어쓰지 않았다.

| 변경 대상 | 변경 내용 및 이유 |
|---|---|
| 별도 복사본 HandoffRuntime._forward_control | departure/return/retreat이고 clearance가 없을 때, 메시지 객체 교체 자체로 거절하지 않고 최종 runtime lock 안에서 최신 odom freshness와 _grid_inputs의 costmap/footprint freshness·frame·형상을 재검사한 뒤 출력 |
| prepare_sensor_commit_fix.py | 현장 원본 SHA 7f64062129f6e285dbcf8a6c1e00d2245a29ecd7631d4ebb81795df55cad7385에만 적용하는 후보 생성기. 원본 바이트, diff, 전후 해시 보존. _forward_control 이외 AST 불변 확인 |
| test_sensor_commit_fix.py | 실제 runtime/gate 메서드를 로드하는 무동작 회귀20개. DDS/시계/출력은 fixture이며 ROS 노드 생성 없음 |

보호 유지: gate identity, epoch, 취소, 정지, error, 출력 소유권 및 최종 check의 세션 검사를 유지한다. 검사가 진행되는 동안 runtime lock은 풀려 있어 stop_output이 즉시 잠금을 얻을 수 있고, 최종 publish까지는 짧은 lock으로 직렬화한다. 추가 commit 검사는 TF 대기·graph 조회·전체 grid 계산을 포함하지 않는다. odom 수신에서 검출한 측정속도 오류도 기존 error 검사로 차단한다. timeout/freshness 값, 충돌 설정, footprint, controller 목록, 공통 모듈은 변경하지 않았다.

범위 제한: window/align/wall 및 clearance가 남은 경로는 기존 identity 보호를 유지한다. 이 단계의 자세·지도별 충돌/관측 증명까지 임의로 최신 메시지로 대체하지 않는다. 따라서 모든 단계의 승인 고갈을 해결했다고 주장하지 않는다. 곡선/후진 이탈에서 실행 중 충돌 검사는 기존 Nav2 controller가 유지한다. 나머지 단계의 구조 검토와 전체 실기는 별도다.

검증:
- PC/로봇 각각 새 회귀20개 통과. 정상 odom/costmap/footprint를 검사 도중 매회 갱신해도20Hz 출력 승인이1초 동안 지속. 취소, 정지, 소유권 상실, gate/epoch 교체, 수신 오류, 최종 세션 오류, 낡은 입력, frame/형상 오류, 동시 검사 차단 및 실제 명령 단절 timeout 확인.
- 실제 Python 스레드에서 validation을 Event로 멈춘 동안 stop_output을 실행하고 검사 재개 후 비영 출력 없음 확인. 이는 ROS executor/GIL 실측 시험이 아니다.
- 로봇 별도 workspace에서 harvest_robot colcon build 성공. underlay의 같은 패키지 존재 경고는 보존. 격리 설치본 handoff_runtime.py와 후보 해시 동일 확인. 운영 install로 빌드하지 않았다.
- 기존 인계 회귀 최초62통과/2실패: 복사본 경로가 기존 시험의 project root 계산과 달라 파일을 찾지 못했다. 시험 코드/기대값을 바꾸지 않고 project/robot/ros_ws/src와 설정 복사본을 구성한 뒤64개 모두 통과. 최초 실패 로그도 보존.
- 기존 계측 계층11개 파일 해시, 이전 manifest, 원래 lock patch state 해시 모두 보존 확인. 미설치 output_trace_candidate_v2와 이번 수정본을 자동 혼합하지 않았다.

산출물: PC runs/handoff_diagnostics/20261023_review/sensor_commit_fix_v1/의 handoff_runtime.before.py, handoff_runtime.py, change.patch, manifest.json, tests.log, build.log, regression.log, regression_layout_fixed.log, verification.json. 로봇 /home/vic/Downloads/handoff_input_trace_20261023/sensor_commit_fix_v1/에 동일 근거와 workspace/src/harvest_robot 및 격리 build/install 보존. 생성기/시험은 robot/tools/transfer/handoff_diagnostics/에 있다.

원복/적용 경계: 현재 운영 미적용이므로 실행본 원복은 불필요하다. 후보는 별도 디렉터리에만 있다. 후속 적용 시 원본 해시를 다시 검증하고 기존 fixed_trace_v3 계층 위의 새 manifest/설치본 백업을 남겨야 한다. 기존 lock state를 후보 해시로 덮어쓰지 않는다. 실행 중 패키지나 install을 교체하지 않고 정지·재시작·현재 위치 및 새 window 기준 확보 절차를 먼저 안내한다. 이번에 기동/재시작/이동/initialpose를 하지 않았다. 전체 인계 실기 미완료, device_services=NOT_TESTED: body-only scope. Git commit/push 없음.


## 센서 갱신 수정본 운영 적용 및 단독 재시작 — 2026-10-23 18:39 KST

사용자 승인: “기존 핫픽스 백업 유지하면서 수정본을 실행본에 적용해줘. 재시작 전에 현재 로봇 상태와 복구 절차 확인하고, 이동은 나한테 알려준 뒤 진행해.” 앞 절의 운영 미적용 상태는 이 절부터 변경된다.

- 사전 실제 조회: body RECOVERY_REQUIRED/곡선 속도 입력 시간 초과, status ERROR/ready=false, odom 선속도·각속도 전 성분0. map pose x=1.1071090004,y=-.0446137147,yaw=.6275716588rad. 초기 스테이션 위치가 아니다.
- 코드상 restore는 ENTERED에서만 허용, reset 서비스 없음. 재시작 시 window=None이고 성공한 window 도착 기준이 다시 필요함을 확인했다. 사용자에게 단독 재시작·기준 소실·초기 좌표 및 이동 미전송 방침을 사전 안내했다.
- 기존 harvest PID51504의 argv/허용목록 환경/params를 보존. SIGTERM으로 정상 종료 확인 후에만 handoff_runtime.py 수정본 적용. 나머지10개 핫픽스 소스, 기존 fixed_trace_v3 manifest 및 원래 lock state는 해시 보존. 원래 state/manifest는 새 계층을 포함하지 않으므로 현재 파일과 바로 일치하지 않는 것이 정상이며 덮어쓰지 않는다.
- 변경 직전 runtime 바이트 및 harvest_robot 설치 디렉터리 전체 tar 백업을 먼저 생성했다. 백업 위치: 로봇 /home/vic/Downloads/handoff_input_trace_20261023/sensor_commit_fix_v1/deployment/의 handoff_runtime.before.py, install_before.tar.gz, previous_layer_manifest.json, lock_state.json, receipt.json. launch.json은 환경을 포함하므로 로봇에서 mode0600으로 보존하며 PC로 복사/출력하지 않았다.
- 운영 workspace에서 harvest_robot colcon build 성공. source와 운영 install runtime 해시가 검증 후보 after 해시와 동일한지 확인했다. 기존 패키지 underlay 경고는 build.log에 보존.
- 새 harvest PID85474, 기존 argv와 params 복사본 및 HANDOFF_TF_EXECUTOR=dedicated로 단독 재시작. trace 출력은 deployment/trace로 분리했다. 원래 launch PID51464 및 Zenoh PID51880 유지. AMCL/Nav2/드라이버를 종료하거나 재기동하지 않았다. 카메라나 초기 위치도 변경하지 않았다.
- 단독 노드는 기존 launch의 자식이 아니라 별도 세션이다. 다음 전체 launch 종료/재시작 때 이 PID의 cmdline과 receipt를 확인하여 함께 정상 종료해야 중복 노드를 방지할 수 있다. 임의 pkill 사용 금지. launch_guard/프로세스 확인 후 전체 기동해야 한다.
- 재시작 후: body IDLE, 일반 RobotStatus IDLE/ready=true, 새 boot_id a3efbd407cdd40b7b25a3330e34315e5. pose는 사전 값과 동일, odom 전 성분0. cmd_vel_nav publisher1=harvest_motion_server. harvest 실행 프로세스1개, 전용 TF 기동 로그 확인.
- ready=true는 인계 준비 완료가 아니다. window 기준은 새 도착이 필요하다. 또한 STATION_RETURN_NOT_CONFIGURED 경고가 있어 자동 스테이션 복귀를 복구 수단으로 사용할 수 없다. 현재 자세에서 restore를 호출하거나 스테이션 initialpose를 발행하지 않는다.
- enter/restore/관제 이동/initialpose/clear costmap 호출 없음. 다음은 현장 공간·정지 준비 및 현재 자세를 확인하고 이동 범위를 알린 뒤 정상 window 도착 기준을 재확보하는 절차다. 현재 회전 중 멈췄던 위치에 그대로 있다. 이번 확인은 적용·기동·정지 검증이며 인계 실기 성공이 아니다. 팔 NOT_TESTED.

원복: 현장 정지 확인 후 새 수확 노드를 정상 종료하고, receipt의 after 해시 및 원래 lock state/계층 manifest 해시를 검증한다. deployment/handoff_runtime.before.py를 원래 source 위치로 복원하고 harvest_robot을 재빌드하면 직전 계층으로 돌아간다. 설치 백업 tar도 보존되어 있다. 새 계층 원복 전 기존 handoff_lock_fix 모드 전환 또는 fixed_trace_v3 원복기를 바로 실행하지 않는다. 이번 수정은 runtime의 한 메서드만 변경하며 다른 현장 수정은 보존한다.

PC 근거: runs/handoff_diagnostics/20261023_review/sensor_commit_fix_v1/deployment/{receipt.json,verification.json,body_status.txt,status.yaml,odom.txt,cmd_vel_publishers.txt,build.log,handoff_runtime.before.py}. 로봇 동일 deployment에는 harvest.log와 전체 설치 백업도 있다. Git commit/push 없음.


## 현재 위치에서 window 재확보 1회 요청 — 2026-10-23 18:44 KST (도착 실패, 이동 시작 전 거절)

사용자 “현재 위치에서 window로 다시 이동해서 도착 기준 잡아줘. 로봇은 그대로 있고 이동 가능한 상태야” 승인. body IDLE/status ready 및 odom0, x1.10710866,y-.04461325,yaw.62757166 확인 후 기록을 시작했다. initialpose/설정 변경 없음.

- 최초 recorder 호출은 추정한 스크립트 경로가 없어서 종료했다. 이동 전 이를 확인하고 실제 수집 스크립트를 배치하여 recorder PID87832 및 MCAP 생성/토픽 구독 확인 후 진행했다.
- PC Action 도구는 최신 ready 상태를 수신하지 못해 send_goal_async 전 사전 검사에서 종료. 요청 미전송. PC Zenoh PID27774 및 lo multicast 활성은 확인했으나 통신 정상으로 단정하지 않는다. 후속 로봇 로컬 Action 요청으로 진행한다는 점을 사용자에게 알렸다. 로봇 Zenoh는 계속 ON. 이번 시험은 PC→Zenoh 관제 왕복 성공 검증이 아니다.
- 관제 형식 목표 (1.186,-.035,0), task REACQUIRE_975e691b60eb_SEC01_TASK001/window ...W001. 로봇 로컬 전송1회, ACCEPTED true. 18:44:57.892 KST 최종 Action status6/FAILED/NAVIGATION_FAILED.
- 실제 오류: APPROACH_RECOVERY_REQUIRED: body_heading,path_heading. forward=.078891m,lateral=.009613/.05m, body_heading=.627572/.052360rad(약36°/3°), path_heading=.121256/.087266rad(약6.95°/5°). 도착 실패이며 성공 window 기준 저장 안 됨.
- 현장 corridor_navigation.py: resume_current는 현재 위치가 work corridor 안이면 _plan_current를 호출해 전방/차체·경로 방향을 검사한다. 이 검사가 예외를 던지므로 SECTION_APPROACH로 자동 우회하지 않는다. 현재는 인계 회전 중 멈춘 자세여서 직선 작업 구간 재개 계약에 맞지 않는다. 이 실패는 수정한 인계 출력 gate 실행 실패가 아니다.
- 실패 뒤 status 위치·yaw 동일, IDLE/ready, odom 모든 속도0. bag의 ROS1792748695~8703 구간 odom205개 모두 비영 속도0; 그 구간 cmd_vel/nav는 수신 표본이 없어 수치 비교 불가, rosout goal 관련 표본도 없음. 코드 경로·빠른 거절 결과와 함께 이동 시작 전 실패로 판정. 재요청/enter/restore 없음.
- recorder SIGINT 정상 종료, metadata 생성 확인. 원본 로봇 runs/handoff_diagnostics/window-reacquire-u67nfim0; PC 요약/Action/최종 상태는 runs/handoff_diagnostics/20261023_review/window_reacquire. raw bag은 로봇에 보존. PC 실패 기록과 로봇 실제 전송 결과를 분리했다.

남은 작업: 현재 자세에서 window 재접근을 위한 명시적 복구 경로(위치와 방향 모두)를 검토해야 한다. 방향만 맞춰도 path_heading 제한이 남으므로 제자리 회전만으로 해결된다고 약속하지 않는다. 안전 검사 완화·직접 cmd_vel·같은 이동 반복으로 우회하지 않는다. 다음 이동 전 경로/현장 준비를 다시 알린다. 현재 정지 유지, 성공 도착 기준 미확보, 전체 인계 미완료/팔 미시험. Git commit/push 없음.


## 현재 자세 복구 후보 준비 — 2026-10-23 (읽기·계산만)

사용자 복구 경로 준비 요청으로 실제 설정·센서·TF를 확인했다. 후보는 시계방향35.96° 제자리 회전 →6.11cm 후진 →14cm 전방 window 재요청. 동일 시각 TF 및 실제 padding footprint로 회전/후진 정적 check_grid 통과, 후진 목표에서 기존 straight_plan 검사 통과(경로 방향3.93°<5°). 원시 snapshot과 세부 계획은 runs/handoff_diagnostics/20261023_review/recovery_plan_v1/{plan.json,snapshot.json,RECOVERY_PLAN.md}, 로봇 Downloads/handoff_input_trace_20261023/recovery_plan_v1.

회전 구간 보수적 여유 하한 .0038979m는 실물 여유거리 보장이 아니다. window 포락선은 실제 추종 궤적이 아니며 live collision 검사 필요. 현재 body_trial에는 IDLE/window 없음에서 호출할 부분 복구 입구가 없다. 따라서 실행 가능한 경로라고 표현하지 않는다. 명시적 복구 실행 문맥/소유권과 기존 Spin·Retreat 안전 검사 연결 및 오프라인 검증이 다음 단계다. 기존 align의 identity 거절 보호를 임의 완화하지 않았다. 실행 직전 센서 재검사·현장 준비 확인 및 동작 안내 후에만 이동한다. 이번 publisher/action/service 요청·운영 코드 변경 없음, 전체 인계/도착 기준 미완료.


## 부분 복구 실행 연결 구현 — 2026-10-23 (운영 미적용)

승인: 사용자 “기존 출력 소유권·취소·정지 보호 유지하면서 복구 실행 연결을 구현하고 오프라인 검증까지 진행해줘. 기존 핫픽스는 보존하고, 실제 이동 전에는 알려줘.”

최신 로봇 패키지 전체를 robot_source_before.tar.gz로 PC에 보존한 뒤 별도 project 복사본에서 구현했다. 기존 센서 commit 수정본과 전용 TF/odom 계측/lock 핫픽스를 포함한 현장본이 기준이다. PC의 오래된 운영 패키지로 로봇을 덮어쓰지 않았다.

## 변경

| 파일 | 내용 |
|---|---|
| handoff_recovery.py(신규) | 명시 plan_file 기반 부분 복구 서비스, 실행별 토큰/취소/worker/단계 관리. 현재/목표/section은 검토된 JSON과 기존 설정에서 읽음 |
| node.py | handoff_recovery_plan 노드 파라미터가 비어 있지 않을 때만 생성. 종료 시 worker 회수. 기본 구성은 비활성 |
| handoff_runtime.py | 기존 check 및 출력 commit에 복구 토큰의 정확한 소유자·취소 재검증 추가. 기존 보호 조건 삭제 없음 |
| test_handoff_recovery.py(신규) | 복구 단계/소유권/정리/실패/사전검사 회귀23개 |
| test_recovery_output.py | 실제 runtime 출력 메서드에 복구 취소·다른 transfer 토큰 교체 주입. 기존 센서 commit 시험 포함22개 |

활성화 시 std_srvs/Trigger /harvest_01/handoff/recovery/{start,stop,status}를 제공한다. start 응답은 접수일 뿐 성공이 아니다. 자동 시작·window Action·팔 Action은 없다. 새 launch 인자는 추가하지 않았고, 별도 노드 파라미터로만 선택한다. 실제 운영 프로세스는 아직 이 파라미터/서비스가 없는 기존 코드다.

## 동작 계약

1. node busy/blocked/stopping, body_trial IDLE, 비선점 ActionHandoff 예약 확인. kind=transfer를 재사용하되 정확한 recovery 토큰을 매번 확인한다. 일반 작업이나 body 인계와 병렬 실행하지 않는다.
2. 출력 정지 및 기존 window 무효화, 실제 odom 세션 확보, 실제 정지 확인. 같은 odom 표본 시각의 map/base와 odom/base pair로 시작 자세를 캡처한다. 검토된 JSON의 시작 자세와5mm/기존 정렬1° 이내인지 확인한다. 가짜 RestoreReference/window 성공값을 만들지 않는다.
3. 실제 section entry 진행축 위치에서 후진 끝점을 계산한다. 후진 범위는 기존 .2m 이하. 첫 동작 전에 전체 회전+후진 경로를 기존 check_grid로 검사하고 정지 유지 확인.
4. 기존 alignment_path는15° 한도이므로 약36°를 최대12°씩3구간으로 나눈다. 각 구간은 최신 자세·경로·AsyncClearance·저속 Spin을 사용하며 완료 후 정지 및 원점5mm/기존 정렬1° 기준을 확인한다. 기존40초 allowance, .03rad/s gate, 충돌/freshness 보호 유지.
5. 기존 retreat_plan/Retreat binding/Navigator(reverse=True)로 약6.1cm 후진. 기존 경로 이탈/측정속도 감시 유지. 최종 실제 정지 자세는5mm와 기존 작업 방향3° 조건을 확인한다. 구간별 계획/실행 분리, 이전 구간 실패 시 다음 구간 실행 없음.
6. 최종 최신 자세로 기존 work._plan_current를 통과해야 READY_FOR_WINDOW. 이 상태는 window 도착이 아니다. 이후 명시된 정상 HarvestTask가 실제 성공해야 remember_window로 기준을 저장한다.

취소는 runtime.lock 안에서 cancel 플래그와 stop_output(epoch)을 함께 변경한다. 최종 publish도 같은 lock 안에서 정확한 토큰/취소를 재검사하므로 늦은 결과가 다시 비영 출력하지 못한다. steps.stop의 자기 Action terminal 확인과 MotionMonitor 정지 확인을 모두 마친 뒤에만 소유권 반납. 취소/정지 미확인 시 STOP_UNCONFIRMED, node.busy/blocked 및 소유 토큰 유지. 같은 stop 서비스로 자기 Action 정리만 재확인할 수 있고 자동 이동 재시도는 없다.

## 검증과 한계

- 최종 pytest87개 통과: 신규23개+기존 인계64개. 초기 신규 시험1개는 가짜 runtime fixture에 heading 설정이 빠져 실패했고 fixture를 채운 뒤 통과. 최초 실패 로그 보존. 실제 제품 코드를 시험에 맞춰 보호 완화하지 않음.
- 실제 runtime 메서드 기반 출력 회귀22개 통과: cancel/epoch/owner·세션 변경, 낡은 입력·형상/frame, 스레드 정지, 복구 토큰 교체, 기존 단계 identity 보호 포함.
- 저장된 실제 costmap/footprint/동일 시각 TF 자료로 새 전체 경로 preflight 직접 호출 통과. 실시간 이동 안전 판정이 아닌 보존 snapshot 오프라인 검사.
- 로봇 격리 colcon build 성공. 격리 install의 node/runtime/recovery 해시가 후보와 동일. 실제 운영 변경 대상은 모두 before 해시 유지, 운영 PID85474 유지 확인. 기존 lock state/계층 변경 없음.
- ROS/DDS 서비스 통합, 실제 Spin/FollowPath 지연·추종, 완전한 복구/인계는 미검증이다. fixture 기반 소유권 시험과 실제 executor 시험을 혼동하지 않는다.
- align 단계의 기존 identity 차단은 유지한다. 고빈도 입력 갱신 중 출력 승인 고갈이나 clearance 재검사 대기로 정지할 가능성이 남는다. 이 후보가 그 문제까지 해결했다고 주장하지 않는다. window 접근 조건은 끝난 뒤 실제 자세로 검사하며, 오차가 크면 READY_FOR_WINDOW를 보고하지 않는다.

## 적용 및 원복 경계

현재 별도 /home/vic/Downloads/handoff_input_trace_20261023/recovery_connection_v1 및 PC runs/handoff_diagnostics/20261023_review/recovery_connection_v1에만 존재한다. 운영 소스·설치본·프로세스 재시작·이동 요청 없음. 실제 적용은 기존 source/install 백업과 before 해시 확인을 먼저 하고 새 계층 manifest로 관리해야 한다. 기존 lock state나 센서 commit deployment receipt를 덮어쓰지 않는다. 복구 입력 plan_file도 함께 보존하며 새 node 파라미터를 명시해야 활성화된다.

후속 적용/이동 전에 현재 자세·현장 공간·정지 대응을 확인하고 약12°×3 회전→약6.1cm 후진의 실제 순서를 안내한다. 그 뒤 정상 window 요청은 별도로 진행한다. 원복은 복구 노드 정상 종료/자기 Action 회수 확인 후 새 파일 제거, manifest의 두 기존 소스 원본 복원 및 재빌드다. 운영 미적용 상태에서는 실행본 원복이 필요 없다.

증거: manifest.json/change.patch/robot_source_before.tar.gz, regression.log/output_tests.log/build.log/captured_grid_check.log/preservation_check.json. Git commit/push 없음. device_services=NOT_TESTED: body-only scope.


## 사용자 스테이션 재배치 후 초기 정합 및 일반 재주행 — 2026-10-23 19:14 KST

승인: 사용자 기존 스테이션 위치/방향 재배치 확인 및 초기위치 설정·정합 확인 후 window 재주행 요청. 복구 연결 미적용 유지, 인계 전 별도 안내 조건.

- 운영 runtime SHA1006dc6cc452ac544e6480bc206b8b3e051fb64b3cf6493fc4c8442773b67790 확인. handoff_recovery.py 운영 경로 없음. 기존 sensor commit 적용본/PID85474 유지.
- AMCL active 확인 뒤 기존 /home/vic/Downloads/init_station_newmap.py 실행: initialpose(.104,-1.105,87.79°), request_nomotion_update5회. 초기 발행 직후 AMCL에는 약34ms 미래 extrapolation 경고와 Setting pose 기록이 함께 있었다. 이를 숨기지 않고 후속 센서 정합으로 확인했다.
- 정지 정합: map pose(.0951254059,-1.1131859674,1.5181745333rad). scan TF는 해당 scan stamp에 lookup 가능한 최신 표본 선택, age .3473s. laser_link의 전체 quaternion 회전을 적용한630개 유효 끝점과 지도 점유 셀 중심 거리 중앙값 .0106694m,90% .0214707m, 모두 .05m 이내. 지도/scan overlay 직접 시각 확인. odom299표본 비영0. 정지 정합 확인이지 실물 절대 위치 정답/모든 주행 안전 보장은 아니다.
- 별도 수집기 station-restart-l5haf42g PID98194 파일 생성/프로세스 확인 후, 로봇 로컬에서 관제 형식 HarvestTask1회 전송. PC 수신 문제는 해결 확인하지 않아 PC→Zenoh 관제 왕복 시험이라고 하지 않는다. 로봇 Zenoh ON.
- task STATION_4950c0f1b6a2_SEC01_TASK001, 목표(1.186,-.035,0). 수락 true, 19:14:36.908 일반 controller goal 시작,19:14:37.810 collision ahead,19:14:38.880 최종 status6/FAILED/NAVIGATION_FAILED/error106. window 미도착, 기준 미확보.
- 이번 bag의 ROS1792750475~0482: cmd_vel_normal/nav 각19표본 중18비영, v=0,w=.1rad/s. cmd_vel도 v=0. odom209표본 중87비영, |v|최대약.00384m/s, w최대.07086rad/s. 출발 직후 제자리 회전 구간에서 중단했다. 인계 controller/gate 실행 실패와 구분.
- 실패 순간 costmap_raw/published_footprint/received_global_plan/lookahead_collision_arc snapshot과 원시 속도 확보. 충돌 원인/실물 장애물/잔상 여부는 아직 미확정. 안전 설정·costmap clearing·초기위치 재발행·반복 이동은 하지 않았다.
- 종료 후 status IDLE/ready, pose(.095124651,-1.113059393,1.52702855rad), odom 모든 성분0. 현장 실제 정지 확인을 별도로 요청했다. bag SIGINT 정상 마감 및 metadata 생성 확인. enter/restore/복구 start 미호출, 팔 미시험.

자료: 로봇 runs/handoff_diagnostics/station-restart-l5haf42g의 bag/alignment.json/action.log/final_status.yaml/final_odom.txt/failure_excerpt.json. PC runs/handoff_diagnostics/20261023_review/station_restart에 정합 JSON/PNG 및 결과·실패 발췌 보존. 정합 읽기 도구 robot/tools/transfer/handoff_diagnostics/check_station_alignment.py 추가(이동/서비스 호출 없음). 다음은 이번 실패 순간 예측 회전 footprint와 costmap의 충돌 판정 대조이며 자동 재주행하지 않는다. Git commit/push 없음.


## 수동 재배치 뒤 costmap 잔존 정보 비교 — 2026-10-23 19:21 KST

사용자 “costmap 초기화 해야할수도? 비상정지 눌러서 옮기면 꼭 꼬이던데” 제안에 따라 원본을 보존하고 무이동 비교. 초기위치 재발행/재주행/인계 호출 없음.

- 실패 당시 footprint(0.64×0.54m)와 costmap의 사각 셀 겹침을 계산. odom(-.73000006,-.69000006) 장애물 셀은 실패 당시 현재 자세에서는약.0292m 떨어져 있으나 반시계+.1rad 예측 회전에서는 차체와 겹침. 이는 controller가 보고한 정확한 내부 셀 ID는 아니며 기록된 지도에서 독립 재현한 충돌 셀이다.
- 동일 실패 구간 bag의 laser_link→odom TF를 scan stamp1792750477.6350312에 조회하고3차원 quaternion으로 반사점을 변환. 해당 셀에서 가장 가까운 반사점은 .2257303m 떨어짐. 단일 scan만으로 가려진 장애물까지 배제하지 않았다.
- 서비스 실제 존재/타입 확인: /harvest_01/local_costmap/clear_entirely_local_costmap, nav2_msgs/srv/ClearEntireCostmap. IDLE/ready, 최신 odom1초간10개 이상 모두0, 최신 costmap 확인 후 before JSON 저장. 사용자에게 먼저 무이동 초기화 비교를 알리고 해당 일반 local costmap만1회 초기화. handoff/global costmap은 초기화하지 않음.
- 응답 확인 후6초간 센서 갱신을 기다리고 정지/IDLE/신선도를 다시 확인. 문제 셀254→253(완전한 빈 셀0이 아님), 전체 lethal/unknown1236→449. 253은 주변 안전 여유 영역이며 자체 장애물 셀과 구분한다.
- 동일한 실패 당시 차체 자세 및 +.1rad 회전 경로를 두 지도에 check_grid로 비교: 초기화 전 footprint 충돌, 초기화 후 통과(보수적 여유 하한 .168243m). 실시간 주행 성공 또는 전체 경로 안전 검증으로 확대하지 않는다.
- 실제 odom·status 위치는 정지 유지. status pose(.095131389,-1.112869678,1.52850422rad). 이번 근거는 local costmap 잔존 정보가 중단에 영향을 주었음을 지지한다. 비상정지 동작 자체/수동 운반 중 odom/TF 처리의 정확한 인과관계는 미확정.
- 앞선 “초기위치 재발행보다 충돌 셀 확인” 판단에 더해, 수동 재배치 후 local costmap의 정지 재생성 비교가 필요한 상황임을 확인했다. 매 실패마다 무조건 초기화하거나 충돌 조건을 낮추는 정책을 만들지 않는다.

PC 근거: station_restart/{rotation_cells.json,cell_scan_comparison.json,costmap_before_clear.json,costmap_after_clear.json,clear_receipt.json,clear_comparison.json,clear_rotation_check.json}. 로봇 동일 trial 폴더 원본 보존. 무이동 비교기 Downloads/handoff_input_trace_20261023/compare_local_costmap_clear.py. 다음 주행은 별도 안내 후에만 진행. 운영 코드/안전 설정 변경 없음, 복구 후보 미적용, 인계 미완료. commit/push 없음.


### 2026-10-23 19:29 costmap 초기화 후 window 재주행 성공
사용자 현재 위치에서 window 재주행 승인, 인계 전 안내 조건. 기존 PID85474/Zenoh 실행을 유지하고 초기위치 재발행·추가 costmap 초기화·설정 변경 없이 로봇 로컬 HarvestTask 1회 전송. PC→Zenoh 왕복 검증은 아님.
출발 scan/map 중앙 오차 .01048m, p90 .02143m. 10초 odom300개 중7개 비영이 있어 최신1초 정지를 별도로 재확인한 뒤 요청했다. task CLEAR_6b7a8172c80a_SEC01_TASK001은 19:27:44 수락 후 19:28:47 최종 status4/SUCCESS, error NONE. 출발 회전과 코너를 지나 window 도착. 19:29:22 확인 pose=(1.158050282,-.031138038), yaw=.01862555rad; 목표 위치오차 .02821527m, 방향오차 약1.067도. IDLE/ready=true, 최근 odom30표본 모두0. body status IDLE, enter/restore 미호출. device_services=NOT_TESTED: body-only scope, harvested_count=0.
이번 결과는 일반 local costmap 초기화 후 정상 주행 복구의 실기 근거이며 비상정지 자체의 인과관계 및 인계 전체 성공을 뜻하지 않는다. 복구 연결 후보 미적용, 운영 코드·안전 설정 변경 없음. 로봇 runs/handoff_diagnostics/window-after-clear-7I6u91LY에 bag(metadata 정상 생성)/action.log/goal.json/precheck.json/alignment.json/final.json 보존. PC runs/handoff_diagnostics/20261023_review/window_after_clear에 주요 결과 복사. 현재 window이므로 스테이션 초기좌표 재발행 금지. 인계 시험은 아직 시작하지 않음. 기존 미커밋 기준 HEAD4b5c5b1 유지, commit/push 없음.


## 2026-10-23 19:31~19:33 차체 인계 실기 — 진입 성공, 복귀 정렬 완료검사 실패

사용자 window 위치 유지/이동 가능 및 인계 시험·로그 수집 승인. 실행 runtime SHA1006dc6cc452ac544e6480bc206b8b3e051fb64b3cf6493fc4c8442773b67790, PID85474 및 Zenoh PID51880 유지. source/install 변경·재시작·초기위치 재발행·추가 costmap 초기화 없음. 회복 연결 후보 미적용, 기존 보호/허용치 유지. PC Git HEAD4b5c5b1 및 기존 미커밋 작업 기준, commit/push 없음.

실행: 정지/현재 window 자세 확인 후 enter 1회. build_body .02044초, capture .83010초. 19:31:51.851 departure goal→19:32:06.403 goal 완료, 19:32:08.248 wall goal→19:32:20.849 완료. 19:32:21.725 enter 실행 반환, status ENTERED. 직후 odom 일부 비영 표본으로 바로 복귀하지 않고 정지를 별도 재확인했다. 19:32:46 최신31표본0 확인 후 사용자에게 복귀 진행 안내.

restore 1회: 19:33:03.705 retreat goal→19:33:16.006 완료. align 계획19:33:17.019 시작, guard 약3.213초. 19:33:20.242 Spin 시작(로그 Turning0.05),19:33:22.493 Spin 성공. 정지 후 check_reentry에서19:33:24.519 RECOVERY_REQUIRED/복귀 원호 재진입 위치·방향 오차 초과. plan:return 기록 없음, 전진 복귀 원호 및 최종 window 보정은 시작되지 않음. 단순 Spin 성공을 정렬 완료로 간주하지 않는다.

최종 pose map=(1.059564070,-.124539700),yaw1.648617895rad. 최신 odom30표본0, 사용자 현장 정지 확인. ERROR/ready=false/CANCEL_UNCONFIRMED는 노드 blocked 상태의 일반 보고이며 이번 detail에는 정지 미확인 부가 오류가 없다. 실제 정지 확인과 복구 필요 상태를 구분한다. 이후 enter/restore/초기위치/추가 이동 없음.

### 원인 대조 및 한계
- 이번은 과거 곡선 속도 입력 시간 초과 재발이 아니다. departure+wall+retreat 제어기 goal 완료, raw_nav/raw_spin/cmd_vel_nav/cmd_vel 기록 확보. 센서 commit 수정 후 진입 성공을 직접 확인했지만 전체 시퀀스 해결 완료는 아니다.
- transfer_restore.check_reentry는 위치8mm 또는 방향1도 중 하나라도 초과하면 같은 오류를 낸다. handoff_planning의 align 완료검사에서 호출되며 return 계획 전에도 호출된다. 이번은 align 이후 검사에서 실패했다.
- 정확한 실행 객체 RestoreReference는 외부 로그에 기록되지 않아, capture 완료 시각 근처 odom13표본(모두 같은 자세)와 기존 arc_pose 수식으로 재구성했다. 원호 끝점 odom=(.075316506,-1.960896515,.096602512rad). Spin 직전 위치오차6.0558mm, 실패 시각 근처8.7717mm; 방향오차.0123019rad(약.705도). 위치 조건 초과를 지지하며 exact validator 입력 재현이라고 주장하지 않는다. Spin 전후 odom 위치 약2.72mm 변동. 실제 차체 평행 이동인지 odometry 오차/정지 표본 선택 영향인지는 미확정.
- raw_spin45비영 명령 중 해당 시간 cmd_vel_nav37개(둘 다 .03rad/s), 최종 cmd_vel43개. 단계 간 소유권/정지/센서 갱신 차단을 포함할 수 있으므로 이 개수 차이만으로 실패 원인을 단정하지 않는다.
- 실행 구간 외부 odom header age최대.18356초/gap.29847초, 내부 callback odom age최대.17128초/gap.51194초. 내부 지연이 완전히 사라졌다고 하지 않는다. 이번 기록에는 odom 만료/곡선 입력 시간초과로 종료하지 않았다. TF 외부 odom/base age최대.08664초. 단일 시험의 최대값이며 다른 부하로 일반화하지 않는다.

### 자료 및 다음 범위
로봇 runs/handoff_diagnostics/body-after-clear-wgzBn9kr: bag(metadata 정상 마감), 외부 observer, enter/restore 상태, raw 속도, scan/costmap/TF, 해당 구간 내부 trace/harvest.log, bag_analysis/motion_samples 보존. PC runs/handoff_diagnostics/20261023_review/body_after_clear에 주요 결과 및 reentry_reconstruction.json/timing_summary.json 저장. 실행 도구는 해당 시험 폴더에만 있으며 서비스 이동은 각1회, status는 읽기 호출이다. recorder/observer는 해당 PID 확인 후 SIGINT 마감. 운영 계측은 그대로 유지.

다음은 이탈 끝점의 정지 오차와 Spin 중 위치 변화, 정지 시각/TF 표본 선택을 대조하여 8mm 계약을 만족시키는 방식 검토다. 허용치 완화·추측 수정·자동 재시험은 하지 않았다. 인계 전체 완료 아님. device_services=NOT_TESTED: body-only scope, 팔/배출 미시험.


## 2026-10-23 복귀 재진입 정책 분리 후보 및 오프라인 검증

승인: 사용자 재진입10mm 별도 설정 방향 수정·오프라인 검증, 기존 핫픽스/안전 보호 및 다음 단계 조건 확인 요청. 실기 이동 전 안내. 이번 작업은 현장 최신본을 백업한 격리 후보에서 수행했다. 운영 소스·설치본·PID85474 변경/재시작/이동 없음. PC 기존 미커밋 운영 트리는 덮어쓰지 않음. Git HEAD4b5c5b1, commit/push 없음.

| 후보 변경 파일(harvest_robot 및 Vic Pinky 시험 설정) | 변경 이유와 내용 |
| --- | --- |
| transfer_restore.py | check_reentry의 위치 한계를 독립 인자로 받음. 미지정 시 기존 ArcSpec.endpoint_tolerance 유지. 실행 중 deviation보다 큰 한계 거부. 실패 시 실제 위치/방향 오차와 한계 수치를 출력. |
| handoff_planning.py | CompletionPolicy.reentry_position 선택형 추가(None 기본). align 계획·완료 및 return 진입에 같은 선택값 적용. return 계획에서 기존 check_motion도 미리 검사. 제어기 원호는 그대로 유지하고 현재 자세→원호 시작점 구간을 guard 충돌 경로에 추가. |
| handoff_runtime.py | 설정의 completion을 구성 시 로드·검증하고 planner에 전달. 센서 commit/epoch/취소/정지/출력 소유권 메서드 변경 없음. |
| robot/config/robots/vicpinky/transfer/handoff_body_trial.json | 이 차체 시험에만 completion.reentry_position=.010m 명시. 원래 arc.endpoint_tolerance=.008m 그대로 유지. |

### 유지한 조건과 다음 단계 대조
- 설정 미선택 사용처는 자체 ArcSpec 끝점 허용치를 그대로 사용한다(다른 ArcSpec의6mm도 보존 검사). 공통 farm_navigation/farm_common 및 controller C++ 소스/서버 목록 변경 없음.
- 정지 판정, 방향 재진입1도, 회전 중 평행이동5mm, 측정속도·freshness·소유권·취소·epoch 보호 유지. 후진 이탈/출발 곡선 끝점8mm 유지. 복귀 곡선 종료8mm/방향3도 및 최종 map window2cm/3도 유지.
- 실제 원호 제어기는 전체 경로가 원형인지 검증한다. 현재 자세를 원호 경로에 추가하면 계약이 깨지므로 제어기 route는 기존 역순 원호 그대로. 현재 자세부터 시작점의 틈은 check_grid에 별도 포함한다. 이 검사는 틈 구간의 보수적 형상 검사이며 실제 추종 궤적과 같다고 주장하지 않는다. 실제 제어기는 예측 footprint 충돌 검사를 계속 수행한다.
- 재진입 위치10mm 이내라도 방향에 따른 곡선 이탈이10mm를 넘으면 기존 check_motion으로 거절한다. 재진입 허용과 실제 추종 가능성은 별개이며 이 거절은 유지한다.
- window 보정은 기존 짧은 전진(.003~.06m), 횡오차≤.015m, 진행 중 횡이탈5mm 및 TF변화5mm/1도 조건을 그대로 유지한다. align/window의 센서 identity 보호 및 지연 가능성도 이번 후보에서 변경하지 않는다.

### 검증 결과
- PC/로봇 최종 pytest 각각82개 PASS: 신규18개+기존 인계64개. 기존 unittest 클래스를 새 파일에 import해11개 중복 수집하던 것을 모듈 import로 바꿔 최종 수치를 중복 없이 집계했다.
- 신규 검사: 이번8.77mm 표본 align 완료→return 계획/monitor/명시적 Path 생성 통과,10mm 초과/1도 초과/별도 경로 이탈 거절, 기존 기본값/종료8mm 보존, 취소/다른window·세션/센서 만료/충돌 실패, 회전5mm 보호, 실제 보존 costmap의 전체 복귀 경로 및 footprint 내부 장애물 주입 차단.
- 기존 실제 runtime 메서드 스레드 주입 출력 회귀20개 PC/로봇 PASS. 정상 odom 갱신 승인, cancel/epoch/owner/정지 후 늦은 비영 출력 금지, 오래된 입력/잘못된 frame·형상 거절, 다른 단계 identity 보호, 무명령 timeout 유지.
- 초기 신규 시험1개는 경로 이탈을 만들려는 fixture 오프셋 방향을 반대로 넣어 실패했다. 제품 안전조건 변경 없이 fixture 방향만 수정. 초기 통합 회귀1개는 격리 폴더에 shared_nav2 원본이 빠져 실패하여 로봇 원본을 읽기 복사한 뒤 통과. 최초 로그 보존, 전체 초회 통과라고 하지 않는다.
- 기존 C++ ArcController의 실제 header validate_path/command를 컴파일해 기록된 실패 자세에서 이상 운동 모델(dt=.01s)로 복귀시켰다.14.55초에 기존 goal 기준 도달. 실물/ROS 제어기 실행 검증은 아니다. Python 기존 감시로1,455표본 검사: 최대 곡선이탈9.5464mm, 종료 직전 위치4.1673mm/방향2.332도. 최종 DONE 표본은 위치4.0673mm/방향2.275도. 예측 실제 모터 오차를 보장하지 않는다.
- 같은 이상 궤적과 실기 보존 costmap의 check_grid 통과(보수적 여유 하한6.62mm). 정적 snapshot 결과이며 현재/미래 장애물 안전 보장 아님. map/odom 불변 가정에서 다음 window 전진 보정 경로도 계산 가능(약3.18cm). 실제 TF변화/구동 편차/정지 오차는 미검증.
- 최대 경로 이탈이10mm 한계에 약.454mm 여유만 남으므로 실물 성공을 단정할 수 없다. 기록 표본 자체가 통과하더라도 다른10mm 영역 자세는 기존 제어기/monitor에서 거절될 수 있다. 보호를 더 완화하지 않았다.
- 로봇 후보 전용 colcon build/install 성공, 수정 Python3개 설치본 바이트 일치. 운영152파일 원본 백업과 모두 일치, lock state 및 fixed_trace_v3 manifest 기존 해시 일치. 운영 runtime SHA1006dc6cc452ac544e6480bc206b8b3e051fb64b3cf6493fc4c8442773b67790 유지.

### 산출물·적용 및 원복 경계
PC runs/handoff_diagnostics/20261023_review/reentry_policy_v1, 로봇 /home/vic/Downloads/handoff_input_trace_20261023/reentry_policy_v1. robot_source_before.tar.gz/test_config_before.tar.gz 원본, project 후보, manifest.json(4파일 before/after), change.patch, tests_initial/regression/최종 회귀·출력 로그, controller_simulation.log/following_stages.json, 보존 검사/격리 build.log.
운영 미적용이므로 현재 원복 작업은 필요 없다. 다음 적용 시 manifest before 해시와 기존 layer 상태를 확인하고 실제 운영 설치본을 새로 백업한 뒤 별도 적용 계층으로 관리한다. 기존 lock/trace/sensor_commit manifest를 수정하지 않는다. 적용 후 원복은 새 계층 백업으로만 수행하며 기존 핫픽스를 과거 ZIP으로 덮어쓰지 않는다.
현재 로봇은 앞선 인계 복귀 실패 정지 위치/RECOVERY_REQUIRED이며, 이번 후보 작성은 이를 해제하지 않는다. 실기 준비·위치·진입 기준 확인 없이 enter/restore를 다시 요청하지 않는다. 실기 이동 전 사용자에게 안내한다. 전체 인계 성공/팔 시험 완료 아님. device_services=NOT_TESTED: body-only scope.


## 2026-10-23 19:55 재진입 정책 운영 적용 — 수확 노드 종료/스테이션 재배치 대기

사용자 승인: 기존 핫픽스 백업 유지하면서 실행본 적용·재시작 준비, 스테이션으로 옮겨도 되는 시점 안내. 초기위치/이동/재기동은 이번 단계에서 수행하지 않았다.

- 사전 body RECOVERY_REQUIRED/재진입 위치·방향 오차, map=(1.059535466,-.124161119),yaw1.646256824. 최신 odom31표본0 확인.
- reentry_policy_v1 manifest의4파일 before 해시가 현장과 일치하고 후보 after 해시가 맞는지 확인. source_before.tar.gz(4원본), install_before.tar.gz(운영 harvest 설치 전체), 기존 lock/trace/sensor_commit 계층 기록을 새 deployment에 백업했다. 이전 백업/manifest/state는 수정하지 않았다.
- 기존 PID85474의 실행 argv·허용목록 환경·params를 새 deployment/launch.json(mode0600) 및 params_5.yaml에 보존. launch.json은 PC 복사/본문 출력하지 않았다.
- SIGTERM 정상 종료를 확인한 뒤4파일 적용, 실제 ROS workspace에서 harvest_robot 빌드 성공. 수정Python3파일 source/install 해시가 후보와 일치하고 JSON의10mm 설정 반영 확인. 다른 핫픽스 계층 state 해시는 그대로다.
- 종료 후 odom31표본0, cmd_vel_nav publisher0. 이번 사용한 general follow_path/handoff follow_path/handoff spin 상태 모두 terminal4. 다른 발견된 action status는 표본이 없었으므로 전체 ROS Action 부재를 과장하지 않는다. 기존 launch51464와 Zenoh51880 유지. 드라이버/AMCL/Nav2는 재시작하지 않았다.
- 수확 노드를 아직 재기동하지 않았다. restart_harvest.py는 원본·설치본·기존 계층 해시와 동일 실행 경로 중복 프로세스를 검사한 뒤 --start가 있어야 시작한다. 이번에는 기본 CHECK_ONLY_OK만 수행. 다음에는 사용자 스테이션 재배치 확인 후 기동 및 ROS 상태/출력 소유권을 별도 검증해야 한다.
- 사용자에게 비상정지를 유지한 상태로 기존 스테이션 위치/방향으로 옮겨도 되는 시점임을 안내했다. 현 위치에 스테이션 initialpose를 보내지 않았다. 재배치 확인 후 수확 노드 재기동→초기위치 설정→지도/scan 정합→필요 시 costmap 정지 초기화/재생성→window 재주행 기준 확보→인계 전 안내 순서를 따른다. 재시작으로 window 기준이 소실되므로 ready만으로 인계 준비 완료라 하지 않는다.
- 현재 코드 적용 완료, 실행 프로세스는 없음. 로봇 움직임·실기 개선 검증·팔 시험은 미실행. Git commit/push 없음.

백업/재시작 자료: 로봇 /home/vic/Downloads/handoff_input_trace_20261023/reentry_policy_v1/deployment. PC runs/handoff_diagnostics/20261023_review/reentry_policy_v1/deployment에 receipt/verification/precheck/build/source백업/restart도구 보존. 설치 전체백업과 환경은 로봇에만 보존. receipt의 phase=installed_verified_await_station_relocation.
원복은 수확 실행 부재/정지 확인 후 receipt after 해시 확인, 새 source_before 원본4파일 복원 및 harvest 재빌드다. 설치 전체백업도 보존. 기존 sensor_commit 및 그 이전 계층을 직접 롤백하지 않는다.


## 2026-10-23 21:05 스테이션 재배치 후 재기동·정합·costmap 무이동 확인

사용자 기존 스테이션 위치/방향 재배치 확인 및 재기동·초기위치·정합/costmap 검사 승인, 이동 전 안내 조건.
- restart_harvest.py --start의 소스/설치/기존 layer 해시·중복 프로세스 검사를 통과하여 수확 PID129702로 단독 재기동. 기존 launch51464/Zenoh51880 유지. 수정 completion 설정이 포함된 운영 handoff_body_trial.json을 params_5.yaml의 handoff_config로 읽는 실행 경로 확인. 전용 TF node/executor·새 deployment trace 기동 로그 확인.
- 기존 init_station_newmap.py로 AMCL active 확인 후 (.104,-1.105,87.79도) initialpose 및 nomotion_update 요청. source 파일/안전값 변경 없음.
- 정지 scan/map 검사: pose=(.089215195,-1.132036579),yaw1.534575574rad. scan627표본, age .32999초, 지도 점유 셀 중심 거리 중앙 .006003m/p90 .021687m, 5cm 이내99.52%,10cm 이내100%. odom300표본 비영0. 저장 overlay 그림도 직접 확인. 상단 벽 일부 편차가 있으며 실물 절대위치 정답/전체 주행 안전 검증은 아님.
- 별도 최신1초 odom31표본0. 일반/인계 local costmap 최신성·odom frame·발행 footprint(.64x.54) 형상 확인. 현재 차체와 +.1rad 소회전 경로 check_grid 모두 통과, 보수적 여유 하한 각각 .18896m/.17829m. 일반 lethal1144/인계1297, unknown0. 장애물 셀 개수만으로 잔상 판정하지 않았다. 현재 차체 부근 검사에 문제가 없어 이번에는 costmap clear를 호출하지 않았다. 전체 window 경로/동적 장애물 미검증.
- cmd_vel_nav publisher1=harvest_motion_server, odom publisher1=vic_pinky_bringup. RobotStatus IDLE/ready=true, body IDLE, 새 boot_id efbf6db9bc734c078f6ee4e2e8e391bc. 새 window 도착 기준은 아직 없음. ready는 비상정지 해제/실기 이동 준비까지 보장하지 않는다.
- 기동 직후 과거 TF extrapolation 계측1회, 이후 age .03~.05초 회복 확인. STATION_RETURN_NOT_CONFIGURED는 기존 유지. BATTERY_UNAVAILABLE/0값을 실제 잔량0%로 해석하지 않음.
- enter/restore/HarvestTask/복구 서비스 호출 및 cmd_vel 직접 발행 없음. 수확 노드만 재기동했으며 초기위치 설정 외 이동은 없음. 팔 미시험/전체 인계 미완료, commit/push 없음.
자료: reentry_policy_v1/deployment/{initialpose.log,station_alignment.json/png,station_checks.json,general_costmap_before.json,handoff_costmap_before.json,각footprint.json,harvest.log,trace/}. PC에 정합/검사/초기위치 로그 보존. 다음 window 재주행은 사용자에게 알린 뒤 시작하며 이후 실제 window 도착으로 인계 기준을 재확보한다. 재기동된 PID129702는 원래 launch 자식이 아니므로 전체 종료 시 별도 정상 종료 확인 필요.


## 2026-10-23 21:11 재진입 정책 적용 후 window 재주행 성공
사용자 위치 유지/이동 가능 및 window 재주행·로그 수집 승인, 인계 전 안내 조건. source/install 변경 없이 PID129702/Zenoh51880 유지. 시작 pose(.089215195,-1.132036579,1.534575574) 및 최신 odom 정지/IDLE/단일 cmd_vel_nav publisher 확인 후 단발 HarvestTask 요청. task REENTRY_6107aba0733e_SEC01_TASK001/window REENTRY_6107aba0733e_SEC01_W001, goal(1.186,-.035,0). 로봇 로컬에서 관제 메시지 형식 전송이며 PC→Zenoh 왕복 검증은 아님.
21:10:02 수락/피드백 후 코너 통과,21:11:04 최종 status4/SUCCESS/error NONE. harvested_count0은 ARRIVAL_ONLY_NO_HARVEST 정책의 결과이며 팔 시험 아님.21:11:36 pose=(1.156698884,-.037115190),yaw=-.007666990rad, 목표 위치오차 .02937736m/방향 약.439도. IDLE/ready=true, 최근 odom31표본0, body status IDLE. enter/restore는 미요청. 초기위치 재발행/costmap 초기화/안전조건 변경 없음.
로봇 runs/handoff_diagnostics/window-reentry-policy-phpV40RJ에 bag(정상 metadata 마감),외부 odom/TF observer 및 해당 구간 내부 trace/harvest.log,goal/action/final/precheck 보존. 이번 수집기만 PID·cmdline 확인 후 SIGINT 종료. PC runs/handoff_diagnostics/20261023_review/window_reentry_policy에 주요 결과·외부 관측 복사. 현재 window 정지 위치를 유지하고 스테이션 초기좌표를 보내면 안 된다. 다음 인계는 사용자에게 알린 뒤 시행. 이번 성공은 일반 주행 결과이며 수정10mm 재진입의 실기 검증은 아직 아님. Git commit/push 없음.


## 2026-10-23 21:15 수정 재진입 정책으로 전체 차체 인계 완료(1회 실기)

사용자 window 위치 유지/이동 가능, 인계·복귀 완료 확인 및 로그 수집 승인. PID129702, Zenoh51880 유지. 운영 source/install3파일과 후보 manifest after 해시, body_trial completion.reentry_position=.010m 확인. 이번 시험 중 코드·설정·costmap/초기위치 변경 없음. enter1회/restore1회, 상태 조회 외 이동 요청 없음.

### 직접 확인한 단계
- 21:13:35.928 enter 작업 시작, build_body .01442초/capture .80720초. 후진 곡선 goal 21:13:37.353→21:13:51.953 완료. 벽 정렬 goal21:13:53.769→21:14:08.370 완료.21:14:09.227 enter 반환, status ENTERED.
- 완료 직후 odom 비영 표본이 일부 남아 바로 복귀하지 않았다. 별도 status 검사에서 최근31표본0 확인 후 복귀를 안내했다.
- 21:14:49.050 restore 시작. 후진 이탈 goal21:14:49.500→21:15:03.401 완료. Spin21:15:05.022(Turning0.03)→21:15:06.473 성공. 재진입 검사 통과 후 return 계획/guard 통과, 전진 복귀 goal21:15:08.219→21:15:21.271 완료.
- 21:15:22.394 window 계획/최종 도착 검증 단계 실행,21:15:25.150 BODY_TRIAL COMPLETED/detail빈문자/arm_tested=false. 별도 window FollowPath goal 및 그 이후 비영 속도가 없으므로, 추가 직선 보정 이동을 수행했다고 표현하지 않는다. 기존 범위 안에서 최종 window 도착 검증을 통과한 결과다. 앞선 진행 설명의 “최종 window 보정”은 이 검증 단계를 포함한 표현이며 실제 추가 이동과 구분한다.
- 완료 직후 odom 일부 비영 표본으로 별도 정지 조회.21:15:54 최종 COMPLETED, IDLE/ready, 최근30표본0. map=(1.184048071,-.028186434),yaw=-.002233613rad. 관제 goal(1.186,-.035,0) 대비 위치7.08765mm/방향.12798도, 저장 출발 방향 대비 약.31131도. 일반 상태 battery0은 기존 BATTERY_UNAVAILABLE 자리값.

### 수정 효과와 한계
- Zenoh ON에서 window 도착 기반 후진 곡선·벽 정렬·후진 이탈·방향 조정·전진 원호 복귀·최종 window 검증 전체를 이번 직접 실기1회 완료했다. 이전 baseline15:47/fixed15:52 및18:00/19:33 실패와 구분한다.
- 적용된 재진입 위치 설정은10mm지만, bag의 capture 근처 정지 odom과 return 계획 근처 odom으로 재구성한 이번 오차는 위치6.07779mm/방향.00315275rad(약.18064도)다. 실행 객체 정확한 reference 미노출 한계가 있으며 이 표본은 기존8mm 안쪽이다. 따라서 전체 수정본 실기 성공은 확인됐으나10mm 완화가 이번 성공의 직접 원인이라고 단정하지 않는다.8~10mm 재진입 구간의 실기 통과는 아직 미검증이고 이전 기록에 대한 오프라인 검증만 있다.
- raw_nav/raw_spin/cmd_vel_nav/cmd_vel·odom/TF/costmap/footprint/scan 동시 bag 및 내부 trace, 외부 수신 기록 확보. raw_spin29비영, raw_nav1048비영, 최종 cmd_vel1080비영. 속도 입력 timeout/재진입 오류로 종료하지 않았다. 부하·여러 출발 오차의 반복 신뢰성은 이번1회로 보장하지 않는다.
- 팔/배출/장치 서비스는 NOT_TESTED: body-only scope. 관제 window 목표는 실제로 사용했으나 요청은 로봇 로컬 관제 형식이며 PC→Zenoh 왕복 재검증은 이번 범위가 아니다. 다른 로봇 실기/시뮬 전체 검증도 하지 않았다.

### 자료와 현재 상태
로봇 runs/handoff_diagnostics/body-reentry-policy-nVLFxOy9: manifest/config/window_arrival/enter·restore·status 로그, bag(metadata 정상 마감), 외부 observer, 해당 구간 내부 trace/harvest.log, bag_summary.json. 수집기 PID133470/133486은 cmdline 확인 후 SIGINT 정상 마감. 운영 node/Zenoh는 유지.
PC runs/handoff_diagnostics/20261023_review/body_reentry_policy에 주요 원본·stages.json·timing_summary.json·RESULT_NOTE.md 보존. 현재 window 부근 정지, body COMPLETED. BodyTrial은 현재 API상 phase IDLE만 enter 허용하므로 완료 후 자동 반복 요청하지 않는다. 추가 이동/초기위치/reset 요청 없음. 기존 백업·핫픽스·운영 보호 유지. 문서에 이번 최초 전체 차체 성공과 미검증 범위를 반영, Git commit/push 없음.


### 2026-10-23 21:31 인계 후 그래프14 일반 주행 연속 시험 성공
사용자 요청으로 관제 웹을 직접 조회: #59/25fabab7b348_SEC01_TASK001(표시 목표1.601,-.035)은21:25:15 대기열 등록 후 Action 전송 전. 수확 Action 서버 대기, 인계 수확Status는18:38:38의 이전boot ERROR/CANCEL_UNCONFIRMED에 정체되어 최신 로봇IDLE/ready와 불일치. 지도 위치 수신은 최신이었다. 근본 통신 원인 미확정. 이후 화면에서 해당 작업의 전송 전 취소 및 수확 대기열 일시정지 확인(에이전트가 취소 버튼을 누르지 않음).
사용자 “일단14번 노드로” 승인으로 실제 graph.geojson 노드14=(3.576,-.035) 읽고 yaw0, expected_count0 시험 HarvestTask NODE14_79189ba30dfe_TASK001을 로봇 로컬에서1회 요청. 현재 위치·정지 확인 및 경로 안내 후21:30:03 수락→21:30:43 status4/SUCCESS. 실제 SECTION_RESUME→WINDOW_MOVE→ARRIVED, 현 위치에서 목표까지2.392278m 직선 FollowPath(reverse=false, graph edge_ids=[]); 그래프 전체 경로 추종 시험으로 확대 해석하지 않는다. 도착 판정오차28.060mm/.5154도, 최종Status(3.550325,-.023535),yaw-.009290;21:31 IDLE/ready 및 최근odom30표본 전부0. PID129702/Zenoh 유지, 재시작·초기위치·코드/안전설정 변경·추가 인계 없음.
새 시험 goal의 arrival와SUCCESS 이벤트를 확인. 현재 communication.py의 remember_window→handle.succeed 순서에 근거하여 새 기준 저장 경로 완료를 판단했으며 메모리를 직접 조회한 것은 아니다. body-only 팔 NOT_TESTED. 인계 완료→일반 주행 전환1회는 실기 확인했으나 관제 웹 다음 실제window 전달은 미완료이며 후속 인계 반복 검증도 별도다.
로그: 로봇 runs/handoff_diagnostics/web-next-window-AiZhUerb (bag 정상 마감, 외부 계측), 하위node14/goal.json,action.log,final.json; PC runs/handoff_diagnostics/20261023_review/web_next_window에 웹 관측과 단발 결과 보존. 기존 핫픽스/백업 보존, 문서만 추가, commit/push 없음. 원복할 운영 변경 없음.


## 2026-10-23 커밋 후 운영 인계 통신 연동 사전 분석

기준 cf870daa00e7b752a39bbb3c84fc61c412cb2de7. 사용자 요청은 분석/가능성 판단이며 운영 코드·설정·프로세스 수정 및 실기 전송 없음.

### 결론과 현재 경로
연동 가능. TransferCommunication(mode=components) → TransferMission → ComponentTransferDevices → HandoffRuntime.build_body → 검증된 HarvestHandoffMotion을 재사용할 연결부가 이미 존재한다. BodyTrial Trigger를 관제에서 대신 호출하는 방식은 ID/허가/Result 계약을 우회하므로 운영 연결로 채택하지 않는다.
현재 로봇 파라미터 직접 조회: handoff_config=handoff_body_trial.json, transfer_rotation_mode=components, transfer_device_services={}, handoff_body_trial_enabled=true, transfer_discharge_mode=device_services. 운영 DockTransfer는 node.body_trial이 있으면 무조건 거절한다. body_trial_enabled 파라미터는 선언하지만 생성 분기는 config trial_enabled를 사용하므로 ros2 param set만으로 운영 전환되지 않는다.

| 통신/단계 | 실제 코드 연결 |
|---|---|
| DockTransfer 수락 | ID/중복/장치ready/window/소유권 검사 및 journal active 기록 |
| prepare_arm | 비차체 준비 완료 응답 후 build_body, 같은시각 map/odom 기준 연결 |
| rotate_to_transfer | body enter: 후진 곡선→벽 정렬→정지 |
| DOCK_READY Feedback | 진입 완료 후 발행, WAIT_DOCK_STABLE을 먼저 설정 |
| DOCK_STABLE Service | ID와 순서 검사 후 배출 요청, 접수와 완료 구분 |
| 배출 완료 | 기존 합의 Discharge Action의 동일transfer_id+SUCCEEDED+error_codes=[] 확인 |
| TRANSFER_COMPLETE Feedback | 배출·닫기 전체 성공 이후 발행 |
| TRANSPORT_CLEAR Service | 허가 후 restore_devices 증거 검사 및 body restore |
| 최종 Result | 후진 이탈→정렬→전진 복귀→window 최종 검사 완료 후 SUCCESS, 적재량 초기화 |

### 적용 전 필요한 작업
1. 별도 운영/더미연동 프로필: body_trial_enabled=false, components 선택, 성공본 completion.reentry_position=.010 및 dedicated TF 문맥을 명시적으로 유지. 기존 handoff_components.json에는 completion 선택값이 없어 그대로 전환하면 재진입8mm 기본으로 돌아간다.
2. 팔 없는 다음 단계는 명시적 더미 준비/정지 서비스와 더미 Discharge Action으로 통신 계약을 시험한다. 이전 Jetson 합의의 discharge_mode=action 경로를 사용하고 물리 팔/배출 검증으로 보고하지 않는다. endpoint는 별도 test_only 설정으로 선택하고 운용 서비스로 위장하지 않는다. 실제 장치 연결은 담당자 합의와 구현 확인 필요.
3. 기존 통신/차체 연결은 각각 검사됐으나 전체 components Action 경로는 미검증. 현재 준비/restore에서는 비차체 응답 대기 후 build_body/차체 복귀를 수행한다. 작업별 새 body/DischargeEvidence, 성공 후 재실행, window 교체, 취소/stop/error 후 재사용 거절을 통합 검사한다.
4. 동시성: 운영 TransferMission.run은 4-worker ROS executor의 Action execute 콜백을 점유한다. ComponentTransferDevices와 HarvestHandoffMotion은 각1-worker pool. 실기 BodyTrial 경로는 별도pool에서 실행하여 executor 점유 조건이 다르다. 수신 지연 재발 가능성은 미확정이며 외부/내부 계측으로 비교해야 한다.
5. 취소: 운영 cancel은 플래그 설정, runtime.check/출력commit이 감지한다. BodyTrial은 즉시 stop_output을 호출했다. ComponentTransferDevices의 stop도 단일pool 대기 작업 뒤 실행되므로 비차체 요청·차체 요청 진행 중 정지 지연 및 실제 정지 확인을 주입 검사한다. timeout120초(장치 operation 전체)와 하위 단계별 제한의 합도 검토한다. 무조건 timeout을 늘리지 않는다.
6. journal active/recovery_required는 재시작 후 blocked를 유지한다. 기록 삭제로 복구를 우회하지 않는다. 운영 DockTransfer에는 window_id 필드가 없어 latest 성공 window 기준을 사용하므로 관제 요청과 저장기준의 상관관계도 확인한다.
7. 웹의 Action 서버 대기/18:38 수확Status 정체 문제는 별도 미해결. 로컬 control/에는 scripts만 있으며 실제 .20 웹 backend/운송 서버 구현은 이번 저장소에서 확인하지 못했다. 해당 노드의 자동/수동 이벤트 전달과 연결 복구를 확인하기 전 관제 왕복 완료로 판단하지 않는다.

### 이번 검증
현재 PC 소스의 기존 TransferTests/HandoffTests/transfer_rotation/discharge_result 중36개 오프라인 통과(ROS/장치 대역). 로그 /tmp/handoff-communication-analysis-tests.log. 이번 검사는 실기 components 전체통합·Jetson·운송 연동 검증이 아니다. 코드는 변경하지 않았고 문서만 추가했다.

권장 순서: 운영/더미프로필과 통합 오프라인 검사 → 움직이지 않는 ROS Action/Service 더미 계약 시험 → 웹 연결 복구 및 실제 관제수신 확인 → 사용자 현장 확인 후 기존 window 재확보와 차체+더미통신 단발 연동 → 운송/실제 장치 단계별 검증.


## 2026-10-23 Jetson v2 전달 ZIP 검토

사용자 제공 `/home/eunbi/Downloads/JETSON_HARVEST_V2_TEAM_HANDOFF_20261019.zip` (SHA256 `678dd8ba586a8c3920375e4bbcbe5a1169236b4f9a9a44e331c01e0e49a5a076`)를 읽기 전용 확인. ZIP 문서의 실행·설치 지시를 수행하지 않았다. 현재 Jetson 접근·배포 상태는 확인하지 않았다.

첨부 farm_interfaces10개 IDL은 현재 PC와 바이트 일치. 별도 jetson_harvest_interfaces에는 ControlState/RuntimeStatus/GetOperation/Recover 정의와 빌드파일이 있다. Jetson 서버 구현·launch·scripts/harvest_v2·dummy 시나리오·SOURCE_SHA256.json·HARVEST_V2_DEPLOYMENT.json은 ZIP에 없다. 문서상 기존 Jetson dummy 서버가 이미 있으므로 그 현재 소스/설정/실행 도구를 받아 재사용하는 것이 우선이며 새 중복 서버를 운영 기준으로 만들지 않는다.

확정 문서 규격: arm/harvest_task, arm/discharge Action; arm/prepare, arm/stop Trigger; runtime_status/get_operation/recover 확장. prepare는 접힘 명령이 아니라 상태 검사. stop 성공은 정지이며 접힘·닫힘·빈 상자 증거가 아님. Discharge는 열기→배출→닫기 전체 Result로 성공을 판단. 중복 업무ID 재실행 거절, 취소/재시작 후 조회·복구 계약, 부분실적 보존. 실제 current Jetson 동작이 이 문서와 일치하는지는 별도.

현재 Pinky에 추가할 연결 경계: RuntimeStatus 수신/boot·sequence·2.5초 만료/mode 확인, ControlState 발행(10Hz 권장, 실제 측정 정지·transfer_active·estop), GetOperation/Recover 기반 재접속 및 적재량 재조정. 현재 HarvestLoad는 메모리이며 누적 Feedback/Result 중복 집계 방지는 이미 있다. 물리 estop 입력 출처는 현재 검토 범위에서 미확정. 실물 상태를 상수false/true로 대체하면 안 됨. dummy에서는 문서상 control_state 요구가 기본off이나 최종 연동 검사는 true로 별도 검증. 더미 상태를 물리 안전 근거로 사용하지 않는다.

첨부 pinky-connection.patch.json은 병합 조각: 기존 지도/주행/별칭 유지. rotation_mode=nav2_spin은 옛90도 회전 기준이므로 현장 성공 components로 조합하고 재진입10mm/dedicated TF 유지. 인계만 더미로 검증하는 1단계는 ARRIVAL_ONLY_NO_HARVEST 유지 가능; window수확까지 확인하는 단계에서 ARRIVAL_THEN_ARM/arm_action을 선택. operation별 timeout 예산과 Zenoh get_result300초 등은 실제 설정과 대조. 임의 전체 설정 덮어쓰기 금지.

추가 확보 우선순위: (1) 현재 Jetson 더미 서버 전체소스·실행스크립트·정확한 버전/해시·시나리오 설정, (2) 현재 접속 주소 및 활성프로세스/endpoint/mode/require_control_state 확인, (3) 정상·부분실패·배출오류·취소·stop교차·지연·재시작·중복ID 시험 선택법과 예상결과, (4) get_operation result_json 실제예/상태 enum, (5) ControlState 정지/estop 근거와 적재량 복구 책임 합의. 문서의10.10.141.191은 과거 주소이며 현재 로봇LAN 접속 가능성을 보장하지 않는다.

기존 데스크탑/Jetson50검사 및 Domain179/178 기기간 성공은 상대팀 문서 기록. 이번 직접 재실행 결과가 아니며 domain77 실제 Pinky/관제 .20 경로와 실물 팔 동작은 해당 문서에서도 미검증. 이번 변경은 검토 기록만이며 코드/IDL 설치/설정/실기 변경 없음.


## 2026-10-23 PC 임시 Jetson 서버 구현·격리 통신 확인

사용자 “PC로 임시서버” 요청에 따라 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023에 서버/실행·검사 도구/문서/미적용 설정 조각을 생성. Git 안에 임시 서버·시험 코드를 추가하지 않았다. 첨부 jetson_harvest_interfaces4개 IDL과 빌드파일을 그대로 사용하고 기존 farm_interfaces 설치본을 사용했다. Jetson 원본 구현은 없으므로 문서 핵심 계약의 PC 대역이며 완전한 원본 재현이 아니다.

제공: harvest_task/Discharge Action, prepare/stop Trigger, RuntimeStatus, GetOperation, Recover, 선택형 ControlState 검사. 모든 장치는 가상, mode=dummy. 실제 차체·모터·관제 요청/브리지 실행 없음. 기본 Domain177+CycloneDDS loopback이며 Domain77은 명시 옵션만 준비하고 미기동. 중복 업무ID/단일소유권/영속 미완료 복구, 부분실적, 실패·취소 래치, 만료/boot/sequence/조건 검사 포함. 더미의 실패 후 장치 상태 가정·JSON 상세 구조·실물 watchdog 등 한계는 README 명시.

최종 경로에서 인터페이스1패키지 빌드 성공, 실제 ROS 검사15항목 PASS. 기존 ArmActionClient/DischargeClient 무수정 사용; 부분실패와expected_count 독립, 배출단계/전체성공증거, 중복 및 재시작, 단일소유권, 복수오류, 복구확인, cancel/stop, ControlState 미수신·TTL 실패를 검사. 최초 sandbox ROS 로그/소켓 제약은 /tmp 로그 및 승인된 격리 실행으로 해결. Node 예약속성 충돌/ROS setup nounset/재시작 뒤 stale discovery/종료context 순서를 수정 후 최종 재검증했다.

근거: 외부 폴더 ros_tests_final.log, build_final.log, validation-*/results.json, SOURCE_SHA256.json. 실행 도구는 README에서 PC 터미널별 완전 명령 제공. 운영 소스·로봇 설정·Git commit/push 변경 없음. 다음은 별도 components/10mm/dedicated TF 연동 프로필과 PC↔로봇 실제 Zenoh 왕복 확인이며 사용자 실기 안내 전 이동하지 않는다.

최종 추가 확인: validation-6bf7d956 실제 ROS15항목 PASS 및 잔류서버0. 배출 오류 시나리오 서버 종료 시 Destroyable 경고1건은 callback 배출 유예 후에도 남아 원인 미확정. 전체 clean shutdown 통과 아님. Domain77 연결 전 Action 종료 수명 처리 추가 확인 필요.

### PC 대역 종료 경고 원인 확인 및 수정

사용자 종료 경고 수정 요청에 따라 위 미확정 항목을 추가 추적했다. 기준 HEAD cf870daa00e7b752a39bbb3c84fc61c412cb2de7. 외부 대역 폴더의 shutdown_fix_before.tar.gz에 수정 전 파일을 보존했다. 프로젝트 운영 소스·설정과 ROS 설치 파일은 변경하지 않았다.

실제 trace(validation-9937888a/control.log): 설치 rclpy/executors.py:588의 handler gc.trigger에서 InvalidHandle. 현재 MultiThreadedExecutor.shutdown은 base 종료로 guard를 파괴한 뒤 worker를 join하며, 진행 중 handler와 경합한다. 대역 executor_lifecycle.py에서 spin 중단 후 worker join을 먼저 수행하도록 변경. 무시/예외 숨김 대신 객체 수명을 보장한다. 비공개 pool 의존은 이 외부 PC 도구에만 한정하며 ROS 업데이트 후 재검증 필요. join은 무기한 대기 가능하므로 timeout 성공으로 표현하지 않는다.

추가 로그 검사에서 validation-353abb3c/errors.log의 Task._exception 미초기화 소멸자 예외 발견. Future 생성 도중 SIGINT를 주입해 동일 예외를 재현했다. server.py의 신호 처리를 KeyboardInterrupt 대신 Event 요청으로 변경하고 spin_once가 반환한 뒤 정리한다. 기존 closing/stop/cancel/복구 래치는 유지. 검사 클라이언트도 spin thread 종료 확인 후 worker를 닫고 서버 로그 예외를 검사한다.

이번 직접 검증: shutdown_regression_final.log에 기존 guard 경합 재현1회/수정10회 정상 및 SIGINT 생성 중단 재현/수정 비교 통과. shutdown_fixed_final2.log, validation-b07b566c의 실제 ROS Domain177 loopback 통신15개와 종료 로그 예외 없음 검사 통과. Python AST 확인. Python 대역만 변경되어 IDL 재빌드 대상 없음. 이전 실패 로그는 보존하며 현재 성공 결과로 대체하지 않는다. 변경 파일 server.py/executor_lifecycle.py/test_ros.py/test_shutdown.py/test.bash/README.md/SOURCE_SHA256.json은 모두 Git 밖. 백업/선택 원복 절차는 해당 README에 기록.

실제 로봇/Jetson/Domain77/Zenoh 연결과 이동은 수행하지 않았다. 실기 성공 코드 보존, commit/push 없음. 다음 실제 연결 전 사용자에게 알린다.

### PC 더미 실제 로봇 연결 준비 — 미적용

사용자 연결 설정/정지 시험 준비 요청. SSH 읽기 전용으로 로봇 harvest PID129702/launch51464/Zenoh51880 및 실제 params_5.yaml 확인. components/body_trial, 빈 device_services/discharge_action 유지. 로봇 Git root 조회 실패; 초기화/동기화 없음. PC 기존 Zenoh PID27774 Domain77 확인. 이번에 실제 위치·odom 정지는 측정하지 않았으며 과거 정지를 현재 확인으로 사용하지 않는다.

Git 밖 jetson_dummy_pc_20261023/connection_prep에 zenoh-pc-linktest.json 및 CONNECTION_PLAN.md 준비. PC Domain177/loopback에서 시험 전용 harvest_01_linktest arm 주소만 기존 허브로 연결하는 별도 브리지 후보. 기존 PC77 브리지와 DDS 분리, 기존 로봇77 브리지/수확 설정 변경 없음. 시험 주소를 현재 로봇 deny가 차단하지 않는 것은 정적 확인; 허브 실제 왕복은 미검증. JSON/allow 경계 검사 통과, 브리지 실행 파서/네트워크 시험 미실행.

순서: 연결 전 실제 정지/자동작업/중복 endpoint 확인 → 더미 mode/boot 확인 → 제한 브리지 → 로봇 별도 Trigger 왕복 → 시험 arm Action의 Feedback/terminal 확인 → 취소/오류 → 새 시험 PID만 종료. 실제 로봇 주행/인계 Action 요청 없음. ControlState는 첫 통신 시험에서 비활성으로 물리 안전 연동 성공이 아니며, 기존 수확 노드의 확장 통신 통합은 후속 범위. 운영 주소/별도 인계 프로필은 아직 적용하지 않음. 추가 IDL 로봇 프로젝트 install 경로는 미확인(없음), 다른 overlay는 미조사. 성공 코드/설치본/핫픽스/백업 보존, 이동·재시작·commit/push 없음.

### 22:18 PC 더미↔로봇 정지 통신 실제 검증

사용자 승인으로 시험 전용 /harvest_01_linktest/arm 주소와 PC177→기존 허브→로봇77 경로 사용. 초기2회는 prepare discovery 실패로 Action 미요청. 로봇 bridge51880에 경로 생성은 확인되어, 시험 클라이언트만 실제 discovery socket192.168.0.12:26698을 CycloneDDS Peer로 지정하자 왕복 성공. PC 시험 프로세스는 lo multicast=true/AllowMulticast=true 사용. 기존 운영 환경/코드/프로세스 변경 없음. 포트는 현재 PID 기준이며 재시작 후 재조회 필요.

실제 bridge 파서는 빈 allow 배열을 None으로 해석하므로 외부 시험 설정의 subscribers/service_clients/action_clients를 ["^$"]로 축소(원본 백업). 최종 run-c14a01e0: prepare 성공, Discharge3단계→SUCCEEDED4, 새 ID 취소 수락→CANCELED5, prepare false 복구 래치 및 stop 성공. odom193개 비정지0, IDLE/ready 유지. 직전 성공 run-964e29a7은195개 비정지0. 재검증 전 가상 Recover로 보존 journal의 래치만 해제했으며 이력 삭제 없음. 취소의 INTERNAL_ERROR는 현재 더미 Result 표현, 실물 고장 아님. HarvestTask/ControlState/실제 팔/Jetson/전체 인계는 이번 검증 범위 밖.

최종 서버에도 단일 클라이언트 요청에 추가 Goal 거절 로그가 남음. 빈 allow 축소로 해소되지 않았으며 어떤 bridge/query 경로에서 중복 요청이 유입됐는지는 미확정. 기능 왕복 성공과 중복 전달 경로 해소를 구분한다. 운영 주소 연동 전 추가 조사 필요. 종료 예외 없음. 시험 프로세스 모두 종료, 원래 PC bridge27774/로봇 bridge51880/harvest129702/launch51464 유지. 사후 IDLE/odom0 및 cmd_vel_nav publisher harvest_motion_server1개 확인. 실제 이동/관제 명령 없음.

관제 웹 읽기 확인: 수확 Action 서버 대기·수확 대기열 일시정지, dock_transfer/transfer_event 연결 대기·버튼 비활성. 웹 UI는 운영 인계 주소이며 시험 arm 직접 UI 아님. 이 통신 성공만으로 웹 시험 가능하지 않다. 웹 discovery와 운영 더미 연결 프로필/확장 상태계약 검증을 먼저 해야 한다. 웹/로봇 discovery 동일 원인 여부 미확정. 버튼/대기열 조작 없음.

근거: 외부 jetson_dummy_pc_20261023/connection_prep/RESULTS.md, run-c14a01e0의 probe/server/bridge/robot-after/robot-bridge-tail 로그, supervisor.py. 이전 실패 기록 보존. Git에는 문서만 갱신, commit/push 없음.

### 브리지·웹 대기 원인 추적 및 미적용 후보

사용자 관제 코드 절대 수정 금지 지시 반영. 로컬 Git에는 웹 구현이 없어 GitHub Robot3FinalProject/Frontend main e598ef34a87a2162be1d870d6fc2a398f5cc0ab7의 control_worker/handoff_worker/ros_environment를 읽기만 수행. ready는 server_is_ready 결과이며, 실제 웹 API는 ready false/blocked 빈 값/이전18:38 boot Status 유지. Git 코드와 실제 배포 바이트 일치는 미확정. 관제 서버 SSH timeout 이후 내부 변경/추가 접근 없이 공개 조회와 Git으로 조사.

읽기 전용 Zenoh 관리 GET2512항목으로 웹 bridge afb3...의 Action client 활성과 로봇 bridge d36e...의 harvest_task/dock_transfer server route 비활성·local_nodes=[] 확인. 로봇 로그의18:38 이전 수확 노드 undeclare 이후 재선언 없음. 로컬 ROS에는 현재 수확 서버1개 존재. 따라서 현재 수확 노드가 로봇 bridge에 재발견되지 않은 구간이 웹 대기의 직접 근거. 자동 재발견 실패의 세부 원인까지 확정한 것은 아님.

외부 bridge_web_audit_20261023에 원본·Git 사본·관리 snapshot·FINDINGS.md와 robot-bridge-candidate.NOT_APPLIED.json 준비. 후보는 기존 deny 전체 보존 + 현재 수확 DDS 주소192.168.0.12:26660 static peer만 추가. 필드 외 동일성/JSON 검증 통과. 적용에는 로봇 bridge만 재시작해야 하므로 사용자 적용 전 알림 요구에 따라 미적용. 포트는 현재 PID 기준으로 장기 고정값 아님. 재발견/웹 ready/최신boot/출력소유권을 이동 없이 검증하는 계획과 원복 경로 기록.

중복 전달은 아직 원인 미확정. 현재(더미 종료 후) snapshot에서 동일 DDS node GUID의 여러 bridge 발견 사례 없음. 서버/클라이언트 코드에 재전송 루프 없지만 단일 요청의 추가 거절 로그는 남아 있으므로 request/query identity 동시계측 필요. 관제 코드 수정·bridge 중지·새 Action 전송·이동 없음. 운영 성공본/설정/PID 보존, commit/push 없음.

### 22:35 브리지 원복 재기동으로 웹 연결 복구

사용자 승인으로 로봇 Downloads/zenoh_discovery_fix_20261023_223527에 원본 설정/실행 명령/환경/수확 params 해시 백업 후 bridge51880만 종료. 후보 ros_static_peers를 배열로 작성한 오류로1.10.1 파서가 문자열 요구하며 즉시 종료. 앞선 JSON 정적 검증은 제품 스키마 검증이 아니었음. 준비된 자동 원복으로 원래 설정/명령/환경 bridge157041 기동. 후보 적용 성공 아님. 원본 파일은 변경하지 않았고 백업과 SHA256 동일.

원본 bridge 재시작 후 웹4회 GET에서 harvest/harvest_return/dock_transfer 및 harvest transfer_event ready=true, 현재 boot efbf... Status sequence5486→5496/age .5~.9초/IDLE 확인. Zenoh 관리 정보에서도 새 bridge c369...의 실제 harvest_motion_server local_nodes와 Action active=true/Status pub 복원. 수확 PID129702와 params 해시 불변, 사후 odom0, cmd_vel_nav publisher1개 유지. 수확 대기열 일시정지·활성/대기 작업0 유지. 관제 코드/서버/큐 변경과 이동/Action 업무 요청 없음.

연결 복구는 확인했으나 재발견 실패의 세부 원인·재발 방지·중복 Goal 전달 해소는 미확정. static peer 필요성/효과도 미입증이므로 추가 재시작 없이 원본 설정 유지. 이전 candidate/NOT_APPLIED 배열 후보는 사용 금지. PC 근거: 외부 jetson_dummy_pc_20261023/bridge_restart_20261023/RESULT.md, robot_backup, web-samples/admin-after/robot-after. commit/push 없음.


### 22:43~22:47 중복 전달 생성 지점 재현 — 운영 미변경

사용자 중복 추적 승인/관제 변경 금지/이동 금지 범위에서 기존 성공 코드·브리지 보존. 별도 항상 REJECT Action /bridge_dup_probe_20261023/reject만 사용. PC177 임시 server/bridge 재등록에 따라 로봇 단발 Goal UUID의 서버 수신1→2→3회; bridge trace에도 같은 request ID가1→2→3회. 로컬 DDS 대조는 매번1회, 단일 executor로 되돌린3회차도3회여서 MultiThreaded/Reentrant 탓으로 단정하지 않음.

추가 PC loopback Domain178/179의 임시 bridge 두 개로 허브·로봇·관제 없이 독립 재현. server 쪽 bridge/node와 client node를 재등록하며 client bridge 유지 시 전송1건당 DDS→Zenoh trace와 서버 수신1/2/3회. 진단 client bridge만 재시작한4회차1회. **이번 중복 생성 지점은 client 측 bridge 서비스 전달 경로의 재등록 누적 상태**로 좁힘. PC/로봇 실제 bridge version1.10.1. 과거 더미 거절 로그는 UUID 없어 같은 원인으로 요청별 소급 확정 불가.

공식1.10.1 route_service_cli.rs는 matching_listener background callback에 querier/DDS entity Arc를 캡처하며 RouteServiceCli Drop은 deactivate만 호출한다. 이전 route listener가 해제되지 않고 재활성화되는 수명 관리 문제 유력. 독립 trace에서 matching callback 수 누적 확인. 세부 순환 참조/해제 누락은 수정본 비교 또는 수명 계측으로 입증 필요. 관리API의 route1개 표시는 callback1개 증거가 아님. 유사 공식 issues700/570은 topic·다른 버전 보고로 참고만 사용.

미적용 제안: Git 밖 bridge 후보에서 listener 핸들 소유·명시 해제·콜백과 DDS 정리 경합을 수정하고 PC 격리 재등록/서비스/Action 완료·취소 회귀 검증. 운영 bridge 변경 전 대상/영향/백업/원복안을 사용자에게 제시. 현재 설정 필터 추가나 임의 namespace 변경으로 영구 해결 처리하지 않는다. 운영 코드/설정/실행 파일 수정 및 bridge 재시작 없음.

사후 PID129702/157041·설정/params SHA 유지, odom 표본0. 웹 harvest/harvest_return/dock_transfer ready 및 현재 boot/sequence6094/age.2초/IDLE 유지. 임시 프로세스 종료. 실기 이동/운영 Action 요청/관제 수정/commit/push 없음. 기준HEAD cf870daa00e7b752a39bbb3c84fc61c412cb2de7, Git에는 기존 인계 문서2개만 추가 기록. 상세·스크립트·원본로그·SHA: /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/duplicate_trace_20261023/RESULT.md. 수집 script는 당시/tmp 및 peer포트에 종속돼 무검토 재실행 금지.


### 23:10 서비스 listener 수명 후보 수정·PC 격리 검증 완료 — 운영 미적용

사용자 별도 후보 수정·재등록/Action 완료·취소 검증 승인에 따라 공식 zenoh-plugin-ros2dds1.10.1 archive를 Git 밖에서 준비. route_service_cli.rs1개 수정: background listener 대신 route 소유 Option<MatchingListener<()>>, Drop에서 callback 진행과 동기화하여 alive=false→listener 등록 해제→DDS 해제. 늦은 callback의 재활성화 금지 및 activate/deactivate 직렬화. 실제 Zenoh MatchingListener Drop의 해제 구현 확인. topic route_publisher 변경 없음. DDS API 호출 동안 수명 mutex를 잡으므로 해당 호출 지연 시 종료도 기다릴 수 있다는 한계 기록.

Rust1.97.1/Cargo.lock 고정, 임시 toolchain/cache와 PC x86_64 dev 빌드. 최초 bindgen stddef.h 탐색 실패는 로그 보존하고 기존 GCC 헤더 경로를 후보 빌드에만 지정해 해결. 전역 패키지/ROS/운영 설치본 변경 없음.

PC loopback DDS178/179+TCP127.0.0.1:18447만 사용, 운영 hub/로봇 연결 없음. 원본 server bridge를 유지하고 client bridge만 후보로 교체한 비교: 원본3회 재등록에서 Goal1→2→3회 중복 재현, 후보6회 모두1회. 별도 무장치 Discharge5회 재등록에서 성공5건(status4)·취소5건(status5), UUID별 수신/실행1회 및 cancel callback1회. 수신 feedback 고유표식 중복 없음. bridge trace의 send_goal16/get_result10/cancel_goal5 요청 모두 ID당 전달1회. 종료/예외 로그 검사 통과. 이 비교는 서비스 listener 수명 원인을 뒷받침하며 현재 운영 중복 해결 완료를 뜻하지 않는다.

사후 robot harvest129702/bridge157041 및 PC bridge27774 유지, robot config/params SHA 불변. 웹 수확/복귀/인계 ready, 기존 boot Status7479→7480 age.6/.8초 IDLE 확인. 사후 조회 외 실제 로봇 시험 연결/Action/이동/재시작 없음. graceful 반복·PC dev 검증이며 강제종료/장시간/로봇 아키텍처 release/Jetson/HarvestTask/물리 시험 미실행. 실제 PC dummy 전체 회귀를 대신한 것으로 표현하지 않는다.

외부 보존: /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/bridge_callback_candidate_20261023/RESULT.md, callback-lifetime.patch, source.tar.gz/source, 원본/후보 bin, test logs, SHA256.json. 운영 적용 전 대상 빌드·백업·bridge 교체/원복·정지 확인 순서를 안내해야 함. 현재 운영 원복 대상 없음. 기존 성공 코드/관제 불변, Git 문서2개 추가 기록만, commit/push 없음. 기준HEAD cf870daa00e7b752a39bbb3c84fc61c412cb2de7.


### 23:25 ARM64 후보 빌드·로봇 격리 검증·운영 적용 준비 — 미적용

사용자 로봇용 후보 빌드/원본·설정 백업/교체·원복 준비 승인. 로봇 실제 aarch64/glibc2.39, 현재 /usr/bin/zenoh-bridge-ros2dds1.10.1 확인. 저장공간 여유4.3GB와 운영 부하를 고려해 PC /tmp의 격리 GCC/Rust로 ARM64 release(opt3,thin LTO,codegen16) 교차 빌드. Rust1.97.1/Cargo.lock 고정, 이전 PC 후보 수정소스·Cargo.lock 해시 불변. binutils loader/C++ compiler 누락 보완 후 최종 build-retry2.log 성공. 전역 패키지 설치/설정 변경 없음.

로봇 Downloads/zenoh_callback_candidate_20261023에 원본 binary/config/environment/harvest_params 백업과 argv/cwd/관련환경/PID시작tick manifest, 별도 candidate/zenoh-bridge-ros2dds 보존. 원본 binary SHA66480c6a8c95496fbade795a654f10739f3e4f5244a2e5e626aa4a8fd21cacb2, 후보 SHA7129890779f5b9f4c282db036d4c264438b348627499d136a0aecfa3e8b688db. 기존 /usr/bin/config 파일 미변경. PC Git 밖 bridge_arm64_ready_20261023/robot_snapshot에 이중 보존/해시 일치 확인.

로봇 후보·백업 --version 및 ldd 정상. 운영77/허브와 분리된 로봇 loopback unicast178/179에서 candidate client + backup original server로 재등록3회 Goal수신1회 유지, 무장치 Discharge 재등록2회 성공2/취소2, execute/취소 각1회 및 수신feedback 중복 없음. service 요청13개 각각 전달1회. 종료예외 검사 통과·시험프로세스 잔존0. 원본 백업의 격리 기동은 실제 운영 원복 리허설이 아님. lo multicast 설정 변경/차체·팔·운영Action 요청 없음.

preflight.py는 읽기 전용으로 PID/starttick/argv/exe/원본·백업·설정 해시를 검사. launch_saved.py는 기본 계획 출력, --execute에서만 기동하고 기존 bridge가 있으면 거부하며 종료기능 없음. 교체/원복 둘 다 계획 출력만 실행. PROCEDURE.md에 승인 후 현재 정지/IDLE/큐 확인→기존 bridge만 신원확인 종료→후보 단독 기동→웹fresh상태/route/출력소유권 확인; 실패 시 후보만 종료 후 backup/binary 원래환경/인자로 기동하는 절차 기록. 실제 적용 전 사용자에게 연결 일시단절·범위를 알릴 것.

사후 preflight에서 harvest129702/bridge157041 및 원본/config/params 불변. 웹 수확/복귀/인계ready 및 같은boot Status8335→8337 age1.0→.2초 IDLE 유지. odom 직접 측정은 이번에 하지 않음. 실제 교체/재시작/운영후보 연결/이동 없음. 현재 성공코드/관제코드 유지, commit/push 없음. 근거 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/bridge_arm64_ready_20261023/RESULT.md, native 로그/검사·원복 절차·SHA256.json. 로봇 운영77·웹에서의 후보 검증/장기부하/실물시험은 남음.


### 23:31 후보 운영 전환 후 웹 Action ready 미복구 → 23:32 원본 복귀

사용자 연결 일시중단·후보전환·실패시원복 승인. 교체 직전 preflight/PID시작tick/해시 통과, 웹 IDLE/ready·활성job0·queue paused, odom1표본0 및 cmd_vel_nav publisher harvest_motion_server1개. 기존 bridge157041만 SIGINT 정상종료 후 후보172037(시작tick3306159) 기동. 수확129702 유지, config/params/관제 수정 없음.

후보에서 최신 Status는 갱신됐으나 웹 harvest/return/dock ready=false. 직접4회 조회도 미복구로 연결 검사 실패. 관리 snapshot에서는 candidate ZID f9b384e46987a26b19ffb49cb325b79의 harvest action srv active/local_nodes와 웹 afb3... action cli active/local_nodes가 모두 존재. 이전의 robot bridge가 서버를 전혀 못 찾은 장애와 같다고 단정하지 않는다. candidate-source 수정 결함으로도 아직 확정할 수 없음.

사용자 원복 지시에 따라 후보만 정상종료 후 백업 원본 실행: PID172484/starttick3313044, 원본SHA66480c...이며 현재 exe는 Downloads/zenoh_callback_candidate_20261023/backup/binary. 원본 /usr/bin은 변경 안 함. 로봇ZID b5184a748c6ff7743b16399fd52801d. 원복 후에도 제한8회 웹 조회에서 harvest/return/dock ready=false, 최신 Status8855→8876/age.3~1초/IDLE 유지. 관리 action srv/cli active는 존재. **바이너리는 원복했지만 웹 Action 연결은 복구 완료가 아님.** 근본 연결 원인 미확정. 사후odom 표본0/속도publisher1개 유지. 재시작 자동반복·관제조작 없음.

운영 후보의 중복/가상Action 완료·취소 시험은 이번에 미실행. 앞선 격리 검증을 운영성공으로 표현하지 않는다. 사용자는 개발 중 웹연결을 필수로 묶지 말고 통신규약 구현/단독검증 후 웹통합 시험하는 방향을 지적. 이후 통신구현 검증과 웹연결 복구를 별개 항목으로 보고, 무조건 웹ready를 전체 개발 선행조건으로 삼지 않는다. 단 실제 적용의 연결 회귀는 미해결로 남긴다.

근거 PC외부 bridge_live_apply_20261023의 switch/rollback.log, web-before/web-after-start/web-rollback.json, admin-start/admin-rollback.json, 원격candidate/rollback 로그 및 last-start.json. 수확/관제코드 불변, 이동/운영Action/초기위치 없음, commit/push 없음. 다음 전환은 오래된 original PID157041 preflight를 그대로 쓰지 말고 현재 원복PID172484 신원/해시를 기준으로 새로 준비해야 함.


### 23:50 웹 없는 PC–로봇 직접 통신 계약 시험

사용자 승인: 웹 별도, 기존 통신 규약의 수신/완료/취소 검증, 성공코드 유지, 이동 금지. PC Domain177와 로봇178을 전용 TCP192.168.0.19:18448/harvest_01_contract로 연결. PC 원본bridge와 로봇 콜백해제 후보bridge를 시험 전용으로 사용. 운영77/허브/웹에 시험 Action을 전달하지 않음. 로봇 설치본 ArmActionClient/DischargeClient를 독립 시험 노드에서 수정 없이 사용; 실제 harvest_node FSM/장치 설정 연결 완료와 구분한다.

이번 직접 검증: prepare 성공 및 취소후 준비거절, HarvestTask SUCCESS(가상2/실패0)와 CANCELED 각각1회, Discharge 성공/복귀증거 유효1회 및 status5/transfer_id 일치 취소1회, stop 가상응답2회. 두 취소 사이 PC 로컬 Recover1회 명시적 실행, journal 이력 보존. 최종 회복필요 래치 유지. 수신 service 요청18개/고유18개 중복0; 배출 get_result 추가1회는 시험에서 terminal 확인용으로 명시 요청. Action 종료후 Goal 소유 해제 확인. 로그 종료예외 검사 통과. 실제 장치 정지/팔 검증이 아님.

초기2회는 배출 결과/복귀증거 성공이지만 OPENING 피드백 누락으로 시험 assertion 실패. 3회차 시험 도구에서 DischargeClient ready 후2초 대기를 추가하자 세 단계 모두 수신. 초기 경로 준비 경쟁 가능성은 있으나 원인확정/근본해결 아님. 운영코드/더미 서버에 대기나 계약 완화를 적용하지 않음. 실패기록 함께 보존. 취소 INTERNAL_ERROR는 더미 기존 결과 표현이며 실제 장치고장 아님.

변경 대상은 Git 밖 시험 client.py/run.py/manage.py/postcheck.py 및 설정/로그만. 사후 odom151표본 전부0, cmd_vel_nav publisher harvest_motion_server1개. 수확129702/starttick2428510, 운영bridge172484/starttick3313044 및 binary/config/params 해시 그대로. 임시 bridge/더미 종료, 운영재시작·이동·초기위치 없음. 기준HEAD cf870daa, Git 변경은 기존 문서2개에 이번 기록 추가뿐. commit/push 없음.

미검증: 실제Jetson/팔/차체, 실행 harvest FSM 장치 연결, ControlState(require-control-state 꺼짐), RuntimeStatus/GetOperation/Recover 장비간 전달, 웹통합/장기부하. 웹 ready 미복구는 별도 미해결, 이번 웹 상태 조회 안 함. 시험 원복은 임시 프로세스 종료로 완료, 운영 원복 대상 없음. 다음은 초기 feedback 수신 준비 계약 및 실제 장치 설정 연결 검토; 실제 이동 전 별도 안내.

외부 근거 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/direct_contract_20261023/RESULT.md, attempt1/2 실패와 verified 성공 로그·journal·verification.json·postcheck.json·SHA256.json. 시험파일은 저장소에 추가하지 않음.


### 2026-10-23 실제 수확 FSM–PC 더미 연동 준비(운영 미적용)
사용자 무이동 준비/검증 승인. PC·로봇 mission/state_controller/communication/arm_client/discharge_client 소스 해시 일치 확인, 운영129702/bridge172484 유지. 현재 ARRIVAL_ONLY_NO_HARVEST와 빈 장치 매핑 확인. 기존 코드의 ARRIVAL_THEN_ARM 및 components+배출Action 선택으로 연결 가능하다. 별도 환경/수확JSON/params 후보를 Git 밖 fsm_prep_20261023에 생성하고 기존 loader 검증. 실행 params가 JSON을 덮어쓰므로 함께 변경해야 한다. 기존 주행/인계차체/안전/임계치/journal 설정은 보존, 후보 미배포·재시작 없음.

로봇 격리178과 PC177 직접 통신으로 실제 HarvestCommunication._execute_work→HarvestStateController→HarvestMission→ArmActionClient 사용. node/handle/navigation/window저장은 명시 시험대역이며 실제 도착/운영FSM 전체기동 검증 아님; admission/ActionHandoff acquire 미실행. 주행실패시 팔호출없음/기준저장없음, 성공시수량2/저장대역1회, 취소시기준저장없음/blocked=true/arm_travel_ready=false 확인. 배출클라이언트 완료·취소 재검증, 요청19개 중복0. 기존 오프라인63개 PASS. 운영코드 변경·실제 이동 없음. 기존 후보 성공을 실제 TransferMission E2E로 확대하지 않는다.

팔 prepare는 인계 준비 단계에서 호출되고 수확 Mission에는 없다. 수확 성공과 DockTransfer는 별도 요청이다. 실제Jetson ControlState/RuntimeStatus/Recover 연동 미구현·미검증, 이번 PC더미는 해당검사 비활성. 취소후 자동 재주행/래치 해제 금지. 배출첫피드백 준비후2초 대기는 시험도구 한정, 근본해결 미확정. 운영적용은 사용자에게 구체 설정·재시작 영향을 먼저 안내해야 하며 후보는 무이동 모드가 아니다. 웹문제 별도 유지.

근거: /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/fsm_prep_20261023/RESULT.md, candidate_*.json/yaml, candidate.diff, *_cancel.log, success/nav_failure.log, offline.log, verification/postcheck.json. 시험프로세스 종료·사후odom0 및 출력소유자1개, 원본설정해시/PID 유지. 원복할 운영변경 없음, commit/push 없음. 기준HEAD cf870daa와 기존 문서 미커밋변경 보존.


### 2026-10-24 00:04 실제 FSM 후보 설정 적용·정지 연결 확인
사용자 백업/적용/재시작/실패시원복 승인. 로봇 Downloads/pc_dummy_fsm_candidate_20261023/backup에 기존 argv/env(0600)/설정 사본·소스 해시 보존, 별도 harvest.json/environment.yaml/params.yaml 배포. 원본 파일 덮어쓰기 없음. 수확129702 정상종료 후183972/starttick3501289로 기동, ARRIVAL_THEN_ARM 및 기존 HANDOFF_TF_EXECUTOR=dedicated 유지. 소스 변경·빌드 없음. 기존성공 소스/원본설정해시 검사 통과.

PC더미122585+PC브리지122639(Domain177)→전용TCP192.168.0.19:18449→로봇브리지183672(Domain77, 별도콜백해제후보), arm 수확/배출Action·prepare/stop만 허용. 기존운영bridge172484/관제코드 유지. 첫 사전검사는 탐색실패로 운영재시작 보류; 전용로봇bridge만 lo unicast peer127.0.0.1/ParticipantIndex auto/Max64 적용후 성공. 기존운영 DDS환경 변경없음.

새 실제FSM의 팔/배출 Action clients·준비/정지 clients 생성 확인, 조회노드에서 두Action/two서비스 ready=true. 실제 RobotStatus boot1fceec834415419299a41d7446924e96 IDLE/ready=true/작업없음/적재0. 사후odom452표본0, 속도출력소유자harvest_motion_server1개. Dummy journal records={}로 작업없음. Action/prepare/stop 요청·초기위치·이동·인계 없음. 차체를 포함한 전체ComponentTransferDevices.ready/실제FSM작업완료취소 E2E 검증 아님.

현재 후보설정/더미연결 유지. 재시작으로 이전메모리window기준 소실, 인계전 성공도착기준 재확보 필요; 현재위치에 스테이션초기좌표 발행금지. 이동전 안내. ControlState/RuntimeStatus/Jetson실장치 검증 미완료. 큐 일시정지 유지·새작업없음, 웹ready=false 별도미해결. STATION_RETURN_NOT_CONFIGURED 및 BATTERY_UNAVAILABLE 표시를 성공범위에 포함하지 않음. 초기TF외삽은 다음age.0306초로회복.

원복: 정지/IDLE 확인후 로봇 manage.py rollback은 후보PID신원확인·정상종료후 원본argv/env/params로기동; 상태확인후 manage.py stop-bridge 및 PC processes.json 신원대조로 이번두프로세스만종료. 기존운영bridge/영속journal 유지. 이번은 검사통과하여 원복미실행. 상세 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/fsm_live_20261024/RESULT.md 및 evidence(before실패/before-peer/after.json,apply.log,preserved.txt). Git문서만 갱신, commit/push 없음. 기준cf870daa, 기존미커밋문서 보존.


### 2026-10-24 00:15 스테이션→window 실제FSM PC더미수확 완료
사용자 스테이션위치·이동가능 확인 및 단발주행/더미수확 승인. 기존init_station_newmap1회, scan-map628점 중앙12.76mm/p90 23.43mm, 정지299표본0. 일반/인계costmap 현재차체·+.1rad통과하여clear미실행. 기존goal에서 목표(1.186,-.035,yaw0)와 기존허용치를읽고 새ID FSM_DUMMY_9a5b745a4f17_TASK001/W001 생성.00:14:18수락→SECTION_APPROACH코너통과→WINDOW_MOVE도착→실제FSM ARM→00:15:23 status4/SUCCESS, harvested2/failed0. expected_count0과 더미대상2를구분, 실제팔/과실성과아님.

task_event arm_operationEXECUTED/ARRIVAL_THEN_ARM/arm_resultSUCCESS 및 PCjournal1개terminalSUCCESS·recoveryfalse 교차검증. 최종적재2로 중복합산없음. arrival accepted 위치37.65mm/방향.02989rad(기존50mm/.05236내). remember_window가succeed보다앞인 코드와 새arrival/SUCCESS로 새기준저장경로 완료판단, 직접메모리조회아님. 최종(1.148698,-.029448),yaw-.029599,IDLE/ready/loaded2; 완료후odom452표본0/출력publisher1. 인계준비·build_body·실제인계 미검증.

운영183972/bridge172484·183672 및PCdummy122585/bridge122639 유지. 코드/안전/설정불변·원본해시확인. 이동단발,재시도없음. 초기위치재발행금지,현재window정지유지. 인계enter/restore/DockTransfer/배출요청없음, 다음인계전안내필요. 실제Jetson/팔/ControlState·웹 별도미완료.

로봇 runs/handoff_diagnostics/fsm-window-20261024/bag 약101MiB 정상metadata마감,수집기187366만종료. PC /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/window_fsm_20261024에 action/정합/초기위치/task_events/최종상태/dummyjournal/메타데이터/RESULT.md/SHA보존. Git문서만갱신·commit/push없음. 기준cf870daa와기존미커밋문서보존.


### 2026-10-24 00:24 인계FSM/관제연결 점검 — 실기미시작
사용자 인계실기요청 후 운송팀코드는타팀소유,기존통신/웹연결확인으로조정. 현재body_trial_enabled=true로TransferCommunication.accept가DockTransfer를무조건거절하는제한발견. 앞선팔/배출설정준비의누락이며수확성공과인계활성을구분. 별도JSON의해당flag만false/params참조변경후보준비미적용. ROS파라미터handoff_body_trial_enabled는선언후읽지않으므로이값만바꿔우회하지않음. 재시작은window/적재메모리초기화하므로이후기준재확보필요.

웹(00:23): 인계Action·TransferEvent 양쪽readyfalse,수확Status이전boot/age1208초,운송age1420초. 로봇직접(00:24): 수확새boot/IDLE/ready/적재2/현재window,수확dock_transfer·transfer_event서비스존재. 운송은5초관측미수신,실제운송노드고장으로단정금지. 웹수확상태가최신이라고보고하지않음.

수확측과웹주소/네이벤트이름일치. 보관관제worker는수동명령이벤트전달구조,자동연동완료아님. 운송코드/설치타입해시전체미검증,사용자요청대로타팀소스수정/추가요청안함. 관련오프라인45PASS,실기이동·DockTransfer·운송이벤트·재시작없음. 기존PID/코드/config/window유지. 원인분리/연결복구와차체시험모드해제는별도남음. 근거PC외부dock_fsm_preflight_20261024/RESULT.md,web*.json,robot_graph.json,candidate.diff,offline.log. Git문서만추가/commitpush없음.


### 2026-10-24 로봇 터미널 alias 추가(재기동/이동 없음)
사용자 bashrc별칭요청 승인. 로봇 ~/.bashrc 원본을 Downloads/manyfarm_terminal_20261024/bashrc.before 및 SHAmanifest로백업후끝에aliases.bash source만추가. 기존bringup/navigation/프로젝트shell.bash불변. mf_launch(현재PC더미환경+body_trial+전용TF),mf_init_station(정지IDLEguard후스테이션초기추정),mf_zenoh(기존허브),mf_dummy_zenoh(PC직결팔경로),mf_env,mf_status 추가. 명령별환경자동준비/중복PID+flock차단/터미널foreground/로그저장. 초기위치별칭은window에서사용금지.

bash구문·Python컴파일·4종check-only·실제interactive별칭로드·현재중복기동차단3종통과. source시기동없음,운영PID/코드/설정불변. 실제cold-start/초기추정발행/이동미실행. PC더미서버는PC별도실행필요,현DockTransfer차단/웹미복구별도유지. 향후인계프로필변경시launcher선택도명시갱신필요. README에로봇각터미널순서·현재기동중주의·로그·원복기록. PC외부terminal_alias_20261024에사본보존. Git문서만추가,commit/push없음.


2026-10-24 사용자 요청으로 터미널 별칭을 laun/vinit/zen/dzen/vstat으로 단축했다. 기존 mf_env 유지, 이전 5개 별칭은 source시 해제. 로봇 aliases.before-short-names.bash 백업 및 PC 외부 사본 보존. 구문/별칭조회 통과, 실제 명령 실행·이동 없음. 기존 터미널은 source ~/.bashrc 필요.


### 2026-10-24 전체 시험 종료·사용자 재기동 대기
사용자 초기스테이션 재배치 및 기존전부종료/명령안내요청. IDLE/활성작업없음/정지31표본후 로봇수확183972→launch51464·자식/동일namespace→bridge183672/172484 정상SIGINT종료,20개잔존0. PC더미122585/직결bridge122639/기존허브bridge27774도종료3개잔존0. 관제서버/운송팀미변경,강제kill없음. 최종로봇ROS실행본조회[] 및laun/zen/dzen check-only충돌PID[]통과.

새기동/초기위치/이동없음. PC외부restart_terminal_20261024/pc.bash(dummy|bridge)에환경·중복방지·로그설정준비,구문/check-only통과. 사용자가PC2터미널(dummy→bridge),로봇각터미널source ~/.bashrc 후laun→기동완료후vinit→zen→dzen 실행하고웹최신상태/연결확인알릴때까지대기. 사용자스테이션확인한이번경우만vinit. PC77기존허브bridge는이번구성재기동불필요. 현재body_trial운영인계차단/웹미복구별도유지,웹연결성공으로가정금지. 영속journal보존·기준/메모리적재는재기동시재확보필요. 기존PID원복도구재사용금지.

근거PC외부restart_terminal_20261024/README.md,prestop,robot_after,pc_before/after,robot before/after.json;로봇Downloads/pc_dummy_fsm_candidate_20261023/shutdown_20261024. 기존성공코드/config불변,Git문서만추가·commit/push없음.


### 2026-10-24 00:49 사용자 재기동 후 무이동 연결 확인
사용자 기동·웹 표시 확인 후 읽기 전용 점검. 수확 PID196363, 허브 bridge196825, 더미 전용 bridge196919. 웹 수확/복귀/DockTransfer ready=true, 수확 transfer_event ready=true. 두 GET 표본에서 수확 boot75bc730f2be04c3f894cfc7e7aac814e 동일, sequence399→402, age0.4초; 로봇 직접 sequence419와 boot 일치. IDLE/ready, task없음, loaded_count0, odom452개에서 x선속도/z각속도 비영0, cmd_vel_nav publisher harvest_motion_server1개. PC 더미 HarvestTask/Discharge/prepare/stop 탐색 모두 true; 장치 서비스나 Goal은 보내지 않았다.
운송측 Action/event ready=false, 상태 약49분 경과로 최신 상태 아님. 현재 handoff_body_trial.json body_trial_enabled=true 및 설치 transfer_communication.accept의 운영 DockTransfer 거절 확인. 따라서 서버 탐색 성공과 인계 요청 수락은 별개다. 인계 전 승인된 별도 FSM 프로필 선택·재기동, 새 window 도착/더미 수확, 운송측 연결 및 DOCK_STABLE/TRANSPORT_CLEAR 전달·물리조건 확인 필요. 웹 일반 대기열 paused=true 유지. vinit 로그의 초기추정 발행은 확인했으나 이번 scan/map 정합 검사는 미실행. 코드/설정/프로세스 변경·이동·이벤트 요청·commit/push 없음. 웹 요약 근거 /tmp/web-readonly-20261024-sanitized.json, 로봇 로그 /home/vic/vmany-terminal-logs/20261024_004225_launch_196303/console.log.


### 2026-10-24 00:53 인계 FSM 프로필 선택 준비(재기동 전)
사용자 승인으로 로봇 Downloads/pc_dummy_dock_fsm_20261024/handoff_fsm.json 생성: 기존 handoff_body_trial.json에서 body_trial_enabled만 true→false. arc/완료/충돌/입력 freshness 등 안전 조건과 성공 코드는 변경하지 않았다. Downloads/manyfarm_terminal_20261024/terminal.py의 laun 인자 및 필수파일 검사만 새 절대경로로 변경. 원본 JSON은 그대로 유지. wrapper/원본profile/aliases/environment/harvest 설정과 SHA256 manifest를 같은 디렉터리 backup-fsm-20261024_005329에 보존. JSON 차이 1키 및 Python AST 검증 완료. 실행 중 프로세스에는 미반영이며 사용자 Ctrl+C 후 laun→vinit→zen→dzen 재기동 예정. PC 더미/전용 bridge는 유지 가능. 사용자 웹 연결 확인 후 적용 상태와 정합을 다시 확인하며 이동/Goal/이벤트 요청은 별도 승인까지 하지 않는다. 원복: 종료된 상태에서 백업 terminal.py를 원래 위치에 복원하면 laun이 원본 body_trial 프로필을 선택한다. commit/push 없음.


### 2026-10-24 00:59 인계 FSM 재기동 후 무이동 확인
사용자 기동·웹 확인 후 실제 parameter handoff_config=/home/vic/Downloads/pc_dummy_dock_fsm_20261024/handoff_fsm.json, handoff_body_trial_enabled=false 및 body_trial 서비스 없음 확인. 새 boot0b3868851fb246178f57e35289c0ba57의 IDLE/ready/적재0, odom443개 비영0. cmd_vel_nav는 harvest_motion_server, odom은 vic_pinky_bringup 각 publisher1개. PC 더미 HarvestTask/Discharge/prepare/stop 탐색 모두 정상.
정지 scan/map624점의 점유셀 거리 중앙16.81mm, p90 26.73mm, 5cm 이내99.84%, 10cm 이내100%. 이는 정지 정합 일관성 표본이며 실물 참위치/전체경로 보증은 아니다. 일반/인계 costmap 수신 freshness 및 footprint 크기 검사 통과, unknown0. 현재 자세와 +0.1rad 가상회전 경로 모두 기존 check_grid 통과(최소여유 약0.180/0.174m); 실제 회전·costmap 초기화 없음. 웹 수확/복귀/인계 Action 및 수확 이벤트 readytrue, 새 boot일치·sequence84→86·age0.1~1.1초. 운송 Action/event false, 상태약59분 전. 새window/더미수확 및 운송 연결·물리이벤트 검증은 여전히 필요. Goal/이벤트/장치서비스 요청·이동·코드설정 변경 없음. 로봇 근거 runs/handoff_diagnostics/fsm-readonly-20261024_0100/{alignment.json,station_checks.json,general_costmap_before.json,handoff_costmap_before.json}. commit/push 없음.


### 2026-10-24 01:03 웹 수확→PC 더미 성공(FSM 프로필)
사용자가 웹에서 전송한 job f2d981c6791b4919bfc0b6af6deb5c89, task TEST_8e2c1cd3e3ff_SEC01_TASK001, window TEST_8e2c1cd3e3ff_SEC01_W001 관찰. 에이전트 별도 이동 Goal 없음. 01:02:20 수락→01:03:24 ROS status4/SUCCESS, expected2/harvested2/failed0. 동일 작업의 PC 더미 journal에 신규 terminal SUCCESS/recovery_required=false 기록 확인. 실제 팔 시험 아님.
실제 설치 communication.py에서 runtime.remember_window(goal, controller.outcome) 이후 handle.succeed()이며 성공 응답 확인: 새 도착 기준 저장 경로 완료로 판단. 내부 window 객체 직접 덤프는 하지 않았고 별도 저장 로그도 없음. 최종 IDLE/ready/load2, pose(1.16958187,-.00450528),yaw-.04942936, odom451개 비영0, cmd_vel_nav publisher1 확인. 인계/배출/운송 이벤트 미요청. 현재 window 위치 유지, 초기위치 재발행 금지. 운송 연결은 이전 점검에서 미완료로 인계 전에 재확인 필요.
로봇 runs/handoff_diagnostics/web-fsm-20261024_010143에 bag/launch.log/final.json 보존, 수집기 SIGINT 정상 종료 및 metadata 생성 확인. Action feedback 등의 embedded message definition 누락 경고가 있어 bag 해석 시 동일 ROS 인터페이스 설치 필요; 웹 결과/더미 journal은 별도 보존. PC Git 밖 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/web_fsm_20261024에 web.jsonl/dummy_journal.json/final.json. 코드·설정 변경/commit/push 없음.


### 2026-10-24 웹 수동 인계 조작 읽기 검토
사용자 요청에 따라 실제 배포 UI /assets/index-CM329H-i.js 및 GET /api/handoff-test, 기존 확보 worker와 수확 TransferMission을 대조. 버튼/POST/Goal/이벤트 실행 없음. 수확 dock_transfer 시작 버튼은 수확 ready/blocked/기존 작업 조건을 보며 운송 ready를 직접 요구하지 않는다. 앞선 운송 미연결만으로 수확 시작 전체를 금지한 설명을 정정한다. 수동 이벤트 4개는 대상이 다름: DOCK_READY/TRANSFER_COMPLETE→운송, DOCK_STABLE/TRANSPORT_CLEAR→수확. 수확은 DOCK_READY 후 DOCK_STABLE을 기다리고, 더미 배출 후 TRANSFER_COMPLETE를 보고하고 TRANSPORT_CLEAR 후 복귀한다. UI는 각 event_controls.allowed 및 수신측 service ready로 버튼을 활성화한다. 현재 수확 Action 미시작이라 이벤트 버튼 allowed=false. DOCK_STABLE/TRANSPORT_CLEAR는 상대 보고 확인 안내이며 운송 미연결 상태에서 수확 단독 수동 주입이 가능한지는 현재 상태 응답만으로 확정 불가. UI의 명시적 보고 없는 예외는 DOCK_READY 및 운송 단독 TRANSFER_COMPLETE이며 이를 수확측 이벤트에도 일반화하지 않는다. 코드/관제/실행 설정 변경 없음.


### 2026-10-24 01:37 웹 DockTransfer 진입 전 실패
사용자가 dock_transfer 전송. task DOCK_TEST_ca085300951941dca507d8ab3b92586a / transfer TRANSFER_TEST_a4e66bec76f04285b77b9ac18476c3c1. 웹 expected_count4(직전 적재2와 다름), 01:37:52.8→53.975 FAILED/status6/DEVICE_FAILED, rotate_to_transfer: 경로의 장애물/unknown 셀과 footprint 접촉/겹침. 수량 차이를 이번 오류 원인으로 단정하지 않는다. DOCK_READY 미수신·배출/복귀 미실행, 후속 이벤트 버튼 allowedfalse. 에이전트 이벤트/Goal 없음.
기존 상시 계측에서 build_body 및 동일시각 TF 확보 통과→capture 통과→plan:departure의 guard:departure에서 충돌검사 오류(약157ms)를 확인. 따라서 이동 경로 실행 전 계획 검사 실패이며 통신 미연결/TF조회 실패와 구분한다. 새 window 기준은 build_body를 통과했다. 현재 정지 odom30개, ERROR/readyfalse/load2; 영속 recovery_requiredtrue. 실패 뒤 수집한 일반/인계 costmap은 unknown0, 현재 footprint 및 +0.1rad 가상회전 검사통과(여유약0.101/0.095m). 이 사후 표본은 실패 당시 전체 departure 경로의 충돌 셀을 확정하지 않는다. 초기위치재발행·재전송·costmap clear·안전완화·재시작 없음.
로봇 runs/handoff_diagnostics/web-dock-20261024_0137에 기존 launch/trace/transfer 기록과 사후costmap/footprint/정지검사 보존. 실패는 이번 조회 시작 전에 종료되어 해당 순간 신규 rosbag 없음; 기존 상시 trace를 수집함. PC Git 밖 web_dock_20261024에 웹/정지/transfer 기록 이중 보존. 다음 버튼 누르지 말고 위치 유지 안내. commit/push없음.


### 2026-10-24 웹 인계 실패 경로·셀 오프라인 대조
사용자 무이동 원인 분석 승인. 성공 body-reentry-policy-nVLFxOy9 bag에서 departure guard 직전 odom/costmap/footprint/status 추출. 성공 costmap 수신은 guard보다 약13.8ms 전이며 실행 내부의 정확한 snapshot과 동일하다고 단정하지 않는다. 실패는 guard 당시 raw grid가 없으므로 01:38 사후 snapshot으로 재구성. 현 arc_path/ArcSpec 및 check_grid 실제 모듈 사용, ROS node/이동출력/서비스 없음. published footprint에서 반폭(.32000001,.27000003)m 확인 후 동일 .32/.27 형상 사용.
성공 manifest의 transfer_restore/handoff_runtime/handoff_planning 및 원본 body profile after SHA는 현재 로봇 소스와 동일, 해당 설치본도 소스와 동일. 새 FSM profile은 body_trial_enabled만 다름. 공통 arc_clearance PC/robot source/install SHA e0d163fa6925dbe9c36c6d7453504b6f2c1e0f19d851353230a375e7a970c5f1 동일. 따라서 확인한 경로 생성·guard 코드가 바뀌어서 생긴 실패라는 증거는 없음.

| 대조 | 기존 check_grid 결과 |
|---|---|
| 성공 당시 자세 + 성공 직전 grid | PASS, 보수적 여유 하한7.03mm |
| 이번 자세 + 실패 후 grid | 동일 충돌 오류 재현 |
| 성공 자세 + 실패 후 grid | PASS, 하한5.89mm |
| 이번 자세 + 성공 grid | 충돌 재현 |
| 성공 위치 + 이번 방향, 실패 후 grid | PASS |
| 이번 위치 + 성공 방향, 실패 후 grid | 충돌 |
| 성공 자세에서 map x만 이번 값, 실패 후 grid | PASS |
| 성공 자세에서 map y만 이번 값, 실패 후 grid | 충돌 |

교차 세션 변환은 각 정지 status(map)/odom 자세 쌍의 강체변환 추정이다. 동일 지도 사용을 확인했으나 완전한 실제 물리위치 일치를 보증하지 않는다. 성공 map출발(1.156382510,-.037112765,-.007371856rad), 이번(1.169581869,-.004505278,-.049429362rad): dx+13.20mm/dy+32.61mm/dyaw-2.41도. 방향만보다 y 위치 차이가 이번 저장자료의 실패를 설명하는 주된 요인. 도착 허용5cm/약3도와 인계 전체 원호 충돌 여유는 다른 계약: 일반 도착 성공만으로 인계 원호 실행 가능성이 보장되지 않음.

실패 후 재구성 경로는 총80표본(0~79), 최초 겹침 표본index30/회전34.177도(실제 연속 첫접촉 각도로 해석 금지). odom차체(1.193479809,-1.007701638,-.935830259), grid셀(ix145,iy121),값254(lethal),해상도.02m,셀중심odom(1.609999935,-1.110000054),셀범위x[1.599999935,1.619999935],y[-1.120000054,-1.100000054]. map 추정 차체(1.11262176,-.01897820),셀(1.25108636,.38695472). 셀중심의 차체좌표(.329419,.274659)로 전방좌측 모서리(.32,.27)와 셀 면적이 겹침. 현재 footprint만은 안전하나 회전 중 앞왼쪽 모서리가 map+y 장애물 띠에 닿음. 해당 map 위치는 같은 many_farm.pgm의 점유 픽셀0이며 PC/로봇 map SHA c16144d12bf45bafbb122f2fa34bd0243a39f25e525349e92195fc0223ae410b 동일. 실제 현장 물체 종류와 실패 순간 정확한 셀 ID는 확정하지 않음. 사후 grid unknown0이므로 이번 재현은 unknown이 아니라 lethal 셀.

운영 코드/안전수치/초기위치/costmap clear/journal/reset/실제이동 변경없음. 현 로봇은 복구필요 상태 유지. 권장 후속은 일반 도착 허용치를 일괄 강화하거나 footprint를 축소하는 것이 아니라, window 도착 후 인계 전용 진입 전체경로 검사를 앞당기고 필요시 기존 안전검사를 통과하는 시작자세 보정 경로를 별도 계획하는 것(제안이며 미구현/미승인). 무조건 재시도 금지.
근거: PC /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/web_dock_20261024/offline/{comparison.json,additional.json,success_snapshot.json,departure_comparison.png,plot_analyze.py}; 로봇 web-dock-20261024_0137/{analyze_departure.py,offline/}. 새 회귀/ROS실기시험 아님, 저장자료 기하 재생 검증. commit/push없음.


### 2026-10-24 padding 64×54 / 62×52 오프라인 비교(미적용)
사용자 실측60×50cm 전달 및 비교 검증 승인. 실제 ROS parameter GET으로 일반/인계 local_costmap 모두 footprint=[±.30,±.25],footprint_padding=.02 확인. nav2.yaml 원본도 동일. handoff_server_config는 일반 local costmap 설정을 복사하고 runtime alignment_footprint는 반폭에 padding을 더함. 추가 이중 padding 증거 없음. 발행 footprint64×54cm와 일치.
기존 동일 ArcSpec/arc_path/check_grid로 80표본 및 표본 사이 연속 swept-footprint 검사. 성공 직전 grid:64×54 PASS(여유 하한7.026mm),62×52 PASS(21.210mm). 실패 후 grid:64×54 FAIL(index30부터12표본 접촉),62×52 PASS(연속 여유 하한1.660mm,표본 최소거리4.291mm). 이는 padding 포함 도형과 저장된 셀 간 기하 여유이며 물리 실측 여유나 위치오차 보장은 아님. 실패 순간 grid가 아니라 사후 snapshot인 한계 유지. 전체 인계/벽정렬/이탈/복귀 검증 아님. grid는 고정하고 검사 도형만 비교했으므로 padding 변경 후 Nav2가 재생성하는 costmap·실시간 센서 변화까지 검증하지 않음.
일반 주행/운영 profile/Nav2 parameter/충돌 코드/기동/이동 변경 없음. 실기/적용 전 사용자 안내 유지. 향후 인계 전용 조정 시 공용 nav2.yaml을 일괄 변경하면 일반 주행도 바뀌므로 금지. launch가 만드는 인계 costmap과 runtime이 계산하는 body_footprint에 동일한 별도 설정을 전달해야 하며, ROS padding만 동적으로 바꾸면 발행 footprint 크기 불일치 보호에 걸림. 설정 경계 변경은 별도 승인 후 진행.
PC 증거 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/web_dock_20261024/padding_comparison/{padding_comparison.py,padding_comparison.json}, 원본 입력 SHA 포함. commit/push없음.


### 2026-10-24 인계 전용 padding 후보 구현·오프라인 검증(실행본 미적용)
사용자 백업/62×52 후보/오프라인 검증 승인, 적용·재기동·이동 전 안내 요구. Git 밖 handoff_padding_candidate_20261024/backup/robot_before.tar.gz에 로봇 최신3소스/nav2.yaml/FSM JSON/터미널 래퍼 백업. 후보만4파일 수정: handoff_server_config에 선택형 footprint_padding(m, 기본None=기존상속), handoff_runtime와 harvest.launch 양쪽에서 cfg.get 전달, 후보 FSM JSON .01. 동일 구성 함수가 인계 costmap과 내부 body_footprint를 만들며 기본60×50+면당1cm=62×52. 일반 nav2 원본·기존 controller·충돌 검사·취소/소유권·완료기준 불변.
오프라인15개PASS: 일반 입력 원본 불변 및 기본64×54 보존, 후보 costmap/runtime동일, padding 외 bundle전체동일, 비정상6종값거절, launch/runtime전달 AST확인, 두형상 및 크기불일치보호, 성공/실패 저장자료4조합. Python AST통과. ROSlaunch/노드통합/실기/전체복귀 미검증, 후보실기안전확정 아님. 정지후 grid 후보 하한1.66mm 한계유지.
로봇 운영3소스/FSM JSON 해시가 manifest.before 그대로임을 후속조회확인. 운영 적용·빌드·재시작·이동/param set 없음. 기존 recovery_required 기록은 그대로이며 후보가 복구상태 해제를 해결하지 않음. 실제 적용시 설치본추가백업,동일파일해시확인,4파일일괄반영,harvest_robot/farm_bringup빌드 및 사용자기동조율 필요. 원복은 백업 원본복원후재빌드(현재미적용이므로불필요).
PC외부 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/handoff_padding_candidate_20261024/{README.md,candidate.diff,manifest.json,test_padding.py,tests.log,backup/robot_before.tar.gz}. 변경이유·범위·한계·원복기록. Git운영소스는변경하지않음,commit/push없음.


### 2026-10-24 02:00 인계62×52 실행본 적용·사용자 재기동 대기
사용자 명시 승인: 기존백업보존/실행본적용/복구상태처리/사용자기동. 사전odom91표본0·진행task없음 확인후 기존launch201479 SIGINT. 드라이버/controller 종료,수확201516은60초종료유예초과로launch가SIGTERM하여종료;Destroyable 종료경고보존. 정상SIGINT종료로미화하지않음. 모든관련런치/차체실행종료확인후사용자에게스테이션이동허용,사용자기존위치·방향복귀확인받음.
로봇 Downloads/handoff_padding_deploy_20261024에후보/기존백업유지,deployment_backup/install_before.tar.gz 및원본transfer.json추가. before해시4개확인후후보3소스+FSM JSON만반영. harvest_robot/farm_bringup colcon build2패키지성공. 실제설치3파일+JSON after해시모두일치,설치모듈구성실행에서인계padding.01/body반폭.31,.26,일반.02및입력원본보존검증. 최초검증도구상대경로오류를절대경로로수정후통과;제품코드오류아님.
사용자스테이션복귀확인후노드정지상태에서실패task DOCK_TEST_ca085300951941dca507d8ab3b92586a 1건만recovery_required=false로수동종결. FAILED/activefalse/원래ID·시각보존,manual_recovery근거·확인시각추가. 원본journal+receipt해시보존,기록삭제/가짜SUCCESS/중복ID우회없음. 이후새window도착/더미수확필요. 자동복구기능변경아님.
현재런치미기동;laun --check 충돌PID없음. 기존로봇zen201974/dzen202048유지,PC더미/전용bridge도유지하므로중복기동불필요. 사용자로봇터미널1 source ~/.bashrc;laun → 준비후터미널2 source ~/.bashrc;vinit → 웹최신상태확인통보 순서. 자동이동/Action/이벤트없음. 웹표시만으로새ready판정하지않고새boot/형상/정합을후속검증. 운영PC소스는후보외미변경,로봇소스와차이있음;commit/push없음. 원복시프로세스종료/after해시확인후백업소스·profile복원/재빌드,수동복구이력은별도보존. 설치검증·빌드는실기검증아님.
근거로봇배포폴더build.log/verification.json/applied.json/manual_recovery_receipt.json/shutdown.log및PC외부handoff_padding_candidate_20261024사본.


### 2026-10-24 02:04 재기동 후 웹 브리지 재발견 실패
새수확PID222078/boot1f03d21959f04981a0ad333e465d557a 직접조회IDLE/ready/odom452개0,PC더미4연결정상. 웹은이전boot종료상태약281초정체및수확Action/event false. 허브bridge201974는실행중이나로그가이전노드undeclare에서멈춰새노드재등록확인안됨. dzen202048은더미연결정상. 프로세스유지만으로웹연결유지를기대한안내를정정. 사용자zen터미널Ctrl+C종료후source ~/.bashrc;zen만재기동안내. laun/vinit/dzen/PC더미재시작불필요. 에이전트재시작/이동없음,웹복구는사용자기동후재확인필요.


### 2026-10-24 02:05 zen 재시작 후62×52 실제 실행 확인(무이동)
사용자zen재시작/웹확인후GET2회수확상태boot1f03d21959f04981a0ad333e465d557a일치,sequence142→145,age.3~.4초. 웹수확/복귀/DockTransfer와수확TransferEvent readytrue,운송false. 로봇직접IDLE/ready/load0/진행task없음,odom452표본0,PC더미HarvestTask/Discharge/prepare/stop탐색정상. 출력/odom publisher각1개.
실제ROS parameter 일반padding.02/인계.01,handoff_config새FSMprofile/body_trialfalse 확인. published footprint 점간거리로일반64×54/인계62×52검증통과(인계내부형상은설치모듈+선택profile구성검증과대조,메모리직접덤프아님). 최신일반/인계costmap unknown0,현재정지/+0.1rad가상회전검사모두PASS. scan626점의map점유셀거리중앙19.45mm,p90 37.69mm,5cm이내99.36%,10cm이내100%. 정지정합일관성검사이며전체경로안전/실제참위치보장아님.
초기위치재발행/costmapclear/이동/Goal/이벤트/설정변경없음. 재기동으로새window기준/더미수확필요,인계실기미검증. 로봇runs/handoff_diagnostics/padding-live-readonly-20261024와PC외부handoff_padding_candidate_20261024/live_check에근거보존. commit/push없음.


### 2026-10-24 02:11 웹 window 재주행 완료·더미 수확 거절
사용자 웹 재전송 job72f522fe3edb4e9586fb785d9943e0b6, task TEST_8e2c1cd3e3ff_SEC01_TASK001. 02:09:49 수락 후 일반 controller 두 goal 모두 완료(02:10:44.509/48.976). 02:10:50.338 PC더미가 busy/recovery/control로 Goal 거절, 웹 FAILED/status6/ARM_REJECTED, 수확0. 더미 journal은 시험 전후 동일하며 최상위 recovery_required=true가 이미 시험 전부터 존재. 서비스/Action 탐색 성공만 확인하고 더미 업무 준비 상태를 확인하지 않은 사전점검 누락이다. 같은 task/window ID의 과거 SUCCESS도 보존돼 있어 복구 후에도 duplicate ID 거절 조건이 남는다. 실제 거절 로그는 duplicate ID가 아니므로 구분한다.
설치 communication.py는 전체 SUCCESS일 때만 remember_window를 호출하므로 이번 요청은 새 인계 도착 기준 저장 경로에 진입하지 못했다(메모리 직접 덤프 아님). 최종 ERROR/readyfalse/ARM_TRAVEL_NOT_READY/load0, pose(1.175342892,-.010742761),yaw-.033464729. 실패 후 odom152표본 비영0. 웹 harvest queue는 자동 paused=true. 인계/재이동/복구서비스/초기위치 요청 없음; 성공코드·설정 불변. 수집기만 SIGINT 종료.
근거: 로봇 runs/handoff_diagnostics/web-window-padding-20261024_020913의 bag/launch.log/final.json, PC Git 밖 jetson_dummy_pc_20261023/web_window_padding_20261024_020920의 시험 전후 journal/result_web.json. 다음은 더미 복구 및 로봇 ARM_TRAVEL_NOT_READY 해제 계약을 확인하고 기존 이력을 보존한 새 작업 ID 시험 절차 준비. 이번 실패를 62×52 인계 충돌 실패로 해석하지 않는다. commit/push 없음.


### 2026-10-24 02:14 PC 더미 복구 완료·수확 노드 재기동 준비
사용자 복구/중복ID 처리 승인으로 PC177에서 실제 RuntimeStatus의 dummy/비활성/접힘·정지·박스닫힘을 확인하고 원본 journal 백업 후 기존 Recover(DEVICE_AND_LOAD_RECONCILED) 호출. recover/prepare 모두success, IDLE/readytrue/recoveryfalse, records 전후 완전동일 검증. 실제팔 복구 아님; 과거 counts2는 새 적재가 아니다. 기존 task/window 성공ID 보호는 유지, 동일 좌표(1.186,-.035,0)/수량2의 새 DUMMY_RETRY_5a0e47f4e3bd_TASK001/W001 자료 생성·기존ID 비충돌 확인, 미전송. 기존 웹 retry는 같은 ID이므로 다시 보내지 않는다. 관제 현재 기본목표1.6006447과 혼동 금지.
설치 mission.py는 ARM 시작시 arm_travel_readyfalse, 실패후 communication.py가 blockedtrue로 설정하며 이를 해제하는 서비스 없음. 코드/메모리 보호값을 우회하지 않고 수확 노드 재기동 필요를 사용자에게 알림. 재기동/종료/이동은 미실행, PID222078 유지. 로봇 Downloads/harvest_recovery_prepare_20261024_021431에 현재argv/ROS환경/params백업 및 NOT_EXECUTED 계획 보존. 전체AMCL을 유지하는 수확노드 단독 재기동 절차는 다음 단계에서 종료·감독정책 확인 후 진행; 현재window에서 스테이션vinit 금지. PC외부 recovery_20261024_021328에 journal전후/상태/응답/검증/새작업/PROCEDURE 보존. 향후 사전검사는 Action탐색뿐 아니라 더미RuntimeStatus/prepare/ID미사용까지 확인한다. 성공코드/설정/중복방지 변경·commit/push 없음. 로봇 오류 해제와 새window기준 저장은 아직 미완료.


### 2026-10-24 02:18 수확 노드 단독 재기동·웹 미복구
사용자 명시 승인으로 정지/비활성 작업 확인 후 PID222078만 SIGINT 정상종료 확인. 동일 실행argv/백업params SHA/ROS환경으로 PID228333 시작. Nav2 일반222051/인계222066·AMCL222050 및 hubbridge223152/dummybridge202048 유지. 초기위치/Goal/이동 없음. 직접 ROS 상태 새boot c7b0174f16614d1795aa74721ca248be, IDLE/readytrue/load0, ARM_TRAVEL_NOT_READY해제, pose(1.175342892,-.010742761),yaw-.033464729 유지. odom452표본0, 출력publisher1, 더미Action·service탐색정상. PC177 RuntimeStatus readytrue/recoveryfalse/접힘정지닫힘 및 실제prepare success확인. 신규 window기준은 아직 없음.
웹 GET2회에서는 이전boot1f03...의ERROR가51→88초정체, 수확/복귀/인계Action·수확event readyfalse. 수확복구와 웹연결복구는 구분; hubbridge는살아있으나 재시작하지 않음. 사용자 zen터미널 Ctrl+C→source ~/.bashrc→zen 재시작 후 새boot/Action을 다시 확인할 단계. laun/vinit/dzen 재실행금지.
이번 수확 PID228333은 기존 ros2 launch 자식이 아닌 별도 세션이다. 이후 전체 종료 때 기존 laun Ctrl+C만으로 종료된다고 가정하지 말고 이 PID/starttick·명령 확인 후 별도 종료해야 한다. 새 로그 Downloads/harvest_recovery_prepare_20261024_021431/harvest_restart.log 및 started.json, PC외부 recovery_20261024_021328/restart_robot_check.json/restart_web_check.json/after_restart_dummy.json 보존. 초기 검증 도구의 base환경변수누락1회 수정후검증통과, 운영설정변경아님. 코드/설정수정·commit/push없음.


### 2026-10-24 02:19 사용자 zen 재시작 후 웹 연결 복구 확인
읽기 전용 웹 GET2회에서 새boot c7b0174f16614d1795aa74721ca248be 확인, sequence140→142, age0.7→0.5초. 수확/복귀/DockTransfer Action 및 수확TransferEvent readytrue. 직접 ROS와boot일치, IDLE/ready/적재0/task없음, odom453표본 비영0, 출력publisher harvest_motion_server1개 및 더미Action/service탐색정상. 위치·방향 유지. 웹수확대기열 pausedtrue 유지, 운송Action/event false. 연결탐색과실행완료구분. 초기위치/이동/Goal/이벤트/설정변경없음. 새window기준은아직미확보, 기존ID재시도금지·새시험요청자료미전송. PC외부recovery_20261024_021328/zen_reconnected_web.json 및 zen_reconnected_robot.json에근거보존. commit/push없음.


### 2026-10-24 02:21 새 ID 동일 window 재요청 사전검사 차단(미전송)
사용자 새ID 수확 재시험 승인 후 이동 전 현재 상태·실제 로봇설정·설치된 straight_plan을 읽기전용으로 검증. IDLE/ready/odom121표본0, 현재(1.175342892,-.010742761),yaw-.033464729. 동일 목표(1.186,-.035,0)에 forward10.657mm/lateral24.257mm로 path_heading1.156845rad(66.28도)가 설정.087266rad(5도)를 초과, APPROACH_RECOVERY_REQUIRED:path_heading 재현. 위치오차26.49mm/방향1.92도는 일반 도착5cm/3도 안이지만 staged_navigation.resume_current→CorridorNavigator._plan_current에서 먼저경로검사를수행한다. 이동Action/더미수확요청을보내지않았으며새ID미사용·도착기준미저장·인계미실행. 안전조건완화/설정변경/초기위치없음. 근거로봇runs/handoff_diagnostics/same-window-preflight-20261024_022059/preflight.json.
현재코드의무이동도착확인경로가이번수확재개경로에연결되지않음. 추후수정은수확재개시구간/목표/정지/동일시각TF/도착을검사하고성공시이미도착결과를반환하도록검토하되미적용. 이미도착으로임의성공시키거나새기준을주입하지않는다. 실행요청이막힌사실과코드수정필요를사용자에게알림. 기존백업/기록유지,commit/push없음.


### 2026-10-24 02:24 스테이션 수동 이동 전 전체 로봇 실행 종료
사용자 승인으로 정지/비활성 확인 후 별도수확228333과런치222032에SIGINT. 드라이버/Nav2/AMCL/수확 종료 확인 후 잔여 카메라·태그 자식8개에 PID/starttick검증후SIGINT하여 런치포함활성잔존0 확인. SIGKILL없음. 초기프로세스조회도구의공백포함comm 파싱오류는신호전발생했으며수정후재검증수행. 설정3파일SHA불변, 기존로그유지·종료로그사본보존. bringup exit1/route_preview ExternalShutdownException 및 별도수확 Destroyable 종료경고는보존,깨끗한종료로보고하지않음. Zenoh브리지·PC더미는이번종료대상아니므로유지. 초기위치/이동/Goal없음.
근거 로봇 Downloads/station_shutdown_20261024_022321/{processes_before.json,stop_check.json,config_sha_before.json,verification.json,launch_shutdown.log,harvest_shutdown.log}. 이제 사용자에게기존스테이션위치·방향으로수동이동가능안내. 이동후확인전재기동/초기위치발행금지. 다음실기전더미실제ready/prepare와새ID미사용확인필수. 기존기록/설정유지,commit/push없음.


### 2026-10-24 02:26 전체 통신 프로세스 종료 확인
사용자 승인으로 남은 로봇 hubbridge229149/dummybridge202048 및 PC더미130190/전용bridge130248에SIGINT 정상종료, 양측 재조회 잔존0. 기존 로봇런치/별도수확/드라이버도 잔존0 유지. PCjournal/bridge설정/pc.bash 원본백업과전후SHA불변, 로봇bridge설정SHA불변. 기록삭제/재기동/이동/초기위치없음. PC외부full_shutdown_20261024_022542 및 로봇Downloads/station_shutdown_20261024_022321/bridges_*에근거.
사용자기동순서: PC별도터미널 pc.bash dummy→pc.bash bridge, 로봇별도터미널 laun→실제스테이션위치방향확인후vinit→zen→dzen. 모든터미널전경유지. 스테이션이동완료는아직사용자확인전이므로vinit조건명시. 웹표시후ready/prepare/정합/costmap/새ID미사용을확인하고작업전송은그후. Gitcommit/push없음.


### 2026-10-24 02:28 스테이션 전체 재기동 후 무이동 준비 확인
사용자 스테이션이동/기동/웹확인 후 점검. 새수확boot089359b65d864d7ba18df20bfc648356 웹/직접일치, 최신age0.7초, 수확/복귀/DockTransfer/수확event readytrue; 대기열pausedtrue유지. IDLE/ready/load0/task없음. PC더미새boot02fc1a5e89db457b83230c1391021382의RuntimeStatus readytrue/recoveryfalse/접힘정지닫힘, prepare success. 준비한DUMMY_RETRY_5a0e47f4e3bd_TASK001/W001은더미영속기록미사용·웹job없음,목표1.186,-.035,yaw0/수량2확인.
scan628점지도점유거리중앙11.89mm,p90 25.66mm,5cm이내100%,scanage.418초;odom300표본비영0. 일반64×54/인계62×52 published footprint검증,최신costmapunknown0,정지및+0.1rad가상경로검사통과(최소여유하한일반.190/.179m,인계.200/.190m). 실제회전없음,전체경로안전보증아님. 출력/odom publisher각1,body_trial서비스없음. 초기위치재발행/clear/이동/Goal/이벤트/설정변경없음. 로봇runs/handoff_diagnostics/station-restart-check-20261024_022735,PC외부station_restart_check_20261024_022735에근거. 새수확/인계는아직미실행,commit/push없음.


### 2026-10-24 02:31 웹 새 작업 의도와 실제 ID 불일치·중복 거절
사용자는새작업전송이라고알렸으나관제GET의실제job eb3be2705425473e8944769e191718a7은 retry_of72f522fe3edb4e9586fb785d9943e0b6,task/window기존TEST_8e2c1cd3e3ff_SEC01_TASK001/W001동일. 어떤UI조작/생성단계에서재사용됐는지는미확정이며사용자오조작으로단정하지않는다. 02:29:03.259전송→일반controller2회목표완료→02:30:08.010더미 duplicate ID거절,웹ARM_REJECTED/status6/수확0. 이전busy/recovery/control실패와구분. PCjournal시험전후동일,신규완료없음.
최종ERROR/ARM_TRAVEL_NOT_READY/load0,pose(1.182954562,-.014297734),yaw.007390011,odom122표본비영0. 전체성공전remember_window미호출및실패invalidate경로로새인계기준미확보. 에이전트이동/Action/재시작/초기위치/복구호출없음. 새준비ID는여전히미사용. 재전송/인계보류,실제웹생성·선택·ID전달경로읽기분석필요.
로봇runs/handoff_diagnostics/web-new-window-20261024_022903에bag/launch/final,PC외부web_new_window_20261024_022912에web_latest/dummy_before/after/log보존. 수집기구독완료는요청전송직후이므로수락 이전부터의 완전 기록이라고 주장하지 않음. 기존launch/웹타임스탬프로수락확인. 수집기만SIGINT종료,설정/기존기록유지,commit/push없음.


### 2026-10-24 PC 더미 반복 수확 후보 준비·오프라인21개 통과(미적용)
사용자승인범위로Git밖 jetson_dummy_pc_20261023/repeat_harvest_candidate_20261024에원본server/journal백업후후보작성. --allow-repeat-harvest 명시옵션에서만 Trigger repeat_last_harvest 서비스생성,유휴/복구완료시마지막terminal수확ID에300초1회허용. 요청timestamp외payload동일검사,활성중중복/만료/배출반복거절,허용권비영속·stop/recover시취소. 이전record전체는historyappend,최신records/attempt_id와원자저장후수락. 저장실패차단. 무조건동일ID재실행이나기존기록삭제없음.
후보실제메서드AST기반ROS없는오프라인21PASS,20개병렬요청중1개수락/반복이력/취소/정지/복구/저장실패/제어실패검증. ROS환경import/--help정상. DDS/service/Action실기/웹반복미검증. 명시허용구간에같은payload의늦은재전달과의도된새요청구별은프로토콜상보장하지않음. 허용서비스는PC177로만관리,브리지설정불변.
현재실행원본server SHA불변,수확성공코드/실행설정/로봇/PC프로세스재기동·이동없음. 실제운영적용전안내필요. 기존수확노드ARM_TRAVEL_NOT_READY와동일window재개제약은별도남음. 후보README/candidate.diff/tests.log/tests.xml/manifest에기록,원복시history포함journal전체백업필수. commit/push없음.


### 2026-10-24 PC 더미 반복 후보 운영 적용·무이동 통신 검증
사용자승인으로PC더미152623만SIGINT종료,server/pc.bash/journal백업후후보server적용·pc.bash에--allow-repeat-harvest추가. PID156603으로기동,기존journal유지. PC177 가상팔Action직접검증9항목통과:prepare/RuntimeStatus정상,기존ID무허용거절,반복서비스1회허용/중복허용거절,실행중5중복Goal모두거절,동일웹ID1회SUCCESS수확2,완료후재요청거절,이전record정확archive/다른record불변,사후prepare성공. 허용권소비완료. 로봇수확FSM/주행/적재/window기준성공을의미하지않는다. 기존수확코드/로봇설정변경없음.
근거PC외부repeat_live_20261024_023651/{server.py,pc.bash,journal.json,applied.json,launcher.log,result.json,checks.json,journal_after_test.json,RECOVERY_PROCEDURE.md}. 후보21오프라인PASS는앞선별도기록. 현재반복서비스는PC177에서만노출,웹/로봇bridge설정불변.
작업초기수확232327존재확인했으나최종조회에서로봇수확/드라이버/브리지및PC브리지없음,ROSstatus/odom표본0. 에이전트는PC더미152623외신호/재시작안했으며다른프로세스종료원인미확정. 로봇정지속도검증성공으로보고하지않음. 현재더미156603만정상확인,수확복구는절차준비만수행. 로봇실행상태/위치재확인→사용자가선택한스테이션전체재기동절차→더미실제ready/prepare→1회반복허용→웹전송순서검토. 현재window에서vinit금지. 사용자에게현재프로세스부재알림,임의재기동/이동없음. commit/push없음.


### 2026-10-24 02:40 사용자 전체종료/스테이션이동 후 PC더미 잔존 종료
사용자가직접로봇/브리지종료·스테이션이동했다고확인하여앞선프로세스부재맥락확인. 승인하에남은PC더미156603만SIGINT정상종료. PC전체journal백업후바이트불변/과거history1건보존검증. PC더미/브리지및로봇수확/드라이버/런치/컨트롤러/태그관련조회잔존없음. 근거PC외부repeat_shutdown_20261024_024035. pc.bash dummy는--allow-repeat-harvest반영확인. 재기동/이동/초기위치/반복허용없음.
사용자재기동순서PCdummy→PCbridge→로봇laun→스테이션vinit→zen→dzen안내. 사용자웹연결확인후에더미실제ready/prepare·정합/costmap·수확ID확인하고PC반복허용서비스호출예정. 현재는허용권없으며웹작업전송보류. 기존기록/설정유지,commit/push없음.


### 2026-10-24 02:43 웹 동일 작업 1회 반복 허용·수집 시작
사용자기동/웹확인및반복허용승인후무이동검사. PC더미readytrue/recoveryfalse/prepare성공,기존웹TEST_8e2c1cd3e3ff_SEC01_TASK001/W001의ID·좌표1.186,-.035,0·수량2와더미원요청완전일치확인. 02:43:17 KST repeat_last_harvest success로1회허용,유효기간300초(02:48:17경). 에이전트Goal/이동없음. 사용자기존웹57번작업1회재전송대기.
새수확boot1ba12c86ca5746faa244aa8428e4c4ce IDLE/ready/load0,odom301표본0. scan624점중앙27.10mm/p90 42.92mm/5cm이내95.83%/10cm100%,정지정합일관성표본. 일반64×54/인계62×52 footprint검증,최신costmapunknown0,현재자세및+0.1rad가상경로검사PASS(일반.193/.179m,인계.206/.190m). 출력/odom각publisher1. 웹수확Action readytrue/대기열pausedtrue,웹조작없음.
로봇runs/handoff_diagnostics/repeat-ready-20261024_024224에정합/costmap/bag(15분한도PID는recorder.json)수집중,PC외부current-web-repeat-trial이가리키는web_repeat_trial폴더에원journal/웹/prepare/repeat_permit보존. rosbag embedded definition누락경고보존. 전체경로/수확/인계성공미확인. 초기위치/설정변경/commit/push없음.


### 2026-10-24 02:45 동일 웹ID 반복 수확 실기 성공(PC더미)
사용자웹전송jobfd062f1935b2476ab72e3d4ed5ebb8c3,기존TEST_8e2c1cd3e3ff_SEC01_TASK001/W001. 02:43:43수락→SECTION_APPROACH/WINDOW_MOVE→02:44:45.148 SUCCESS/status4/수확2/실패0. 더미명시1회허용정상소비,신규attempt3142dfa0292c49d69f17b456c9143632와terminalSUCCESS/recoveryfalse,history1→2/이전record정확보존검증. 로봇FSM전체성공이며실제팔대신PC더미범위.
실제task_events의arrival acceptedtrue,위치29.947mm/방향.042854rad(2.46도),동일stamp1792777483444898266. 설치communication.py에서remember_window→handle.succeed순서와이번성공결과로새도착기준저장경로완료확인(메모리직접덤프아님). 최종IDLE/ready/load2/task없음,pose1.175381672,-.006764902,yaw-.044919955,odom121표본0/출력publisher1. 인계/배출/운송이벤트/초기위치/재시작없음. 현위치유지·인계버튼보류안내. 인계62×52전체실기는아직미검증.
로봇runs/handoff_diagnostics/repeat-ready-20261024_024224의bag/task_events/final/launch,PC외부web_repeat_trial_20261024_024251의web_monitor/journal전후/task_events/final보존. 수집기만SIGINT정상종료·metadata확인. 기존설정/코드/commit/push변경없음.


### 2026-10-24 02:48 웹 인계62×52 실기 준비·사용자버튼대기
사용자인계시험승인(버튼은사용자)후기존성공window/동일boot1ba12...유지,IDLE/ready/load2/odom정지30표본확인. 일반64×54/인계62×52 footprint와최신costmapunknown0,현재정지및+0.1rad가상경로PASS(인계여유.1266/.1156m). 전체departure경로사전검증은아니며실행중기존guard유지. cmd_vel_nav/odom publisher각1,body_trial서비스없음. 더미RuntimeStatus ready/recoveryfalse/prepare success,Discharge탐색정상. 웹DockTransfer/수확event readytrue,운송false/오래된상태. 이번안내범위는수확인계진입→DOCK_READY이며운송실물완료주장없음.
웹UI문구상현재실행중job없을때다음start_dock은새transfer ID생성. 과거transfer ID는로봇journal에보존돼중복거절되므로전송후새ID확인필수. 수량은현재load2에맞춰2안내. 에이전트웹클릭/Goal/이벤트/이동없음. 후속버튼은DOCK_READY확인뒤별도안내.
로봇runs/handoff_diagnostics/web-dock-62x52-20261024_024737에현재costmap/footprint/정지기록및bag수집시작(PID240851,900초한도),PC외부current-dock-pc이가리키는web_dock_62x52폴더에웹/원journal/더미준비기록보존. 기록정의누락경고는기존과동일보존. 기존코드/설정/commit/push변경없음.


### 2026-10-24 02:49 인계62×52 실기 계획검사 실패
사용자dock_transfer전송새task DOCK_TEST_2264a8ea62be40819b43e5c1f92f4f32/transfer TRANSFER_TEST_198c841110ff41cdb52fc910be349faa/수량2. 02:48:23.502요청→25.061FAILED/status6/DEVICE_FAILED,rotate_to_transfer:경로의장애물/unknown셀과footprint접촉겹침. ID중복아님. 내부trace build_body13.25ms/동일시각TF완료,capture810.60ms완료후plan:departure→guard:departure479.23ms에서충돌검사실패. 인계경로controller실행전실패,DOCK_READY/배출/복귀미수행.
현재ERROR/readyfalse/load2,동일pose유지,사후odom122표본0. PCdummy records/history전후동일·신규배출없음,최상위recoveryfalse→true는실패정리중정지요청과부합(서비스원인추적미완료). 이전허용수확성공기록보존. 이번62×52는현재정지자세통과와달리전체진입계획실패. 원인셀·경로지점은아직재구성전이며추가완화/재시험금지.
로봇runs/handoff_diagnostics/web-dock-62x52-20261024_024737에실패시각bag(costmap/TF/odom/Action),failure_trace.jsonl2493행/launch/transfer/final보존;수집기SIGINT정상종료metadata확인. PC외부current-dock-pc폴더web_latest/journal전후보존. 후속버튼/이벤트/재전송/초기위치/재기동/설정변경없음. 다음은이번실패시점grid+path를과거성공/오프라인후보와대조. commit/push없음.


### 2026-10-24 02:48 실패와 과거 성공의 62×52 교차 재구성
사용자의 동일 위치인데 실패한 이유 확인 요청에 따라 저장된 bag과 설치된 경로/충돌 검사로 오프라인 대조했다. 과거 성공 대비 현재 map 추정 자세는 x +18.999mm, y +30.348mm, yaw -2.151도다. 모두 62×52 형상으로 검사하면 과거 자세+과거 grid PASS(여유 하한21.21mm), 현재 자세+현재 grid FAIL, 과거 자세+현재 grid FAIL, 현재 자세+과거 grid FAIL이었다. 따라서 이번 실패는 자세 차이만으로 설명할 수 없으며 costmap 표현 차이도 판정에 영향을 준다. 실제 물체가 바뀌었다거나 localization 오류라고 확정하지 않는다.
현재 재구성 경로의 첫 접촉 표본은 90도 departure 중 약77.47도(index68/79), 2cm grid 셀(103,118), 값254(lethal)이다. 셀 중심 map 환산 추정은 (1.25187,-0.44943)m. 실제 로봇이 그 지점까지 움직였다는 뜻이 아니라 실행 전 경로 검사 결과다. unknown 때문이라는 해석은 이 표본에 해당하지 않는다.
한계: 사용 grid는 guard 시작166.13ms 전 수집 표본이며 내부에서 사용한 객체의 정확한 복사본은 아니다. 교차 좌표변환은 정지 시 map/odom 자세로 재구성했다. 센서 관측/정합/rolling grid 표현 중 어떤 원인이 grid 차이를 만들었는지는 추가 확인 대상이다. 이전 62×52 후보의 1.66mm 여유 통과는 이전 실패 자료에 한정되며 이번 실기 통과를 보장하지 않았다.
근거: 로봇 runs/handoff_diagnostics/web-dock-62x52-20261024_024737/offline/{failure_snapshot.json,comparison.json}. 코드·설정 변경, 이동, 재시작, commit/push 없음.


## 2026-10-24 성공 시험 이후 통신 연동 변경 추적 — 읽기 전용 대조

사용자 요청: 성공 당시와 통신 연결 후 바뀐 코드·실행 조건을 추적. 기준 PC HEAD cf870daa, 로봇 body-reentry-policy-nVLFxOy9의 config/manifest 및 통신 적용 직전 pc_dummy_fsm_candidate_20261023/backup을 사용했다. 현재 수확 PID237742의 argv, 실제 /tmp/launch_params_l6w54ilb, 환경도 읽었다. 이동·재시작·제품 소스/설정 변경 없음.

### 직접 확인한 변경

| 대상 | 성공/연동 전 → 현재 | 이번 충돌과의 관계 |
|---|---|---|
| harvest.json completion_policy | ARRIVAL_ONLY_NO_HARVEST → ARRIVAL_THEN_ARM, arm_action 추가 | 도착 후 더미 완료까지 기다린 후 window 기록. 원호 식 자체 변경 없음 |
| transfer 설정 | 준비/정지 서비스 연결, discharge_mode action, 배출 Action 연결 | prepare 뒤 build_body, rotate_to_transfer에서 body.start('enter') 호출 |
| handoff profile | body_trial_enabled true → false | BodyTrial 서비스 대신 DockTransfer FSM 진입. 내부 build_body/enter/capture/planner/guard는 공통 |
| 최근 padding 승인 | 인계 .02 → .01, 내부·Nav2 동일 64×54 → 62×52 | 실제 변경. 일반 설정은 .02 보존. 고정 grid 도형 비교만으로 재생성된 costmap의 동등성을 보장하지 않음 |
| 환경 파일 | harvest_config 경로만 후보로 변경 | map/nav/navigation policy/tag 설정 경로는 연동 전과 동일 |
| 대기/실패 관리 | BodyTrial 외부 대기240초, FSM operation120초·서비스 준비·영속 journal | 운영 경로 차이지만 이번 약0.48초 guard 충돌 실패는 이 timeout 때문이 아님 |

연동 전 백업 SHA의 수확 Python43개 중41개 현재 일치. 다른2개는 handoff_runtime.py의 footprint_padding 인자 전달과 handoff_server_config.py의 선택형 padding 처리/값 검증뿐이다. PC 성공 커밋 대비 harvest.launch.py도 같은 인자를 전달하는 변경만 있다. 현재 로봇 harvest43개와 farm_navigation25개는 소스/설치본 모두 바이트 일치. 현재 프로세스는 이 설치 경로와 HANDOFF_TF_EXECUTOR=dedicated를 사용한다. 과거 메모리 로딩 전체를 직접 재현한 것은 아니며 당시 manifest/백업을 근거로 비교했다.

PC와 로봇의 공통 Nav2/주행정책/route_server 및 지도 YAML/PGM/graph6개 SHA 일치. robot/config/robots/vicpinky 수집 원본도 PC와 일치. 원호 radius .1m/angle pi/2/spacing .002m/deviation .01m/yaw .05rad/endpoint .008m/timeout60초, 재진입 .01m은 성공 config와 현재 config가 같다. 회전 모드는 실제 launch params에서 components이며 nav2_spin으로 잘못 전환된 흔적 없음.

별도 기존 차이: 로봇 wall_trial_runtime.py는 PC보다 expected-session/cycle-id 등 독립 CLI 기능이 적은 버전이다. 통신 연동 후 새 변경이라는 증거는 없고 파일 시각은10/21. 현재 harvest 경로에 해당 CLI 호출은 없으므로 이번 departure 실패 원인으로 연결하지 않았다. 덮어쓰지 않음.

### 코드에서 확인한 재현성의 빈틈(통신 연동으로 새로 만든 변경은 아님)

BodyTrial.run → runtime.build_body → body.start('enter'), 운영 ComponentTransferDevices._run의 prepare_arm → 같은 build_body → rotate_to_transfer → 같은 body.start('enter')다. 둘 다 HandoffPlanner.capture가 진입 직전 정지 상태의 동일 시각 map/odom TF를 확보하고 RestoreReference에 현재 자세를 저장한다. departure_route는 그 arc_origin_odom에서 arc_path를 생성한다. 웹 요청이 원호 방향/반경을 바꾸지 않는다.

WindowEntryReference는 window ID·목표xy·도착위치허용치만 보존한다. 목표 yaw/성공 당시 실제 자세를 고정하지 않으며 build_body는 현재xy만 window 범위로 검사한다. 일반 도착 허용치5cm/약3도와 전체 원호의 충돌 여유는 별개다. 인계 직전 자세 정규화/보정 단계 없이 현재 자세에서 출발한다. 이 구조는 과거 성공 코드에도 존재한다. 현재 성공 조건 재현 실패의 유력한 구조적 설명이나, 실제 위치오차 또는 costmap 차이의 발생 원인을 확정한 것은 아니다.

이번 실패는 prepare/build_body/capture를 통과한 뒤 departure guard의 기하 충돌에서 발생했다. 통신 지연·cancel·odom freshness·소유권 오류와 구분한다. 앞선 교차 재구성에서 이전 자세+현재 grid도 실패했으므로 자세 보정만으로 해결된다고 주장하지 않는다. 같은 데이터에서 두 진입 경로가 다른 원호를 만든다는 증거는 발견하지 못했다.

검증: SHA/소스 diff/설정 재귀 diff/실제 argv·params 및 정적 호출 추적. 새 실기/ROS Action/빌드 수행 없음. 읽기 사본과 source_hash_comparison.json은 /tmp/handoff-comm-audit, 영속 원본은 로봇 Downloads 백업과 runs 성공/실패 자료에 남아 있다. 남은 항목은 실패 셀의 센서 관측·TF 변환·rolling grid 생성 차이와 도착 허용영역 전체에서 인계 경로가 성립하는지 확인하는 것이다. commit/push 없음.


## 2026-10-24 장애물 셀 차이의 센서·TF 대조(무이동)

사용자 승인 범위는 성공/실패 센서·TF 분석과 정지 관측이며 설정/안전 조건/실제 이동 변경 금지다. 제품 코드, 파라미터, 브리지, costmap clear, 초기위치, Action에 쓰기 요청을 하지 않았다. 읽기 전용 구독 수집기만 기동·종료했다.

### 기록 범위와 직접 확인
- 성공 body-reentry-policy-nVLFxOy9 bag에는 scan_filtered/tf_static/tf/grid가 있다. 실패 web-dock-62x52-20261024_024737 bag에는 tf/grid/odom은 있으나 scan과tf_static이 없다. 앞선repeat-ready 수확 bag에도 scan/grid가 없어 문제 셀 최초 생성 시점의 센서 원본을 복구할 수 없다. 과거 실패 센서를 직접 확인한 것으로 표현하지 않는다.
- 현 위치 12초 수집(live_bag): scan106,TF579,정적TF1,odom316,인계grid43,일반voxel layer42표본. 별도10초 원본/필터 구독으로 scan101/filtered100표본 수집. 로봇측 cell-sensor-audit-20261024에 bag·스크립트·JSON·실행 costmap params 보존.
- 성공/실패 guard 전2초: odom각60표본 속도0, odom→base 자세 변화0, map→odom도 변화0. TF최대 도착간격 odom성공40.9ms/실패42.9ms, map성공102.5ms/실패105.1ms. 이 구간에서 TF 튐/큰 수신 공백 증거 없음. map→odom 미래stamp 약.9초는 기존AMCL조건과 일관하며 오류로 보지 않음. 최초 셀 생성 때 TF정상까지 증명한 것은 아니다.
- 성공과 현재 기록의 정적TF 행렬 전체 동일. 실패의 정적TF는 없어서 현재것을 보조 사용했다고JSON에 표시했다. 문제셀 map좌표변환 자체는 실패bag의 map→odom만으로 계산하여 앞선status기반추정과 동일한 (1.251869555,-.449433255)m 확인.
- 인계 local costmap은 voxel_layer+inflation_layer이며 static_layer는 실행 plugins 목록에 없다. 문제lethal254를 정적PGM에서 직접 가져온 것으로 해석하지 않는다. 성공 grid의 해당 map영역에는 가까운lethal이 없으며 최근접셀 중심은약.340m 떨어져 있다. 2cm 격자 원점 차이만으로 설명할 수 있는 규모가 아니다.
- 실패bag350개 grid 모두 문제셀(103,118)이254(약87초 관측구간). 현재bag에서는 같은셀43개 모두253이고 약4.47cm 떨어진 이웃에254가 있다. TF와 로봇정지 상태가 같아도 grid는 관측 이력으로 달라짐. 일반voxel layer의 해당 위치42개는0이며 인계master와 다른layer를 비교한 것이므로 둘이 동일한 셀내용이어야 한다고 주장하지 않는다.

### 센서 방향과 clearing 조건
같은 map지점을 각 시점의 laser_link로 역변환했다. 현재 대상거리 약.448m, 각도1.371rad. 성공 직전20scan의 주변7빔140개 중유효58/inf82, 현재20scan은유효1/inf139. 현재scan 반사점의 해당map점 최근접거리도 최소약.546m로, 대상셀의 현재 직접반사 증거는없다. 이는 실물장애물 부재 증명이 아니다.

후속 원본scan101개(주변9빔909개) inf857/유효52, 필터scan100개(900빔) inf849/유효51. 같은stamp100쌍 해당방향 거리값 전부동일. 현재무응답은polygon필터가 그방향 정상값을 제거해서 생긴 현상은 아니다. 설치filter형상은70×60cm지만 이번결과로 해당형상을 원인으로단정/수정하지않는다.

실제 인계params: marking/clearing=true, inf_is_valid=false, observation_persistence0, raytrace_max_range5m, obstacle_max_range4.5m, footprint_clearing=true. Jazzy Nav2 공식 obstacle_layer/voxel_layer 및 laser_geometry 구현상 inf를유효최대거리로변환하는 경로는별도이며 현재선택되지않는다. 따라서 inf가많은방향은그광선으로기존장애물셀을지우지못할수있다. observation_persistence0도이미찍힌grid셀의시간자동삭제가아니다.
공식참조: https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_costmap_2d/plugins/obstacle_layer.cpp , https://raw.githubusercontent.com/ros-navigation/navigation2/jazzy/nav2_costmap_2d/plugins/voxel_layer.cpp , https://raw.githubusercontent.com/ros-perception/laser_geometry/ros2/src/laser_geometry.cpp . 설치바이너리정확commit과소스동일성까지증명한것은아니다.

결론: 현재 근거는 TF순간튐보다 유효레이저관측 차이와 장애물셀잔존/clearing부족 경로를지지한다. 최초mark가실제물체/일시반사/과거TF오차중무엇인지는실패·주행scan누락으로미확정. inf를빈공간으로간주하여강제clear하거나설정을바꾸지않음.

추가관측: scan_filtered publisher목록에필터와zenoh2개가보임. 10초filtered100개는header stamp100개로중복미관측. 현재rclpy MessageInfo에GID가없어메시지별발행자귀속은못함. publisher목록만으로브리지중복이이번원인이라고단정하지않는다. 수집기MessageInfo형식오류2회후dict형식그대로기록하도록고쳐완료했으며제품노드변경없음.

근거: 로봇 runs/handoff_diagnostics/cell-sensor-audit-20261024/{live_bag,sensor_audit.py,sensor_comparison.json,ray_audit.py,ray_comparison.json,scan_sources.py,scan_sources.json,costmap_params.yaml}. PC /tmp/handoff-comm-audit에스크립트/결과사본. 재시험·실기이동·설정변경·commit/push없음.


## 2026-10-24 잔존 셀 해결 방법 검토 — 후보 검토만, 미적용
사용자는 안전 조건 유지·방법 확인을 요청했고 적용/이동 전 안내를 요구했다. 제품 소스·파라미터·costmap clear·이동 명령은 변경/호출하지 않았다.

로봇 sllidar_ros2/src/sllidar_node.cpp publish_scan은 dist_mm_q2에서 계산한 read_value==0이면 inf로발행한다(238/247행). 실행PID237715는vicpinky_ws/install의sllidar_node를사용한다. 현재소스와바이너리의빌드동일성은입증하지않았으나무응답을최대거리자유공간으로판정할근거는확보되지않았다. inf_is_valid=true를즉시적용할수없다. Nav2설치버전1.3.11확인,공식해당tag voxel_layer의유효point cloud raytrace처리대조. https://raw.githubusercontent.com/ros-navigation/navigation2/1.3.11/nav2_costmap_2d/plugins/voxel_layer.cpp

추가오프라인기하검사: 성공20scan과현정지20scan을각stamp TF로공통좌표에변환하여실패문제셀영역을통과하는유한거리광선(5m raytrace범위)을계산했다. 성공20/20scan에서1~3개,현재1/20scan에서1개만교차. 기존clearing입력이성공때와현저히다르다는근거다. 실제Nav2 3Dvoxel/Bresenham/끝점단축/입력수신을재생한시험은아니며셀삭제성공보장이아니다. 근거로봇cell-sensor-audit-20261024/clearing_audit.py,clearing_geometry.json/log. 실패당시scan누락한계유지.

권장순서:
1. 현행유효거리기반clearing을유지한다. 장애물뒤유효반사까지통과한광선과해당시각TF가확보된영역에서만기존Nav2자연갱신을관찰하고전체departure충돌검사를다시계산한다. 단일셀제거만으로재주행허용하지않는다.
2. 무효관측이계속되는방향은센서창/가림/반사조건/필터전원본품질을확인하여유효관측을회복해야한다. 센서가보지못하는영역을소프트웨어로안전하다고만들지않는다. 관측위치변경은사용자사전안내/승인및별도경로검증필요.
3. 유효광선이있는데도3Dvoxel이남는것이재현되면,인계voxel_grid·clearing_endpoints·raw/filteredscan·TF동시기록을이용해높이층/광선격자화/입력누락을격리재생한다. 입증된처리결함만후보수정하며일반주행불변,실제장애물잔존/무효측정차단/취소정지를오프라인검증한다.
4. 관측회복이어렵다면장애물셀을유지한채충분한여유가있는인계진입경로를별도계획하는방향을검토한다. 고정원호가기존window도착범위전체에서성립하지않는문제와함께검토하되경로존재/실기성공보장없음.

보류안: 전체/영역강제clear뒤최신timestamp만확인,TTL자동삭제,inf일괄자유공간변환,형상추가축소,충돌판정완화,확인없이voxel을obstacle layer로교체. 현재track_unknown_space=false이므로clear된0을관측완료된빈공간으로오인할위험이있다. 초기화가필요하더라도위험영역관측coverage와전체경로검사확보전출력차단조건이필요하며현재미구현·미승인이다.

이번결론은자동삭제패치적용이아닌안전한해결방향선정이다. 현재문제셀최초mark원인/실제물체부재는미확정. 기존recovery_required를우회하여재요청하지않는다. 운영적용/재시작/이동/commit/push없음.


## 2026-10-24 인계 voxel·clearing 광선 동시 수집 — 관측 부족 확인
사용자 승인에 따라 현위치 정지 상태에서 25초 구독 수집만 수행했다. 제품설정/안전조건/clear/초기위치/이동/재시작 미실행. 수집 전후 실제 인계 costmap params YAML 의미상동일, odom711표본 linear/angular 최대0.

근거 로봇 runs/handoff_diagnostics/voxel-clearing-audit-20261024: bag/metadata,params_before/after.yaml,voxel_audit.py/analysis.json,voxel_followup.py/followup.json,raw_filtered_sectors.json. bag은SIGINT정상종료. 원본scan236/필터237,voxel_grid237,clearing_endpoints237,voxel_layer_raw92,master93,TF1303/정적1,Status24수집.

직접결과:
- 이전 실패셀 중심odom(.749999954,-1.210000053)은 현재voxel237개모두marked높이없음,voxel layer92개모두0,master93개모두253. 따라서 현재 이 셀의253은잔존lethal이아니라주변장애물의팽창영역이다. 실패때350개254였던기록과구분한다. 자연삭제시점/직접원인관측은이번bag시작전이라미확정.
- 현재근처lethal3셀 중심odom(.589999957,-1.170000054),(.569999958,-1.170000054),(.549999958,-1.170000054)은master93/layer92개모두254,voxel237개모두z-index4만marked. z_resolution.05/origin_z0이므로높이.20~.25m. laser/clearing endpoint z=.237m로같은층이며다른높이의유령voxel이라는증거없음.
- clearing endpoint237개중과거latched1개는TF기록범위이전이라제외,나머지236개는526~550점/메시지. TF원점과설치nav2_voxel_grid header의정수셀/Bresenham수평분기를사용한오프라인계산에서위4셀통과광선0. 모든endpoints높이가동일층이므로수평분기적용,가까운대상범위만계산. Nav2전체실행재생은아님.
- 필터scan237개는해당셀에새유효반사점0,TF조회실패0. 대상별중심±2beam1185값모두비유한. 같은stamp원본/필터236쌍은해당각영역모두동일,원본1180개유효거리0. 무관측은필터전부터존재한다. 관측부재가물리장애물부재를뜻하지않는다.
- 동시에다른셀에서는marked→unmarked2433회,unmarked→marked2426회전이가관측됐다(고유셀개수아님). voxel origin은전체1종으로고정,따라서격자이동으로셀삭제처럼보인결과아님. 지우기/갱신이전체적으로멈춘증거는없다.

판정: 현재관측구간은 '유효clearing광선이셀을지나는데지우지못함'보다 '해당방향원본측정이무효라지우기광선자체가없음'에해당한다. 최초mark원인과무응답의물리원인은아직미확정. 기존inf_is_valid=false에서관측없는영역을보수적으로보존한상태와부합한다. 바로clearing코드수정/inf허용/강제clear할근거없음. 현위치그대로의반복수집만으로시야/반사정보를추가할수있다는보장없으며다음은라이다가림·측정면·무응답각영역확인또는별도승인후관측조건변경검토. 현재전체인계경로통과재검증/실기재시험미실행. 문서만갱신,commit/push없음.


### 2026-10-24 충전 후 스테이션 재시작 준비
사용자가충전완료/기존스테이션위치·방향복귀확인,웹연결후정합·costmap·원본레이저비교요청(이동금지). PC/로봇ps직접조회에서더미·브리지·수확·런치·드라이버·Nav2관련잔존없음. 현재별칭/pc.bash/실제profile확인. 로봇기존실패DOCK_TEST_2264... recovery_required=true로재기동만으로복구안됨확인. 앞선수동복귀기록절차에따라전체transfer.json백업후동일FAILED결과/ID보존하고manual_recovery근거추가·해당record복구래치만false. 로봇runs/handoff_diagnostics/charged-station-restart-20261023T193628Z에전후JSON/SHAreceipt보존. 코드·설정변경/기동/이동없음.
PC더미journal recovery_required=true,records2/history2보존·미수정. 사용자기동후웹확인단계에서더미공식Recover/실제준비상태별도확인필요. 명령순서PCdummy→PCbridge→로봇laun→스테이션vinit→zen→dzen→vstat. 각foreground별도터미널,기존실패를성공처리하지않으며웹작업전송/인계/반복허용은아직금지. 새window기준없음. commit/push없음.


### 2026-10-24 04:39 충전 후 스테이션 정지 점검
사용자 순서대로 기동/웹 표시 확인 후 무이동 상태 조회·구독 수집만 수행. 현재 harvest PID270128/boot af5ac68e53d44b03a38f5511e34bfb13, 일반관제 bridge270566/더미 bridge270640. RobotStatus IDLE/readytrue/load0/현재작업없음. PC더미 boot f46d67cef1684c159f314d596768e0ce, mode dummy/ERROR/readyfalse/recovery_requiredtrue, active ID없음/가상팔정지·접힘·상자닫힘. 이전실패복구래치유지이며Recover/prepare/Action호출안함. 웹GET harvest/harvest_return readytrue(장치업무준비증거아님).
정지정합: scan629점중앙22.23mm/p90 38.66mm,5cm이내97.30%/10cm100%,odom300표본비영0. 추정map(.0793484,-1.1236693),yaw1.52009954rad. 실제참위치정확성보장아님. scan_age .441s는검사종료시선택표본값이고별도bag도착age통계와구분.
일반64×54/인계62×52 published footprint일치,두costmapunknown0. 현재정지및가상+.1rad검사PASS:일반여유하한.190/.179m,인계.200/.190m. 실제회전없음/전체인계경로검증아님. cmd_vel_nav publisher harvest_motion_server1개,odom vic_pinky_bringup1개.
충전전window bag와충전후station bag원본scan비교:236→137표본,각header중복0,약10.10→10.01Hz,전체유효거리84.01→96.04%,이전문제laser각도1.3713rad±2beam구간유효0→100%. header도착age중앙98.72→99.85ms로주기는비슷. 필터전체유효74.81→86.77%. 위치/방향/관측물체·재기동이달라배터리인과확정불가. 현재전압/실제잔량계측없으며battery0은BATTERY_UNAVAILABLE자리값유지.
근거로봇 runs/handoff_diagnostics/charged-station-check-20261024/{bag,alignment.json,station_checks.json,charge_scan_compare.py,charge_scan_compare.json,dummy_status.json} 및원costmap/footprint. PC /tmp/charged-dummy-status.json,/tmp/charged-web-control.json(토큰제거). 이전기록보존. 설정/clear/Recover/반복허용/초기위치/이동/재시작/commit/push없음. 다음업무시험전더미공식복구·준비확인필요. 새window도착기준미확보.


### 2026-10-24 04:41 충전 후 PC더미 복구·같은 웹 작업 1회 허용
사용자승인으로PC공식Recover(DEVICE_AND_LOAD_RECONCILED)호출전journal백업,가상장치정지/접힘/상자닫힘·비활성확인. Recover/prepare success,RuntimeStatus IDLE/readytrue/recoveryfalse. records2/history2 내용전후완전동일확인. 마지막TEST_8e2c1cd3e3ff_SEC01_TASK001/W001(expected2,goal1.186,-.035,0)1회반복허용04:41:19→04:46:19 KST(더미수락기준). 웹마지막성공job fd062f1935b2476ab72e3d4ed5ebb8c3와ID일치. 웹새테스트기본goal1.6006447/count1은다른작업이므로기존동일작업재전송안내. 에이전트주행Action/웹버튼미호출.
PC외부charged_repeat_ready_20261024_044115에journal전후/서비스응답/상태/웹보존. 로봇runs/handoff_diagnostics/charged-web-repeat-20261024_044111에원본scan·TF·인계voxel/clearing포함bag수집시작(900초한도,recorder.json),전체구독확인. 사용자웹전송대기,새window/수확/인계성공아직미확인. 코드·설정변경/commit/push없음.


### 2026-10-24 04:43 충전 후 웹 window 수확 완료 및 센서 비교
사용자가 웹에서 보낸 job e4186857241a487dac90891043d63911은 04:43:14 KST SUCCESS(더미 수확 2개, 실패 0개). SECTION_APPROACH/WINDOW_MOVE ARRIVED, 도착 accepted=true. 실제 도착 map=(1.1389807834,-0.0290450005), yaw=-0.0101276697rad, 위치오차47.395mm/허용50mm, 방향오차0.580도/허용3도. 설치 communication.py의 SUCCESS 분기는 remember_window를 handle.succeed보다 먼저 호출하므로 새 도착 기준 저장 경로 수행을 성공 응답과 대조했다(메모리 직접 덤프는 아님). 실물 팔 시험이 아니라 PC 더미 Action 성공이다.
최종 조회 IDLE/ready=true/loaded_count=2, 최근 odom 30표본 속도0. 일반 footprint64×54/인계62×52 유지, 두 costmap unknown0. PC 더미 새 attempt0325d758e30a45b8836ec508615d2c8e terminalSUCCESS/recoveryfalse. history2→3, 기존 history prefix와 이전 record의 archive 내용 완전 동일, 나머지 record도 동일 확인. 1회 반복 허용은 이번 실행에 소비됨.
충전 전 비교 대상은 최초 실패 순간이 아니라 이후 정지 관측 voxel-clearing-audit-20261024다. 각 마지막10초 원본 scan100개: 약10Hz 동일, 유효거리84.079→83.899%, 이전 laser 각도1.3713113rad±2beam 유효0→1.75%. 해당 방향 관측 부족이 충전으로 해결됐다는 근거 없음. 이전 문제 map점의 master cost253→97, 최근접 lethal 거리0.165→0.572m. 현재 grid의 장애물 배치는 달라졌지만 실제 추정 정지 자세도 약4.28cm/1.99도 다르며 재기동도 있었으므로 배터리 인과 확정 불가.
저장한 최종 grid/odom으로 62×52 진입 곡선 오프라인 검사 PASS(여유 하한10.87mm). 비교 정지 관측 당시도 PASS(14.45mm)였으며 최초 인계 실패 grid는 별개다. 현재 실행 중 모든 guard, 벽 정렬·배출·복귀 또는 전체 실기 성공을 의미하지 않는다.
이번 기동의 tag_capture_session PID270129가 작업 전 종료됨: capture.log camera code1/rectify code-11/detector code-9, 세션 code1. 종료 코드만으로 원인 확정 불가. 태그 보정 조건이 이전 성공 시험과 달라 인계 전 추가 확인 사항으로 보고. 재시작/설정변경/강제clear/인계 요청 없음.
근거: 로봇 runs/handoff_diagnostics/charged-web-repeat-20261024_044111/{bag,station_checks.json,window_charge_audit.py,window_compare.json}; tag 로그 runs/harvest_tag/20261024_043704_r5777hn8/capture.log; 런치 /home/vic/vmany-terminal-logs/20261024_043703_launch_270055/console.log. PC /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/charged_repeat_ready_20261024_044115/journal_after_work.json 및 before 보존. 수집 recorder만 종료하고 bag metadata 저장 확인. 코드·안전 설정 변경/commit/push 없음. 인계 미실행.


### 2026-10-24 태그 캡처 최초 종료 원인 확인(읽기 조사)
사용자 승인 범위는 원인 조사이며 수정·재기동 전 보고, 실제 이동 금지. PC/로봇 trial_io.py, opencv_camera_compare.py, pinky_tag_capture_compare.py, harvest_tag_capture.yaml SHA256 모두 일치. 실제 commands.json은 로봇 robot/tools/tag_camera 스크립트 및 /opt/ros/jazzy image_proc/rectify_node, apriltag_ros/apriltag_node 실행을 확인한다.
최초 실패는 rectify 충돌이 아니라 opencv_camera_compare.py:95→TrialIO.before_publish():121의 RuntimeError control_readback_stale다. process_exits.json unexpected_exits=[camera], camera code1/signals_sent=[]; 감독자가 이후 detector에 SIGINT/SIGTERM/SIGKILL(code-9), rectify에 SIGINT(code-11)를 보냈다. 따라서 detector-9는 이 기록에서 감독자의 강제 종료이며 OOM 증거가 아니다. rectify-11은 종료 중 별도 결함이고 최초 카메라 중단 원인이 아니다.
원인 조건: TrialIO._poll은 완료 후1초 대기하고 v4l2-ctl --list-ctrls(timeout3초)를 수행한다. before_publish는 매 영상 루프에서 마지막 성공 조회의 monotonic age>3.5초이면 예외를 발생시키며 main finally에서 캡처를 끝낸다. 주기+조회 최대대기4초가3.5초 검사와 양립하지 않아 조회 timeout 없이도 stale 종료가 가능한 구조다. 현재 기록은 polling 시작/완료 소요시간·스케줄링 지연을 분리하지 않아 실제 지연 원인이 USB/ioctl인지 CPU/GIL/프로세스 대기인지 확정할 수 없다. 단순 허용시간 연장으로 해결했다고 볼 수 없다.
이번 camera_controls.jsonl270개 모두 controls 값 동일, 마지막 갱신 04:41:45.595629→04:41:49.430691 KST 간격3.835061초. 최초 예외 시각/age 수치는 기록되지 않아 이 간격 자체가 최종 예외 순간이라고 단정하지 않는다. 마지막 영상 단계들에서 raw/rect/detect 동반 공백과 publish 소요 증가가 있으나 인과 미확정. controls_restored=true, frames_written0/record_token null, 설정 불일치·녹화큐 초과 오류 없음. 커널 journal 해당 구간 조회는 No entries(USB/OOM 부재를 확정하는 증거는 아님).
최근12개 capture.log 중 이번 포함6개에서 같은 control_readback_stale 발견. 충전 전 20261024_024131_29el3jsz 세션도 capture_exit1로 종료됨. 앞선 설명의 이번에만 태그 보정 조건이 달라졌다는 암시는 정정한다. 각 성공/실패 주행 당시 태그 적용 여부는 개별 events로 별도 판단해야 한다. 현재 관련 캡처 자식 프로세스는 ps에서 없음.
다음 제안(미적용): 카메라 제어 조회 시작/완료·timeout·snapshot age·예외를 영구 기록하고, 조회 지연/설정 불일치/영상 입력 실패를 구분한다. 확인되지 않은 설정의 영상은 태그 보정에 사용하지 않는 보호를 유지하며 일시적인 조회 지연의 처리 및 제한된 회복을 별도 설계·오프라인 검증한다. 종료 중 C++ rectify 충돌은 별도로 재현/스택 확인 필요. 실제 캡처 재시작이나 설정 조회 재현은 사용자에게 먼저 알린 뒤 수행한다. 이번 코드·설정 변경/재기동/이동/commit/push 없음. 원본 근거 runs/harvest_tag/20261024_043704_r5777hn8/{capture.log,session.json} 및 하위20261024_043707_ylm_oizh/{commands.json,process_exits.json,camera_controls.jsonl,recording_summary.json} 보존.


### 2026-10-24 태그 설정 조회 지연 후보 구현·오프라인 검증(미적용)
사용자 승인: 일시 조회 지연 시 캡처 유지, 미확인 영상의 보정 사용 차단, 기존 성공본 보존, 실제 적용/재기동 전 알림, 이동 금지. runs/tag_control_candidate_20261024에 original 백업/candidate 두 파일/manifest.json/candidate.patch/test_candidate.py/verification.log/README.md 준비. Git ignore 대상 후보이며 운영 PC robot/tools/tag_camera와 로봇 소스·설정은 미변경. 백업과 운영 PC 원본 바이트 동일 확인.
trial_io.py 후보: 기존3.5초 freshness를 유지한 발행 gate, timeout만 snapshot 무효화 후 주기 재시도, 정상 조회 재확인 후 새 획득 프레임부터 재개, 실제 설정 불일치/기타 명령 오류 종료 유지. start/verified/timeout/failed 시각 기록. opencv_camera_compare.py 후보: Image/CameraInfo 및 녹화를 동일 gate 안에서 실행, 차단 프레임 폐기. snapshot 갱신과 발행 사이 경쟁은 RLock으로 직렬화하고 이미지 바이트 변환은 밖에서 수행. stale 자체는 전체 캡처 종료 사유에서 제외하되 미확인 영상 발행을 허용하지 않음.
최종 오프라인14개 통과 및 py_compile 통과: stale/미확인/미래시각/복구 이전 프레임 차단, timeout 반복·정상회복, 설정 불일치·명령 실패의 종료, 동시 무효화, 실제 main 발행 블록의 Image/CameraInfo 동시 차단 검사. 최초 테스트 작성 중 괄호 SyntaxError 수정 후 최종본 재실행. 실제 USB/ROS/DDS/태그 보정 성공 또는 실기 검증 아님. DDS publish의 잠금 점유 지연과 C++ 종료 -11은 남은 별도 항목. 조회값은 프레임별 센서 노출 메타데이터가 아님. 적용은 사용자에게 알린 뒤 현재 로봇 해시 재검사·백업 후 두 파일 함께 교체하며 현재 미적용. 문서 외 운영 파일 변경/재기동/이동/commit/push 없음.


### 2026-10-24 영상 ROS 부하와 설정 조회 지연 대조·이전 구조 확인
읽기 조사만 수행. 현재 종료된 카메라를 재기동하거나 설정/후보를 적용하지 않았다. 로봇 capture.log와 camera_controls.jsonl의 wall time을 대조: 충전 후04:41:21.179 조회간격2.649초 근처 avg publish126.0ms,04:41:49.430 간격3.835초 근처90.1ms. 같은 세션04:38:33.532 간격2.374초 근처12.4ms. 충전 전 세션024131의03:03:43.893 간격3.468초 근처10.0ms,02:46:00.621 간격3.264초 근처10.5ms. 마지막022628 세션은128개발행통계 max27.4ms,조회간격>2초없음. 일부 동시 지연은 확인하지만 모든 조회 공백을 발행 지연으로 설명하지 못함.
중요 계측 한계: avg publish는 약5초 집계이며 images.publish+infos.publish+trial.record_published(상태 파일 기록 포함) 전체 소요다. 순수 DDS 시간이나 대역폭 지표가 아니다. 조회 로그도 성공 완료 사이 간격이며 v4l2 호출 시간과 스레드 실행 대기를 분리하지 않는다. 별도 프로세스 Navigator와 직접 callback group 공유 없음. 카메라 내부 발행/조회 스레드의 GIL·CPU·파일I/O·USB 경쟁 및 DDS 역압 후보를 기존 기록만으로 구분 불가.
Git2091859(2026-10-08) 최초 해당 카메라 런타임 반입본도 OpenCV→image_raw/camera_info→image_proc rectify→image_rect→apriltag_ros→monitor 구조이며 domain178/LOCALHOST/reliable/10Hz cap 사용. 해당 커밋 대비 HEAD의 opencv_camera_compare.py와 trial_io.py diff 없음; 현재 운영 PC 바이트도 이전 조사 기준 유지. 통신 연동 작업에서 새로 영상 ROS 전달을 도입했다는 증거 없음. 더 이전 외부 개인 실험의 모든 구현까지 확인한 것은 아니다.
알고리즘상 영상 단계마다 ROS 전달이 필수는 아니다. 한 프로세스에서 직접 영상 보정·검출 후 작은 검출/자세 결과만 ROS로 보내는 대안은 가능하지만 기존 image_proc/apriltag_ros의 보정 모델·검출 파라미터·시간/CameraInfo 계약·기록 경로 동등성 검증이 필요하다. 현재 성공 경로를 그 방식으로 변경하지 않는다.
추가 인과 검증에는 사용자에게 먼저 알린 뒤 정지 상태 태그 세션 실행과 분리 계측(V4L2 시작/종료, 영상 변환, 각 publish, 상태파일 기록, 스레드/프로세스 CPU·스케줄링)을 같은 시각에 수집해야 한다. 검사 전용 격리 도메인에서 고정 입력/동일설정 조건의 구독자 부하 비교가 필요하며 운영 QoS/안전조건을 임의 변경하지 않는다. 이번 문서만 갱신, 재기동/이동/commit/push 없음.


### 2026-10-24 05:00 카메라 단독 분리 계측 시도 — 디스크 공간 차단
사용자 카메라 단독 재기동 승인, 계측 변경 사전 고지 후 별도 runs/tag_timing_probe_20261024/code 복사본에 시간 계측만 추가했다. 기존 stale 종료 로직/3GiB 검사/영상 설정 유지, 복구 후보 미적용. py_compile 및 계측 반환값/예외전파/동시301건 기록 검사 통과. V4L2·poll wait·영상변환·Image/CameraInfo publish·파일기록을 분리 계측하도록 준비했다. 위치 보정 adapter 미기동, 이동 명령 없음.
로봇 실행은 카메라 TrialIO 초기화에서 at_least_3GiB_free_required로 실패. 여유3,102,498,816 bytes <3,221,225,472 bytes. 카메라 영상 입력 시작 전이며 부하 판정 불가. 부모277903 종료1,자식camera277910 종료1/monitor277907·rectify277908·detector277909 종료0 및 ps 잔존없음. harvest270128 유지. receipt.json 운영3파일/설정 전후SHA동일. 기록 삭제나 검사 완화 안함. RAM저장은 I/O조건변경이므로 우회안함.
공간 확보 준비: 로봇 runs/handoff_diagnostics/charged-web-repeat-20261024_044111/bag 436MiB를 PC runs/tag_timing_probe_20261024/preserved_logs/bag에 추가 보존 완료. mcap SHA293fc7d2c87b838157c8e6733cbf73fe4d6c21014330c0c02117b700add5043f, metadata SHA a1ffcc79dcef9c9fdb5e974cf2323fdb448d7828cdb60dce3d88189d463409b7 양측일치. 해당 로봇 bag만 삭제하고 PC사본 보존 후 계속할지 사용자 확인 대기. 다른 코드·설정/로그 삭제/주행노드 재기동/이동/commit/push 없음. 원본 로그 현재 양쪽 보존.


### 2026-10-24 로봇 대용량 자료 PC 이전·정리
사용자 '지금 필요한 코드만 남기고 나머지는 PC 백업 후 삭제' 승인. 실행 경로·열린 FD 확인 후 종료된 runs의 rosbag/영상/1MiB초과 jsonl·log 및 Downloads 최상위 배포 압축본을 선별했다. 실행 소스/설치본/프로파일/현재 브리지/핫픽스 원복/진행중 계측은 보존. Downloads 전체 삭제하지 않음(현재 실행 의존 포함).
PC /home/eunbi/vmany_artifacts/robot_storage_archive_20261024에 원래 상대경로·manifest.json(크기/mtime/SHA)/rosbag metadata와 함께 백업. 1,180개/3,929,540,132 bytes 전수PC SHA일치 확인 후 로봇에서 열린파일/변경여부/해시 다시 확인하여 동일1,180개만 unlink. 변경·열림 skip0, 폴더/설정삭제없음. 삭제 receipt와 PC검증receipt/README도보존. 공간약2.9→6.6GiB. 예전 로봇runs의 대용량 원본 경로를 읽을 때 PC archive의 대응경로를 사용하거나 개별 복원할 것. 기존 JSON 요약/설정/작은 기록은 로봇에 유지.
정리 후 사용자 승인된 카메라 단독3분 분리계측을 runs/tag_timing_probe_20261024_retry에서 실행. 원래 로직/설정/QoS/3.5초기준 유지, 앞선복구후보 미적용, 위치보정어댑터 미기동, 주행노드270128유지. 계측 결과 별도 후속 기록. Git commit/push 없음.


### 2026-10-24 공간 확보 후 카메라 단독 분리 계측 결과
runs/tag_timing_probe_20261024_retry에서180초캡처+종료(186.9초) 수행. 동일 폴더 PC사본 보존. 영상1430회, 설정조회177회(전후복원포함),controls175기록 값변경0/최대갱신간격1.047225초. 이번 정지시험에서 control_readback_stale 재현없음.
구간별 평균/최대(ms): v4l2 subprocess14.298/103.248, Image ROS publish8.481/30.421, CameraInfo publish0.745/5.972, 영상변환2.664/9.846, camera read28.443/52.314, atomic 파일쓰기1.382/49.714, control log쓰기0.239/5.549, monitor JPEG 인코딩+쓰기9.776/43.418. 최대조회103ms는시작구간. poll 1초대기최대1.013706초. 구간별상세analysis.json에초별집계/느린호출/스레드CPU보존. 중첩구간은합산불가. 이번관측은ROS통신으로3.5초조회만료된증거없음; 정지상태3분/계측복사본/디스크공간조건변경 때문에과거부하장애배제불가. V4L2·DDS·I/O의이전실패인과는아직미확정.
정해진시간후SIGINT정리: camera0/monitor0,detector-11/rectify-11,unexpected_exits없음. 즉운영중예외아니라종료과정별도결함재현,부모exit1을전체정상종료로표현하지않음. 카메라노출원값복원성공,PNG녹화요청없음. 모든계측자식종료ps확인. 기존harvest270128유지/운영3코드및설정전후SHA동일. 계측중15초상태조회IDLE/ready/load2,odom453표본비영0,PC더미Action연결ready. AMCL보정adapter미기동/이동명령없음. 원래성공코드및앞선stale복구후보미적용. commit/push없음.


### 2026-10-24 검출기·rectify 종료 SIGSEGV 읽기 조사
사용자 원인 조사 승인, 수정/재기동 전 고지·이동 금지. 이번에는 재기동·수정·attach 없이 기존 Apport와 설치 래퍼를 읽고 기존 코어를 gdb -batch로 오프라인 분석했다. 최신3분시험은 camera정상0 이후 detector/rectify SIGINT 처리중 각각-11,강제SIGKILL없음/운영중unexpected exit없음. 따라서 카메라 설정조회 stale와 구분되는 종료경로 SIGSEGV다.
설치 버전 image_proc5.0.13/apriltag_ros3.4.0/image_transport5.1.8/rclcpp28.1.18/rmw_cyclonedds_cpp2.2.4. /var/crash의 두 보고서는 최신이 아니라2026-10-16이며 버전은현재와일치. Signal11/VmSwap0,당시RSS약31~33MiB. 두CoreDump각60KiB로gdb에서segment past end/stack read failure,전체스택복원불가. 고장PC rectify0xffffb48a005c,detector0xffff9e51005c는각ProcMaps의유효매핑밖. 미매핑코드주소접근/종료중라이브러리해제경쟁가능성과부합하지만덤프불완전/과거자료이므로같은원인이나특정라이브러리확정불가. 'corrupt stack?'출력을실제스택손상증명으로사용하지않음.
설치 /opt/ros/jazzy/share/rclcpp_components/node_main.cpp.in은node instance→executor spin/remove→node파괴→shutdown→loader파괴구조. 이것은설치템플릿확인이며해당바이너리빌드시소스와완전동일하다는증명아님. 종료시callback/스레드/동적라이브러리수명교차를다음우선조사항목으로분류. 공식image_common#379에도Ctrl+C종료시segfault보고있으나Humble3.1.12/특정전송플러그인조건으로현재Jazzy원인확정/패치근거가아님: https://github.com/ros-perception/image_common/issues/379 .
현재RAM7.8GiB중available6.6GiB,swap0/1GiB,memory PSI avg10/60/300=0,CPU PSI some약9.75/11.00/18.52%. 현시점측정만으로과거paging/압박배제불가. fragmentation/major page fault증가/장애시context switch rate자료없음. CPU대기존재는원인확정아님. 페이지폴트·스케줄링은조회지연후보,단편화특정근거없음;SIGSEGV를메모리부족/페이징과동일시하지않음.
다음필요검증은사용자에게알린뒤주행·AMCL과격리한영상노드만디버거하위에서기동하여SIGSEGV직전전체thread backtrace/유효maps/라이브러리해제순서수집. 최신완전스택이없으므로지금종료순서변경·플러그인교체·버전업하지않는다. 원본코어/로그보존,PC runs/tag_shutdown_audit_20261024에bt결과보존. 운영코드/설정/재기동/이동/commit/push 없음.


### 2026-10-24 영상 노드 gdb 종료 충돌 직접 포착
사용자승인으로영상노드만디버거하위실행. 운영카메라3파일/설정불변·SHA전후동일,domain178/기존검출설정·영상설정유지. 보정adapter미기동,harvest270128유지,이동명령없음. 별도 runs/tag_shutdown_debug_20261024/run.py에서60초영상검출후camera먼저SIGINT정상종료,1초후detector/rectify실제inferior에SIGINT각전달. gdb는SIGSEGV에서정지하여모든스레드bt40/레지스터/siginfo/공유라이브러리/maps확보.
확정 관측: detector PID286523/LWP286598 PC0xffff7b87005c,rectifyPID286521/LWP286596 PC0xffff946c005c,둘다SEGV_MAPERR(si_addr=PC). 종료전maps에서모두/usr/lib/aarch64-linux-gnu/libtbb.so.12.11+0x1005c,충돌시maps에서TBB매핑없음. 동시에main thread는__run_exit_handlers→class_loader unloadLibrary→rcpputils→rcutils→dlclose/_dl_close_worker. libtbb12:arm64 2021.11.0-2ubuntu2의해당명령어대조:0x10058 bl dlclose@plt,0x1005c 다음add명령. 따라서종료중라이브러리가해제된영역으로실행스레드가복귀하는수명경쟁직접증거확보. paging/fragmentation원인으로분류하지않음. 내부함수명은strip된TBB라미확인,정확한책임소스/수정안은추가검토필요.
기존설정조회stale의원인과동일하다는증거없음. 수정방향은스레드완료와라이브러리수명보장검토이며무작정타임아웃연장·오류무시·플러그인교체하지않음. oneTBB공식finalize는worker완료대기API이나안전한호출위치/조건검토전적용안함: https://www.intel.com/content/www/us/en/docs/onetbb/developer-guide-api-reference/2021-11/initializing-and-terminating-the-library.html .
PC/로봇동일runs/tag_shutdown_debug_20261024에camera/monitor/detector/rectify로그,종료전maps/status,receipt,디버거스크립트보존. PC analysis.json/README/tbb_disassembly추가. gdb wrapper exit0은inferior성공아님. 최종ps에서모든시험자식/gdb종료,기존harvest270128그대로. 운영코드/설정수정·주행노드재시작·이동·commit/push없음.


### 2026-10-24 TBB 종료 순서 실행 후보·오프라인 검증(운영 미적용)
사용자승인: TBBworker완료후라이브러리해제후보및검증,성공코드/설정보존,적용/재기동전고지,주행/이동금지. PC·로봇 runs/tbb_shutdown_candidate_20261024에별도C++runner 후보작성. 기존librectify.so(image_proc::RectifyNode)/libAprilTagNode.so(AprilTagNode)와원본바이너리의SingleThreadedExecutor계약유지(nm확인). 영상알고리즘·QoS·파라미터·주행코드수정없음.
runner가TBB를직접링크(DT_NEEDED)하고component보다먼저task_scheduler_handle확보. node/executor정리→ROSshutdown→TBBfinalize(nothrow)성공→factory/loader해제. 생성실패exit1유지. finalize false이면해제안하고명시로그후_Exit(3),정상종료로숨기지않음. finalize무응답내부timeout은추가하지않았으며외부감독자의기존유예시간내완료여부실측필요.
PC검증: x86_64빌드,finalize/unload순서단위3개(성공/false/예외)통과,loopback231합성TBB컴포넌트parallel_for실행후SIGINT0/SIGTERM0/생성실패1의3경로모두순서검사통과. 두후보TBB직접링크2개확인. 실카메라영상/로봇/DDS부하시험과구분. verification.log/verification/*보존. 로봇별도폴더-j1 ARM컴파일2개성공,AArch64/TBB직접링크확인. 로봇후보실행없음.
로봇original/에원래rectify_node/apriltag_node/캡처감독자/카메라설정백업,바이트동일검사·SHA기록. 원본설치파일/launch/설정변경없음,harvest270128유지. 앞선조회stale복구후보도미적용. 다음은사전안내후실카메라단독후보비교로실제종료SIGSEGV/종료시간/영상검출동등성확인필요. PC README/source_manifest/arm_build_receipt/build로그/검증로그보존,commit/push없음.


### 2026-10-24 TBB 후보 실제 영상 종료 검증 — 실패
사용자 카메라 전용 실행 승인으로 운영 설정·주행 노드를 유지하고 별도 ARM runner만 선택했다. 원본 카메라/monitor, 기존 rectify/detector 인자·파라미터 그대로 사용했으며 태그 보정 adapter와 이동 요청은 실행하지 않았다. Git 기준 cf870da 및 기존 문서 미커밋 변경 보존.
실제 120.034초 처리: raw/rect/detections 각각944표본, tag100 검출. camera/monitor 종료0. detector는 SIGINT 이후0.266초, rectify0.264초에 각각 exit3: TBB_FINALIZE_FAILED. TBB_FINALIZED/COMPONENT_LIBRARY_RELEASED는 출력되지 않았다. SIGTERM/KILL 없이 전체 종료3.813초(카메라 후1초 대기 포함).
이전 -11과 달리 후보의 실패 보호 경로로 종료했으므로 정상 종료 해결로 인정하지 않는다. 실제 OpenCV/TBB 사용 후 남은 scheduler/arena/참조 소유권은 추가 조사 대상이며 이번 결과만으로 특정 소유자를 확정하지 않는다. finalize 실패를 무시하거나 강제 성공 처리하지 않는다. 합성 시험 통과는 실제 영상 종료 성공을 보장하지 않았음.
운영 카메라 코드3개/설정SHA 전후동일, harvest PID270128 유지, 시험 자식 종료 확인. 읽기 상태 수집15초에서 odom452표본 비영0/IDLE. 카메라 closed=true/fault없음 및 controls 복원 기록 보존. 별도 카메라 후보 시험만 종료했으며 운영 launch 교체·주행 재시작·이동·commit/push 없음.
PC·로봇 runs/tag_tbb_candidate_trial_20261024에 run.py, commands/settings/파라미터, 영상 표본, 로그, receipt.json(종료코드·시간), robot_status.json 보존. PC에는 processes_after.txt도 보존. 후보는 운영 적용하지 않았으며 추가 후보 수정/실행 전 보고한다.


## TBB 종료 v2 후보 — 2026-10-24

사용자 승인: 자원 소유권 추적·별도 후보 보완·오프라인 검증. 운영 적용/실제 카메라 재실행은 미승인 범위로 수행하지 않음. 기준 Git cf870da, 기존 미커밋 문서와 이전 v1 후보/실패 로그 보존.

## 발견한 소유권
- 로봇 OpenCV 4.6.0+dfsg-13.1ubuntu1, TBB 2021.11.0-2ubuntu2. rectify/AprilTag 컴포넌트 모두 OpenCV core와 TBB 의존.
- OpenCV는 노드 객체가 아닌 라이브러리 전역 정적 task_arena를 보유한다. 노드/executor 소멸만으로 이 arena가 해제되지 않는다. parallel_for 및 remap 경로가 이를 사용한다.
- upstream 4.6.0 parallel.cpp의 setNumThreads(0)는 활성 arena를 terminate하고 재초기화하지 않는다. 로봇 설치 바이너리 disassembly에서도 terminate 호출과 0 입력 시 initialize 생략 확인. 1을 사용하면 arena를 재생성하므로 이번 목적에 맞지 않는다.
- 카메라 없는 동일 OpenCV remap 대조에서 PC와 ARM 각각 retain 5/5 finalize=false(exit3), release 5/5 finalize=true(exit0). 이미지 처리값 동일 검증 포함. 완료된 연산 뒤에도 OpenCV arena가 종료를 막을 수 있음을 재현했다.
- 지난 실제 영상 프로세스의 모든 잔존 자원을 직접 열거한 것은 아니다. 실제 detector/rectify의 다른 소유자까지 해소됐는지는 다음 카메라 전용 시험 필요.

## 후보 변경
| 파일 | 변경 |
| --- | --- |
| src/safe_node_main.cpp | spin/node/executor 정리 후 cv::setNumThreads(0), 이어 TBB finalize 성공 확인 후 loader 해제. 실패 exit3 유지 |
| CMakeLists.txt | OpenCV core 직접 링크, 카메라 없는 remap 대조 실행 파일 추가 |
| test/probe_node.cpp | 기존 합성 노드에 실제 OpenCV 병렬 연산 추가 |
| test/run_offline.py | OpenCV 해제→TBB finalize→컴포넌트 해제 로그 순서 검사, 시험 폴더 ROS 로그 사용 |
| test/opencv_owner.cpp, test/run_owner.py | 전역 arena 보존/해제에 따른 종료 결과를 별도 프로세스에서 5회씩 대조 |

처리 중 스레드 수/영상 설정/검출 파라미터는 바꾸지 않는다. 전용 단일 컴포넌트 실행 파일 종료 경로에서만 사용하며, 다른 영상 작업이 병행하는 공유 컨테이너에 그대로 적용할 수 없다. 보정 adapter는 실행하지 않음.

## 직접 검증
PC·ARM 빌드 성공. 각 환경에서 remap 대조10건, SIGINT0/SIGTERM0/생성실패1 및 정리 순서3경로, 기존 finalize 보호 순서 단위3건, TBB 직접 링크2건 검사 통과. PC 최초 실행은 ~/.ros/log 쓰기 제한으로 실패했으며 시험폴더 ROS_LOG_DIR 지정 후 재검증 통과; 초기 오류는 실제 TBB 검증 결과로 사용하지 않음.

운영 카메라3스크립트/설정 SHA 전시험과 일치, /opt/ros 원본2실행파일 백업과 바이트 일치, harvest270128 유지. 실제 카메라 재실행/이동/운영 적용/commit/push 없음. v1 후보와 원본 백업은 그대로 보존. 되돌리기 작업은 불필요하며 다음 시험에서 사용할 후보 실행 파일만 v2로 선택해야 함.

## 증거
- owner_results.json, verification/: PC 검증
- robot_verification/: ARM 검증·빌드·preservation.json
- robot_setNumThreads_disassembly.txt: 설치 바이너리 해제 분기
- candidate.diff: v1 대비 변경
- https://github.com/opencv/opencv/blob/4.6.0/modules/core/src/parallel.cpp (정적 arena 및 setNumThreads)

다음 단계: 사전 고지 후 카메라 전용 v2 실행에서 실제 영상 처리, SIGINT 종료코드0, TBB_FINALIZED→COMPONENT_LIBRARY_RELEASED, 기존4초 종료제한, 원본 SHA/주행 유지 확인. 아직 실기 종료 해결 완료 아님.


### 2026-10-24 TBB v2 실제 영상 종료 시험 통과 (1회)
사용자 카메라 전용 v2 실행 승인. 원본 카메라/monitor 및 영상 설정 그대로, rectify/apriltag 실행 파일만 runs/tbb_shutdown_candidate_v2_20261024/build 후보 선택. 운영 launch/바이너리 교체와 보정 adapter·이동 요청 없음. 기준 cf870da 및 기존 미커밋 변경 보존.
120.035초 실행, raw/rect/detections 각각939표본, tag100 검출. camera/검출기/rectify/monitor 모두SIGINT 종료0. 검출기0.264714초, rectify0.267155초(신호 전송~프로세스 wait 관측의 monotonic 경과). camera0.465257초,monitor1.867278초,전체3.865244초(카메라 후1초 대기 포함). 기존 검출기/rectify4초 제한 내 종료,TERM/KILL없음. 두 로그 모두 OPENCV_ARENA_RELEASED→TBB_FINALIZE_BEGIN→TBB_FINALIZED→COMPONENT_LIBRARY_RELEASED 확인. 이전 원본-11/v1 exit3과 달리 이번 v2 실제 영상 종료 정상.
운영 카메라3스크립트/설정SHA 전후동일, /opt/ros 실행파일2개 원본 백업과 동일, harvest270128/launch270080 유지. 시험 자식모두종료. 영상 중 별도15초 읽기 odom453개 비영0/IDLE 확인(전체120초 연속 odom계측은 아님). 카메라 설정 복원 기록 보존. PC·로봇 runs/tag_tbb_v2_trial_20261024에 commands/settings/후보SHA/영상표본/로그/receipt.json/보존검사 저장,31파일복사SHA일치검증. Git commit/push없음.
이번 한 차례 카메라 종료 시험 통과이며 장시간/반복 종료·주행과 태그보정 통합·control_readback_stale 원인 해결은 별도. 운영 설정은 여전히 원본 실행 파일 사용. 다음 운영 적용은 사전 안내 필요.


### 2026-10-24 v2 종료 처리 운영 경로 반영 — 재기동 대기
사용자 운영 적용·백업·원복 준비 승인. Git cf870da+기존 미커밋 변경 유지. PC/로봇 robot/ros_ws/src/farm_tag_camera_runtime에 실제 시험한 v2 C++/헤더 바이트 그대로 추가, ament 설치용 CMake/package.xml과 설치 선택 검사 추가. 양측 colcon에서 새 패키지만 빌드. 기존 harvest/Nav2/AMCL 패키지는 빌드·재시작하지 않음.
robot/tools/tag_camera/pinky_tag_capture_compare.py가 기존 /opt/ros 실행 파일 대신 ament index의 farm_tag_camera_runtime/{apriltag_safe,rectify_safe}를 선택. 기존 명령 인자/검출·카메라 설정/종료 제한은 불변. 누락·권한 오류 시 시작 전 실패, 자동 원본 fallback 없음. settings.json에 실행 파일 경로·SHA 기록 추가. /opt/ros 바이너리와 기존 v1/v2 후보·백업 보존. 시뮬 ROS 영상 launch 불변.
PC 오프라인 캡처/설정/세션/실행 선택21건 통과. 최초2건은 시험명령 PYTHONPATH에서 ROS 경로를 제외한 ModuleNotFoundError; 환경 수정 후21건 통과. 임시 복사본 원복3건(정상복원/원본상태/추가변경거부) 통과. 로봇 새 env source에서 설치된 두 바이너리 경로 확인, v2 소스동일, 나머지 카메라2파일+trial_io 및 설정SHA 동일, harvest270128유지. 캡처 적용 SHA 2f21f848041b5e2307233387ec33a0ccd74d3c82c961d48abcd88fc0d1450451. 카메라 재기동/이동/commit/push 없음. 운영 경로 실제 재기동 검증은 아직 미수행.
PC/로봇 runs/tag_tbb_v2_deploy_20261024에 capture.before.py/after.py, 빌드·적용 receipt 및 rollback.py 보존. 카메라 종료 상태에서 로봇 터미널 `python3 /home/vic/vmany/main/farm_project/runs/tag_tbb_v2_deploy_20261024/rollback.py`로 실행 선택 원복. PC는 같은 경로의 /home/eunbi 사용. 실행 중 카메라 또는 적용 후 추가변경이 있으면 거부. 새 패키지는 남아도 원본 스크립트가 참조하지 않으며 삭제/기존노드 재기동 불필요. 새 설치만 복사할 때 farm_tag_camera_runtime을 빌드 목록에 명시한다. 원복 도구는 프로세스 시작/종료하지 않는다.


### 2026-10-24 운영 캡처 경로 v2 실영상·종료 검증 통과
사용자 카메라만 재기동/정상종료 검증 승인. 운영 pinky_tag_capture_compare.py를 변경 없이 subprocess 실행, 기존 캘리브레이션·manual_2ms·검출 파라미터 그대로 사용하고 출력 폴더만 별도 지정. 실제 ament 설치 경로 farm_tag_camera_runtime의 apriltag_safe/rectify_safe 선택을 settings.component_runtime 및 commands.json으로 확인. fleet 주행 노드·보정 adapter 재기동/주행 명령 없음.
약2분 시험, raw/rect/detections 각950표본,tag100검출. 운영 부모+camera/detector/rectify/monitor 모두exit0,process_exits.clean_shutdown=true,예기치않은종료없음,SIGINT만 사용. 검출기·rectify 각각 OpenCV arena 해제→TBB_FINALIZED→COMPONENT_LIBRARY_RELEASED 확인. -11/TERM/KILL없음. 운영 스크립트는 수정하지 않고 외부 수집기가 STOPPING/EXIT 출력 수신시각(monotonic)을 기록: 검출기0.264560초,rectify0.265867초,camera0.414579초,monitor0.565077초. 이는 정확한 OS 신호~exit 시각이 아닌 로그 관측 구간이다. 부모 SIGINT 요청~수집 종료2.736272초.
기존 운영 코드3파일/카메라설정 SHA 전후동일, 기존 성공 주행 PID270128/launch270080유지,시험자식 모두 종료. 별도15초 odom455개 비영0/IDLE. 카메라 controls_restored=true. 검출파라미터 이전v2시험과동일. 로그·종료시간·실행해시·표본은 PC/로봇 runs/tag_operational_v2_trial_20261024, 실제 세션 capture/20261024_060235_la99uakv. PC복사32파일SHA일치 확인. 원복백업/도구 유지,commit/push없음.
검증 범위는 운영 캡처 스크립트와 설치 실행파일의 카메라 전용 시작·영상처리·정상종료 1회. 전체launch 재기동·태그보정/주행 통합·장시간 반복·설정조회 stale 원인 해결은 이번 검증에 포함하지 않는다. 현재 카메라는 종료 상태,주행노드는 유지.


### 2026-10-24 카메라→태그 보정 정지 연결 확인
사용자 정지 연결 확인 요청 후 카메라·어댑터가 모두 종료 상태임을 확인하고 재기동 범위를 사전 고지. 운영 tag_capture_session만 기존 environment에 지정된 capture config와 runs/tag_bias_trial/20261023_165950_381707_on/localization.yaml로 잠시 실행. 주행/AMCL 유지, 작업 활성화·보정·initialpose·이동 명령 미발행. 설정/코드 변경 없음.
새세션 runs/harvest_tag/20261024_060658_l_wtlwis,하위20261024_060659_8h_4ce7t:raw/rect/detections418개,tag100검출. 실제어댑터FD17이새detections.jsonl을열었고5초간읽기위치89623→114588로각시점파일끝까지전진. 이전세션재사용아님.
DDSgraph: harvest_motion_server control publisher→adapter/AMCL subscriber, adapter correction publisher→AMCL subscriber, AMCL events publisher→adapter subscriber 확인. AMCL read-only parameters tf_broadcast=true,protocol=scan_sync_v1,robot=harvest_01,map=many_farm_v1 일치. 이는 연결·계약 확인이며 실제 보정 적용 왕복 성공을 의미하지 않음.
35초읽기관측control/correction/events각0,odom1052표본비영0. 어댑터 start/closed 기록 correction_requests=0. 유효작업lease없으면출력을차단하는기존보호를유지했으므로정지대기는정상이며보정성공으로표기하지않음. 영상→관측계산→AMCL 실제적용은유효작업구간에서별도확인필요,이번에는작업신호를인위적으로발행하지않음.
시험후adapter/capture부모및camera/detector/rectify/monitor전부exit0,clean_shutdown=true,-11/강제종료없음. 세션SIGINT→부모종료3.834초. 시험자식종료,기존launch270080/AMCL270098/harvest270128유지. 설정·설치/소스모듈전후SHA동일. 현재카메라·어댑터는시험종료상태. 로그는PC/로봇runs/tag_stationary_link_20261024,로봇원세션도보존;PC에원세션전체추가복사. commit/push없음.


### 2026-10-24 주행 중 태그 보정 시험 준비 — 이동 미실행
사용자 요청에 따라 읽기 조회/오프라인 준비만 수행. 현재 map추정(1.138854,-.029044),yaw-.010128rad(-.58도),IDLE/readytrue/load2/활성작업없음,최근odom30개정지. 일반64x54/인계62x52 footprint일치,정지costmap하한.1104/.1204m,unknown0. 이는실측정합/전체경로안전확정아님. cmd_vel_nav단일harvest_motion_server,odom단일driver. launch270080/harvest270128/AMCL270098/일반bridge270566/더미bridge270640 실행중. PCdummy172229/bridge172290 실행중,최신더미IDLE/readytrue/recoveryfalse. 카메라·보정종료상태.
웹읽기에서수확Action연결,#57기존목표(1.186,-.035)완료와#59 25fabab7b348_SEC01_W001 목표(1.601,-.035)예상1개선택대기확인. 저장작업상세에서정밀목표1.6006447347066082,-.035,yaw0 및 TASK001 ID확보. 현재→#59 직선거리.46183m,저장일반costmap 직선후보검사PASS 하한.10580m. 실제Route/FollowPath계획을획득한것은아님. 더미journal에#59task ID없음,반복허용서비스미호출. #57재전송은거리부족/반복ID보호문제로이번시험선택안함. 웹Goal전송/선택변경없음.
PC/로봇 runs/tag_motion_prepare_20261024에 current check,selected_task_NOT_SENT,straight_candidate_check,사용자용start_camera.bash,추후에이전트구독전용collect.bash 준비. bash syntax통과,두스크립트미실행. start_camera는기존환경과기존보정프로파일로tag_capture_session만실행·로그tee·중복프로세스검사. laun/vinit/zen/dzen/PCdummy 재기동불필요;현재window이므로vinit금지. 사용자카메라기동/웹표시확인뒤최신상태·현장정지가능여부확인과수집시작,이동방향안내후사용자가#59만선택해수확시작할예정. 아직전송하지않음.
성공조건: 실제WINDOW_MOVE 중control lease와동일세션의TAG_CORRECTION_SENT→AMCL tag_correction_applied(발행만으로성공아님),주행완료/새window기준/더미결과를대조. 태그ROI/관측조건부족으로보정0회면주행성공과별도로미검증기록,조건완화/자동반복없음. 코드·설정/기동/이동/commit/push없음.


### 2026-10-24 #59 전송 전 점검 — 기동 보조 스크립트 오류 수정
사용자 카메라기동/웹표시보고후실제프로세스조회에서카메라/어댑터없음확인. 준비한start_camera.bash와collect.bash가set -u 상태에서Jazzy setup을source하여 AMENT_TRACE_SETUP_FILES: unbound variable로중단되는문제재현. 운영영상/TBB코드문제가아니며에이전트제공보조스크립트오류. 원본을양측runs/tag_motion_prepare_20261024/source_env_fix에백업하고source동안만nounset해제,이후복원하도록수정. 기존운영코드/설정불변. bash구문/환경source검증후사용자동일명령재실행필요. 카메라자동재기동/웹전송/이동없음,#59전송보류. 영상기동확인후bag수집을시작해야하며현재수집미시작. commit/push없음.


### 2026-10-24 #59 주행 전 연결 확인·로그 수집 시작
사용자 TAG_ADAPTER_STARTED/현위치유지·이동가능확인후 최신읽기검사. 카메라세션 runs/harvest_tag/20261024_061926_bm7gpkmi/20261024_061927_3iqz3xrc,영상·검출약8~9Hz/tag100/control_readytrue/fault없음. adapter305752와AMCL control/correction/events연결·scan_sync_v1/robot/map계약일치. harvest270128 IDLE/readytrue/현재목표없음/이전window위치유지,관측odom비영0,일반/인계정지costmap통과. PC더미IDLE/readytrue/recoveryfalse.
사용자승인으로구독전용bag수집시작,최대600초/SIGINT종료상한. runs/tag_motion_live_20261024/recorder.json에소유PID/명령,recorder.log에전체요청토픽구독완료확인. control/correction/events,task_events/status,odom/amcl_pose/TF,scan/filter,cmd_vel_nav,일반costmap/footprint포함. 카메라자체검출·보정events기록도계속유지. 점검결과/더미상태PC사본보존.
준비된#59 25fabab7b348_SEC01_W001 예상1개(목표1.600645,-.035,0)만웹에서사용자가한번보내도록안내. 현재대비약46cm앞목표이며실제경로는주행기가결정. 에이전트이동/수확Goal전송없음,아직주행·보정적용성공미확인. 기존코드/설정/안전조건불변,commit/push없음. 사용자가보냈다고알리면같은세션요청·AMCL적용·window도착·더미결과대조,완료후수집기만종료할것.


### 2026-10-24 웹 #59 완료 — 주행/더미 성공, 태그 보정 적용 0회
사용자웹전송후추가Goal없이로그대조. #59 task=25fabab7b348_SEC01_TASK001/window=25fabab7b348_SEC01_W001,event7357b74e8b404edc82c335d600a3516c. 06:21:56 KST SECTION_RESUME→WINDOW_MOVE,FollowPath nav2status4/ARRIVED. 06:22:06.858 도착(1.559834,-.023754,yaw-.015347rad),목표(1.600645,-.035,0),위치오차42.332mm<50mm,방향.879도<약3도,accepted=true. 새arrival request fe76a5fc659f4d6d81eec0761ddfc3f0. 설치communication.py는SUCCESS에서remember_window→handle.succeed 순서 확인(내부메모리를직접조회한것은아님).
06:22:08.555 작업SUCCESS/ARM EXECUTED. PC더미동일ID 영속terminalSUCCESS attempt4f167399130346ceb5ba9657621198bd,수확2/실패0. expected1과결과2의차이는서버--targets기본2,expected_count를상한으로쓰지않는기존더미시나리오이며실물팔수확아님. 최종IDLE/readytrue/활성작업없음/load4,odom451표본비영0.
태그통신은정상: bag control28/AMCL events26(전부tag_control_accepted). correction메시지0/요청0/적용0. 어댑터observation35개selected0. 동일stamp원검출35개와설치본동일SHA roi_accept 재판정: 실제보정ROI 가로60%·세로80%,x[256,1024),y[72,648),네모서리모두내부조건. tag100 11개왼쪽밖,tag101 24개오른쪽밖,상하밖0,통과0. 따라서영상태그검출→작업lease/관측진입은확인됐으나사용가능ROI관측없어보정요청전제외. 단순통신고장이나AMCL거절로해석하지않음. roi60모니터(60%정사각형)와실제ROI구분유지. 향후태그가실제ROI안에들어오는구간/카메라시야를기존기록으로확인해야하며안전/ROI조건변경이나자동재주행없음.
이번수집기306359만SIGINT정상종료,metadata저장. bag_20261024_062041 약57MiB PC/로봇SHA일치(1149ef08a7381b7ac6ad18fc2b9d1741e05690f006c104ca38507a6571aa2298),metadata도일치. PC/로봇 runs/tag_motion_live_20261024에추출events/states/counts/최종상태,PC에더미journal/영상세션사본/roi_analysis보존. 카메라·보정은사용자기동상태계속유지,주행/AMCL/브리지미재시작. 코드·설정·보호변경/이동재요청/commit/push없음. 이번태그보정실적용시험은미성공(0회)이며수확작업성공과구분.


### 2026-10-24 #59 스테이션 재시험 — 주행 중 AMCL 보정 1회·window·더미 완료
사용자 웹 #59 전송만 관찰, 추가 이동/인계 요청 없음. 기준 cf870da 및 기존 미커밋 변경 유지. 06:34:50 KST SECTION_APPROACH 시작→06:35:49.730 ARRIVED→WINDOW_MOVE→06:36:01.824 ARRIVED. 두 단계 nav2status4. 새 도착 request3743062914d2446d9d8beef69dbbe09f/plan d345ff727a50490db6edd1ca71f1ef20; 실제(1.581903,-.011735,yaw-.009188rad), 목표(1.600645,-.035,0), 위치오차29.874mm/방향.526도, 기존50mm/.05236rad 조건 accepted=true. SUCCESS 경로 remember_window 호출은 코드 확인이며 메모리 직접조회와 구분.
이번 실제 주행 중 태그100 관측→동일token1639b1e2872a47d1b6e46ebec20de110/producer86ebb25426bb4d0199676992dd9eff7f/sequence1 요청→queued→AMCL tag_correction_applied 확인. 06:35:52.153 적용, scan_stamp1792791352007843075, reason scan_aligned/filter_initialized=true. 보정시점 최근 odom 약.060m/s(직전.0615/직후.0597)로 실제 이동 중 적용 근거 확보. 카메라 검출만/요청 발행만의 성공이 아님.
06:36:03.519 전체SUCCESS/ARRIVAL_THEN_ARM. PC더미 새 attempt312e370f20ce4d96b64dbb642b2b7744 terminalSUCCESS,수확2/실패0,기존#59기록은history보존. expected1/더미결과2는 기존 --targets=2 시나리오이며 실제팔아님. 최종IDLE/readytrue/활성작업없음/load2,정지검사odom453표본비영0,출력소유자1.
남은 문제: SECTION_APPROACH 제어token84c57fc37157468c868ff0615b9f4585는begin1792791290584018999<barrier1792791290585771322(1.752323ms)로AMCL inactive_or_task_begin120회거절. bag앞부분에첫token enable→disable→새token enable이연속됨. task_ended invalidate에서수신현재시각barrier를쓰는코드와전환경쟁가능성은부합하나barrier변경원인직접로그없어확정하지않음. 이후WINDOW_MOVE 새token은수락하여실제적용성공. 전체보정제어경로가무결하다고보고하지않으며안전조건완화/코드변경/재시작없음.
완료정지확인후이번수집기313447만SIGINT종료/metadata작성확인. bag 및 camera세션/launch_snapshot/분석events·상태·적용시점odom·더미journal을PC runs/tag_station_retest_20261024에보존,로봇원본보존. mcap SHA256 080d883f32e6733e49262212d4ac49ba6f7d534379e707d3d4b12b852f925352 및metadata7e5189f3104912b06c0213f37c611497460f7f5c6d468049e8b0040e02351d5d 양측일치. 인계시험미실행;현위치유지,별도진입점검·안내후진행. commit/push없음.


### 2026-10-24 #59 후 웹 인계 — 곡선 완료, 벽 관측 시각 실패
사용자 dock_transfer 전송. DOCK_TEST_a0aefa4082974daa8159e68436ed031b / TRANSFER_TEST_a2cda2e6d875403796e24584b0cfaa21. 06:40:15.715 KST 시작, 인계controller 06:40:18.084 goal→06:40:32.736 Reached goal(후진곡선). 06:40:35.012 벽정렬goal→06:40:35.069 Wall observation expired / future→abort. 06:40:36.733 journalFAILED/activefalse/recovery_requiredtrue,Actionstatus6. bag의Actionfeedback0개로DOCK_READY미발행확인. 배출/복귀요청없음. 현재ERROR/readyfalse/load2, map(1.432120,-.130576,yaw1.631119). 최근odom61표본비영0 및사용자현장정지확인.
wall_control.hpp의 w.stamp>now 또는 now-w.stamp>observation_age 공통문구조건. 이번로그만으로과거만료/미래시각어느쪽인지·실제차이수치확정못함. 충돌장애물실패로해석하지않으며기준완화/설정변경/재시작/초기위치/재진입없음. 다음이벤트전송보류.
수집기316724만SIGINT정상종료/metadata확인. runs/handoff_after_tag_20261024에bag/launch_snapshot/transfer_after/live_observation/action_events 및costmap을PC사본포함보존. 주행·카메라·브리지유지. Actionfeedback메시지정의bag임베드경고있으나구독완료,PC설치인터페이스로status해석성공;feedback자체는0개. 기존로그/코드/설정불변,commit/push없음. 다음은실패시각센서/벽관측/시각기준추적이며인계성공으로표시하지않음.


### 벽 관측 만료 오류의 직접 조건 확인
실행 중 wall_alignment.observation_age=.3초 조회. 실제로봇 wall_control.hpp SHA151f6ea803c486db466149c856aa52cfe0c3de08b52724012d6d932d9e93ccf7. 오류는수신유무검사뒤 w.stamp>now 또는 now-w.stamp>.3 조건에서발생하며충돌/거리오차검사와별개다. 벽 관측stamp는원scan stamp를보존하고Python TF조회2회+벽fit후발행한다. 실패1792791635.068501358전후bag에서raw/filtered scan은약10Hz,수신headerage약.09~.105초,실패직전수신scan은실패시각기준.11684초였다. 외부수집기에서레이저발행중단증거없음;내부벽처리/전달지연가능성은남음. 이번bag에handoff/wall_observation을포함하지않았고C++오류에도실제stamp/now가없어제어기가쓴표본과expired/future분기확정불가. 다음수집에벽관측토픽및실패수치필요. 수정/재기동/이동없음. 분석산출물runs/handoff_after_tag_20261024/failure_scan_timing.json.


### 2026-10-24 성공 스냅샷과 현재 벽 시각 실패 대조
/tmp/robot-success-20261023 성공보존소스와로봇현재소스·Python설치본해시직접대조. wall_reference/WallTracker/handoff_motion/planning/navigation/body_trial/transfer_communication 및C++wall_control/wall_input/wall_plugins 동일. runtime차이는build_server_config의footprint_padding선택인자추가뿐(승인62×52);_observe/wall_error 변화없음. wall_alignment_trial.json SHA4705444028ac1694ce0a0f1f655c0e1c7cb0a4bc28256651fb016654ded1a632도동일,실행관측허용.3초. 현재controller PID311306 maps에서프로젝트install libwall_controller.so 로딩확인,파일SHA99594e551a2b2169d0e50ea9e960ddac9972a890b6a2456625797b3a6e6ae0ce/mtime10월20일19:31:23;이정보만으로과거실행바이너리동일성까지증명하지않음.
과거10/20관측지연수정은독립wall_observer_node의KEEP_LAST1/세부timing과wall_trial_runtime정수시각검사범위,문서에운영FSM미연결명시. 공통wall_reference벡터화/캐시는현재소스·설치본에도보존. 10/23통합body성공본도현재와같은_observe였으므로이번통신연동때벽계산최적화를되돌렸다는증거없음. 반면독립관측기진단은통합_observe에동등하게없어실패표본추적공백존재.
검사시점차이: _observe는scan읽을때.3초검사후TF2회/fit/lock/발행,발행직전측정age재검사없음. wall_error도사전검사이며C++첫명령시점재검사까지시간경과가능. 최근수신(steady)과측정header나이가다른검사는유지됨. 처리/전달지연으로C++시점에만만료될가능성은코드상확인,이번정확표본미수집으로직접원인확정금지.
성공기준(10/23 21:15)은bodyenter/restore·goal1.186,-.035. 현재는웹DockTransfer/PC더미FSM·#59goal1.600645,-.035,인계padding2cm→1cm선택변경도있어동일조건은아님. 어느차이가시각실패를유발했는지통신부하/콜백/TF/계산등미확정. 비교산출물runs/handoff_after_tag_20261024/comparison. 코드/설정/재시작/이동/commit/push없음.


### 2026-10-24 사용자 요청: 벽 시간 임계값 조정 후보
사용자 반복 차단 조건 제거 또는 임계값 확대 요청에 따라 실제 로봇 wall/handoff 설정 원본을 runs/wall_timing_candidate_20261024에 보존. 운영소스/설정/프로세스 불변,PC 후보만 작성. 변경2개: controller.observation_age .3→.45초, observation.max_gap_s .3→.45초. dwell .5초와충돌/취소/정지/속도/미래시각거절유지,일반주행변경없음. .45는원인확정후도출한해결값이아닌제한된실험후보이며이번오류가future분기면해결못함. 최대설정속도.02m/s·.05rad/s에서추가150ms는3mm/.0075rad 이동분에해당하나실물안전증명아님.
실제C++헤더와후보설정생성검사: .35/.44초수락/.451초만료/미래1ms거절/기존.3초거절/실측비영속도정지우선/같은stamp반복성공금지확인. 기존C++회귀도실행,로그test.log. ROS부하·실기검증아님. 이전성공코드및핫픽스보존,이번에는적용/재기동/이동없음. 운영적용은Python과controller가같은설정을기동때읽어야하며수확노드만값변경으로불일치시키지않는다. 현재recovery_required유지. 원복은미적용후보불사용,추후배포시원본설정복원필요. commit/push없음.


### 2026-10-24 0.45초 후보 운영 설정 적용·종료 확인
사용자백업유지/실행본적용/종료·재기동절차승인. 종료전ERROR·odom91표본0,실패transfer기록백업. 카메라311318→launch311278→로봇브리지311773/311836 정상종료,자식포함remaining[];PCdummy196592/bridge196652도기록백업후종료remaining[].최종로봇관련프로세스검색없음. 런치종료중harvest Destroyable 경고1회후finished cleanly;정상종료경고문제까지해결됐다고표시하지않음.
공용wall_alignment_trial.json불변. /home/vic/Downloads/pc_dummy_dock_fsm_20261024/wall_alignment_045.json 신규전용후보배치,동폴더handoff_fsm.json의wall_config참조만변경. observation_age/max_gap_s=.45,dwell=.5,padding=.01 유지. 실제설치구성생성기로controller/observer설정오프라인일치검증,노드기동없음/빌드불필요(JSON선택변경). runs/wall_timing_deploy_20261024에로봇·PC원본/배포receipt/검증/종료PID/rollback.py보존. 원복은프로세스부재·afterSHA검증후원래handoff참조복원,신규설정파일미참조로보존.
현재실패journalrecovery_required유지(물리복구전해제하지않음). 사용자에게드라이버종료확인후스테이션재배치가능시점안내. 스테이션위치·방향이동확인받은뒤이번실패원문보존+수동복구기록을추가하고재기동하도록할것. 아직재배치확인/복구해제/재기동/초기위치/이동없음. PC더미도기동후복구상태조회필요. 사용자기동순서PCdummy→PCbridge→로봇laun→vinit→zen→dzen→vstat,웹연결확인후파라미터·정합·costmap·더미·새window기준점검. commit/push없음.
