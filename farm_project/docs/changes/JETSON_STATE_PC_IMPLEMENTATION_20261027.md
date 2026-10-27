# 최신 변경: Jetson 10/27 회신 반영 (PC 미배포)

아래 회신 반영 내용이 최신이다. 뒤의 “최종 축소안”은 직전 사용자 요청의 이력이며 현재 팔 요청 직전 확인 범위는 이 절을 따른다.

## 승인과 근거

사용자: “회신 기준으로 필요한 설정이랑 팔 요청 직전 최소 준비 확인만 PC에서 수정하고 검증 … 문서에 있는 기준으로만”.
근거 ZIP: `/home/eunbi/Downloads/MANYFARM_JETSON_PINKY_REPLY_20261027.zip`, REPLY_KR.md(17:06 KST),
pinky-depth-connection.patch.json, zenoh-jetson-pinky.json. 첨부 해시와 IDL14개/PC소스/설치기록 해시 일치를 대조했다.
Jetson 실시간 상태나 서버 소스를 이번에 직접 확인한 것은 아니다.

## 이번 변경

- 별도 harvest_handoff_jetson_real.json만 팔 준비10초/응답5초/실행1260초/취소20초 및 transfer.stop_timeout_s=20초로 변경.
  기존 성공 harvest_handoff_real.json/YAML은 그대로다. 인계 경로·단계·완료/취소 알고리즘은 변경하지 않는다.
- jetson_state.py: mode=depth_v11 설정, 마지막 수신 TTL2.5초 및 원문 stamp의 나이2.5초,
  ready=true를 팔 요청 직전 조건으로 제공. robot_id/비어 있지 않은 boot_id, 같은 boot의 증가 sequence를 검증한다.
  중복/역순 sequence·이전 boot의 늦은 메시지는 갱신하지 않는다. 새 boot의 최신 상태는 허용하고 영구 차단하지 않는다.
  RuntimeStatus의 미래시각에 새로운 수치 기준을 추가하지 않았다. 회신의 미래50ms는 Jetson의 ControlState 수신 기준이다.
- arm_client.py: 기존 서버 발견 뒤 send_goal_async 직전에만 선택형 before_send 콜백 호출.
  서버 발견과 상태 준비는 같은 readiness_timeout_s=10초 예산을 공유한다.
- mission.py: 도착 후 ARM 단계에서만 콜백 전달. 기존 프로필은 콜백 없음.
- jetson_connection.py: 제한시간 안에 위 상태를 기다리고 기존 취소 확인만 수행.
  준비 실패 시 Goal을 보내지 않으며 기존 예외 정리 경로를 사용한다.
  실행 중 ready=false로 중단하지 않는다. 박스/팔자세/device_state_valid/recovery/error/업무ID를 별도 준비 조건으로 덧붙이지 않는다.
- `robot/config/robots/vicpinky/communication/zenoh-pinky-jetson.json`: domain77, peer,
  connect=tcp/192.168.0.29:18449, multicast/gossip OFF, namespace=/, LOCALHOST.
  회신 Jetson 설정의 서버/클라이언트·publisher/subscriber를 반대로 매핑한 팔 전용 allow.
  get_result1300초, send_goal/cancel_goal5초, default20초.
- 같은 디렉터리 cyclonedds-loopback.xml은 회신 첨부 원문.
- control-bridge-jetson-exclusions.json은 관제 브리지에서 제외할 팔 주소 목록 **조각**이다.
  완전한 실행 설정이 아니며 기존 관제 allow 전체를 대체하지 않는다. README.md에 적용 경계를 기록했다.
  현재 운영 관제 설정을 PC에서 확정할 수 없어 관제 실행 파일/별칭/실제 브리지는 변경하지 않았다.

## 비상정지 입력의 미확정 사실

이번 변경에서 새 입력 토픽이나 고정 false 신호를 만들지 않았다. 기존 PC 선택형 Bool 어댑터는 있으나
회신에서 std_msgs/Bool 방식이나 실제 토픽을 확정한 것은 아니다. estop_topic은 빈 값으로 남아 있다.
미확인 입력의 기존 보수적 estop_active=true 발행은 실물 준비 완료를 뜻하지 않는다.
Jetson이 estop_active=false를 요구하므로 입력 계약이 해결되기 전 실제 수확 가능하다고 말하지 않는다.

사용자는 버튼이 모터드라이버 전원을 차단하는 구조로 추정하고, 누르면 브링업이 실패한 경험을 전달했다.
PC에 보관된 진단 bringup.py와 10/08 백업 zlac_driver.py를 읽었다. bringup은 모드설정/enable/RPM조회 실패 시 초기화를 중단하고,
드라이버의 읽기 함수는 RPM·엔코더이며 버튼 상태 읽기/ROS 토픽은 확인되지 않았다.
이는 현재 로봇 설치본이나 실제 배선을 확인한 결과가 아니다. 통신 무응답을 비상정지 입력으로 치환하지 않는다.
담당자에게 읽을 수 있는 입력의 존재·출처·형식 확인이 필요하다는 사실을 전달할 항목으로 남긴다.

## 검증·미검증

PC 단위·회귀106개 통과, 기존 timeout 전제 불일치3개 제외. 팔 Goal 전송 직전 순서,
미준비 시 이동은 수행하되 팔 Goal은 미전송, 준비 대기 중 기존 취소, 실행 중 ready=false 허용,
부분 실패 수량을 포함한 정상 Window 결과를 확인했다.
PC 격리 ROS3개 시험은 domain231/loopback/시험 토픽만 사용했다. 별도 PC 빌드·설치 import 및 소스 일치 검사.
브리지 JSON은 회신과 방향/시간값/허용목록을 정적으로 대조했고 실제 Zenoh 프로세스로 로딩하거나 상대 연결하지 않았다.
관제/인계 통신·장치·미션/복귀 판정7파일 + 기존 성공 설정3파일은 HEAD48d2d1c와 바이트 동일.
새 프로필은 기존 값에서 상태 연결 블록과 요청된 팔/정지 시간만 다르다.

ROS 시험에서 두 입력의 만료 시각을 같다고 가정한 검사1개가 실패했다.
각 입력 만료를 독립적으로 기다리도록 시험만 수정했다. 제품 TTL은 그대로다.
최종 결과와 로그는 reply_regression.log, reply_ros.log, reply_build.log 및 reply_install/:
`/tmp/manyfarm_jetson_pc_20261027/` (임시 보관).
실제 Jetson/기기간 Zenoh/시계 오차/실물 팔/로봇 주행·인계 미검증.
회신의 startup_auto_prepare=true 때문에 실제 ControlState 연결만으로 팔 준비 동작이 시작될 수 있다.
실물 Discharge가 현재 거절된다는 회신 내용도 유지하며, 배출 검증 완료로 확대하지 않는다.

로봇 배포/접속/재기동/이동, 운영 설치본 수정, staging/commit/push 없음.
원복은 이번 팔 전송 콜백·회신 설정만 이전 관측 전용 구현과 대조한다. 기존 사용자 문서 변경은 보존한다.

---

# Jetson 상태 통신 PC 구현 — 2026-10-27 최종 축소안

## 기준과 승인

기준 HEAD: `48d2d1c812a968058254ddb2355ee5dfc9b96c68`.
사용자 후속 요청: “불필요하게 추가한 차단 조건은 빼고 ControlState 발행이랑 젯슨 상태 수신에 필요한 것만 … 기존 성공한 주행·인계 동작은 건드리지 말고 PC에서만 수정하고 검증”.
직전 PC 구현에 추가했던 작업 차단은 제거했다. 로봇 배포·재기동·이동 및 commit/push/staging 없음.
기존 사용자 미커밋 인계 문서 변경은 보존했다.

## 최종 변경 범위

- `robot/ros_ws/src/jetson_harvest_interfaces/`: 제공 ZIP의 IDL·빌드 정의 그대로 유지.
- `robot/ros_ws/src/harvest_robot/harvest_robot/jetson_state.py`: 설정, 전체 RuntimeStatus 필드의 불변 표본, 수신 경과/만료 조회, odom 기반 ControlState 값 산출.
- 같은 패키지 `jetson_connection.py`: 선택형 ControlState publisher/RuntimeStatus subscriber 및 `snapshot()` 조회. 자동 장치 명령 없음.
- 같은 패키지 `node.py`: 선택형 객체 생성·종료 4줄만 추가. `package.xml`: 메시지 의존성.
- 별도 `robot/config/environments/harvest_handoff_jetson_real.yaml` 및 `robot/config/harvest/harvest_handoff_jetson_real.json`: 성공 프로필을 유지한 상태 연결 선택 설정.
- 같은 패키지 test의 test_jetson_state.py, test_jetson_gates.py, test_jetson_connection_ros.py: 상태 관측 및 기존 미션 비개입 검증.

communication.py, mission.py, status.py, handoff_devices.py, transfer_communication.py,
transfer_mission.py는 이번에 추가했던 차단만 제거해 성공 기준 HEAD와 바이트 동일하다.
node.check/prepare_station_return도 기존 로직 그대로다.
관제/운송 코드·공통 주행 라이브러리·경로/컨트롤러·인계 알고리즘·완료 5cm/6도는 변경하지 않았다.

## 제거한 조건

작업 수락·주행 시작·팔 요청·스테이션 복귀·인계 컴포넌트 시작 및 실행 중 검사에 연결했던
require_ready/check/before_operation을 제거했다. RuntimeStatus로 기존 RobotStatus.ready/error를 덮어쓰지 않는다.
mode 허용 목록, 팔/박스 준비 조합, 활성 작업 ID 일치, 발행자 개수, 재시작/시계 역행 영구 차단을 제거했다.
팔 Action 존재나 components 인계 조합을 상태 연결 생성 조건으로 요구하지 않는다.

## 남긴 통신 동작

ControlState: 10Hz STEADY timer, RELIABLE/VOLATILE/KEEP_LAST1, 부팅 UUID 및 증가 sequence.
base_stopped는 신선한 odom·속도·지속 정지 관측과 기존 이동 Goal/작업 소유 상태로 산출한다.
이 값은 관측 결과이며 Pinky 미션을 중단하지 않는다. 잘못된 frame/비정상 속도/오래된 odom을 정지로 보고하지 않는다.
odom 시계 역행 시 관측을 새로 쌓으며 영구 래치하지 않는다. stamp는 odom 원본 측정 시각이다.
transfer_active는 인계 snapshot의 task_id 존재로 산출한다.
estop_topic이 있으면 std_msgs/Bool(True=활성)를 구독한다. 미설정/미수신/만료는 estop_active=true로 보수적으로 표시한다.
비상정지 미확인을 거짓 false로 만들지는 않는다. 정지 여부와 비상정지 여부는 별도 필드다.
이 값으로 Pinky 자체 작업을 차단하지 않지만 Jetson 서버의 기존 수락 정책에는 영향을 줄 수 있다.
실제 비상정지 신호의 토픽/형식/주기는 연결 전에 확인해야 한다.

RuntimeStatus: robot_id가 해당 로봇인 메시지의 모든 필드를 그대로 저장한다.
ready=false·mode·팔/박스·recovery_required·오류·작업 ID·boot/sequence/stamp는 관측 정보이며 Pinky 정책을 강제하지 않는다.
`snapshot()`은 status(전체 원문 값, stamp는 ns), age_s(단조 수신 경과), stale(기본 2.5초)을 제공한다.
미수신은 status/age_s=None, stale=true다. 새 메시지를 받으면 만료는 해제된다.
stale은 마지막 수신으로부터의 시간이며 원격 센서 갱신/장치 정상성의 증거는 아니다.
재시작·중복·시계 변화도 수신 정보로 기록하며 자동 복구/재전송·미션 예외를 만들지 않는다.

기존 프로필에는 jetson_connection 설정이 없으므로 확장 ROS 객체를 생성하지 않는다.
새 프로필의 estop_topic은 아직 빈 값이며 accepted_modes 설정은 삭제했다.
Zenoh 실행 설정/운영 launch 선택은 이번에 바꾸지 않았다.

## 검증

- PC 단위·회귀: **101 passed, 3 deselected**. 새 상태 12개 + 미션 비개입 1개 + 기존 회귀 88개.
- 실제 PC 격리 DDS 왕복: **3 passed**, domain231/LOCALHOST/127.0.0.1 및 /test_only_jetson/*만 사용.
  ControlState 발행·정지/이동/인계 값, RuntimeStatus ready=false/다른 작업 ID 원문 보관,
  만료 및 새 boot 수신 회복 확인. Action/서비스/속도/초기위치 발행 없음.
- 기존 3개 timeout 전제 시험은 기준 HEAD의 event_timeout_s=None과 불일치하여 이전과 같이 제외.
  test_event_timeout_stops_and_keeps_recovery_block_after_restart 2개 및
  test_failed_transfer_preserves_load_and_request 1개. 통과로 계산하지 않았다.
- 성공 프로필 YAML/JSON, handoff_fsm.json, handoff_planning.py, handoff_window.py 및 위 6개 미션/통신 파일은 HEAD와 바이트 동일.
- PC 독립 colcon 빌드 및 Python 문법/git diff --check 확인. 운영 install은 변경하지 않는다.

임시 로그: `/tmp/manyfarm_jetson_pc_20261027/observation_regression.log`, observation_ros.log,
observation_build.log, observation_colcon_log/, observation_install/.
과거 109+3 통과는 차단 포함 이전 PC 구현 결과이며 현재 결과로 사용하지 않는다.
이전 구현 테스트의 고정 대기 수신 타이밍 실패를 조건 수신 대기로 수정한 방식은 유지했다.
실제 Jetson/Zenoh 기기간 연결·로봇 주행/인계·실제 팔·Isaac 검증은 수행하지 않았다.

## 남은 범위와 원복

Jetson 서버 계약과 비상정지 입력, 브리지/도메인77 기기간 통신 확인은 별도다.
GetOperation/Recover IDL은 있으나 업무 연동/재시작 적재량 대조는 구현하지 않았다.
이번 수신 상태를 근거로 동작 차단 정책을 다시 추가하지 않는다.
운영 미배포이므로 운영 원복 없음. PC 원복 시 이번 추가 파일 및 node 생성/종료·package 의존성만 대조하고,
기존 미커밋 문서 변경은 보존한다. 전체 reset/clean이나 저널 복원은 하지 않는다.
