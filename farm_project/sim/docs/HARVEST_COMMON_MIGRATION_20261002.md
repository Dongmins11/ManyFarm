# 수확 서버 공통화 정정 — 2026-10-02

이 패치는 수확 서버를 sim에 배치했던 이전 구현을 정정한다. 사용자가 승인한 공통 서버·bringup 이전이며, 기존 수확 패치 적용 여부와 무관하게 앞선 launch 분리 프로젝트 위에 적용할 수 있다. 이전 수확 패치 내용과 이번 정정을 합친 대체 패치다. 원본 농장 USD·지도·예찰 프로젝트는 필요하다.

## 현재 구조

| 위치 | 책임 |
|---|---|
| `robot/ros_ws/src/harvest_robot/harvest_robot/node.py` | 환경 설정 로드 및 공통 Navigator 연결 |
| 같은 패키지 `communication.py` | HarvestTask 수신·피드백·결과·취소 처리 |
| 같은 패키지 `mission.py`, `state_controller.py`, `contract.py` | 이동 미션·상태 전환·입출력 계약 |
| `robot/ros_ws/src/farm_bringup/launch/harvest.launch.py` | mode별 장치·지도 선택, 동일 수확 서버 실행 |
| `sim/ros_ws/src/farm_sim_runtime/launch/harvest.launch.py` | 공통 bringup 호출 + 시뮬 과실 평가 노드 |
| `sim/ros_ws/src/farm_sim_harvest/` | 과실 평가만 담당. Action 서버·미션·주행 요청 코드 없음 |
| `sim/.../farm_sim_config/config/harvest_task.json` | 공통 서버가 읽는 시뮬 환경의 작업 설정 |
| `sim/.../farm_sim_config/config/harvest_audit.json` | 시뮬 전용 실제 과실 비교·로그 설정 |

공통 서버는 sim 패키지를 import하지 않으며 Isaac snapshot을 읽지 않는다. 환경 설정만 바꿔 sim/real에 같은 서버를 사용한다. 주행은 기존 farm_navigation을 공유한다.

## 적용

실행 중인 이전 ROS·Isaac을 종료한다. 다운로드 위치가 Downloads라고 가정한다. 프로젝트 변경 파일은 적용 전 Git 또는 파일 백업으로 보존한다.

```bash
cd ~/main/farm_project
unzip -o ~/Downloads/farm_harvest_common_20261002.zip -d .
python sim/tools/migrate_harvest_common.py
bash scripts/build.sh sim
source scripts/env.sh sim
ros2 interface show farm_interfaces/action/HarvestTask
```

이관 도구는 이전 `farm_sim_harvest` 안의 node/communication/mission/state_controller/contract 5개 소스와 기존 설치된 harvest_node 진입점만 백업 후 제거한다. 백업은 `sim/runs/patch_backups/old_sim_harvest_*.zip`에 생성한다. 새 평가 모듈·설정·실행 결과는 삭제하지 않는다. 이전 패치를 적용하지 않았다면 삭제할 파일이 없어도 정상이다. 압축 해제만으로는 기존 파일이 삭제되지 않으므로 이관 명령을 반드시 실행한다.

## 전체 실행

```bash
ros2 launch farm_sim_runtime all.launch.py \
  project_root:="$PWD" \
  isaac_python:="$HOME/isaac/env_isaaclab/bin/python" \
  harvest:=true device:=0
```

활성 robot_venv의 비전 Python을 자동 사용한다. Isaac은 한 개, scout/harvest bringup은 각각 한 개, 수확 서버는 공통 harvest_robot 한 개, 과실 평가 노드는 별도 한 개다. 수확만 시험하려면 `scout:=false`를 추가한다. Isaac 내부 물리 로봇 두 대는 유지되고 예찰 서버만 빠진다.

## 분리 실행

각 터미널에서 프로젝트 루트 및 `source scripts/env.sh sim`을 적용한다. 전체 실행과 아래 실행을 중복 기동하지 않는다.

```bash
# 1. Isaac 환경과 두 물리 로봇, 독립 시계
ros2 launch farm_sim_runtime isaac.launch.py \
  project_root:="$PWD" \
  isaac_python:="$HOME/isaac/env_isaaclab/bin/python" \
  fleet_config:=sim/ros_ws/src/farm_sim_config/config/harvest_fleet.json

# 2. 예찰 bringup — fleet용 설정은 중복 /clock 발행을 끔
ros2 launch farm_sim_runtime scout.launch.py \
  project_root:="$PWD" device:=0 \
  environment_config:=sim/ros_ws/src/farm_sim_config/config/scout_fleet_runtime.yaml

# 3. 수확 공통 bringup + 시뮬 평가
ros2 launch farm_sim_runtime harvest.launch.py project_root:="$PWD" mode:=sim

# 4. RViz
ros2 launch farm_bringup rviz.launch.py \
  project_root:="$PWD" mode:=sim \
  environment_config:=sim/ros_ws/src/farm_sim_config/config/scout_fleet_runtime.yaml \
  rviz_config:=sim/ros_ws/src/farm_sim_config/config/scout_harvest.rviz
```

평가 없이 공통 수확 bringup만 실행하려면 3번 대신 다음 명령을 쓴다. Isaac은 별도로 실행해야 한다.

```bash
ros2 launch farm_bringup harvest.launch.py project_root:="$PWD" mode:=sim
```

## 실물 담당자 인수

공통 서버와 bringup은 구현했다. **실물 장치 드라이버·수확용 실물 환경 데이터는 이번 범위에서 구현하지 않았다.** 기본 real 실행은 장치 미구현 오류로 종료하며 sim으로 대체하지 않는다.

담당자가 실물 드라이버를 별도로 실행하고 실제 환경 프로파일을 만든 후에는 아래처럼 같은 서버를 연결할 수 있다. 아래 경로는 작성해야 할 예시이며 현재 제공 파일이 아니다.

```bash
ros2 launch farm_bringup harvest.launch.py \
  project_root:="$PWD" mode:=real devices:=false \
  environment_config:=robot/config/environments/harvest_real.yaml
```

프로파일 필수값: schema_version=1, mode=real, robot_id, map_id, map_yaml, route_graph, nav_params, device_config, harvest_config, navigation. 장치 설정의 robot_id/map_id는 프로파일과 일치해야 한다. 파일들은 sim 외부에 둔다. 실물 지도·TF·graph·Nav2 값은 실제 수확 로봇 기준으로 작성한다. harvest_config에는 robot_id, map_id, segments, completion_policy=`ARRIVAL_ONLY_NO_HARVEST`를 지정한다. 시뮬 평가 설정은 필요 없다.

외부에서 Nav2도 실행하는 구성이라면 `navigation:=false`를 추가한다. 중복 Nav2를 실행하지 않는다. 추후 장치 연결부를 완성하면 기본 bringup이 해당 드라이버를 포함하도록 연결한다. 팔 작업은 현재 양 모드 모두 생략하며 실제 수확 실적 기능은 후속 구현 대상이다.

## 결과 계약과 평가 분리

- Action: `/harvest_01/harvest_task`, `farm_interfaces/action/HarvestTask`.
- 공통 서버가 위치·방향·정지를 확인한 후 ROS SUCCEEDED, result_code SUCCESS, error_code NONE을 반환한다. harvested_count=0, failed_count=0, Feedback.success_count=0. expected_count는 요청값을 유지한다.
- 경로 노드 사이 window XY도 기존 RouteGraph → Nav2 FollowPath/RPP를 사용한다. 목표가 graph에서 2cm 초과 이탈하면 실패하며 자유 주행 모드로 자동 변경하지 않는다. 같은 주행 알고리즘을 쓰되 수확용 graph/footprint/속도 제한은 별도다.
- 미도착은 FAILED, 취소 완료는 CANCELED, 정지 확인 실패는 CANCEL_UNCONFIRMED로 새 작업을 막는다. 교통 제어·도킹·자동 복귀·팔 작업은 추가하지 않았다.
- 공통 서버는 환경 독립적인 작업 진단 JSON을 상대 토픽 `task_events`에 발행한다. 수확 namespace에서는 `/harvest_01/task_events`이다. std_msgs/String, RELIABLE/TRANSIENT_LOCAL, depth=100. 관제 HarvestTask 규약의 대체가 아닌 내부 진단 채널이다.
- 시뮬 평가 노드만 이 이벤트를 구독하여 실제 Isaac pose와 과실 중심점으로 expected/actual/delta/GT ID/중복을 기록한다. **공통 서버는 평가를 호출하거나 기다리지 않는다.** 평가 노드 오류·부재는 Action 결과에 영향을 주지 않는다.
- 결과 파일: `sim/runs/harvest_motion/<평가세션>/<task_id>_<event_id>.json`. snapshot: `sim/runs/runtime/harvest_scene.json`.
- 최신 snapshot이 없거나 도착 시점과 맞지 않으면 UNAVAILABLE로 기록한다. 지연 구독으로 과거 이벤트를 받으면 과거 과실 수를 재구성하지 않는다. 실패한 이동은 SKIPPED_NOT_ARRIVED이다. 평가 노드가 아예 실행되지 않으면 비교 로그가 생기지 않는다.
- 비교 기준은 기존 임시 박스 중심 [-0.19,0.435,0.828]m, 크기 [0.35,0.10,0.45]m이며 red/yellow 과실만 집계한다. 실제 팔 IK/충돌 도달성 판정은 아니다. 박스는 Isaac에 보라색으로 표시한다.

## 시험 입력

실제 예찰 검출 결과가 아닌 경로 이동 확인용 입력이다. 좌표는 task/graph에서 읽고 task_id는 매번 생성한다. W99, expected=0은 시험값이다.

```bash
ros2 action send_goal /harvest_01/harvest_task farm_interfaces/action/HarvestTask \
  "$(python sim/tools/harvest_smoke_goal.py --section SEC01 --fraction 0.313 --expected-count 0)" \
  --feedback
```

실제 expected 비교에는 관제가 받은 window ID/goal_pose/expected_count를 그대로 사용한다.

## 검증과 변경 기록

오프라인 31개(시뮬/계약/공통 sim-real 조합 22개 + 기존 launch 9개), 기존 경로 371개 및 수확 엣지 내부 목표 48개 통과. sim/real이 같은 harvest_robot 노드를 선택하는 것, real의 use_sim_time=false, 공통 단독 실행에 평가 노드가 없는 것, 동시 실행에 수확 서버와 평가가 각각 한 개인 것을 확인했다.

ROS·colcon·Isaac이 없는 환경이므로 실제 빌드/통신/주행은 미검증이다. 물리 station 배치, 바퀴 방향, LiDAR/AMCL 정합, Action 도착 결과, 과실 로그를 사용자 PC에서 확인해야 한다. 시뮬 reset 시 Nav2와 서버도 함께 재시작한다.

공통 변경: 새 harvest_robot 패키지, farm_bringup harvest.launch.py와 package.xml. 앞서 승인한 HarvestTask.action/CMake 등록은 그대로 포함한다. 자세한 변경 기록은 sim/docs/CHANGELOG.md의 009 항목을 따른다. 원복 시 적용 전 백업·Git 기준으로 공통 패키지/launch 및 sim 파일을 복원하고 양 workspace를 재빌드한다.
