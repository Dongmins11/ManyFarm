# 공통 운송 후방 접근 경로 제한 — 2026-11-01

## 승인과 변경
사용자 “수확로봇 뒤로 붙을수있는 경로를 탐색하게 바꿔 실물도 어차피 그렇게해야돼” 명시 승인. 기준 main c40a036 및 기존 미커밋 변경 보존.

- farm_navigation/route.py: 선택적 goal_yaw/heading_tolerance를 추가. 목표 방향과 일치하는 도착 엣지만 허용하고, 연결된 직선 접근 통로의 역방향 엣지 및 목표 너머를 통과하는 전체 엣지 탐색을 제외한다. 도착 엣지는 목표까지 부분 경로로만 사용한다. 후보가 없으면 거절하며 일반 경로로 대체하지 않는다. 기존 blocked_nodes/blocked_edges 제한 유지.
- transport_robot/navigation_adapter.py: rear_approach=True일 때 위 경로 조건을 사용한다. navigate_to_pose 방식은 방향 보장이 불가하므로 명시적으로 거절. 그 외 운송 이동은 기존 동작 유지.
- transport_robot/harvest_approach.py: 수확물 인계 접근에 rear_approach=True 지정. 실물·시뮬 같은 호출 경로. 마커 전환, 취소·정지, 도킹 거리/허용각은 변경 없음.
- 목표 yaw는 뒤쪽에서 수확로봇을 향하는 접근 방향이라는 기존 인계 입력 계약을 사용한다. 지도 경로가 없거나 입력 방향이 잘못되면 자동으로 반대편 접근을 허용하지 않는다.

## 검증
- 공통 후방 접근/기존 navigation 및 실제 농장 SEC01~16 경로 검사 총33개 통과.
- SEC02 실패 목표 (-4.045,8.414899), yaw+90° 그대로 사용. 이전 경로는 북쪽 Y11.5→10.7→목표. 수정 경로는 다른 통로 X=-1.045로 남쪽 Y0까지 내려온 후 X=-4.045에서 북쪽 Y1.3→6→목표로 접근. 수확 위치 Y9.39를 먼저 통과하지 않음.
- 분할 엣지, 경로 없음, 목표를 지나쳐 돌아오는 우회, 기존 통행 제한, 작은 yaw 차이 검사 포함. 모듈 컴파일과 diff 공백 검사 통과.
- 확장 실행한 기존 traffic 검사21개는 모의 Clock의 ros_time_is_active 누락으로 setup 실패. 이번 경로 변경과 별개이며 수정하지 않음.
- 원본/수정 경로: sim/runs/rear_approach_fix_20261101/SEC02_routes.json. 설치 파일 해시·이전 파일 백업: 같은 폴더 installed.json 및 *.before.

## 적용과 시험
Python 공통3개 파일을 설치 경로에 원자 교체했다. 실행 중8차는 이미 이전 모듈을 로드했으므로 변경 적용을 위해 정상 종료 요청. operator_interruption.json에 로봇 신규 고장이 아닌 수정 적용 중단으로 기록. 캠페인 감독기는 유지하여 SEC02를 새 프로세스로 재시작한다. SEC01 성공과 기존 로그 보존.

실물 주행과 수정 후 도킹 E2E 성공은 아직 검증하지 않았다. Nav2가 접근 중 충돌을 놓친 비용지도/차체 범위 문제는 이 경로 수정과 별도이며 충돌 검사를 완화하지 않았다.

미커밋·미푸시. 되돌릴 때는 이번3개 소스의 후방 접근 추가분과 설치 백업만 복원하며 기존 미커밋 변경을 덮어쓰지 않는다.


### 2026-11-01 — 후방 접근 옵션의 제어권 래퍼 전달 누락 수정

9~14차 6회 모두 ExclusiveNavigator.navigate() got an unexpected keyword argument rear_approach로 실패. 이전 공통 후방 접근 수정의 호출 경로 검증 누락으로 발생한 회귀다. farm_docking/clients.py의 ExclusiveNavigator.navigate가 키워드 옵션을 내부 Navigator에 전달하도록 수정. acquire/try/finally/release 순서와 기존 일반 호출 보존. 사용자의 기존 실물·시뮬 공통 후방 접근 수정 승인 범위 내 보완.

sim/tests/test_pickup_navigation_chain.py는 실제 HarvestApproach→ExclusiveNavigator→TransportNavigator→RouteGraph 호출을 연결하여 경로 계산까지 실행하고 ROS 이동 직전에 종료한다. 전달 성공/경로 오류 시 lease 해제/일반 호출 포함, 후방 경로 검사와 합계26개 PASS. 설치 clients.py 원자 교체 및 설치된 시그니처 확인. 실제 도킹 성공은 아직 확인하지 않음. 15차도 구버전이 로드돼 적용 목적으로 종료했고 operator_interruption.json으로 신규 로봇 고장과 구분. 캠페인 감독기 유지, SEC01 완료 보존. 설치 백업·해시 sim/runs/rear_approach_fix_20261101. 미커밋·미푸시.
