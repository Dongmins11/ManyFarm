# v0.3: 1번 베드 경로 주행

## 이번에 추가한 것

1. 기존 `scan`(LiDAR)과 `odom`(바퀴 회전 기반 위치)을 AMCL에 연결합니다.
2. AMCL이 지도 위 위치를 추정하고 `map → scout_01/odom` 변환을 발행합니다.
3. Nav2가 목적지까지 이동 경로와 속도를 계산합니다. 기존 바퀴 연결부가 `/scout_01/cmd_vel`을 받아 움직입니다.
4. RViz에 지도·LiDAR·경로점을 표시합니다. **bringup만으로는 출발하지 않습니다.**
5. 별도 `scout_route.launch.py` 실행 시 1~8번 경로점을 순서대로 주행합니다.

경로점마다 Nav2 도착 결과를 확인하고 다음 점을 보냅니다. 실패하면 중단합니다.
이 점들은 한 베드 안의 경로점이며, 최종 예찰의 관측 정차점은 아닙니다.
Nav2는 점 사이 경로를 지도와 장애물에 맞춰 계획하므로 GeoJSON 선을 정확하게 강제 추종하는 방식은 아닙니다.

아직 YOLO, ScoutArea 서버, 검출 결과 전송은 추가하지 않았습니다.
section/segment 이름을 임의로 정하지 않았으며 return_to_station과 status도 추가하지 않았습니다.

## 1. 적용 및 빌드

기존 실행 중인 bringup을 Ctrl+C로 종료합니다.
압축 안의 `farm_project/` **내용물**을 기존 `~/robotarm/farm_project/`에 병합하세요.
추가·변경 파일만 들어 있습니다. assets와 map 이미지, GeoJSON은 압축에 없으며 기존 파일을 사용합니다.
`scout.json`은 주석 성격의 notes만 한글로 정리했습니다. 별도로 바꾼 설정이 있으면 변경 내용을 비교하여 병합하세요.

robot_venv를 사용하는 터미널에서 Nav2가 아직 없다면 한 번 설치합니다.

```bash
sudo apt update
sudo apt install ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-rviz2
```

기존과 같은 robot_venv에서 빌드합니다.

```bash
cd ~/robotarm/farm_project
bash scripts/build.sh sim
source scripts/env.sh sim
```

## 2. 지도와 위치부터 확인

```bash
ros2 launch farm_bringup scout.launch.py mode:=sim navigation:=true rviz:=true \
  isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python \
  assets_root:="$PWD/sim/assets"
```

기존 `navigation:=false`가 기본값이므로 예전 명령은 장치 연결만 수행합니다.
기존 Isaac/ROS 연결을 실행한 상태라면 중복 실행하지 말고 위 단계에서 종료 후 다시 시작하세요.

RViz에서 확인할 것은 세 가지입니다.

- 로봇 좌표축과 분홍색 footprint가 베드 1 시작점 근처에 보입니다.
- 빨간 LiDAR 점이 지도 벽/장애물과 대체로 겹칩니다.
- 하늘색 경로/화살표는 진행 방향(-Y), 노란 화살표는 예정된 카메라 방향(+X)입니다.

초기 위치 추정값은 현재 씬에 저장된 배치 좌표 `x=-6.2842, y=12.0611, yaw=-1.5708`입니다.
이는 시작할 때 넣는 추정값입니다. 실제 위치를 매 프레임 정답으로 넣지 않습니다.
로봇 배치를 바꾸면 `nav2_scout.yaml`의 `amcl.initial_pose`를 함께 바꾸거나 RViz의 **2D Pose Estimate**로 초기 위치와 방향을 지정하세요.

LiDAR와 지도가 크게 어긋나면 주행 전에 위치를 바로잡으세요.
LiDAR가 비어 있으면 씬 장애물에 충돌 형상이 있는지도 확인해야 합니다.
로봇 외형 mesh 대신 좌표축/footprint를 표시합니다. 메쉬가 안 나오는 것은 현재 설정에서 정상입니다.

## 3. 명시적으로 주행 시작

위 bringup을 켜 둔 상태에서 **두 번째 robot_venv 터미널**을 엽니다.

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout_route.launch.py mode:=sim
```

이 명령부터 로봇이 움직입니다. 기본 순서는 1→2→3→4→5→6→7→8입니다.
앞의 두 점만 먼저 확인하려면 다음처럼 실행합니다.

```bash
ros2 launch farm_bringup scout_route.launch.py mode:=sim node_ids:=1,2
```

- 주행 터미널 Ctrl+C: 자신이 보낸 Nav2 목표를 취소하고 결과를 확인합니다. 바로 터미널을 강제 종료하지 마세요.
- 취소 확인에 실패했다는 메시지가 나오면 첫 번째 bringup도 종료하세요.
- 목표 하나당 기본 제한은 실제 시계 300초입니다. 오래 일시정지하면 시간 초과로 취소됩니다. `goal_timeout_s:=600.0`으로 조정할 수 있습니다.
- 동시에 다른 주행 클라이언트나 수동 cmd_vel 발행 프로그램을 실행하지 마세요.
- 현재 시험 속도는 전진 최대 0.12m/s, 회전 최대 0.8rad/s입니다.
- 시뮬레이션을 재설정하여 시간이 되돌아갔다면 bringup도 재시작하세요.

## 파일을 어디서 수정하나

| 파일 | 역할 |
|---|---|
| `robot/ros_ws/src/farm_bringup/launch/scout.launch.py` | 공통 시작점. mode와 navigation 선택 |
| `robot/ros_ws/src/farm_bringup/launch/scout_navigation.launch.py` | AMCL·Nav2 실행 및 mode별 설정 선택 |
| `robot/ros_ws/src/farm_bringup/launch/scout_route.launch.py` | 별도로 실행했을 때 경로 주행 시작 |
| `robot/ros_ws/src/scout_robot/scout_robot/route.py` | GeoJSON 읽기/연결 검증 |
| `robot/ros_ws/src/scout_robot/scout_robot/route_preview.py` | 이동 없는 경로 표시 |
| `robot/ros_ws/src/scout_robot/scout_robot/drive_route.py` | Nav2 목표 전송·결과 확인·취소 |
| `sim/ros_ws/src/farm_sim_config/config/nav2_scout.yaml` | sim 지도 좌표계, 초기 위치, 속도, 장애물 설정 |

파일 경로는 설치된 ROS 패키지 기준으로 찾습니다. `/home/ysy/...`를 코드에 박아 넣지 않았습니다.
사용자 명령의 `isaac_python`만 설치된 Python의 실제 경로입니다.

`map:=/다른/map.yaml`, `nav_params:=/다른/nav2.yaml`, `route_file:=/다른/graph.geojson`로 덮어쓸 수 있습니다.
다른 경로를 쓰면 표시용 bringup과 주행용 launch 양쪽에 같은 `route_file`을 지정해야 합니다.
현재 경로 표시 기본 노드는 1~8입니다. 다른 노드 집합을 표시하려면 route_preview의 `node_ids` 파라미터도 맞추세요.
real 장치 연결은 계속 미구현입니다. 실물 담당자는 장치 코드와 실제 map/nav_params/route_file을 제공해야 합니다.
현재 robot namespace는 scout_01로 고정되어 있습니다. 여러 예찰 로봇 동시 실행은 별도 확장이 필요합니다.

## 통신 연결

- `/scout_01/scan` → AMCL 및 Nav2 장애물 처리
- `/scout_01/odom` → Nav2
- `/scout_01/map` → AMCL 및 global costmap
- `/tf`, `/tf_static`은 기존 연결부와 같은 전역 토픽을 사용합니다.
- controller/behavior → `cmd_vel_nav` → velocity_smoother → `/scout_01/cmd_vel`
- 속도 메시지는 기존 연결부와 같은 `geometry_msgs/Twist`입니다.
- ROS 노드들은 시뮬레이션 `/clock`을 사용합니다. 주행 클라이언트의 제한 시간/취소 대기는 실제 시계 기준입니다.

카메라 공유메모리와 기존 바퀴·LiDAR 모듈은 변경하지 않았습니다.

## 검증 범위

제공된 지도와 GeoJSON으로 초기 위치/경로점이 자유 공간에 있는지,
경로 연결과 방향이 올바른지, Python 문법과 패키지/설정 구성을 점검했습니다.
주행 클라이언트의 성공·실패·거절·취소·시간 초과 처리도 ROS 통신을 제외한 단위 수준에서 점검했습니다.
이 작성 환경에는 ROS Jazzy/Isaac Sim 실행 환경이 없어 실제 colcon 빌드와 주행은 실행하지 못했습니다.
실제 센서와 지도 정합, AMCL 수렴, 회전·충돌 여유는 사용자 환경에서 확인해야 합니다.
주행 완료 로그는 경로 이동 완료만 의미하며 예찰/검출 성공을 의미하지 않습니다.
