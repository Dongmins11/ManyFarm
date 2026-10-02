# 프로젝트 구현 합의

- control/robot/sim 및 기존 패키지 역할을 유지한다. 런치 mode=sim/real로 환경별 설정과 장치를 선택하고 동일한 로봇 로직을 실행한다.
- 좌표·노드·엣지·베드 데이터를 코드에 고정하지 않는다. JSON/YAML/GeoJSON을 project_root 기준으로 로드한다. 양 환경의 베드는 직선이다.
- Node/Mission/Communication/StateController/States를 유지한다. Python _ 멤버와 snake_case를 사용한다. m_ 컨벤션으로 바꾸지 않는다.
- 각 State는 enter에서 행동을 요청하고 반환한다. 완료 콜백에서 전환을 요청하며 Controller가 exit/enter를 관리한다.
- 로봇별 관제 통신과 작업 의미는 각 로봇에 둔다. farm_interfaces는 형식 정의이며 공통 작업 실행기가 아니다.
- farm_navigation은 공통 주행·위치 조회 라이브러리다. ScoutNode 내부 변수나 예찰 도메인에 의존하지 않는다.
- kinematics는 장치가 필요한 경우 재사용한다. 기존 드라이버가 제공하는 odom/바퀴 제어를 중복 계산하지 않는다.
- 경로 계산과 실행은 분리한다. 미니관제 수확 이동은 자체 RouteToPose와 FollowPath였으며 ComputeRoute 사용으로 잘못 기록하지 않는다.
- 교통 제어·AprilTag·도킹은 별도 도입 범위다. 가짜 성공이나 빈 pause/resume 구현을 추가하지 않는다.
- 현재 시뮬 그래프는 베드별 16개 비연결 성분이다. 연결을 임의로 추가하거나 FollowPath 실패를 조용히 목적지 이동으로 대체하지 않는다.
- 실물 SEC_01 설정과 D435 어댑터는 기존 로봇 설정으로 연결했다. 실물 전체 주행 검증은 아직 하지 않았다. farm_real_devices는 기존 TurtleBot3/vicpinky 하드웨어 bringup을 재사용하며 파이캠은 포함하지 않는다. sim/real 설정 선택 지원과 실물 검증 완료를 구분한다.
- 이전 구현은 outputs/navigation_refactor 백업과 docs/NAVIGATION_REFACTOR_HISTORY.md에 기록했다. 실제 예찰 E2E 확인 전 기존 구현과 scout_new를 삭제·최종 교체하지 않는다.
- 코드 주석과 문서는 한국어로 책임·단위·호출 순서를 설명한다. 함수 인자와 반환 타입을 표시한다.

- 실물 지도는 사용자 지정 매니팜 지도다. robot/config/maps/many_farm의 many_farm.yaml/pgm 및 graph.geojson을 사용한다. graph.json은 이전 관제 참조 데이터이며 경로 계산 입력은 graph.geojson이다. 시뮬 지도와 혼용하지 않는다.

- 실물 설정은 robot/config/environments, robots, survey, vision, maps로 나눈다. 장치 설정 원본은 robots/burger/devices.json이며 farm_real_devices/config의 파일은 패키지 설치용 심볼릭 링크다. 중복 원본을 만들지 않는다.
