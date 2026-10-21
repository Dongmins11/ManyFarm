## 실제 실행 도구 연결 검사 준비 — 2026-10-21
사용자 PC에서 v4의 실제 ROS 9개 검사가 통과했다. 후진/재진입 Spin/전진 복귀와 충돌 전달 차단 및 정상 종료가 확인되었다. 모델 odom이며 실물·전체 실행 도구 E2E는 아니다.
실제 arc_trial.py의 릴레이·watchdog와 restore_sequence.main 호출 경계를 추가 검사한다. 벽 이후 retreat 선택, 단계별 plan/execute 명령, 기록 변경·잘못된 cycle·실패·정지 미확인 시 다음 요청 차단을 확인한다. 하위 프로세스 응답을 대역으로 주입하는 순서 검사와 실제 ROS를 구분한다.
arc_trial.py의 기존 속도 전달 검사에 6축 유한성 검사를 추가한다. 사용하지 않는 축의 NaN도 0 출력 후 차단한다. 기존 공통 Navigator/Nav2Client/PoseProvider/MotionMonitor/SpinClient와 충돌/속도/정지 기준은 유지한다.
새 PC 검사에서는 복사한 모듈 함수 대신 후보 arc_trial.py를 별도 프로세스로 실행한다. 새 departure plan/execute로 세션·map/odom 기준을 기록한 후 벽 종료 자세 fixture, retreat plan/execute, align plan/execute, return plan/execute 및 장애물 plan 거절의 9항목을 요청한다. 기존 v4 C++ 소스가 동일할 때만 통과한 독립 설치본을 재사용한다.
범위 제한: 검사 노드가 모의 odom/TF와 이상 명령 적분을 제공한다. velocity_smoother 노드는 timeout 파라미터 계약 대역이며 실제 smoother/드라이버 시험이 아니다. wall 단계와 arc_isolated 감독 프로세스는 이번 ROS 검사에서 실행하지 않는다. 순서 관리 도구의 프로세스 경계는 오프라인으로 검사한다. 따라서 전체 복귀 E2E/실물 검증 완료로 표시하지 않는다.
직접 수행한 검증은 패키지 OFFLINE_VERIFICATION.json 참조. 새 실제 runtime ROS 검사는 사용자 PC에서 수행해야 하며 이 환경에는 ROS가 없다. 설치본/사용자 Git 소스 적용·로봇 접속·커밋 없음. 모든 산출물은 Downloads 하위. 실물 실행 래퍼의 차단은 유지한다.
