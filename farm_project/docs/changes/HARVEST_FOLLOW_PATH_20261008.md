# 수확 작업·출구 FollowPath 전환 — 2026-10-08

## 기준과 승인

사용자가 scout_new 기준으로 재확인을 요청했고, 비교 결과에 따라 “지금 확인한 사항대로 코드 다시 수정”을 승인했다. 이전 harvest_corridor_fix_20261008.tar.gz는 PC/로봇에 적용하지 않은 상태다. 이번 변경은 그 패치 이전 runtime 검토·ComputeRoute 메시지 호환 수정 적용본에서 시작한다. aa18b2c 원격 조회본과 사용자 적용 기록을 기준으로 하며 원격에는 여전히 과거 충돌 표시가 있어 원격 파일로 덮어쓰지 않는다.

## 변경 대상과 실행

- `robot/config/harvest/harvest_real.json`: movement_mode만 route_then_pose → route_then_follow.
- `harvest_robot/node.py`: 단계별 모드 선택에 새 모드 추가. 진입 RouteServerPlanner 유지. 작업 Navigator는 기존 settings(mode=follow_path)와 같은 RouteGraph 객체를 받는다.
- `harvest_robot/contract.py`: 새 모드에도 등록된 section_id 요구.
- `harvest_robot/staged_navigation.py`: 설정 누락 오류 문구를 두 모드에 맞춤. 단계 순서/취소 로직 변경 없음.
- `farm_bringup/launch/harvest.launch.py`: 새 모드에서도 필요한 Route Server/lifecycle을 한 번 실행. navigation=false일 때 중복 실행하지 않음.
- 수확·태그 launch 검사, README·실행 가이드·상태/결정/변경 기록 갱신.

진입은 ComputeRoute→FollowPath, 작업/출구는 RouteGraph.plan(Dijkstra)→build_path→Nav2Client.execute(FollowPath)이다. Nav2가 받은 목표점만으로 전역 격자 경로를 새로 만드는 NavigateToPose 분기를 실물 작업 모드에서 사용하지 않는다. 기존 RouteGraph의 원본 좌표와 방향 엣지/중간 목표 처리를 그대로 쓴다.

새 C++ planner, 전용 BT, ±10cm corridor 및 추종 감시를 추가하지 않는다. 기존 max_start_distance_m=0.1/max_goal_distance_m=0.02는 그래프 대응 허용값이며 이번에 만든 주행 이탈 한계가 아니다. 예찰 소스, farm_navigation 알고리즘, footprint, Nav2 설정, 지도/graph/태그 자산, 팔 정책/메시지 계약은 변경하지 않았다. 명목 옆면–벽 20cm의 기존 배치를 유지하며 실제 20cm 유지 정확도를 검증했다고 주장하지 않는다.

## 이번 직접 검사

- 수확 41개 PASS(기존31+신규10), AprilTag 44개 PASS(기존42+신규2).
- 신규 검사는 운영 HarvestNode 클래스 본문을 그대로 실행하고 공통 Navigator/RouteGraph/path_builder/Nav2Client 구현을 실제로 사용한다. Node·ROS 메시지/Action 응답·TF·odom·Route Server I/O는 대역이다. 운영 알고리즘을 시험 코드로 복제하지 않았다.
- 실물 모드의 진입/작업 모두 FollowPath Action Goal 전송, 경로의 모든 점이 기존 직선 위에 있음, 최종 XY/yaw 보존, RPP 선택, 작업 계획 기록/정지 확인 결과를 검사했다.
- 엣지 중간 목표와 같은 구역 연속 이동, 구역 변경 시 출구→진입→작업 순서, 그래프 밖 목표 거절, 실패 시 NavigateToPose fallback 없음, 취소/태그 begin-end, 미등록 section 거절, 명시적 legacy pose 및 graph_only 보존을 검사했다.
- 새 모드 Route Server 한 번 생성, 외부 navigation 시 중복 없음 검사.
- 기존 check_runtime.py: Python35개 구문·지도 해시·보정 자산·route 파라미터·카메라 plan PASS. 대상 diff 공백 검사, 보호 파일 바이트 비교 PASS.
- 시험 대역 Path를 함수로 선언해 타입 주석 평가에 실패한 초기 시험 오류는 대역을 클래스로 수정했다. 최종 모든 검사는 통과했다.

## 한계와 다음 확인

이 환경에는 ROS가 없어 colcon 빌드, 실제 ROS Action 통신, Nav2 lifecycle, 카메라 및 실물 주행을 실행하지 않았다. 오프라인 성공을 실물 성공으로 바꾸어 보고하지 않는다. 로봇 적용 후 수확/bringup 패키지 빌드, 설치 사전 검사, 재시작 후 로그의 작업 mode=follow_path 및 route 계획을 확인해야 한다. 물리 흔들림·AMCL initialpose 시간 보상 경고·카메라 종료 -11은 별도 미해결이다. FollowPath도 추정 위치와 컨트롤러를 사용하므로 경로 지정만으로 실제 이탈 0을 보장하지 않는다.

## 적용과 복원

동봉 apply_follow.py는 기존 SHA256을 모두 비교한 후 백업·적용한다. 사용자가 미적용이라고 한 corridor 코드가 발견되면 자동으로 제거하지 않고 중단한다. 문서 지정 절만 추가하며 다른 문서 내용은 보존한다. 이번 변경 파일만 로봇 동기화 후 harvest_robot와 farm_bringup을 빌드한다. commit/push는 수행하지 않는다. 복원은 runs/review_backups/follow_*의 manifest에 있는 이번 원본 파일만 사용한다. 다른 미커밋 변경이나 원본 graph를 reset하지 않는다.
