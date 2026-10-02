# 이 패키지의 사용자 합의

- 기존 역할 이름을 유지한다: ScoutNode, ScoutMission, ScoutCommunication, ScoutStateController, Navigator.
- Python snake_case 및 `_` 멤버 스타일을 유지한다. m_ 접두사나 PascalCase 메서드로 일괄 변경하지 않는다.
- Node는 초기화·연결, Mission은 작업 데이터·수명, StateController는 상태 전환·공통 중단, State는 단계별 행동·완료 판단을 담당한다.
- State의 enter는 요청 후 반환한다. 큰 Mission.execute 반복문이나 State.execute에서 완료까지 기다리는 구조로 되돌리지 않는다.
- 실제 I/O 대기는 어댑터의 작업 스레드에서 수행할 수 있다. 완료는 Controller 큐를 통해 해당 State에 전달하고 전환한다.
- 정상 전환과 장치 중단을 구분한다. exit마다 무조건 주행을 취소하지 않는다.
- 취소/실패 후 이전 작업·상태의 늦은 응답을 차단한다. 중단 확인 전에 새 작업을 시작하지 않는다.
- 상태명은 Confluence 예찰 State 문서를 따른다. 현재 정지 관측·촬영 지점 Segment 의미는 유지하며 문서와의 차이를 명시한다.
- 기존 계산 알고리즘·ROS 메시지·launch·폴더 위치는 요청 범위를 넘어 변경하지 않는다.
- 도킹 액션·장치 연결 없이 도킹 성공을 만들어내지 않는다.
- 함수 매개변수와 반환값에 타입을 표시하고, 단위·좌표계·None 시점 및 호출 흐름을 한국어로 설명한다.
- 새 데모 실행기를 추가하지 않는다. 검증용 테스트의 가짜 장치와 운영 코드를 분리한다.
