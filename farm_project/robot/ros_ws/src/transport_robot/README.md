# transport_robot

실물 운송 1~5단계 구현. 기존 farm_navigation과 기종별 devices launch를 사용한다.

- transport_node: 설정·ROS 자원 조립
- transport_communication: Goal 예약·거절·취소·응답
- transport_mission: 작업 context·영구 기록
- transport_state_controller / states: 비동기 행동 요청·완료·중단
- configuration / route_cli: 기종·목적지 검증과 경로 미리보기/실행
- docking_port: 후속 정밀 도킹 연결 경계, 현재 미연결

ReturnToStation은 도킹 없이는 거절한다. internal/check_route는 이동만 검증하며 복귀/하역 성공을 의미하지 않는다. Isaac/sim은 사용자 요청으로 제외했다. 작업본 루트 START_HERE.md에 실행 순서와 미확정 항목을 기록했다.
