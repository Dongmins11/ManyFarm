# 공통 주행 구조와 예찰 연결

2026-10-01 합의와 구현 기록. robot/control/sim 구조와 예찰 State 패턴을 유지하고 주행 기능을 farm_navigation으로 분리했다. 기존 코드의 백업 위치는 이 문서 아래에 기록했다.

## 현재 구현한 것

| 위치 | 역할 |
|---|---|
| farm_navigation/navigation_types.py | 주행 조건, 경로 계획, 요청별 상태·결과 |
| farm_navigation/navigator.py | 공통 이동 창구. 계획과 실행 분리, 도착·정지 확인 |
| farm_navigation/nav2_client.py | NavigateToPose/FollowPath 전송·승인·결과·취소 |
| farm_navigation/route.py | JSON GeoJSON 방향 그래프 검증, 엣지 중간 목표까지 거리 기반 탐색 |
| farm_navigation/path_builder.py | 경로 좌표를 ROS Path로 보간, 최종 목표 방향 보존 |
| farm_navigation/pose_provider.py | 현재 또는 촬영 시각의 TF 조회. TF 발행·위치추정기는 아님 |
| farm_navigation/motion_monitor.py | odom 수신·최신성·정지 판정. 바퀴 odom을 다시 계산하지 않음 |
| farm_navigation/arrival.py | 기존 위치·방향 도착 오차 및 Goal checker 검사 |
| farm_navigation/configuration.py | 환경별 JSON/YAML 읽기, 경로 해석, 지도·로봇·그래프 일치 검사 |

공통 라이브러리는 ScoutNode·Mission·과실·윈도우를 import하지 않는다. 현재 예찰 Node가 공통 객체를 생성해 State의 I/O 작업 스레드에 연결한다. 별도 주행 프로세스를 추가한 것이 아니다.

예찰 State의 enter는 요청 후 반환한다. Controller의 완료 큐를 거쳐 다음 State로 전환한다. NAVIGATION_MOVE는 NavigationResult의 stamp_ns를 받아 그 이후 프레임을 관측한다. 과실 ID·좌표·윈도우 계산은 변경하지 않았다.

## 기존 코드와 달라진 점

- 이전 scout_new/navigator.py는 ScoutNode 내부의 액션·odom·TF 필드에 직접 접근했다. 이제 필요한 공통 객체와 설정·취소 확인 콜백을 명시적으로 받는다.
- 기존 scout_robot/route.py와 arrival.py는 공통 모듈의 재노출 파일로 남겼다. 기존 survey_server·도구의 import를 깨지 않고 실제 구현을 한 곳으로 모았다.
- 미니관제의 수확 이동은 자체 RouteToPose → ROS Path → FollowPath였다. 이 알고리즘을 일반화했고, LineString과 시뮬의 단일 직선 MultiLineString 모두 읽는다.
- 엣지 ID와 그래프 내용 해시를 계획에 보관한다. 현재 위치가 차지한 엣지나 교통 허가를 계산하는 기능은 아직 아니다.
- 원래 _ 멤버·snake_case와 Node/Mission/Communication/StateController 분리는 유지했다.

## 중요한 현재 데이터 제약

현재 시뮬 graph.geojson은 128개 노드, 112개 방향 엣지이고 약하게 연결된 성분이 16개다. 각 베드의 8개 노드는 연결되어 있지만 베드 사이 이동 통로는 없다.

따라서 현재 데이터로 전 구역을 FollowPath만으로 주행할 수 있다고 주장하지 않는다. 베드 간 통로를 실제 지도에 맞춰 추가하고, 초기 위치가 그래프에 대응하는지 확인해야 한다. 노드 연결을 임의로 추가하거나 경로 탐색 실패 때 몰래 NavigateToPose로 바꾸지 않는다.

동봉 시뮬 환경의 navigation.mode는 기존 동작 보존을 위해 navigate_to_pose다. 연결된 그래프가 준비되면 동일한 코드에서 follow_path를 선택한다. 그래프 경로가 없거나 시작·목표가 허용 거리 밖이면 이동 요청 전에 실패한다.

## 환경 선택

- sim 기본: sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml
- real 작성 예제: robot/config/environments/scout_real.yaml
- real 기본 로드 위치: robot/config/environments/scout_real.yaml

모든 상대 파일 경로는 project_root인 farm_project 기준이다. YAML은 지도·그래프·Nav2·예찰·장치 설정 파일의 위치와 주행 설정을 모은다. 베드 좌표와 노드 ID는 기존 예찰 JSON 및 그래프에 그대로 있다. 다른 환경의 파일 경로를 코드에 삽입하지 않는다.

map_id·robot_id가 환경/장치/예찰에서 다르거나, 베드 경로 파일과 주행 그래프가 다르면 실행을 거절한다. 실물 예제는 configured=false이며 실제 실측값을 채우기 전 실행할 수 없다. 실물 드라이버도 아직 미구현이다.

```yaml
navigation:
  mode: follow_path  # 또는 navigate_to_pose. 실패 시 자동 전환하지 않음
  base_frame: scout_01/base_footprint
  map_frame: map
  controller_id: FollowPath
  goal_checker_id: general_goal_checker
  progress_checker_id: progress_checker
  max_start_distance_m: 0.10
  max_goal_distance_m: 0.02
  path_spacing_m: 0.04
```

위 플러그인 ID는 선택한 Nav2 YAML과 일치해야 한다. 숫자는 물리적 보증값이 아니라 현재 초기 설정이며 로봇·환경에 맞춰 검증해야 한다. 현 예찰 인터페이스의 frame은 map을 유지한다.

## 한 명령으로 실행

빌드 환경에서 scripts/build.sh sim으로 공통·시뮬 패키지를 빌드하고 scripts/env.sh sim을 source한 다음 실행한다. 다음은 사용자가 실행할 명령이며 이번 작업 중 실제 장치 실행은 하지 않았다.

```bash
ros2 launch farm_bringup scout.launch.py \
  mode:=sim survey:=true \
  project_root:=$HOME/manyfarm/main/farm_project \
  isaac_python:=/실제/Isaac환경/bin/python \
  vision_python:=/실제/영상환경/bin/python \
  headless:=true
```

Isaac을 이미 따로 실행 중이면 start_isaac:=false를 사용한다. 새 지도·베드 설정으로 시작한 기존 Isaac 인스턴스인지 확인해야 한다. 통합 런치는 장치·Nav2·예찰 서버를 포함하고, 실제 이동은 ScoutArea Goal을 받은 뒤 시작한다. Nav2/위치추정/영상 준비는 여전히 필요하며 launch 포함 순서만으로 준비 완료를 보장하지 않는다.

기존 장치 전용 scout.launch.py 기본값(survey=false)과 서버 전용 scout_survey.launch.py를 유지한다. 환경 파일을 지정한 통합 실행에서 map/nav_params/route_file을 다른 파일로 덮어쓰는 혼합은 거절한다. 기존 직접 서버 실행도 호환되지만 새 환경 통합 방식을 권장한다.

실물은 mode:=real과 작성 완료된 실물 환경 파일을 사용한다. 아직 farm_real_devices가 구현되지 않았으므로 바로 실물에서 동작한다는 뜻은 아니다.

## 교통 제어는 추후 연결

지금은 대기/재개 서비스·예약·점유 판단을 구현하지 않았다. Navigator의 계획 단계와 실행 단계, 요청 ID, 읽기 전용 상태 스냅샷을 분리했다. 위치·경로·동작 상태는 로봇마다 독립 객체에 둔다.

나중에는 로봇이 경로를 계산하고 관제가 진입 전 대기·재개를 지시하는 계약을 연결한다. 예찰은 NAVIGATION_MOVE를 유지하며 교통 대기를 주행 실패와 구분한다. 현재 cancel_nav는 Goal 종료와 정지 확인을 수행하는 취소이며 pause를 흉내 내지 않는다. 취소 완료만으로 점유를 해제하면 안 된다.

## 이관 상태와 검증 범위

scout_new는 아직 기존 위치에 있다. 아이작심에서 이동·실제 촬영·결과 보고 전체 확인 후 scout_robot/scout_robot으로 최종 교체하고 임시 폴더와 대체된 실행 코드를 정리한다. 이 검증 없이 기존 구현을 삭제하지 않았다.

검증 스크립트와 상세 결과는 NAVIGATION_REFACTOR_HISTORY.md를 확인한다. 실제 시뮬/장치 E2E 및 실물 검증은 남아 있다.
