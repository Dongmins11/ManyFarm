# 시뮬레이션 장치 연결 구현 — v0.2

## 구조

공통 bringup이 real/sim을 선택합니다. sim에서는 다음 두 프로그램을 실행합니다.

1. `farm_sim_runtime/run_sim.py`: env_isaaclab Python. Isaac Sim 한 개에서 바퀴·카메라·LiDAR 모듈을 호출합니다.
2. `farm_sim_devices/ros_adapter.py`: ROS Python. 표준 ROS 토픽을 발행·구독합니다.

Isaac Sim 5.1의 Python 3.11과 Ubuntu 24.04 ROS Jazzy의 기본 Python 환경을 억지로 합치지 않습니다.
두 프로그램 사이의 작은 명령·센서 데이터는 localhost UDP로 교환합니다.
카메라 이미지는 UDP나 이미지 토픽으로 보내지 않고 Linux `/dev/shm`에 mmap으로 기록합니다.
공통 로봇 로직은 내부 UDP를 알 필요가 없습니다. 실제/시뮬레이션 모두 같은 ROS 인터페이스를 사용합니다.

## 파일별 역할

| 파일 | 역할 |
|---|---|
| `farm_bringup/launch/scout.launch.py` | 공통 mode 분기 |
| `farm_sim_runtime/launch/scout_devices.launch.py` | Isaac/ROS 프로그램 실행 및 함께 종료 |
| `farm_sim_runtime/run_sim.py` | 씬 열기, 장치 초기화, 물리/센서 반복 실행 |
| `farm_sim_devices/base_sim.py` | 속도 명령→바퀴 velocity target, encoder 읽기 |
| `farm_sim_devices/camera_sim.py` | 같은 렌더 프레임의 RGB-D 수집 |
| `farm_sim_devices/lidar_sim.py` | PhysX raycast 거리 측정 |
| `farm_sim_devices/ros_adapter.py` | ROS 토픽/TF 변환 |
| `farm_sim_devices/wire.py` | 로컬 통신, session·순서·명령 유효기간 확인 |
| `farm_common/kinematics.py` | 차동구동 계산, encoder odom 적분 |
| `farm_common/rgbd_shm.py` | real/sim 공용 RGB-D writer/reader 규격 |
| `farm_sim_config/config/scout.json` | 장면 경로, prim, 센서 주기, 치수, 이름 |

`arm_sim.py` 및 공통 예찰 업무 코드는 아직 구현하지 않았습니다.
`farm_interfaces`의 ScoutArea 자료형은 존재하지만 이번 장치 연결부에서 사용하거나 Action 서버를 띄우지는 않습니다.

## 시각·좌표 처리

- `/clock`, odom, scan, joint_states, TF는 simulation timestamp를 사용합니다.
- 명령 통신 끊김은 동일 PC의 monotonic 시계로 확인합니다. ROS use_sim_time 정지에 감시 타이머가 멈추지 않습니다.
- odom은 실제 joint position 변화량을 사용합니다. cmd_vel이나 월드 정답 위치를 적분하지 않습니다.
- 월드 정답 pose는 가상 LiDAR 빔의 출발점/방향 계산에만 사용합니다.
- 원본 stage에서 차체와 센서의 고정 상대 변환을 읽습니다.
- USD 카메라의 -Z 전방/+Y 위 방향은 ROS optical의 +Z 전방/-Y 위 방향으로 변환합니다.
- 카메라 rendering_time에 맞는 encoder odom 기록을 골라 저장합니다. 일치하는 기록이 없으면 현재 pose로 대체하지 않고 프레임을 건너뜁니다.
- 카메라 pose는 평면 주행 odom 기반이며 지면 요철로 인한 roll/pitch를 추정하지 않습니다.

## 영상 공유 규약

`/dev/shm/farm_scout_01_rgbd.bin`은 tmpfs 기반 영상 버퍼입니다.
정상 종료하면 유효 프레임 표시를 해제하며 파일은 재사용을 위해 남깁니다.
`.owner` 파일 잠금으로 같은 이름의 writer 중복 실행을 방지합니다.

한 번의 잠금 안에서 metadata, RGB, Depth를 기록합니다. reader는 같은 잠금 안에서 복사한 다음 잠금을 해제하므로
writer가 추론 완료를 기다리지 않습니다. 잠금 경합 시 해당 프레임을 건너뛰어 최신 데이터 위주로 처리합니다.
Python multiprocessing resource_tracker에 의존하지 않아 서로 다른 Python 환경의 reader 종료가 writer 버퍼를 삭제하지 않습니다.

포함 정보: 버전, session, sequence, simulation timestamp, optical frame ID, pose timestamp,
odom 기준 optical transform(4×4 column-vector 규칙), 카메라 K, 크기/stride/encoding, depth 단위 m, 정렬 여부.
RGB는 uint8 H×W×3, Depth는 float32 H×W의 광축 깊이입니다. 유효 범위를 벗어난 depth는 NaN입니다.
YOLO 입력 크롭/패딩을 적용했다면 검출 좌표를 원본 영상 좌표로 되돌린 뒤 depth와 K를 적용해야 합니다.
map 기준 위치는 촬영 시각의 map→odom을 소비자가 추가 적용해야 합니다.

## 종료·오류 처리

- 마지막 명령 수신 0.5초 후 바퀴 속도 목표를 0으로 설정합니다.
- NaN/Inf, 다른 session, 순서가 뒤집힌 명령, 오래된 명령을 거부합니다.
- ROS adapter 재시작에도 command sequence가 되돌아가지 않도록 monotonic_ns를 사용합니다.
- Pause 중 명령은 저장해 재사용하지 않습니다.
- 동일 포트/공유메모리 writer 중복 실행은 오류로 중단합니다.
- 연결 종료/시뮬레이터 종료 시 bringup의 나머지 프로그램도 종료합니다. 강제 종료의 최종 방어는 Isaac 측 watchdog입니다.
- UDP 수신 포트는 127.0.0.1:17600(Isaac), 127.0.0.1:17601(ROS)이며 영상은 통과하지 않습니다.

## 검증

작성 환경에서 다음 8개 자동 시험을 통과했습니다.

1. encoder 기반 직진/제자리 회전 odom.
2. 후진/곡선 odom의 정확 적분.
3. encoder ±π 경계 처리.
4. 속도 제한과 NaN 명령 정지.
5. 오래된 명령·다른 session·역순 명령 거부 및 timeout 정지.
6. localhost UDP 송수신.
7. 별도 Python 프로세스에서 RGB-D 읽기, writer 중복 방지, 재시작 후 새 session 읽기.
8. 제공 USD의 실제 관절 이름·velocity drive 및 카메라 높이·왼쪽 시선 확인.

Python/XML 구문과 ROS 패키지 설치 대상 파일도 확인했습니다.
시험 코드는 요청에 따라 사용자 프로젝트 패치에 추가하지 않았습니다.
**ROS colcon 빌드, 실제 DDS 통신, Isaac 물리/렌더링, 센서 실측 FPS는 아직 검증하지 못했습니다.**

## API 근거

- Isaac Sim 5.1 camera API 및 같은 버전 camera.py: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/py/source/extensions/isaacsim.sensors.camera/docs/index.html
- Articulation API: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/py/source/extensions/isaacsim.core.prims/docs/index.html
- PhysX scene query: https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.3/extensions/runtime/source/omni.physx/docs/api/python.html
- ROS/Isaac Python 호환: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_ros.html
