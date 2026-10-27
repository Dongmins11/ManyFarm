# 관제 교통·주행 시험 전달본 반영 — 2026-10-27

## 범위와 승인

사용자 `main/traffic_and_drive_tests_sim_20261027` 반영 요청. main68e5ef7 위 기존 교통 미커밋 작업 및 직전 공통 주행 재시도를 보존하며 선별 반영했다. 공통 변경의 목적은 관제 계약 연결이며 시뮬 업무 로직 복사본/별도 교통 서버는 만들지 않았다. 실물 프로필과 기존 업무 액션은 유지한다. 미커밋/미푸시.

## 반영한 내용

- 전달본98파일 무결성 PASS. interface_additions9타입 중8개 기존 작업본과 바이트 일치. NavigateToNode.action만 추가하고 CMake 등록. Discharge/기존 업무 타입 유지. RobotStatus 차이는 주석만 있고 필드는 동일.
- 제공된 traffic_zones.yaml, 예찰 graph.geojson, 수확 harvest_graph.geojson은 현재 시뮬 입력과 SHA256 일치.
- 시뮬 전용 `farm_sim_runtime/traffic_drive_test.py`: `/scout_01/traffic_test/navigate_to_node`, `/harvest_01/traffic_test/navigate_to_node` 제공. 두 로봇 현재 등록 READY와 자기 교통·위치 준비를 확인한 요청만 접수한다.
- 일반 작업·복귀·인계와 같은 ActionHandoff 예약을 비선점/선점불가로 사용한다. 기존 Navigator/RouteGraph/Nav2Client/TrafficClient가 계획·허가·주행을 담당한다. Acquire.task_id는 예약 중인 상위 테스트 task_id를 그대로 사용한다.
- 기존 TrafficClient의 WAITING Feedback 교체·취소 확인 후 새 request_id/route_revision 요청을 재사용. 수확 작업 구간의 hold_zone_ids/exit_node_id가 막힌 후보도 제외하며 전체 우회 경로의 허가를 요청한다. 중간 통과 작업 구간의 예약 공간도 보존한다.
- 성공 전에 목표 도착 오차, 정지, 도착 이후 RobotStatus 표본 및 동일 허가 문맥 Progress를 확인한다. PLANNING/MOVING Feedback과 결과 로그를 남긴다.
- 취소는 자신의 Nav2 종료/정지와 대기 Acquire 취소·미사용/이탈 예약 정리를 확인한 후 CANCELED. 정리 불명은 FAILED/CANCEL_UNCONFIRMED 및 새 작업 차단. 현재 차체 점유는 유지하고, 그 허가의 Progress.context도 보존한다. Goal 결과는 같은 UUID로1시간 재조회 가능하다.
- 시뮬 교통 전용 두 환경에만 `traffic.test_drive_enabled=true`. 일반 시뮬/실물에서는 서버가 생기지 않는다. 공통 scout/harvest Node에는 해당 시뮬 모듈의 조립·종료 연결만 추가했다. 실물 모드에서 시험 플래그를 선택하면 오류로 거절한다.
- 예찰 Status는 시험 예약의 task_id와 NAVIGATION_MOVE 상태를 보고한다. 수확은 기존 handoff 상태 보고를 재사용한다.

## 수정 경로

- robot/ros_ws/src/farm_interfaces/{action/NavigateToNode.action,CMakeLists.txt}
- robot/ros_ws/src/farm_navigation/farm_navigation/{traffic_client.py,traffic_contract.py}
- robot/ros_ws/src/{scout_robot/scout_new/scout_node.py,scout_robot/scout_new/traffic_status.py,harvest_robot/harvest_robot/node.py}
- sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/traffic_drive_test.py
- sim/ros_ws/src/farm_sim_config/config/{scout,harvest}_traffic_runtime.yaml
- sim/tests/test_traffic_drive_test.py、farm_navigation/test/test_traffic.py。
- harvest_robot/test/test_navigator_dispatch.py의 설정 대역에 앞선 재시도 API의 기본0 필드를 추가. 관련4개 회귀 실패를 확인하고 시험 대역만 보정했다.

## 직접 실행한 검증

| 검증 | 결과와 한계 |
|---|---|
| 전달본 무결성/ROS 구조 | 98파일 PASS, 실제 생성 타입과35개 메시지 예시 PASS, 노드 생성 없음 |
| 실제 사용 workspace 빌드 | 공통4패키지 + sim2패키지 PASS, 양 Node/시험 모듈 import 및 두 프로필 로드 PASS |
| 공통 주행 전체·시험 서버·수확 연결 회귀 | **117 passed** |
| 실제 DDS Action 전송 | Domain13/SUBNET 별도 probe 이름공간, 성공4/SUCCESS·실패6/FAILED·취소5/CANCELED 및 동일 UUID 결과 재조회 PASS. **주행 실행기는 대역** |
| 실제 저장 그래프 우회 | 예찰9004점유 차단 입력에서 수확9010→10103 **47.5m** 전체 경로, 차단 노드·엣지 및 작업 예약/출구 비접촉 PASS. **오프라인 계산** |
| Isaac 두 로봇 공동 대기·우회 주행 | **NOT_RUN** |
| 실제 관제 연결 중 OFF/ON·취소·재시작·시계 역행 | **NOT_RUN**. 기존 모의 교통 회귀와 구분 |

원본 실행 스크립트/첫 회귀 실패/최종 로그: `sim/runs/traffic_drive_integration_20261027/`. 공유용 결과: `sim/docs/test_results/20261027_traffic_drive/`. 실제 시험 서버는 아직 상시 기동하지 않았다. 별도 probe는 검사 후 종료했다.

## 다음 공동 시험 실행

기존 업무·복귀·인계를 정리한 뒤 아래 환경으로 시작한다. 관제 교통 서버는 기존 관제에서 실행하며 시뮬 PC에 추가하지 않는다.

```bash
cd /home/ysy/main/farm_project
source /opt/ros/jazzy/setup.bash
source scripts/env.sh sim
export ROS_DOMAIN_ID=13
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
ros2 launch farm_sim_runtime all.launch.py \
  project_root:="$PWD" harvest:=true rviz:=false headless:=true physics_device:=cpu \
  environment_config:=sim/ros_ws/src/farm_sim_config/config/scout_traffic_runtime.yaml \
  harvest_environment_config:=sim/ros_ws/src/farm_sim_config/config/harvest_traffic_runtime.yaml
```

관제에서 교통 ON/양 로봇 등록 READY를 확인한다. 테스트는 기존 관제 UI에서 요청한다. `ros2 action list -t`에서 두 traffic_test 엔드포인트를 확인할 수 있다. 일반 시뮬 launch의 기본 환경 파일만으로는 이 서버가 활성화되지 않는다.

1. 대기 후 통과: 예찰9004 → 수확9010 → 수확9004요청 WAITING → 예찰9001이탈 → 반납/허가/도착.
2. 우회: 예찰9004정차 유지 → 수확9010 → 수확10103. 동일 task_id의 전체 경로 허가 및 실제 우회 중간 위치/도착을 확인.
3. 진행 중 취소, 우회로 없음, OFF/ON, 관제·로봇 재시작, sim일시정지/시간 역행은 별도 결과로 기록.

이번 타입 빌드나 대역 Action PASS를 공동 실주행 PASS로 보고하지 않는다. 작업자 브랜치 정리본 수령 시 이 변경과 새 공통 주행/교통 변경을 선별 대조한다. 복원 시 위 변경만 역적용하고 기존 교통/재시도 작업 전체를 초기화하지 않는다.
