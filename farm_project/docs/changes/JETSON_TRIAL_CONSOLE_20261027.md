## 2026-10-27 배출 시험 모드 PC 구현 — 로봇 미배포

사용자 “미니관제에서 배출 시험 모드 켜고 끌 수 있게 … transfer_active만 … PC 수정/검증” 승인.
기존 JetsonConnection 발행기가 시험 활성 시 transfer_active만 true로 보낸다. 실제 정지/관측0.2초/10Hz/원본stamp는 유지.
Pinky /harvest_01/transfer_test_mode/set_enabled(SetBool), enabled(Bool 상태10Hz)를 미니관제 SSH ROS 클라이언트에 연결.
초기값 off, 영속 저장 없음. 실제 운영 작업 중 on 거절, 운영 작업이 시작되면 시험값 자동 해제.
주행/인계 작업 수락·FSM·완료·제어·적재량·저널·ControlState IDL 변경 없음.
모드만으로 배출을 요청하지 않는다. 별도 Discharge 버튼 사용. 웹 연결 종료만으로 모드는 해제되지 않음.
PC37개(격리 domain231/loopback 포함) 및 기존 JS 요약 테스트/문법 검사 통과.
로그 /tmp/manyfarm_control_v3/transfer_test_check.log. 실제 로봇/Jetson 접속·동작/배포/재시작 없음.
후속 적용 시 harvest_robot 재빌드, 관제 브리지 deny에 시험 토픽/서비스 제외 항목 추가, 사용자 프로세스 전환 필요.
그 후 PC 미니관제 재시작/시험 연결로 사용. 현재 운영 설치본은 새 시험 서비스를 제공하지 않는다.
상세: docs/changes/DISCHARGE_TEST_MODE_PC_20261027.md. commit/push/staging 없음.

## 2026-10-27 미니관제 팔 상태·수량 요약 추가

사용자 요청으로 static/index.html/app.js/style.css에 준비됨·요청 대기·수확 중·수확 완료·오류/취소와 수확/실패 개수를 표시했다.
ready는 별도 문구로 노출하고 완료는 검증된 최종 Result.success로만 표시한다.
진행 개수는 해당 요청 Feedback, 종료 개수는 최종 Result를 사용한다. 새 요청은 이전 개수를 이어받지 않는다.
수신 만료/연결 종료 시 현재 상태 확인 필요로 표시하며 마지막 수량·결과는 보존한다.
오류 코드/메시지·복구 필요 및 작업 ID도 원문을 펼치지 않고 확인 가능하다.
검증: tests/test_arm_overview.cjs의 준비/수락/진행/수량/성공/실패/복구/단절/거절/새 요청/미확정 시나리오 통과,
JS 문법·git diff --check 통과. 표시 로직만 변경, ROS/서버/프로세스/실물 명령 변경 없음.
웹 새로고침만으로 적용하며 연결 재시작·로봇 재빌드 불필요. commit/push 없음.

## 2026-10-27 미니관제 수확 초안 무반응 수정

사용자 연결 후 초안/수확 버튼 무반응 보고를 조사했다. 실제 PC arm-audit.jsonl에 prepare 송신 및
success=true 응답이 있으며, 최근 snapshot에는 robot/control/runtime만 있고 pose는 없었다.
기존 volatile AMCL 구독을 transient-local reliable depth1로 수정해 정지 중 뒤늦게 연결해도 보존 표본을 받는다.
보존 표본을 최신으로 오인하지 않도록 초안 안내에 원본 header 측정 시각을 표시한다.
static/app.js/index.html/style.css에 버튼 인근 안내와 빈 JSON 오류 설명·초안 예외 표시를 추가했다.
기존 RobotStatus·ControlState·팔 명령·주행 로직 변경 없음. 실제 명령 송신/프로세스 재시작 없음.
PC 단위/격리 ROS33개 통과(9.72초), JS 모의 DOM에서 자세 없음/초안 생성/빈 요청 안내 통과.
로그 /tmp/manyfarm_control_v3/console_pose_check.log, check_console_ui.cjs.
사용자 웹 새로고침→유휴 연결 종료→팔 시험 연결로 새 SSH 클라이언트 적용. 로봇 재빌드 불필요.

# 미니관제 실제 팔 통신 시험 확장 — 2026-10-27

사용자 요청: 이동 없이 미니관제에서 수동 통신 명령 전송·수신 확인·상태/프로세스 정리.
추가 확인: Jetson에 접속할 필요 없이 수신 여부만 확인. Jetson SSH/서비스 관리는 구현하지 않는다.
기준 HEAD48d2d1c 및 기존 미커밋 Jetson 상태 연결/회신 설정/로봇 alias 변경을 보존했다.

변경: robot/tools/trial_console/의 app.py, backend.py, config.json, robot_agent.py,
static/index.html/app.js/style.css, README.md 및 새 arm_agent.py, arm_session.py, process_agent.py, tests/.
기존 로봇 주행·인계 패키지/설정·배포본·별칭은 이번 작업에서 변경하지 않았다.

구조: 기존 PC HTTP 서버→지속 SSH→Pinky ROS 시험 클라이언트→기존 팔 Zenoh→Jetson.
Pinky에서 farm_interfaces/jetson_harvest_interfaces와 기존 validate_task/validate_counts,
RuntimeTracker를 재사용한다. 수확은 내부 /arm/harvest_task Action에만 보내며 차체 이동 Goal은 보내지 않는다.
ROS client 실행·명령은 웹 사용자 버튼으로만 시작한다. 개발 중에는 실물 접속/명령을 하지 않았다.

기능: 수확/배출, prepare/stop, 자기 Goal 취소, GetOperation/Recover,
RuntimeStatus/ControlState/RobotStatus/AMCL 수신, 송신/수락/Feedback/terminal/서비스 응답 로그,
그룹별 프로세스 조회/SIGINT 종료 및 시험 연결 정리. 기존 더미/복구 UI는 유지.
명령 요청/수락과 실제 성공을 구분한다. 서비스 success=false도 작업 실패로 표시하도록 기존 큐 결과 판정을 수정했다.
Goal/result ID와 ROS 상태를 대조하며 부분 수량을 원문으로 보존한다.

ControlState·가짜 비상정지·초기위치·속도 명령은 발행하지 않는다. 팔 stop과 프로세스 종료도 구분한다.
Pinky 서버의 정상 ControlState가 필요하며 기존 비상정지 미확정 문제는 남아 있다.
수동 팔 수확 결과는 운영 Pinky 적재량/관제 대기열에 자동 반영하지 않는다.
서버 발견은 실제 수신 증거가 아니고, Jetson 응답을 받았을 때만 해당 단계가 수신됐다고 표시한다.
Jetson 내부 로깅/물리 동작 검증으로 확대하지 않는다.

검증: 단위7개(명령 확인, 고정 프로세스 그룹, 목록 변경/PID 재사용 방지, 요청과 수신 구분, 결과 ID 불일치),
격리 ROS3개(Action 수락/Feedback/취소/부분 결과, 서비스/배출 거절, 미준비 미전송/ControlState 미발행) 통과.
Python 문법·JS 문법·git diff --check. 별도 모의 서버8092에서 화면 레이아웃/명령 확인/요청 표시/결과 상세/프로세스 조회 확인.
모바일 폭과 결과 상세가 자동 갱신 때 닫히는 UI 문제를 수정했다.
테스트 로그: /tmp/manyfarm_jetson_pc_20261027/console_ros.log, console_tests.log (임시).
실제8091 서버 재기동·로봇 접속·Jetson 명령·운영 프로세스 종료·실물 시험은 하지 않았다.

사용자가 기존 미니관제 터미널을 종료한 뒤 python3 robot/tools/trial_console/app.py로 다시 실행하고 브라우저 새로고침해야 한다.
로봇에 추가 파일 설치는 필요 없으며 웹 연결 시 현재 PC의 agent 코드를 SSH로 전달한다.
실행 순서와 상세 제한은 robot/tools/trial_console/README.md 참고.
원복은 이번 콘솔 파일 변경만 대조한다. 기존 로봇 코드·문서 미커밋 변경과 실제 저널은 보존한다.
Git staging/commit/push 없음.
