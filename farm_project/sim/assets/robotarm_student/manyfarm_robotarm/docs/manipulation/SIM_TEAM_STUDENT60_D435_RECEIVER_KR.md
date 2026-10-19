# D435 카메라 Student + v20 보조제어 전달본 — 2026-10-16

## 전달할 파일과 실행 범위

`harvest_student60_d435_v20_20261016.tar.gz`, `SHA256SUMS`, 이 README와
`SEND_MESSAGE_KR.txt`를 함께 전달한다. `.pt` 하나로 전달하면 수확 동작을 재현할 수 없다.
아카이브에는 정책·보조제어·탐지 모델·센서 설정·로봇 자산·검증 근거가 함께 있다.
수신자는 압축을 푼 `manyfarm_robotarm`을 작업 디렉터리로 사용한다.
기본 형식은 **PyTorch `.pt` + 실행 Python 소스 + USD/URDF 자산을 묶은 `.tar.gz`**다.
ONNX/TorchScript 단독 파일은 recurrent 이력·전처리·보조제어·실제 적용 확인을 함께 표현하지
않으므로 이번 인수 형식으로 사용하지 않는다.

| 구성 | 전달본 내부 경로 | 용도 |
|---|---|---|
| Student 가중치 | `handoff/models/student.pt` | recurrent camera Student, 원본 바이트 보존 |
| 카메라 중심 추정 보정 | `handoff/models/center.pt` | 영상 추정치·bbox·depth 품질 11입력 |
| 과실 분할 모델 | `handoff/models/detector.pt` | 기존 사용자 제공 YOLO 분할 모델 |
| 전체 입력·출력 계약/해시 | `handoff/DEPLOYMENT.json` | 관절 순서, 범위, 카메라 K/TF, 물성, 버전 |
| 현재 장착 형상 | `src/smartfarm_description/urdf/harvest_robot.urdf` 및 `meshes/` | 고정 프레임·두 SO101·박스·손목/후방 카메라 CAD |
| 카메라 포함 실행 자산 내보내기 | `handoff/robot/robot_with_d435.usdc` | 실제 평가 scene에서 분리한 로봇·현재 우측 손목 외형·센서 prim |
| 검증 당시 물리 USD | `outputs/harvest_rl/current_robot/b73ed90a6e56216d/` | 원래 강체·충돌·관성·구동 설정 및 레이어 |
| 센서 생성·영상 처리 | `src/harvest_robot/harvest_sensors/`, `harvest_vision/` | 활성 RGB/depth/IR render product 및 전처리 |
| 정책·보조제어 | `src/harvest_robot/harvest_runtime/`, `harvest_rl/` | 추론·상태·제한된 접근/파지/당김/운반/놓기 |
| 수신 실행기 | `scripts/sim_team/run_student60_delivered.py` | 전체 학습 데이터 없이 CPU 점검 / GUI / headless 시연 |
| 자체 scene 연결 예제 | `scripts/sim_team/student60_session.py` | 카메라·관절 입력→실제 적용할 명령→적용 확인 |
| 파일 무결성 | `handoff/MANIFEST.json` | 전달 파일별 크기·SHA256 |
| 수신 검증 기록 | `handoff/verification/` | 경로 이전 CPU 검사와 짧은 native 실행 결과 |

U20용 모델과 지연 반영 timing 후보는 실행 기본값에 포함하지 않았다. 원본 학습 데이터,
가상환경, `.git`, 실물 실행 도구는 전달 대상이 아니다. 동결 물성 프로파일의 무결성 검사에
필요한 Teacher 참조 체크포인트 4개는 포함하지만 **Student 실행은 Teacher actor를 로드하거나
호출하지 않는다**. 모델 입력의 정답 과실 위치·접촉력·분리 플래그·시뮬레이터 phase 사용도 없다.

## 설치 환경과 수신 후 실행

검증 환경은 **Linux**, Isaac Sim **5.1.0.0**, 설치 패키지 표기 Isaac Lab **0.54.2**,
Python **3.11**, PyTorch **2.7.0+cu128**, NumPy **1.26.0**, SciPy **1.15.3**이다.
정확한 설치 패키지는 `handoff/EXECUTION_ENVIRONMENT.json`을 확인한다.
실행기의 동시 작업 검사는 Linux `/proc` 기준이다.
Isaac Python과 Ultralytics용 별도 Python을 사용한다. 가상환경 디렉터리를 복사하지 않는다.
`handoff/VISION_ENVIRONMENT.json`에 탐지 환경의 버전을 기록했다.
다른 Isaac 버전에서는 USD 열림만 확인하고 정책 재현 성공을 가정하지 말고 아래 native 점검부터 한다.

```bash
sha256sum -c SHA256SUMS
tar -xzf harvest_student60_d435_v20_20261016.tar.gz
cd manyfarm_robotarm

# 각 팀 PC의 실제 실행 파일 경로로 지정
export HARVEST_PY=/path/to/isaac-python
export VISION_PYTHON=/path/to/vision-venv/bin/python

# GPU 시뮬레이션 없이 파일·모델·관측·원래 물성 pin 검사
"$HARVEST_PY" scripts/sim_team/run_student60_delivered.py --check-only

# 짧은 네이티브 점검: 완주/수확 성공률 평가가 아님
"$HARVEST_PY" scripts/sim_team/run_student60_delivered.py \
  --vision-python "$VISION_PYTHON" --output outputs/receiver_smoke_001 \
  --headless --colors Red --per-color 1 --smoke-steps 20

# 3D 수확 과정 + 손목 RGB/오른 IR/후방 RGB-D 입력 패널
"$HARVEST_PY" scripts/sim_team/run_student60_delivered.py \
  --vision-python "$VISION_PYTHON" --output outputs/receiver_gui_001
```

출력 경로는 매번 새 이름을 사용한다. GUI 기본값은 이미 평가한 seed106146의
Red/Yellow/Red/Yellow 4회다. 새 독립 평가로 집계하면 안 된다. 창을 끄거나 Ctrl+C로 종료한다.
본 실행은 시뮬레이션 시간 기준 정책20Hz/물리60Hz/촬영30Hz이며 실제 시계보다 느릴 수 있다.
기존 전달본의 `prepare_receiver.py`로 이 Student 전달본을 수정하지 않는다.
원래 pin 파일은 그대로 보존하고 새 실행기가 USD 입력 경로만 전달본 내부로 바꾼다.
학습 계획 JSON의 과거 절대 경로는 출처 기록이며 원본 학습 폴더를 읽지 않는다.

## 카메라가 달린 로봇 자산 사용

URDF와 mesh 폴더는 상대적인 `package://smartfarm_description/` 구조를 유지한다.
이 URDF는 현재 센서 장착 형상·FK 기준이다. **정책 재현을 위해 현재 URDF를 새로 물리 변환해
기존 frozen USD를 교체하지 않는다.** 검증된 물성은 동결 USD이며, 현재 우측 손목 외형만
시각적으로 덧씌웠다. 현재 마운트의 질량·충돌을 새로 넣어 검증한 결과가 아니다.

`robot_with_d435.usdc`는 평가 장면의 실제 로봇을 별도로 내보낸 자산이다. 고정 프레임,
두 팔, 박스와 원래 강체 물성을 포함한다. 실제 제어 대상은 **우측 arm_2 한 팔**이다.
이동 플랫폼 주행·양팔 협조·농장 전체 scene은 포함 범위가 아니다.
USD 기본 prim `/World`를 기존 scene 아래 reference하고 팀 scene의 physicsScene을 사용한다.
카메라 prim은 우측 손목 강체 아래에 배치해 관절 운동을 따라가며 후방 카메라는 prefab에 고정했다.
센서 경로는 `handoff/robot/export_audit.json`에 있다. 오른쪽 원시 depth 카메라도 진단용으로
함께 있으며 **정책과 과실 3D 추정에는 손목 depth를 넣지 않는다**.

USD의 카메라 prim만 열어서는 RGB/depth 배열이나 ROS 토픽이 자동 발행되지 않는다.
받는 팀이 해당 prim에 RTX render product/annotator를 연결하거나 아래 원래 rig를 사용한다.

내보낸 카메라는 원래 rig의 중심 정렬 overscan 렌더 설정을 사용한다. native 해상도로만
render product를 지정하면 주점/K가 달라질 수 있다. `handoff/verification/robot_asset_check.json`의
각 stream `render_wh`/`render_k`로 렌더하고 `harvest_sensors.profile.remap_render`로 native 영상에
복원하거나, 이 처리가 포함된 원래 rig를 사용한다.

- 생성: `harvest_sensors.deployment_rig.DeploymentD435Rig`.
- 매 물리 tick에서 실제 측정 관절/손목 자세를 반영하고 촬영30Hz를 유지한다.
  참조 구현은 `install_physics_hook(env)`, `begin_episode(None)`, `capture()`다.
- 원래 rig를 쓰면 센서를 자체 생성하므로, prefab 카메라에 다시 render product를 붙여
  중복 촬영하지 않는다. 전체 독립 시연 실행기가 가장 먼저 확인할 재현 기준이다.
- 농장 scene 연결 시 원래 rig의 고정 `/World/StudentD435_*` 경로와 단일환경 전제를
  robot namespace로 감싸는 어댑터가 필요하다. 외부 scene을 자동 reset하거나 로봇을 순간이동시키면 안 된다.

| 사용 영상 | 원본 해상도 | 의미 |
|---|---:|---|
| 우측 손목 RGB | 1280×720 @30fps | 손목 근접 시야 |
| 우측 손목 **오른쪽** IR, stream index2 | 848×480 @30fps | RGB와 다른 렌즈/광학 pose, 근접 과실 가림 보완 |
| 후방/오버헤드 RGB | 1280×720 @30fps | 분할 탐지·전역 접근 |
| 후방 native depth | 848×480 @30fps | 광학 Z[m], 무효0, 공장 내부TF로 RGB에 정렬 |

K·왜곡·내부TF는 `src/harvest_robot/config/d435_deployment_20261013_overhead30.json`과
`DEPLOYMENT.json`에 있다. 광학 좌표는 x오른쪽/y아래/z전방이다. RGB와 오른 IR의 같은 픽셀을
같은 광선으로 취급하지 않는다. IR은 시뮬레이터 가시광 흑백 기하 근사이며 NIR/투사기/stereo
실패를 재현하지 않는다. 실제 카메라 공장 내부 보정과 실물 장착 hand-eye 검증은 별개다.

## 시뮬레이션팀 scene에 연결할 계약

`student60_session.py`의 `Student60Session`은 외부 scene을 만들거나 reset하지 않는다.
`start(target_id, label, initial_applied_joint_goals_rad)`로 작업을 시작하고
`step(capture,q_rad,qd_rad_s,elapsed_s)`의 명령을 자체 명령 경계로 적용한 뒤
`acknowledge(actually_applied_command)`를 호출한다. 이 어댑터의 실제 농장 scene 통합은 별도 작업이다.
처음에는 한 로봇·우측 한 팔·단일 지정 과실로 맞춘다. 색상 하나만 남았을 때 선택하는 예제이므로
동색 복수 과실의 외부 target_id↔비전 track 매핑은 팀 배정 프로토콜에 연결해야 한다.

입력 capture는 right/rear별 RGB, `aligned_depth_m`, `raw_depth_m`, `depth_m`, `color_from_depth`,
`ir['ir_right']`(right), 원본 stream별 `intrinsics`, `world_from_optical`,
`stamp_s`, `pose_stamp_s`, `frame_number`를 가진다. 원래 rig의 `capture()` 반환값이 기준이다.
관절은 실제 시뮬레이터 측정값6개, rad/rad·s 단위이고 촬영 시각/pose 시각을 보존한다.
TCP는 관절과 제공된 URDF의 `grasp_fk`에서 계산한다.

| 명령 항목 | 정확한 의미 |
|---|---|
| 출력0~5 | 정규화[-1,1]의 **절대 관절 목표**, delta/토크가 아님 |
| 관절 순서 | arm_2_shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper |
| 출력6 | 정규화[-1,1] → 집게 position drive 강성1~8 Nm/rad |
| 출력7 | 정규화[-1,1] → 집게 속도 제한0.15~1.5 rad/s |
| 역변환 | `harvest_runtime.student60.decode_command(command, lower_rad, upper_rad)` |
| 이력 갱신 | 예측 직후가 아니라 **실제 적용한 명령**으로 acknowledge |

팔 나머지 drive·집게 damping/effort·마찰·과실9g/70mm/75mm·response6/attachment4·
박스 좌표는 제공된 계약을 유지한다. 집게 출력6을 STS3215의 P gain/토크 제한과 같은 값으로
직접 대응시키는 실물 연결은 구현되지 않았다. 전체 환경의 좌표를 이동하면 카메라 world pose와
`world_from_robot`도 일치시킨다. 박스와 팔의 상대 배치를 바꾸면 기존 계약을 그대로 쓸 수 없다.

카메라·정규화 상태23·후방 target crop96×96이 신경망 입력이다. 전체 RGB/IR 입력은160×90으로
전처리하며 손목 depth 자리는0이다. 상태는 측정q6+측정qd6+이전 실제 적용 목표6+
비전 목표−TCP3+유효성1+age1이다. Teacher 관측82차원과 섞지 않는다.
기존 v20의 연속20Hz 시뮬레이션 시각을 유지해야 하며 임의 간격으로 step을 호출하는 정책이 아니다.

기존 ROS2 Action/상태·permission 경계는 `docs/INTERFACES.md` 원본을 따른다.
이번 전달본은 독립 재현과 내부 Python 연결 예제이며 농장용 ROS backend 완성본이 아니다.
실제 농장 연결은 허용·취소·실제 정지 확인·작업 ID·동일 시계 stamp·성공 판정 경계를
각 담당 팀 어댑터에서 연결한다. 정책 함수에 정답 과실 위치나 접촉 판정을 넣지 않는다.

## 확인된 성능과 인수 기준

개발4/4와 소스를 고정한 별도 seed106146 평가4/4에서 박스 적재에 성공했다.
이는 9g 과실·우측 한 팔의 작은 평가이며 일반 성공률100%를 뜻하지 않는다.
보조제어를 포함한 결과이고 신경망 단독 성능이 아니다. 성공 기준 `box_outcome_v2`는
분리된 과실의 실제 mesh가 박스 안에 정지하고 양 집게와 떨어진 상태를0.6초 유지하는 것이다.
legacy grasp/release 품질 점수는 별도 진단으로 남긴다.

지연을 주입한 별도 timing 후보는4회 중0회 성공하여 이번 기본 실행에서 제외했다.
v20 전달은 실시간20Hz 처리나 실물 수확 성공을 인증하지 않는다. 카메라 hand-eye,
실물 payload, 관절 방향·영점·backlash, 통신 및 집게 출력의 모터 매핑은 후속 검증 대상이다.

수신팀 인수 확인 순서는 다음과 같다.

1. SHA256 및 CPU check 통과.
2. 두 팔·박스·손목/후방 카메라 외형과 sensor prim 확인.
3. 짧은 native 실행에서 네 가지 정책 입력 영상, 시각, 관절 순서/단위 확인.
4. 알려진4장면 완주 후 같은 box_outcome_v2 결과와 command boundary 확인.
5. 그 뒤 기존 농장 scene에 한 팔부터 연결하고 새 seed/작물/물성 조건을 별도로 평가.

수신 시 Isaac/Isaac Lab 버전, GPU, 위 점검 결과, 바꾼 scene/물성/카메라 항목을 회신하면
차이를 대조할 수 있다. 과실 정답/접촉 정보는 평가에만 사용하고 제어 입력과 분리한다.
