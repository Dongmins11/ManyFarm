# harvest_robot

<!-- HARVEST_CURRENT_20261009 -->
> **현재 실물 기준 — 2026-10-09**
> - 공용 지도 `maps/many_farm`, map_id `many_farm_v1`.
> - `route_then_follow` + `approach_planner=graph`: 진입·작업 모두 그래프 다익스트라 → FollowPath. Route Server는 실행하지 않는다.
> - 11번 정밀 도착·정지 후 작업 목표로 이동한다. lifecycle 확인 대상은 amcl, controller_server, planner_server, bt_navigator다.
> - 사용자 로봇 빌드·설치 검사 PASS. 14번 성공 뒤 반복 시험에서 작업 끝점 회전·충돌 예측 중단을 확인했다. 진입과 작업 끝점 문제를 구분한다.
> - 태그 보정 효과·실측 정확도 검증 완료가 아니다. 카메라 종료 -11과 AMCL 시각 경고도 남아 있다.
> - 진입 HarvestApproach는 사용자 실물 개선 확인. 작업점 전용 HarvestWork를 추가한 이번 변경은 오프라인 검증 완료·실물 미검증이며 이탈은 RPP를 유지한다.
> - 아래 날짜별 기록의 미실행·이전 구조 설명은 작성 당시 상태이며 현재 실행 안내는 이 기준을 따른다.


수확 HarvestTask를 받아 환경별 이동과 선택적 팔 작업을 연결하는 ROS 패키지다. 예찰 코드를 복사하거나 변경하지 않고 공통 farm_navigation을 사용한다.

## 이동 모드

- `graph_only`: 기존 그래프 Dijkstra → FollowPath. 시뮬 등 기존 환경 동작 유지.
- `route_then_follow`: 실물 기본. 화단 진입은 ComputeRoute → FollowPath, 작업·출구 이동은 RouteGraph Dijkstra → Path → FollowPath. scout_new가 사용하는 공통 구현을 재사용한다.
- `route_then_pose`: 이전 환경 호환용 명시적 선택. 작업·출구는 NavigateToPose. 현재 실물 기본 설정에서는 선택하지 않는다.

`route_then_follow`와 `route_then_pose`는 등록된 section_id가 필요하다. 화단 진입, 같은 구역 연속 작업, 구역 변경 시 이탈, 재시작 후 재진입 순서를 유지한다. Window ID에서 구역을 추측하지 않는다.

## 경로와 보정

목표 XY·yaw와 기준 graph를 그대로 사용한다. 그래프 엣지 중간 목표를 지원하고 허용 거리 밖/연결되지 않은 목표는 실패한다. FollowPath 실패를 NavigateToPose로 대체하지 않는다. 차체 옆면–벽 명목 20cm 기준의 기존 route 좌표, 지도, 카메라 외부 파라미터는 변경하지 않는다.

AprilTag는 기존 TagControl을 통해 미션 동안 활성화되고 성공·실패·취소 때 종료된다. 태그가 없다는 이유만으로 이동을 취소하지 않는다. 주행 취소는 기존 자기 Goal 종료·정지 확인을 따른다. 기존 팔 정책과 메시지 계약은 유지한다.

새 C++ planner/BT/±10cm corridor 설정은 사용하지 않는다. 기존 max_start_distance_m 등의 그래프 대응 허용값은 바꾸지 않았다.

## 검증

```bash
python3 -m unittest discover -s robot/ros_ws/src/harvest_robot/test -v
python3 -m unittest discover -s robot/ros_ws/src/farm_tag_localization/test -v
python3 robot/tools/tag_camera/check_runtime.py
```

프로젝트 루트에서 실행한다. 이번 41+44개 오프라인 검사 PASS. 실제 수확 초기화 클래스·공통 Navigator/RouteGraph/path_builder/Nav2Client를 사용하고 ROS 통신·TF·물리 이동은 대역으로 검사했다. ROS 빌드·설치 Action 통신·실제 주행을 검증한 것은 아니다.

상세 변경·검증·복원: `docs/changes/HARVEST_FOLLOW_PATH_20261008.md`.

## 2026-10-09 현재 실물 설정 갱신

앞선 시험 그래프/ComputeRoute 진입 설명은 현재 실물 설정에서는 이 절로 대체한다. 예찰과 같은 maps/many_farm의 지도·전체 그래프와 map_id=many_farm_v1을 사용한다. approach_planner=graph로 진입·작업 모두 공통 Dijkstra→FollowPath다. route_server는 실행하지 않으며 lifecycle 확인 대상은 amcl/controller_server/planner_server/bt_navigator 네 개다. 11번 단계 도착 정지 확인은 유지한다.

14번 목표는 x=1.188,y=-4.02이며 코드에 직접 입력하지 말고 현재 그래프에서 생성한다. 아래 첫 명령은 JSON 생성만, 두 번째 action 명령은 실제 이동이다. 로봇 빌드/설치 검사와 실제 초기 위치·활성화를 확인한 후 보낸다.

```bash
cd /home/vic/vmany/main/farm_project
goal=$(python3 robot/tools/tag_camera/harvest_graph_goal.py --node 14 --heading-from 13) &&
ros2 action send_goal /harvest_01/harvest_task farm_interfaces/action/HarvestTask "$goal" --feedback
```

예전 해시형map_id·13번 목표를 재사용하지 않는다. 단위검사와 실제14번 주행은 구분한다. 상세: docs/changes/HARVEST_SHARED_MAP_20261009.md.

### 실물 진입 전용 제어기

`harvest_real.json`의 `approach_controller_id`는 SECTION_APPROACH용 FollowPath 제어기를 선택한다.
실물 진입은 `HarvestApproach`, 작업은 `work_controller_id=HarvestWork`, 이탈은 기존 `RPP`다. 키가 없는 기존 환경과 graph_only 동작은 유지한다.
새 프로파일이 controller_server에 없으면 기존 Nav2Client의 준비 검사에서 Goal 전송 전에 실패한다.
진입 제어기는 0.4m 가상 곡률 참조점을 마지막 선분 방향으로 연장한다. 실제 목표와 정밀 도착·정지 조건은 유지한다.
정적 검사 PASS는 실물 검증 완료가 아니다. 설정 적용 후 controller_server 재시작이 필요하다.

### 2026-10-09 작업점 제어기 적용

현재 선택은 진입 HarvestApproach / 작업 HarvestWork / 이탈 RPP다. 각 작업 좌표의 위치·yaw·정지 확인을 유지한다. 코드와 설정 복사 후 harvest_robot 빌드, check_runtime.py --ros, 수확 launch 재시작이 필요하다.

```bash
ros2 param get /harvest_01/controller_server controller_plugins
ros2 param get /harvest_01/controller_server HarvestWork.use_fixed_curvature_lookahead
ros2 param get /harvest_01/controller_server HarvestWork.curvature_lookahead_dist
ros2 param get /harvest_01/controller_server HarvestWork.interpolate_curvature_after_goal
```

HarvestWork 등록 및 True / 0.4 / True를 확인한다. 상세·미검증 범위는 docs/changes/HARVEST_WORK_CONTROL_20261009.md에 기록했다.
