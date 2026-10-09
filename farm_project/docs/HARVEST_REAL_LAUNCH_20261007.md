# Vic Pinky 통합 실행 — 이동 시험 + 선택적 태그 보정

<!-- HARVEST_CURRENT_20261009 -->
> **현재 실물 기준 — 2026-10-09**
> - 공용 지도 `maps/many_farm`, map_id `many_farm_v1`.
> - `route_then_follow` + `approach_planner=graph`: 진입·작업 모두 그래프 다익스트라 → FollowPath. Route Server는 실행하지 않는다.
> - 11번 정밀 도착·정지 후 작업 목표로 이동한다. lifecycle 확인 대상은 amcl, controller_server, planner_server, bt_navigator다.
> - 사용자 로봇 빌드·설치 검사 PASS. 14번 주행 성공 사례가 있으나 반복 시험의 충돌 예측 중단과 진입점 부근 회전 문제는 미해결이다.
> - 태그 보정 효과·실측 정확도 검증 완료가 아니다. 카메라 종료 -11과 AMCL 시각 경고도 남아 있다.
> - 11번 접근 제어의 추가 수정은 아직 적용하지 않았다.
> - 아래 날짜별 기록의 미실행·이전 구조 설명은 작성 당시 상태이며 현재 실행 안내는 이 기준을 따른다.


## 두 단계 이동 적용 후 변경

2026-10-08 FollowPath 전환 승인으로 실물 기본 미션은 화단 접근 ComputeRoute+FollowPath, 작업·출구 RouteGraph Dijkstra+FollowPath로 연결한다. 상세 현재 기준은 [FollowPath 전환](changes/HARVEST_FOLLOW_PATH_20261008.md)이다. [두 단계 이동과 메시지 변경](HARVEST_TWO_STAGE_NAVIGATION_20261007.md)을 먼저 읽는다. HarvestTask Goal에 section_id가 추가되어 양쪽 인터페이스 재빌드가 필요하다. 현재 SEC_01 진입점은 기존 A 시험 경계 11번이며, 시험 그래프 10~13을 전체 농장 접근 그래프로 오해하지 않는다.

## 범위

예찰 `scout.launch.py`와 같이 `harvest.launch.py` 하나에서 실물 장치·Nav2·수확 이동 서버를 실행한다. `tag_correction:=true`이면 성공한 로봇 내부 카메라/검출 실행본과 태그→AMCL 어댑터도 자동 실행한다. 시작만으로 이동하지 않는다. 목표는 기존 HarvestTask Action으로 받는다.

미션은 `ARRIVAL_ONLY_NO_HARVEST`: 도착 성공을 반환하며 팔 작업은 수행하지 않는다. 전체 수확 FSM 구현 완료가 아니다. [FSM 차이 검토](HARVEST_FSM_GAP_20261007.md)를 참고한다.

## 기존 로봇에서 한 번 준비

- 작업 브랜치: `feat/apriltag-localization`. `project_root`는 저장소 아래 **farm_project**다.
- ROS Jazzy와 `~/vicpinky_ws`의 원래 Vic Pinky 드라이버가 필요하다.
- 카메라 코드는 `robot/tools/tag_camera/`, 캘리브레이션은 `robot/config/cameras/`의 Git 내부 파일을 사용한다. 삭제한 과거 실험 폴더를 다시 만들 필요가 없다. OS·ROS 패키지 설치는 별도다.
- 기존 캡처의 CycloneDDS/image_proc/apriltag_ros/OpenCV/v4l2-ctl 의존성이 필요하다. 기존 전용 Domain 178·loopback 설정을 그대로 사용하며 주행 Domain 156 환경은 변경하지 않는다.
- 기존 캡처가 요구하는 수신 버퍼: `sudo sysctl -w net.core.rmem_max=16777216` (재부팅 후 설정이 유지되는지 운영체제 설정에 따라 다름).
- 기존 mini_fleet·별도 Nav2·별도 장치·카메라·보정 실행본을 동시에 켜지 않는다. 이미 같은 장치나 Nav2를 운영 중인 경우에만 devices/navigation 옵션으로 해당 중복 실행을 제외한다.

프로젝트 루트에서 빌드:

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/vicpinky_ws/install/setup.bash"
cd robot/ros_ws
colcon build --symlink-install --packages-up-to farm_bringup harvest_robot
source install/setup.bash
```

## 로봇 메인 실행

아래 명령은 `farm_project` 디렉터리에서 실행한다. 초기 설치 후에는 환경 source와 이 launch로 실행한다. SSH 비밀번호·IP는 패키지에 넣지 않는다.

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/vicpinky_ws/install/setup.bash"
source robot/ros_ws/install/setup.bash
export ROS_DOMAIN_ID=156
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ROS_LOCALHOST_ONLY
ros2 launch farm_bringup harvest.launch.py \
  project_root:="$PWD" mode:=real tag_correction:=true
```

- OFF: 마지막 옵션을 `tag_correction:=false`로 변경.
- OFF에서도 태그 검출 비교 기록: `tag_correction:=false tag_camera:=true`.
- 외부 캡처를 이미 실행한 경우: `tag_camera:=false capture_directory:=/실제/현재/캡처폴더`.
- RViz는 예찰과 동일하게 별도 모니터링 실행이다. 초기 위치는 실제 로봇 위치에 맞게 설정한다. 임의 초기 위치를 자동 주입하지 않는다.
- launch 후 `/harvest_01/harvest_task`에 목표를 전달한다. 임의 좌표를 시작 시 자동 전송하지 않는다.

## 자동 연결과 종료

실물 환경 기본 파일은 `robot/config/environments/harvest_real.yaml`이다. 10/07 실험 지도 원본과 A 시험 경로를 `maps/harvest_field_20261007`에 별도로 보존했다. 예찰용 `maps/many_farm`은 수정하지 않았다. 태그 등록 파일의 지도 SHA-256과 동일함을 검사했다. 실제 로봇에서 새 Git 실행기로 주행 검증했다는 의미는 아니다.

카메라 세션마다 `runs/harvest_tag/<고유세션>`을 만든다. 성공 실행본이 그 아래 만든 현재 `settings.json`/`detections.jsonl`을 찾아 어댑터에 전달한다. 사용자가 매번 폴더를 복사하지 않는다. 이전 실행 폴더를 선택하지 않는다.

- `capture.log`: 카메라/검출 로그.
- `correction.log`: 태그 보정 노드 시작·요청 로그.
- `session.json`: 실제 캡처 경로와 자식 종료 코드.
- 캡처 하위 `amcl_tag_*/events.jsonl`: 보정 요청과 후속 AMCL 관측.

캡처/어댑터 오류는 `TAG_SESSION_ERROR`로 표시하고 해당 자식만 정리한다. Nav2/미션에 취소를 보내지 않는다. 보정 ON 옵션과 실제 보정 요청 발생은 구분한다. 오류가 발생한 주행을 ON 효과 실험으로 집계하지 않는다.

카메라의 전체 PNG 기록 요청은 자동으로 켜지 않는다. 검출 로그와 기존 캡처 자체의 진단 이미지는 저장되지만, 주행마다 전체 영상 저장을 보장하지 않는다. 이전 PNG 저장 큐가 주행/검출을 방해하는 경로를 추가하지 않았다.

Ctrl+C 시 태그 어댑터를 종료하고 기존 캡처 관리자가 카메라→검출→rectify 순서로 정리한다. 본 실행이 만든 프로세스 그룹만 종료한다. Nav2/미션 종료는 기존 launch 및 미션 취소 처리를 따른다.

## 검증과 제한

- 태그 패키지 계약 시험 30개 통과: 자동/외부 캡처, ON/OFF, 실물 장치 선택, 이중 캡처 거절, 현재 세션 폴더 선택, DDS 환경 분리, 자기 자식만 종료, 지도/모델/경로/goal checker 일치 등.
- Python 컴파일 검사. 10→13 경로 계산 및 14번 제외 확인. 실험 지도 YAML/PGM 원본 SHA-256 일치.
- ROS가 없는 환경에서 수행했다. colcon 빌드, 실제 ROS launch/DDS, 카메라 하드웨어, 실물 주행은 아직 미검증이다.
- 실물 접근은 Route Server+FollowPath, 작업·출구 구간도 그래프 Dijkstra+FollowPath를 사용한다. 아래 30개 검사는 이전 통합 시점 기록이며 두 단계 변경 검증은 별도 문서를 따른다.


## 2026-10-08 실행 전 검사와 현재 제한

소스 동기화·빌드 후 로봇에서 프로젝트 overlay를 source하고 실행한다. 이 검사는 장치를 열거나 로봇을 움직이지 않는다.

```bash
cd /home/vic/vmany/main/farm_project
source /opt/ros/jazzy/setup.bash
source /home/vic/vicpinky_ws/install/setup.bash
source robot/ros_ws/install/setup.bash
python3 robot/tools/tag_camera/check_runtime.py --ros
```

FAIL이 있으면 launch 전에 해당 설치·소스·설정을 확인한다. PASS는 실물 주행 합격이 아니다.
RViz를 먼저 준비하고 launch 후 실제 위치·방향으로 `/harvest_01/initialpose`를 지정한다.
현재 Nav2 설정에서는 global costmap이 TF를 60초 기다리다 실패할 수 있다.
이미 활성화 실패한 실행은 초기 위치만 늦게 지정해도 전체 lifecycle이 자동 재시작되지 않는다.
해당 launch를 정상 종료하고 다시 시작해 초기 위치를 지정한 뒤 아래 상태를 확인한다.
임의 좌표를 자동 주입하거나 미션의 시작 거리 검사를 완화하지 않는다.

```bash
for node in amcl controller_server planner_server bt_navigator route_server; do
  printf '\n%s\n' "$node"
  timeout 5s ros2 lifecycle get "/harvest_01/$node"
done
```

모두 active이고 실제 지도/로봇 위치가 일치한 뒤 기존 HarvestTask 절차를 사용한다.
이번 수정은 Goal을 자동 전송하지 않는다. 태그 보정 수식·속도·충돌 검사는 유지한다.
미션 최종 도착 기준 5cm/3도는 그대로이고 Nav2 종료 기준만 4cm/2.5도로 좁혔다.
이는 공통 주행 사전 검사의 엄격 부등식에 맞춘 것으로 실물 도달 성능은 재검증해야 한다.

카메라 종료의 detector/rectify -11은 아직 원인이 확인되지 않았다.
이번 수정은 그 실패를 상위 세션에서도 실패로 보고하며, 충돌 자체를 해결한 것으로 기록하지 않는다.
상세 검토와 검사 범위는 `docs/changes/APRILTAG_RUNTIME_REVIEW_20261008.md`에 있다.

## 2026-10-09 현재 실물 설정 갱신

앞선 시험 그래프/ComputeRoute 진입 설명은 현재 실물 설정에서는 이 절로 대체한다. 예찰과 같은 maps/many_farm의 지도·전체 그래프와 map_id=many_farm_v1을 사용한다. approach_planner=graph로 진입·작업 모두 공통 Dijkstra→FollowPath다. route_server는 실행하지 않으며 lifecycle 확인 대상은 amcl/controller_server/planner_server/bt_navigator 네 개다. 11번 단계 도착 정지 확인은 유지한다.

14번 목표는 x=1.188,y=-4.02이며 코드에 직접 입력하지 말고 현재 그래프에서 생성한다. 아래 첫 명령은 JSON 생성만, 두 번째 action 명령은 실제 이동이다. 로봇 빌드/설치 검사와 실제 초기 위치·활성화를 확인한 후 보낸다.

```bash
cd /home/vic/vmany/main/farm_project
goal=$(python3 robot/tools/tag_camera/harvest_graph_goal.py --node 14 --heading-from 13) &&
ros2 action send_goal /harvest_01/harvest_task farm_interfaces/action/HarvestTask "$goal" --feedback
```

예전 해시형map_id·13번 목표를 재사용하지 않는다. 단위검사와 실제14번 주행은 구분한다. 상세: docs/changes/HARVEST_SHARED_MAP_20261009.md.
