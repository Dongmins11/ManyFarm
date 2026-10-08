# 시뮬레이션팀 요청: 전달 Teacher 재현 및 농장 통합 진단 자료

작성일: 2026-10-08. 목적: 전달 정책·실행기·환경 설정이 실제 실행과 같은지 확인하고, 농장 환경에서 파지하지 못하는 원인을 구분한다.

## 먼저 확인할 사항

전달물 `harvest_teacher_9g.tar.gz`에는 Teacher 4개뿐 아니라 `harvest_runtime/staged_teacher.py`, `harvest_rl/env.py`, `eval_current_pair.py`, `scripts/eval_teacher_mass.sh` 및 의존 코드·자산이 들어 있다. Student 체크포인트는 포함하지 않았다. `collect_student_*`라는 이름은 Teacher 시연을 Student용으로 기록하는 경로를 뜻하며, 이름만으로 Student 제어라고 판단하지 않는다. 외부 YOLO `.pt`는 탐지 모델이다.

이번 Teacher는 다음 실행 구성을 사용한다.

```text
지정 목표 + 시뮬레이터 상태
  → 82차원 관측 및 전문가별 저장 정규화
  → 접근·파지(-1) → 당김(0) → 운반(1) → 놓기(2)
  → 정규화된 팔 5관절·그리퍼 1관절 목표 증가 명령
  → 기존 하위 관절 제어 및 물리 시뮬레이션
```

단계 사이 장면을 초기화하지 않는다. 전달 기준 놓기는 박스 위 정지 승인 후 팔 목표를 유지하고 그리퍼 `+0.15` 증가 명령을 사용한다. 놓기 전문가 파일도 로드하지만 `release_mode=fixed`에서는 그 단계 출력이 고정 명령으로 대체된다. 정책 하나만 직접 호출하는 전체 수확과는 구성이 다르다.

독립 환경에서 수확 능력을 검증한 구성이나 모든 농장 배치에서 성공을 보장하지 않는다. 별도 농장 통합 어댑터의 관측·좌표·접촉·제어 연결은 수신팀에서 확인해야 한다.

## 1. 받은 버전과 실제 로드한 모델

아래를 보내 주세요.

- 받은 TAR 파일 이름·SHA256, 압축 해제 폴더, `handoff/base_commit.txt`, `handoff/git_status.txt`.
- 실제 실행한 명령 전체와 사용한 환경변수: Python 경로, 정책/자산 경로, seed, 물리·제어·렌더 주기, 옵션.
- 로드한 정책 4개의 절대/상대 경로 및 SHA256, 각 파일 옆 `run.json`, 사용한 `teacher_ramp_20260930.json`.
- 기존 `StagedTeacher` 사용 여부, 실제 정책 로더·관측 어댑터·관절 명령 적용 코드. 수정했다면 diff 또는 해당 소스.
- Isaac Sim/Isaac Lab/Python/PyTorch/RSL-RL/CUDA runtime/GPU driver 버전, GPU 모델.

전달 기준 정책 목록:

| 역할 | 상대 경로 | SHA256 |
|---|---|---|
| 접근·파지 | `runs/harvest_rl/entry_grasp_refine_20260929_202452_137384791/train/model_200.pt` | `e676f43738515446636782f22f51cf81e4fc945210729fdd0ff0458b66b1db9b` |
| 당김 | `runs/harvest_rl/pull_direction_20260927_211734_412361705/train/teacher_final.pt` | `4914107143f59cb321ce332b6cf185fe563cb44522f50ade782b715fccc045fd` |
| 운반 | `outputs/harvest_rl/entry_transport_20260929_220740_390998651/transport_refine/train/teacher_final.pt` | `47f3b7bf6500d35448ed9510db6884ac584921eeddc072350000728402ddb528` |
| 놓기 | `runs/harvest_rl/place_short_hook_20260923_074907_182931509/train/teacher_final.pt` | `c6c96f0bb81f861519fc5ac0e2467d9083d3c9b5c309d054bd0a7c30c4dcce27` |

로컬에서 확인한 전달 압축 버전은 다음과 같다.

| 묶음 | TAR SHA256 | 참고 |
|---|---|---|
| `harvest_teacher_9g_20261006_143434` | `7b33e66a3cad8003204fc69819eaf95be6362d246c574bb6cf827f953e161139` | 초기 전달본, 6회 평가 원본 포함 |
| `harvest_teacher_9g_20261006_200626` | `2430a6ea86ea14877217445f959af70751bf610c3c22bd4f5f0c9d83ae53ba8b` | 추가 제어·10회 평가/비교 원본 포함 |

두 묶음의 정책 4개는 같다. 실제 받은 버전은 TAR 해시로 구분한다. 10월 7일 손목 카메라 수정 및 `greenhouse_v1` 배경은 두 전달본에 포함하지 않는다.

## 2. 독립 평가를 먼저 재현

농장 통합 코드와 별도로, 압축 해제한 저장소의 전달 스크립트로 빨강·노랑 각 5회 평가한다. 학습 명령이 아니다.

파일 검사는 새로 압축을 푼 폴더에서 캐시 경로 보정 전에 실행한다. 이미 경로를 보정/수정했다면 그 변경 내역을 함께 제공하고, 현재 작업물을 덮어써 초기화하지 않는다.

```bash
cd /path/to/manyfarm_robotarm
python3 scripts/sim_team/verify_bundle.py
python3 scripts/collect_student_ramp.py --check
python3 scripts/sim_team/prepare_receiver.py

export HARVEST_PY=/path/to/env_isaaclab/bin/python
export STUDENT_DETECTOR="$PWD/external/models/model_yolo11_seg_ver1.2.pt"
export STUDENT_VISION_PY="$PWD/.venvs/harvest_vision/bin/python"
export EVAL_OUT="$PWD/outputs/harvest_rl/sim_receiver_check_$(date +%Y%m%d_%H%M%S_%N)"
FRUIT_MASS_KG=0.009 POSE_STOP=1 HEADLESS=1 EPISODES=5 \
  bash scripts/eval_teacher_mass.sh
```

이 경로는 Teacher로 수확하면서 두 D435·YOLO 기록을 생성한다. 비전 환경이 준비되어 있어야 한다. 카메라를 사용하는 기록 경로이고, 기존 전달본은 물리/제어 검사만 하는 무카메라 명령을 따로 제공하지 않았다.

수신팀 결과 폴더의 아래 파일을 우선 압축해서 보내 주세요.

```text
sim_receiver_check_.../
  red.log
  yellow.log
  red/ 및 yellow/
    run.json
    expert_contract.json
    actuator_runtime.json
    dataset_manifest.json
    collect_phase.json       # 정체/오류가 있으면 포함
    episode_*/metadata.json
    episode_*/result.json
    episode_*/*.json         # 프레임별 기하·접촉·단계 진단
```

처음에는 영상·RGB-D NPZ 전체를 보낼 필요가 없다. 실패 1~2회와 성공 1회의 viewport 영상만 추가하면 좋다. 불가능하면 실패 영상부터 제공한다. 목표 미선정(`TARGET_UNAVAILABLE`), 실행 오류, 시간초과, 수확 실패, 적재 성공을 각각 기록하고 파지만으로 전체 성공을 계산하지 않는다.

## 3. 농장 통합 실행의 상태·제어 로그

자체 통합 실행기는 위 파일을 자동 생성하지 않을 수 있다. 그 경우 아래 항목을 **정책 tick마다 시뮬레이션 시간 기준 20Hz**로 JSONL 또는 NPZ에 저장한다. 종료 직전만 저장하면 초기 접근 오류를 찾기 어렵다. 초기화부터 종료까지 실패 1~2장면의 연속 기록을 요청한다.

| 항목 | 필요한 값 |
|---|---|
| 시간 | 시뮬레이션 timestamp, wall timestamp, 물리 step 번호, 정책 tick 번호, 물리 dt와 실제 정책 dt |
| 대상·단계 | 목표 ID/슬롯, 선택 색상, 현재 전문가(-1/0/1/2), 전환 이유·시각, episode/요청 상태 |
| 관측 | 실제 입력한 원본 82개, 전문가용 시간 슬롯 보정 후 82개, 저장 정규화 적용 후 82개. 항목 순서와 기준 프레임 명시 |
| 출력 | 전문가 raw action 6개, clip/ramp/고정열기 후 action 6개, 최종 관절 목표각 6개 |
| 로봇 | 6개 관절 이름·순서·현재각·속도·제한, TCP 위치·자세, 집게 간격·중심, 활성 팔/고정 베이스 pose |
| 과실·박스 | 과실 root/COM/연결점 위치·자세·선속도·각속도, 박스 내벽·바닥 경계, 사용 좌표 프레임 |
| 접촉 | 고정 집게/움직이는 집게의 접촉력, bilateral/centered/entry_inside 판정, 접촉 센서 body/prim 경로 |
| 줄기·분리 | 앵커, 인장 방향, 연결점 변위·하중·임계값·유지시간, attached/valid_detach/pending_detach |
| 보유·적재·실패 | has_grasped/has_retained/grip/release_armed/valid_release/in_box, 실패 조건별 플래그, 종료 이유 |

Teacher 관측을 Student 입력/RGB 추정값으로 대체하지 않는다. 전달 `CurrentPairEnv`는 지정 목표를 기존 슬롯에 매핑하고 주변 과실 슬롯을 0으로 채운다. 새로운 과실 목록을 임의로 같은 벡터에 넣으면 원래 입력 의미가 달라진다. 전문가별 저장 normalizer를 유지하고 평가 중 통계를 다시 학습하지 않는다.

## 4. 물리·좌표·주기 설정 원본

아래는 전달 기준이다. 요청하는 값은 문서에 적힌 설정뿐 아니라 **실제로 적용된 USD/PhysX 값**이다.

| 항목 | 전달 기준 및 확인 사항 |
|---|---|
| 질량·외형 | 과실 0.009kg, 외형 폭 0.070m/꼭지 포함 전체 높이 0.075m. collision mesh와 scale, COM/inertia, 원점 확인 |
| 충돌·재질 | 시각 mesh 기반 convex decomposition, 정지/운동 마찰 1.0/1.0, restitution 0.02, contact offset 1mm/rest offset 0. 재질 binding·combine mode도 기록 |
| 결합 | attachment4/response5 short hook, 인장 60N/m, 횡방향 비율0.25, 수직40N/m, 감쇠4.2Ns/m. force 조건 외 이동량 이탈 조건도 있음 |
| 분리 | 기본 임계힘2.5N(reset별2.0~3.0N), 인장 이동25mm 또는 전체40mm 이탈 분기, 조건 연속40ms. 단순 native breakable joint로 교체하면 별도 모델임 |
| 제어 | 정책20Hz(0.05초), 정규화된 관절 목표 증가량, 팔0.8rad/s·그리퍼1.2rad/s 기준. 직접 토크/절대각이 아님 |
| 물리 | nominal 240Hz/decimation12 + contact_substeps2 → 실제480Hz/decimation24. 실제 적용 dt를 로그에 기록 |
| 액추에이터 | 팔5개 effort limit 각2Nm, 그리퍼0.5Nm. stiffness/damping·관절 축/부호/제한도 기록 |
| 운반·놓기 | 팔 명령 scale0.25에서3초에1.0까지 확대, 정지 확인0.3초, 기준속도0.05m/s, transport_linear_pose_stop 활성, fixed release |
| 프레임 | 후보 JSON은 `arm_2/base_link` 기준 +X 과실, +Y 좌우, +Z 위, 단위m. farm/world/arm/policy 사이 TF와 quaternion 순서 명시 |
| 배치 | 첫 비교는 전달 `legacy-near` 후보18개 및 HOME, 과실2개 중 목표1개, 중심간 최소0.18m. 전체 직육면체 임의 샘플링과 구분 |

각 전문가 `run.json`의 학습 질량은0.035kg이며, 전달 평가는 명시적 override로0.009kg을 사용한다. 전문가 메타데이터의 질량과 runtime의 질량을 구분한다. 실행 환경 `runtime.mass`가0.009인지 확인한다.

추론을 물리 callback480Hz마다 호출하지 않는다. 렌더링 FPS와 무관하게 시뮬레이션 시간으로20Hz 호출하고 중간에는 목표를 유지한다. 물리를 낮췄다면 실제 dt/decimation과 성공률을 별도 비교한다.

## 5. 진단 순서와 회신 요약

1. 모델 해시·실행기·관측/출력 계약이 일치하는지 확인한다.
2. 독립 전달 평가 결과와 농장 결과를 분리한다.
3. 독립 평가도 실패하면 환경·자산·버전·접촉 설정부터 비교한다.
4. 독립 평가가 성공하면 같은 초기 관절·목표·임계값으로 농장에 배치하고 첫 관측/action이 달라지는 tick을 찾는다.
5. 목표에 접근하지 못함 / 진입 전에 밀어서 분리 / 잡은 뒤 접촉 소실 / 운반·정지 전환 실패 / 열기·적재 실패로 구분한다.

회신은 아래 형식이면 충분하다.

```text
받은 TAR SHA256 및 폴더:
Teacher 4개 경로·SHA256 검사 결과:
실행 명령 및 사용한 실행기:
독립 평가: 성공 __ / 실패 __ / 시간초과 __ / 목표미선정 __ / 실행오류 __
농장 평가: 성공 __ / 실패 __ / 시간초과 __ / 목표미선정 __ / 실행오류 __
실제 물리/정책/렌더 주기:
초기 로봇·목표·박스 프레임 및 TF:
첨부: 전체 stdout 로그, runtime/모델 계약, 에피소드 결과, 실패 trace, 관련 통합 코드
```

## 송신측 이번 빠른 검사

2026-10-08 초기 전달본 `harvest_teacher_9g_20261006_143434`의2148개 파일을 검사한 독립 복사본에서 빨강182/노랑183 seed 각5회 진단한다. 정책·전달 실행기·물리·자산 코드는 보존하고 영상/탐지 기록만 제외한다. 현재 Student 수집과 분리하며 학습 및 실물 구동을 하지 않는다.

진단 어댑터는 `scripts/sim_team/eval_delivered_teacher.py`다. 전달 `eval_current_pair.py`를 실행하면서 AppLauncher의 카메라 활성화, RGB-D rig 생성, 기록 루프만 대체한다. 모델 로더, `StagedTeacher`, 관측, 하위 제어, 판정은 전달 코드를 사용한다. 카메라/YOLO 목표 선정까지 포함한 전달 스크립트 전체 재현과는 구분한다.

결과 경로: `outputs/harvest_rl/delivered_teacher_check_20261008_105626_691560/`. `first_tick_reference.json`에는 색별 첫 장면의 초기 관측82개·전문가 시간 보정 관측82개·정규화 관측82개·실제 명령6개를 보존한다. 같은 초기 관절·배치·프레임에서만 숫자를 직접 비교한다.

완료 결과:

| 목표 | 적재 성공 | 실패 | 시간초과 | 완료 |
|---|---:|---:|---:|---:|
| 빨강(seed182) | 3 | 2 | 0 | 5 |
| 노랑(seed183) | 4 | 1 | 0 | 5 |
| 전체 | **7** | **3** | **0** | **10** |

성공은 박스 안 실제 안착 판정까지 완료한 경우다. 모든 성공 장면이 전문가 단계 -1→0→1→2를 거쳤고 정상 분리·보유를 확인했다. 실패는 빨강0의 파지 전 비유효 분리, 빨강4의 분리 후 capture 확인 실패, 노랑2의 정상 분리 후 보유 확인 전 낙하다. 운반/놓기 단계 실패 및 시간초과는 이번10회에서 없었다.

평가 종료 후 Teacher 4개와 각 `run.json` 해시가 프로파일과 계속 일치했다. 실제 물리480Hz/정책20Hz 및 질량9g을 로그로 확인했다. 기존 Student 수집과210파일 reference는 유지했다. 평가 어댑터 Python 구문·CLI·문서 및 diff 검사를 수행했다.

집계·실패 플래그는 `summary.json`, 색별 원본은 `run.json`/`expert_contract.json`/`actuator_runtime.json`/`diagnostic_runtime.json`/`episodes.json`/`metrics.json`, 정책 tick 기록은 `trace_*.jsonl`, 전체 stdout은 `red.log`/`yellow.log`다. 출처 및 실제 명령은 `red_invocation.json`/`yellow_invocation.json`에 있다.

이번7/10은 영상/탐지 기록을 제외한 제어·물리 진단이다. 과거 영상기록 포함6/10과 실행 경로가 달라 정책이 개선됐다는 비교로 해석하지 않는다. 같은 정책·실행기로 적재 동작이 가능함은 확인했지만 농장 통합 성공률·임의 위치·새 카메라·실물 성능의 보장은 아니다. 농장에서 전혀 파지하지 못한다면 위 관측/좌표/관절 명령 로그부터 비교한다.
