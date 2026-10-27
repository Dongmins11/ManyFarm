## 2026-10-27 백업 보관 위치 변경

사용자 요청으로 이번 V3 백업을 PC /home/eunbi/vmany_artifacts/robot_backups/control_state_v3_20261027_184225/before.tar.gz로 이전했다.
SHA256 e7f056489d44f6bae15a777e669bb0ce7a48a6daeb8a9e2586317a268a77feac 일치 및 tar473항목 읽기 검증 후
로봇 /home/vic/vmany-runtime-backups/control_state_v3_20261027_184225의 백업 파일과 빈 디렉터리를 삭제했다.
아래 해당 로봇 백업 경로는 생성 당시 기록이며 복원 시 PC 보관본을 사용한다.
이전부터 있던 다른 백업은 이번 작업에서 삭제하지 않았다. 앞으로 백업은 PC Git 외부에 보관한다.
실행본·프로세스·저널 변경 없음.

## 2026-10-27 후속 — 로봇 ControlState V3 재빌드 완료

사용자 “재빌드해줘” 요청으로 로봇 격리 경로
/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741의 V3 대상7파일만 갱신했다.
설정의 기존 차이는 estop 두 항목뿐임을 확인하고 원본 src/install/config/manifest를
/home/vic/vmany-runtime-backups/control_state_v3_20261027_184225/before.tar.gz에 백업했다.
jetson_harvest_interfaces/harvest_robot 빌드 성공(15.4초). 설치본 6필드/CDR/설정,
PC→로봇7파일 해시 및 설치 Python2모듈 일치 확인. launch/팔 브리지 --check 통과(충돌 PID 없음).
운영 ROS/브리지 기동·종료·이동·초기위치·저널 변경 없음. 기존 alias 경로 유지.
다음 사용자 기동부터 V3 설치본 사용. 실제 Jetson 왕복/팔 동작 검증은 아직 남았다.
로봇 로그 build_control_v3.log, log_control_v3/, manifest_control_v3.json;
PC 증거 /tmp/manyfarm_control_v3/robot_verify.log. 원래 manifest.json은 이전 배치 기록으로 보존.
원복은 관련 프로세스 종료 확인 후 백업에서 필요한 소스·설정·설치본을 대조 복원하며 저널은 복원하지 않는다.
아래 “로봇 미배포”는 이번 재빌드 전 상태다. commit/push/staging 없음.

# ControlState V3 PC 반영 — 2026-10-27

기준 HEAD: 48d2d1c812a968058254ddb2355ee5dfc9b96c68, 기존 미커밋 변경 보존.
사용자 V3 반영 승인 및 0.2초 논의 이후 “그럼 일단 그대로 수정”을 근거로 첨부 계약을 적용했다.
첨부 ZIP의 SHA256SUMS 26개 확인. 과거 estop 필수 계약은 이번 첨부 문서로 대체된다.

## 변경 파일과 동작

- robot/ros_ws/src/jetson_harvest_interfaces/msg/ControlState.msg 및 package.xml:
  첨부 원문 6필드/3.0.0. farm_interfaces 및 RuntimeStatus/서비스 형식은 변경 없음.
- robot/ros_ws/src/harvest_robot/harvest_robot/jetson_connection.py:
  Bool 비상정지 구독/콜백/대입 제거. V3 타입 확인, 유효 관측에만 10Hz 발행.
- 같은 디렉터리 jetson_state.py: 비상정지 상태/설정/만료 판정 삭제.
  발행 시 실제 측정 시각 및 수신 나이 각각 0.2초 이내 확인. 미래 허용 기존 50ms 유지.
  관측 없음/만료 시 sequence 증가나 발행 없음. 새 관측이면 재개. 원본 측정 stamp 유지.
  주행의 odom_max_age_s·지속 정지 시간·속도 임계값은 변경하지 않았다.
- robot/config/harvest/harvest_handoff_jetson_real.json: estop_topic/estop_timeout_s 삭제.
- robot/tools/trial_console/static/app.js: estop 표시 제거. 기존 일반 메시지 구독은 V3 설치 환경 사용 필요.
- test_jetson_state.py/test_jetson_connection_ros.py: V3/0.2초 경계/만료·재개 검증.
- 인계·상태·결정·sim 변경 이력과 콘솔/통신 README 갱신.

## 검증과 영향

/tmp/manyfarm_control_v3/install에 jetson_harvest_interfaces 단독 colcon 빌드 성공.
PC 단위/최소 준비/ROS 상태/콘솔 단위·ROS 검사 총32개 통과(8.52초).
ROS domain231, LOCALHOST, 127.0.0.1만 사용. 실제 로봇/Jetson 접속·동작 명령 없음.
로그 /tmp/manyfarm_control_v3/check.log, 빌드 log/. JS 문법 및 git diff --check 통과.
성공 주행/인계 코드, 도메인77/18449/Zenoh 설정, 팔 요청 전 ready 판정은 변경하지 않았다.
로봇 /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741 설치본은 이번 수정 미반영.
PC 소스 변경만으로 현재 laun 실행본이 V3가 되지 않는다. 양측 타입 일치 후 실물 검증 필요.

## 되돌리기

이번 여섯 필드 타입·발행/설정·표시·테스트 변경만 대조하여 되돌린다.
기존 사용자 미커밋 변경 전체를 reset하지 않는다. Jetson V3와 구형 타입 혼용은 지원하지 않는다.
로봇 적용/프로세스 변경/저널 변경/commit/push/staging 없음.
