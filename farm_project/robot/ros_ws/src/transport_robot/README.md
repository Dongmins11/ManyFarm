# transport_robot

실물 운송 1~5단계 구현. 기존 farm_navigation과 기종별 devices launch를 사용한다.

- transport_node: 설정·ROS 자원 조립
- transport_communication: Goal 예약·거절·취소·응답
- transport_mission: 작업 context·영구 기록
- transport_state_controller / states: 비동기 행동 요청·완료·중단
- configuration / route_cli: 기종·목적지 검증과 경로 미리보기/실행
- docking_port / farm_docking: 마커·라이다 정밀 도킹 및 단일 속도 출력 연결

실물 ReturnToStation은 도킹 없이는 거절한다. 시뮬은 환경 파일의
`station_return_mode: navigation_only`를 명시하면 실제 경로 주행·도착 오차·정지를
확인한 뒤 마커 단계만 생략한다. 이 선택은 pickup/unload에 적용되지 않는다.
`docked=true`는 기존 sim ReturnToStation과 같은 가상 주차 완료 의미다.

internal/check_route는 이동만 검증하며 인계/하역 성공을 의미하지 않는다.
업무 FSM과 도킹 코드는 feature_dongmin `9686aca`에서 선별 통합했다.
가상 센서·바구니 정렬 판정·전체 관제/교통 연결은 별도 구현 단계다.
운송 교통 허가가 연결되기 전 traffic.enabled=true는 시작 시 거절한다.
통합 현황: sim/docs/changes/TRANSPORT_SIM_IMPLEMENTATION_20261027.md.
