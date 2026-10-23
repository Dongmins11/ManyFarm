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
