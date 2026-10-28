# HCR-3A 선별장 농장 시뮬레이션 통합 전달서

작성일: 2026-10-08. 대상은 **HCR-3A 선별장**이다. OMX 선별 학습 환경 및 SO-ARM101 수확 정책과 구분한다.

## 1. 전달 목적과 현재 상태

농장 시뮬레이션에 투입 미끄럼틀, HCR-3A 기능 근사 로봇/그리퍼, 색별 보관부를 함께 배치하고, 운반로봇의 과실 투입부터 RGB 기반 선별·운반·완료까지 연결한다.

현재 자료는 **단독 실행 가능한 선별장**의 코드·원본 자산·설정·검증 기록이다. 농장 공통 실행 루프용 플러그인으로 분리된 상태는 아니다. USD만 열면 제어가 실행되지 않는다. 아래 농장 통합 항목은 앞으로 수행할 작업이며 구현 완료된 API로 해석하지 않는다.

권장 진행 순서: 전달 묶음의 단독 재현 → 농장 위치/경로 적용 → 농장 실행 루프 연결 → 기존 운반로봇 연결 → 관제 Action 검증.

## 2. 구현 범위와 유지할 동작

| 항목 | 구현 내용 | 범위·제약 |
|---|---|---|
| 선별장 구조 | 4레인 투입 미끄럼틀, 설치판/컨트롤러, 2색 보관 통로·보관함 | 실물 사진·치수 노트 기반, 일부 치수는 근사 |
| 로봇팔 | 6축 근사 모델, IK 티칭, 집기·운반·복귀 순서 | 실물 HCR 관절 영점·관성·Rodi 데이터와 호환되지 않음 |
| 그리퍼 | JRT JEGH-3520P-A-Y003 사진 기반 손가락·분홍 패드 | 파지는 가까이 도착한 뒤 보조 고정 조인트 사용 |
| 운반로봇 | 기존 Waffle/박스/틸트/배출문/슬라이딩 뚜껑 자산 재사용 | 이동·기구는 지정 경로, 실제 주행/모터 토크 제어 검증은 아님 |
| 과실 투입 | 무작위 위치·회전 생성 → 중력으로 박스에 적재 → 접촉/중력 배출 | 운반 과실 순간이동·고정·색별 레인 재배치 없음 |
| 카메라 | 실제 렌더 RGB, A–D 사각 ROI 직접 지정, HSV·시간 안정화 | 객체 색 라벨이나 segmentation을 색 판정 입력으로 사용하지 않음 |
| 선택·반복 | 사용자 구역 A→B→C→D 우선순위, 작업 중 새 선택 차단 | 같은 레인에 다음 과실이 오면 반복 선택 |
| 완료 | HOME 복귀·올바른 색 보관부 도착 후 1회 계수 | 단축 검증 종료와 전체 배치 SUCCESS를 구분 |
| 관제 | 기존 SortBatch Action·SorterStatus 및 Modbus handshake | 단독 `g`는 ROS 없는 더미 시작, `--modbus`는 ROS Goal 사용 |

투입 중 영상 상태는 WAIT다. 전체 과실의 충돌 hull이 원래 박스 전면을 완전히 벗어나고 중심이 미끄럼틀 판정 범위 안에 들어와야 선별을 시작한다. 미배출은 TRANSPORT_DUMP_INCOMPLETE, 적재 안정화 실패는 TRANSPORT_LOADING_FAILED다.

모든 ROI가 NO_COLOR로 연속 3초일 때 빈 배치 완료 정책을 적용한다. WAIT/MIXED/미지정/카메라 오류는 빈 배치로 취급하지 않는다. 이는 상류 막힘이나 색 미검출까지 포함한 실제 빈 선별장 증명은 아니다.

## 3. 좌표계·치수·물성 기준

단위는 m, kg, s, rad이며 Z-up이다. 현재 기준 좌표계의 원점은 로봇 설치판 중앙 바닥이다. 투입부는 +X, 보관부는 −X다. 모델의 물리 레인 A–D는 +Y→−Y이며, 사용자가 영상에서 지정한 A–D는 별도 매핑된다. 보관부 +Y는 빨강, −Y는 노랑이다.

| 값 | 현재 설정 | 근거 |
|---|---|---|
| 설치판 | 0.50×0.60×0.04 m | 사용자 노트 |
| 설치판–컨트롤러 간격 | 0.07 m | 사용자 노트 |
| 투입부 폭/경사면 길이/상승 | 0.505 / 0.50 / 0.225 m | 사용자 노트 |
| 레인 유효 폭/폼보드 두께 | 0.12 / 0.005 m | 사용자 노트 |
| 바깥 벽/내부 구분벽 높이 | 0.10 / 0.055 m | 사용자 노트 |
| 하단 턱 | 0.10 m | 이탈 방지를 위한 기능 근사, 실측 아님 |
| 컨트롤러 외형 | 0.223×0.47×0.47 m | 평면 치수 참고, 높이는 명목값 |
| 보관 경사 길이/낙차/보관함 길이 | 0.26 / 0.13 / 0.22 m | 근사값 |
| 운반박스 | 0.30×0.30×0.19 m | 기존 운반 자산 유지 |
| 과실 전체 높이 | **0.075 m** | 사용자 정정값, 원본 메시 전체 Z 범위 축척 |
| 과실 지름/질량 | 0.09 m / 0.009 kg | 명목값, 실측 확정 아님 |
| 폼보드 마찰 static/dynamic | 0.12 / 0.08 | 명목값 |
| 패드 마찰 static/dynamic | 1.2 / 1.0 | 명목값 |
| 운반박스 마찰 static/dynamic | 0.5 / 0.4 | 명목값 |
| 판정 카메라 | 640×480, 수평 FOV 58°, eye=(0.48,0,1.0) | 명목 시뮬레이션 설정, 실측 보정 아님 |

카메라 target=(0.4,0,0.1)이다. 자료 속 이전 105 mm 과실/별도 넓힌 차량/OMX 구성은 현재 전달 기준이 아니다. 수확용 geometry v2도 이번 HCR 기준에 자동 적용하지 않는다.

## 4. 파일 구성과 의존성

압축 묶음의 `workspace/`에서 기존 저장소 구조를 유지한다. 해당 디렉터리가 독립 실행의 작업공간 루트다.

| 파일·디렉터리 | 역할 |
|---|---|
| src/sorting_station/run_hcr_sim.py, .sh | 독립 AppLauncher, 물리/렌더/GUI/관제 실행 루프 |
| src/sorting_station/hcr_sim/scene.py | 구조물·로봇·과실 생성 |
| hcr_sim/model.py, control.py | 근사 FK/IK/티칭, 선별 시퀀스·완료 판정 |
| hcr_sim/transport_asset.py, transport.py, payload.py | 원본 운반 자산/FK, 투입 단계, 무작위 적재 |
| hcr_sim/vision.py, cv_window.py | 실제 RGB 판정, 수동 ROI·별도 GUI 프로세스 |
| hcr_sim/link.py | 시뮬레이션 Modbus 클라이언트/벽시계 heartbeat |
| src/smartfarm_description/config/hcr3a_station.json | 현재 기본 4개 운용 설정 |
| config/hcr3a_random8_validation.json | 기존 성공 검증의 8개 설정 스냅샷 |
| scripts/generate_hcr3a.py, hcr3a_environment.py | 근사 로봇 및 세 부분의 구조물 생성기 |
| urdf/hcr3a_functional.urdf | 근사 로봇 참고 원본, 실행 시 설정으로 파생 URDF 생성 |
| urdf/transport_robot.portable.urdf 및 참조 메시 | 기존 운반로봇 원본, 경로 구조 보존 |
| config/transport.json, scripts/model_geometry.py | 기존 운반 크기/기구 설정·FK |
| meshes/pepper의 원본 USD·manifest·텍스처 | HCR에서 파생 충돌/시각 자산 생성 |
| src/sorting_station/sorting_sim/assets.py, settings.py, __init__.py | 과실 생성 헬퍼의 import 의존성만 포함 |
| src/sorting_station/hcr/zone_preview.py | 실제 카메라와 공유하는 HSV/안정화 판정 |
| src/sorting_station/hcr_sorting, src/smartfarm_interfaces | ROS supervisor·더미 관제·Action/상태 타입 |

`sorting_sim`의 이름·settings에는 OMX 상수가 남아 있지만 HCR에서는 `prepare_pepper_usd`에 별도 source/cache/크기/질량을 명시한다. OMX 환경·팔 제어·학습을 실행하지 않는다. 수확 Python 모듈·정책·학습 캐시는 이 묶음에 포함하지 않는다.

원본 USD/URDF의 참조 파일은 경로 그대로 제공한다. 변환된 Isaac USD 캐시는 PC 절대 경로를 포함할 수 있어 전달본에서 제외하고 수신 PC에서 재생성한다. 제조사 STEP ZIP은 `reference/source_cad/`에 참고용으로 제공하며 현재 움직이는 모델을 대체하지 않는다. 실물 사진·치수 노트는 `reference/photos/`, 검증 기록은 `reference/validation/`에 있다.

## 5. 수신 후 단독 실행

먼저 압축 해제 루트에서 `python3 verify_delivery.py`로 파일 해시·운반 메시·텍스처 누락을 검사한다. 이후 `cd workspace` 한다. 환경 버전 실측값은 전달 루트의 `ENVIRONMENT.json`을 확인한다. 수신 PC와 호환 검증을 수행해야 하며 설치를 강제로 변경하는 스크립트는 포함하지 않는다.

현재 확인한 환경: Isaac Sim 5.1.0.0, Python 3.11.15, 설치된 isaaclab 배포 메타데이터 0.54.2, torch 2.7.0+cu128, NumPy 1.26.0, SciPy 1.15.3. GUI는 별도 Python 3.12.3/OpenCV 4.6.0(Qt5), Isaac 내부는 opencv-python-headless 4.11.0.86이다. 버전 기록은 전달 시점 환경 조회값이다.

```bash
# workspace/에서. 본인 Isaac Lab 환경 Python의 실제 경로로 바꾼다.
export ISAAC_PYTHON=/본인/IsaacLab환경/bin/python
export HCR_GUI_PYTHON=/usr/bin/python3

# 전달된 검증 ROI가 있는 새 workspace에서 8개 배출 후 1회 선별·복귀
bash src/sorting_station/run_hcr_sim.sh \
  --config src/smartfarm_description/config/hcr3a_random8_validation.json \
  --pepper-per-lane 2 --payload-layout random --payload-seed 43 \
  --auto-start --stop-after-sorted 1
```

처음 4.5 simulation seconds는 박스 위 과실을 떨어뜨려 쌓고 안정화를 확인한다. 이후 접근·문 열기·도킹·45° 기울임·5~45° 재기울임2회 후 8개 배출을 확인한다. 기본 설정(4개, 38°, 도킹 X=0.715 m)과 구분한다. 검증 설정은 도킹 X=0.695 m다. wall time은 PC 부하에 따라 다르다.

전달본의 `workspace/outputs/sorting_station/hcr_sim/zones.json`은 기존 성공 시험의 수동 ROI를 복사한 재현 자료다. 기존 농장 작업공간의 ROI를 덮어쓰는 용도가 아니다. 다른 카메라 배치·해상도·시야에서는 새로 지정한다.

```bash
# 투입만 보고 구역을 직접 다시 지정하려면
bash src/sorting_station/run_hcr_sim.sh \
  --config src/smartfarm_description/config/hcr3a_random8_validation.json \
  --pepper-per-lane 2 --payload-seed 43 --unload-only
```

카메라 창에서 a/b/c/d 선택 → 하단 가이드의 앞 과실 **몸통**에 사각형 드래그 → s 저장. 배출 완료 후 g로 선별을 시작할 수 있다. t는 투입만, x는 진행 중 1회 완료 후 취소, q/ESC는 종료다. 꼭지를 포함한 작은 ROI는 YELLOW/MIXED 오판 가능성이 있다.

기능 회귀:

```bash
PYTHONPATH=src/sorting_station "$ISAAC_PYTHON" -m unittest discover \
  -s src/sorting_station/hcr_sim/tests -v
```

`--headless`는 GUI 없이 실행한다. `--auto-roi`는 검증용이며 실제 통합의 수동 영역 지정을 대체하지 않는다. `--stop-after-sorted`는 standalone 검증용이며 ROS 모드에서는 사용하지 않는다.

## 6. 농장 통합 시 수정할 부분

### 6.1 농장 pose와 선별장 좌표

농장 기준 `T_farm_station`을 하나 정한다. 위치는 `p_farm=R_farm_station·p_station+t_farm_station`, 자세도 같은 회전으로 변환한다. 로봇 실제 world pose/TCP/과실 pose를 판정할 때는 역변환하여 선별장 좌표계에서 기존 집기·보관·배출 조건을 검사한다.

`/World/HCRStation`만 옮기면 다른 형제 prim과 제어 좌표는 따라오지 않는다. HCRRobot, Peppers, Transport, SortingCamera, 보조 파지 조인트와 집기/놓기 자세·차량 축·배출면을 함께 처리해야 한다. 카메라 eye/target와 가이드 투영도 같은 변환을 적용한다.

### 6.2 prim 경로와 실행 루프

현재 `/World/HCRStation`, `/World/HCRRobot`, `/World/Transport`, `/World/Peppers`, `/World/SortingCamera`, `/World/AssistedGrasp` 및 재료 경로가 고정돼 있다. 농장 경로와 충돌하지 않도록 root 경로를 설정화하고 생성·조회·충돌 필터·접촉 센서·보조 조인트 경로를 함께 갱신한다.

농장 AppLauncher/SimulationContext/ground/light/물리 step을 한 주체가 관리한다. 선별 런처를 그대로 import하여 별도 AppLauncher/parse_args를 실행하지 않는다. scene 생성, 센서 갱신, Transport/Sorter tick, GUI/통신 종료를 농장 루프에 연결하는 어댑터로 분리한다. 이것은 통합 작업 제안이며 현재 build/step 플러그인 API가 제공됐다는 뜻이 아니다.

현재 dt=1/240 s, CPU PhysX·GPU 렌더로 검증했다. 이 설치의 GPU PhysX에서는 운반 기구 kinematic target이 지원되지 않아 운반 모드의 GPU device를 차단한다. 농장의 backend와 호환되는 구동 방식은 통합 전에 확인하고, 변경하면 배출·RGB·완료를 다시 검증한다. 현재 CPU에서는 Fabric을 끄고 실제 물리 pose를 USD에 반영한다. 렌더가 과거 pose를 보여주면 실제 색 판정과 충돌이 어긋날 수 있다.

### 6.3 농장 운반로봇 연결

농장에 이미 존재하는 운반로봇과 과실을 받아 연결한다. 시연용 Transport 접근 경로·박스 초기 적재를 중복 실행하지 않는다. 도킹 완료/정지 pose, 박스 틸트·문·뚜껑 제어 주체, 과실 소유권과 실제 배출 완료 조건을 모바일/Simulation팀과 합의한다. 색 라벨에 따라 과실을 강제로 레인에 재배치하지 않는다.

### 6.4 reset·시간·파일·완료

재시작 시 seed/과실 pose/물리 속도/보조 고정/충돌 필터/카운트/빈 영역 타이머/ROI 안정화/관제 job을 일관되게 초기화한다. 농장 전체 reset과 선별장만 reset하는 경우를 구분한다. ROI는 카메라 구성이 동일하면 유지할 수 있다.

ROI 안정화·이동·3초 빈 배치는 simulation time 기준이다. 현재 Modbus heartbeat 및 PC 카메라 JSON의 monotonic freshness는 wall time 기준이다. pause/저속 실행 때 통신 timeout 정책을 별도로 합의해야 한다. 최신 상태·저널·GUI 출력 경로는 스테이션별로 분리하고, 전체 배치 완료는 ROS Result로 확인한다.

## 7. 관제 연결 재현

통합 전 standalone ROS를 선택적으로 확인한다. sim robot_id는 `sorter_sim`, Modbus는 **127.0.0.1:1502**, unit1이다. 아래 시뮬레이션 서버 override를 유지한다. 기존 서버 기본값은 실물용이므로 기본 실행 명령으로 대체하지 않는다.

workspace에서 ROS 패키지 빌드:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --base-paths src/smartfarm_interfaces src/sorting_station/hcr_sorting \
  --packages-select smartfarm_interfaces hcr_sorting --symlink-install \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
```

세 터미널 모두 workspace에서 ROS 환경 및 install/setup.bash를 source하고 `export ROS_DOMAIN_ID=67 ROS_LOCALHOST_ONLY=1`로 맞춘다. 67은 분리 검증용 예시이며 팀 환경과 충돌하면 함께 변경한다.

```bash
# 터미널 1: PC supervisor
ros2 run hcr_sorting sorter_node --ros-args \
  -p robot_id:=sorter_sim \
  -p modbus_host:=127.0.0.1 -p modbus_peer:=127.0.0.1 -p modbus_port:=1502 \
  -p camera_timeout:=3.0 \
  -p camera_state:="$PWD/outputs/sorting_station/hcr_sim/state.json" \
  -p journal:="$PWD/outputs/sorting_station/hcr_sim/ros/journal.sqlite3" \
  -p runtime_state:="$PWD/outputs/sorting_station/hcr_sim/ros/runtime.json"

# 터미널 2: 모의 팔. 투입/카메라 ROI를 확인한 뒤 Goal을 보낸다.
bash src/sorting_station/run_hcr_sim.sh --modbus \
  --config src/smartfarm_description/config/hcr3a_random8_validation.json \
  --pepper-per-lane 2 --payload-seed 43

# 터미널 3: 더미 관제
ros2 run hcr_sorting dummy_control --robot-id sorter_sim
```

이 ROS 8개 배치 명령은 통합 확인용이며 최신 무작위8개 전체 선별 SUCCESS 검증 명령으로 보증하지 않는다. 완료/취소/오류를 관제 Result에서 확인한다. GUI g는 --modbus의 시작 Goal을 대신하지 않는다.

Action `/sorter_sim/sort_batch`: Goal robot_id/task_id/batch_id/timestamp, Feedback phase/red_count/yellow_count, Result result_code/red_count/yellow_count/error_code/error_message와 식별자·timestamp. 상태 Topic은 `/sorter_sim/status`, reset은 `/sorter_sim/reset_fault`다.

레지스터 0–4는 COMMAND/JOB_ID/REQUEST/BATCH_ACTIVE/HEARTBEAT, 100–103은 STATE/ACK_JOB_ID/DONE_JOB_ID/ERROR_CODE다. STATE 0=미준비,1=READY,2=BUSY,3=DONE,4=ERROR. 명령은 A 빨강11/노랑12, B21/22, C31/32, D41/42다. BUSY 동안 새 작업을 수락하지 않고 정상 놓기·복귀 후 DONE을 유지하며 PC clear 확인 뒤 READY다. 전체 계약은 workspace/docs/INTERFACES.md의 HCR 항목을 따른다.

## 8. 검증 사실과 알려진 한계

| 기록 | 확인 결과 | 해석 |
|---|---|---|
| random8_seed43_unload | 4.5초 적재 안정화, 59초8개 전체 배출, 독립 hull 검사 통과 | 선별0회, 전체 배치 SUCCESS 아님 |
| random8_seed43_sort1 | 8개 배출 후 노랑1회 선별·운반·HOME/보관 확인, DONE/오류없음 | 18,697 steps, 단축 종료 true, batch_complete=false |
| random8_seed43_sort2_error | 8개 배출/노랑1회 완료, 두 번째 VISION_PICK_COLOR_MISMATCH | 작은 B ROI가 초록 꼭지를 노랑으로 판정, 두 번째 이동 전 차단 |
| random8_seed42_spatial_only | 예전 중심 판정으로 통과했으나2개 몸체가 박스에 남음 | 8개 배출 성공에서 제외한 사후 발견 기록 |
| height75_manual 및 existing_transport_ros | 이전 ordered4개 배출·전체 선별/ROS 확인 | 최신 random8 성능이나 새 기본random4 검증으로 일반화하지 않음 |

시뮬레이션 제어/자산 원본123개 hash는 최신 seed43 성공 당시 metadata와 전달 시점에 일치했다. ROS supervisor는 별도 계층이며 최신8개 전체 ROS 검증은 수행하지 않았다. 역사적 원본98개 운반 자산과 수동 ROI 불변 검사 자료를 포함한다.

다른 seed의 배출 성공률, 8개 전체 선별 완료, 실물 운동/모터 동특성/파지력은 검증하지 않았다. 실패 기록을 성공으로 집계하지 않는다. 보조 파지는 기능 검증용이며 물리 접촉만으로 유지하는 그리퍼 실증이 아니다.

## 9. 팀 회신과 통합 완료 기준

팀에서 Isaac Sim/Isaac Lab·Python·ROS 버전, CPU/GPU physics 및 Fabric 설정, farm prim root와 선별장 pose, 운반로봇 도킹 pose/관절 구동 방식, 공통 step/reset/pause·ROS namespace를 회신해 주세요.

통합 완료는 다음을 새 환경에서 확인한 뒤 판단한다.

1. 세 부분의 상대 치수·좌표·충돌·카메라가 함께 배치된다.
2. 실제 농장 운반로봇의 과실이 자유 접촉으로 미끄럼틀에 들어온다. 지정 개수 중 미배출이 있으면 선별이 차단된다.
3. 수동 ROI의 실제 렌더 RGB가 올바른 물리 레인에 연결된다. 한 작업 중 다른 명령을 받지 않는다.
4. 정상 놓기·복귀·색 보관부 확인 후만 카운트/DONE이 증가하고 같은 레인의 다음 과실을 처리한다.
5. 전체 빈 배치/관제 완료, 취소·통신 오류·ROI 오류 및 reset/pause를 별도로 확인한다.
6. seed/설정/소스 hash, Result와 과실 최종 상태·화면을 함께 저장한다.

전달된 단독 실행 성공은 농장 통합 완료를 의미하지 않는다. 수신 팀의 새 환경에서 위 항목을 검증한다.
