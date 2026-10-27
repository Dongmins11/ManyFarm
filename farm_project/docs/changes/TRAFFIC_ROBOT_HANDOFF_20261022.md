# 교통 제어 로봇 측 구현 및 실물 파트 인계

2026-10-22 KST. 시작 기준 main/0832b6f. 사용자 승인: “공통코드랑 시뮬코드쪽에 필요작업 적용하고 실물쪽 작업파트는 문서로 …”. 이번 변경은 미커밋이며 실행 중인 프로세스·실물 환경 파일을 변경하지 않았다.

## 책임과 적용 범위

관제가 충돌·예약·점유·허가·반납을 최종 판단한다. 이번 코드는 로봇 측 ROS 클라이언트와 주행 연결이다. 관제 서버, 임의 TTL/Renew, 자동 양보, 운송 도킹은 추가하지 않았다.

계약 기준: `traffic_sim_handoff_20261021`의 DECISIONS, STARTUP_RESET, 인터페이스 8개. 통신 타입은 전달본을 그대로 공통 farm_interfaces에 통합했다. 기존 RobotStatus의 필드·타입은 유지하며 교통 활성 시 boot를 영속 연번으로 발급한다.

## 적용 파일과 처리

| 파일 (robot/ros_ws/src/ 기준) | 역할 |
| --- | --- |
| farm_interfaces/{msg,srv,action}/Traffic*, AcquirePassage.action, ReleasePassage.srv, GetPassageState.srv, CMakeLists.txt | 공통 타입 8개 및 빌드 등록 |
| farm_navigation/farm_navigation/traffic_client.py | 등록·조회·허가 대기·Feedback 교체·취소/발급 경합·진행 보고·반납 |
| farm_navigation/farm_navigation/traffic_contract.py | 영속 ID와 중복 프로세스 잠금, 그래프/구역 대응, 차체 점유의 보조 보고 |
| farm_navigation/farm_navigation/nav2_client.py | 모든 기존 Nav2Client 실행의 허가 검사. 주행 제한시간 시작 전에 허가를 기다림 |
| farm_navigation/farm_navigation/route.py | 차단 노드/엣지를 제외하는 기존 경로 탐색 확장. 기존 호출은 동일 |
| farm_navigation/farm_navigation/pose_provider.py | 보고용 TF 원본과 샘플 시각 조회 |
| farm_navigation/farm_navigation/spin_client.py | 첫 교통 범위 밖의 인계 Spin을 명시적으로 차단 |
| harvest_robot/harvest_robot/{node,status,communication}.py | 수확 객체 연결·같은 boot의 기존 Status 발행·업무 초기화 중단 |
| scout_robot/scout_new/{scout_node,scout_communication,traffic_status}.py | 예찰 객체 연결·Status 발행·업무 초기화 중단 |

실제 경로는 주행 전에 그래프 노드·방향 엣지 목록으로 대응한다. 짧은 위치 오차 연결선은 기존 허용거리 내에서만 허용하며 모호하거나 등록 그래프 밖인 경로는 실행하지 않는다. 수확 중간 목표는 작업 구간 출구까지 예약 범위를 확장하되 실제 작업 목표 좌표는 유지한다. 수확 구간 전체 보호가 Result에 포함되지 않으면 출발하지 않는다.

허가를 기다리는 동안 기존 업무는 종료되지 않고 Status/Progress는 계속 처리된다. 정상 이동은 현재 요청·boot·epoch·등록·전체 경로와 맞는 GRANTED/ACTIVE만 실행한다. 초기화/세대 변경은 정지 명령과 주행 취소를 보내고 진행 업무도 기존 중단 경로로 종료한다. 등록 복구가 이전 팔/예찰 업무의 자동 재개가 되지 않도록 새 업무 시작과 분리했다.

Feedback은 증가한 순번의 전체 차단 목록으로 교체한다. 목록 변경 때 기존 공통 그래프 탐색기로 우회한다. 설치된 ComputeRoute Action에는 차단 ID 입력이 없으므로 교통 우회는 이 명시적 로컬 그래프 경로를 사용한다. 후진 경로는 일반 전진 우회로 바꾸지 않는다. 우회 불가 시 원 요청을 유지한다. 취소와 발급이 경합해 GRANTED가 오면 이동하지 않고 Get으로 확인 후 미사용 예약을 정리한다.

Progress는 정확히 발행한 Status 순번을 참조한다. POSITION sync 수신 시 ROS 시각보다 나중에 생성된 유효 TF 샘플이 필요하다. 캐시 재발행은 등록으로 인정하지 않는다. /clock 역행 후 같은 epoch로 재출발하지 않는다. 위치 불명 상태에서는 반납하지 않는다.

차체의 실제 보고 위치가 빠져나온 자원을 EXITED 후보로 요청한다. 미래 경로에서 다시 사용할 공간과 현재 작업 구간은 보호한다. UNUSED는 폐기한 요청/이전 허가의 미진입 후보에만 적용한다. 로컬 계산은 보고·요청용이며 관제의 released=true를 받은 뒤에만 반납을 반영한다. 거절 응답은 성공으로 처리하지 않는다.

## 실물 담당자가 할 일

### 1. 공통 코드와 타입 재빌드

이번 공통 소스를 반영하고 기존 실물 빌드 절차로 최소 farm_interfaces, farm_navigation, scout_robot, harvest_robot와 의존 패키지를 재빌드한다. 관제도 동일한 8개 타입을 사용해야 한다. 서로 다른 예전 farm_interfaces overlay가 먼저 로딩되지 않는지 확인한다.

### 2. 실물 전용 교통 등록 파일 작성

시뮬 `traffic_zones.yaml`과 맵/좌표를 실물에 복사하지 않는다. 실제 실물 환경의 map_yaml·역할별 route_graph·차체 프로파일·노드/양방향 엣지 대응·수확 작업 구간 및 출구 공간으로 같은 스키마의 파일을 제공한다. 기준점이 차체 중심인지, base_frame과 일치하는지 확인한다. 팔을 제외하는 첫 시뮬 프로파일이 실물 안전성을 보증하지 않는다.

실물 환경 YAML에 다음 설정을 추가한다. 경로는 실물 담당이 정한 project_root 기준 경로 또는 절대 경로다.

```yaml
traffic:
  enabled: true
  registry: <실물 전용 등록 YAML 경로>
  state_file: <해당 로봇의 영속 SQLite 파일 경로>
```

SQLite는 로봇마다 별도 파일이며 재시작·전체 초기화 때 삭제하지 않는다. 같은 로봇의 중복 실행은 파일 잠금으로 거절한다. 이 파일을 다른 로봇/PC에 그대로 복제해 ID를 재사용하지 않는다. 디스크 손상·교체 시 관제와 ID 복구를 맞춘다.

등록 YAML의 source_file 상대 경로에는 실제 실행 그래프와 해시가 같은 원본을 둔다. graph_id·graph_revision·map_revision·zone_revision을 관제와 일치시킨다. 실물 환경 YAML은 이번 작업에서 수정하지 않았다.

### 3. 상태와 구동 연결 확인

- 예찰/수확의 실제 robot_id·namespace·map/base TF를 확인한다. 기존 robot_status 발행기가 따로 있으면 중복 발행하지 않도록 정리한다. 교통 활성 예찰은 scout_new 내부에서 Status를 발행한다.
- 수확은 기존 HarvestStatus 발행을 재사용한다. RobotStatus와 TrafficProgress의 boot가 같아야 한다.
- 새 위치는 TF 원본 stamp로 판별한다. 위치 공급기가 오래된 pose를 새 timestamp로 재포장하지 않도록 한다. 위치 초기화 시 공급기/TF 캐시의 초기화 전 샘플 처리를 검증한다.
- 정지 명령은 로봇 namespace의 cmd_vel_nav/cmd_vel에 보낸다. 실제 mux/smoother/모터 입력 연결과 우선순위를 확인한다. 시작 시 지정 FollowPath/NavigateToPose Action의 이전 Goal도 CancelGoal로 취소한다.
- stopped=true는 명령 전송 의미다. 실물 제동거리·실제 속도 0·프로세스 정지 시 모터 watchdog은 별도 검증 대상이다. 기존 팔 접힘·측정 정지 확인은 제거하지 않았다.
- 첫 범위는 예찰·수확이다. 도킹/인계를 활성화하지 않는다. 교통 활성 상태에서 기존 인계 Spin은 명시적으로 거절한다.

### 4. 관제와 공동 확인

| 통신 | 경로 |
| --- | --- |
| AcquirePassage Action | /traffic/acquire_passage |
| ReleasePassage Service | /traffic/release_passage |
| GetPassageState Service | /traffic/get_passage_state |
| TrafficControlState | /traffic/control_state (Reliable, TransientLocal, depth 1) |
| TrafficProgress | /<robot_id>/traffic_progress (Reliable, Volatile, depth 1) |
| RobotStatus | /<robot_id>/status |

전체 초기화의 **시뮬 조작 완료 → 관제 POSITION sync 발급** 연결은 관제의 로컬 이벤트에 해당한다. 전달본에는 외부 이벤트 endpoint가 없고 관제 실행 소스도 이 작업공간에 없으므로 임의 ROS 서비스를 추가하지 않았다. 현재 시뮬 실행기는 실행 중 reset을 감지하면 재시작을 요구한다. 관제 통합 시 전원 STOP_SENT 확인 후 기존 실행기를 초기화/재시작하고, 완료된 뒤 관제 로컬 완료 이벤트를 호출하는 연결을 담당해야 한다. 로봇 측은 새 POSITION sync와 새 위치 없이 출발하지 않는다.

관제 재연결은 Get 서비스의 발견 상태 변화 또는 새 epoch 통지로 확인한다. DDS 발견이 유지된 채 응답만 영구히 사라지는 경우 자동 타임아웃/재시도를 하지 않는다. 운영자 복구/프로세스 재등록이 필요하다.

## 시뮬 담당 적용과 실행

새 파일:
- `sim/ros_ws/src/farm_sim_config/config/scout_traffic_runtime.yaml`
- `sim/ros_ws/src/farm_sim_config/config/harvest_traffic_runtime.yaml`
- `sim/ros_ws/src/farm_sim_config/config/traffic/` — 전달본 구역 및 원본 맵/그래프 사본

기존 기본 runtime YAML은 유지했다. 교통 시험은 두 새 프로파일을 명시적으로 선택한다. 기존 단독/야간 시험이 갑자기 관제 허가를 기다리지 않게 하기 위한 선택이다. 실제 교통 운용에서 기본 프로파일로 실행하면 교통 제어가 비활성이라는 점에 유의한다.

기존 공통/시뮬 빌드와 환경 로딩을 완료한 터미널에서:

```bash
export ROS_DOMAIN_ID=13
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
ros2 launch farm_sim_runtime all.launch.py \
  project_root:=/home/ysy/main/farm_project \
  harvest:=true \
  environment_config:=sim/ros_ws/src/farm_sim_config/config/scout_traffic_runtime.yaml \
  harvest_environment_config:=sim/ros_ws/src/farm_sim_config/config/harvest_traffic_runtime.yaml
```

vision_python/isaac_python 등 기존 실행 환경 인자는 기존 가이드를 따른다. 관제 서버가 없으면 등록/허가 대기하며 이동하지 않는다. 이 명령은 이번 작업에서 실행하지 않았다.

## 검증과 미검증

직접 실행한 검증 결과는 이 문서 하단에 기록한다. 가짜 전송을 사용하는 상태 시험을 실제 두 로봇 교통 주행 시험으로 해석하지 않는다.

미실행: 전달본 공동 시뮬 시험 25개, 실제 관제와 FIFO/허가 전환 트랜잭션·공간 해제 대조, Isaac 동시 주행, 실물 주행·제동, 전체 초기화 완료 이벤트 통합. 실제 출발 경로/정차 공간/회전 여유는 관제와 함께 검증해야 한다.

되돌리기: 교통 전용 프로파일 대신 기존 runtime 프로파일을 선택하면 기존 주행 경로를 사용한다. 이번 변경 파일만 되돌리고 공통 타입 변경 전 버전으로 관제·로봇을 함께 재빌드한다. 발급 ID DB는 되돌리거나 삭제하지 않는다. commit/push/실물 배포는 수행하지 않았다.

### 직접 검증 결과

- 전달본 무결성: 45개 파일 SHA-256 PASS. 시뮬 지도 YAML/PNG와 역할별 그래프는 현재 원본과 동일.
- ROS 2 Jazzy 실제 `farm_interfaces` isolated colcon build PASS (`/tmp/traffic-build`, `/tmp/traffic-install`). 실행 워크스페이스에 설치하거나 ROS 노드를 시작하지 않음.
- 공통 주행·수확·예찰 테스트 25개 파일, 최종 **235개 PASS**. 새 교통 테스트 19개 포함. 타입을 사용하는 교통 테스트는 가짜 전송/노드와 실제 생성 메시지로 실행.
- 기존 시험의 전역 ROS 모듈 mock이 다른 파일의 생성 타입과 충돌하므로 파일별 별도 프로세스로 실행했다. 수확 가짜 파라미터 서버의 `desired_linear_vel` 누락을 실제 preflight 계약에 맞춰 보완했다. 초기 실패 이후 수정 대상 재검증 통과.
- 구역 경로 대응: 예찰 452개/수확 260개 방향 엣지의 원본 끝점 경로 대응 검사 PASS. 교차 노드 24개 좌표 차이 보존 검사 PASS.
- Python compileall 및 git diff --check PASS.
- 상세 로컬 결과: `sim/runs/traffic_integration_20261022/validation.json`. 실제 관제/Isaac/실물 시험은 모두 미실행이다.
