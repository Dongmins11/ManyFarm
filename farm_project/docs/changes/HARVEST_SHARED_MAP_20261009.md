# 공용 실물 지도·그래프와 수확 14번 연결 검토

기준일: 2026-10-09 KST. 사용자가 적용한 FollowPath 수정본을 기준으로 검토했다. 예찰 운영 코드는 수정하지 않는다.

## 확인 근거

- [지도·Route Graph 명세, 300cm·21포인트](https://robot3final.atlassian.net/wiki/spaces/3/pages/33914899) 버전2, 2026-10-09.
- [그래프 이동 구조](https://robot3final.atlassian.net/wiki/spaces/3/pages/33194003) 버전2.
- [과거 AprilTag 실행 가이드](https://robot3final.atlassian.net/wiki/spaces/3/pages/32112642) 버전1: 10→13 시험,14 제외였던 이력.
- Git main/feat/apriltag-localization의 scout_real.yaml과 many_farm/graph.geojson은 각각 같은 Git blob이다. 지도 문서의 SHA256과 받은 Git 원본을 대조했다.
- graph SHA256 fc72ffb617c0f756a6eb58477c0e1211dbc3f4cea2ca9855874008b150cfc504
- YAML SHA256 bbe46086336b76b5f11611160803260a91339d87c97709a6ffe5114d8d328fac
- PGM SHA256 a9f852637490aaff50c7115a543e2780a60ecf654747b3e777319251e151949e

## 실제 연결과 변경 이유

scout_new는 robot/config/environments/scout_real.yaml의 route_graph 전체를 RouteGraph에 전달한다. 관측노드4/6/8 선택은 방문 정책이며 그래프에서 수확·운송 엣지를 제거하는 처리가 아니다. kind 표시는 로봇 접근 권한이 아니다. 따라서 수확에도 같은 전체 그래프를 연결한다. 교통 예약·동시 충돌 방지는 이번 기능이 아니다.

기존 수확 지도 YAML/PGM과 공용 지도는 바이트 동일하다. 태그 등록 지도 해시도 일치하여 자산/태그 좌표/장착/캘리브레이션을 이동시키지 않았다. 이전 후보 wall x=1.653과 새 도면 변환상 wall x=1.643의 차이는 독립 재측량으로 해소한 것이 아니다. 새 그래프 적용을 보정 절대 정확도 검증으로 설명하지 않는다.

기존 시험 그래프는10~13만 포함하고 x=1.198,13번 y=-3.289621이었다. 현재 전체 그래프는10~14 x=1.188,12번 y=-1.972,13번 y=-2.672,14번 y=-4.02이다. 지도 원점이 이동한 것이 아니라 그래프 기준이 달라졌다. 과거 목표 좌표를 그대로 재사용하지 않는다.

Confluence는 map_id를 farm_map_v1로 표기하지만 실제 scout_real.yaml은 many_farm_v1이다. 이번 수확은 실행 설정값 many_farm_v1에 맞춘다. 예찰 파일과 Confluence는 수정하지 않았다. 태그 자산의 map_version은 과거 등록 버전 식별자로 보존하며 작업용 map_id와 구분한다. 이전 해시형 map_id 목표는 거절된다.

Confluence 수확선 45.5cm는 중심→측면25.5cm+20cm 명목 설계이다. 문서의 별도25cm 요청 서술을 이번 사용자20cm 기준으로 자동 적용하지 않았다. 로봇 기준 프레임/최외측 실측과 실제 간격은 현장 확인 대상이다.

## 선분 중간 출발

기존 수확 진입은 ComputeRoute 결과의 첫 점과 실제 위치 거리를 검사했다. 실제14:52시험에서도 현재 위치에서10번으로 되돌아가는7.6cm 연결이 있었다. 그래프를 넓히기만 해서는 같은 끝점 문제가 없어졌다고 할 수 없다.

수확 설정에 approach_planner=graph를 명시해 기존 공통 Navigator/RouteGraph를 그대로 재사용한다. 현재위치→허용거리 내 선분 투영→방향 그래프 다익스트라→Path 보간→FollowPath 흐름이다. 새 Dijkstra/직선 우회/NavigateToPose fallback을 만들지 않는다. 최대 시작 대응거리10cm는 유지하므로 그래프에서 멀리 떨어진 임의 위치 합류 기능은 아니다.

harvest.launch.py는 graph 선택 시 불필요한 route_server와 route_lifecycle_manager를 실행하지 않는다. 명시적 또는 기본 route_server 선택의 기존 환경은 기존 동작을 유지한다. 공통 farm_navigation 및 예찰 코드는 바꾸지 않았다. 이번 설정의 확인 대상 lifecycle은 amcl/controller_server/planner_server/bt_navigator 네 개다.

11번 진입 도착·정지 확인 뒤 WINDOW_MOVE를 시작하는 구조는 유지한다. 중간 정지 제거를 완료했다고 주장하지 않는다.

## 검증

- harvest_robot48개, farm_tag_localization46개 PASS. TF/Action I/O 대역과 실제 HarvestNode 본문·공통 경로 계산·Path 생성·클라이언트 연결 검사다. 실제 Nav2 controller 실행이 아니다.
- 21×21=441 노드쌍 및46방향엣지 중간점→11/14=92개 연결 검사.
- 0↔10 중간(.8455,-.02)에서11번 후14번으로 FollowPath 두 요청,0번으로 되돌아가지 않음.
- 10↔11 중간(1.188,-.096)에서10번으로 되돌아가지 않음.
- 그래프 밖 시작 거절, 작업 실패시 pose fallback 없음, 취소·태그 수명 유지.
- 지도/그래프 문서 해시·예찰 참조와 동일, 지도 바이트 유지,14번 Goal을 실제파일에서 생성, 이전 map_id 거절.
- check_runtime.py 오프라인 PASS. ROS 설치본/장치, 새그래프의 실제 주행/회전공간/태그효과, 동시교통, 종료 -11 원인 해결은 미실행/미완료.

## 파일과 적용

환경 harvest_real.yaml, 수확 harvest_real.json, 장치 vicpinky/devices.json, 보정 harvest_real.yaml의 식별/참조를 맞춘다. 수확 node.py와 harvest.launch.py는 선택한 계획기를 연결한다. test_follow_work/test_shared_map/test_launch_contract와 check_runtime 검사를 갱신한다. harvest_graph_goal.py는 실제 그래프에서 JSON만 생성하며 ROS 이동을 실행하지 않는다.

공용 maps/many_farm 및 예찰 설정은 원본 해시 확인 대상으로만 사용하고 덮어쓰지 않는다. 적용본과 비교한 원본이 다르면 적용 도구가 중단한다. 기존 시험 지도는 과거 재현용으로 보존한다. ROS/드라이버/예찰 소스는 패치에 포함하지 않는다.

사용자의 feat/apriltag-localization 브랜치와 FollowPath 수정본에만 적용한다. PC 미커밋 변경은 해시 불일치 시 덮어쓰지 않는다. docs/PROJECT_STATE·DECISIONS·sim/CHANGELOG·REAL_RUNTIME_BUNDLE에는 새 절만 덧붙인다. 원복은 백업manifest에 있는 이번 파일만 복구하고 전체 reset/clean을 하지 않는다.
