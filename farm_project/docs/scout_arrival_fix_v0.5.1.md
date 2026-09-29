# v0.5.1 — 예찰 도착 판정 재발 방지

## 확인한 문제

기존 배포본의 Nav2 도착 허용 거리는 0.12m, 예찰 허용 거리는 0.08m였습니다.
방향도 Nav2 0.15rad, 예찰 0.12rad로 서로 달랐습니다.
따라서 Nav2가 성공으로 종료해도 예찰이 거부할 수 있습니다.
2026-09-29 실패 로그에는 실제 오차와 실행 중인 설정값이 없어, 이번 실패의 원인을 이 불일치 하나로 확정할 수는 없습니다.

이번 수정은 Nav2 기준을 0.05m / 0.08rad로 영구 저장합니다.
예찰의 0.08m / 0.12rad 판정은 유지합니다.
예찰 시작 시 실행 중인 Nav2 설정을 직접 읽어, 기준이 맞지 않으면 이동 전에 `NAV_CONFIG_MISMATCH`로 알립니다.
Nav2 성공 후 정지 확인(기존 0.8초)을 먼저 하고, 그 odom 시각의 `map → base_footprint`로 실제 오차를 계산합니다.

Nav2 기준을 더 엄격히 해도 정지 후 위치추정 변화 등으로 예찰 기준을 벗어날 수 있습니다.
그때는 실패를 유지하고 실제 거리·방향 오차, 목표·현재 좌표를 결과에 기록합니다. 자동 재주행은 하지 않습니다.

## 1. 종료·적용·빌드

실행 중인 예찰 서버와 Isaac/Nav2 bringup을 각각 Ctrl+C로 종료합니다.
robot_venv 터미널에서 실행하세요.

```bash
unzip -o ~/Downloads/farm_scout_arrival_fix_v0.5.1.zip -d ~/robotarm/
cd ~/robotarm/farm_project
source scripts/env.sh sim
python scripts/apply_scout_arrival_fix.py &&
(cd robot/ros_ws && colcon build --packages-select scout_robot farm_bringup) &&
(cd sim/ros_ws && colcon build --packages-select farm_sim_config)
```

적용 스크립트가 현재 YAML의 두 도착 기준만 바꿉니다.
속도, 최소 속도, `FollowPath.max_angular_accel`, 초기 위치, 주석은 보존합니다.
변경 전 YAML은 `runs/config_backups/`에 저장됩니다. 다시 실행해도 중복 변경하지 않습니다.
ZIP에는 전체 `nav2_scout.yaml`을 넣지 않았으므로 이 스크립트까지 실행해야 합니다.

별도 `nav_params:=...` 파일을 사용한다면 실제 사용하는 파일에 적용하세요.

```bash
python scripts/apply_scout_arrival_fix.py --nav-params /실제/사용중인/nav2.yaml
```

이 스크립트는 현재 프로젝트의 `general_goal_checker` 하나를 쓰는 YAML 구조용입니다.
구조가 다르면 파일을 바꾸지 않고 알립니다.

## 2. 터미널 A — Isaac + Nav2

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout.launch.py mode:=sim navigation:=true rviz:=true \
  isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python \
  assets_root:="$PWD/sim/assets"
```

시작 로그의 `Scout Nav2 설정 파일:`에 이번에 빌드한 `farm_sim_config` 경로가 나옵니다.
설정 파일을 바꾸는 것만으로 이미 실행 중인 Nav2 설정이 바뀌지는 않으므로 재시작이 필요합니다.

## 3. 터미널 B — 예찰 서버

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout_survey.launch.py mode:=sim \
  project_root:="$PWD" vision_python:="$(cat runs/vision_python.txt)" device:=0
```

## 4. 터미널 C — 시작 요청

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
ros2 param get /scout_01/controller_server general_goal_checker.xy_goal_tolerance
ros2 param get /scout_01/controller_server general_goal_checker.yaw_goal_tolerance
python control/scripts/send_scout_area.py --section BED_01
```

설정값은 각각 **0.05**, **0.08**이어야 합니다.
기존 값이면 Nav2가 읽은 파일, 빌드, 재시작을 확인합니다. 새 예찰 서버도 같은 값을 검사합니다.
기존 `scout_route` 실행기를 동시에 켜지 마세요.

## 추가된 기록

`runs/scout_survey/<session>/survey.json`:

- `navigation_preflight`: 실행 중인 controller에서 읽은 값과 사전 점검 결과.
- `navigation`: 이동 목표별 목표/현재 좌표, 정지 시각, 위치·방향 오차, 판정.
- 관제의 실패 `error_message`에도 실제 오차와 허용값이 표시됩니다.

예시(설명용 수치):

```text
Nav2 succeeded but settled pose is outside survey tolerance:
distance=0.1050m (limit=0.0800m), heading=0.0400rad (limit=0.1200rad);
goal=(-6.655,9.500,-1.571), actual=(-6.655,9.605,-1.531)
```

이 수치는 AMCL/TF가 추정한 로봇 위치의 오차이며 Isaac 정답 위치 오차가 아닙니다.
원인 분석 시 `navigation_preflight`와 해당 `navigation` 항목을 함께 보면 됩니다.

## 검증 범위

설정값 불일치 차단, YAML의 다른 튜닝 보존, 각도 경계 처리, 정지 후 시각을 사용한 도착 판정,
실패·취소 시 도착 승인 차단을 ROS 없이 검증했습니다.
이번 수정의 회귀 검사 10개와 기존 예찰 검사 9개가 통과했습니다.
작성 환경에는 ROS Jazzy/Isaac Sim이 없어 실제 ROS 서비스 통신, colcon 빌드, 시뮬레이션 주행은 실행하지 못했습니다.

구현 참고: [Nav2 Jazzy SimpleGoalChecker](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/controller_server/controller_server_plugins/simple_goal_checker/),
[Jazzy SimpleGoalChecker 소스](https://api.nav2.org/nav2-jazzy/html/simple__goal__checker_8cpp_source.html).
새 종류의 goal checker를 도입하면 사전 점검의 지원 규칙도 함께 확장해야 합니다.
