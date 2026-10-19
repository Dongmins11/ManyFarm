# ROS 2 인터페이스

## 2026-10-16 — D435 Student/v20 시뮬레이션 전달 내부 API

`scripts/sim_team/student60_session.py`의 `Student60Session`은 외부 scene을 reset하지 않는
내부 Python 연결 예제다. 기존 ROS 메시지/Action/state는 변경하지 않는다.
`start(target_id,label,initial_applied_joint_goals_rad)` →
`step(capture,q_rad,qd_rad_s,elapsed_s)` → 실제8출력 적용 →
`acknowledge(actually_applied_command)` 순서이며 우측 한 팔/연속20Hz 시뮬레이션 시각을 유지한다.
촬영30Hz의 원래 영상·K·TF·stamp와 측정 관절6개가 입력이고 TCP는 제공 URDF의 공개 FK다.
출력6절대 관절목표+집게 강성/속도2, NN·v20 보조제어를 함께 사용한다.
Teacher/정답 과실/접촉/분리 flag는 제어 입력에 없다. 농장 ROS backend·동색 다중 track 매핑은
아직 별도 통합 대상이다. 상세 계약/검증 범위는
`manipulation/SIM_TEAM_STUDENT60_D435_RECEIVER_KR.md`를 따른다.

## 2026-10-15 — 내부 Student timing 계약 v1

`harvest_runtime.student60_timing`은 기존 ROS 메시지와 상태 enum을 유지하는 별도 내부 Python 실행 계약이다. 시뮬레이터 정답/Teacher/접촉/물리 phase는 입력에 없다. 여기서 phase는 보조제어기 자신의 관측/접근/삽입/닫힘/보유/당김/운반/놓기 상태다.

| 입력/경계 | 필수 정보와 의미 |
|---|---|
| `ingest_camera(capture, received_s)` | right/rear 원본 RGB·depth·오른IR·K·광학TF·frame_number·원래`stamp_s`/`pose_stamp_s`/촬영 관절. 시각은 공통 monotonic 초. 늦게 도착한 과거 프레임은 최신 프레임을 덮지 않음 |
| `ingest_proprio(stamp_s,q,qd,tcp,received_s)` | 측정 관절6개 rad/rad·s와 공개 FK TCP[m]. 원래 측정 시각과 도착 시각을 구분. 최신 목표를 측정 관절로 대신하지 않음 |
| `tick(now)` |20Hz 소비자가 최신 완료 명령을 가져오고 dispatch에서 age 재검사. 미완료/기한 초과 시 마지막 실제 적용 목표 유지. 캡처/pose/수신/vision 완료/정책 요청·완료/관절 시각/거부 원인을 trace에 기록 |
| `applied(command,now)` | 실제 명령 경계가 적용한8출력 확인 뒤 호출. 시뮬레이션의 실제 command boundary 또는 읽기 전용 replay sink만 현재 연결됨. 예측만으로 ack 금지 |
| `RosClockMap` / `JointHistory` | ROS 원본 header age를 보존해 monotonic으로 변환, clock jump 거부. 촬영 관절은 양쪽 실측 표본으로만 보간하고 현재 관절을 과거 촬영 pose로 대입하지 않음 |

NN의 목표50ms/카메라300ms 계약은 유지하며, helper 목표 age 후보만 단계별로 별도 정의한다. `TimingProfile`은6구간 지연의 출처/측정 종류/표본을 요구하고 일부 가정을 실측으로 승격하지 않는다. wall worker는 실행1개·대기 최신1개이며 상태 보유 정책은 실제 ack 전 다음 계산을 시작하지 않는다. Python worker와 복사 비용이 있어 하드 실시간20Hz 보장은 별도 계측 대상이다.

실물 카메라 드라이버 header가 실제 노출 시각인지, 카메라 간 시계 동기화, hand-eye, 서보 읽기/쓰기 완료와 유한 preload 대응은 아직 검증되지 않았다. 이 구현에는 실물 actuator publisher/serial driver가 없다. 시뮬레이터 강성 출력의 실물 STS 명령 매핑을 완료한 것으로 취급하지 않는다. 기존 ROS 접점 변경 전 본 문서를 다시 갱신한다.

## 2026-10-13 — 오버헤드30fps 공장 내부 보정 프로파일 확인

D435920312070027의USB3/5Gbps·RGB1280×720/depth848×480@30 실수신과 SDK 공장 K/왜곡/색→depth 내부TF를 확인했다. 새 `d435_deployment_20261013_overhead30.json`은 rear target_profile_verified/internal_calibration_verified를 참으로 기록하되, 실제 미장착으로 mount_calibration_verified/calibration_verified는 거짓이다. 공장값 조회·목표 프로파일 확인과 checkerboard 기반 정확도 검증을 구분한다. 촬영30Hz/제어20Hz/Student v3 입력 계약은 유지한다. 이전 프로파일과 이미 진행 중인 Student60 수집의 원본/소스 pin은 변경하지 않는다.

## 2026-10-13 — Jetson 더미 통합 운용 v1

`harvest_jetson`은 기존 팔 Window 계약 위에 아래 임시 접점을 추가한다. 모두
`robot_id`(기본 harvest_01)로 구분하며 관제팀 확정 프로토콜은 아니다.

| 접점 | 타입 | 의미 |
|---|---|---|
| `/<robot>/mission/harvest` | HarvestWindow Action | 더미 관제→로봇 관리자→기존 팔 Action 전달, feedback/result/cancel |
| `/<robot>/mission/status` | ArmStatus | 관리자 공통 state(IDLE/RUNNING/ERROR/UNAVAILABLE), 팔 phase 별도 보존 |
| `/<robot>/box/set_open` | std_srvs/SetBool | true 열기/false 닫기 요청 수락. 완료는 BoxStatus로 확인 |
| `/<robot>/box/status` | BoxStatus | CLOSED/OPENING/OPEN/CLOSING/ERROR, 0~1 열림 비율, 항상 dummy=true |
| `/<robot>/arm/dummy_joint_states` | sensor_msgs/JointState | 성공 Teacher의 기록된 관절 목표[rad] 가상 재생. 실물 command가 아님 |
| `/<robot>/arm/dummy_phase` | std_msgs/String | 기록에서 읽은 접근/파지/당김/운반/적재 및 가상 복귀 단계 |
| `/<robot>/camera/{wrist,overhead}/{color,depth,ir_right}/image_raw` | sensor_msgs/Image | RGB8/32FC1[m]/mono8, best effort. depth 0은 무효 |
| 같은 stream의 `camera_info` | sensor_msgs/CameraInfo | 영상과 같은 stamp/optical frame; native stream별 내부 보정 |
| `/<robot>/camera/{wrist,overhead}/status` | diagnostic_msgs/DiagnosticArray | dummy/realsense, 새 frame 수신/timeout/오류 구분 |

관리자는 최신 dummy backend 상태를 확인해야 Goal/permission/가상 Vision을 보낸다.
실물 주행 permission을 위조하는 운영 노드가 아니며 실제 주행 연동 때 교체한다.
더미 목표 수는 설정된 목록으로 결정하고 expected_count를 완료 근거로 쓰지 않는다.
취소/허용 상실은 기존 STOPPING 경로, 결과 후 permission 해제 및 반영 확인을 따른다.
박스는 신선한 팔 복귀·정지·허용해제 상태에서만 개폐하고, 열림/이동/통신 상실 시
팔 시작을 거부한다. 수확 중 하부 배출판은 닫힘을 유지한다. MG996R GPIO/PWM은 쓰지 않는다.
Teacher는 `teacher60_finger_friction_run_v2` 성공 평가 한 건의 원래20Hz 목표를
재생하며 판정은 명시적 dummy다. 실시간 신경망 추론/카메라 기반 성공 검증은 아니다.
카메라 실물 모드는 시리얼을 명시하고 오류 시 합성 영상으로 자동 전환하지 않는다.
카메라 내부 보정과 robot hand-eye/TF는 별개이며 가상 Vision은 영상에서 탐지한 결과가 아니다.
BoxStatus는 reliable/volatile depth1, 기본10Hz; 팔 상태 TTL2.5초와 박스 TTL0.6초는 임시값이다.

## 2026-10-13 — Student 멀티모달 촬영 계약 v3

사용자 최종 선택은 손목 RGB+오른IR(Depth 정책 제외), 후방/오버헤드 RGB+Depth다. `d435_deployment_v2`는 right/rear 장치별 K와 공장 T_color_from_depth/right_IR를 지원한다. `physics_scheduled_multimodal_v3`는 촬영30Hz·제어20Hz·history3을 분리한다. NPZ는 기존 rgb/depth_m/camera_valid/state/action과 wrist_ir_right/wrist_ir_valid를 저장한다. depth_m[right]는0이고 새 네트워크는 손목RGB3/손목IR1/후방RGB-D5를 각각 인코딩한다. RGB와IR의 같은 픽셀 번호를 대응점으로 취급하지 않는다.

제어 시각, 촬영 frame number·촬영/pose 시각·촬영 관절·K/TF·원본 RGB/IR/depth를 별도 저장한다. 장착 FK는 촬영 관절로 검사하고 reset에서 프레임/history를 비운다. 오버헤드 분할은 원본RGB에 수행하고, 마스크를 내부TF로 native depth에 대응시켜 기존 품질 기준을 적용한다. 정렬 depth의 결측은0/mask로 유지한다. v2 데이터/체크포인트를 새 계약과 묵시적으로 혼합하지 않는다.

Teacher 물리자산/정책을 바꾸지 않는 별도1환경 센서 수집 경로이며 ROS 메시지는 그대로다. 두 장치 hand-eye는 미완료, rear 목표30fps K는 임시다. IR 렌더는 별도 광학 위치의 가시광 흑백 근사이며 NIR/투사기/실제 stereo 재현이 아니다. 상세: manipulation/STUDENT_DEPLOYMENT_CAMERA_KR.md.

## 2026-10-13 — 실물 D435 프로파일에 맞춘 Student 센서 실험 v1

- 기존 ROS Topic/Action과 Teacher tensor 입력, 동결 Student v2 계약은 유지한다. 별도 `harvest_sensors` 경로의 `d435_student_sensor_v1`은 손목 RGB 1280×720, native depth/좌우 IR 848×480의 실제 SDK K·RGB_from_stream·획득 fps를 사용한다. 공장 내부 보정과 gripper→camera 외부 보정의 검증 여부를 별도로 기록한다.
- Optical 좌표는 x 오른쪽/y 아래/z 전방, depth는 광학 Z[m], 0은 무효다. RGB·IR 영상은 서로 다른 렌즈의 원본 시야를 보존하며 같은 픽셀 좌표로 취급하지 않는다. RGB용 depth만 공장 extrinsic으로 재투영하고 구멍을 채우지 않는다.
- `rgbd`, `rgbd_ir_left`, `rgbd_ir_right`, `rgbd_ir_pair` 비교 입력은 RGB-D(5채널)와 각 IR(1채널)을 별도 배열로 저장한다. 영상은 비율을 유지해 160×90으로 축소하고 패딩·depth validity mask를 기록한다. 기존 v2 데이터/체크포인트와 자동 혼용하지 않는다.
- 프레임 번호·각 스트림 timestamp/domain·age·emitter 상태를 보존한다. 제어 tick 반복 수신을 새 영상으로 간주하지 않는다. 실제 6fps와 제어 20Hz는 별도 값이며, 시뮬레이션 센서 갱신도 획득 fps를 따른다. 기존 v2 추론·학습 실행기는 이 실험 입력에 아직 연결되지 않는다.
- IR 시뮬레이션 영상은 실제 IR optical pose의 가시광 흑백 기하 근사다. NIR 반사·IR projector·stereo 실패를 재현한 센서로 표시하지 않는다. rear 카메라는 미측정 nominal 값을 명시한다. 모터 명령·ROS 발행·학습 자동 시작 없음.

## 2026-10-12 — 수확 주행부 ↔ 팔 Window 운용 어댑터 v1

- 근거: 관제 Confluence `수확 <-> 수확팔 통신 프로토콜` 29589533, 2판(2026-10-08). 기존 단일 과실/학습 계약은 보존하며 새 `harvest_arm_interfaces`, `harvest_arm_control` 패키지에서 Window 작업을 관리한다. 팀 간 최종 합의 전 구현 가능한 초안이다.
- `/harvest_01/arm/harvest_window`: `HarvestWindow` Action. Goal은 robot/arm/task/window/operation ID, 예상 개수, 선택적 Window/대상 timeout이다. operation ID는 주행부가 Window 실행 시도마다 생성한다. 단일 작업만 수락하며 중복 ID는 영속 저널에서 거부한다. expected_count는 종료 조건이 아니다.
- `/harvest_01/arm/status`: `ArmStatus`, 1Hz 및 변경 즉시. 내부 phase와 외부 state, ready, arm_stowed, motion_inhibited, stop_confirmed, 오류, boot_id/sequence, 적용한 permission boot_id/sequence를 보고한다. 종료/정지와 실제 복귀는 별개다.
- `/harvest_01/arm/permission`: `ArmPermission`, 주행부 발행. 현재 robot/arm/task/window/operation 일치, base_stopped, !transfer_active, !estop_active, motion_allowed, 메시지 유효시간을 모두 검사한다. 순번 역행/중복/폐기된 boot 세션은 거부한다. 허용 상실 시 새 수확/복귀 명령을 차단하고 정지 확인 후 실패로 종료한다. 통신 복구는 자동 재개가 아니다.
- `/harvest_01/arm/targets`: `WindowTargets`, Vision 어댑터 입력. 현재 작업 ID, 유효 센서 상태, 과실별 target_id/frame/stamp/position[m]/valid를 제공한다. 좌표는 설정한 팔 기준 프레임(기본 arm_2/base_link)으로 사전 보정해야 한다. core는 TF를 추측하지 않는다. 빈 목록만으로 종료하지 않으며, 작업/복귀 후 새 관측의 no_targets_confirmed와 비어 있지 않은 completion_evidence가 필요하다. 종료 알고리즘은 Vision/팀 합의 사항이다.
- failed_count는 최종 실패한 대상 수, failed_attempt_count는 실패한 시도 수로 분리한다. v1은 자동 재시도/건너뛰기가 없으므로 첫 대상 실패에서 종료한다. 이미 확인한 적재 수는 복귀 실패/취소에도 보존한다. Feedback은 작업 시작/phase/개수 변경 시 발행한다.
- ROS stamp는 노드의 ROS clock domain, timestamp 문자열은 ISO8601 기록용이다. 실행기/watchdog는 수신 측 monotonic clock으로 실행한다. 메시지 age는 ROS clock에서 계산 후 core monotonic 관측 시각으로 변환한다. 실물 ROS time은 동기화된 system time, simulation time은 명시적 use_sim_time이다. permission은 reliable/volatile/keep-last1; 자체 TTL 검사와 장치 watchdog를 대체하지 않는다.
- `/harvest_01/arm/reset_fault`: Trigger. 작업 없음·허용 해제·실제 정지/복귀/정상 상태에서 오류 래치만 해제하며 모터 이동/환경 reset은 하지 않는다. `/harvest_01/arm/get_window_result`: 영속 결과 조회.
- 정상: 허용 유지 중 수확/복귀 → 실제 복귀 확인/Result → 주행부 허용 해제 → 해당 permission 반영/정지/복귀 확인 → 주행/인계. 비정상: STOPPING → 정지 확인 → FAILED/CANCELED; 복귀하지 못했으면 arm_stowed=false로 이동 금지. 정지 확인 실패는 STOP_UNCONFIRMED 오류다.
- 기본 backend는 disabled이며 실제 장치 연결 없이는 Goal을 거부한다. mock는 명시적 통신 시험용으로 상태/결과에 표시한다. 실물/Isaac 정책·장치 backend는 별도 factory 계약으로 연결하며 학습은 ROS를 import하지 않는다. 현재 모터·카메라·정책 성능 검증을 의미하지 않는다.
- 로컬 시제품 기본값: permission TTL0.6s, Vision TTL0.5s, Window120s, 대상20s, 복귀20s, 정지확인2s, 제어 tick20Hz. 모두 설정 가능하며 팀 합의값으로 확정하지 않는다. 구현/실행/연결 계약: `src/harvest_arm_control/README.md`.

2026-09-15: 상판 상면은 지면에서 0.705 m (팔 장착판 제외), 모든 프레임 프로파일은 0.03 × 0.03 m. 중간 가로보와 하부 박스 받침을 제거하고 외형 0.20 × 0.20 × 0.20 m의 열린 박스를 상단 전면 가로보에 직접 고정한다. 박스 후면 x=0.30 m를 가로보 전면에 맞추며, 입구 z=0.701 m는 상판 아래 프로파일 상면에 맞춘 배치값이다. 팔 베이스 높이는 0.713 m다.

> 상태: 초안. 다른 파트와 합의되기 전까지 임시 표준으로 사용한다.
> 상세 설계 원본: `docs/manipulation/PHASE1_DESIGN.md`

## 책임 경계

- 관제: 작업 ID, 로봇 ID, 대상 ID, 실행·취소 명령과 우선순위를 제공하고 전체 작업 상태를 관리한다.
- 모바일: 목표 지점 도착, 도킹 완료, 차체 정지 상태와 base pose를 제공한다.
- Vision: 대상 ID, 3D pose, 크기, 신뢰도와 timestamp를 제공한다.
- Manipulation: 접근, 파지, 당기기, 분리 확인, 트레이 적재, 내부 상태와 결과를 제공한다.
- Simulation: 농장 scene, 작물·카메라·물리 환경과 simulation time을 제공한다.

## 3. 통신 프로토콜 선정안

## 3.1 기본 원칙

- 파트 간 실시간 데이터와 명령은 **ROS 2**를 사용한다.
- 긴 실행 명령, feedback, cancel이 필요한 작업은 **Action**을 사용한다.
- 연속 센서 데이터는 **Topic**을 사용한다.
- 짧고 즉시 끝나는 설정/조회/리셋은 **Service**를 사용한다.
- 실제 안전 정지는 ROS 2와 독립된 하드웨어 회로를 사용한다. ROS software stop은 보조 기능이다.
- 모든 pose 메시지는 `header.frame_id`와 timestamp를 필수로 한다.
- 강화학습의 병렬 environment step, observation, action, reward 경로에는 ROS 2를 사용하지 않는다.
- 학습된 정책의 환경 평가와 시뮬레이션·실물 운용에서는 동일한 ROS 2 입출력 계약을 사용한다.
- ROS 2 정책 실행 노드는 joint state와 목표를 observation으로 변환하고, 정책 출력을 안전 제한을 거쳐 로봇 명령으로 변환한다.
- 관제와 합의하기 전까지 아래 명칭을 임시 표준으로 사용한다.

## 3.2 Namespace와 frame

```text
ROS namespaces: /manipulator/arm_1, /manipulator/arm_2

base_footprint
└── base_link                       # existing Vic Pinky
    ├── wheels / lidar_mount / laser_link
    └── platform_base               # fixed, same pose as base_link
        └── upper_frame
            ├── top_deck
            │   ├── arm_1_mount -> arm_1/base_link -> ... -> arm_1/tool0
            │   └── arm_2_mount -> arm_2/base_link -> ... -> arm_2/tool0
            └── upper_rail_front -> box_support -> harvest_box
                ├── place_left
                └── place_right
```

2026-09-14: 승강축을 생략한 양팔 고정 프레임 자산의 TF 초안이다. x 전방(현재 작업면), y 좌측, z 위쪽, 단위 m/rad. `map/odom -> base_footprint`는 모바일 측 소유이며 조합 URDF에 world 고정 joint를 넣지 않는다. 팔 link/joint에는 `arm_1/`, `arm_2/` prefix를 사용한다. ROS namespace만으로 link/joint 이름은 변경되지 않는다.

`tool0`는 원본 `gripper_frame_link`의 동일 pose alias이며 실물 TCP 보정 전 임시 기준이다. `place_left/right`는 박스 내부 바닥 위 기준 프레임으로, 과실 크기·적재 높이·자세를 반영한 최종 명령 pose가 아니다. Phase 1 Action은 기존처럼 arm_1부터 검증한다.

### 2026-09-15 D435 장착 프레임

양쪽 `arm_i/gripper_link -> arm_i/wrist_camera_mount_link -> arm_i/wrist_camera_link`를 fixed로 연결한다. 중앙은 `top_deck -> overhead_base_link -> overhead_riser_link -> overhead_post_link -> overhead_adapter_link -> top_camera_link`다. 카메라 link 원점은 몸체 중심이며 +x 시선, +y 왼쪽, +z 위쪽이다. 각각 `_color_frame`, `_depth_frame` 및 `_color_optical_frame`, `_depth_optical_frame`을 갖는다. Optical frame은 +z 시선, +x 오른쪽, +y 아래쪽이다. RGB/depth offset은 nominal 값이며 실물 보정값으로 대체해야 한다.

`overhead_camera_height_above_deck=0.10`은 상판 상면에서 `top_camera_link` 몸체 중심까지의 높이이다. 따라서 기본 지상 높이는 0.805 m다. 중앙 카메라는 전방(+x)을 보며 위치·방향을 설정에서 변경한다. 0.10 m 배치를 위해 중앙 포스트 STL의 세로축만 시뮬레이션상 0.06285 m로 축소한다. 실물 드라이버와 URDF가 동일 TF를 중복 발행하지 않도록 최종 통합 시 발행 주체를 정한다.

기존 `/manipulator/arm_1/wrist_camera` RGB 계약을 arm_2에도 동일하게 적용한다. 각 손목 및 `/top_camera` namespace의 `depth/image_raw`, `depth/camera_info`는 향후 RGB-D 발행 경로다. 이번 구현은 URDF의 형상·질량·collision·좌표계만 포함하며 영상 발행기나 Isaac 센서를 생성하지 않는다.

## 3.3 인터페이스 목록

| 방향 | 이름(임시) | 형식 | 용도 | QoS/조건 |
|---|---|---|---|---|
| Robot → 전체 | `/joint_states` | `sensor_msgs/JointState` | 관절 상태 | best effort, 50 Hz |
| Robot → 전체 | `/tf`, `/tf_static` | TF2 | 좌표계 | 표준 TF QoS |
| Camera → 인식 | `/manipulator/arm_1/wrist_camera/image_raw` | `sensor_msgs/Image` | 손목 RGB | best effort, 15 Hz |
| Camera → 인식 | `/manipulator/arm_1/wrist_camera/camera_info` | `sensor_msgs/CameraInfo` | 내부 파라미터 | reliable/transient local |
| Camera → 인식 | `/top_camera/image_raw` | `sensor_msgs/Image` | 상단 RGB | best effort, 15 Hz |
| 인식 → 관제/Robot | `/perception/target_pose` | `geometry_msgs/PoseStamped` | 추정 목표 | reliable, event 기반 |
| Vision → Robot | `/harvest_robot/vision/targets` | `vision_msgs/Detection3DArray` 또는 합의한 custom msg | 대상 ID·3D pose·크기·신뢰도 | reliable, event 기반 |
| Mobile → Robot | `/harvest_robot/mobile/state` | 공통 `RobotState` | 도착·도킹·차체 정지 확인 | reliable, 변경 즉시+heartbeat |
| Robot → Mobile | `/harvest_robot/manipulation/base_motion_inhibit` | `std_msgs/Bool` | 수확 중 차체 이동 금지 | reliable, transient local |
| 관제 → Robot | `/harvest_robot/manipulation/harvest` | `HarvestTarget.action` | 대상 수확·트레이 적재 | reliable Action |
| 내부 시험 | `/manipulator/arm_1/reach` | `ReachPose.action` | Reach 단위 시험 | reliable Action |
| 관제 → Robot | `/manipulator/arm_1/reset` | `std_srvs/Trigger` | 오류/episode reset | reliable Service |
| 관제 → Robot | `/manipulator/arm_1/software_stop` | `std_msgs/Bool` | 보조 정지 | reliable, transient local |
| 수확 로봇 관리 → 관제 | `/harvest_robot/status` | 공통 `RobotTaskStatus` | 공통 robot/task state, phase, 결과 | reliable, 2~10 Hz+변경 즉시 |
| Robot arm → 수확 로봇 관리/디버깅 | `/harvest_robot/manipulation/status` | `ManipulatorStatus` | 접근·파지·당기기 등 내부 상세 상태 | reliable, 10 Hz+변경 즉시 |
| Robot → 관제 | `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | 진단 | reliable, 1~5 Hz |
| Sim → 전체 | `/clock` | `rosgraph_msgs/Clock` | simulation time | 표준 clock QoS |

카메라 depth가 필요해지면 `image_raw`와 동일 namespace에 `depth/image_raw`를 추가한다.

관제는 `수확 대상 X를 처리하라`는 큰 단위 명령만 보내고, 접근·파지·당기기·적재의 세부 상태 전환은 수확 로봇 관리 노드가 담당한다.

## 3.4 외부 Harvest Action 초안

```text
# HarvestTarget.action Goal
string task_id
string target_id
string tray_id
geometry_msgs/PoseStamped target_pose
geometry_msgs/Vector3 preferred_pull_direction
float32 target_radius_m
uint8 max_retries
float32 timeout_sec
---
# Result
bool success
uint16 result_code
string message
uint8 retries_used
geometry_msgs/PoseStamped final_target_pose
duration elapsed_time
---
# Feedback
uint8 manipulation_state
float32 progress
string detail
```

`preferred_pull_direction`은 Vision이 줄기/과실 방향을 신뢰성 있게 추정할 수 있을 때만 사용한다. 제공되지 않으면 로봇팔 파트의 설정된 기본 당김 방향 또는 재배 구조 기준 방향을 사용한다.

## 3.5 내부 Reach Action 초안

```text
# ReachPose.action Goal
string request_id
string arm_id
geometry_msgs/PoseStamped target_pose
float32 position_tolerance_m
float32 orientation_tolerance_rad
float32 timeout_sec
float32 max_velocity_scale
---
# Result
bool success
uint16 result_code
string message
geometry_msgs/PoseStamped final_pose
float32 position_error_m
float32 orientation_error_rad
duration elapsed_time
---
# Feedback
uint8 state
float32 progress
geometry_msgs/PoseStamped current_pose
float32 position_error_m
float32 orientation_error_rad
```

### Goal 검증 규칙

- `request_id`는 중복되지 않아야 한다.
- `arm_id`는 1차에서 `arm_1`만 허용한다.
- timestamp가 현재 시간보다 설정값 이상 오래되면 거부한다.
- 지원되지 않는 `frame_id`는 TF 변환을 시도하고, 변환 실패 시 거부한다.
- position/orientation에 NaN 또는 Inf가 있으면 거부한다.
- workspace 밖 목표는 실행 전에 `INVALID_GOAL`로 반환한다.
- tolerance와 timeout이 0이면 서버 기본값을 사용한다.

## 박스 바닥 슬라이드 관절 (2026-09-15)

박스 몸체 `harvest_box`는 고정한다. `box_bottom_left_joint`는 `box_bottom_left`를 +y로, `box_bottom_right_joint`는 `box_bottom_right`를 -y로 이동시키는 prismatic 관절이다. x는 전방, z는 위쪽이며 닫힌 바닥의 분할선은 x와 평행하다.

두 관절의 위치 단위는 m이며 각각 0은 닫힘, `box_width/2 + box_bottom_slide_clearance`는 완전 열림이다(기본 0.105 m). 같은 양수 위치를 두 관절에 주면 대칭으로 열린다. `/joint_states`에 이 이름과 위치를 포함하여 TF를 표현한다. mimic은 사용하지 않으며, 실제 동기 구동 제어기와 새 ROS 명령 인터페이스는 이번 자산 변경에 포함하지 않는다. 기존 팔 정책의 action 차원에는 추가하지 않는다.

## 3.6 관제·모바일·Vision 파트와 합의할 항목

- 관제가 저수준 pose를 직접 보낼지, `object_id + skill_name`을 보낼지
- 요청 중복 처리 및 request ID 생성 주체
- 취소와 emergency stop의 우선순위
- 상태 enum과 오류 코드의 공통 정의
- heartbeat 주기와 통신 단절 판정 시간
- 재시도 책임이 관제에 있는지 로봇 노드에 있는지
- 인식 pose의 기준 frame, covariance 전달 여부
- 시뮬레이션/실물에서 동일 topic을 사용할지 namespace로 분리할지
- 모바일 상태 중 어떤 조합을 manipulation 시작 허가로 볼지
- 수확 중 `base_motion_inhibit`의 소유권과 해제 조건
- Vision target 메시지에 크기, 접근 방향, covariance, 추적 ID를 포함할지
- 수확 성공을 로봇팔의 분리 감지로 확정할지 Vision 재확인으로 확정할지
- 정책 실행 노드에서 simulator/실물 controller로 보낼 저수준 joint command의 topic, message 형식과 QoS
- 평가 시 policy/control 주기, command timeout과 episode reset 동기화 방식

---

## 2026-09-17 제작 뚜껑 독립 미리보기

`display_sliding_lids.launch.py`는 실물 명령을 보내지 않는 RViz 전용 뷰어다.
`world` 아래 `harvest_lid_*`, `transport_lid_*` 프레임을 쓰며 기존 로봇 관절과 분리한다.
각 `*_pinion_joint`의 양수 rad 입력은 -X축 회전이다. 두 슬라이드 관절은 각각 ±Y축으로,
피니언 각도에 피치 반경(수확 0.042 m / 운반 0.060 m)을 곱한 mimic 위치를 사용한다.
이 뷰어의 `/joint_states`, `/tf`, `/tf_static`은 기존 실물/전체 로봇 publisher와 별도 실행한다.

## 2026-09-18 전체 로봇 제작 뚜껑 기구 반영

수확로봇은 기존 `box_bottom_left_joint`(+Y, m)를 주 관절로 유지한다.
`box_bottom_right_joint`는 왼쪽 위치를 1:1 mimic하고 새 `harvest_lid_pinion_joint`는
왼쪽 위치/0.042를 -X 회전으로 표현한다. 기존 독립 두 바닥 명령 방식은 이 제작 조합에서 대칭 연동으로 변경된다.
운반로봇은 기존 `lid_pinion_joint`가 주 관절이며 `top_lid_left/right_joint`가 0.060 m/rad mimic한다.
구동부/지지부는 실제 조립 좌표로 추가하며 새 하드웨어 명령 토픽은 만들지 않는다.
학습 실행/기존 체크포인트는 자동 전환하지 않으며, 변경된 조합 자산으로 재준비·검증이 필요하다.

## 2026-09-21 단일 목표 정책 전달 계약 (팀 간 합의 전 초안)

- 학습 tensor 경로는 ROS 비의존으로 유지한다. `harvest_rl/target_contract.py`는 추후 ROS adapter가 호출할 공통 검증 계층이다. ROS node/action 서버는 이번 범위에 포함하지 않는다.
- 배정: `task_id`, `target_id`를 고정한다. 시뮬레이션 fruit slot은 adapter 내부 값이며 policy 입력에 넣지 않는다. 실행 도중 다른 ID로 교체하지 않는다.
- Vision 관측: `target_id`, `frame_id`, `stamp_s`, `position_m[3]`, `valid`. 위치는 보정된 TF로 팔 기준 좌표계로 변환한 뒤 전달한다. stamp와 now는 동일 clock domain이다. frame 불일치/역순 timestamp/미래 timestamp는 거부한다.
- Student 전달 계약 v1: 기존 proprio 18값(정규화 관절각6, 속도6, 직전 action6) + 팔 기준축으로 표현한 `(목표 위치 - TCP 위치)` 3값[m] + 관측 유효1 + 경과시간1[s, TTL에서 clip] = 23값. RGB와 history는 별도다. 무효/TTL 초과는 상대위치0, valid0; 이전 위치를 새 관측처럼 전달하지 않는다. target ID, 실제 접촉/분리/성공/줄기 힘은 입력에서 제외한다.
- 목표 관측 상실은 수확 실패와 구분한다. `OBSERVATION_LOST`를 올리고 adapter는 접근 명령을 차단한다. 파지 후 가림은 정상일 수 있으므로 향후 student 실행기는 작업 단계/관절 상태/독립 확인 신호를 이용해 회복 여부를 판단한다. valid0만으로 그리퍼를 열거나 새 목표로 교체하지 않는다.
- 결과 상태: WAIT_TARGET → RUNNING → SUCCEEDED / FAILED / TIMED_OUT / CANCELLED. terminal은 소비할 때까지 유지한다. 재시도에는 명시적인 recovery/reset이 필요하다. 시뮬레이션 reset은 실물 복구 동작이 아니다.
- 시뮬레이션 성공은 기존 task 판정을 사용한다. 실물 성공은 박스 통과 등 독립된 증거를 완료 확인 계층에서 받아야 한다. vision에서 목표가 사라졌다는 이유만으로 성공으로 처리하지 않는다.

## 2026-09-21 두 D435 simulator 영상 경계

현재 URDF의arm_2/wrist_camera 및top_camera color/depth optical frame을사용하는검사경로를추가했다. native depth는float32 optical-Z metre, 유효mask별도, RGB정렬depth도같은단위다. raw렌더depth에는inf가있을수있고전처리/정렬결측은0이다. 각센서K와color_from_depth는캡처metadata에기록한다. RGB 픽셀을native depth에서그대로조회하지않는다. 이는ROS topic발행기구현이아니며실물CameraInfo/extrinsic은실제장치보정값을사용해야한다. 상세: manipulation/HARVEST_D435_PREVIEW_KR.md.

## 2026-09-21 공통 순차 실행기 내부 계약

`harvest_runtime`은 ROS/Isaac/torch 비의존 단일 팔 순차 실행기다. 대상 목록은 상위 배정 계층이 순서를 정해 제공한다. target_id/frame_id/position_m/stamp_s/valid와 request_id/timeout_s를 사용한다. 시간은 caller가 주는 단조 증가 초이며 관측도 같은 clock domain이다. backend는 정책/완료검출/제어를 연결하는 start_target, tick_target, start_return, tick_return, stop, tick_stop을 제공한다. 결과는 대상 ID와 request ID를 모두 포함하며 오래된 결과는 오류로 처리한다.

첫 목표 및 목표 사이 RETURNING에서 실제 복귀/정지/재관측 준비 완료를 확인한다. 환경 reset/순간이동 API는 계약에 없다. 성공 후 수확 완료 ID를 기록하되 마지막 복귀까지 완료해야 batch SUCCEEDED다. 실패/시간초과/취소/예외 시 STOPPING으로 전이하고 stop acknowledgement 후 terminal로 고정한다. stop 확인 실패도 성공으로 취급하지 않는다. 자동 재시도/장면 초기화/양팔 배정/ROS topic 변경은 없다. 실물 emergency stop 대체가 아니다. 실제 ROS adapter와 두 카메라 student 구현은 별도이며 공통 core 호환성과 실물 검증을 구분한다.

## 2026-09-21 teacher 물리 연속 수확 평가

공통 Motion 계약을 구현한 Isaac 전용 복귀 어댑터를 추가한다. 성공한 실제 관절 이력을 역순 추종하되 그리퍼를 열린 상태로 유지하고, 실제 접촉/과실 상태/추종 오차를 매 물리 substep 감시한다. 이는 범용 충돌 회피 계획기가 아니라 접촉 감시를 동반한 보수적인 기록 경로 복귀다. 실패하면 정지하며 충돌을 뚫고 HOME으로 보내지 않는다. external 작업 terminal을 RUNNING으로 위조하거나 장면 reset하지 않고 별도 physics step을 쓴다. 수확 중에도 이전 적재 과실 보존을 확인한다.

## 2026-09-21 Motion 복귀 경로 변경

Isaac 기본 복귀는 direct HOME(근사 기하 검사+실제 접촉 감시)으로 변경한다. 이력 역추종은 retrace 명시 옵션만 유지한다. 공통 Backend/Policy 계약은 유지한다. sequence 결과에 target_starts(ID/slot/실제 위치/관절)를 저장해 목표 재지정과 복귀 경로를 구분한다. strict와 checkpoint 행동 조건은 run.json에 기록한다.

## 2026-09-29 HCR 카메라 구역 판정 PoC (운용 계약 아님)

독립 카메라 진단 UI가 A~D ROI를 HSV로 판정하고 A>B>C>D 기본 우선순위의 선택 후보를 출력한다. 기본 더미 JSON 출력이며 선택형 PC Modbus 서버를 HCR이 읽는다. 동작 START/작업 실행/완료 handshake는 구현하지 않는다.

테스트용 unit1, FC03/04 읽기 전용: 주소0=구역*10+색상(0=선택없음, A빨강11/A노랑12/.../D노랑42), 1=구역(0..4), 2=색상(0/빨강1/노랑2), 3=유효여부, 4=프레임 카운터(mod65536). 다중 레지스터는 한 요청에서 읽어야 일관된 snapshot이다. 원본영상 갱신이1초 이상 멈추거나 UI 편집/정지/미설정이면 후보0. 모든 쓰기 거부. 현재 후보는 작업 요청이 아니며 실물 시퀀스와 연결하지 않는다.


## 2026-09-29 Student 준비용 비전 진단 어댑터 (임시, 구동 없음)

Vision팀 모델을 읽기 전용으로 검증한다. rectified RGB+aligned optical-Z depth+CameraInfo.P와 촬영시각 TF(arm_2/base_link<-color optical)를 입력으로 사용한다. `harvest/perception_debug` std_msgs/String JSON은 camera_id/stamp_s/detections(색,신뢰도,표면좌표,중심추정,valid/candidate_valid/control_valid/이유)를 제공한다. 기존 대상ID/관제 계약은 변경하지 않으며 이 토픽은 제어 명령이 아니다. ID융합·목표배정은 후속작업. 상세 STUDENT_VISION_PREP_KR.md.


## 2026-09-29 Student v2 수집 계약 (ROS 비의존 내부 API)

동일 arm_2/base_link와 simulation/monotonic clock의 탐지 중심 후보를 TrackManager에 전달한다. 근접·색상으로 ID를 연계하되 모호한 연계는 거부하고 미관측은 TTL 후 invalid다. ID는 에피소드/현장 session 내에서만 유효하며 완료는 외부 증거로 명시한다. 낮은 미완료 후보부터 배정하되 실행 중 ID를 교체하지 않는다. 실물에서는 control_valid가 필요한 기본 모드, 시뮬레이션 수집에서만 provisional을 명시한다.

Student v2: 카메라 순서 right,rear, RGB uint8 및 정렬 depth float32 metres/invalid=0, 3프레임 history, 상태23(proprio18+목표-TCP3+valid1+age1). ID·truth·expert stage는 네트워크 입력이 아니다. 시각/관절은 같은 관측 시점이며 action은 그 관측으로 계산한 다음 제어 명령이다. 카메라 결측은 이미지/depth0과 camera_valid0. Teacher stage/성공/실패는 별도 라벨/품질 metadata다. 기존 단일RGB Student checkpoint와 호환되지 않는 명시적 v2다. 수집은 학습 및 실물 구동이 아니다.

## 2026-09-29 Student BC 파일 계약

prepared.json은명시적train/validation episode목록·파일SHA256·센서/자산/Teacher계약을보존한다. 학습시재검사. 새BCcheckpoint는schema_version2,camera_order[right,rear],student state_dict,input_contract와재개용optimizer/epoch/sampler·torch RNG를저장한다. best는검증단계별MSE평균기준,성공률을의미하지않는다. ROS명령/실물인터페이스변경없음.


## 2026-09-30 — 고정 Teacher 점진 운반 프로파일 및 Student 기록 연결

teacher_ramp_20260930.json에entry model200/pull_direction/transport_refine final/place전문가 파일과run.json SHA256 고정. collect_student_ramp.sh는매시작해시검증후기존두D435수집실행,외부체크포인트환경변수우회없음. .25→3초1 ramp,방향보유분리,captured_break_grace명시. 기존수집명령기본보존,STUDENT_COLLECTOR로새wrapper선택.

Student라벨은staged제어와ramp후clip[-1,1]된실제6관절증분명령. 매step env.actions와정확일치확인;불일치episode ERROR. dataset_manifest에profile내용/해시,experts.action_execution에scale/ramp/release/recovery와student_reapply_teacher_ramp=False 기록. Student출력에동일ramp중복적용금지;Student폐루프실행기완성의미아님. audit계약비교에action_execution포함,이전미명시데이터와혼합거절. 실제모터토크나실물안전검증아님.

201개회귀통과. student_ramp_smoke_20260930:seed55빨강1회전체수확성공125frames,target valid116,FK동기화/실행명령일치통과,종료0,재audit accepted. Student가중치학습없음. 이는수집통합검증1회이며일반성공률검증아님.

## 2026-10-01 — HCR 선별 배치 실행 인터페이스 v1

사용자 지시에 따라 `/sorter_01/sort_batch` Action Server와 `/sorter_01/status` Topic을 구현한다. 참조는 Confluence page12746755 v6(2026-10-01). 실제 타입은 이 저장소의 `smartfarm_interfaces/action/SortBatch`, `smartfarm_interfaces/msg/SorterStatus`로 구체화하며 관제도 같은 패키지를 사용해야 한다. Goal의robot_id/task_id/batch_id/timestamp, Result의result_code/red_count/yellow_count/error_code/error_message, Feedback의phase/누적개수와식별자를 보존한다. 총운반횟수는 red_count+yellow_count. 상태1Hz, Feedback1Hz및상태/개수변경시. 동일task_id는영속기록으로중복수락거부. 선별중receive_ready/ready=false. 반입준비는운영자가설정한receive_enabled와장치준비조건으로계산하며실물반입센서검증은아니다.

종료정책은 사용자요청으로 변경: 복귀 후 새 영상에서4구역모두 NO_COLOR가연속3초(설정가능)일때SUCCESS. WAIT/MIXED/미설정/정지/카메라오류는종료근거가아니다. 이정책은상류레인막힘이나색상미검출물체까지비었음을증명하지않는다. 배치시작후에도같은미검출시간을적용한다. 안정화대기기본0.5초. A완료후A재선택가능. 계수는일치하는BUSY수락과DONE(정상놓기+초기위치복귀)의작업번호당한번.

### Modbus 실행용 맵 (기존 preview 서버와 동시 사용 금지)

PC서버/HCR클라이언트,port502/unit1. FC03/04읽기,FC06/16은100..103만쓰기허용. HCR프로그램수정필수. 주소0은기존11/12/21/22/31/32/41/42값유지. 주소1..4는preview의미와호환되지않는다.

| 주소 | 소유자 | 의미 |
|---|---|---|
|0|PC|COMMAND: 대기0, 구역*10+색상. 요청/운반중고정 |
|1|PC|JOB_ID: 1..65535, SQLite에영속증가,재사용없음,소진시오류 |
|2|PC|REQUEST: 수락전1,일치BUSY수신후0 |
|3|PC|BATCH_ACTIVE: Goal처리중1 |
|4|PC|PC heartbeat: 제어tick별증가,통신정지시HCR측신규수락차단에사용 |
|100|HCR|STATE: 0미준비,1READY,2BUSY,3DONE,4ERROR |
|101|HCR|ACK_JOB_ID: 로컬에복사해수락한작업번호 |
|102|HCR|DONE_JOB_ID: 정상놓기및초기위치복귀를완료한작업번호 |
|103|HCR|ERROR_CODE: 정상0,장치오류비영 |

HCR은101/102/103을먼저갱신하고100을마지막에써서상태를commit한다(또는100..103 FC16원자쓰기). 상태100을최소1Hz로반복쓰기;PC는3초미갱신을통신고장으로판정. BUSY는PC가REQUEST=0을보일때까지유지해야한다. DONE은PC COMMAND=0/REQUEST=0확인까지유지한후READY. PC는READY확인및복귀후새영상안정화후다음작업. 로봇은REQUEST를대기중에만수락,active_command/active_job에복사한값으로실행. 현재PC서버는HCR관절/그리퍼이동을구현하지않는다.

취소는새작업을막고이미발행한요청/운반의DONE과READY를기다린뒤CANCELED. 완료된운반개수보존. timeout/통신고장은FAILED와오류latch;물리정지명령은아니므로HCR측오류정리필요. `/sorter_01/reset_fault` Trigger는현장복구후READY/카메라준비가확인될때만latch해제. PC재시작시미완료작업은재실행하지않고중단기록/오류latch. 최초서버가동만으로작업을발행하지않는다.


### 2026-10-07 손목 D435 체결면/nominal TF 보정

카메라 link/topic 이름과 optical 축 계약은 유지한다. 양쪽 `gripper_link -> wrist_camera_mount_link -> wrist_camera_link` fixed TF를 실제 STL의 모터 5홀 면과 D435 뒤판 2홀 면에 맞춰 보정했다. 최신 값은 `src/smartfarm_description/config/assembly.yaml`, 형상 근거는 `config/d435_wrist_attachment.json`이다. 현재 두 D435 시뮬레이션 경로는 오른팔과 후면 카메라를 사용하며, 왼팔 손목은 조합 자산에 포함된다. 실제 카메라→팔 보정값과 같다는 의미는 아니다. 새 URDF 기반 RGB-D 수집은 촬영 시점 TF와 새 자산 hash를 저장해야 하며 기존 카메라 보정/데이터와 묵시적으로 혼합하지 않는다.

### 2026-10-12 손목 D435 큰 구멍 정렬 기준

사용자는 실물에 SO100용 원본 STL 출력물을 설치하고 마운트와 고정 그리퍼/손목 몸체의 큰 구멍을 맞췄다고 확인했다. 현재 조합의 양팔 `gripper_link -> wrist_camera_mount_link`는 실제 SO101 홀더 STL의 외측 −X 면 큰 구멍 축에 맞춘다. 카메라 뒤판의 마운트 상대 TF와 RGB/depth 내부 TF는 유지하고 마운트 전체를 이동·회전한다. 현재 특징점/도출값은 `src/smartfarm_description/config/d435_wrist_hole_alignment.json`, 적용값은 `assembly.yaml`이다. 이전 `d435_wrist_attachment.json`은 동결 학습의 과거 기준이다.

마운트 안쪽 면이 홀더 외측 면에 닿고 두 큰 구멍의 중심축이 일치한다. 구멍 지름 자체는 마운트 0.015 m/홀더 0.010 m로 다르다. 원형 축 둘레의 자세는 카메라가 그리퍼 +Y 쪽에서 집게 안쪽·−Z 방향을 보는 조합 기준으로 정한다. 나사 체결법·출력 공차·hand-eye 실측을 추정하지 않는다. 기존 이름/메시지/상태 계약은 유지한다. 새 카메라 데이터는 새 자산 hash/촬영 TF를 사용하며 과거 동결 Teacher/Student USD와 reference는 이 배치로 자동 교체하지 않는다.


## 2026-10-07 — HCR 선별장 기능 시뮬레이션 프로파일

- 기존 `SortBatch` action, `SorterStatus`, 레지스터 0..4 / 100..103 계약은 유지한다. 수확 SO-ARM101 및 OMX 실행기와 별도인 `src/sorting_station/run_hcr_sim.py`를 사용한다.
- 시뮬레이션 HCR 클라이언트는 `127.0.0.1:1502`만 사용한다. PC 서버의 peer도 loopback으로 지정하고 robot_id는 `sorter_sim`으로 분리한다. 카메라 상태·구역·저널·런타임은 `outputs/sorting_station/hcr_sim` 아래에서 관리한다.
- 시뮬레이션 카메라 JSON은 실제 렌더 RGB에 기존 HSV/안정화 판정을 적용한다. ROS PC는 배치 완료·취소를 관리하며 모의 로봇은 한 작업의 복귀/보관부 도착 후 DONE을 보낸다. READY/ACK/BUSY/DONE 상태 쓰기는 렌더 속도와 독립된 벽시계 스레드로 반복한다.
- 기본 `g` 시작은 ROS 없는 더미 배치다. `--modbus`에서는 기존 ROS 더미 관제의 goal을 사용한다. 공개 메시지/필드 변경은 없다.
- 운반박스 모드는 최초 BATCH_ACTIVE 상승에서 스크립트 도착·배출을 시작한다. 투입 중 카메라 zone_states는 모두 WAIT, zone/color는0, valid=false이며 지정 구역 ready는 유지한다. 기존 supervisor는 WAIT를 빈 배치로 완료하지 않는다. 모든 과실의 미끄럼틀 진입·안정화 후 실제 HSV 상태를 전달하고 요청을 수락한다. 공개 ROS/Modbus 필드 변경 없이 시뮬레이션 JSON에 supply_phase/lane_map 진단을 추가한다.
- A–D 명령은 사용자가 지정한 카메라 구역 이름 기준이다. 사각형 중심을 카메라 투영 집기 레인에 일대일 대응시켜 역방향 영상에서도 올바른 레인을 집는다. 가이드 밖/중복 레인은 ready=false다. 내부 모델의 물리 레인명과 카메라 구역명은 다를 수 있다.
- PC에서 카메라 파일을 읽은 다음 monotonic 시각을 얻는다. 원자 갱신 파일의 타임스탬프가 먼저 얻은 시각보다 수십 µs 새로워 정상 프레임을 미래 시각으로 거절하는 경합을 방지한다.
- 근사 모델의 IK 티칭 라디안 값을 실제 HCR/Rodi 관절 명령으로 전달하지 않는다. 상세 사용법은 `src/sorting_station/hcr_sim/README.md`.


## 2026-10-15 — U20 손목 카메라 선택형 수집 계약

기존 ROS 메시지/Action/기본 D435 센서 계약은 유지한다. 별도 URDF `harvest_robot_u20_wrist_v1.urdf`와 `u20_wrist_deployment_v1.json`에서 오른팔 손목은 U20 RGB1920×1080@30fps, 오버헤드는 기존 D435 RGB-D@30fps다. `arm_2/wrist_camera_color_optical_frame`은 새 URDF의 렌즈 관통 방향을 따르며 오른팔 depth/IR frame은 이 버전에 없다. 왼팔은 기존 D435를 유지한다.

새 수집 manifest는 schema_version4 / capture_contract=physics_scheduled_u20_rgb_v1로 구분하고 원본 손목 NPZ에는 RGB만 저장한다. 축소 관측의 빈 depth_m[right]=0은 사용 불가 모달리티이며 실제 U20 depth가 아니다. IR 배열은 만들지 않는다. 촬영30Hz/물리60Hz/명령20Hz와 기존 관절 절대목표/그리퍼 명령 레이블은 유지한다. 기존 D435/IR Student v3 자료·모델과 혼합하지 않으며 RGB 전용 BC 준비기는 별도 다음 단계다. 자세한 체결/임시 치수·명령: manipulation/U20_WRIST_VARIANT_V1_KR.md.


### 2026-10-15 — U20 양팔 외형 r2

U20 선택형 URDF는 양팔 손목 RGB optical frame을 제공하며 depth/IR frame은 두 손목 모두 없다. 흰색 마운트/검정 카메라를 양팔에 적용한다. Student 입력은 기존대로 오른손목 RGB와 오버헤드 D435 RGB-D의 두 시점이며 왼손목 입력/양팔 제어를 추가하지 않는다. schema4/capture_contract/60·20·30Hz는 유지하고 revision은 u20_dual_wrist_white_v1_r2_20261015로 갱신한다. 원본 파일과 해시가 다른 r1/v3 자료를 조용히 혼합하지 않는다. ROS 메시지/Action 변경은 없다. 오버헤드 높이는 비교 후 기존값을 유지한다.

## 2026-10-15 — U20 시연 compact 내부 파일 계약

U20 sensor schema4/physics_scheduled_u20_rgb_v1의 절약 보관은 compact_certificate.json의 schema=student60_u20_audited_compact_v1로 식별한다. 모든20Hz 입력 NPZ/명령 JSON과 모든 native metadata, 단계별 대표 native 영상쌍을 보존하며 all_native_images_retained=false다. 원래 raw_capture 절대경로는 이력이고 native_path_mapping 및 retained_native_frames를 통해 보존된 프레임만 찾아야 한다. 전체 raw 프레임이 있다고 가정하는 loader를 사용하지 않는다. u20_full_audit.json은 전체 원본이 존재할 때 검증한 결과이며 compact 무결성은 verify_compact로 별도 검사한다. 기존 D435 v3 계약과 호환으로 처리하지 않는다. U20 BC 준비기는 별도 작업이고 ready_for_u20_bc_training=false다. ROS Action/상태 인터페이스 변경은 없다.

## 2026-10-15 — U20 Student BC 체크포인트·준비 계획

U20 전용 준비 계획은 student60_version/model_family=student60_u20_rgb_executed_targets_v1, student_schema_version=4로 식별한다. command_version=student60_executed_targets_servo_v1의 관절 절대목표6+집게 강성/속도2 의미는 유지한다. 관측은 rgb(2,90,160,3), depth_m(2,90,160; 손목슬롯0), camera_valid(2), state(23)의 최근3프레임이다. 손목IR/정답/접촉/phase 입력은 없다. D435 v3 체크포인트를 U20 로더로 로드하거나 반대로 처리하지 않는다.

scripts/prepare_student60_u20.py가 별도compact 인증서/전체 파일해시/관측·행동/훈련검증 분리를 확인해 data.json을 생성한다. scripts/train_student60_u20.py의 student_best.pt/student_last.pt는 위 모델 가족과 정확한 contract/data hash를 포함한다. U20Inference는 실제 이전 실행 명령 acknowledgement를 요구한다. 학습 완료 후 U20 자율수확 평가 경로 연결은 별도이며 현재 ROS 요청/상태 enum 변경은 없다.
