# 복귀 공통 gate 및 격리 ROS 실행 검사


## 복귀 플러그인 격리 ROS 검사 준비 — 2026-10-21

사용자 PC에서 복귀 기반 farm_arc_controller 빌드 및 CTest 2개가 통과했다. 실제 동적 로딩과 FollowPath 실행은 아직 검증 전이다.
기존 CommandGate에 direction 인자를 추가한다. 기본 reverse_left의 범위와 호출은 유지하며, 명시적인 forward_right에서만 속도 부호를 대칭으로 검사한다. 속도 상한, 시간 초과, 충돌 시 차단, 종료 차단은 유지한다.
검사 도구는 PC 전용 domain 95 / localhost / 고유 namespace에서 실제 controller_server와 공통 gate를 사용한다. TF와 odom은 이상 평면 모델이며 모터 속도 발행은 없다. 기존 후진 좌회전, 역경로 전진 우회전, Goal 취소 후 0 출력, 잘못된 경로 거절과 종료를 검사한다. 장애물 충돌 실험 및 하드웨어 성능을 입증하는 검사는 아니다.
벽 정렬 설정과 제어기, 곡선 충돌검사 및 주행 설치본은 변경하지 않는다. 복귀 기준 저장, 벽 이탈/재진입 실행, 전체 미션 연결은 후속 작업이다. 커밋은 사용자가 VS Code에서 진행한다.
