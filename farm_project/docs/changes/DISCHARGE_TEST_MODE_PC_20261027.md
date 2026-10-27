## 2026-10-27 후속 — 배출 시험 모드 로봇 반영·재빌드 완료

사용자 “시험용 상태 전환 기능 로봇에 반영하고 재빌드 … 백업 PC … 프로세스 직접” 승인.
로봇 격리 경로 jetson_reply_20261027_1741의 jetson_connection.py, 관련 ROS 시험,
config/zenoh-control-without-arm.json 3파일만 갱신. 기존 관제 deny 보존 후 시험 서비스/토픽 제외 추가.
PC 백업 /home/eunbi/vmany_artifacts/robot_backups/transfer_test_20261027_194653/before.tar.gz,
manifest.json(해시) 및 verification.json(설치/프로세스 검증). 로봇에는 백업을 생성하지 않았다.
첫 빌드 후 이전 설치 Python 복사본이 남은 것을 해시 검사로 발견했고 소스 수정시각 갱신 후 재빌드했다.
최종 harvest_robot 빌드 성공(5.92초), 설치 import 경로/소스 동일, 기존 V3 6필드/SetBool import 확인.
소스·설정88파일 해시 대조로 지정한3파일 외 보존 확인. 실제 운영 노드/브리지 PID161238/161273/161722/161786 유지.
ROS 노드·명령·초기위치·이동/프로세스 기동·종료·저널 변경 없음. 실제 시험 서비스 왕복은 사용자 전환 후 필요.
다음: 사용자 laun/zen 재시작, PC 미니관제 서버 재시작과 웹 새로고침/시험 연결.
dzen 설정 변경 없음. 아래 로봇 미배포 기록은 이전 상태. commit/push/staging 없음.

# 배출 시험 모드 — PC 구현 (2026-10-27)

기준 HEAD48d2d1c812a968058254ddb2355ee5dfc9b96c68 및 기존 미커밋 V3/미니관제 변경을 보존했다.
사용자 명시 요청으로 구현. 이번에 ROS 노드/브리지 실제 기동·종료나 배포는 하지 않았다.

## 변경 범위

- robot/ros_ws/src/harvest_robot/harvest_robot/jetson_connection.py:
  기존 단일 ControlState 발행기에 일시적인 시험 활성값 추가.
  transfer_active = 실제 인계 활성 OR 시험 활성. base_stopped·원본 시각·관측 만료·발행률 유지.
  별도 ControlState 발행기/더미 odom/도킹 성공/주행 명령/저널 변경 없음.
  로봇 ID 기반 /transfer_test_mode/set_enabled(SetBool) 서비스와 /enabled(Bool,10Hz) 토픽 제공.
  시험은 기본 off. 실제 작업 진행 중 on 거절, 운영 작업 시작 시 자동 off. 기존 작업은 차단하지 않는다.
  모드 off는 실제 인계 active를 false로 덮어쓰지 않는다. 데이터 만료 중에도 시험 모드 자체는 조회 가능.
- robot/tools/trial_console/arm_session.py: transfer_test 요청 허용, 기존 명령 확인 및 bool 형식 확인.
- robot/tools/trial_console/arm_agent.py: Pinky 서비스 호출·상태 구독. Jetson 서비스와 다른 로컬 주소 사용.
  콘솔은 ControlState를 직접 발행하지 않는다. on/off는 배출 명령을 자동 전송하지 않는다.
- static/index.html/app.js: 켜기·끄기, 실제 수신 상태 및 미연결/구버전 안내.
  응답은 Pinky 시험 모드 응답으로 표시한다. 로봇 상태 수신 없이 요청 접수만으로 켜짐이라 표시하지 않는다.
- robot/config/robots/vicpinky/communication/control-bridge-jetson-exclusions.json:
  관제 브리지에 시험 상태/제어가 전달되지 않도록 deny 병합용 조각 추가. Jetson 전용 allow는 변경 없음.
  현재 운영 관제 config는 수정하지 않았다. 실제 적용 시 기존 deny를 보존하며 새 항목만 합친다.
- 테스트: test_jetson_connection_ros.py, test_arm_agent_ros.py, test_console_unit.py.

## 사용 순서 (후속 로봇 적용/사용자 기동 이후)

1. 시험 연결, 실제 상태 확인, 명령 전송 확인란 체크.
2. 배출 시험 모드 켜기 → Pinky 성공 응답 및 상태 켜짐 확인.
3. ControlState 실제 base_stopped=true, transfer_active=true 수신 확인.
4. 새 transfer_id로 Discharge 요청. Jetson 장치/준비 조건은 서버가 판정하며 별도 우회 없음.
5. 최종 결과 및 실제 정지 확인 후 모드 끄기 → 꺼짐 확인.

모드 해제는 팔 정지 명령이 아니다. 웹/SSH 연결 종료만으로 모드는 해제되지 않으며 재연결 후 상태를 조회한다.
실제 운영 작업이 시작되거나 Pinky 노드가 재시작되면 시험 모드는 해제된다.
시험 중 운영 주행/인계 요청을 함께 보내지 않는다. Jetson이 아직 배출을 구현하지 않았다면 시험 모드로 해결되지 않는다.
Pinky 적재량·관제 미확정 인계/작업 완료 기록을 변경하지 않는다.

## 검증·남은 작업

PC 단위/격리 ROS37개 통과(14.40초), 기존 JS 요약 테스트 및 문법, git diff --check 통과.
단일 발행기 유지, 실제 속도에서 base_stopped=false, 관측 만료 시 미발행, on/off 왕복,
운영 작업 시작 시 시험 해제·실제 인계 active 유지, 콘솔이 Action/ControlState를 자동 발행하지 않음을 검사했다.
로그 /tmp/manyfarm_control_v3/transfer_test_check.log. ROS domain231/LOCALHOST/127.0.0.1 모의 환경.
실물/Isaac 검증 아님. 로봇 설치본 미반영, 후속 배포·harvest_robot 재빌드 및 사용자 프로세스 전환 필요.
PC 미니관제 서버도 사용자 재시작 필요(ArmSession 명령 목록 변경). 이번에 재시작하지 않았다.

## 되돌리기

이번 시험 필드/서비스/상태 토픽·콘솔 버튼/클라이언트·deny 조각만 대조해 제거한다.
기존 V3 변경과 주행/인계 코드는 보존한다. 백업은 이후 배포 시 PC Git 외부 보관, 로봇에 보관하지 않는다.
Git commit/push/staging 없음.
