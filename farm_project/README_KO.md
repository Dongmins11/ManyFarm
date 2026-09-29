# 농장 로봇 — 예찰로봇 시뮬레이션 장치 연결 v0.2

이번 코드는 **속도 명령을 받아 가상 바퀴를 움직이고, 센서값을 내보내는 부분**입니다.
GeoJSON 자율주행, AMCL/Nav2, YOLO 추론, ScoutArea 서버는 아직 포함하지 않습니다.
공통 코드는 `robot/ros_ws`, 시뮬레이션 장치 코드는 `sim/ros_ws`에 있습니다.

## 적용

압축 안의 `robot`, `sim`, `scripts`를 기존 `farm_project`에 합쳐 덮어씁니다.
자산과 맵 파일은 이번 패치에 포함하지 않았습니다. 기존 `sim/assets`를 유지합니다.
예전 `stage:=check`는 제거했습니다. 이제 기본 bringup은 장치 연결을 실행합니다.
사용하지 않는 아래 파일은 삭제해도 됩니다.

```bash
rm -f sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/preflight.py
```

이전 파일 이동용 tools/tests/reports는 이번 패치에 포함하지 않았으며 다시 필요하지 않습니다.

## 1. Isaac Sim만 먼저 실행

`env_isaaclab` 환경에서 프로젝트 루트로 이동해 실행합니다.
이미 열려 있는 Isaac Sim은 닫고 실행하세요. 이 명령이 Isaac Sim 한 개를 새로 엽니다.

```bash
cd ~/robotarm/farm_project
python scripts/run_scout_sim.py
```

농장 씬을 열고 현재 배치된 예찰로봇을 연결합니다. 시작 위치를 새로 지정하지 않습니다.
카메라/RGB-D와 LiDAR를 켜고, 바퀴는 명령이 올 때까지 정지합니다.
씬 위치는 `sim/ros_ws/src/farm_sim_config/config/scout.json`의 `scene`에 있습니다.
창 없이 실행하려면 `--headless`를 추가하세요.

## 2. ROS 연결 실행

별도 `robot_venv` 터미널에서 빌드하고 실행합니다.

```bash
cd ~/robotarm/farm_project
bash scripts/build.sh sim
source scripts/env.sh sim
ros2 launch farm_bringup scout.launch.py mode:=sim start_isaac:=false
```

`start_isaac:=false`는 1번에서 이미 실행한 Isaac Sim에 연결한다는 뜻입니다.
`Isaac Sim 연결됨` 로그가 나오면 장치 데이터가 도착한 상태입니다.

첫 연결 확인 후에는 bringup 하나로 두 프로그램을 함께 실행할 수 있습니다.
`env_isaaclab`에서 `python -c 'import sys; print(sys.executable)'`로 Python 경로를 확인하고,
그 경로를 ROS 터미널의 다음 명령에 사용합니다.

```bash
ros2 launch farm_bringup scout.launch.py mode:=sim \
  isaac_python:=/실제/env_isaaclab/bin/python \
  assets_root:="$PWD/sim/assets"
```

이때는 1번 명령으로 실행한 Isaac Sim을 먼저 종료합니다. `/실제/...`는 반드시 확인한 경로로 바꾸세요.
`isaac_python`은 설치 폴더가 아니라 **Python 실행 파일**입니다.

## 3. 느리게 움직여 보기

ROS 환경이 준비된 별도 터미널에서 실행합니다.

```bash
ros2 topic pub -r 10 /scout_01/cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.05}, angular: {z: 0.0}}'
```

초당 5cm 전진 명령입니다. **Ctrl+C로 발행을 멈추면 마지막 명령 이후 0.5초가 지나 정지 목표를 적용합니다.**
실제 정지는 시뮬레이션이 다음 물리 스텝을 진행할 때 반영됩니다.
회전은 `linear.x: 0.0`, `angular.z: 0.3`으로 바꿉니다.
속도는 설정의 최대값(초기값 0.22m/s, 1.5rad/s)으로 제한합니다.
이 코드는 장애물을 보고 자동으로 정지하는 주행 제어기가 아닙니다.

```bash
ros2 topic echo /scout_01/odom --once
ros2 topic echo /scout_01/scan --once --qos-reliability best_effort
```

기본 cmd_vel 자료형은 `Twist`입니다. 기존 주행 코드가 `TwistStamped`이면 bringup에
`cmd_vel_type:=twist_stamped`를 지정하고 발행 자료형도 맞춥니다.

## 카메라 영상 읽기

별도 Python 환경(NumPy 필요)에서 실행합니다.

```bash
cd ~/robotarm/farm_project
python scripts/read_rgbd.py
```

촬영 프레임 번호·영상 크기·유효한 depth 비율이 출력됩니다.
이 스크립트는 영상 소비자 예시이며 YOLO 모델은 실행하지 않습니다.
실제 YOLO는 `farm_common.rgbd_shm.RgbdReader.read()`로 같은 프레임을 읽으면 됩니다.
RGB는 RGB 순서이며 OpenCV의 BGR과 구분하세요.

## 현재 발행/구독

| 인터페이스 | 방향 | 내용 |
|---|---|---|
| `/scout_01/cmd_vel` | 구독 | 직진·회전 속도 |
| `/scout_01/odom` | 발행 | 시뮬레이션 바퀴 회전량으로 적분한 위치 |
| `/scout_01/joint_states` | 발행 | 좌우 바퀴 회전각·각속도 |
| `/scout_01/scan` | 발행 | 360도 충돌체 기반 거리 측정 |
| `/clock` | 발행 | 물리 시뮬레이션 시간 |
| `/tf`, `/tf_static` | 발행 | odom→차체, 차체→센서 변환 |
| `farm_scout_01_rgbd` 공유메모리 | 기록 | 같은 프레임의 RGB·Depth·시각·카메라 정보 |

`map→odom`은 발행하지 않습니다. 추후 AMCL이 담당합니다.
odom의 원점은 로봇이 실행을 시작한 위치입니다. 농장 map 좌표와 바로 같지 않습니다.
공유메모리의 카메라 pose도 odom 기준입니다. map 좌표로 바꿀 때 촬영 시각의 TF를 사용해야 합니다.

## 확인된 모델 설정

- 씬 로봇: `/World/scout_robot_camera_fixed`
- Articulation root: 그 아래 `base_footprint`
- 바퀴: `wheel_left_joint`, `wheel_right_joint`
- 바퀴 반지름 0.033m, 바퀴 중심 간 거리 0.16m
- 카메라: `base_link/scout_camera`, base_link보다 0.59m 위, 로봇 왼쪽(+Y) 시선
- LiDAR: `base_scan`, base_footprint 기준 약 (-0.032, 0, 0.182)m

카메라는 USD의 수평 시야각을 사용합니다. 초기 출력은 **640×384 / 15fps**로 USD의 5:3 비율에 맞췄습니다.
실제 D435 내부 파라미터를 적용한 상태는 아닙니다. 15fps는 설정값이며 실측 성능은 아직 확인하지 않았습니다.

## 알아둘 제한

- Isaac Sim 5.1 API를 기준으로 작성했습니다. 이 작업 환경에는 Isaac Sim/ROS 실행 환경이 없어 실제 구동 검증은 사용자 PC에서 해야 합니다.
- LiDAR는 충돌체가 있는 물체만 감지합니다. 반사율, 센서 노이즈, 회전 중 왜곡은 아직 없습니다.
- 카메라/바퀴 위치와 USD를 자동으로 저장하거나 바꾸지 않습니다. 실행 설정은 session layer에만 반영합니다.
- 바닥 아래로 로봇이 떨어지면 중단합니다. 임의의 바닥 collider를 추가하지 않습니다.
- GUI Pause는 가능하지만 Stop 후 재시작에 따른 시간 reset은 프로그램 재실행이 필요합니다.
- 한 PC의 예찰로봇 1대를 위한 초기 구성입니다. 다른 시뮬레이터의 `/clock` 발행과 중복시키지 마세요.
- 실물 장치 연결은 기존 원칙대로 미구현 오류를 냅니다.

파일별 역할과 검증 내용은 `docs/simulation_connection.md`를 참고하세요.
