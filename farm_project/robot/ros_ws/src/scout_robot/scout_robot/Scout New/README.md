> 2026-10-01: 주행·위치 기능을 farm_navigation으로 분리했습니다. [현재 공통 구조와 환경 실행](../../../../../../docs/navigation_common_structure.md)을 함께 읽어주세요.

# 실제 ROS 예찰 실행 — State 패턴

ScoutNode·ScoutMission·ScoutCommunication을 유지하고 ScoutStateController를 추가했습니다.
각 State가 행동 요청·완료 처리·다음 단계 판단을 맡습니다. Mission에 전체 순서를 실행하는 반복문을 두지 않습니다.

실제 코드는 `robot/ros_ws/src/scout_robot/scout_new`입니다. 이 문서 옆 `scout_new`는 그 경로를 가리키는 기존 링크입니다.

## 실행 흐름

```text
ScoutArea Goal → Communication → StateController → Mission 데이터 준비
IDLE → NAVIGATION_MOVE → SEGMENT_PROGRESS → SEGMENT_COMPLETE
                ↑                                  │
                └──────── 다음 관측 지점 ───────────┘
마지막 지점 → SECTION_COMPLETE → 다음 구역 이동 또는 작업 종료 → IDLE
```

`enter()`는 행동을 요청하고 반환합니다. 완료 이벤트는 Controller를 거쳐 해당 State로 전달됩니다.
정상 전환은 `exit → enter` 순서이며, 취소·오류는 Controller의 공통 중단 경로에서 처리합니다.
현재 정지 관측·촬영 지점 Segment 의미와 기존 과실 매칭 알고리즘은 유지합니다.

## 파일 역할

| 파일 | 담당 |
|---|---|
| scout_node.py | 설정·ROS 자원 초기화와 객체 연결 |
| scout_communication.py | 실제 ScoutArea 접수·취소·Feedback·Result |
| scout_mission.py | 작업 데이터·진행 기록·자원 수명·결과 구성 |
| scout_state_controller.py | 현재 State·전환·완료 이벤트·공통 중단 |
| states/ | 각 단계의 행동과 다음 단계 판단 |
| navigator.py / observer.py | 실제 Nav2 이동 / 영상 워커 RPC |

[전체 로직과 코드 읽는 순서](scout_new/STATE_ARCHITECTURE.md)를 먼저 읽으면 됩니다.

## ROS 연결

namespace=scout_01 기준입니다. 이름은 remapping으로 변경할 수 있습니다.

| 연결 | 이름과 형식 |
|---|---|
| 작업 서버 | /scout_01/scout_area — ScoutArea Action |
| 이동 요청 | /scout_01/navigate_to_pose — NavigateToPose Action |
| 주행 상태 | /scout_01/odom — Odometry |
| 설정 확인 | controller_node 설정 + /get_parameters |
| TF | map, base_frame, 관측 pose_frame 변환. 채널은 기존 TF remapping에 따름 |
| RViz | /scout_01/survey_markers — MarkerArray |
| 영상 | 기존 워커의 stdin/stdout RPC 및 같은 호스트 RGB-D 공유 메모리 |

## 빌드와 실행

```bash
source /opt/ros/jazzy/setup.bash
cd ~/manyfarm/main/farm_project/robot/ros_ws
colcon build --symlink-install --packages-up-to farm_bringup
source install/setup.bash
```

장치 및 Nav2 bringup을 먼저 실행합니다. 아래 서버는 Nav2나 장치를 자동 실행하지 않습니다. VISION_PYTHON은 YOLO 의존성이 설치된 실제 Python 경로로 바꿉니다.

```bash
VISION_PYTHON=/실제/YOLO환경/bin/python
ros2 launch farm_bringup scout_survey.launch.py \
  mode:=sim \
  project_root:=$HOME/manyfarm/main/farm_project \
  vision_python:=$VISION_PYTHON headless:=true
```

기본 실행 파일은 scout_node입니다. 기존 구현은 executable:=survey_server로 선택할 수 있습니다. 같은 namespace에 두 서버를 동시에 실행하지 않습니다.

기존 관제 클라이언트를 사용할 수 있습니다. 아래 명령은 실제 작업을 요청하며 연결된 로봇을 움직일 수 있습니다.

```bash
python3 ~/manyfarm/main/farm_project/control/scripts/send_scout_area.py --section BED_01
```

## 시뮬과 실물

같은 Mission·State·Navigator를 사용합니다. 실물 환경은 mode:=real 및 실물 survey_config를 지정하고 Nav2·odom·TF·RGB-D 공급 계약을 맞춰야 합니다. 공유 메모리는 같은 호스트에서만 사용할 수 있습니다.

scout_survey_real.example.json은 configured=false인 미완성 예제입니다. 실측 지도·베드·센서 보정과 실제 영상 공급 연결이 필요합니다. 이번 변경은 실제 ROS 호출을 연결한 것이며 실물 장치 통합 완료는 아닙니다. 실제 주행과 추론을 포함한 시뮬/실물 전체 검증도 아직 수행하지 않았습니다.

[Unity 비교와 코드 읽기](GUIDE.md), [State 실행 방식](STATE_STEP_GUIDE.md)을 참고하세요.
