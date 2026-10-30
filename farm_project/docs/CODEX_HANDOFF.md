## 2026-10-30 최종: 원본 웹 복귀 성공·PC 일치 확인

사용자 복귀 확인 후 실제 관제에서20:18:43 KST RETURN_3e875504cd584bd6bdfa3e8875289889의 SUCCEEDED/docked=true를 직접 확인했다. 현재 laun 원본 설치본 실행 중. 관련 소스·설정289파일 PC/로봇 일치, 주요 Python 설치본도 일치하여 추가 실행 코드 수정은 없다. 과거 시험 도구·예찰 설정·문서 차이는 별도로 기록했다. 종료된 로그131개를 PC에서 파일별 해시 검증 후 로봇에서 삭제해 가용2.5G→4.5G 확보. 현재 로그·운영 프로세스·드라이버·성공 release 유지. 팔 상태 생략 조건 유지, 전체 팔 운영 검증으로 확대하지 않는다. [상세 대조·백업·원복](changes/STATION_DOCKING_SOURCE_INTEGRATION_20261030.md)의 마지막 절 참조. 아래 원본 웹 복귀 미검증은 이전 상태다. commit/push 없음.

## 2026-10-30 후속: laun 원본 전환·실제 관제 연결 확인

사용자 승인으로 로봇 기존 laun 별칭을 원본 workspace 실행으로 전환했다. zen/dzen은 검증된 관제/실제 Jetson 연결 유지. 별칭 검사·launch --check 통과, 재기동 없음. 실제 관제 웹 수확 복귀 ready=true/allowed=true·차단 사유 없음 및 요청/결과 계약 확인. 웹에서 주행 명령은 보내지 않았으며 원본 재기동 후 실물 검증은 남는다. [변경·검증·원복 기록](changes/STATION_DOCKING_SOURCE_INTEGRATION_20261030.md)의 후속 절을 따른다. 아래 별칭 미변경 기록은 이전 단계다.

## 2026-10-30 최신: 성공본을 원래 코드·정식 workspace로 통합 완료

성공 복귀·두 벽 도킹 구현을 로봇 원래 프로젝트 src/config에 선별 이식하고 robot/ros_ws/install에7패키지 빌드했다. 최종48파일 PC·로봇 일치 및 성공본 실행 소스 대조, 원본 CTest7/Python49 통과. 제어값/인계/sim은 불변. 재기동은 미실행이며 기존 laun 별칭은 그대로다.

원본 실행: `bash /home/vic/vmany/main/farm_project/robot/tools/terminal/run.bash launch`.
정확한 범위·빌드·원복은 [원본 이식 기록](changes/STATION_DOCKING_SOURCE_INTEGRATION_20261030.md), 성공 근거는 [성공 고정 문서](changes/STATION_DOCKING_SUCCESS_FREEZE_20261030.md)를 따른다. 과거 ‘격리 release만 적용’은 당시 상태다. commit/push 없음.

## 2026-10-30 최신 확정: 스테이션 두 벽 도킹 성공 기준

사용자 실물 동작 만족 확인으로 **뒤+왼쪽 벽 도킹**과 `station_docking_two_wall_20261030`을 성공 기준으로 고정했다. 복귀→도킹→정리 후 SUCCESS/docked=true 수신, 도킹약15.9초. 허용치5mm/5mm/1도·기존 속도/충돌/정지 조건 유지. 구조는 기존 State/Controller/Mission과 도킹 조립·공통 관측/제어 컴포넌트 분리로 확정하며 이번에 제어 코드를 바꾸지 않았다.

현재 상태·파일 책임·성공 증거·실행·원복은 [확정 문서](changes/STATION_DOCKING_SUCCESS_FREEZE_20261030.md)를 우선한다. 아래 과거의 세 벽/허용치 미확정/미배포 표기는 작성 당시 이력이다. 팔 상태 생략 차체 시험의 성공이며 전체 팔·인계 운영 성공은 아니다. commit/push 없음.

## 2026-10-28 ControlState 업무 차단·정지 분리 로봇 배포 완료

사용자 “로봇에 적용해줘” 승인으로 jetson_reply_20261027_1741 release의
src/harvest_robot/harvest_robot/jetson_connection.py 한 파일만 적용하고 harvest_robot 재빌드 성공(패키지4.95초).
PC·로봇 소스·설치 Python SHA256 일치: 4bdc457d0ab909fe75df29bf8094cc22b044e35854c8932d1fcde4f7e6f8945a.
백업 대비 소스/설정 및 설치 일반 파일 대조에서 해당 소스와 설치 Python만 변경 확인(__pycache__ 제외).
PC 백업 /home/eunbi/vmany_artifacts/robot_backups/control_state_blocked_20261028_191811/
(before.tar.gz, before_hashes.json, verification.json). 로봇에 백업 생성 없음.
수확89480/관제89957/Jetson브리지90018 PID 유지. 프로세스 재기동·명령·복구·초기위치·이동 없음.
현재 실행 노드는 기존 코드를 유지하므로 사용자가 laun을 재시작해야 적용된다. zen/dzen 설정 변경 없음.
blocked 자동 해제 없음. 실제 Jetson 복구·주행 시험은 미실행. PC 검증38개 통과는 아래 기록 참조.
원복은 사용자 프로세스 종료 후 PC 백업의 해당 소스를 대조 복원·재빌드하며 저널은 복원하지 않는다.
기존 스테이션 복귀 변경 보존. commit/push/Confluence 수정 없음.

## 2026-10-28 ControlState의 업무 차단·실측 정지 분리 — PC 수정

사용자 “그렇게 바꿔야할것같아” 승인으로 jetson_connection.py의 _motion_idle에서
blocked만으로 false를 반환하던 조건을 제거했다. blocked 설정/해제·작업 및 주행 수락 로직은 그대로다.
실제 odom·정지 지속시간·진행 중 이동·stopping·관측0.2초 기준은 유지한다.
기존 배출 시험 모드의 blocked 중 활성화 거절은 _test_available에서 명시적으로 유지한다.
Jetson 오류 해제나 Pinky blocked 해제를 자동 수행하지 않는다. 최초 수확 중 false 전환 원인 해결과는 별개다.
기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4. 다른 작업의 스테이션 복귀/node.py 등 미커밋 변경 보존.
직접 검증: PC domain231/loopback 통신·미니관제 회귀38개 통과(17.32초), git diff --check 통과.
로그 /tmp/control_state_blocked_20261028.log. 실제 Jetson 복구/실물 주행은 미검증.
로봇 적용·재빌드·재기동·명령 전송·Confluence 변경·staging/commit/push 없음.
원복은 이번 _motion_idle/_test_available 변경 및 추가 회귀 시험만 되돌리며 다른 미커밋 변경을 보존한다.

## 로봇팔 테스트 재개 요청 시 준비 기준 — 2026-10-27

사용자가 “로봇팔 테스트할 거야”라고 하면 아래 현재 설정을 먼저 읽고 현 상태와 대조해 준비한다.
사용자가 커밋·push 완료를 알렸으며, 이번 로컬 확인 HEAD는 `e135cdef9462276cc25d9fa336f084e2dcac72e4`, 기록 추가 전 작업 트리는 깨끗했다. 원격 push 상태는 별도 조회하지 않았다.

- PC 원본: `robot/config/environments/harvest_handoff_jetson_real.yaml`, `robot/config/harvest/harvest_handoff_jetson_real.json`, `robot/config/robots/vicpinky/communication/`.
- 실행 진입점 보존본: `robot/tools/terminal/jetson_release_20261027/README.md` 및 run.bash/terminal.py/aliases.bash.
- 미니관제: `robot/tools/trial_console/README.md`, config.json, `docs/changes/JETSON_TRIAL_CONSOLE_20261027.md`, `docs/changes/DISCHARGE_TEST_MODE_PC_20261027.md`.
- 로봇 `vic@192.168.0.12`, release `/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741`, Jetson `192.168.0.29:18449`, ROS_DOMAIN_ID=77, Jazzy/CycloneDDS, ControlState V3 비상정지 필드 없음.
- 로봇은 사용자 터미널에서 `source ~/.bashrc` 후 laun(수확), zen(관제), dzen(실제 Jetson 팔 전용). dzen이라는 기존 모드 이름이 남았지만 PC 더미 연결이 아니다. PC 더미/더미 브리지를 새로 켜지 않는다.
- PC 미니관제는 프로젝트에서 `python3 robot/tools/trial_console/app.py`, 웹 `http://127.0.0.1:8091`. 이미 실행 중이면 중복 기동하지 않는다.
- 준비 시 현재 프로세스·alias·설치본과 수신 ControlState/RuntimeStatus·자세·시험 모드 상태를 읽기 전용 확인한다. 과거 위치/IDLE/ready/수량/복구 상태를 현재 상태로 간주하지 않는다. Jetson SSH 접속은 필요하지 않다.
- 명령 순서는 장비/터미널을 구분해 안내하고 사용자가 프로세스와 시험 명령을 직접 실행한다. 테스트 재개라는 말만으로 자동 기동·종료·초기위치·이동·수확·배출·복구 명령을 보내지 않는다.
- 배출 단독 시험은 미니관제의 확인란→배출 시험 모드 켜기→실제 상태 수신 확인→별도 Discharge 요청. 시험 모드는 transfer_active만 바꾸며 실제 정지 확인을 유지한다. 종료 후 모드를 끄고 실제 운영 전 off 확인. 웹 연결 종료만으로 해제되지 않는다.
- vinit은 실제 스테이션 위치/방향과 IDLE·정지 확인 후에만 안내한다. 다른 위치에 스테이션 초기좌표를 보내지 않는다.
- 기존 성공 주행·인계 로직은 유지한다. 통신 수락/Feedback/최종 Result를 구분하며 실제 전체 팔·운송 연동 성공을 가정하지 않는다. Feedback 6회 반복 원인은 미확정이다.
- 변경·재빌드는 별도 요청 범위에서만 진행하고 백업은 PC Git 외부에 보관한다.

이번 요청은 재개 절차 기록만 반영했다. 코드·설정·로봇 변경 없음, commit/push 없음.

## 2026-10-27 현재 로봇 실행본 PC 수집·커밋 준비

사용자 “현재코드 git에 올릴수있도록 PC에 가져오고 커밋 준비” 요청으로 로봇을 읽기 전용 조회했다.
기준 HEAD `48d2d1c812a968058254ddb2355ee5dfc9b96c68`, 기존 PC 미커밋 변경 보존.
로봇 release의 두 패키지 소스82파일은 PC와 일치하며 수확 설치 Python48파일도 소스와 일치했다.
누락된 실제 run.bash/terminal.py/aliases.bash를 `robot/tools/terminal/jetson_release_20261027/`에,
실행 중 관제 브리지 전체 설정을 `robot/config/robots/vicpinky/communication/zenoh-control-without-arm.json`에 보존했다.
환경 YAML은 배치 JSON 경로만 다르므로 PC 상대경로 원본 유지. 로봇의 오래된 제외 참고 목록은 PC에 덮어쓰지 않았다.
이번 신규 실행 동작 변경 없음. 기존 성공 주행 프로필·인계 FSM·handoff_planning/window는 HEAD와 동일.
직접 PC 검사37개 통과(14.51초, domain231/loopback), JS 상태 표시/문법·Bash 문법·diff 공백 검사 통과.
PC 백업 `/home/eunbi/vmany_artifacts/commit_prepare_20261027/`에 수집본과 기존 미커밋 파일 보관.
실물 재시험·로봇 변경·프로세스 조작·초기위치·명령 발행 없음. staging/commit/push 미수행.
상세/커밋 범위/복원: `docs/changes/JETSON_COMMIT_PREPARATION_20261027.md`.

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

## 2026-10-27 후속 — ControlState V3 PC 반영 완료, 로봇 미배포

사용자 “그럼 일단 그대로 수정” 승인으로 PINKY_CONTROL_STATE_V3_20261027.zip 기준을 반영했다.
ControlState의 estop_active와 발행·입력·설정·미니관제 표시를 제거하고 패키지를 3.0.0으로 맞췄다.
관측 없음/수신 또는 측정 나이 0.2초 초과 시 발행하지 않으며 최신 관측 수신 시 재개한다.
원본 측정 시각과 기존 차체 정지·인계 판정, 주행·인계 알고리즘 및 허용오차는 유지한다.
구형 생성 메시지 환경은 발행 전에 CONTROL_STATE_SCHEMA_MISMATCH로 알린다.
PC 격리 인터페이스 빌드 및 단위/최소 준비/ROS 상태/미니관제 32개 검사 통과.
ROS는 domain231/loopback 모의 서버만 사용했으며 실물·Isaac 시험이 아니다.
로그: /tmp/manyfarm_control_v3/check.log 및 log/. 상세: docs/changes/CONTROL_STATE_V3_PC_20261027.md.
로봇 격리 설치본과 alias는 이번에 변경하지 않았다. 로봇 적용·재빌드 및 사용자 재시작이 남았다.
아래 비상정지 미확정 설명은 V3 이전 기록이다. commit/push/staging 없음.

## 최신 미니관제 변경 — 2026-10-27
실제 팔 수동 통신/응답 확인/프로세스 정리 UI를 PC에 구현했다. 운영8091 서버는 사용자가 재시작해야 한다. 실물 명령은 개발 중 보내지 않았다. [구현/검증 기록](changes/JETSON_TRIAL_CONSOLE_20261027.md).

## 최신 alias 상태 — 2026-10-27 17:50 KST
사용자 승인으로 로봇 laun/zen/dzen이 새 격리 버전을 가리키도록 변경·백업 완료. 기존 프로세스는 계속 실행 중이며 재시작은 사용자가 수행한다. 열린 셸은 source ~/.bashrc 필요. 백업·검증: [로봇 배치 기록](changes/JETSON_ROBOT_STAGING_20261027.md)의 마지막 절.

# 최신: 로봇 격리 설치 완료·운영 전환 전

[2026-10-27 로봇 배치 기록과 사용자 실행 명령](changes/JETSON_ROBOT_STAGING_20261027.md)을 먼저 읽는다. 기존 성공 프로세스는 계속 실행 중이며 새 버전은 별도 경로에만 설치했다. 비상정지 입력 계약은 미확정이다.

---


### 2026-10-27 후속 — Jetson 담당자 회신 기준 최소 준비 확인
사용자 승인으로 별도 Jetson 프로필의 팔 준비10/응답5/실행1260/취소20초 및 인계 정지20초,
전용 peer192.168.0.29:18449/domain77/get_result1300/default20초 설정을 PC에 준비했다.
팔 Goal 직전에만 depth_v11·ready=true·TTL2.5초 및 boot/sequence 유효 수신을 확인한다.
서버 발견과 상태 대기는 10초 예산 공유. 일반 주행/인계 수락/실행 중 ready=false 차단은 추가하지 않는다.
박스/팔자세 등 별도 조건 없음. 관제 브리지 실제 수정 없이 팔 주소 제외 목록 조각만 작성했다.
비상정지 신호는 미확정이며 토픽·고정 false를 만들지 않았다. PC 드라이버 백업에서 버튼 읽기 기능은 확인되지 않았으나 실제 배선/로봇 설치본은 미확인.
PC106개+격리 ROS3개 검증, 기존 정책 불일치3개 제외. 운영 배포·접속·재기동·이동/commit/push 없음.
원복: 이번 팔 콜백·회신 설정만 대조하고 기존 문서 변경 보존. 실물·Isaac 시험 아님.
최신 파일/검증/남은 범위는 docs/changes/JETSON_STATE_PC_IMPLEMENTATION_20261027.md의 **맨 앞 회신 반영 절**을 따른다.

---
# PC 미배포 변경 — 2026-10-27 Jetson 상태 통신

사용자 승인으로 ControlState/RuntimeStatus 선택형 연결을 PC에 구현했다. 로봇 성공 운영본은 기존 `48d2d1c…`이며 로봇 배포·재기동은 하지 않았다. 후속 요청으로 작업 차단을 제거하고 상태 발행·수신·조회만 남겼다. 비상정지 미확인은 발행값에 보수적으로 표시하며 Pinky 미션에는 연결하지 않는다. 기존 성공 프로필과 주행·복귀 완료 설정은 그대로다. 구현·시험·미검증·되돌리기는 [상세 기록](changes/JETSON_STATE_PC_IMPLEMENTATION_20261027.md)을 먼저 읽는다. 적재량 영속화/GetOperation 복구 연동은 후속 범위이며 실제 운영 준비 완료가 아니다. commit/push/staging 없음.

---

# 현재 인계 시작점 — 2026-10-27

성공 기준 커밋: `48d2d1c812a968058254ddb2355ee5dfc9b96c68` (사용자 커밋 확인). **[현재 상태·장비별 전체 실행 명령·복구·남은 문제](changes/HARVEST_CURRENT_HANDOFF_20261027.md)를 먼저 읽는다.** 인계 진입·벽 정렬·PC 더미 배출·복귀·다음 window 수확 성공을 보존했다. 실제 팔/운송 물리 통합 및 반복 안정성은 별도다.

코드·설정은 유지하며 기동/종료와 웹 버튼은 사용자가 수행한다. 과거 아래 기록은 작성 당시 상태다. 현재 로봇 위치/프로세스는 다시 확인하고, Git 밖 실행 의존성과 백업도 위 문서를 확인한다. 이번 갱신은 문서만 변경, 원격 push 여부 미확인.

---


## 2026-10-22 수확 인계 컴포넌트 연결 (별도 수정본)

사용자의 컴포넌트 조합 설계 및 진행 요청을 근거로 구현했다. 상태별 공통값 변경 대신 시작 시 전용 controller/저속 Spin 객체를 구성한다. 관제 window 좌표를 사용하고 기존 TransferMission의 TRANSPORT_CLEAR 이후 복귀한다. 다음 window는 다음 관제 목표로 받는다.

기준 커밋: 4b5c5b13605216d1b8b163ea988805572a6a908a. 대상: harvest_robot 연결/런타임/시험, farm_bringup의 선택적 출력 라우팅, vicpinky 전용 설정, 점검 도구. handoff_config 기본값은 빈 값으로 기존 실행을 유지한다. 시뮬에서는 새 기능 선택을 거부한다. 공통 Navigator/StationReverse 알고리즘은 변경하지 않았다.

직접 검증: 오프라인 64+58개 통과 및 정적 컴파일. 로그: 전달 패키지 component_checks.log, regression_checks.log. 실제 ROS/실물 주행은 미실행이다. 사용자 PC 적용 및 commit/push는 미실행. 실제 장치 서비스와 TF/odom/명령 라우팅 확인이 남았다. 변경 전 파일은 패키지 baseline에 보관하며 적용 도구는 기존 파일 비교 및 백업 후 변경한다. 상세 및 되돌리기: docs/changes/HARVEST_HANDOFF_COMPONENT_INTEGRATION_20261022.md.

# Codex 시작 및 ChatGPT 프로젝트 인계 절차

## 2026-10-21 복귀 단독 시험 보존 및 커밋 준비

기준 PC HEAD: `8df5f8eab87d450c675587b0be38ed85e3866a2e`. 사용자 제공 PC 소스와 로봇 `harvest_align_resume_tgm2zr8q/candidate`를 대조하여 누락된 실행 코드를 보존했다. 이번 변경은 검증 후보를 저장소로 옮기는 작업이며 제어 수치·완료 허용오차를 추가 변경하지 않는다. 커밋은 사용자가 VS Code에서 수행한다.

- 실물 후진 이탈 성공: 위치 오차 4.17mm, 정지 확인 완료. 기록 `1792558359276249505/1792558365404338213_arc.json`.
- 실물 방향 조정 성공: 위치 오차 5.56mm, 방향 오차 0.248도, 입력 시각 오류 없음. 기록 `1792560526521819101/1792560533286982755_arc.json`.
- 충돌 계산을 별도 프로세스로 분리하고 현재 입력과 유효한 기하 조건으로 결과를 검증한다. 계산 시간은 진단값이며 50ms 초과만으로 주행을 차단하지 않는다. 충돌·unknown·센서 단절·속도·정지 검사는 유지한다.
- 전진 복귀는 Nav2 성공 후 정지했으나 최종 방향 오차 1.91도가 기존 1도 기준을 넘어 실패 판정됐다. 위치 오차 1.77mm. 기록 `1792560666951148110/1792560672778478081_arc.json`. 성공으로 바꾸지 않는다.
- 같은 사이클의 벽 정렬은 관측 만료로 실패했다. 이전 벽 정렬 성공과 구분한다. 전체 연속 실물 주행 및 관제 연동 완료가 아니다.
- 다음 작업: 과한 완료 조건 검토와 초기 위치→12번→후진 곡선→벽 정렬→후진 이탈→방향 조정→전진 복귀→14번 연속 실행 연결.
- 이번 패키지 적용은 PC 소스만 변경하며 로봇 설치·이동·Git stage/commit/push는 하지 않는다. 백업은 Downloads에 저장한다.


## 최신 확인 상태 — 2026-10-21 KST

이 절은 아래 과거 기록의 “미반영/미검증/미커밋” 이후 확인된 결과다. 과거 기록은 당시 검증 범위를 남기기 위해 유지한다.

- 코드 커밋: `5d47a230699fa80551aad35cd5875a2fc87318a7`, 브랜치 `feat/harvest-handoff-real-20261018`. GitHub 반영 확인. 코드·설정·테스트·문서 79개이며 로그/빌드/설치 산출물은 해당 커밋에 포함되지 않았다.
- PC: 관련 회귀 26개, 실제 ROS 타입 16개, 독립 설치 및 실제 ROS 모의 FollowPath/파라미터/정지 odom 계약 검사 통과. 기록: `/home/eunbi/Downloads/harvest_preflight_check_zVeZWN`.
- 로봇: 16개 변경 항목 적용, 회귀 26개·ROS 타입 16개 및 독립 ROS 계약 검사 통과. 운영 `install/farm_navigation` 빌드 후 실제 import 파일과 소스 해시 일치 확인. 당시 검사에서는 실제 이동하지 않았다.
- 로봇 배포 기록: `/home/vic/Downloads/harvest_common_robot_TJWw1P`. 배포 전 PC 백업: `/home/eunbi/Downloads/harvest_common_robot_5Tg82O/robot_before.tar.gz` (체크섬 확인).
- 이후 공통 Navigator를 사용하는 벽 접근 실물 실행 성공: `SUCCEEDED`, `navigation.status=ARRIVED`, `accepted=true`, `cleanup_stopped=true`, `ros_cleanup_complete=true`, `baseline_unchanged=true`.
- 실물 기록: `/home/vic/vmany/main/farm_project/runs/wall_alignment/1792515109507469094/result.json`. 계획: `1792515066706348113/result.json` (동일 wall_alignment 폴더).
- 최종 관측 거리 0.4357192517535471m, 목표 0.4325m 대비 +3.219mm (허용 ±5mm). 보정 기준 각도 오차 -0.004926108427052628rad, 약 -0.282° (허용 ±0.5°).
- 최대 전진 명령 0.02m/s, odom 최대 전진속도 0.020808379895475848m/s. 속도 감시 이벤트 없음. 시작 시 TF 과거 시각 조회 실패 1건이 기록됐으며 이후 관측 및 완료 판정은 통과했다. TF 오류가 완전히 제거됐다고 기록하지 않는다.
- 성공 기준 유지: 연속 P·순차 정렬, target_angle=0.04276056667386108rad, 각도 허용오차 0.5°, 최대 전진 0.02m/s. 펄스 미사용. 곡선 충돌 검사·footprint 축소 없음.
- 최신 보존: `/home/eunbi/Downloads/harvest_common_success_dbLWxY`. `pc_source.tar.gz`, `robot_success.tar.gz` 모두 체크섬 확인. PC 소스/미추적 파일/Git diff 및 로봇 소스/설정/대상 설치본/이번 벽 계획·실행 기록 포함.
- 검증 범위: 이번 출력으로 공통 구조 적용 후 벽 접근의 실제 실행을 확인했다. 같은 재시험의 후진 곡선 상세 결과는 이 기록에 제공되지 않았으므로 별도의 신규 성공 수치를 만들지 않는다. 이전 곡선 성공 보존 기록은 유지한다. 물리 외부 측정 각도와 라이다 판정 각도는 구분한다.
- 전체 인계 FSM·팔/배출 연동·윈도우 복귀의 실물 통합 완료를 뜻하지 않는다. 본 갱신은 문서만 변경하며 커밋은 사용자가 VS Code에서 수행한다.


작성: 2026-10-06. 기준 코드: `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`.
이 문서와 PROJECT_STATE.md는 최신 코드·결정을 전달하기 위한 시작점이다. 기존 상세 인수인계서와 시험 기록을 대체·삭제하지 않는다.

## 1. 작업 위치와 읽는 순서

- 저장소: `Robot3FinalProject/main`, 기준 브랜치 `main`.
- 저장소 안 프로젝트 위치: `farm_project/`.
- 사용자 PC 작업 경로: `~/main/farm_project`.
- 프로젝트 폴더에서 Codex를 시작한다. 다른 경로에서 시작하면 작업 루트와 AGENTS 적용 범위를 먼저 확인한다.

1. 루트 `AGENTS.md`와 수정 대상 디렉터리의 추가 AGENTS.
2. [PROJECT_STATE.md](PROJECT_STATE.md): 현재 구조·통신·설정·검증 상태.
3. [DECISIONS.md](DECISIONS.md): 확정 설계·미확정 과제.
4. 시뮬 작업: `sim/AGENTS.md`, [현행 실행·로그 가이드](../sim/docs/RUN_GUIDE_20261006.md), `sim/docs/CHANGELOG.md`.
5. 관련 변경 문서와 실제 코드·설정. 최신 통신 변경은 `docs/changes/PROTOCOL-20261006-014.md`.
6. 상세 예찰 구조가 필요할 때 `docs/SUMMARY_인수인계서.md`를 읽되 10/2의 시점을 구분한다.

현재 코드의 동작과 사용자에게 확정받은 요구사항을 각각 확인한다. 문서·코드가 충돌하면 차이를 기록하며 임의로 과거 코드에 되돌리지 않는다. AGENTS의 변경 승인 규칙은 요약 문서보다 우선 적용한다.

## 2. 첫 세션에서 확인할 것

```bash
cd ~/main/farm_project
git status --short
git branch --show-current
git rev-parse --show-toplevel
git rev-parse HEAD
git remote -v
```

현재 파일을 덮어쓰거나 pull하기 전에 미커밋 변경과 원격을 확인한다. 원격 조회가 가능하면 `git fetch origin` 후 현재 브랜치와 `origin/main`의 차이를 읽는다. fetch 성공과 실제 코드 반영은 다르다. 이 문서는 reset, clean, stash, 강제 push를 지시하지 않는다.

처음 Codex에 전달할 요청:

```text
AGENTS.md와 docs/CODEX_HANDOFF.md를 먼저 읽어.
docs/PROJECT_STATE.md, docs/DECISIONS.md와 작업에 관련된 하위 AGENTS를 확인해.
Git 상태·현재 브랜치·HEAD를 확인하고 내 미커밋 변경을 보존해.
인수인계 기준 커밋과 현재 코드가 다르면 관련 차이를 확인해.
현재 구현 상태, 실제 검증된 범위, 남은 문제, 바로 이어서 할 작업을 간단히 알려줘.
내가 작업을 지시하면 해당 범위 안에서 수정·검증하고 관련 상태·변경 문서를 갱신해.
공통 코드 변경은 기존 승인 규칙을 따르고, 실행하지 않은 시험을 통과했다고 쓰지 마.
```

## 3. 양쪽 역할과 전달 기준

| 구분 | 역할 | 저장할 내용 |
|---|---|---|
| ChatGPT 프로젝트 | 세부 설계·기획·논의·보고서·도식 | 확정 결정, 요구사항, 완료 조건, 미확정 사항 |
| 로컬 Codex | 현재 코드 확인·구현·디버깅·실행 검증 | 변경 파일, 실제 결과, 미실행 항목, 다음 작업 |
| GitHub | 공통 기준과 변경 이력 | 공유할 문서·코드의 커밋과 브랜치 |

### ChatGPT → Codex

1. 이 프로젝트에서 최신 저장소 문서와 관련 코드를 읽고 설계를 논의한다.
2. 확정된 내용은 DECISIONS.md 또는 해당 상세 설계 문서에 기록한다. 제안/확정 상태를 표시한다.
3. 저장소 반영을 요청받은 경우 연결 권한과 범위 안에서 반영한다. 파일만 전달한 경우 사용자가 로컬에 적용하고 기록해야 한다.
4. Codex에는 결정 ID·파일·완료 조건을 전달한다. 별도 브랜치에 기록했다면 그 브랜치/커밋도 명시한다.

### Codex → ChatGPT

1. 관련 구현·검증 후 PROJECT_STATE.md를 갱신한다.
2. 시뮬 변경은 `sim/docs/CHANGELOG.md`, 공통 계약 등은 `docs/changes/`의 해당 기록을 유지한다. 같은 내용을 별도 WORKLOG에 다시 복제하지 않는다.
3. 사용자 요청·기존 승인 범위에 따라 commit/push한다. 요청되지 않은 원격 게시를 자동으로 수행하는 규칙은 아니다.
4. 이 프로젝트로 돌아오면 저장소·브랜치·최신 문서를 다시 읽는다. 직전 대화 기억보다 현재 파일과 근거 기록을 확인한다.

**최신 공유의 기준은 반영된 파일과 커밋이다.** PC에만 있는 변경, 대화에만 있는 결정, 전송하지 않은 로그는 다른 쪽에서 자동으로 알 수 없다. 파일을 수정하거나 이 ZIP을 해제한 것만으로 GitHub push 또는 ChatGPT 프로젝트 지침 변경이 완료되지는 않는다.

## 4. ChatGPT 프로젝트 지침에 추가할 문구

프로젝트 설정의 지침에 사용자가 아래 내용을 추가한다. 이 파일 생성만으로 해당 설정이 변경되지는 않는다.

```text
이 프로젝트의 공통 자료 원본은 GitHub Robot3FinalProject/main의 farm_project/다.
현재 코드·상태가 필요한 요청은 사용할 브랜치와 커밋을 확인하고
docs/PROJECT_STATE.md, docs/DECISIONS.md 및 관련 변경 문서를 읽고 답한다.
기본 기준은 main이며, 사용자가 작업 브랜치를 지정하면 그 브랜치를 사용한다.
코딩·실행 검증은 로컬 Codex, 세부 설계·기획·논의·자료 작성은 이 프로젝트에서 진행한다.
확정 설계는 결정 기록으로, 구현·시험 결과는 상태와 변경 기록으로 인계한다.
GitHub에서 읽지 못한 내용이나 PC에만 있는 변경은 확인했다고 말하지 않는다.
구현 완료, 사용자 확인, 과거 시험 기록, 이번 직접 검증, 미검증을 구분한다.
공통 코드 변경 승인 규칙과 sim 전용 파일을 sim 안에 두는 규칙을 유지한다.
파일 전달 시 다운로드 후 프로젝트 경로에 압축을 푸는 Bash 명령을 함께 제공한다.
```

공식 참고: [Projects and chats](https://learn.chatgpt.com/docs/projects), [Memories](https://learn.chatgpt.com/docs/customization/memories), [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md). 2026-10-06 확인 기준으로 ChatGPT Work와 Codex 대화 기록은 분리되어 있고, 로컬 Codex 메모리도 별도다. 문서 공유 절차를 대화 전체의 실시간 자동 동기화로 설명하지 않는다.

## 5. 작업 종료 시 남길 최소 기록

```text
일자(KST) / 담당 작업:
작업 시작 코드 커밋 / 종료 커밋(없으면 미커밋):
관련 결정 ID / 승인 범위:
변경 파일과 변경 이유:
실물·시뮬 영향:
실제로 실행한 검증 명령과 결과:
미실행 항목 / 실패 / 남은 문제:
로그·보고서·재현 조건:
다음 작업:
원격 반영 상태: 미반영 / push 완료 / PR 검토 중
```

PROJECT_STATE.md의 코드 기준에는 검토한 코드 커밋을 적는다. 문서 자신이 속할 미래 커밋 해시를 미리 쓰지 않는다. SHA가 없는 로컬 변경은 경로·내용·미커밋 상태로 표시한다. UTC 로그와 KST 보고 시각을 구분하고 ROS_DOMAIN_ID 등 실행 환경값은 각 세션에서 확인한다.

## 6. 이 문서 패키지 적용

ZIP 파일명: `farm_codex_handoff_20261006.zip`. ZIP 루트가 `farm_project/` 내부에 해당한다. 기존 AGENTS.md·README.md·시뮬 변경 이력을 갱신하고 인수인계 문서를 추가한다. 실행 코드·ROS 형식·USD·모델은 변경하지 않으므로 이 ZIP 자체를 적용하기 위한 colcon 재빌드는 필요 없다.

먼저 Codex가 같은 문서를 수정 중이라면 작업을 정리한다. 아래는 기존 파일을 백업한 뒤 적용하는 명령이다. 로컬에 별도로 편집한 문서가 있으면 백업본과 차이를 확인해 필요한 내용을 병합한다.

```bash
cd ~/main/farm_project &&
mkdir -p backups &&
tar -czf "backups/codex_handoff_before_$(date +%Y%m%d_%H%M%S).tar.gz" \
  AGENTS.md README.md docs sim/docs &&
unzip -o "$HOME/Downloads/farm_codex_handoff_20261006.zip" -d "$PWD"
```

적용 후 Codex 새 세션을 열어 갱신된 AGENTS를 읽게 한다. 파일 적용 결과는 `git diff`와 `git status --short`로 확인한다. 원격 반영은 별도 작업이다.


## 2026-10-20 공통 실행 정리

공통 실행 정리 패치 작성. PC ROS 검사 후 로봇 설치/무이동 검증이 남아 있다. 운영 설치본은 아직 변경하지 않는다.
상세 파일·검증 한계·복원 방법: `changes/HARVEST_COMMON_EXECUTION_20261020.md`. commit/push 없음.


## 2026-10-21 PC ROS preflight 수정

사용자 PC의 독립 설치·실제 ROS 타입 검사까지 통과했으나, WallGoalChecker에 일반 checker의 미선언 xy_goal_tolerance 등을 함께 요청하여 실제 ROS 계약 검사가 실패했다. 오프라인 대역이 누락 항목을 None으로 돌려주는 방식이어서 이를 놓쳤다. plugin 종류를 먼저 읽고 Simple/Stopped의 기존 키 또는 wall_alignment.*만 조회하도록 수정했다. 필수 벽 키가 없는 경우의 실패는 유지한다. 테스트 대역에 미선언 항목 전체 실패를 반영하여 수정 전 오류를 재현하고 수정 후 공통 주행/명시적 경로 26개를 통과했다. 일반 Simple/Stopped 검사와 허용오차 초과 거절도 확인했다. PC 실제 ROS 재검사는 전달 스크립트에서 수행하며 이 수정본의 실물 검증은 미완료다. 제어기·주행 수치·FSM 변경 없음. 원본/로그/독립 빌드 경로는 Downloads 하위다.


## 2026-10-21 윈도우 복귀 기반 구현(로컬, 미배포)

사용자 승인으로 기존 곡선 플러그인에 전진 우회전 역경로를 추가하고 harvest_robot.transfer_restore에 기준 저장/역원호/재진입 검사/공통 Navigator 완료 판정 연결부를 구현했다. 윈도우 2cm·저장 방향 1°는 초기 기준이다. 기존 벽/후진 설정·FSM은 유지한다. Python 172개, 양방향 C++ 이상 궤적 60개, 기존 후진 명령 동등성 4,545조건 및 벽 861 assertion 통과. ROS 빌드/실물 복귀 미검증. 벽 이탈·재진입 보정·운영 호출은 미연결이며 전체 복귀 완료로 취급하지 않는다. 원본/빌드/로그는 Downloads 하위. commit/push 없음. 상세: docs/changes/HARVEST_WINDOW_RESTORE_BASE_20261021.md.


## 복귀 플러그인 격리 ROS 검사 준비 — 2026-10-21

사용자 PC에서 복귀 기반 farm_arc_controller 빌드 및 CTest 2개가 통과했다. 실제 동적 로딩과 FollowPath 실행은 아직 검증 전이다.
기존 CommandGate에 direction 인자를 추가한다. 기본 reverse_left의 범위와 호출은 유지하며, 명시적인 forward_right에서만 속도 부호를 대칭으로 검사한다. 속도 상한, 시간 초과, 충돌 시 차단, 종료 차단은 유지한다.
검사 도구는 PC 전용 domain 95 / localhost / 고유 namespace에서 실제 controller_server와 공통 gate를 사용한다. TF와 odom은 이상 평면 모델이며 모터 속도 발행은 없다. 기존 후진 좌회전, 역경로 전진 우회전, Goal 취소 후 0 출력, 잘못된 경로 거절과 종료를 검사한다. 장애물 충돌 실험 및 하드웨어 성능을 입증하는 검사는 아니다.
벽 정렬 설정과 제어기, 곡선 충돌검사 및 주행 설치본은 변경하지 않는다. 복귀 기준 저장, 벽 이탈/재진입 실행, 전체 미션 연결은 후속 작업이다. 커밋은 사용자가 VS Code에서 진행한다.


## 전진 우회전 단독 실물 시험 준비 — 2026-10-21

사용자 PC에서 실제 Nav2 플러그인의 후진 좌회전/전진 우회전, 취소·정지, 변형 경로 차단과 정상 종료가 확인되었다. odom은 이상 모델이며 실물 시험은 아직 아니다.
기존 arc_isolated/arc_trial에 --return-from을 추가한다. 새 후진 성공 기록의 원호를 역순으로 사용하며, 부팅 ID 및 odom publisher GID, 설정 해시, 곡선 설정과 경로를 확인한다. 오래된 기록과 재시작한 odom 기록은 거절한다.
복귀 시작 자세는 기존 endpoint 8mm 및 방향 1도 이내여야 한다. 복귀만 임시 goal checker를 0.5도로 설정하고 정지 후 출발점 8mm/1도를 판정한다. 기본 후진 profile과 벽 정렬은 유지한다. 공통 Navigator/Nav2Client/MotionMonitor/CommandGate 및 check_grid/check_motion을 재사용한다.
실측 속도 감시는 부호만 반전해 동일 한도를 사용한다. 역경로와 현재 시작 자세를 기존 footprint·costmap으로 검사하며 Nav2 실시간 충돌 검사도 유지한다. 판정 실패 시 자동 자세 복원이나 충돌 임계 완화는 없다.
단독 시험은 후진 곡선 직후 벽 접근을 하지 않은 상태에서 복귀한다. 벽 이탈/재진입과 전체 미션 연결은 후속 단계다. 백업·빌드·기록은 Downloads에 저장하며, 준비 스크립트는 실제 이동을 실행하지 않는다.


## 복귀 전체 순서 검증 후보 — 2026-10-21 패키지명

사용자 승인: 코드와 검증 준비 후 실물 실행. 기존 보존 스냅샷에서 후보를 작성했으며 최신 원격 Git 대조·커밋·로봇 적용은 하지 않았다.
출발 기준 저장 → 기존 후진 좌회전 → 기존 벽 정렬 → StationReverse 기반 RPP 후진 → 기존 SpinClient를 통한 재진입 방향 맞춤 → 기존 ArcController 전진 우회전 순서다.
공통 Navigator/Nav2Client/MotionMonitor와 정지 확인을 재사용한다. 새로운 모터 제어기와 펄스는 추가하지 않는다. 벽 성공 설정과 곡선 충돌 검사 원본은 유지한다.
동일 cycle/odom 세션·직전 성공 결과 해시·정지 이후 자세·단계 순서를 확인한다. 재시작/실패/진행 중 기록은 자동 재시도하지 않는다. 출발 시점 map/odom 자세를 저장하며 마지막 위치는 저장한 map 자세 기준 2cm/1도다. 그래프 윈도우 도착 판정과는 별개인 시험 기준이다.
RPP 후진의 중간 방향 허용은 15도이며 뒤따르는 Spin 재진입 기준은 1도다. 벽 정렬 0.5도 기준은 유지된다.
직접 수행: Python 단위/회귀 및 구문 검사. 실제 ROS, 실제 장치, 전체 실행 도구 E2E는 미실행. 격리 ROS 검사도 실제 벽 제어 단계 대신 이상 모델 위치를 설정하므로 전체 미션 E2E로 표현하지 않는다.
이번 배포물은 Downloads 안에서 후보를 빌드·검사하는 용도다. 기존 소스/설치본을 적용하지 않으며 실물 실행 래퍼는 차단한다. 되돌리기는 후보 폴더 삭제만으로 충분하다. 다음 단계는 PC ROS 검사 결과 확인 후 전체 실행 경로 검증이다.

수정 기록 — 2026-10-21: PC에서 ROS Python 경로 덮어쓰기와 실제 StationReverse 플러그인 계약 불일치가 발견되어 ROS 동작 검사는 시작되지 않았다. ROS 환경 경로를 보존하며, 기존 farm_nav2_controller::ReverseRegulatedPurePursuitController를 선택한다. 기존 C++ 구현은 수정하지 않는다. 회전 속도는 격리 후진 gate 범위에 맞춰 0.03rad/s로 설정한다. 두 플러그인 패키지를 독립 빌드하고 로딩 prefix를 검사한다. 전달하는 station_reference.json을 직접 사용하는 설정 생성/오류 플러그인 차단 회귀 3개를 추가했다. ROS 결과는 여전히 미확인이다.

2026-10-21 v3: 사용자 PC의 v2 결과는 후진/회전/복귀/취소/잘못된 경로/후진 충돌까지 통과했으나 기본 Spin에서 비영 명령 후 충돌 중단으로 전체 실패했다. 기본 Spin 자체를 수정하거나 무출력 통과로 간주하지 않는다. 기존 check_grid를 alignment_clearance로 재사용해 회전 요청 전과 전달 전 남은 회전 footprint를 검사한다. 기존 SpinClient를 실제 ROS 정상 회전 검사에 사용한다. 장애물 사전 거절과 사전 검사 우회 고장 주입에서 실제 모델에 전달되는 비영 명령 0회를 별도로 요구한다. 원본 Spin 비영 명령 수를 숨기지 않고 기록한다. 9개 PC ROS 검사는 아직 미실행이며 전체 실행 도구 E2E/실물 배포는 보류다. 데이터 갱신 사이의 장애물 변화까지 무조건 방지한다고 주장하지 않는다.


## v4 footprint 좌표 입력 수정 — 2026-10-21 패키지
사용자 PC의 v3는 기존 후진 좌회전과 RPP 후진 뒤 ‘중심 대칭 사각 footprint 확인 실패’로 중단했다. 전체 성공으로 취급하지 않는다.
원인 후보를 코드로 재현했다: world footprint의 발행 시각과 현재 자세가 다른 상태로 역변환하면, 2mm 이동 또는 0.004rad 회전만으로 같은 오류가 발생한다. 사용자 로그에는 두 입력의 원시 시각/좌표가 없어 현장 실패의 시차를 확정한 것은 아니다.
회전 검사에서 costmap의 차체 좌표 footprint 및 padding으로 현재 자세의 형상을 구성한다. 발행 polygon은 시각·frame·크기 일치 검사에 계속 사용한다. 점간 거리 비교만으로 과거의 위치·방향과 현재 자세를 섞지 않고 동일 형상인지 확인한다. 설정/발행 형상 크기 불일치는 차단한다. arc_clearance/check_grid와 사각형 허용 오차, 장애물/unknown 차단은 변경하지 않았다.
실행 후보와 PC ROS checker 모두 같은 alignment_footprint/alignment_clearance를 호출한다. 실제 costmap 파라미터를 조회하여 검사 설정과 대조한다. 실행 후보는 odom/footprint 기준 frame이 다르면 공통 PoseProvider로 평면 원점/축 일치를 확인하며 다른 회전 중심을 추정해 통과시키지 않는다.
직접 검증: 기존 오류 재현 3조건, 발행 자세 지연 조합 200조건의 정상/장애물/unknown 검사, padding 영역 접촉 차단, 형상 변경 차단, 실제 checker 콜백을 추출한 실행 검사, 기존 회귀·구문 검사. ROS Jazzy가 이 작업 환경에 없어서 v4 실제 ROS 9항목은 미실행이다. 사용자 PC에서 그 검사를 수행하도록 패키지를 제공한다. 전체 도구 E2E 및 실물 복귀는 미검증이며 실물 실행 래퍼는 계속 차단한다. 기존 프로젝트/설치본 수정, 로봇 접속, commit/push는 하지 않았다.


## 실제 실행 도구 연결 검사 준비 — 2026-10-21
사용자 PC에서 v4의 실제 ROS 9개 검사가 통과했다. 후진/재진입 Spin/전진 복귀와 충돌 전달 차단 및 정상 종료가 확인되었다. 모델 odom이며 실물·전체 실행 도구 E2E는 아니다.
실제 arc_trial.py의 릴레이·watchdog와 restore_sequence.main 호출 경계를 추가 검사한다. 벽 이후 retreat 선택, 단계별 plan/execute 명령, 기록 변경·잘못된 cycle·실패·정지 미확인 시 다음 요청 차단을 확인한다. 하위 프로세스 응답을 대역으로 주입하는 순서 검사와 실제 ROS를 구분한다.
arc_trial.py의 기존 속도 전달 검사에 6축 유한성 검사를 추가한다. 사용하지 않는 축의 NaN도 0 출력 후 차단한다. 기존 공통 Navigator/Nav2Client/PoseProvider/MotionMonitor/SpinClient와 충돌/속도/정지 기준은 유지한다.
새 PC 검사에서는 복사한 모듈 함수 대신 후보 arc_trial.py를 별도 프로세스로 실행한다. 새 departure plan/execute로 세션·map/odom 기준을 기록한 후 벽 종료 자세 fixture, retreat plan/execute, align plan/execute, return plan/execute 및 장애물 plan 거절의 9항목을 요청한다. 기존 v4 C++ 소스가 동일할 때만 통과한 독립 설치본을 재사용한다.
범위 제한: 검사 노드가 모의 odom/TF와 이상 명령 적분을 제공한다. velocity_smoother 노드는 timeout 파라미터 계약 대역이며 실제 smoother/드라이버 시험이 아니다. wall 단계와 arc_isolated 감독 프로세스는 이번 ROS 검사에서 실행하지 않는다. 순서 관리 도구의 프로세스 경계는 오프라인으로 검사한다. 따라서 전체 복귀 E2E/실물 검증 완료로 표시하지 않는다.
직접 수행한 검증은 패키지 OFFLINE_VERIFICATION.json 참조. 새 실제 runtime ROS 검사는 사용자 PC에서 수행해야 하며 이 환경에는 ROS가 없다. 설치본/사용자 Git 소스 적용·로봇 접속·커밋 없음. 모든 산출물은 Downloads 하위. 실물 실행 래퍼의 차단은 유지한다.


## 전체 실행 연결 검사 후보 — 2026-10-21 패키지

사용자 PC의 실제 arc_trial.py 별도 프로세스 9항목이 통과했다. 성공 기록은 /home/eunbi/Downloads/harvest_restore_runtime_check_xHZnQV이며 runtime SHA256은 ae9a8c0b98ece07e4ee0a0f1104dbb9de705d259b87b2ccf6bb719d57a0de97f다. 벽 종료 fixture와 smoother 파라미터 대역을 사용한 결과이므로 전체 연결/실물 결과로 확대하지 않는다.

사용자 ‘준비해’ 승인으로 Downloads 후보에서 실제 restore_sequence.py → arc_isolated 감독/벽 실행 → 기존 Navigator/Controller → 실제 velocity_smoother 연결 검사를 준비했다. 기본 실물 Bash의 domain 77 및 설치 경로는 그대로 유지한다. 명시 HARVEST_PC_CHECK=1에서는 domain 95/localhost/FastDDS, Downloads 후보·독립 플러그인 설치 경로와 Python 모듈 위치를 확인하고 사전 로딩 환경을 사용한다. PC에서 실물 domain으로 빠지는 것을 막는다. 실물 restore_sequence.bash 차단은 유지한다.

검사 순서: departure/wall/retreat/align/return 각 plan/execute 10항목 및 footprint 장애물 departure plan 거절 1항목. 기존 상태/증명 파일을 실제 순서 도구가 생성한다. 벽 종료 위치를 강제 설정하지 않고 이상 평면 환경의 LaserScan을 기존 WallTracker/WallController가 처리한다. 실제 CLOSED_LOOP velocity_smoother 출력을 이상 모델에 적분한다. 지도·TF는 PC 검사 전용이며 실물 지도/모터 성능을 검증하는 것이 아니다.

기존 성공 후보/상세 결과를 새 검사 폴더의 preserved_success에 복사하고 파일 해시를 기록한다. 이전 v4와 두 C++ 패키지 소스 일치 시 독립 설치본을 재사용하며 벽 플러그인만 새 Downloads 설치본으로 빌드한다. 기존 제어기, arc_trial, 공통 주행 코드, 충돌/속도/정지 기준과 성공 벽 설정은 변경하지 않았다.

직접 수행: 오프라인 회귀 238개 PASS, Bash/Python 구문 검사, 성공 핵심 5파일 해시 보존, 실제 wrapper의 잘못된 domain 진입 차단. 실제 ROS 전체 연결은 이 환경에 Jazzy가 없어 미실행이다. 사용자 PC 실행 결과 전에는 완료로 간주하지 않는다. 프로젝트 적용/로봇 접속/실물 이동/커밋/원격 Git 검증 없음. 후보 삭제로 되돌릴 수 있다.


## 출발 기준 TF 시각 수정 — 2026-10-21

사용자 “확인하고 확실하게 고쳐와서 말해” 승인. 독립 Downloads 후보만 변경한다. 정지 확인 시각이 TF 버퍼보다 45.223ms 이른 실물 plan 실패를 확인했다. PoseProvider.lookup_available_pair는 기존 lookup을 재사용하여 진행하는 odom 표본 중 map/odom을 같은 시각에 조회할 수 있는 표본을 선택한다. TF가 지연될 때 최신 표본만 추격하지 않도록 유효 기간 내 표본을 보관한다. 시각 역행, 오래된 표본, 정지 상실, 다른 Action, TF 누락은 실패한다. 출발 경로 원점도 저장한 odom 자세와 일치시킨다. 기존 lookup/current 및 도착 판정 호출, 컨트롤러, 충돌/정지/속도 기준은 불변이다. 최신 TF 두 개를 독립 조회하는 대체 동작은 없다.

로컬 검증은 대역 TF 버퍼 및 기존 회귀이며 실제 ROS/실물 결과가 아니다. 배포 전 PC Jazzy tf2 Buffer 검사, 로봇 적용 후 설치 위치 및 무이동 departure plan 검사를 요구한다. 해당 결과가 나오기 전 실물 해결 완료로 표시하지 않는다. Git 커밋/푸시 없음. 원본 및 진입 도구 해시는 Downloads 백업으로 보존한다.


## 2026-10-23 수확 인계 지연 재조사 (PC 확인, 로봇 인증 대기)

HEAD `4b5c5b13605216d1b8b163ea988805572a6a908a` 및 기존 미커밋 변경 기준. PC에는 body_trial/locking/window/transfer_sequence 일부가 없으며 최신 현장본으로 간주하지 않는다. SSH 서버 접속 후 인증 거절로 로봇 현재 소스·설치본·patch state는 미확인이다. Downloads의 최신 capture를 직접 읽어 odom 만료 실패를 확인했지만 긴 runtime lock 점유를 원인으로 확정하지 않았다. fixed 적용 없음.

사용자 요청에 따라 `robot/tools/transfer/handoff_diagnostics/`에 읽기 전용 수집·외부 관측·내부 계측 제안 생성 도구를 추가했다. 운영 코드/설정 변경 없음. 이번 오프라인 검사 6개와 ROS 메시지 import 통과, 실기/DDS 미검증. 전체 인계 완료·팔 시험 완료 아님. 상세 호출/잠금 표, 변경·원복·로그·후속 절차: [HANDOFF_DELAY_AUDIT_20261023](changes/HANDOFF_DELAY_AUDIT_20261023.md). Git commit/push 없음.


## 2026-10-23 직접 로봇 수정·실기 확인 후속

로봇 SSH 접근 확인. fixed 위 수확 전용 입력 계측 및 선택형 전용 TF node/executor를 적용·빌드했다. 주행용·상태용 TF buffer는 독립 유지한다. 같은 시각 외부 TF는 최신인데 기존 buffer만 약2.95초 오래된 증거를 확보했고, 전용 문맥의 이번 이동 구간 최대 age는 약0.077초였다. 허용시간·공통 PoseProvider·충돌 조건 변경 없음.

PC→Zenoh→HarvestTask window 이동 1회는 일반 controller의 collision ahead/status6/error106으로 실패했다. 사용자 실제 정지 확인. window 미도착이므로 body enter/restore 미호출, 전체 인계 미완료/팔 미시험. 수정 소스 동시성20·계측3·기존 인계64 검사 및 무동작 ROS TF 문맥 검사 통과. 원본 백업/원복/실기 로그는 [상세 기록](changes/HANDOFF_DELAY_AUDIT_20261023.md). PC 운영 소스를 로봇본으로 덮어쓰지 않았다. commit/push 없음.

## 2026-10-23 17:53 코너 비교 이동 후 상태

카메라만 복구하고 기존 정지 위치에서 1회 window 이동: SECTION_APPROACH/WINDOW_MOVE/최종 Action SUCCESS. 위치오차2.13cm, yaw오차0.01224rad. 속도 명령과 odom에서 전진·회전 복합 동작 확인. 해상도/footprint 수정 없음. 현재 window 위치이며 스테이션 초기 좌표를 보내면 안 된다. body enter/restore 미실행, 팔 미시험. 태그 보정 적용은 확인되지 않았고 control 거절 이벤트가 있어 별도 조사 필요. 상세 증거·bag 종료 한계는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md의 최신 절. commit/push 없음.

## 2026-10-23 18:00 인계 시험 후 상태

body enter 1회: 동일 시각 TF/경로 준비 통과, 인계 controller goal 수신 및 실제 회전 후 곡선 속도 입력 시간 초과로 RECOVERY_REQUIRED. controller 취소 성공·실측 속도0·사용자 정지 확인. 현재 map=(1.10706,-.04465),yaw=.62728rad, ERROR/ready=false. window 도착 당시 자세와 다르므로 자동 restore/enter/initialpose 금지. 원인 후보는 fixed 검사 후 속도 승인 공백이며 raw 속도 미수집으로 확정하지 않음. 상세 증거/단계 시각/계측 한계: docs/changes/HANDOFF_DELAY_AUDIT_20261023.md. 팔 미시험, 전체 인계 미완료, commit/push 없음.

### 2026-10-23 정지 유지 오프라인 후속

현장 fixed의 snapshot identity 변경 거절로 정상20Hz 명령/최신 odom 상태에서도 .3초 승인 공백 오류가 발생할 수 있음을 실제 메서드 오프라인 주입으로 재현. 실기 원인 확정은 아님. 출력 수신/거절/승인/expiry 계측 v2를 별도 준비, 제어 AST 동일 및 곡선·벽·정지 회귀6개 PC/로봇 통과. 운영 미적용, 재시작/이동 없음. 기존 RECOVERY_REQUIRED 유지. 상세: docs/changes/HANDOFF_DELAY_AUDIT_20261023.md.


### 2026-10-23 성공 독립 시험 대비 구조 대조
공통 Navigator 사용 후 독립 곡선·벽 정렬 실기 성공 원본을 확인했다. 성공 설정 대비 곡선 관련25개/주요 costmap8개는 동일하며 전체 서버 설정은 차이가 있다. fixed의 검사 중 센서 객체 변경 거절은 이전 출력 경로에 없던 조건이고 승인 공백을 만들 수 있다. 실제 실패 직전 연속 거절 여부는 raw 기록 누락으로 미확정이다. 상세는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md의 마지막 절 참고. 이번에는 읽기 비교·증거 보존·문서만 추가. 운영 코드/프로세스/위치 변경 없음, 전체 인계 미완료, commit/push 없음.


### 2026-10-23 센서 갱신 출력 수정 후보 검증 완료
사용자 승인으로 현재 현장 원본 기준 departure/return/retreat의 객체 동일성 거절을 최신 입력 유효성 재검사로 변경한 별도 수정본을 작성했다. 취소·정지·epoch/소유권 검사는 유지. PC/로봇 회귀20개, 로봇 격리 빌드 및 기존 인계64개 통과. window/align/wall 보호는 기존 유지하며 전체 시퀀스 해결은 미확인. 운영 소스/설치본에는 미적용, 프로세스 재시작·이동 없음. 산출물 sensor_commit_fix_v1 및 적용/원복 경계는 HANDOFF_DELAY_AUDIT_20261023.md 마지막 절. 기존 핫픽스11개/patch state 보존 확인, commit/push 없음.


### 2026-10-23 18:39 KST 운영 적용 완료
사용자 승인으로 sensor_commit_fix_v1을 로봇 소스·운영 install에 적용/빌드하고 수확 노드만 PID51504→85474 단독 재시작했다. AMCL/Nav2/드라이버/Zenoh 유지. 기존 핫픽스·state 보존 및 설치본 전체 백업 완료. body IDLE, 일반 ready=true이나 window 기준은 소실되어 재도착 필요. 현재 x1.107109,y-.044614,yaw.627572, odom0. 이동/초기위치/enter/restore 요청 없음. 자동 스테이션 복귀 미설정. 단독 PID85474는 원래 launch 자식이 아니므로 다음 전체 종료 시 별도로 정상 종료할 것. 상세 백업/원복/로그는 HANDOFF_DELAY_AUDIT_20261023.md 마지막 절. 전체 인계 실기 미완료, commit/push 없음.


### 2026-10-23 18:44 window 재확보 실패 — 정지 유지
사용자 승인1회 요청은 수락됐으나 이동 전 APPROACH_RECOVERY_REQUIRED(body_heading,path_heading)로 실패했다. corridor 내부에서 현재 약36° 자세가 직선 접근 계약과 맞지 않아 SECTION_APPROACH로 우회되지 않았다. 위치 동일/odom0, window 기준 미확보. PC는 최신 상태 미수신으로 전송 전 종료, 실제1회 Action은 로봇 로컬에서 전송(Zenoh ON). PC 통신 정상 검증 아님. 상세 HANDOFF_DELAY_AUDIT_20261023.md 마지막 절. 재이동·인계 enter 없음.


### 2026-10-23 현재 자세 복구 후보 준비(미실행)
현재 자세에서 시계방향35.96°회전→6.11cm후진→window14cm전방 접근 후보를 계산했다. 실제 snapshot에서 회전/후진 footprint 검사 및 후진 자세의 기존 straight_plan 통과. 동적 안전/실기 검증 아님. IDLE에서 부분 복구할 기존 서비스가 없으므로 단일 출력/취소 보호를 갖춘 명시적 연결 및 검증 후에만 실행 가능. 안전 설정 변경·이동 없음. 상세 HANDOFF_DELAY_AUDIT_20261023.md 및 recovery_plan_v1/RECOVERY_PLAN.md.


### 2026-10-23 부분 복구 실행 연결 후보 완료
사용자 승인으로 recovery_connection_v1에 opt-in start/stop/status 서비스 및 정확한 복구 토큰/취소 commit 검사를 구현했다. 약36°를 기존15° 제한 내12°씩3회 정지 검증 후 후진, 최종 work._plan_current 통과 시 READY_FOR_WINDOW만 보고. window 성공 모사 없음. 정지 미확인은 소유권 유지. 신규23+기존64=87개 및 출력22개, 보존 grid preflight/격리 빌드 통과. 운영은 기존 PID85474/센서 commit 수정본 유지, 복구 후보 미적용·이동 없음. align 승인 고갈 가능성·실기 미검증은 남음. 상세 HANDOFF_DELAY_AUDIT_20261023.md 및 recovery_connection_v1/IMPLEMENTATION_NOTE.md.


### 2026-10-23 19:14 스테이션 재주행 중단
사용자 스테이션 재배치 후 기존 initialpose 설정 및 정지 scan/map 정합 확인. 일반 window 이동1회는 시작 후 약.9초 제자리 회전(v0,w.1)에서 collision ahead/status6/error106으로 중단. window 기준 미확보/인계 미실행. 최종 odom0, 스테이션 부근 자세 유지. 복구 후보 미적용, 센서 commit 운영본 유지. 실패 순간 costmap/예측 arc/속도 bag 확보, 반복 이동 없음. 상세 HANDOFF_DELAY_AUDIT_20261023.md 마지막 절.


### 2026-10-23 19:21 일반 local costmap 정지 초기화 비교
사용자 수동 재배치/costmap 잔상 제안 확인. 실패 당시 회전 footprint 충돌 셀과 실제 scan 차이 확인 후, IDLE/odom0에서 일반 local costmap만1회 초기화하고6초 재생성 비교. 셀254→253, 동일 회전 경로 오프라인 충돌→통과. 잔존 정보 영향 근거 확보, 비상정지 자체 원인은 미확정. 초기위치 재발행/재이동/인계 없음. 상세 HANDOFF_DELAY_AUDIT_20261023.md 마지막 절.


### 2026-10-23 19:29 window 재주행 성공
일반 local costmap 초기화 후 사용자 승인1회 이동 최종 SUCCESS. 현재 window 위치(1.15805,-.03114), yaw.01863rad, 목표 오차2.82cm/1.07°, IDLE/odom0 확인. Zenoh ON/요청은 로봇 로컬. 초기위치 재발행·복구 후보 적용·안전 설정 변경 없음. 인계 enter/restore 미실행, 팔 미시험. 근거/한계/로그는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. 문서·수집 자료만 갱신, commit/push 없음.


### 2026-10-23 19:33 차체 인계 후 정지 유지
사용자 승인 enter/restore 각1회. departure·wall 완료/ENTERED 및 정지 확인 후 restore. retreat와 Spin 제어기는 성공했으나 align 정지 후 재진입 검사 실패: RECOVERY_REQUIRED. 전진 복귀 미시작. odom 재구성 위치오차 약8.77mm(한계8mm), 방향약.70도(한계1도); 정확한 runtime reference 미노출로 재구성 근거임을 구분. map=(1.059564,-.124540),yaw1.648618, odom0 및 사용자 현장 정지 확인. 재진입/초기위치/추가 이동 없음. Zenoh ON, 팔 미시험, 전체 인계 미완료. 안전조건/운영 코드 변경 없음. 상세·로그·잔여 범위: docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 복귀 재진입 정책 후보 검증 완료(운영 미적용)
사용자 승인으로 현장 최신본 백업 후 reentry_policy_v1 별도 후보4파일 수정. 재진입 위치는 선택형 설정으로 분리하여 body_trial만10mm, 기존 사용처/출발·최종 곡선8mm/방향·정지·충돌·출력 보호 유지. 현재 자세→원호 시작점 충돌 검사 추가, controller 원형 경로는 불변. PC/로봇 신규18+기존64=82개 및 출력20개 PASS, 로봇 격리 빌드/설치 해시 확인. 보존 costmap/실제 C++ 제어식 이상 모델로 다음 복귀·window 보정 계약 통과했으나 최대 이탈9.55mm로10mm 대비 여유가 작아 실기 성공은 미확정. 운영152파일 및 기존 핫픽스 상태 보존. 재시작/이동 없음, RECOVERY_REQUIRED 정지 상태 유지. 상세·초기 시험 실패·원복 경계는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 19:55 재진입 정책 적용/재배치 대기
사용자 승인으로 reentry_policy_v1 원본4파일·운영 설치본 백업 후 PID85474 정상 종료,4파일 적용 및 harvest 빌드/설치 해시 일치 확인. 기존 핫픽스 상태/백업 유지. 수확 노드는 아직 미기동, 기존 launch·Zenoh·AMCL/Nav2/드라이버 유지. odom0/cmd_vel_nav publisher0/사용한 Action terminal 확인 후 사용자에게 비상정지 유지하여 스테이션 재배치 안내. 재기동 검사 도구 CHECK_ONLY_OK, 실제 기동/초기위치/이동 없음. 다음은 재배치 확인 후 재기동·정합·costmap 확인·window 재확보. 상세 백업/원복은 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:05 수정본 재기동·스테이션 정합 확인
사용자 스테이션 재배치 확인 후 수확 PID129702 재기동, 기존 초기좌표 설정. scan/map 중앙오차6mm/p90 2.17cm, odom300개0, 중첩 그림 확인. 일반/인계 local costmap의 현재 차체 및 +.1rad 회전 검사 통과하여 이번 clear 미실행. cmd_vel_nav/odom publisher각1개, IDLE/ready·body IDLE, 전용TF 유지. 전체 경로/비상정지 해제/실기 이동 안전 보장은 아님. 주행·enter/restore 미요청, window 기준 재확보 필요. 상세 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:11 수정본 일반 window 재주행 성공
사용자 승인 단발 window 이동 status4/SUCCESS. 현재(1.156699,-.037115),yaw-.007667rad, 목표 오차2.94cm/.44도, IDLE 및 odom31표본0. PID129702/Zenoh 유지, 요청은 로봇 로컬. bag·외부/내부 계측 마감 보존. body IDLE, enter/restore 미요청. 재진입10mm 수정의 실기 검증은 아직 아님. 초기위치 재발행 금지, 인계 전 안내. 상세 HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:15 전체 차체 인계 실기1회 완료
사용자 승인 enter/restore 각1회. 적용10mm 재진입 정책·Zenoh ON 상태에서 후진 곡선/벽 정렬/후진 이탈/Spin/전진 복귀/최종 window 도착 검증 COMPLETED. 추가 window 보정 이동은 없었음. 최종(1.184048,-.028186),yaw-.002234, 관제 goal오차7.09mm/.128도; IDLE·최근odom30표본0 별도 확인. bag 재구성 재진입오차6.08mm로 기존8mm 이내여서8~10mm 실기 통과·완화의 인과 효과는 아직 미확인. 팔 NOT_TESTED, 반복신뢰성/PC관제왕복/타로봇 실기 미검증. 현재 body COMPLETED이므로 자동 enter 반복 금지. 로봇 body-reentry-policy-nVLFxOy9 및 PC body_reentry_policy에 로그/분석 저장. 상세 HANDOFF_DELAY_AUDIT_20261023.md 최신 절. commit/push 없음.


### 2026-10-23 21:31 인계 후 그래프14 일반 주행 연속 시험 성공
사용자 요청으로 관제 웹을 직접 조회: #59/25fabab7b348_SEC01_TASK001(표시 목표1.601,-.035)은21:25:15 대기열 등록 후 Action 전송 전. 수확 Action 서버 대기, 인계 수확Status는18:38:38의 이전boot ERROR/CANCEL_UNCONFIRMED에 정체되어 최신 로봇IDLE/ready와 불일치. 지도 위치 수신은 최신이었다. 근본 통신 원인 미확정. 이후 화면에서 해당 작업의 전송 전 취소 및 수확 대기열 일시정지 확인(에이전트가 취소 버튼을 누르지 않음).
사용자 “일단14번 노드로” 승인으로 실제 graph.geojson 노드14=(3.576,-.035) 읽고 yaw0, expected_count0 시험 HarvestTask NODE14_79189ba30dfe_TASK001을 로봇 로컬에서1회 요청. 현재 위치·정지 확인 및 경로 안내 후21:30:03 수락→21:30:43 status4/SUCCESS. 실제 SECTION_RESUME→WINDOW_MOVE→ARRIVED, 현 위치에서 목표까지2.392278m 직선 FollowPath(reverse=false, graph edge_ids=[]); 그래프 전체 경로 추종 시험으로 확대 해석하지 않는다. 도착 판정오차28.060mm/.5154도, 최종Status(3.550325,-.023535),yaw-.009290;21:31 IDLE/ready 및 최근odom30표본 전부0. PID129702/Zenoh 유지, 재시작·초기위치·코드/안전설정 변경·추가 인계 없음.
새 시험 goal의 arrival와SUCCESS 이벤트를 확인. 현재 communication.py의 remember_window→handle.succeed 순서에 근거하여 새 기준 저장 경로 완료를 판단했으며 메모리를 직접 조회한 것은 아니다. body-only 팔 NOT_TESTED. 인계 완료→일반 주행 전환1회는 실기 확인했으나 관제 웹 다음 실제window 전달은 미완료이며 후속 인계 반복 검증도 별도다.
로그: 로봇 runs/handoff_diagnostics/web-next-window-AiZhUerb (bag 정상 마감, 외부 계측), 하위node14/goal.json,action.log,final.json; PC runs/handoff_diagnostics/20261023_review/web_next_window에 웹 관측과 단발 결과 보존. 기존 핫픽스/백업 보존, 문서만 추가, commit/push 없음. 원복할 운영 변경 없음.


### 2026-10-23 실기 성공본 PC 커밋 준비
사용자 승인으로 로봇 실행/설치 출처 대조 후 최신 핫픽스25파일을 PC에 반영. 기존 dirty 원본 및 시험/로그/백업은 /home/eunbi/vmany_artifacts/handoff-success-20261023-commit-prep에 보존. 관련 없는 예찰/Burger 차이 및 기존 추적 시험 보존. 성공 실행의 dedicated TF 환경 선택과 body-only 프로필을 문서화. 이번 PC 오프라인64+18+20검사,4패키지 격리 빌드 통과. 인계→일반주행 실기1회 성공이며 웹 관제 전달/반복/팔 검증은 미완료. 운영 로봇 변경/이동/commit/push/staging 없음. 상세 docs/changes/HANDOFF_SUCCESS_COMMIT_PREP_20261023.md.


### 2026-10-23 PC Jetson 더미 준비
Git 밖 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023에 문서계약 대역 생성. Domain177 실제 ROS15검사 통과, 원본 Pinky 클라이언트 사용. Domain77/실기/Jetson 실제 연결 미실행, 운영코드 불변. 상세 HANDOFF_DELAY_AUDIT_20261023.md 최신 절.

PC 대역 잔여 종료 경고 후속 수정: 설치 rclpy의 worker/guard 종료 경쟁과 SIGINT 중 Task 부분 초기화를 재현. 외부 대역에서 worker 먼저 join 및 신호 Event 요청으로 수정. 종료 경합 수정10회·신호 비교 검사 및 실제 ROS 통신15개/서버 종료 로그 검사 통과. 근거 외부 shutdown_regression_final.log, shutdown_fixed_final2.log, validation-b07b566c. 운영 성공본·ROS 설치 파일 불변, 실제 연결 미수행. 비공개 executor pool 의존과 원복 절차는 외부 README에 기록.

22:18 후속 실제 정지 통신 시험: PC177 시험 arm→허브→로봇77 서비스/Discharge 완료·취소 통과. 로봇 시험 클라이언트의 명시적 DDS peer 추가 필요, 운영 설정 불변. 최종 odom193개 비정지0, 원래 PID/출력소유권 유지, 시험 프로세스 종료. 단일 요청에 추가 Goal 거절 로그가 남아 bridge 중복 경로 미해결. 웹은 운영 Action 연결 대기로 바로 시험 불가. 실제 이동/인계/팔 시험 아님. 외부 connection_prep/RESULTS.md 및 audit 최신 절 참조.

22:35 사용자 승인 bridge 재시작 후 웹 수확 연결 복구. 후보 static-peers 배열 형식 오류로 기동 실패해 자동 원복, 원래 설정의 bridge157041 재기동으로 harvest/복귀/인계 Action·이벤트 및 현재boot Status 갱신 확인. 수확129702/params/관제 코드 불변, odom0/속도 publisher1개, 이동 없음. 후보 성공 아님/이전 배열 후보 사용 금지. 재발 방지·중복 전달 미해결. 외부 bridge_restart_20261023/RESULT.md 참조.


### 2026-10-23 22:47 중복 Action 전달 생성 지점 확인
운영/관제 변경 없이 거절 전용 진단. 기존 경로 및 PC 단독 loopback bridge1.10.1에서 재등록마다 단발 Goal 전달1→2→3회, PC 진단 client bridge 재시작 후1회. client bridge DDS→Zenoh 구간에서 같은 request ID 중복 확인. background matching listener 수명 누적 유력, 세부 수정 비교 미실행. 운영PID129702/157041·설정·웹 최신연결 유지, 이동/운영Action 없음. 다음은 외부 bridge 후보의 listener 소유/해제 수정 및 격리 검증 제안이며 운영 적용 전 알림 필요. 상세 HANDOFF_DELAY_AUDIT_20261023.md 최신 절 및 외부 duplicate_trace_20261023/RESULT.md. commit/push 없음.


### 2026-10-23 23:10 서비스 콜백 수명 후보 검증 완료(운영 미적용)
사용자 승인으로 Git 밖 bridge1.10.1의 route_service_cli1파일에 listener 소유/해제 및 종료후 재활성화 보호 수정. PC 격리 원본3회 중복1/2/3 재현→후보6회 모두1. 원본 server+후보 client bridge 혼합에서 무장치 Discharge 성공5/취소5, Goal별 실행1·cancel1·수신feedback 중복 없음, 총31 service 요청 전달1회. PC x86_64 dev 빌드이며 robot release/실제Jetson/이동 미검증. 운영PID/설정/웹 최신연결 유지, 운영 적용 전 안내 필요. 외부 bridge_callback_candidate_20261023에 원본·패치·소스·bin·로그·SHA 보존. 상세 audit 최신 절. commit/push 없음.


### 2026-10-23 23:25 ARM64 브리지 후보 적용 준비 완료(운영 미적용)
PC 격리 cross build로 동일 콜백 후보 ARM64 release 완료. 로봇 Downloads/zenoh_callback_candidate_20261023에 원본·설정·환경/manifest 백업, 별도 후보, 읽기전용 preflight/기본 계획출력 launch_saved 및 PROCEDURE 준비. 로봇 loopback178/179에서 재등록3회 중복0, 가상Discharge 성공2/취소2, 요청13개 각전달1 확인. 후보/백업 로딩 정상·임시프로세스 종료. 운영129702/157041·원본설정·웹최신연결 유지, 이동/운영교체 없음. 적용 전에 현장상태·PID/starttick 재확인 및 사용자에게 안내 필수. PC 외부 bridge_arm64_ready_20261023에 이중 백업/로그/SHA. 상세 audit 최신절. commit/push 없음.


### 2026-10-23 23:32 운영 후보 원복 — 웹 Action 연결 미복구
사용자 승인 후보172037로 전환했으나 최신Status만 갱신되고 웹수확/복귀/인계ready=false. 실패시원복 지시에 따라 백업원본PID172484로 복귀; 수확129702/원본파일/config/params 유지. 원복 후에도 웹ready=false·Status최신·odom표본0/속도publisher1. 관리action srv/cli active존재, 원인미확정. 바이너리원복과 연결복구를 구분. 운영후보 중복/Action완료취소 시험 미실행, 이동없음. 사용자 지적대로 통신규약/단독시험과 웹통합을 분리해 진행할 것. 근거 외부 bridge_live_apply_20261023 및 audit최신절. 과거PID157041 preflight 재사용금지, 현재backup/binary PID172484. commit/push없음.


### 2026-10-23 23:50 웹 없는 PC–로봇 더미 계약 검증
전용177/178·TCP직결로 로봇 설치 ArmActionClient/DischargeClient를 독립 노드에서 사용. 수확/배출 성공·취소 각1회, prepare/stop 왕복 및 취소후 준비거절 확인, service18요청 중복0. 첫2회 배출 OPENING누락 실패 보존; 시험도구 준비후2초 대기한3회차 세단계수신, 근본해결 주장 금지. 운영 성공코드·설정/PID129702·172484 불변, 사후odom151표본0/출력publisher1, 임시시험종료. 실제 harvest FSM 연결/Jetson/물리동작/ControlState·확장상태통신/웹통합은 미검증. 웹 ready 이전미복구 별도 유지. 외부 direct_contract_20261023/RESULT.md 및 audit 최신절 참조. Git에는 문서2개 기록만, commit/push 없음.


### 2026-10-23 수확 FSM 더미 연동 준비 — 미적용
기존 ARRIVAL_THEN_ARM/components+Discharge 설정을 이용한 별도 환경·JSON·실행params 후보 준비(운영 override 동시변경 필요). 실제 통신/미션/상태전환 모듈과 PC더미를 격리 연결하여 주행실패 차단·수확완료·취소후 이동차단 검증, 오프라인63개 통과. 주행/node/handle/window는 시험대역으로 실제 운영FSM 전체·차체 검증 아님. 성공코드/PID/config 유지, 이동·재시작·후보배포 없음. 적용/이동 전 사용자 안내 필요. 외부 fsm_prep_20261023/RESULT.md 및 HANDOFF_DELAY_AUDIT_20261023 최신절 참조. 웹·Jetson확장상태/복구 연동 별도 미완료. commit/push 없음.


### 2026-10-24 PC더미 실제FSM 설정 적용·정지연결 확인
승인된 별도후보3파일 적용, 원본설정/env/소스해시 백업보존. 수확129702→183972 재시작, ARRIVAL_THEN_ARM/전용TF 유지. PC더미122585·전용PCbridge122639/로봇bridge183672 연결, 기존운영bridge172484 그대로. 실제FSM clients 생성/IDLE-ready 및 팔·배출·준비·정지 탐색정상, odom452개0/출력publisher1, 더미작업0. 이동/장치요청없음. 적용유지, 이전window기준은재시작으로소실하므로 이후인계전재확보필요. 웹ready미복구/Jetson확장통신미완료 별도. 원복관리도구 및 근거는 외부 fsm_live_20261024/RESULT.md와 audit최신절. 원본성공코드 불변, commit/push없음.


### 2026-10-24 00:15 실제FSM window수확 성공(PC더미)
사용자승인 스테이션초기위치/정합·costmap확인후 window(1.186,-.035,0)단발이동. SECTION_APPROACH→WINDOW_MOVE→ARM, status4/SUCCESS 수확2/실패0,적재2는PC더미결과. accepted arrival37.65mm/1.71도 및 remember_window→succeed 경로로 새도착기준저장완료판단. 현재(1.148698,-.029448),yaw-.029599,IDLE/ready/odom452개0. 초기위치재발행금지. 인계·배출미요청, 다음인계전안내. 성공코드/PID/설정보존. 로봇fsm-window-20261024/bag 및 PC외부window_fsm_20261024/RESULT.md, audit최신절에근거. 실제팔·Jetson·웹 별도미완료, commit/push없음.


### 2026-10-24 00:24 인계실기보류·웹연결미완료
현재body_trial_enabled=true라운영DockTransfer거절(앞선후보준비누락). false별도프로필후보만준비,미적용. 웹양쪽Action/이벤트readyfalse,수확이전boot상태약20분/운송약24분정체. 로봇직접은최신IDLE/ready/적재2·수확인계서버존재. 주소/이벤트이름은맞지만웹전달미완료. 운송팀코드불변·요청안함,기존계약/연결만점검. 오프라인45PASS,실제인계/이벤트/재시작/이동없음. 외부dock_fsm_preflight_20261024/RESULT.md 및audit최신절. commit/push없음.


### 2026-10-24 로봇 터미널 별칭
~/.bashrc백업후mf_launch/mf_init_station/mf_zenoh/mf_dummy_zenoh/mf_env/mf_status추가. 실제기동/초기위치/이동없음,중복차단검증통과. 현재PC더미+body_trial설정선택이며운영인계/웹미복구는별도. 로봇 Downloads/manyfarm_terminal_20261024/README.md와 PC외부terminal_alias_20261024/README.md에순서·원복·한계. 기존성공코드불변,commit/push없음.


2026-10-24 사용자 요청으로 터미널 별칭을 laun/vinit/zen/dzen/vstat으로 단축했다. 기존 mf_env 유지, 이전 5개 별칭은 source시 해제. 로봇 aliases.before-short-names.bash 백업 및 PC 외부 사본 보존. 구문/별칭조회 통과, 실제 명령 실행·이동 없음. 기존 터미널은 source ~/.bashrc 필요.


### 2026-10-24 사용자 확정 실행·시험 절차
앞으로 실행을 동반한 확인/실기시험은 에이전트가 먼저 장비·터미널별 기동 명령을 순서대로 안내하고, 사용자가 직접 기동하여 웹페이지 연결을 확인했다고 알린 뒤 진행한다. 기존 실행 프로세스와 현재 위치를 확인해 필요한 명령만 안내하며 실행 중인 런치/브리지를 중복 기동하지 않는다. 로봇 별칭은 laun/vinit/zen/dzen/vstat, 기존 터미널 갱신은 source ~/.bashrc. vinit은 실제 스테이션 위치·방향일 때만 포함하며 현재 window에서는 생략한다. PC 더미 서버가 필요한 시험은 PC 측 기동도 별도로 안내한다. 웹 확인 전 자동 기동·재시작·이동·작업 요청은 하지 않는다. 읽기 분석/오프라인 검증은 계속 가능하다. 웹 연결 확인은 인계·운송측 물리 완료 조건을 대신하지 않으며 시험 범위와 이동 전 안내는 유지한다. 이번 합의 기록만 수행, 실행/이동/commit/push 없음.


### 2026-10-24 현재 실행 전부 종료·사용자 기동 대기
승인하에로봇시험20개와PC더미/bridge3개정상종료·잔존0확인. 관제/운송팀유지. 아직새기동/초기위치/이동없음. PC외부restart_terminal_20261024/pc.bash dummy→bridge,로봇laun→스테이션확인후vinit→zen→dzen 순서안내. 사용자웹연결확인후진행. 기존PID/메모리도착기준은현재사용불가. 상세audit최신절/외부README. commit/push없음.


### 2026-10-24 00:49 사용자 재기동 후 무이동 연결 확인
사용자 기동·웹 표시 확인 후 읽기 전용 점검. 수확 PID196363, 허브 bridge196825, 더미 전용 bridge196919. 웹 수확/복귀/DockTransfer ready=true, 수확 transfer_event ready=true. 두 GET 표본에서 수확 boot75bc730f2be04c3f894cfc7e7aac814e 동일, sequence399→402, age0.4초; 로봇 직접 sequence419와 boot 일치. IDLE/ready, task없음, loaded_count0, odom452개에서 x선속도/z각속도 비영0, cmd_vel_nav publisher harvest_motion_server1개. PC 더미 HarvestTask/Discharge/prepare/stop 탐색 모두 true; 장치 서비스나 Goal은 보내지 않았다.
운송측 Action/event ready=false, 상태 약49분 경과로 최신 상태 아님. 현재 handoff_body_trial.json body_trial_enabled=true 및 설치 transfer_communication.accept의 운영 DockTransfer 거절 확인. 따라서 서버 탐색 성공과 인계 요청 수락은 별개다. 인계 전 승인된 별도 FSM 프로필 선택·재기동, 새 window 도착/더미 수확, 운송측 연결 및 DOCK_STABLE/TRANSPORT_CLEAR 전달·물리조건 확인 필요. 웹 일반 대기열 paused=true 유지. vinit 로그의 초기추정 발행은 확인했으나 이번 scan/map 정합 검사는 미실행. 코드/설정/프로세스 변경·이동·이벤트 요청·commit/push 없음. 웹 요약 근거 /tmp/web-readonly-20261024-sanitized.json, 로봇 로그 /home/vic/vmany-terminal-logs/20261024_004225_launch_196303/console.log.


### 2026-10-24 00:53 인계 FSM 프로필 선택 준비(재기동 전)
사용자 승인으로 로봇 Downloads/pc_dummy_dock_fsm_20261024/handoff_fsm.json 생성: 기존 handoff_body_trial.json에서 body_trial_enabled만 true→false. arc/완료/충돌/입력 freshness 등 안전 조건과 성공 코드는 변경하지 않았다. Downloads/manyfarm_terminal_20261024/terminal.py의 laun 인자 및 필수파일 검사만 새 절대경로로 변경. 원본 JSON은 그대로 유지. wrapper/원본profile/aliases/environment/harvest 설정과 SHA256 manifest를 같은 디렉터리 backup-fsm-20261024_005329에 보존. JSON 차이 1키 및 Python AST 검증 완료. 실행 중 프로세스에는 미반영이며 사용자 Ctrl+C 후 laun→vinit→zen→dzen 재기동 예정. PC 더미/전용 bridge는 유지 가능. 사용자 웹 연결 확인 후 적용 상태와 정합을 다시 확인하며 이동/Goal/이벤트 요청은 별도 승인까지 하지 않는다. 원복: 종료된 상태에서 백업 terminal.py를 원래 위치에 복원하면 laun이 원본 body_trial 프로필을 선택한다. commit/push 없음.


### 2026-10-24 00:59 인계 FSM 재기동 후 무이동 확인
사용자 기동·웹 확인 후 실제 parameter handoff_config=/home/vic/Downloads/pc_dummy_dock_fsm_20261024/handoff_fsm.json, handoff_body_trial_enabled=false 및 body_trial 서비스 없음 확인. 새 boot0b3868851fb246178f57e35289c0ba57의 IDLE/ready/적재0, odom443개 비영0. cmd_vel_nav는 harvest_motion_server, odom은 vic_pinky_bringup 각 publisher1개. PC 더미 HarvestTask/Discharge/prepare/stop 탐색 모두 정상.
정지 scan/map624점의 점유셀 거리 중앙16.81mm, p90 26.73mm, 5cm 이내99.84%, 10cm 이내100%. 이는 정지 정합 일관성 표본이며 실물 참위치/전체경로 보증은 아니다. 일반/인계 costmap 수신 freshness 및 footprint 크기 검사 통과, unknown0. 현재 자세와 +0.1rad 가상회전 경로 모두 기존 check_grid 통과(최소여유 약0.180/0.174m); 실제 회전·costmap 초기화 없음. 웹 수확/복귀/인계 Action 및 수확 이벤트 readytrue, 새 boot일치·sequence84→86·age0.1~1.1초. 운송 Action/event false, 상태약59분 전. 새window/더미수확 및 운송 연결·물리이벤트 검증은 여전히 필요. Goal/이벤트/장치서비스 요청·이동·코드설정 변경 없음. 로봇 근거 runs/handoff_diagnostics/fsm-readonly-20261024_0100/{alignment.json,station_checks.json,general_costmap_before.json,handoff_costmap_before.json}. commit/push 없음.


### 2026-10-24 01:03 웹 수확→PC 더미 성공(FSM 프로필)
사용자가 웹에서 전송한 job f2d981c6791b4919bfc0b6af6deb5c89, task TEST_8e2c1cd3e3ff_SEC01_TASK001, window TEST_8e2c1cd3e3ff_SEC01_W001 관찰. 에이전트 별도 이동 Goal 없음. 01:02:20 수락→01:03:24 ROS status4/SUCCESS, expected2/harvested2/failed0. 동일 작업의 PC 더미 journal에 신규 terminal SUCCESS/recovery_required=false 기록 확인. 실제 팔 시험 아님.
실제 설치 communication.py에서 runtime.remember_window(goal, controller.outcome) 이후 handle.succeed()이며 성공 응답 확인: 새 도착 기준 저장 경로 완료로 판단. 내부 window 객체 직접 덤프는 하지 않았고 별도 저장 로그도 없음. 최종 IDLE/ready/load2, pose(1.16958187,-.00450528),yaw-.04942936, odom451개 비영0, cmd_vel_nav publisher1 확인. 인계/배출/운송 이벤트 미요청. 현재 window 위치 유지, 초기위치 재발행 금지. 운송 연결은 이전 점검에서 미완료로 인계 전에 재확인 필요.
로봇 runs/handoff_diagnostics/web-fsm-20261024_010143에 bag/launch.log/final.json 보존, 수집기 SIGINT 정상 종료 및 metadata 생성 확인. Action feedback 등의 embedded message definition 누락 경고가 있어 bag 해석 시 동일 ROS 인터페이스 설치 필요; 웹 결과/더미 journal은 별도 보존. PC Git 밖 /home/eunbi/vmany_artifacts/jetson_dummy_pc_20261023/web_fsm_20261024에 web.jsonl/dummy_journal.json/final.json. 코드·설정 변경/commit/push 없음.


### 2026-10-24 01:37 웹 DockTransfer 진입 전 실패
사용자가 dock_transfer 전송. task DOCK_TEST_ca085300951941dca507d8ab3b92586a / transfer TRANSFER_TEST_a4e66bec76f04285b77b9ac18476c3c1. 웹 expected_count4(직전 적재2와 다름), 01:37:52.8→53.975 FAILED/status6/DEVICE_FAILED, rotate_to_transfer: 경로의 장애물/unknown 셀과 footprint 접촉/겹침. 수량 차이를 이번 오류 원인으로 단정하지 않는다. DOCK_READY 미수신·배출/복귀 미실행, 후속 이벤트 버튼 allowedfalse. 에이전트 이벤트/Goal 없음.
기존 상시 계측에서 build_body 및 동일시각 TF 확보 통과→capture 통과→plan:departure의 guard:departure에서 충돌검사 오류(약157ms)를 확인. 따라서 이동 경로 실행 전 계획 검사 실패이며 통신 미연결/TF조회 실패와 구분한다. 새 window 기준은 build_body를 통과했다. 현재 정지 odom30개, ERROR/readyfalse/load2; 영속 recovery_requiredtrue. 실패 뒤 수집한 일반/인계 costmap은 unknown0, 현재 footprint 및 +0.1rad 가상회전 검사통과(여유약0.101/0.095m). 이 사후 표본은 실패 당시 전체 departure 경로의 충돌 셀을 확정하지 않는다. 초기위치재발행·재전송·costmap clear·안전완화·재시작 없음.
로봇 runs/handoff_diagnostics/web-dock-20261024_0137에 기존 launch/trace/transfer 기록과 사후costmap/footprint/정지검사 보존. 실패는 이번 조회 시작 전에 종료되어 해당 순간 신규 rosbag 없음; 기존 상시 trace를 수집함. PC Git 밖 web_dock_20261024에 웹/정지/transfer 기록 이중 보존. 다음 버튼 누르지 말고 위치 유지 안내. commit/push없음.


### 2026-10-24 웹 인계 departure 충돌 원인 대조
무이동 저장자료 분석: 성공 당시 grid+자세 PASS, 이번 사후grid+자세 FAIL. 서로 grid를 교환해도 성공자세PASS/이번자세FAIL. 방향만 교환은 성공위치PASS, 위치만 교환은 이번위치FAIL; map y+32.61mm 차이만으로 재현. 최초 충돌 경로표본index30/34.18도, lethal셀(145,121),map추정(1.25109,.38695)에서 전방좌측 footprint 모서리 접촉. 성공 manifest3모듈 및 설치본 동일, FSM 프로필은 body_trial_enabled만 변경. 일반 도착5cm/3도 성공과 인계 원호 전체 충돌 통과는 별개. 실패 순간 raw grid 미보존으로 정확한 당시 셀 확정은 불가하며 사후재현과 구분. 코드/안전조건/실행상태 변경없음. 상세audit 최신절과 PC외부web_dock_20261024/offline 자료 참조. 다음은 인계 전용 전체경로 사전검사 및 필요한 시작자세 보정 계획 검토(아직 미구현); 재전송/초기위치/reset하지 않음.


### 2026-10-24 인계 padding 비교 완료·미적용
실제 일반/인계 costmap 모두60×50cm+면당2cm padding=64×54 확인. 기존 충돌 검사 오프라인 비교: 성공자료는64×54/62×52 모두PASS, 이번 실패 후 자료는64×54 FAIL/62×52 PASS. 후보 연속 경로 여유 하한1.66mm로 작으며 저장grid 진입원호만 검증한 결과. 실제 적용/이동/일반주행변경없음. 추후 인계만 변경하려면 인계costmap/runtime형상 선택을 함께 맞춰야 함; 단독 동적padding 변경 금지. 상세audit 및 외부web_dock_20261024/padding_comparison 참조.


### 2026-10-24 인계 padding 후보 준비 완료(미적용)
사용자 승인으로 운영원본백업후 Git밖 handoff_padding_candidate_20261024에3소스+FSM JSON 후보. 선택형 .01padding을 launch/runtime동일전달하여 인계만62×52, 일반64×54 및 안전보호보존. 오프라인15PASS,운영3소스/profile해시원본유지. 적용/빌드/재기동/이동없음. 복구필요기록은그대로이며 적용전별도절차필요. 상세audit최신절및외부README참조. commit/push없음.


### 2026-10-24 인계62×52 로봇실행본적용·미기동
사용자승인으로원본/설치본백업후3소스+FSM JSON적용,2패키지빌드/설치해시·형상검증완료. 일반64×54/안전보호유지. 기존런치종료(수확SIGINT60초지연→SIGTERM종료경고보존),사용자스테이션복귀확인. 실패1건은FAILED기록보존+수동복구근거를남기고recovery_required해제. 새window기준/더미수확필요. 로봇/PC브리지·PC더미유지,사용자laun→vinit→웹확인대기. 실제기동/이동없음. 상세audit최신절/외부배포검증자료참조. PC운영소스는미반영,commit/push없음.


### 2026-10-24 02:04 재기동 후 웹 브리지 재발견 실패
새수확PID222078/boot1f03d21959f04981a0ad333e465d557a 직접조회IDLE/ready/odom452개0,PC더미4연결정상. 웹은이전boot종료상태약281초정체및수확Action/event false. 허브bridge201974는실행중이나로그가이전노드undeclare에서멈춰새노드재등록확인안됨. dzen202048은더미연결정상. 프로세스유지만으로웹연결유지를기대한안내를정정. 사용자zen터미널Ctrl+C종료후source ~/.bashrc;zen만재기동안내. laun/vinit/dzen/PC더미재시작불필요. 에이전트재시작/이동없음,웹복구는사용자기동후재확인필요.


### 2026-10-24 02:05 zen 재시작 후62×52 실제 실행 확인(무이동)
사용자zen재시작/웹확인후GET2회수확상태boot1f03d21959f04981a0ad333e465d557a일치,sequence142→145,age.3~.4초. 웹수확/복귀/DockTransfer와수확TransferEvent readytrue,운송false. 로봇직접IDLE/ready/load0/진행task없음,odom452표본0,PC더미HarvestTask/Discharge/prepare/stop탐색정상. 출력/odom publisher각1개.
실제ROS parameter 일반padding.02/인계.01,handoff_config새FSMprofile/body_trialfalse 확인. published footprint 점간거리로일반64×54/인계62×52검증통과(인계내부형상은설치모듈+선택profile구성검증과대조,메모리직접덤프아님). 최신일반/인계costmap unknown0,현재정지/+0.1rad가상회전검사모두PASS. scan626점의map점유셀거리중앙19.45mm,p90 37.69mm,5cm이내99.36%,10cm이내100%. 정지정합일관성검사이며전체경로안전/실제참위치보장아님.
초기위치재발행/costmapclear/이동/Goal/이벤트/설정변경없음. 재기동으로새window기준/더미수확필요,인계실기미검증. 로봇runs/handoff_diagnostics/padding-live-readonly-20261024와PC외부handoff_padding_candidate_20261024/live_check에근거보존. commit/push없음.


### 2026-10-24 02:11 웹 window 재주행 완료·더미 수확 거절
사용자 웹 재전송 job72f522fe3edb4e9586fb785d9943e0b6, task TEST_8e2c1cd3e3ff_SEC01_TASK001. 02:09:49 수락 후 일반 controller 두 goal 모두 완료(02:10:44.509/48.976). 02:10:50.338 PC더미가 busy/recovery/control로 Goal 거절, 웹 FAILED/status6/ARM_REJECTED, 수확0. 더미 journal은 시험 전후 동일하며 최상위 recovery_required=true가 이미 시험 전부터 존재. 서비스/Action 탐색 성공만 확인하고 더미 업무 준비 상태를 확인하지 않은 사전점검 누락이다. 같은 task/window ID의 과거 SUCCESS도 보존돼 있어 복구 후에도 duplicate ID 거절 조건이 남는다. 실제 거절 로그는 duplicate ID가 아니므로 구분한다.
설치 communication.py는 전체 SUCCESS일 때만 remember_window를 호출하므로 이번 요청은 새 인계 도착 기준 저장 경로에 진입하지 못했다(메모리 직접 덤프 아님). 최종 ERROR/readyfalse/ARM_TRAVEL_NOT_READY/load0, pose(1.175342892,-.010742761),yaw-.033464729. 실패 후 odom152표본 비영0. 웹 harvest queue는 자동 paused=true. 인계/재이동/복구서비스/초기위치 요청 없음; 성공코드·설정 불변. 수집기만 SIGINT 종료.
근거: 로봇 runs/handoff_diagnostics/web-window-padding-20261024_020913의 bag/launch.log/final.json, PC Git 밖 jetson_dummy_pc_20261023/web_window_padding_20261024_020920의 시험 전후 journal/result_web.json. 다음은 더미 복구 및 로봇 ARM_TRAVEL_NOT_READY 해제 계약을 확인하고 기존 이력을 보존한 새 작업 ID 시험 절차 준비. 이번 실패를 62×52 인계 충돌 실패로 해석하지 않는다. commit/push 없음.


### 2026-10-24 02:14 PC 더미 복구 완료·수확 노드 재기동 준비
사용자 복구/중복ID 처리 승인으로 PC177에서 실제 RuntimeStatus의 dummy/비활성/접힘·정지·박스닫힘을 확인하고 원본 journal 백업 후 기존 Recover(DEVICE_AND_LOAD_RECONCILED) 호출. recover/prepare 모두success, IDLE/readytrue/recoveryfalse, records 전후 완전동일 검증. 실제팔 복구 아님; 과거 counts2는 새 적재가 아니다. 기존 task/window 성공ID 보호는 유지, 동일 좌표(1.186,-.035,0)/수량2의 새 DUMMY_RETRY_5a0e47f4e3bd_TASK001/W001 자료 생성·기존ID 비충돌 확인, 미전송. 기존 웹 retry는 같은 ID이므로 다시 보내지 않는다. 관제 현재 기본목표1.6006447과 혼동 금지.
설치 mission.py는 ARM 시작시 arm_travel_readyfalse, 실패후 communication.py가 blockedtrue로 설정하며 이를 해제하는 서비스 없음. 코드/메모리 보호값을 우회하지 않고 수확 노드 재기동 필요를 사용자에게 알림. 재기동/종료/이동은 미실행, PID222078 유지. 로봇 Downloads/harvest_recovery_prepare_20261024_021431에 현재argv/ROS환경/params백업 및 NOT_EXECUTED 계획 보존. 전체AMCL을 유지하는 수확노드 단독 재기동 절차는 다음 단계에서 종료·감독정책 확인 후 진행; 현재window에서 스테이션vinit 금지. PC외부 recovery_20261024_021328에 journal전후/상태/응답/검증/새작업/PROCEDURE 보존. 향후 사전검사는 Action탐색뿐 아니라 더미RuntimeStatus/prepare/ID미사용까지 확인한다. 성공코드/설정/중복방지 변경·commit/push 없음. 로봇 오류 해제와 새window기준 저장은 아직 미완료.


### 2026-10-24 02:18 수확 노드 단독 재기동·웹 미복구
사용자 명시 승인으로 정지/비활성 작업 확인 후 PID222078만 SIGINT 정상종료 확인. 동일 실행argv/백업params SHA/ROS환경으로 PID228333 시작. Nav2 일반222051/인계222066·AMCL222050 및 hubbridge223152/dummybridge202048 유지. 초기위치/Goal/이동 없음. 직접 ROS 상태 새boot c7b0174f16614d1795aa74721ca248be, IDLE/readytrue/load0, ARM_TRAVEL_NOT_READY해제, pose(1.175342892,-.010742761),yaw-.033464729 유지. odom452표본0, 출력publisher1, 더미Action·service탐색정상. PC177 RuntimeStatus readytrue/recoveryfalse/접힘정지닫힘 및 실제prepare success확인. 신규 window기준은 아직 없음.
웹 GET2회에서는 이전boot1f03...의ERROR가51→88초정체, 수확/복귀/인계Action·수확event readyfalse. 수확복구와 웹연결복구는 구분; hubbridge는살아있으나 재시작하지 않음. 사용자 zen터미널 Ctrl+C→source ~/.bashrc→zen 재시작 후 새boot/Action을 다시 확인할 단계. laun/vinit/dzen 재실행금지.
이번 수확 PID228333은 기존 ros2 launch 자식이 아닌 별도 세션이다. 이후 전체 종료 때 기존 laun Ctrl+C만으로 종료된다고 가정하지 말고 이 PID/starttick·명령 확인 후 별도 종료해야 한다. 새 로그 Downloads/harvest_recovery_prepare_20261024_021431/harvest_restart.log 및 started.json, PC외부 recovery_20261024_021328/restart_robot_check.json/restart_web_check.json/after_restart_dummy.json 보존. 초기 검증 도구의 base환경변수누락1회 수정후검증통과, 운영설정변경아님. 코드/설정수정·commit/push없음.


### 2026-10-24 02:19 사용자 zen 재시작 후 웹 연결 복구 확인
읽기 전용 웹 GET2회에서 새boot c7b0174f16614d1795aa74721ca248be 확인, sequence140→142, age0.7→0.5초. 수확/복귀/DockTransfer Action 및 수확TransferEvent readytrue. 직접 ROS와boot일치, IDLE/ready/적재0/task없음, odom453표본 비영0, 출력publisher harvest_motion_server1개 및 더미Action/service탐색정상. 위치·방향 유지. 웹수확대기열 pausedtrue 유지, 운송Action/event false. 연결탐색과실행완료구분. 초기위치/이동/Goal/이벤트/설정변경없음. 새window기준은아직미확보, 기존ID재시도금지·새시험요청자료미전송. PC외부recovery_20261024_021328/zen_reconnected_web.json 및 zen_reconnected_robot.json에근거보존. commit/push없음.


### 2026-10-24 02:21 새 ID 동일 window 재요청 사전검사 차단(미전송)
사용자 새ID 수확 재시험 승인 후 이동 전 현재 상태·실제 로봇설정·설치된 straight_plan을 읽기전용으로 검증. IDLE/ready/odom121표본0, 현재(1.175342892,-.010742761),yaw-.033464729. 동일 목표(1.186,-.035,0)에 forward10.657mm/lateral24.257mm로 path_heading1.156845rad(66.28도)가 설정.087266rad(5도)를 초과, APPROACH_RECOVERY_REQUIRED:path_heading 재현. 위치오차26.49mm/방향1.92도는 일반 도착5cm/3도 안이지만 staged_navigation.resume_current→CorridorNavigator._plan_current에서 먼저경로검사를수행한다. 이동Action/더미수확요청을보내지않았으며새ID미사용·도착기준미저장·인계미실행. 안전조건완화/설정변경/초기위치없음. 근거로봇runs/handoff_diagnostics/same-window-preflight-20261024_022059/preflight.json.
현재코드의무이동도착확인경로가이번수확재개경로에연결되지않음. 추후수정은수확재개시구간/목표/정지/동일시각TF/도착을검사하고성공시이미도착결과를반환하도록검토하되미적용. 이미도착으로임의성공시키거나새기준을주입하지않는다. 실행요청이막힌사실과코드수정필요를사용자에게알림. 기존백업/기록유지,commit/push없음.


### 2026-10-24 02:24 스테이션 수동 이동 전 전체 로봇 실행 종료
사용자 승인으로 정지/비활성 확인 후 별도수확228333과런치222032에SIGINT. 드라이버/Nav2/AMCL/수확 종료 확인 후 잔여 카메라·태그 자식8개에 PID/starttick검증후SIGINT하여 런치포함활성잔존0 확인. SIGKILL없음. 초기프로세스조회도구의공백포함comm 파싱오류는신호전발생했으며수정후재검증수행. 설정3파일SHA불변, 기존로그유지·종료로그사본보존. bringup exit1/route_preview ExternalShutdownException 및 별도수확 Destroyable 종료경고는보존,깨끗한종료로보고하지않음. Zenoh브리지·PC더미는이번종료대상아니므로유지. 초기위치/이동/Goal없음.
근거 로봇 Downloads/station_shutdown_20261024_022321/{processes_before.json,stop_check.json,config_sha_before.json,verification.json,launch_shutdown.log,harvest_shutdown.log}. 이제 사용자에게기존스테이션위치·방향으로수동이동가능안내. 이동후확인전재기동/초기위치발행금지. 다음실기전더미실제ready/prepare와새ID미사용확인필수. 기존기록/설정유지,commit/push없음.


### 2026-10-24 02:26 전체 통신 프로세스 종료 확인
사용자 승인으로 남은 로봇 hubbridge229149/dummybridge202048 및 PC더미130190/전용bridge130248에SIGINT 정상종료, 양측 재조회 잔존0. 기존 로봇런치/별도수확/드라이버도 잔존0 유지. PCjournal/bridge설정/pc.bash 원본백업과전후SHA불변, 로봇bridge설정SHA불변. 기록삭제/재기동/이동/초기위치없음. PC외부full_shutdown_20261024_022542 및 로봇Downloads/station_shutdown_20261024_022321/bridges_*에근거.
사용자기동순서: PC별도터미널 pc.bash dummy→pc.bash bridge, 로봇별도터미널 laun→실제스테이션위치방향확인후vinit→zen→dzen. 모든터미널전경유지. 스테이션이동완료는아직사용자확인전이므로vinit조건명시. 웹표시후ready/prepare/정합/costmap/새ID미사용을확인하고작업전송은그후. Gitcommit/push없음.


### 2026-10-24 02:28 스테이션 전체 재기동 후 무이동 준비 확인
사용자 스테이션이동/기동/웹확인 후 점검. 새수확boot089359b65d864d7ba18df20bfc648356 웹/직접일치, 최신age0.7초, 수확/복귀/DockTransfer/수확event readytrue; 대기열pausedtrue유지. IDLE/ready/load0/task없음. PC더미새boot02fc1a5e89db457b83230c1391021382의RuntimeStatus readytrue/recoveryfalse/접힘정지닫힘, prepare success. 준비한DUMMY_RETRY_5a0e47f4e3bd_TASK001/W001은더미영속기록미사용·웹job없음,목표1.186,-.035,yaw0/수량2확인.
scan628점지도점유거리중앙11.89mm,p90 25.66mm,5cm이내100%,scanage.418초;odom300표본비영0. 일반64×54/인계62×52 published footprint검증,최신costmapunknown0,정지및+0.1rad가상경로검사통과(최소여유하한일반.190/.179m,인계.200/.190m). 실제회전없음,전체경로안전보증아님. 출력/odom publisher각1,body_trial서비스없음. 초기위치재발행/clear/이동/Goal/이벤트/설정변경없음. 로봇runs/handoff_diagnostics/station-restart-check-20261024_022735,PC외부station_restart_check_20261024_022735에근거. 새수확/인계는아직미실행,commit/push없음.


### 2026-10-24 02:31 웹 새 작업 의도와 실제 ID 불일치·중복 거절
사용자는새작업전송이라고알렸으나관제GET의실제job eb3be2705425473e8944769e191718a7은 retry_of72f522fe3edb4e9586fb785d9943e0b6,task/window기존TEST_8e2c1cd3e3ff_SEC01_TASK001/W001동일. 어떤UI조작/생성단계에서재사용됐는지는미확정이며사용자오조작으로단정하지않는다. 02:29:03.259전송→일반controller2회목표완료→02:30:08.010더미 duplicate ID거절,웹ARM_REJECTED/status6/수확0. 이전busy/recovery/control실패와구분. PCjournal시험전후동일,신규완료없음.
최종ERROR/ARM_TRAVEL_NOT_READY/load0,pose(1.182954562,-.014297734),yaw.007390011,odom122표본비영0. 전체성공전remember_window미호출및실패invalidate경로로새인계기준미확보. 에이전트이동/Action/재시작/초기위치/복구호출없음. 새준비ID는여전히미사용. 재전송/인계보류,실제웹생성·선택·ID전달경로읽기분석필요.
로봇runs/handoff_diagnostics/web-new-window-20261024_022903에bag/launch/final,PC외부web_new_window_20261024_022912에web_latest/dummy_before/after/log보존. 수집기구독완료는요청전송직후이므로수락 이전부터의 완전 기록이라고 주장하지 않음. 기존launch/웹타임스탬프로수락확인. 수집기만SIGINT종료,설정/기존기록유지,commit/push없음.


### 2026-10-24 PC 더미 반복 수확 후보 준비·오프라인21개 통과(미적용)
사용자승인범위로Git밖 jetson_dummy_pc_20261023/repeat_harvest_candidate_20261024에원본server/journal백업후후보작성. --allow-repeat-harvest 명시옵션에서만 Trigger repeat_last_harvest 서비스생성,유휴/복구완료시마지막terminal수확ID에300초1회허용. 요청timestamp외payload동일검사,활성중중복/만료/배출반복거절,허용권비영속·stop/recover시취소. 이전record전체는historyappend,최신records/attempt_id와원자저장후수락. 저장실패차단. 무조건동일ID재실행이나기존기록삭제없음.
후보실제메서드AST기반ROS없는오프라인21PASS,20개병렬요청중1개수락/반복이력/취소/정지/복구/저장실패/제어실패검증. ROS환경import/--help정상. DDS/service/Action실기/웹반복미검증. 명시허용구간에같은payload의늦은재전달과의도된새요청구별은프로토콜상보장하지않음. 허용서비스는PC177로만관리,브리지설정불변.
현재실행원본server SHA불변,수확성공코드/실행설정/로봇/PC프로세스재기동·이동없음. 실제운영적용전안내필요. 기존수확노드ARM_TRAVEL_NOT_READY와동일window재개제약은별도남음. 후보README/candidate.diff/tests.log/tests.xml/manifest에기록,원복시history포함journal전체백업필수. commit/push없음.


### 2026-10-24 PC 더미 반복 후보 운영 적용·무이동 통신 검증
사용자승인으로PC더미152623만SIGINT종료,server/pc.bash/journal백업후후보server적용·pc.bash에--allow-repeat-harvest추가. PID156603으로기동,기존journal유지. PC177 가상팔Action직접검증9항목통과:prepare/RuntimeStatus정상,기존ID무허용거절,반복서비스1회허용/중복허용거절,실행중5중복Goal모두거절,동일웹ID1회SUCCESS수확2,완료후재요청거절,이전record정확archive/다른record불변,사후prepare성공. 허용권소비완료. 로봇수확FSM/주행/적재/window기준성공을의미하지않는다. 기존수확코드/로봇설정변경없음.
근거PC외부repeat_live_20261024_023651/{server.py,pc.bash,journal.json,applied.json,launcher.log,result.json,checks.json,journal_after_test.json,RECOVERY_PROCEDURE.md}. 후보21오프라인PASS는앞선별도기록. 현재반복서비스는PC177에서만노출,웹/로봇bridge설정불변.
작업초기수확232327존재확인했으나최종조회에서로봇수확/드라이버/브리지및PC브리지없음,ROSstatus/odom표본0. 에이전트는PC더미152623외신호/재시작안했으며다른프로세스종료원인미확정. 로봇정지속도검증성공으로보고하지않음. 현재더미156603만정상확인,수확복구는절차준비만수행. 로봇실행상태/위치재확인→사용자가선택한스테이션전체재기동절차→더미실제ready/prepare→1회반복허용→웹전송순서검토. 현재window에서vinit금지. 사용자에게현재프로세스부재알림,임의재기동/이동없음. commit/push없음.


### 2026-10-24 02:40 사용자 전체종료/스테이션이동 후 PC더미 잔존 종료
사용자가직접로봇/브리지종료·스테이션이동했다고확인하여앞선프로세스부재맥락확인. 승인하에남은PC더미156603만SIGINT정상종료. PC전체journal백업후바이트불변/과거history1건보존검증. PC더미/브리지및로봇수확/드라이버/런치/컨트롤러/태그관련조회잔존없음. 근거PC외부repeat_shutdown_20261024_024035. pc.bash dummy는--allow-repeat-harvest반영확인. 재기동/이동/초기위치/반복허용없음.
사용자재기동순서PCdummy→PCbridge→로봇laun→스테이션vinit→zen→dzen안내. 사용자웹연결확인후에더미실제ready/prepare·정합/costmap·수확ID확인하고PC반복허용서비스호출예정. 현재는허용권없으며웹작업전송보류. 기존기록/설정유지,commit/push없음.


### 2026-10-24 02:43 웹 동일 작업 1회 반복 허용·수집 시작
사용자기동/웹확인및반복허용승인후무이동검사. PC더미readytrue/recoveryfalse/prepare성공,기존웹TEST_8e2c1cd3e3ff_SEC01_TASK001/W001의ID·좌표1.186,-.035,0·수량2와더미원요청완전일치확인. 02:43:17 KST repeat_last_harvest success로1회허용,유효기간300초(02:48:17경). 에이전트Goal/이동없음. 사용자기존웹57번작업1회재전송대기.
새수확boot1ba12c86ca5746faa244aa8428e4c4ce IDLE/ready/load0,odom301표본0. scan624점중앙27.10mm/p90 42.92mm/5cm이내95.83%/10cm100%,정지정합일관성표본. 일반64×54/인계62×52 footprint검증,최신costmapunknown0,현재자세및+0.1rad가상경로검사PASS(일반.193/.179m,인계.206/.190m). 출력/odom각publisher1. 웹수확Action readytrue/대기열pausedtrue,웹조작없음.
로봇runs/handoff_diagnostics/repeat-ready-20261024_024224에정합/costmap/bag(15분한도PID는recorder.json)수집중,PC외부current-web-repeat-trial이가리키는web_repeat_trial폴더에원journal/웹/prepare/repeat_permit보존. rosbag embedded definition누락경고보존. 전체경로/수확/인계성공미확인. 초기위치/설정변경/commit/push없음.


### 2026-10-24 02:45 동일 웹ID 반복 수확 실기 성공(PC더미)
사용자웹전송jobfd062f1935b2476ab72e3d4ed5ebb8c3,기존TEST_8e2c1cd3e3ff_SEC01_TASK001/W001. 02:43:43수락→SECTION_APPROACH/WINDOW_MOVE→02:44:45.148 SUCCESS/status4/수확2/실패0. 더미명시1회허용정상소비,신규attempt3142dfa0292c49d69f17b456c9143632와terminalSUCCESS/recoveryfalse,history1→2/이전record정확보존검증. 로봇FSM전체성공이며실제팔대신PC더미범위.
실제task_events의arrival acceptedtrue,위치29.947mm/방향.042854rad(2.46도),동일stamp1792777483444898266. 설치communication.py에서remember_window→handle.succeed순서와이번성공결과로새도착기준저장경로완료확인(메모리직접덤프아님). 최종IDLE/ready/load2/task없음,pose1.175381672,-.006764902,yaw-.044919955,odom121표본0/출력publisher1. 인계/배출/운송이벤트/초기위치/재시작없음. 현위치유지·인계버튼보류안내. 인계62×52전체실기는아직미검증.
로봇runs/handoff_diagnostics/repeat-ready-20261024_024224의bag/task_events/final/launch,PC외부web_repeat_trial_20261024_024251의web_monitor/journal전후/task_events/final보존. 수집기만SIGINT정상종료·metadata확인. 기존설정/코드/commit/push변경없음.


### 2026-10-24 02:48 웹 인계62×52 실기 준비·사용자버튼대기
사용자인계시험승인(버튼은사용자)후기존성공window/동일boot1ba12...유지,IDLE/ready/load2/odom정지30표본확인. 일반64×54/인계62×52 footprint와최신costmapunknown0,현재정지및+0.1rad가상경로PASS(인계여유.1266/.1156m). 전체departure경로사전검증은아니며실행중기존guard유지. cmd_vel_nav/odom publisher각1,body_trial서비스없음. 더미RuntimeStatus ready/recoveryfalse/prepare success,Discharge탐색정상. 웹DockTransfer/수확event readytrue,운송false/오래된상태. 이번안내범위는수확인계진입→DOCK_READY이며운송실물완료주장없음.
웹UI문구상현재실행중job없을때다음start_dock은새transfer ID생성. 과거transfer ID는로봇journal에보존돼중복거절되므로전송후새ID확인필수. 수량은현재load2에맞춰2안내. 에이전트웹클릭/Goal/이벤트/이동없음. 후속버튼은DOCK_READY확인뒤별도안내.
로봇runs/handoff_diagnostics/web-dock-62x52-20261024_024737에현재costmap/footprint/정지기록및bag수집시작(PID240851,900초한도),PC외부current-dock-pc이가리키는web_dock_62x52폴더에웹/원journal/더미준비기록보존. 기록정의누락경고는기존과동일보존. 기존코드/설정/commit/push변경없음.


### 2026-10-24 02:49 인계62×52 실기 계획검사 실패
사용자dock_transfer전송새task DOCK_TEST_2264a8ea62be40819b43e5c1f92f4f32/transfer TRANSFER_TEST_198c841110ff41cdb52fc910be349faa/수량2. 02:48:23.502요청→25.061FAILED/status6/DEVICE_FAILED,rotate_to_transfer:경로의장애물/unknown셀과footprint접촉겹침. ID중복아님. 내부trace build_body13.25ms/동일시각TF완료,capture810.60ms완료후plan:departure→guard:departure479.23ms에서충돌검사실패. 인계경로controller실행전실패,DOCK_READY/배출/복귀미수행.
현재ERROR/readyfalse/load2,동일pose유지,사후odom122표본0. PCdummy records/history전후동일·신규배출없음,최상위recoveryfalse→true는실패정리중정지요청과부합(서비스원인추적미완료). 이전허용수확성공기록보존. 이번62×52는현재정지자세통과와달리전체진입계획실패. 원인셀·경로지점은아직재구성전이며추가완화/재시험금지.
로봇runs/handoff_diagnostics/web-dock-62x52-20261024_024737에실패시각bag(costmap/TF/odom/Action),failure_trace.jsonl2493행/launch/transfer/final보존;수집기SIGINT정상종료metadata확인. PC외부current-dock-pc폴더web_latest/journal전후보존. 후속버튼/이벤트/재전송/초기위치/재기동/설정변경없음. 다음은이번실패시점grid+path를과거성공/오프라인후보와대조. commit/push없음.


### 2026-10-24 02:48 실패와 과거 성공의 62×52 교차 재구성
사용자의 동일 위치인데 실패한 이유 확인 요청에 따라 저장된 bag과 설치된 경로/충돌 검사로 오프라인 대조했다. 과거 성공 대비 현재 map 추정 자세는 x +18.999mm, y +30.348mm, yaw -2.151도다. 모두 62×52 형상으로 검사하면 과거 자세+과거 grid PASS(여유 하한21.21mm), 현재 자세+현재 grid FAIL, 과거 자세+현재 grid FAIL, 현재 자세+과거 grid FAIL이었다. 따라서 이번 실패는 자세 차이만으로 설명할 수 없으며 costmap 표현 차이도 판정에 영향을 준다. 실제 물체가 바뀌었다거나 localization 오류라고 확정하지 않는다.
현재 재구성 경로의 첫 접촉 표본은 90도 departure 중 약77.47도(index68/79), 2cm grid 셀(103,118), 값254(lethal)이다. 셀 중심 map 환산 추정은 (1.25187,-0.44943)m. 실제 로봇이 그 지점까지 움직였다는 뜻이 아니라 실행 전 경로 검사 결과다. unknown 때문이라는 해석은 이 표본에 해당하지 않는다.
한계: 사용 grid는 guard 시작166.13ms 전 수집 표본이며 내부에서 사용한 객체의 정확한 복사본은 아니다. 교차 좌표변환은 정지 시 map/odom 자세로 재구성했다. 센서 관측/정합/rolling grid 표현 중 어떤 원인이 grid 차이를 만들었는지는 추가 확인 대상이다. 이전 62×52 후보의 1.66mm 여유 통과는 이전 실패 자료에 한정되며 이번 실기 통과를 보장하지 않았다.
근거: 로봇 runs/handoff_diagnostics/web-dock-62x52-20261024_024737/offline/{failure_snapshot.json,comparison.json}. 코드·설정 변경, 이동, 재시작, commit/push 없음.


### 2026-10-24 성공 코드 대비 통신 연동 변경 감사
연동 직전 백업 수확43개 중41개 현재 해시 일치, 2개 차이는 승인한 인계 padding 전달/처리뿐이다. 로봇 소스·설치본 수확43/공통주행25개 일치. 실제 PID237742 params는 components/현재 FSM profile, dedicated TF 유지. 원호·재진입 설정 동일, 일반 Nav2/지도 원본 PC와 일치. body-only→FSM, 도착완료→팔완료, 준비/배출 연결 및 최근 인계 padding이 실제 차이다. 두 경로 모두 같은 build_body→enter→capture→departure를 사용하며 통신 때문에 다른 원호 생성 코드로 연결된 증거 없음.
진입 직전 현재 자세에서 원호를 생성하며 window 목표 yaw/성공 당시 자세로 미리 정렬하지 않는 구조는 성공 코드부터 존재한다. 일반 도착 허용치5cm/3도는 전체 인계 원호 통과 보장이 아니다. 현재 grid에서도 과거 자세가 실패하므로 자세만 원인으로 단정하지 않는다. 상세/근거/한계는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md의 성공 시험 이후 통신 연동 변경 추적 절. 코드·설정·이동·재시작·commit/push 없음.


### 2026-10-24 정지 센서·TF 대조: 장애물 셀 잔존 경로로 원인 축소
성공/실패 직전2초 TF·odom자세변화0, TF큰수신공백없음. 성공/현재정적TF동일. 실패bag350grid모두문제셀254, 성공grid같은map영역최근접lethal약34cm밖. 현재문제방향laser는대부분inf이고원본/필터100쌍값동일. 실제inf_is_valid=false에서무응답방향기존셀clearing부족가능성을지지한다. 실패bag과앞선주행bag에scan누락으로최초mark원인미확정;현재관측을과거센서증거로대체하지않는다. scan_filtered publisher2개이나현재100표본중복stamp없음/GID귀속미확인. 세부근거·한계는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md의 장애물 셀 차이의 센서·TF 대조 절. 로봇cell-sensor-audit-20261024에자료보존. 설정/clear/이동/재시작/commit/push없음.


### 2026-10-24 잔존 셀 해결안 검토(미적용)
드라이버소스는거리0을inf로발행하여무응답을자유공간으로간주할근거없음. inf_is_valid일괄활성/강제clear/TTL삭제보류. 저장scan기하검사에서문제셀통과유효광선은성공20/20scan,현재1/20scan뿐이다(Nav2 voxel재생아님). 유효관측회복→기존clearing→전체경로검사가우선이며,유효관측에도셀잔존시3Dvoxel/clearing_endpoints동시기록으로처리결함검증후최소수정. 불가시셀유지한경로재계획검토. 상세는인계감사문서 잔존 셀 해결 방법 검토 절. 설정/clear/이동/재시작/commit/push없음.


### 2026-10-24 voxel/clearing 동시 수집 결과
25초무이동구독수집완료(odom711표본0/전후params동일). 기존실패셀은현재voxel미점유/layer0/master253으로이미lethal삭제됨. 인근잔존3셀은laser와같은.20~.25m높이층marked유지,236개유효clearing메시지에서통과광선0. 원본/필터236쌍모두해당방향값동일·유효거리0. 다른셀marked→unmarked2433전이관측으로전체지우기기능정지증거없음. 현재는지우기광선부재/관측부족에부합,최초mark및물리무응답원인미확정. 근거로봇voxel-clearing-audit-20261024,상세인계감사문서. 설정/clear/이동/재시작/commit/push없음.


### 2026-10-24 충전 후 스테이션 재시작 준비
사용자가충전완료/기존스테이션위치·방향복귀확인,웹연결후정합·costmap·원본레이저비교요청(이동금지). PC/로봇ps직접조회에서더미·브리지·수확·런치·드라이버·Nav2관련잔존없음. 현재별칭/pc.bash/실제profile확인. 로봇기존실패DOCK_TEST_2264... recovery_required=true로재기동만으로복구안됨확인. 앞선수동복귀기록절차에따라전체transfer.json백업후동일FAILED결과/ID보존하고manual_recovery근거추가·해당record복구래치만false. 로봇runs/handoff_diagnostics/charged-station-restart-20261023T193628Z에전후JSON/SHAreceipt보존. 코드·설정변경/기동/이동없음.
PC더미journal recovery_required=true,records2/history2보존·미수정. 사용자기동후웹확인단계에서더미공식Recover/실제준비상태별도확인필요. 명령순서PCdummy→PCbridge→로봇laun→스테이션vinit→zen→dzen→vstat. 각foreground별도터미널,기존실패를성공처리하지않으며웹작업전송/인계/반복허용은아직금지. 새window기준없음. commit/push없음.


### 2026-10-24 04:39 충전 후 스테이션 정지 점검
사용자 순서대로 기동/웹 표시 확인 후 무이동 상태 조회·구독 수집만 수행. 현재 harvest PID270128/boot af5ac68e53d44b03a38f5511e34bfb13, 일반관제 bridge270566/더미 bridge270640. RobotStatus IDLE/readytrue/load0/현재작업없음. PC더미 boot f46d67cef1684c159f314d596768e0ce, mode dummy/ERROR/readyfalse/recovery_requiredtrue, active ID없음/가상팔정지·접힘·상자닫힘. 이전실패복구래치유지이며Recover/prepare/Action호출안함. 웹GET harvest/harvest_return readytrue(장치업무준비증거아님).
정지정합: scan629점중앙22.23mm/p90 38.66mm,5cm이내97.30%/10cm100%,odom300표본비영0. 추정map(.0793484,-1.1236693),yaw1.52009954rad. 실제참위치정확성보장아님. scan_age .441s는검사종료시선택표본값이고별도bag도착age통계와구분.
일반64×54/인계62×52 published footprint일치,두costmapunknown0. 현재정지및가상+.1rad검사PASS:일반여유하한.190/.179m,인계.200/.190m. 실제회전없음/전체인계경로검증아님. cmd_vel_nav publisher harvest_motion_server1개,odom vic_pinky_bringup1개.
충전전window bag와충전후station bag원본scan비교:236→137표본,각header중복0,약10.10→10.01Hz,전체유효거리84.01→96.04%,이전문제laser각도1.3713rad±2beam구간유효0→100%. header도착age중앙98.72→99.85ms로주기는비슷. 필터전체유효74.81→86.77%. 위치/방향/관측물체·재기동이달라배터리인과확정불가. 현재전압/실제잔량계측없으며battery0은BATTERY_UNAVAILABLE자리값유지.
근거로봇 runs/handoff_diagnostics/charged-station-check-20261024/{bag,alignment.json,station_checks.json,charge_scan_compare.py,charge_scan_compare.json,dummy_status.json} 및원costmap/footprint. PC /tmp/charged-dummy-status.json,/tmp/charged-web-control.json(토큰제거). 이전기록보존. 설정/clear/Recover/반복허용/초기위치/이동/재시작/commit/push없음. 다음업무시험전더미공식복구·준비확인필요. 새window도착기준미확보.


### 2026-10-24 04:41 충전 후 PC더미 복구·같은 웹 작업 1회 허용
사용자승인으로PC공식Recover(DEVICE_AND_LOAD_RECONCILED)호출전journal백업,가상장치정지/접힘/상자닫힘·비활성확인. Recover/prepare success,RuntimeStatus IDLE/readytrue/recoveryfalse. records2/history2 내용전후완전동일확인. 마지막TEST_8e2c1cd3e3ff_SEC01_TASK001/W001(expected2,goal1.186,-.035,0)1회반복허용04:41:19→04:46:19 KST(더미수락기준). 웹마지막성공job fd062f1935b2476ab72e3d4ed5ebb8c3와ID일치. 웹새테스트기본goal1.6006447/count1은다른작업이므로기존동일작업재전송안내. 에이전트주행Action/웹버튼미호출.
PC외부charged_repeat_ready_20261024_044115에journal전후/서비스응답/상태/웹보존. 로봇runs/handoff_diagnostics/charged-web-repeat-20261024_044111에원본scan·TF·인계voxel/clearing포함bag수집시작(900초한도,recorder.json),전체구독확인. 사용자웹전송대기,새window/수확/인계성공아직미확인. 코드·설정변경/commit/push없음.


### 2026-10-24 충전 후 웹 수확 성공·인계 전 대기
웹 job e4186857241a487dac90891043d63911 SUCCESS, PC 더미 수확2/실패0. 새 window accepted=true(위치오차47.395mm/허용50mm) 및 설치 코드의 remember_window→succeed 순서 확인. IDLE/ready/loaded2, 최근 odom30개 정지. 이전 더미 이력 원문 보존, 새 attempt 기록 완료.
충전 전후 window 원본 유효거리84.079→83.899%, 문제 각도 구간0→1.75%로 관측 부족 회복 증거 없음. 현재 costmap에서 이전 문제점 cost97, 62×52 진입 곡선 저장 자료 오프라인 PASS(하한10.87mm). 전후 자세·재기동 조건이 달라 배터리 원인 확정 불가. 전체 인계 실기 성공 아님.
태그 캡처 세션이 주행 전 종료(camera1/rectify-11)되어 이전 태그 보정 조건과 차이 있음. 인계 전 확인 필요. 설정/주행 명령/인계/재시작/commit/push 없음. 상세·로그 경로는 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md의 동일 날짜 웹 window 수확 절.


### 2026-10-24 태그 캡처 종료 조사 정정
최초 종료는 camera의 control_readback_stale(설정 조회 결과 age>3.5초), 이후 감독자 종료 중 detector-9/rectify-11 발생. controls270표본 값 동일/마지막 갱신 간격3.835초. polling1초+조회timeout3초와 stale3.5초 검사 간 불일치 확인; 실제 지연 원인 USB/CPU/GIL 등은 미확정. PC·로봇 관련3스크립트/설정 해시 동일. 충전 전 세션에서도 같은 오류가 반복되어 충전 후에만 생긴 문제라는 해석 정정. 상세는 HANDOFF_DELAY_AUDIT_20261023.md 동일 날짜 태그 캡처 절. 코드·설정/재기동/이동 변경 없음, 수정안과 재시작은 사전 보고 후 진행. commit/push 없음.


### 2026-10-24 태그 조회 지연 후보 준비(운영 미적용)
사용자 승인 범위로 runs/tag_control_candidate_20261024에 백업·두 파일 후보·diff·해시·검증 기록 준비. 조회 stale/timeout 동안 Image/CameraInfo 차단, 정상 확인 이후 새 프레임부터 재개. 기존3.5초 기준과 실제 설정 불일치 종료 보호 유지. 오프라인14개/py_compile 통과, 실제 USB·DDS·보정/종료-11 미검증. PC/로봇 운영본·설정 미변경, 적용/재기동 전 보고 필요. 이동/commit/push 없음. 상세 HANDOFF_DELAY_AUDIT_20261023.md 태그 설정 조회 지연 후보 절.


### 2026-10-24 영상 통신 부하 조사
일부 조회 공백과 avg publish 상승이 겹치지만3.468초 조회공백/발행10ms 사례도 있어 DDS 원인 미확정. avg publish는 DDS뿐 아니라 녹화·상태기록 함수 포함, 조회공백은스케줄링/명령시간미분리. Git2091859(10/08)도이미ROS영상파이프라인사용; 카메라발행/설정조회2파일은HEAD까지diff없음. 상세인계감사문서참조. 운영 변경/재기동/이동 없음. 추가 원인분리는 승인 후 정지캡처 분리계측 필요.


### 2026-10-24 카메라 분리 계측 — 공간 확보 확인 대기
사전 고지한 별도 계측 복사본으로 카메라 단독 실행했으나 최소3GiB 여유 검사에서 영상 시작 전 종료. 현재2.89GiB, 검사 유지. 모든 계측 자식 종료/harvest270128 및 운영 코드·설정 SHA 유지. 기존window bag436MiB를 PC runs/tag_timing_probe_20261024/preserved_logs/bag에 추가 보존·SHA동일 확인. PC사본 보존하며 해당 로봇bag만 제거 후 계속할지 사용자 확인 대기; 아직 삭제없음. 실제 영상 부하 계측 미완료. 주행/보정 요청·commit/push 없음. 상세 인계감사문서 참조.


### 2026-10-24 로봇 대용량 시험자료 PC 보관
사용자 승인 후 종료자료1,180개/3.66GiB를 PC /home/eunbi/vmany_artifacts/robot_storage_archive_20261024에 전수SHA검증 보존하고 로봇동일파일만 제거. 코드·설치·설정·브리지·핫픽스 보존, 여유6.6GiB. 이전 runs 대용량자료는 PC archive 대응경로에서 조회/개별복원. 삭제/검증receipt와 manifest 보존. 카메라 단독 계측 재개, 이동/주행재시작/commit/push없음. 상세 인계감사문서 참조.


### 2026-10-24 카메라 분리 계측 완료
공간확보후카메라만3분계측: 설정최대갱신1.047초,stale미재현. Image ROS발행평균8.48/최대30.42ms,설정조회평균14.30/최대103.25ms. 이전조회만료의DDS원인입증/배제불가. 종료중detector/rectify-11재현(운영중예외없음). 계측자식모두종료,노출복원/운영코드설정SHA동일/harvest270128유지. 상태IDLE/ready/load2,odom453개정지. PC·로봇runs/tag_timing_probe_20261024_retry자료보존. 이동/보정요청/운영후보적용/commit/push없음. 상세인계감사문서참조.


### 2026-10-24 종료 -11 조사
최신시험은카메라정상종료후검출기/rectify SIGINT종료중SIGSEGV. 과거10/16 Apport 코어각60KiB불완전으로전체스택없음; 두고장PC가당시maps밖이라종료중수명/해제경쟁후보이나확정불가. 현재메모리available6.6GiB/swap0/memory PSI0으로현재압박없음,과거조회지연의paging/스케줄링원인은미확정·단편화근거없음. 다음은사전고지후격리영상노드디버거실행으로최신스택확보필요. 이번읽기/오프라인코어조사만,재기동/수정/이동없음. 상세인계감사문서참조.


### 2026-10-24 종료 충돌 gdb 근거 확보
영상노드만60초실행후종료시두SIGSEGV재현. detector/rectify모두종료전libtbb.so.12.11+0x1005c에서충돌,당시TBB매핑제거됨/main thread class_loader→dlclose진행. 해당주소는TBB내dlclose호출바로다음명령. 라이브러리해제와남은실행스레드수명경쟁증거이며조회stale/paging과동일원인확정아님. PC/로봇runs/tag_shutdown_debug_20261024에로그/스택/maps/명령보존. 시험자식모두종료,운영SHA불변/harvest270128유지/보정·이동없음. 패치미적용,commit/push없음. 상세인계감사문서참조.


### 2026-10-24 TBB 종료 순서 후보 준비
PC·로봇runs/tbb_shutdown_candidate_20261024에별도runner(rectify_safe/apriltag_safe). node/executor정리후TBBfinalize성공해야loader해제;직접TBB링크유지,실패exit3. 기존컴포넌트/설정/주행불변. PC순서단위3·합성노드3경로·링크2검사통과,ARM2후보빌드성공. 로봇에서는후보실행/운영적용없음,원본별도백업. 실제영상종료시-11해결은아직미검증/다음사전안내필요. commit/push없음. 상세인계감사문서와후보README참조.


### 2026-10-24 TBB 후보 실제 영상 종료 검증 — 실패
사용자 카메라 전용 실행 승인으로 운영 설정·주행 노드를 유지하고 별도 ARM runner만 선택했다. 원본 카메라/monitor, 기존 rectify/detector 인자·파라미터 그대로 사용했으며 태그 보정 adapter와 이동 요청은 실행하지 않았다. Git 기준 cf870da 및 기존 문서 미커밋 변경 보존.
실제 120.034초 처리: raw/rect/detections 각각944표본, tag100 검출. camera/monitor 종료0. detector는 SIGINT 이후0.266초, rectify0.264초에 각각 exit3: TBB_FINALIZE_FAILED. TBB_FINALIZED/COMPONENT_LIBRARY_RELEASED는 출력되지 않았다. SIGTERM/KILL 없이 전체 종료3.813초(카메라 후1초 대기 포함).
이전 -11과 달리 후보의 실패 보호 경로로 종료했으므로 정상 종료 해결로 인정하지 않는다. 실제 OpenCV/TBB 사용 후 남은 scheduler/arena/참조 소유권은 추가 조사 대상이며 이번 결과만으로 특정 소유자를 확정하지 않는다. finalize 실패를 무시하거나 강제 성공 처리하지 않는다. 합성 시험 통과는 실제 영상 종료 성공을 보장하지 않았음.
운영 카메라 코드3개/설정SHA 전후동일, harvest PID270128 유지, 시험 자식 종료 확인. 읽기 상태 수집15초에서 odom452표본 비영0/IDLE. 카메라 closed=true/fault없음 및 controls 복원 기록 보존. 별도 카메라 후보 시험만 종료했으며 운영 launch 교체·주행 재시작·이동·commit/push 없음.
PC·로봇 runs/tag_tbb_candidate_trial_20261024에 run.py, commands/settings/파라미터, 영상 표본, 로그, receipt.json(종료코드·시간), robot_status.json 보존. PC에는 processes_after.txt도 보존. 후보는 운영 적용하지 않았으며 추가 후보 수정/실행 전 보고한다.


### 2026-10-24 TBB 잔존 arena 추적·v2 후보 오프라인 검증
OpenCV 전역 task_arena가 노드 소멸 뒤 남는 구조 확인. 설치 ARM disassembly와 카메라 없는 remap 대조로 PC/ARM 각각 보존5회 finalize실패, 해제5회 정상종료 재현. v2 후보는 node/executor 정리 후 cv::setNumThreads(0)→TBB finalize→loader 해제, 실패 보호 유지. 양측 합성 OpenCV 노드 SIGINT/SIGTERM/생성실패·순서·링크 검사 통과. 운영원본/설정 SHA·백업 바이트 일치, harvest270128 유지. 카메라 재실행/운영 적용/이동/commit/push 없음. 실제 영상 재검증 전 해결 확정 금지. 근거 runs/tbb_shutdown_candidate_v2_20261024/README.md 및 상세 인계감사문서. 이전 v1과 백업 보존.


### 2026-10-24 TBB v2 실제 영상 종료 시험 통과 (1회)
사용자 카메라 전용 v2 실행 승인. 원본 카메라/monitor 및 영상 설정 그대로, rectify/apriltag 실행 파일만 runs/tbb_shutdown_candidate_v2_20261024/build 후보 선택. 운영 launch/바이너리 교체와 보정 adapter·이동 요청 없음. 기준 cf870da 및 기존 미커밋 변경 보존.
120.035초 실행, raw/rect/detections 각각939표본, tag100 검출. camera/검출기/rectify/monitor 모두SIGINT 종료0. 검출기0.264714초, rectify0.267155초(신호 전송~프로세스 wait 관측의 monotonic 경과). camera0.465257초,monitor1.867278초,전체3.865244초(카메라 후1초 대기 포함). 기존 검출기/rectify4초 제한 내 종료,TERM/KILL없음. 두 로그 모두 OPENCV_ARENA_RELEASED→TBB_FINALIZE_BEGIN→TBB_FINALIZED→COMPONENT_LIBRARY_RELEASED 확인. 이전 원본-11/v1 exit3과 달리 이번 v2 실제 영상 종료 정상.
운영 카메라3스크립트/설정SHA 전후동일, /opt/ros 실행파일2개 원본 백업과 동일, harvest270128/launch270080 유지. 시험 자식모두종료. 영상 중 별도15초 읽기 odom453개 비영0/IDLE 확인(전체120초 연속 odom계측은 아님). 카메라 설정 복원 기록 보존. PC·로봇 runs/tag_tbb_v2_trial_20261024에 commands/settings/후보SHA/영상표본/로그/receipt.json/보존검사 저장,31파일복사SHA일치검증. Git commit/push없음.
이번 한 차례 카메라 종료 시험 통과이며 장시간/반복 종료·주행과 태그보정 통합·control_readback_stale 원인 해결은 별도. 운영 설정은 여전히 원본 실행 파일 사용. 다음 운영 적용은 사전 안내 필요.


### 2026-10-24 v2 종료 처리 운영 경로 반영 — 재기동 대기
사용자 운영 적용·백업·원복 준비 승인. Git cf870da+기존 미커밋 변경 유지. PC/로봇 robot/ros_ws/src/farm_tag_camera_runtime에 실제 시험한 v2 C++/헤더 바이트 그대로 추가, ament 설치용 CMake/package.xml과 설치 선택 검사 추가. 양측 colcon에서 새 패키지만 빌드. 기존 harvest/Nav2/AMCL 패키지는 빌드·재시작하지 않음.
robot/tools/tag_camera/pinky_tag_capture_compare.py가 기존 /opt/ros 실행 파일 대신 ament index의 farm_tag_camera_runtime/{apriltag_safe,rectify_safe}를 선택. 기존 명령 인자/검출·카메라 설정/종료 제한은 불변. 누락·권한 오류 시 시작 전 실패, 자동 원본 fallback 없음. settings.json에 실행 파일 경로·SHA 기록 추가. /opt/ros 바이너리와 기존 v1/v2 후보·백업 보존. 시뮬 ROS 영상 launch 불변.
PC 오프라인 캡처/설정/세션/실행 선택21건 통과. 최초2건은 시험명령 PYTHONPATH에서 ROS 경로를 제외한 ModuleNotFoundError; 환경 수정 후21건 통과. 임시 복사본 원복3건(정상복원/원본상태/추가변경거부) 통과. 로봇 새 env source에서 설치된 두 바이너리 경로 확인, v2 소스동일, 나머지 카메라2파일+trial_io 및 설정SHA 동일, harvest270128유지. 캡처 적용 SHA 2f21f848041b5e2307233387ec33a0ccd74d3c82c961d48abcd88fc0d1450451. 카메라 재기동/이동/commit/push 없음. 운영 경로 실제 재기동 검증은 아직 미수행.
PC/로봇 runs/tag_tbb_v2_deploy_20261024에 capture.before.py/after.py, 빌드·적용 receipt 및 rollback.py 보존. 카메라 종료 상태에서 로봇 터미널 `python3 /home/vic/vmany/main/farm_project/runs/tag_tbb_v2_deploy_20261024/rollback.py`로 실행 선택 원복. PC는 같은 경로의 /home/eunbi 사용. 실행 중 카메라 또는 적용 후 추가변경이 있으면 거부. 새 패키지는 남아도 원본 스크립트가 참조하지 않으며 삭제/기존노드 재기동 불필요. 새 설치만 복사할 때 farm_tag_camera_runtime을 빌드 목록에 명시한다. 원복 도구는 프로세스 시작/종료하지 않는다.


### 2026-10-24 운영 캡처 경로 v2 실영상·종료 검증 통과
사용자 카메라만 재기동/정상종료 검증 승인. 운영 pinky_tag_capture_compare.py를 변경 없이 subprocess 실행, 기존 캘리브레이션·manual_2ms·검출 파라미터 그대로 사용하고 출력 폴더만 별도 지정. 실제 ament 설치 경로 farm_tag_camera_runtime의 apriltag_safe/rectify_safe 선택을 settings.component_runtime 및 commands.json으로 확인. fleet 주행 노드·보정 adapter 재기동/주행 명령 없음.
약2분 시험, raw/rect/detections 각950표본,tag100검출. 운영 부모+camera/detector/rectify/monitor 모두exit0,process_exits.clean_shutdown=true,예기치않은종료없음,SIGINT만 사용. 검출기·rectify 각각 OpenCV arena 해제→TBB_FINALIZED→COMPONENT_LIBRARY_RELEASED 확인. -11/TERM/KILL없음. 운영 스크립트는 수정하지 않고 외부 수집기가 STOPPING/EXIT 출력 수신시각(monotonic)을 기록: 검출기0.264560초,rectify0.265867초,camera0.414579초,monitor0.565077초. 이는 정확한 OS 신호~exit 시각이 아닌 로그 관측 구간이다. 부모 SIGINT 요청~수집 종료2.736272초.
기존 운영 코드3파일/카메라설정 SHA 전후동일, 기존 성공 주행 PID270128/launch270080유지,시험자식 모두 종료. 별도15초 odom455개 비영0/IDLE. 카메라 controls_restored=true. 검출파라미터 이전v2시험과동일. 로그·종료시간·실행해시·표본은 PC/로봇 runs/tag_operational_v2_trial_20261024, 실제 세션 capture/20261024_060235_la99uakv. PC복사32파일SHA일치 확인. 원복백업/도구 유지,commit/push없음.
검증 범위는 운영 캡처 스크립트와 설치 실행파일의 카메라 전용 시작·영상처리·정상종료 1회. 전체launch 재기동·태그보정/주행 통합·장시간 반복·설정조회 stale 원인 해결은 이번 검증에 포함하지 않는다. 현재 카메라는 종료 상태,주행노드는 유지.


### 2026-10-24 카메라→태그 보정 정지 연결 확인
사용자 정지 연결 확인 요청 후 카메라·어댑터가 모두 종료 상태임을 확인하고 재기동 범위를 사전 고지. 운영 tag_capture_session만 기존 environment에 지정된 capture config와 runs/tag_bias_trial/20261023_165950_381707_on/localization.yaml로 잠시 실행. 주행/AMCL 유지, 작업 활성화·보정·initialpose·이동 명령 미발행. 설정/코드 변경 없음.
새세션 runs/harvest_tag/20261024_060658_l_wtlwis,하위20261024_060659_8h_4ce7t:raw/rect/detections418개,tag100검출. 실제어댑터FD17이새detections.jsonl을열었고5초간읽기위치89623→114588로각시점파일끝까지전진. 이전세션재사용아님.
DDSgraph: harvest_motion_server control publisher→adapter/AMCL subscriber, adapter correction publisher→AMCL subscriber, AMCL events publisher→adapter subscriber 확인. AMCL read-only parameters tf_broadcast=true,protocol=scan_sync_v1,robot=harvest_01,map=many_farm_v1 일치. 이는 연결·계약 확인이며 실제 보정 적용 왕복 성공을 의미하지 않음.
35초읽기관측control/correction/events각0,odom1052표본비영0. 어댑터 start/closed 기록 correction_requests=0. 유효작업lease없으면출력을차단하는기존보호를유지했으므로정지대기는정상이며보정성공으로표기하지않음. 영상→관측계산→AMCL 실제적용은유효작업구간에서별도확인필요,이번에는작업신호를인위적으로발행하지않음.
시험후adapter/capture부모및camera/detector/rectify/monitor전부exit0,clean_shutdown=true,-11/강제종료없음. 세션SIGINT→부모종료3.834초. 시험자식종료,기존launch270080/AMCL270098/harvest270128유지. 설정·설치/소스모듈전후SHA동일. 현재카메라·어댑터는시험종료상태. 로그는PC/로봇runs/tag_stationary_link_20261024,로봇원세션도보존;PC에원세션전체추가복사. commit/push없음.


### 2026-10-24 주행 중 태그 보정 시험 준비 — 이동 미실행
사용자 요청에 따라 읽기 조회/오프라인 준비만 수행. 현재 map추정(1.138854,-.029044),yaw-.010128rad(-.58도),IDLE/readytrue/load2/활성작업없음,최근odom30개정지. 일반64x54/인계62x52 footprint일치,정지costmap하한.1104/.1204m,unknown0. 이는실측정합/전체경로안전확정아님. cmd_vel_nav단일harvest_motion_server,odom단일driver. launch270080/harvest270128/AMCL270098/일반bridge270566/더미bridge270640 실행중. PCdummy172229/bridge172290 실행중,최신더미IDLE/readytrue/recoveryfalse. 카메라·보정종료상태.
웹읽기에서수확Action연결,#57기존목표(1.186,-.035)완료와#59 25fabab7b348_SEC01_W001 목표(1.601,-.035)예상1개선택대기확인. 저장작업상세에서정밀목표1.6006447347066082,-.035,yaw0 및 TASK001 ID확보. 현재→#59 직선거리.46183m,저장일반costmap 직선후보검사PASS 하한.10580m. 실제Route/FollowPath계획을획득한것은아님. 더미journal에#59task ID없음,반복허용서비스미호출. #57재전송은거리부족/반복ID보호문제로이번시험선택안함. 웹Goal전송/선택변경없음.
PC/로봇 runs/tag_motion_prepare_20261024에 current check,selected_task_NOT_SENT,straight_candidate_check,사용자용start_camera.bash,추후에이전트구독전용collect.bash 준비. bash syntax통과,두스크립트미실행. start_camera는기존환경과기존보정프로파일로tag_capture_session만실행·로그tee·중복프로세스검사. laun/vinit/zen/dzen/PCdummy 재기동불필요;현재window이므로vinit금지. 사용자카메라기동/웹표시확인뒤최신상태·현장정지가능여부확인과수집시작,이동방향안내후사용자가#59만선택해수확시작할예정. 아직전송하지않음.
성공조건: 실제WINDOW_MOVE 중control lease와동일세션의TAG_CORRECTION_SENT→AMCL tag_correction_applied(발행만으로성공아님),주행완료/새window기준/더미결과를대조. 태그ROI/관측조건부족으로보정0회면주행성공과별도로미검증기록,조건완화/자동반복없음. 코드·설정/기동/이동/commit/push없음.


### 2026-10-24 #59 전송 전 점검 — 기동 보조 스크립트 오류 수정
사용자 카메라기동/웹표시보고후실제프로세스조회에서카메라/어댑터없음확인. 준비한start_camera.bash와collect.bash가set -u 상태에서Jazzy setup을source하여 AMENT_TRACE_SETUP_FILES: unbound variable로중단되는문제재현. 운영영상/TBB코드문제가아니며에이전트제공보조스크립트오류. 원본을양측runs/tag_motion_prepare_20261024/source_env_fix에백업하고source동안만nounset해제,이후복원하도록수정. 기존운영코드/설정불변. bash구문/환경source검증후사용자동일명령재실행필요. 카메라자동재기동/웹전송/이동없음,#59전송보류. 영상기동확인후bag수집을시작해야하며현재수집미시작. commit/push없음.


### 2026-10-24 #59 주행 전 연결 확인·로그 수집 시작
사용자 TAG_ADAPTER_STARTED/현위치유지·이동가능확인후 최신읽기검사. 카메라세션 runs/harvest_tag/20261024_061926_bm7gpkmi/20261024_061927_3iqz3xrc,영상·검출약8~9Hz/tag100/control_readytrue/fault없음. adapter305752와AMCL control/correction/events연결·scan_sync_v1/robot/map계약일치. harvest270128 IDLE/readytrue/현재목표없음/이전window위치유지,관측odom비영0,일반/인계정지costmap통과. PC더미IDLE/readytrue/recoveryfalse.
사용자승인으로구독전용bag수집시작,최대600초/SIGINT종료상한. runs/tag_motion_live_20261024/recorder.json에소유PID/명령,recorder.log에전체요청토픽구독완료확인. control/correction/events,task_events/status,odom/amcl_pose/TF,scan/filter,cmd_vel_nav,일반costmap/footprint포함. 카메라자체검출·보정events기록도계속유지. 점검결과/더미상태PC사본보존.
준비된#59 25fabab7b348_SEC01_W001 예상1개(목표1.600645,-.035,0)만웹에서사용자가한번보내도록안내. 현재대비약46cm앞목표이며실제경로는주행기가결정. 에이전트이동/수확Goal전송없음,아직주행·보정적용성공미확인. 기존코드/설정/안전조건불변,commit/push없음. 사용자가보냈다고알리면같은세션요청·AMCL적용·window도착·더미결과대조,완료후수집기만종료할것.


### 2026-10-24 웹 #59 완료 — 주행/더미 성공, 태그 보정 적용 0회
사용자웹전송후추가Goal없이로그대조. #59 task=25fabab7b348_SEC01_TASK001/window=25fabab7b348_SEC01_W001,event7357b74e8b404edc82c335d600a3516c. 06:21:56 KST SECTION_RESUME→WINDOW_MOVE,FollowPath nav2status4/ARRIVED. 06:22:06.858 도착(1.559834,-.023754,yaw-.015347rad),목표(1.600645,-.035,0),위치오차42.332mm<50mm,방향.879도<약3도,accepted=true. 새arrival request fe76a5fc659f4d6d81eec0761ddfc3f0. 설치communication.py는SUCCESS에서remember_window→handle.succeed 순서 확인(내부메모리를직접조회한것은아님).
06:22:08.555 작업SUCCESS/ARM EXECUTED. PC더미동일ID 영속terminalSUCCESS attempt4f167399130346ceb5ba9657621198bd,수확2/실패0. expected1과결과2의차이는서버--targets기본2,expected_count를상한으로쓰지않는기존더미시나리오이며실물팔수확아님. 최종IDLE/readytrue/활성작업없음/load4,odom451표본비영0.
태그통신은정상: bag control28/AMCL events26(전부tag_control_accepted). correction메시지0/요청0/적용0. 어댑터observation35개selected0. 동일stamp원검출35개와설치본동일SHA roi_accept 재판정: 실제보정ROI 가로60%·세로80%,x[256,1024),y[72,648),네모서리모두내부조건. tag100 11개왼쪽밖,tag101 24개오른쪽밖,상하밖0,통과0. 따라서영상태그검출→작업lease/관측진입은확인됐으나사용가능ROI관측없어보정요청전제외. 단순통신고장이나AMCL거절로해석하지않음. roi60모니터(60%정사각형)와실제ROI구분유지. 향후태그가실제ROI안에들어오는구간/카메라시야를기존기록으로확인해야하며안전/ROI조건변경이나자동재주행없음.
이번수집기306359만SIGINT정상종료,metadata저장. bag_20261024_062041 약57MiB PC/로봇SHA일치(1149ef08a7381b7ac6ad18fc2b9d1741e05690f006c104ca38507a6571aa2298),metadata도일치. PC/로봇 runs/tag_motion_live_20261024에추출events/states/counts/최종상태,PC에더미journal/영상세션사본/roi_analysis보존. 카메라·보정은사용자기동상태계속유지,주행/AMCL/브리지미재시작. 코드·설정·보호변경/이동재요청/commit/push없음. 이번태그보정실적용시험은미성공(0회)이며수확작업성공과구분.


### 2026-10-24 스테이션 재기동 후 #59 태그 주행 재시험 준비
사용자 전체 종료·실제 스테이션 위치/방향 이동 및 별칭 순서 재기동/웹 표시 확인. 기존 성공 코드·설정 변경 및 이동 요청 없음. harvest311315/AMCL311296/camera311318/adapter311606 실행 확인. 정지 odom452표본 비영0, IDLE/readytrue, cmd_vel_nav 소유자 harvest_motion_server 한 개·odom 드라이버 한 개. 현재 map 자세(.085089,-1.119479,1.529215rad), 스테이션 지정값 대비 약23.8mm. 원본scan 동일stamp map TF 비교694끝점: 점유셀 중심거리 중앙37.4mm,5cm내84.87%,10cm내89.77%,p90 216.1mm. 일부 환경/관측 차이가 남으므로 완전 정합·전체경로 안전 증명 아님. 일반64×54/인계62×52 실제 footprint 확인, 현재자세 및 +.1rad 오프라인검사 통과.
카메라 약8Hz/control_readytrue/fault없음, 현재 태그 미검출. harvest→control→AMCL/adapter, adapter→correction→AMCL, AMCL→events→adapter 연결 및 scan_sync_v1 확인. 작업 전 control/correction/events 0회는 작업대기와 구분. PC더미IDLE/readytrue/recoveryfalse, 수확/배출Action과 prepare/stop 서비스 연결. 웹 수확Action 연결·최신위치 수신, #59/#57 완료 목록 읽기만 수행.
사용자 재시험 범위로 #59(25fabab7b348_SEC01_TASK001/W001)만 PC더미 repeat_last_harvest 1회/300초 허용 성공, 기존journal 복사 보존; #57 허용 아님. 06:34:14 KST 허용, 약06:39:14 만료. 사용자 웹 전송 전 상태이며 에이전트 Goal 없음. 06:34:03 구독전용 수집 전체15토픽 연결 완료, 소유timeout PID313447/최대600초. 로봇 runs/tag_station_retest_20261024/bag_20261024_063402 및 PC 동일폴더에 점검/허용/백업 보존. 태그실적용/주행/더미완료는 이번 시험 아직 미검증. commit/push 없음.


### 2026-10-24 #59 스테이션 재시험 — 주행 중 AMCL 보정 1회·window·더미 완료
사용자 웹 #59 전송만 관찰, 추가 이동/인계 요청 없음. 기준 cf870da 및 기존 미커밋 변경 유지. 06:34:50 KST SECTION_APPROACH 시작→06:35:49.730 ARRIVED→WINDOW_MOVE→06:36:01.824 ARRIVED. 두 단계 nav2status4. 새 도착 request3743062914d2446d9d8beef69dbbe09f/plan d345ff727a50490db6edd1ca71f1ef20; 실제(1.581903,-.011735,yaw-.009188rad), 목표(1.600645,-.035,0), 위치오차29.874mm/방향.526도, 기존50mm/.05236rad 조건 accepted=true. SUCCESS 경로 remember_window 호출은 코드 확인이며 메모리 직접조회와 구분.
이번 실제 주행 중 태그100 관측→동일token1639b1e2872a47d1b6e46ebec20de110/producer86ebb25426bb4d0199676992dd9eff7f/sequence1 요청→queued→AMCL tag_correction_applied 확인. 06:35:52.153 적용, scan_stamp1792791352007843075, reason scan_aligned/filter_initialized=true. 보정시점 최근 odom 약.060m/s(직전.0615/직후.0597)로 실제 이동 중 적용 근거 확보. 카메라 검출만/요청 발행만의 성공이 아님.
06:36:03.519 전체SUCCESS/ARRIVAL_THEN_ARM. PC더미 새 attempt312e370f20ce4d96b64dbb642b2b7744 terminalSUCCESS,수확2/실패0,기존#59기록은history보존. expected1/더미결과2는 기존 --targets=2 시나리오이며 실제팔아님. 최종IDLE/readytrue/활성작업없음/load2,정지검사odom453표본비영0,출력소유자1.
남은 문제: SECTION_APPROACH 제어token84c57fc37157468c868ff0615b9f4585는begin1792791290584018999<barrier1792791290585771322(1.752323ms)로AMCL inactive_or_task_begin120회거절. bag앞부분에첫token enable→disable→새token enable이연속됨. task_ended invalidate에서수신현재시각barrier를쓰는코드와전환경쟁가능성은부합하나barrier변경원인직접로그없어확정하지않음. 이후WINDOW_MOVE 새token은수락하여실제적용성공. 전체보정제어경로가무결하다고보고하지않으며안전조건완화/코드변경/재시작없음.
완료정지확인후이번수집기313447만SIGINT종료/metadata작성확인. bag 및 camera세션/launch_snapshot/분석events·상태·적용시점odom·더미journal을PC runs/tag_station_retest_20261024에보존,로봇원본보존. mcap SHA256 080d883f32e6733e49262212d4ac49ba6f7d534379e707d3d4b12b852f925352 및metadata7e5189f3104912b06c0213f37c611497460f7f5c6d468049e8b0040e02351d5d 양측일치. 인계시험미실행;현위치유지,별도진입점검·안내후진행. commit/push없음.


### 2026-10-24 #59 도착 후 웹 인계 시험 준비
사용자 인계 시험 요청. 현재 map(1.581903,-.011735,-.009188rad)/IDLE readytrue/load2,odom452표본비영0;이전인계journal active/recovery_required없음. DockTransfer/TransferEvent 서버 및 PC더미 수확/배출/prepare/stop 연결 확인. 인계62×52 및 일반64×54 현재자세/+0.1rad 오프라인충돌검사통과(인계현재하한.1354m),전체진입경로통과로일반화하지않음. 기존안전조건/성공코드불변. 사용자웹dock_transfer 수동전송대기,DOCK_READY까지확인예정;배출·복귀이벤트/운송로봇동작대행없음. runs/handoff_after_tag_20261024에읽기전용검사와구독수집기PID316724/900초상한기록. 인계Goal은아직보내지않음. commit/push없음.


### 2026-10-24 #59 후 웹 인계 — 곡선 완료, 벽 관측 시각 실패
사용자 dock_transfer 전송. DOCK_TEST_a0aefa4082974daa8159e68436ed031b / TRANSFER_TEST_a2cda2e6d875403796e24584b0cfaa21. 06:40:15.715 KST 시작, 인계controller 06:40:18.084 goal→06:40:32.736 Reached goal(후진곡선). 06:40:35.012 벽정렬goal→06:40:35.069 Wall observation expired / future→abort. 06:40:36.733 journalFAILED/activefalse/recovery_requiredtrue,Actionstatus6. bag의Actionfeedback0개로DOCK_READY미발행확인. 배출/복귀요청없음. 현재ERROR/readyfalse/load2, map(1.432120,-.130576,yaw1.631119). 최근odom61표본비영0 및사용자현장정지확인.
wall_control.hpp의 w.stamp>now 또는 now-w.stamp>observation_age 공통문구조건. 이번로그만으로과거만료/미래시각어느쪽인지·실제차이수치확정못함. 충돌장애물실패로해석하지않으며기준완화/설정변경/재시작/초기위치/재진입없음. 다음이벤트전송보류.
수집기316724만SIGINT정상종료/metadata확인. runs/handoff_after_tag_20261024에bag/launch_snapshot/transfer_after/live_observation/action_events 및costmap을PC사본포함보존. 주행·카메라·브리지유지. Actionfeedback메시지정의bag임베드경고있으나구독완료,PC설치인터페이스로status해석성공;feedback자체는0개. 기존로그/코드/설정불변,commit/push없음. 다음은실패시각센서/벽관측/시각기준추적이며인계성공으로표시하지않음.


### 2026-10-24 0.45초 후보 운영 설정 적용·종료 확인
사용자백업유지/실행본적용/종료·재기동절차승인. 종료전ERROR·odom91표본0,실패transfer기록백업. 카메라311318→launch311278→로봇브리지311773/311836 정상종료,자식포함remaining[];PCdummy196592/bridge196652도기록백업후종료remaining[].최종로봇관련프로세스검색없음. 런치종료중harvest Destroyable 경고1회후finished cleanly;정상종료경고문제까지해결됐다고표시하지않음.
공용wall_alignment_trial.json불변. /home/vic/Downloads/pc_dummy_dock_fsm_20261024/wall_alignment_045.json 신규전용후보배치,동폴더handoff_fsm.json의wall_config참조만변경. observation_age/max_gap_s=.45,dwell=.5,padding=.01 유지. 실제설치구성생성기로controller/observer설정오프라인일치검증,노드기동없음/빌드불필요(JSON선택변경). runs/wall_timing_deploy_20261024에로봇·PC원본/배포receipt/검증/종료PID/rollback.py보존. 원복은프로세스부재·afterSHA검증후원래handoff참조복원,신규설정파일미참조로보존.
현재실패journalrecovery_required유지(물리복구전해제하지않음). 사용자에게드라이버종료확인후스테이션재배치가능시점안내. 스테이션위치·방향이동확인받은뒤이번실패원문보존+수동복구기록을추가하고재기동하도록할것. 아직재배치확인/복구해제/재기동/초기위치/이동없음. PC더미도기동후복구상태조회필요. 사용자기동순서PCdummy→PCbridge→로봇laun→vinit→zen→dzen→vstat,웹연결확인후파라미터·정합·costmap·더미·새window기준점검. commit/push없음.


### 2026-10-24 06:56 KST 스테이션 재배치 확인·수동 복구 기록
사용자가 기존 스테이션 위치·방향으로 직접 옮겼음을 확인했다. 로봇 launch/드라이버/수확/controller/카메라/브리지 프로세스가 없는 상태를 확인한 뒤, transfer.json의 DOCK_TEST_a0aefa4082974daa8159e68436ed031b 항목만 수동 복구 처리했다. result_code=FAILED와 active=false 및 다른 기록은 보존하고 recovery_required=false와 manual_recovery 근거/시각을 기록했다. 변경 전후 원본은 PC·로봇 runs/wall_timing_deploy_20261024/manual_recovery/transfer.before.json 및 transfer.after.json에 보존했다. 이는 물리 재배치 후 복구 기록이며 인계 성공 판정이 아니다.
PC 더미 PID204039 및 PC 브리지 PID204098은 이미 실행 중이다. 로봇은 사용자 laun→vinit→zen→dzen→vstat 재기동 대기이며 에이전트가 기동·초기위치 발행·이동하지 않았다. 0.45초 후보 런타임 적용, 정합/costmap, 더미 준비 상태는 기동 후 재확인 필요하다. 초기위치 발행 실패의 정확한 터미널 출력은 확보하지 못했으며, 남아 있던 recovery_required가 수확 노드 ERROR 및 vinit의 IDLE 선행 조건을 막는 코드 경로는 확인했다. commit/push 없음.


### 2026-10-24 0.45초 후보 재기동 후 정지 상태 점검
사용자 순서 기동·웹 표시 확인 후 읽기 전용 점검. 로봇 launch324533/harvest324564/AMCL324543, 후보 파일 수정06:50:54 이후06:58:39 기동. 실제 /harvest_01/handoff/controller_server wall_alignment.observation_age=0.45, dwell=0.5 응답 확인; 최초 WallAlign.observation_age 조회는 잘못된 키로 Parameter not set였으며 실제 선언 키로 재조회했다. observer max_gap_s=0.45는 선택된 JSON과 시작 시 로드 경로 기준 확인이며 Python 내부 메모리 직접 조회는 아니다. AMCL active, 수확 IDLE/ready=true/task 없음/load0, odom444개 비영0. cmd_vel_nav/odom publisher는 각각 harvest_motion_server/vic_pinky_bringup 하나씩.
현재 map(.086064,-1.083511,yaw1.538461rad), 지정 스테이션 대비 위치28.0mm/방향약0.357도. 동일시각 TF 레이저689점 비교 중앙40.6mm, 5cm 이내87.23%,10cm 이내89.40%,p90 222.4mm. 이전 점검과 유사하나 환경 차이를 포함하며 완전 정합 증명 아님. 일반 footprint64×54cm·인계62×52cm, 양 costmap 해상도0.02m/unknown0, 최신 수신 및 현재 자세·+.1rad 오프라인검사 통과. 실제 회전/전체 경로 검증 아님.
PC 더미 runtime_status 5개 수신: ERROR/ready=false/recovery_required=true, active ID 없음, 팔 정지·접힘/박스 닫힘 모델. journal의 기존3건은 모두 terminal SUCCESS/recovery=false이며 최상위 복구 래치만 true로 남음. 래치 발생 시각·원인은 이번 자료로 확정하지 않는다. 로봇에서 arm/discharge Action 및 prepare/stop 서비스 발견은 모두 성공했으나 서비스 실행 준비 완료와 구분한다. 웹 작업은 더미 복구 및 반복 허용 전 보류. 이번 요청은 확인 범위이므로 recover/prepare/repeat/Goal/초기위치/재기동 호출 및 설정변경 없음.
PC·로봇 runs/wall_045_restart_check_20261024에 costmap/footprint/상태 보존, PC에 runtime_params.log/robot_check.log/dummy_status.json/dummy_journal_readonly.json 포함. 코드·설정 변경 및 commit/push 없음.


### 2026-10-24 PC 더미 복구·동일 웹 작업 1회 허용
사용자 명시 승인에 따라 기존 journal을 runs/dummy_recover_045_20261024/journal.before.json으로 백업한 뒤 Recover(DEVICE_AND_LOAD_RECONCILED) 성공, prepare 성공을 확인했다. 새 RuntimeStatus IDLE/ready=true/recovery_required=false/활성 ID 없음, 가상 팔 정지·접힘/박스 닫힘. journal.after.json과 비교하여 records 및 history 내용 동일함을 확인했으며 최상위 복구 래치만 해제했다. 실제 팔 검증이 아닌 PC 더미 통신 모델이다.
repeat_last_harvest 성공: 기존 #59 task25fabab7b348_SEC01_TASK001/window25fabab7b348_SEC01_W001에만1회, 07:02:49~07:07:49 KST 300초 허용. 실행 중 중복 방지 코드 및 기존 성공 코드/설정 불변. 이동·인계 Goal, 재기동, 초기위치 발행 없음. 사용자 웹 전송 대기. 서비스 응답/상태/변경 전후 journal은 위 폴더에 보존. commit/push 없음.


### 2026-10-24 07:05 KST 0.45초 후보 기동 후 #59 window·더미 성공
사용자 웹 #59만 전송, 추가 이동/인계 요청 없음. SECTION_APPROACH ARRIVED(07:04:49), WINDOW_MOVE ARRIVED(07:05:01.962), 두 nav2_status=4. 새 arrival request7e3c78ed9bdc45458031bc79cbec7e0e/plan8f758eca22b8400ba7a3210ca6e89f87, 위치(1.582115,-.008944,yaw-.027477rad), 목표(1.600645,-.035,0), 오차31.973mm/1.574도, 기존50mm/.05236rad 허용조건 accepted=true. 07:05:03.637 전체SUCCESS/ARM EXECUTED.
PC더미 새 attempt d87bf81e80b54a6c83054d5187c59873 terminalSUCCESS, 수확2/실패0/recovery=false, 이전attempt와 구분했다. expected1/결과2는 기존 더미 targets=2 모델이며 실제 팔 수확 아님. 실제 설치 communication.py 성공분기에서 runtime.remember_window(goal,controller.outcome) 이후 handle.succeed 순서를 확인했고 새arrival을 포함한 완료 이벤트와 대조했다. 내부 self.window 메모리를 직접 조회한 것은 아니다. AMCL 로그 TAG_CORRECTION_APPLIED 1회도 확인.
최종 IDLE/readytrue/활성작업없음/load2 및 odom 비영0 확인. 인계 Goal/DOCK_READY/배출/복귀는 이번에 실행하지 않았다. 0.45초 설정의 벽정렬 실기 성공은 아직 미검증. runs/dummy_recover_045_20261024에 구독 상태/완료이벤트/설치 저장계약/런치로그/더미 새journal/최종정지검사를 보존했다. 주행 중간부터 구독하여 전체 주행 bag 수집으로 표시하지 않는다. 코드/설정/재기동/commit/push 없음.
정지 검증 odom 451개, 비영 0개.


### 2026-10-24 07:08 KST 0.45초 인계 시험 수집 준비
사용자 현위치 유지·이동 가능 확인 후 읽기 전용 점검: IDLE/readytrue, 실제 wall_alignment.observation_age=.45, 복구journal active/recovery_required없음. 일반64×54/인계62×52 현재자세 및+.1rad 오프라인충돌검사 통과(인계현재 하한.13427m); 전체경로 통과 보장 아님. PC더미 IDLE/readytrue/recoveryfalse/팔정지·접힘/박스닫힘 모델 및 로봇 arm/discharge Action·prepare/stop 연결 확인.
runs/handoff_045_live_20261024 수집 시작. 최초수집기328910에서숨김Action토픽제외경고확인해해당수집기만SIGINT종료,초기bag보존. --include-hidden-topics 추가한수집기329429/900초상한재기동, wall_observation·raw/filtered scan·TF·odom·costmap·footprint·cmd_vel·DockTransfer feedback/status 포함19토픽구독완료. Action메시지정의bag임베드경고남음(구독완료,설치된인터페이스로역직렬화필요). 기존주행/카메라/브리지재기동없음. 벽관측header와수신시각대조가능하나controller내부가선택한샘플직접계측은아님. 사용자웹dock_transfer전송대기,에이전트Goal없음. DOCK_READY확인전다음이벤트보류. 코드/운영설정/commit/push없음.


### 2026-10-24 07:09 KST 0.45초 인계 실기 — 벽 관측 만료 재현
사용자 웹 dock_transfer 전송: DOCK_TEST_5793582207d24bc4a9beabdafcae85b8 / TRANSFER_TEST_ad18052db4a24695993b24354f03bd89. 07:08:37.999 시작, 후진곡선 goal07:08:40.180→07:08:54.781 Reached. 벽정렬 goal07:08:56.797→07:09:06.498 Wall observation expired / future, 약9.701초 뒤중단. 최종07:09:08.290 FAILED/activefalse/recovery_requiredtrue. Actionstatus1→2→6,feedback0개로DOCK_READY미발행. 사용자현장정지확인,구독최근odom10표본비영0. 재진입/복귀/배출/설정변경없음.
이번에는 wall_observation421개와raw/filteredscan각992개포함bag확보. 오류직전마지막외부벽관측 stamp1792793346044316693,수신1792793346167674992,수신시age.123358초. 오류시각1792793346498081125에서해당stamp age=.453764초로실제.45한계를넘는다. 다음벽관측은오류후.051초수신,수신age.403초;오류직전~직후벽관측수신간격약.381초. 같은시각최신filteredscan은오류.041초전에수신되고headerage는오류시점.151520초. 따라서이번수집은미래stamp보다벽관측업데이트지연에따른만료와부합한다. controller내부선택sample직접로그없으므로동일sample사용확정은아니며,관측계산/TF대기/스케줄링/내부전달중어디인지미확정. 원시레이저전체중단으로단정하지않음. .45확대만으로문제해결안됨,추가완화없음.
소유수집기329429만SIGINT종료,두bag metadata확인및PC사본보존. runs/handoff_045_live_20261024에live.jsonl/transfer_after.json/launch_snapshot.log/bag/timing_analysis.json/analyze.py. 사용자현위치유지,주행/카메라/브리지계속실행. 코드·설정·초기위치·재기동·commit/push없음.


### 2026-10-24 인계 중단 조건 전체 검토·정지 대기 후보
사용자가 벽 관측 외의 불필요한 중단 조건도 제거/조정 요청. 로봇 최신 소스를 runs/handoff_guard_audit_20261024/source에 확보하고 후보 디렉터리만 수정했다. PC runtime은 로봇과 달라 덮어쓰기 금지 유지. 공통 wall_controller/WallTracker 및 harvest runtime 후보5개 파일, 전용JSON과 patch 작성. 벽header만료·수신없음·표본gap·tracker재획득·준비단계 stale pair를 통합 처리하며 default는 기존정책, 후보만 observation_wait=.8초/stable재획득 선택. 충돌/취소/소유권/미래시각/odom/costmap 유효성 유지. 상세 중단조건 표·남은문제는 runs/handoff_guard_audit_20261024/REVIEW.md.
PC Jazzy 공유라이브러리 별도빌드 성공, 기존861assertions/ctest1통과, 새정지대기C++/tracker/runtime분류오프라인검사통과. ROS통합·전체인계·실기미검증; wall/align snapshot 및 상위watchdog 경로가 남아 모든 지연해결로 표시하지않음. 운영소스/설치/실행설정 불변,재기동/이동/commit/push없음. 후보 적용 전 안내 필요.


### 2026-10-24 watchdog·wall/align 후보 v2 통합검사
사용자 후보 보완·통합검증 승인, 운영 적용/재기동/이동 전 안내 유지. 후보 runtime에서 wall 최신 입력 재검증, align 최신 costmap 키·최신 자세 clearance 재검증을 연결했다. 증명 재계산은 실제 controller 입력을 받은 경우 0 출력으로 최대3초 대기하며 기존 .3초 watchdog은 유지한다. Navigator live guard도 취소 가능한 bounded wait로 연결하여 callback 외 경로의 즉시 실패를 보완했다. epoch/취소/정지/소유권/세션·충돌·freshness보호 유지.
실제 메서드/gate/clearance 통합16, guard 경로4, 실제스레드경쟁4 검사 통과. 실패bag→후보C++ Control 199개 재생(max age .502972초) 통과. PC격리loopback domain191 시험토픽 DDS→실제후보메서드/gate 199개 일치, 입력단절시watchdog정지 확인. 기존861assertions/ctest 및기타후보검사통과. 주변Node/센서/시각은harness이며전체Nav2 Action/실물부하 통합검증과구분한다. 모든조건/지연해결이나실기성공으로보고하지않음.
로봇현재원본5파일hash가보관source와일치. 운영소스/설치/설정/프로세스불변,실물이동/재기동/commit/push없음. runs/handoff_guard_audit_20261024/REVIEW.md의v2표·검증한계와candidate.patch/manifest/검사로그참고. 적용전로봇아키텍처빌드·배포·재기동절차준비필요.


### 2026-10-24 정지 대기 v2 로봇 빌드·설치 적용
사용자 기존핫픽스백업/로봇빌드/실행본적용/종료·재기동절차 승인. 적용전odom91개비영0 확인. camera324570,launch324533 및자식,로봇브리지325032/325095 SIGINT종료,선택28개remaining[] 및최종프로세스부재확인. 드라이버종료후사용자에게스테이션재배치가능안내. 아직물리재배치확인없어실패DOCK_TEST_5793582207d24bc4a9beabdafcae85b8의recovery_required=true는유지했다. 실패원문/결과FAILED 보존.
로봇원본5파일hash와후보manifest대조후 source5개+install3패키지 original.tar.gz 백업. PC/로봇SHA256 6cd5f3ff8f408cc4a7a5ef80d5973ce47afd4115c4c6efed46b12f5f8628c509일치. 로봇colcon farm_navigation/farm_wall_controller/harvest_robot 순차빌드27초성공. underlay재선택경고있음;빌드실패아님. 로봇ctest1/1 및새C++정지대기검사통과. 설치Python2개hash후보와일치,설정생성기로 .45/.8/.5 및재획득선택검증.
/home/vic/Downloads/pc_dummy_dock_fsm_20261024/wall_alignment_wait_v2.json신규,기존handoff_fsm.json의wall_config참조만변경. age=.45/observation_wait=.8/dwell=.5/footprint_padding=.01,충돌·취소·정지·소유권보호유지. 실제노드기동없음. PC운영소스덮어쓰기없음. runs/handoff_wait_deploy_20261024에원본/배포receipt/빌드·검증/종료/rollback.py 보존. rollback은프로세스부재·afterhash일치후원본tar/설정복원,후보C++빌드캐시보존이동으로재설치혼입방지;문법검사만수행,실제원복미실행.
PCdummy204039/bridge204098은계속실행중으로중복기동금지. 재배치확인→실패기록보존수동복구→사용자로봇laun→vinit→zen→dzen→vstat 순서. 웹확인후실제파라미터·정합·costmap·더미복구상태확인필요. laun카메라포함. 종료중harvest Destroyable경고후finishedcleanly확인,기존종료경고까지해결했다고표시하지않음. 실기성공미검증/초기위치발행/재기동/이동/commit/push없음.


### 2026-10-24 07:30 KST v2 적용 후 스테이션 수동 복구 확인
사용자 기존 스테이션 위치·방향 재배치 확인. 로봇 harvest/controller/driver/camera 종료 상태 재검증 후 DOCK_TEST_5793582207d24bc4a9beabdafcae85b8 기록의 recovery_required만 false로 변경하고 manual_recovery 근거·시각 추가. active=false/result_code=FAILED 및 다른 기록 보존. 변경 전후 journal을 PC·로봇 runs/handoff_wait_deploy_20261024/manual_recovery에 보존. 사용자 laun→vinit→zen→dzen→vstat 기동 대기. 에이전트 재기동/초기위치/이동 없음. 웹 확인 후 실제 설정·정합·costmap·더미 준비 재점검 필요. commit/push 없음.


### 2026-10-24 07:32 KST v2 재기동 정지 상태 확인
사용자 순서기동·웹표시확인 후 읽기전용점검. 인계controller337741의maps가배포libwall_controller.so를참조하며수확337764포함배포파일최종mtime이후기동. deployment afterhash10항목모두일치. 실제ROS파라미터 wall_alignment.observation_age=.45, observation_wait=.8, dwell=.5 응답확인. 수확기동params파일handoff_config는승인된설정을선택,observer reacquire_after_gap=true는선택파일/설치코드기준확인(내부메모리직접조회아님). AMCL active.
수확IDLE/readytrue/활성작업없음/load0,odom452개비영0. 현재map(.094454,-1.108797,1.542578rad),지정스테이션오차10.27mm/0.593도. 동일시각scan686점의점유셀중심거리중앙4.47mm,p90 36.42mm,5cm이내90.38%;일부환경차이남아완전정합/전체경로안전증명아님. 일반64×54cm/인계62×52cm,해상도각2cm,unknown0,현재및+.1rad오프라인검사통과(실제회전없음).cmd_vel_nav출력소유자1,odom드라이버1.
PC더미RuntimeStatus4개수신,ERROR/readyfalse/recoverytrue/errorEXTERNAL_STOP,활성ID없음/가상팔정지·접힘/박스닫힘. arm/dischargeAction및prepare/stop서비스발견정상이나준비완료아님. 이번은조회요청으로recover/prepare/repeat/작업Goal호출없음. 다음은이력보존더미복구및반복허용후웹시험. runs/handoff_wait_restart_check_20261024에실행경로/hash/선택설정/파라미터/정합/costmap/더미상태보존. 코드·설정·초기위치·재기동·이동·commit/push없음.


### 2026-10-24 v2 #59 반복 준비
사용자 승인으로 PC더미journal.before/after 백업 후 recover/prepare 성공, RuntimeStatus IDLE/readytrue/recoveryfalse 확인. records/history 동일 검증, 기존실행이력보존. #59 task25fabab7b348_SEC01_TASK001/window25fabab7b348_SEC01_W001 1회 반복허용 07:33:45~07:38:45 KST. 실물팔검증아닌더미모델.
로봇구독수집기339493/600초상한 시작,14토픽(작업·상태·태그·TF·scan/filtered·odom·cmd_vel·costmap/footprint·AMCL) 구독완료. runs/window_wait_v2_20261024에수집정보·복구/준비/허용·journal보존. 사용자웹전송대기,에이전트Goal/이동/인계요청없음. 코드/설정/재기동/commit/push없음.


### 2026-10-24 07:35 KST v2 재기동 #59 — 일반 주행 충돌 예측 중단
사용자웹#59전송만관찰. 07:34:54.640 시작→SECTION_APPROACH 일반controller07:35:32.877 RegulatedPurePursuitController detected collision ahead→07:35:34.219 FAILED/NAVIGATION_FAILED(status6,error106). task25fabab7b348_SEC01_TASK001/W001, event72d62abc3f0a467fb346789b1ef6571f,requestdb7114c433fd40f1bdfed5c535907074,plan4394ad661d63476a8929a771913bc7d1. route는동일graphrevision의28/26/14엣지. 현map(.049570,-.111918,yaw1.027691),WINDOW_MOVE미진입/arrival없음/ARM SKIPPED/수확0.
PC더미최근attempt는이전07:05성공d87bf81e80b54a6c83054d5187c59873그대로로이번신규수확실행없음. 새도착기준저장성공으로표시하지않음. 최종IDLE/readytrue/load0이지만작업은실패이며,odom453개비영0확인. 사용자현장정지확인요청,현재응답대기. 재전송/초기위치재설정/인계요청없음. 이번인계용wall후보동작은미진입이므로wall수정실패나원인으로단정하지않음.
수집기339493만SIGINT종료,bag metadata완료및PC사본확보. runs/window_wait_v2_20261024에bag_20261024_073343/launch_snapshot/task_events/live/final_status/journal.after 보존. 코드/설정/충돌조건변경·노드재기동·추가이동·commit/push없음. 다음은동일코너의이전성공과실패costmap/TF/경로/자세비교이며물리장애물유무는아직확정하지않음.


### 2026-10-24 #59 반대 회전 조사·현장 정지 확인
사용자가 실제 정지를 확인하고 이번 변경과 반대 회전의 관계 조사를 요청했다. cmd_vel_nav -0.1→+0.1rad/s 및 odom 각속도 전환을 확인했다. 이전06:34 성공 코너와 다르다. 배포 백업/현재 설치 패키지 비교에서 계획된 인계 변경 외 일반 주행 코드 덮어쓰기 흔적 없음, normal 출력 분기 AST 동일, 현재/이전 성공 일반 controller YAML 값 동일, 일반 프로세스에 수정 wall 라이브러리 미로드 확인.
직전 map→odom 갱신을 같은 odom에 적용하면 map 위치 약23.7mm 차이. 0.1m 전방 경로 원 교점 가정의 방향은 -4.49→+16.56도로 변하며 기존 회전 기준6도를 넘는다. 위치 추정/짧은 lookahead에 따른 회전 선택 변화가 구체적 후보이나 실제 carrot/pruning/TF 조회 시각 기록이 없어 확정하지 않는다. 태그 적용 이벤트 미수집, 이번 수정의 간접 스케줄링 영향도 배제하지 않음.
상세 runs/turn_direction_audit_20261024/REPORT.md 및 diff/파라미터/TF/명령/기하계산 보존. window/더미/새 도착 기준 미완료 유지, 추가 이동·설정 변경·재기동·commit/push 없음.


### 2026-10-24 AMCL 변화·반대 회전 추가 대조
사용자 승인 범위의 기존 bag 분석/오프라인 계산만 수행. 실패 직전 AMCL pose→map/odom 갱신을 확인했고 초기위치/지도 재수신/태그 적용의 같은 시각 증거는 없음. 성공/실패 모두 회전 중2~4초 AMCL 갱신은 기존0.2rad/0.05m 기준과 부합. filtered 레이저 최대수신간격 성공0.134초/실패0.114초로 실패만의 장기수신중단 증거 없음. 실패 AMCL y표준편차127.6mm, 성공 비슷한 방향94.3~104.1mm(실제오차아님).
동일odom에 전후TF만 적용한23.67mm 변화로 RPP 경로각 -4.49→+16.56도, rotate false→true를 오프라인 확인. PC1.3.13/로봇1.3.11 버전차이를 발견하여 로봇 설치 라이브러리의 getLookAheadPoint/shouldRotateToPath 함수로도 재검증, 동일결과. /tmp 별도 계산 프로그램만 빌드하며 노드/DDS생성없음. 실제 pruning/TF조회시각/carrot미수집으로 전체실행 인과확정은 아님; AMCL의 특정 빔/입자 선택 원인은 미확정. runs/turn_direction_audit_20261024/REPORT.md에 결과/한계/증거보존. 운영소스·설정·안전조건·프로세스변경/이동/commit/push없음.


### 2026-10-24 13:42 KST 반대 회전 재시험 준비
사용자 스테이션 재배치·수동 재기동·웹표시 확인 후 읽기 점검. AMCL active, 로봇 IDLE/ready=true, 최근odom30개 정지. map(.082577,-1.107848,yaw1.540982), 스테이션 대비약21.6mm. 레이저685점 지도거리 중앙27.9mm/p90 67.4mm/5cm이내82.77%, 실제환경차이포함. 일반64×54/인계62×52cm·해상도2cm·unknown0, 현재자세/+0.1rad 오프라인검사통과(전체주행보장아님). cmd_vel_nav/odom publisher각1개. 로봇에서arm harvest/discharge Action과prepare/stop 서비스 발견.
PC더미IDLE/readytrue/recoveryfalse,가상장치정지·접힘/닫힘. recover불필요. 기존journal백업 후prepare성공,records/history불변 확인, #59 task25fabab7b348_SEC01_TASK001/window25fabab7b348_SEC01_W001에만1회반복허용13:41:11~13:46:11KST. 실물팔검증아님.
수집기첫명령추가토픽누락을시작후검증에서발견해해당구독수집기442977만SIGINT종료,기록보존. 수정수집기443382/20분상한,bag_20261024_134151에22토픽전체구독확인. 추가cmd_vel_normal/lookahead_point/curvature_lookahead_point/is_rotating_to_heading/received_global_plan/lookahead_collision_arc/particle_cloud/map 포함. 실제비영controller메시지는주행시발행여부확인필요. 근거PC·로봇runs/turn_retest_ready_20261024. 사용자웹#59전송대기. 운영설정/안전조건/주행노드변경·재기동·이동Goal·인계요청·commit/push없음.


### 2026-10-24 13:42 #59 재시험 실패·반대 회전 미재현
사용자 웹 전송13:42:27.104→일반 SECTION_APPROACH13:42:57.537 collision ahead→13:42:58.704 FAILED/NAVIGATION_FAILED(status6,error106). event d3ac2e1ba66a47d69d3b51303a1598c5,request6d350042b57a41858938d9519b81b09b,plan418e85daf75443089d0a67ad3d8d97e4. 사용자 현장 정지 확인, 구독 odom0 및최종IDLE 확인. 위치약(.0334,-.1079,yaw1.048),초기위치/재전송/인계요청없음.
이번 코너13:42:51.8~57.54의 비영 일반 원본명령114개:전진v0,회전w양수0개,마지막w=-.1rad/s. 실제carrot각도-37.27~-18.55도,회전모드true. 이전같은지속반대회전은이번구간미재현이며 오른쪽제자리회전중충돌예측으로중단했다. 이전AMCL변화→반대회전가설이이번충돌원인까지설명한다고볼수없음. 구체적충돌셀은추가분석필요.
WINDOW_MOVE/새arrival미완료,ARM SKIPPED. PCdummy journal records/history가시험전과같아새수확실행없음. 성공으로표시하지않음.수집기443382만SIGINT종료하여bag완결,PC복사보존. 원본명령608/출력605/lookahead608/received_global_plan608/회전모드607/입자22/AMCL23/odom3156 등22토픽실제수신확인. topic_counts/command_evidence/task_events/amcl/analysis/live/launch_snapshot/journal.after_trial을runs/turn_retest_ready_20261024에보존. 주행노드·안전조건·설정변경/재기동/추가이동/commit/push없음.


### 2026-10-24 일반 주행 충돌 입력 교차 재현
사용자최근변경오류의심에따라기존성공자료와이번실행을대조. 이번일반실행YAML전체값이이전성공과동일. 이번costmap/근접odom으로Nav2 footprint함수계산시현재cost253,오른쪽추가0.089rad부터254. 셀119,145(odom .93,.45 / 근접TF map-.380,-.214),왼쪽뒤모서리부근. 성공grid에서대응중심cost253. 성공/실패costmap와map자세교차4조건중실패grid+실패pose만0~-.1rad범위충돌. 자세약15.4mm/2.46도차이. 동일환경변화증거아니며controller내부원자snapshot아닌근접수집자료재현이라는한계명시. 이번반대회전미재현;셀배치/자세차이의센서원인은미확정. 상세runs/turn_retest_ready_20261024/COLLISION_AUDIT.md. 설정/안전조건/운영소스변경·이동·commit/push없음.


### 2026-10-24 전진·회전 선택과 설정 변경 이력 재검토
사용자 지적대로 기존 성공에는 전진+회전이 존재한다. 10/18 성공bag 분석 이력에는 v0,w-.1 제자리회전과v.0532~.0640,w-.1111 복합동작의교대가명시돼있고, 이번직접비교06:34성공bag에도제자리우회전표본이있다. 성공경로가항상전진회전만했던것으로설명하면안됨.
현재실패의원본controller는carrot각-37.27~-18.55도/rotate=true/v0를발행하여충돌검사대상은제자리회전이었다. 전진곡선의가능성검사/대체곡선탐색을수행했다는증거는없으며제자리회전실패를모든전진곡선불가능으로일반화하지않음.
Git이력:fb5c61a(10/18)에서실물HarvestApproach lookahead/curvature .1추가(10/14검증설정보존기록);6f21119(10/18성공기준)에서resolution .025→.02,footprint/padding유지;5d47a23(10/21)은behavior spin속도추가로controller분기와별개. 6f21119의공통HarvestApproach도use_rotate_to_heading=true/min_angle6도확인. 최근wall후보에서일반주행전진을제거한설정변경증거없음. 설정동일해도경로점/추정자세에따라분기달라질수있음. 원래기대하는코너복합주행과현재회전우선정책의적합성검토가필요하며본턴은설정변경/이동없음.


### 2026-10-24 코너 종료 대신 전진 곡선 대안 후보
사용자 방향 승인 후 운영파일을보존한별도runs/corner_alternative_candidate_20261024에Corner RPP 후보구현/PC빌드. 정상RPP유지,경로방향맞춤NoValidControl시에만속도규제/각속도·가속제한을따르는전진곡선3개기존충돌검사,전부불가시0출력후재평가/기존progresschecker유지. 취소/TF/최종자세/후진보호유지의도. 실패저장입력에서제자리v0,w-.1은.89초충돌,전진v.02이상+w-.1의1초표본검사통과. PC기존회귀CTest1/1통과는새fallback전체검증아님. 새메서드전체취소/실패/재개통합,실제제동·smoother궤적,진행성,로봇1.3.11호환미검증이므로운영적용준비완료아님. 운영코드/설정/설치본/기동/이동/commit/push없음. 원본hash와한계/후속검증REVIEW.md보존.


### 2026-10-24 전체 실패 승격 정책 조사
사용자 다른불필요종료도조사요청. 현재로봇설치harvest_robot/farm_navigation/farm_common74개Python모듈수집/hash보존,raise/광역catch624개목록(버그수아님),주요종료호출경로분석. 우선후보12개:Nav2실패전파,입력freshness영구래치,측정odom간격래치,명령watchdog래치,wall TF오류영구래치,align5mm이탈,3초재검사기한,window객체변경drop/watchdog결합,이벤트대기timeout,prepare전_begun복구승격,중첩기한,전송전장치준비대기. 실제메서드ROS없는주입으로gate .31초/odom .6초정상후래치/전송전prepare실패recoverytrue 재현. 이미있는TF복구·벽대기·일반도착warning과필수보호는별도구분. 전수실기검증아님. 상세runs/failure_policy_audit_20261024/AUDIT.md/exception_inventory/probe_results. 운영코드·설정·기동·이동·commit/push변경없음.


### 2026-10-24 일시적 실패 대기 1차 후보·운영 미적용
사용자승인으로현재로봇설치코드/선택설정백업,조사기준74개hash일치확인. 별도runs/transient_wait_candidate_20261024/candidate에수확모듈6개변경:명령공백watchdog0출력대기/최신연속정지증거후재개,전송전DeviceNotStarted만FSM재대기,비동기어댑터분류전달,운송이벤트대기기한을장치실행기한과분리. 취소/epoch/owner/실제충돌/센서만료/전송불명보호유지. 일반normal출력AST불변.
실제후보gate/FSM경계23개+실제runtime메서드통합harness18개=41오프라인검사통과. 전체ROS/DDS/실기검증아님. 센서/TF만료래치·odom샘플간격·align5mm/3초등은이번미변경,전체12개개선완료아님. 상세REVIEW.md/patch/hash/tests로그보존. 운영소스/설정/설치본변경·재기동·이동·commit/push없음.


### 2026-10-24 센서·TF 재관측 및 align 보완 후보 — 운영 미적용
사용자 승인으로 1차 후보 위에 2차 후보를 별도 `runs/transient_sensor_candidate_20261024`에 작성했다. 운영 설치 Python 74개를 SSH로 다시 읽어 기존 백업 해시 일치를 확인했다. 입력 과거 만료/TF 부재를 0출력 재관측으로 분리, worker 대기 중 raw 명령 재개 차단, 최신 연속 정지 확인 후 재개, odom 간격만 인계 선택형 대기로 분리했다. 실제 과속·미래/역행·형상·취소·epoch·소유권·충돌 보호는 유지한다. align의 5mm 즉시 실패는 현재 자세 증명 재계산으로 대체하되 고정 원호 끝점 재진입 한계와 16도 한계를 출력 직전에도 검사한다. 전체 장애물 마스크 키에서 갱신 시각을 제외했다.
후보 재관측/벽 관측 대기는 5초로 맞췄으며 센서 유효기간(odom 등 .5초, wall .45초)은 불변. 상위 전체 Action/FSM/Spin/progress 기한은 계속 진행하므로 잔여 기한을 넘는 대기는 여전히 실패할 수 있다. 자동 Goal 재전송 없음. 1차 후보의 장치 생성자에 잘못 전달된 event_timeout_s도 제거하고 실제 signature 검사를 추가했다(운영 미적용 후보 오류).
실제 runtime/FSM/비동기 어댑터와 대역 입력을 연결한 검사 포함 Python 137개, 로봇 동일 헤더 C++ 7개 시나리오 통과. 실제 spawn 충돌 프로세스의 입력 공백/3.15초 계산 후 복구·종료 포함. 전체 ROS/DDS/Nav2 서버·실기·다른 로봇 E2E 검증은 아님. 공통 모듈 2개는 후보에서만 수정했다. 운영 소스/설치/설정·기동·이동·commit/push 변경 없음. 상세 변경·검증 로그·잔여 기한 한계·원복은 후보 REVIEW.md와 verification.json에 보존. 기존 백업·미커밋 변경·1차 후보 보존.


### 2026-10-24 실제 ROS 서버 격리 검증 — 상위 기한 경합 확인
사용자 요청으로 PC domain191/loopback/validation_no_hardware namespace에서 실제 Nav2 ControllerServer·BehaviorServer와 로봇 현재 WallController 소스의 격리 빌드, 후보 runtime/Navigator/SpinClient/TransferMission을 검증했다. 구동기 연결 없음, 고정 자세·시험 관측·빈 costmap 사용. odom/wall/costmap 지연 중 0출력 및 복구 후 동일 Goal 재개, TF 재조회 중0/복구 후 worker 반환, 취소 후 terminal/출력 차단, 실제 spawn 충돌계산 포함 align 지연·재개·취소 확인. 관측 지속 중단은 약5.494초 후106, 고정 자세에서7초 후 관측 중단하면 총10초/대기3초에 progress105 발생. 후보만으로 상위 기한 소진에 따른 종료를 방지하지 못함을 확인했다.
검증용2초 Navigator/FSM/Spin 기한은 각각 timeout/DEVICE_TIMEOUT/Spin701로 종료하고 자기 Goal 정리 및0출력을 확인했다. 운영120초 등을 그대로 경과시킨 시험은 아님. 시험 settle_s=.3/tf_timeout_s=.5 사용, PC Nav2 1.3.13과 로봇1.3.11 차이 명시. 실기/Zenoh/팔/운영 FSM 전체 성공 아님. 후보 추가수정·운영 적용/재기동/이동 없음. 운영 설치 Python74개 백업 해시 및 후보 해시 불변, 검증 프로세스 모두 종료. 상위 기한 정책 보완 또는 한계 수용 전 운영 준비 완료로 표시하지 않는다. 로그/소스/YAML/버전/상세결과는 runs/transient_ros_validation_20261024/REPORT.md 및 run1~3에 보존. commit/push 없음.


## 2026-10-24 인계 정지 대기 실행시간 후보 및 실제 ROS 무구동 검증

사용자 승인 범위: 일시 정지로 progress·상위 FSM이 먼저 만료되지 않도록 후보 보완, 실제 ROS 무구동 검증. 운영 적용·재기동은 승인 범위 밖이며 하지 않았다. 기준 HEAD `cf870da`; 기존 미커밋 변경과 성공 실행본·백업 보존.

`runs/pause_budget_candidate_20261024/REPORT.md`에 변경표·검증·한계를 기록했다. 인계 전용 0 출력 대기 누계로 progress/Spin/wall/차체 상위 기한을 연결하고 실행별 제외 상한 30초, 연속 입력 대기 5초와 취소·정지·충돌 보호를 유지한다. 후보 Python 9개 및 전용 C++ 패키지만 별도 경로에서 변경했다. 일반 주행 설정과 운영 실행본은 변경하지 않았다.

직접 검증: 격리 PC ROS domain191의 실제 Nav2 서버에서 progress 10초를 넘는 관측 대기 후 같은 Goal 완료(10.548초), 상위 FSM 2초를 넘는 관측 대기 후 완료(3.562초), odom 지연 중 Spin 0 출력·복구·취소 확인. 대기가 없으면 progress/FSM/Spin의 원래 제한이 작동했고 지속 벽 관측 단절 5.499초에 중단했다. 초기 시계 계산 결함과 실패 로그도 보존하고 수정 후 재검증했다. Python 143개·C++ 7개 통과. PC Nav2 1.3.13, 로봇 1.3.11 차이가 있어 로봇용 빌드와 전체 실기/FSM 시험은 남았다. 전체 운영 완료·실기 성공으로 해석하지 않는다.

다음 작업: 운영 적용 전에 버전별 빌드·기존 설치본 대조와 사용자 사전 안내. 원복: 후보 overlay 미사용 시 기존 실행본 유지. 시험 프로세스 종료 확인, 로봇 이동/재기동 및 Git commit/push 미수행.


### 2026-10-24 로봇용 pause budget 후보 빌드·플러그인 로드 확인 (운영 미적용)
사용자 승인으로 로봇 Downloads/pause_budget_robot_20261024에서 ARM64/Nav2 1.3.11용 farm_wall_controller 및 farm_navigation/harvest_robot 별도 빌드. ROS init/노드/Goal 없는 pluginlib 생성·해제로 4종 플러그인 로드, 기존 underlay 위 후보 library 경로, 설치 Python import·전용 설정 선택 확인. 사용 API 헤더3종은 PC1.3.13과 동일하나 전체 동작 동등성 검증 아님. 운영 소스/설치/설정250개 전후 불변, 기존 성공 Python74개 해시 일치, 주요 운영 PID 유지. 기존 백업 유지 및 PC 추가 스냅샷 보존.
실제 laun의 run.bash→terminal.py 경로를 확인하여 launch 분기만 후보 overlay 및 handoff JSON을 선택하는 적용 제안 diff를 준비했다. 운영 파일 수정/재기동/이동/commit/push 없음. 적용 전 사용자 안내·승인 및 현재 상태 확인 필요. 원복은 적용 직전 별칭 wrapper 백업 복원+새 터미널 재기동. 상세 빌드·버전·로드·증거·한계·적용 순서: runs/pause_budget_robot_20261024/REPORT.md. 로봇 lifecycle/전체 FSM 실기 검증은 남았다.


### 인계 pause budget 후보 실행 선택 적용 — 2026-10-24
사용자 승인으로 실제 laun wrapper 두 파일만 백업 후 적용. 기존 운영 소스/install/설정250개 불변, 로봇 후보 overlay와 새 handoff JSON 선택. --check 통과/충돌PID없음. 이번 확인 시 양측 실행은 이미 종료되어 종료신호 미전송. 영구 인계 journal 4건 모두 active/recovery false이며 원본 보존. 사용자 스테이션 재배치 확인 대기, 실제 재기동/초기위치/이동 없음. 원복 백업 activation-backup-20261024_183013; 상세 runs/pause_budget_apply_20261024/REPORT.md. commit/push 없음.


### 2026-10-24 pause budget 운영 기동 후 정지 확인
사용자 스테이션재배치·기동·웹표시 확인 후 실제 PID 후보경로/libmaps·파라미터·lifecycle active 확인. progress4종/Spin후보 및wall .45초/대기5초 반영. IDLE/ready,최근정지odom30개,출력·odom단일publisher. 일반/인계2cm grid와64×54/62×52형상유지,현재정지충돌검사통과. 레이저지도689점 중앙1.44cm/p903.16cm. PC더미ready/recoveryfalse 및로봇prepare왕복success(DUMMY_ONLY). 이번이동/재설정/Action실행없음. 상세 runs/pause_budget_restart_check_20261024/REPORT.md. 반복허용·window/인계실기는아직미수행,commit/push없음.


### 2026-10-24 후보 #59 반복 준비
사용자 승인으로 PC 더미 기록 백업 후 ready/prepare 확인, 25fabab7b348 작업 1회 반복 허용(300초). 로봇 구독 전용 bag PID525077/startticks10184311,15분상한,모든토픽 구독·파일증가 확인. runs/pause_budget_window_20261024에 근거 보존. 사용자 웹 전송 대기이며 이동/수확/인계 요청 미전송,도착·더미완료·새기준저장은아직미확인.


### 2026-10-24 18:39 후보 window+PC더미 성공
사용자 #59 웹 요청, task25fabab7b348 SEC01_TASK001. 이번 accepted 도착 위치오차34.83mm/방향1.345도, request cb7e3a995a2e4b6bb26915ee55fbbaaa. PC더미 새attempt7a064d19… SUCCESS수확2,전체SUCCESS,최종IDLE/ready적재2. SUCCESS전 remember_window 저장 호출·실패시invalidate 계약과 이번이벤트로 새기준저장경로확인(메모리직접조회아님). 인계 동일시각map/odom기준은아직미확보. 수집기만종료,인계요청없음. runs/pause_budget_window_20261024/RESULT.md/이벤트/저널보존. 실제팔·전체인계성공아님,commit/push없음.


### 2026-10-24 후보 인계 웹 시험 준비
사용자window위치유지·이동가능확인. 동일PID/IDLEready적재2/정지/현재형상검사통과/더미prepare성공/인계endpoint확인. wall관측은tracker생성전미발행하는구조,진입후검증필요. 수집PID527824 startticks10210120,15분상한/모든토픽구독. runs/pause_budget_handoff_20261024/READY.md에근거. 사용자버튼대기,인계요청·이동·재기동·설정변경없음.


### 2026-10-24 18:45 인계 후보 DOCK_READY 실기 확인
사용자dock_transfer task7974ad4f…/transfer41fffa2d… 진입goal완료→벽정렬goal완료→DOCK_READY feedback18:45:42 수신. TF/벽준비일시대기후재개확인. WAIT_DOCK_STABLE/최근odom30개0/적재2. 다음사용자DOCK_STABLE만안내,배출·복귀아직미수행. bagPID527824 계속수집(15분상한). 상세runs/pause_budget_handoff_20261024/DOCK_READY.md. 에이전트추가명령·설정변경·재기동·commit/push없음.


### 2026-10-24 운송 대기 중 로그 수집 종료 확인
사용자 STABLE 전까지 수집중지요청. PID527824는이미15분상한으로18:56:45정상기록종료,이번조회에서부재확인하여추가종료신호없음. bag_20261024_184145 metadata/mcap완결,로봇원본유지/PC사본보존진행. 운영PID522218/522199/522200유지,이벤트·정지서비스·취소요청없음. WAIT_DOCK_STABLE의새상태조회는이번미실행이므로직전확인상태로만기록. 사용자STABLE전알림후새상태/준비검사와수집재개필요.


### 2026-10-24 운송연동 재시험 전체종료
사용자 스테이션→#59수확→새관제운송인계 재시험 승인. 기존DOCK_TEST7974…의 정확한ActionUUID만취소,return_code0/terminal5(CANCELED)/최근odom30개0 확인. 이동/복귀/배출요청없음. 취소뒤ERROR/recovery_required=true이며성공으로덮어쓰지않음. PC더미도stop에따라전역recovery_required=true. 기존기록전후백업보존.
수확launch522163와자식·드라이버,로봇hubbridge522657/dummybridge522712,PC더미252660/bridge252718를검증한PID/startticks기반SIGINT로종료. 양측remaining0. 수확노드종료시Destroyable경고있으나cleanexit/잔존없음,원인해결주장없음. 관제서버·운송로봇미접근/미변경.
스테이션수동재배치가능안내. 아직사용자재배치확인전이므로복구journal해제/새기동/초기위치발행없음. 사용자재배치확인뒤취소기록보존한수동복구처리와PC더미복구,기동순서안내필요. 기존성공코드/후보선택/백업유지,commit/push없음.


### 2026-10-24 스테이션 재배치 후 복구 표시만 해제
사용자 명시승인/실제스테이션재배치확인/양측종료확인. 로봇 DOCK_TEST7974…의 recovery_required만false 및manual_recovery근거추가,기존CANCELED결과/ID/시각/다른records불변 검증. PC더미는종료중exclusive journal.lock확보후전역recovery_required만false,records/history완전동일. 전후백업runs/transport_restart_20261024/manual_recovery 및manual_recovery_pc. 기존운영소스/install/설정250개해시불변. 후보재빌드/교체/초기위치/기동/이동없음. 다음사용자PC더미→PCbridge→로봇laun까지실행,에이전트IDLE/정지확인후vinit,그뒤zen/dzen. 아직IDLE실행확인전. commit/push없음.


### 2026-10-24 20:18 운송 연동 재시험 #59 준비
사용자 웹 연결 확인 및 동일 작업 1회 반복 승인. 기존 코드·설정·기동 상태 변경 없이 최신 IDLE/ready, 최근 odom30개 정지, 출력/odom 각 단일 publisher 확인. 일반64×54/인계62×52cm 및2cm costmap 유지, 현재 정지 형상 검사 통과(전체 경로 통과 보장 아님). PC더미 이력 백업/records·history 불변 확인 후 prepare 성공 및 #59 task25fabab7b348 1회 반복 허용(20:18:32부터300초). 구독 전용 수집 PID555201/startticks10790370,15분상한,전체14토픽 구독 및mcap생성 확인. 증거 runs/transport_window_retest_20261024. 사용자 웹 전송 대기; 이동·인계 요청/재기동/commit/push 없음. 다음 window 도착·새 더미attempt 완료·새 도착기준 저장 확인 후 인계 사전 안내.


### 2026-10-24 20:22 운송 연동 재시험 window 완료
사용자 #59 웹 요청으로 SECTION_APPROACH/WINDOW_MOVE accepted, 도착오차26.97mm/1.22도. 새 arrival bfe32fc5… 및 PC더미 새attempt c04c6969… SUCCESS수확2/실패0, 최종IDLE/ready/적재2/최근odom30개0. 실행본 SUCCESS전 remember_window 호출과 이번성공 이벤트로 저장경로확인(메모리직접조회 아님). 별도카메라 control_readback_stale 종료1, detector/rectify종료0; 이번태그보정성공아님. 코드·설정·재기동·인계명령변경없음. 수집기만종료하고 로봇원본/PC사본보존. 상세 runs/transport_window_retest_20261024/RESULT.md. 다음인계전안내필요,commit/push없음.


### 2026-10-24 20:51 실제 운송 연동 인계 준비 결과
사용자dock_transfer a64d… 진입·벽정렬 완료, DOCK_READY20:51:03.538 직접수신/관제수신확인. 수확WAIT_DOCK_STABLE/최근odom30개0/적재2. 운송은20:50:07부터대기해20:51:07 DOCK_READY시간초과FAILED,수확보고후약3.87초뿐. 웹실물snapshot에서다음이벤트allowedfalse,DOCK_READY전달기록없음. 운송내부원인은직접미확인. 다음버튼보류안내,강제이벤트/배출/복귀/재기동/코드설정변경없음. 수집563856은15분상한으로계속,초반진입은수집전이라launch로그보완. 상세runs/transport_handoff_retest_20261024/RESULT.md. 전체인계미완료,commit/push없음.


### 2026-10-24 20:55 운송 연동 재시험 종료
사용자 전체종료/재배치후재시험 요청. 현재 수확 인계 a64d… UUID만 CancelGoal, ack0/terminal5(CANCELED)/최근odom31개0 확인. 종료직전ERROR(CANCELED·복구필요),IDLE확인아님. 로봇launch552969와자식·driver,bridge553658/553713,recorder563856 및PCdummy264119/bridge264177 SIGINT 종료,양측selected remaining0/로봇별도ps잔존없음. 수확노드는종료시Destroyable경고후cleanexit. 기존코드/설정/저널취소결과/로그보존,복구표시해제미수행. 관제서버·타팀운송로봇미변경. 근거runs/transport_shutdown_20261024. 사용자스테이션재배치가능,재배치확인후복구처리/재기동/IDLE확인→vinit 순서 필요. commit/push없음.


### 2026-10-24 인계 a64d 재배치 후 복구 표시 해제
사용자 스테이션 위치·방향 재배치 확인 및 명시 승인. 로봇 수확/드라이버 부재 재확인 후 해당 CANCELED 레코드만 recovery_required=false/manual_recovery근거추가,기존결과/ID/시각/다른레코드불변 검증. PC더미 종료확인+exclusive journal.lock으로 전역 recovery_required만false,records/history완전동일 검증. 전후백업runs/transport_shutdown_20261024/manual_recovery 및manual_recovery_pc(로봇백업도PC복사). 코드·설정·초기위치·재기동·이동 변경 없음. 다음 PCdummy→PCbridge→로봇laun 사용자기동,IDLE/정지확인후vinit,이후zen/dzen/vstat. 현재종료상태여서IDLE미확인. commit/push없음.


### 2026-10-24 21:00 재배치 후 #59 재시험 준비
사용자기동·웹표시·vinit성공확인후 read-only검사: 새boot ee021a052ae6421ab32371238464fb66,IDLE/ready/적재0,최근odom29개0,일반64×54/인계62×52 및2cm costmap 유지/현재형상검사통과. scan693점 지도거리중앙2.07cm/p904.46cm. 더미prepare성공/recoveryfalse/기록백업후동일#59 1회반복허용21:00:05부터300초. 구독수집PID568140/startticks11041844,15분상한,전체14토픽구독/mcap생성확인. runs/transport_retry2_window_20261024에보존. 코드·설정·이동요청·인계요청·commit/push없음. 사용자웹전송대기.


### 2026-10-24 21:02 #59/태그/더미 완료
이번웹#59 accepted 도착오차27.89mm/0.659도,새arrival9a8add9f…/event7f1e3b8f…,더미새attemptbb70efb4…SUCCESS수확2/실패0. 동일실행본저장계약+이번이벤트로새window기준저장경로확인(메모리직접조회아님). AMCL21:01:50 TAG_CORRECTION_APPLIED:1 확인. 최종IDLE/ready/적재2/odom30개0. 수집기만종료,로봇원본/PC사본보존. 코드설정·재기동·인계/운송요청없음. 상세runs/transport_retry2_window_20261024/RESULT.md. 인계전양측이벤트순서및수집준비필요,commit/push없음.


### 2026-10-24 21:04 인계 재시험 벽 관측 대기초과
사용자dock_transfer6b4c… 진입완료후wall21:04:20.509시작→28.135 Wall observation wait exceeded.23.479runtime costmap headerage.5319>.5로대기로그,연쇄원인미확정. ERROR/DEVICE_FAILED/DOCK_READY미확인/배출복귀없음. odom31개0+사용자정지확인. bag은실행후수집시작해초반누락,launch/저널보완. 수집기만종료,코드설정/재기동/추가명령없음. runs/transport_retry2_handoff_20261024/RESULT.md 및로그보존. commit/push없음.


### 2026-10-24 센서 정지대기 작업 유지 후보·통합 검증(운영 미적용)
사용자 센서지연 중 정지/작업유지/회복재개 및벽·watchdog·상위FSM 통합검증 승인. runs/sensor_hold_candidate_20261024에 별도후보. 로봇실행선택본백업/설치Python바이트대조일치,기존성공본·백업·미커밋변경보존. 인계전용 명시선택으로센서재관측5초·벽관측5초 실패와정지누계30초제외상한해제;취소/소유권/epoch/충돌/공간/속도/시각보호유지. 상위FSM/body/Nav2/Spin은기존주입시계를통해동일정책사용,일반주행미변경.
Python147/C++wall10/CTest1 통과. 실제PC ROS domain191무구동:wall38초정지중1488개출력0/동일Goal완료,상위FSM2초제한에서도38초대기후완료,wall+costmap/odom각8초동시지연후복구성공,6초대기취소후출력차단. 정상입력무진행FSM2초/progress10초제한유지. 로봇1.3.11빌드/실기/전체FSM미검증,PC1.3.13결과와구분. runtime자체heartbeat단절·프로세스장애까지무조건유지하는수정아님. 운영적용/재기동/이동/commit/push없음. 상세변경표/검증/남은범위/원복은runs/sensor_hold_candidate_20261024/REPORT.md,시험프로세스정리확인.


### 2026-10-24 센서 정지대기 후보 로봇 빌드·플러그인 로드 완료(운영 미적용)
사용자 로봇용 빌드·로드·적용 준비 승인에 따라 /home/vic/Downloads/sensor_hold_robot_20261024 별도 후보에서 3개 패키지 빌드 완료. ARM64/Nav2 1.3.11에서 플러그인 4종 생성·해제 및 실제 로드 경로, Python 설치 경로·정책 선택 확인. ROS 노드/Goal 없이 검사. C++ assertions 10개/CTest 통과, ldd -r 누락·미해결 없음. 운영 관련 비교 파일 468개 해시 및 주요 PID 5개/명령 동일. 기존 성공본·백업·실패 기록 보존, 운영 적용/재기동/이동/복구 해제/commit/push 없음. 운영 wrapper 두 파일 변경 제안과 적용 직전 백업·원복 절차 준비. 실제 lifecycle/인계 실기 미검증. 상세 runs/sensor_hold_robot_20261024/REPORT.md 및 ACTIVATION_PLAN.md. 이전 PC ROS 검증과 이번 로봇 빌드·로드 범위를 구분한다.


### 2026-10-24 21:25 센서 대기 후보 운영 경로 적용·재기동 전
사용자 후보 운영 적용/종료/재기동 안내 승인. 종료 직전 ERROR/DEVICE_FAILED, task 없음, 최근 odom30개 속도0. 실패 인계 DOCK_TEST_6b4c… active=false/recovery_required=true 기록 보존. 런치566901과 자식 총18개 SIGINT 종료 확인(추가 SIGINT로 수확 노드 종료), 잔존 없음. 종료 중 기존 드라이버 context invalid(exit1), sllidar exit-6 기록 보존하며 이번 변경 원인으로 단정하지 않음. PC 더미/브리지 및 로봇 브리지 실행 없음, PC 더미 recovery_required=true.
실행 선택 run.bash/terminal.py 두 파일만 sensor_hold_robot_20261024로 전환. 로봇 원본 백업 /home/vic/Downloads/sensor_hold_robot_20261024/activation-backup-20261024_212510. 이전 비교대상468개 중 해당2개만 변경, 기존 성공 설치본/설정 유지. launch --check 후보 경로/충돌PID없음 확인(실제 기동 아님). 사용자가 스테이션 재배치 후 알려주도록 안내했으며 현재 확인 대기: 복구 표시 미해제, 초기위치 발행/재기동/이동 없음. 상세 runs/sensor_hold_robot_20261024/activation 및 ACTIVATION_PLAN.md. Git stage/commit/push 없음.

스테이션 재배치 사용자 확인 수신 후, 종료 상태를 재확인하여 실패 인계 한 건의 recovery_required만 false로 변경하고 manual_recovery 근거 추가. FAILED 결과/시간/다른 기록 동일 검증. PC 더미는 활성 작업 없음·모든 기록 terminal 확인 후 최상위 recovery_required만 false 변경; history/records 바이트 의미 동일 검증. 양측 원본 백업 보존. 로봇·PC 프로세스 재기동/초기위치/이동 없음. 다음: PC dummy→PC bridge→로봇 laun, 에이전트 IDLE/정지 확인 후 vinit→zen→dzen→vstat. 같은 #59 반복 허용은 기동 후 별도 서비스 준비 필요하며 아직 수행하지 않음.


### 2026-10-24 21:30 후보 실행 후 웹 #59 관찰
사용자가 직접 기동/초기위치/웹 명령. 에이전트는 읽기·경량 구독만 수행. 후보 sensor_hold 설치 경로 및 handoff controller 로드 maps, wall_alignment.wait_until_fresh=true 확인. 초기위치 발행 기록 및 IDLE/ready/odom30개0 확인 뒤 웹 주행 시작.

SECTION_APPROACH와 WINDOW_MOVE 완료. 21:29:59 window accepted, 오차29.086mm/0.005274rad. arrival request29251f4b8db44783b2d5f32663a7b596 및 새 stamp1792844999178232191 이벤트 기록. 이후 ARM_REJECTED: PC 더미21:29:59.208 duplicate ID 실제 로그 확인. 재기동 후 반복 허용권 미설정 상태였으며 새 더미 수확 완료 아님. 최종 ERROR/ARM_TRAVEL_NOT_READY/loaded0, 최근 odom30개0. 같은 작업 반복 허용 서비스 호출/복구/재전송/인계/이동/재기동/설정 변경은 수행하지 않음.

태그 캡처도 code1로 종료 기록. 상세 원인은 아직 미확정이며 이번 더미 duplicate 거절과 구분. 현재 도착 이벤트를 메모리 내부 저장/복구 후 재사용 가능성까지 검증한 것으로 간주하지 않음. 기록: console.log, live.jsonl, latest.json, dummy.log. 인계 진행 전 더미 반복 준비 및 수확 노드 복구 필요.

21:32:23 사용자 start_dock DOCK_TEST_56f956b42e5046299edefeb98db05782는 웹에서 REJECTED 확인. 수확 ERROR/ARM_TRAVEL_NOT_READY 지속, 인계 진입 미실행. 운송은 별도 pickup 후 WAIT_DOCK_READY 수신; 물리 도킹 성공으로 해석하지 않음. 웹 읽기만 수행, 추가 명령 없음. dock_rejected.web.json 보존.

### 2026-10-24 21:35 중복 ID 실패 후 수확·더미 복구
사용자 다시 시험 가능하도록 복구 승인. 이후 운송측 개입 금지 명시: 관제 읽기 확인 이후 운송 명령/변경 없음. 수확 노드578985만 SIGINT종료 후 동일 인자/환경/후보로582108 재기동, Nav2/AMCL/드라이버 기존PID 유지. 실패 저널/명령/로그 백업, 코드·설정·초기위치/이동 명령 변경없음. PC 더미 공식 recover/prepare 성공, records/history 동일 검증, IDLE/ready/복구false 확인. repeat_last_harvest21:34:53 성공으로 #59 1회300초(21:39:53까지) 허용. 수확 IDLE/ready,odom30개0 확인. 다만 pose 약(1.455,-1.319),yaw1.527로 이전window와 달라 사용자 실제 재배치 여부 질문 대기; 이동 준비완료로 단정하지 않음. 카메라 control_readback_stale 종료 확인, detector/rectify는code0/TBB_FINALIZED. 카메라 복구는 미완료. 수확 재기동으로 이전 메모리 도착기준은 소실, 새 작업 도착기준 필요. 상세 runs/sensor_hold_recovery_20261024.

21:36 사용자 초기스테이션 수동재배치 확인. 기존 vinit IDLE/정지보호 통과후(21:36:21) x.104/y-1.105/yaw87.79 초기추정 발행. 이후IDLE/ready,odom30개0,pose(.09487,-1.11590),yaw1.52543. 레이저-map 끝점687개 median34.06mm/p90 80.78mm/5cm이내75.55%, 전체주행 안전증명 아님. 두 costmap2cm,일반64x54/인계62x52 현재자세검사통과. 일반제자리+.1rad 가상경로는충돌검사실패(실제주행경로아님),안전조건 유지/clear서비스 미호출. 출력publisher/odom 각1. 기존코드설정으로카메라만583295재기동,raw/rect/detect약8Hz/TAG_ADAPTER_RUNNING 확인. 과거control_readback_stale근본원인 수정없어재발가능성남음. #59허용21:39:53까지1회,실제이동명령없음.

### 2026-10-24 21:40 #59 재전송 관찰: 관제 QUEUED
사용자 #59 전송 후 로봇 Goal 수신 없음. 관제 /api/control?environment=real 읽기에서 task59 QUEUED/ready.harvest=false, paused.harvest=false. 로봇 IDLE/ready=true/스테이션 위치/최근odom31개0. 새window도착/더미완료/도착기준 없음. 더미 반복허용21:39:53만료. 재전송/브리지재시작/설정변경/인계 명령 없음. runs/sensor_hold_repeat2_20261024/control.json,latest.json 보존. 수확노드 재기동 이후 관제Action재연결 확인 필요; 재연결 시 대기작업 자동출발 가능하므로 더미반복허용 선행 필요.

### 2026-10-24 21:41 브리지 복구 후 #59 실패
사용자 더미반복허용→브리지복구→대기작업관찰 승인. PC더미recover/prepare/repeat 성공21:41:04(300초). 로봇 관제브리지만579435→585474 동일 인자/환경/바이너리/설정 재시작. 관제ready.harvest=true 복구 및 대기#59 자동시작21:41:19.559. 일반controller Goal21:41:19.651→20.353 detected collision ahead/106, 작업FAILED21.351. SECTION_APPROACH 단계,window도착/더미수확/새도착기준 없음. 더미repeat는소비되지않음(21:46:04만료). 최종IDLE/ready/loaded0/odom31개0. 기존정적검사에서 일반costmap제자리+.1rad 접촉이 있었으나 이번controller 실제검사점과 동일원인인지 미검증. 충돌조건변경/재전송/인계/운송명령 없음. 카메라약8Hz 유지. 실패이벤트5b87baca…및launch.log/web.after.json/robot/live.jsonl 보존. 관찰프로세스585472만종료,운영프로세스유지.

### 2026-10-24 21:44 전체 종료·costmap 메모리 정리
사용자 이전대조 분석을 중단하고 초기위치 재배치/내부정리/costmap정리 요청. 조회 시 기존 메인launch/Nav2/드라이버/PC더미·PC브리지는 이미없음. 남은 별도수확582108/카메라583295/관제브리지585474와 자식10개 SIGINT 종료,잔존없음. 전체controller/behavior/driver/AMCL/velocitysmoother/카메라/bridge 프로세스없음 확인. costmap 프로세스 종료로 이전 휘발성 격자/voxel 상태 소멸,다음기동에서 재생성;지도/설정/충돌보호 변경·로그삭제 없음. PC더미 journal recoveryfalse/미완료없음/row복구없음 확인,원본백업만. 사용자에게 스테이션 재배치 가능 안내. 다음 재기동후 초기위치/새관측costmap 확인 및 같은#59반복허용을 주행 직전에 수행해야함. 이동/초기위치발행/재기동/운송명령없음. 자료 runs/station_clean_restart_20261024.

### 2026-10-24 21:47 완전종료 후 스테이션 재기동 준비 확인
사용자 재배치/수동기동 확인 후 읽기검증 및 더미반복허용 승인. 후보수확587544/런치587515,새boot2381… IDLE/ready/odom29개0. 사용자vinit21:46:11발행기록 확인. 레이저끝점690개 median21.87mm/p90 70.20mm/5cm82.61%. 새일반/인계costmap해상도2cm,형상64x54/62x52,stationary 및+.1rad가상회전 모두통과. 일반최소거리약.210m(이전유지시.018m),lethal454(이전1305);rolling창/좌표다르므로 단순cellcount로잔존원인확정불가. cmd_vel_nav/odom 각단일publisher. 카메라raw/rect/detect약8Hz/adapter기동. 웹ready.harvest=true,paused.harvest=true(사용자웹해제필요),#59과거FAILED/재시도가능. 더미recover/prepare/IDLE검증/이력동일/반복1회성공21:47:30→21:52:30까지. 이동/웹버튼/재시작/설정변경없음. 자료 runs/clean_station_ready_20261024.

### 2026-10-24 21:49 완전재기동 후 #59 성공
사용자웹전송,관찰만수행. SECTION_APPROACH/WINDOW_MOVE 완료,이벤트SUCCESS21:49:15.886/더미새attempt1976d76be6484a11806139c449cadf0a SUCCESS 수확2/실패0(expected1과더미2기존동작구분). 새arrivalrequest79b17b064b5e4934a4b78aa73597a159,plan13ed447738e54c08bf843121d8657d5a,stamp1792846154151270408,accepted true,오차29.106mm/0.02727rad. 실행설치communication 성공콜백remember_window 계약과이번이벤트로새기준저장경로확인(메모리직접조회아님). 최종IDLE/ready/loaded2. AMCL TAG_CORRECTION_APPLIED:1 21:49:04 확인. 인계경량관찰590109 10분제한으로기동,clean_handoff/live.jsonl;인계명령없음,사용자버튼대기. 기존코드설정/안전조건변경/운송개입없음. 자료 runs/clean_station_window_20261024.

### 2026-10-25 재시험 전 잔존 확인
사용자 처음부터 재배치/재기동/#59반복 준비 요청. SSH접근 가능. 로봇 수확/Nav2/AMCL/드라이버/카메라/브리지/관찰/rosbag 및PC더미/브리지/수집 프로세스 잔존없음. 기존sensor_hold_robot_20261024실행선택 유지/launch --check충돌없음. transfer저널 DOCK_TEST_009b429d77ef4237b382964f5ab46c04 active=true/recovery_required=true(2026-10-24 21:52시작) 발견,원본백업. PC더미 recoveryfalse/미완료없음. 사용자에게 스테이션재배치가능 및 확인요청;아직저널복구변경없음. #59반복허용은재기동후메모리서비스로마지막에수행해야함. 기존코드설정/로그삭제/운송조작/초기위치/이동/재기동없음. runs/restart_ready_20261025 자료보존.

2026-10-25 20:52 사용자 스테이션 위치·방향 재배치 확인. 종료 재확인 및 원본SHA동일 확인 후 인계009b… 한건 active/recoveryfalse, resultFAILED 및 manual_recovery 추가. 실제 종료시각/ROS취소응답은 미확인이므로 생성하지 않음. previous_record에 원래 필드 전체 보존,다른행 동일 검증. 로봇백업 /home/vic/Downloads/sensor_hold_robot_20261024/manual-recovery-20261025_205244. 코드설정/PC더미이력/운송측변경없음. 재기동은 사용자 수행,더미반복허용은기동후별도.

### 2026-10-25 20:55 재기동 준비 검사
사용자 정합/costmap/더미/웹확인 및#59반복허용 승인. 새boot e1ddee… IDLE/ready/최근odom23개0. 실행sensor_hold후보3954,초기위치발행20:53:35확인. 레이저694끝점 median29.82mm/p90 58.55mm/5cm86.46%. 일반64x54/인계62x52,2cm costmap현재자세 및+.1rad검사 모두통과(일반여유약16cm);전체경로보장아님. 출력/odom publisher각1. TAG_ADAPTER_STARTED. 웹 Action ready.harvest=true지만 paused.harvest=true 및 수동인계미확정 차단. 어제DOCK_TEST_009b… 관제UNKNOWN 남음,로봇저널복구와관제정리별개. 사용자웹조작원칙에따라관제수정/명령없음. 더미recover/prepare/IDLE/이력보존 검증 및repeat1회성공;유효기간은repeat_last_harvest.json wall_s+300초. 관제미확정정리 전 주행보내지않도록안내. 자료 runs/station_ready_20261025.

### 2026-10-25 21:04 #59 window/더미 성공
관제재개후 사용자#59전송,에이전트구독만. SECTION_APPROACH/WINDOW_MOVE 완료,이번SUCCESS21:04:27.031/수확2실패0(expected1과더미출력2 구분). 더미새attemptdf64c252ca714e7eb38318fe0472fa4c,완료21:04:26.910. 새arrivalf326a7f14bf8496bb10b45cd0f6a1867/plan904683bced3b47aba66aed8a6c6ff50d/stamp1792929864965796828 accepted true,오차28.613mm/0.015325rad. 기존실행설치본의SUCCESS후remember_window계약 및새이벤트로저장경로확인;내부메모리직접조회와구분. 최종IDLE/ready/loaded2,별도인계명령없음. 인계관찰8792 600초제한구독/handoff_20261025,사용자버튼대기. 코드설정/재기동/운송개입없음. runs/window_retry_20261025 기록.

## 2026-10-25 반복 시험 웹 후보
`robot/tools/trial_console/README.md` 참고. 운영 소스/프로세스는 변경하지 않았다. 더미 수량 patch는 원본 해시 검증 후 별도 폴더에 생성한다. 실장비 종료/복구 버튼 및 운영 적용 검증은 아직 하지 않았다. 기존 관제·수확·운송 코드는 변경하지 않으며 터미널 기동과 관제 이동 버튼은 사용자가 담당한다. 결과: `docs/changes/TRIAL_CONSOLE_20261025.md`.

### 2026-10-26 반복 시험 콘솔 검증
실제 사용자 웹 조회는 로봇 SSH/관제 GET 정상, 로봇·더미 실행 없음/Action false 확인. 별도 domain191에서 HTTP→ROS 후보 더미 완료·반복·취소·수량 및 기록 보존 통과. 운영 원본 해시 동일, 운영 교체/기동/복구/이동 미실시. 상세 TRIAL_CONSOLE_20261025.md, runs/trial_console_20261026. 사용자 웹 PID316199 유지.

### 2026-10-26 PC 더미 운영 후보 적용
사용자 승인으로 원본·journal·설정 백업 후 server.py 후보 적용, PC dummy/bridge 기동, 웹 최신status 및 서비스 왕복 확인. 이전 recovery latch가 그대로 남아 준비·수량 변경은 거절됨. 로봇도 recovery=true 기록 남아 실제 재배치 확인 대기; 로봇기동/이동/복구 변경 없음. 상세 TRIAL_CONSOLE_20261025.md 및 runs/trial_console_apply_20261026. PC 중복 기동 금지.

### 2026-10-26 충전 위치 유지·PC 더미 복구 완료
사용자 승인으로 PC더미만 웹 recover/prepare 성공, IDLE/ready=true. 수량3→기존2 변경 성공 및 ROS 직접조회2 확인. 기존history/결과 보존, 로봇저널 SHA동일; 로봇 복구/초기위치/이동 없음. runs/trial_console_recover_20261026. 로봇은 스테이션 아닌 충전 위치이므로 vinit 금지, 기존 수동복구 확인 대기 유지.

### 2026-10-26 PC 기동 소유권 정정
사용자는 모든 운영 프로세스를 자기 터미널에서 기동/종료한다. 에이전트가 PC더미/브리지를 검증 후 남겨둔 것은 사용자 운영 원칙 위반으로 지적받음. 사용자 명시 종료 요청에 따라 경로·PID 재확인 후 에이전트 기동 더미325835/브리지326066만 SIGINT 종료, 잔존없음. 사용자 웹316199 유지, 기록삭제/로봇조작 없음. 앞으로 운영 프로세스를 임의 기동하거나 검증 후 남기지 않는다.

### 2026-10-26 vinit 차단 읽기 진단
사용자 스테이션 재배치 확인 및 변경 금지 지시. 프로세스 기동/종료·초기위치·이동·저널변경 없이 조회. 현재 런치2824/수확2854 동작, status ERROR/TRANSFER_RECOVERY_REQUIRED/current_task_id 빈값, 최신odom30개 정지. 로봇 저널 DOCK_TEST_188c3962206a465cab024b8092f108ca active=false/recovery_required=true. 실제 설치 transfer_communication이 기동 때 이 기록을 읽어 node.blocked=True 설정함. vinit의 state==IDLE 조건 불충족이 직접 차단 원인; odom정지 조건은 이번 조회에서 충족. ARM_NOT_READY/POSE_UNAVAILABLE도 동반하나 이번 vinit의 직접 조건과 구분. 새 웹 audit에는 robot_stop 성공만 있고 robot_reconcile 요청 기록 없음. 근거 runs/vinit_diagnosis_20261026/{robot,runtime}.json. 해결은 사용자 종료→백업 수동복구→사용자 재기동 필요, 이번에는 수행하지 않음.

### 2026-10-26 사용자 종료 후 로봇 수동복구
사용자 laun 종료 및 기존 스테이션 재배치 확인, 백업 후 복구표시 해제 명시 승인. robot_agent status 수확 관련 process={} 재확인 후 저널SHA 재검증/원본백업, DOCK_TEST_188c3962206a465cab024b8092f108ca의 recovery_required=false 및 manual_recovery(previous_record 포함) 기록. 기존 FAILED/종료시각/transfer_id 등 원래 필드와 타 기록 보존. 백업 /home/vic/.local/state/manyfarm/harvest_01/console-backup-1792968354999941481. 자료 runs/robot_reconcile_20261026. 재기동/초기위치/이동 명령 없음, 사용자 laun 후 IDLE/정지 확인을 거쳐 사용자 vinit 예정.

### 2026-10-26 인계 벽 정렬 Clock reversed 읽기 진단
사용자 후진회전 뒤 벽정렬 미동작 보고. 최신 launch 20261026_074613_launch_4553: 후진곡선 controller goal1792968720.670→Reached1792968738.324. TF대기→재개, 벽관측대기1792968739.865→재개1792968742.790 확인. 벽goal1792968742.669 수신 후1792968743.279 Clock reversed 및Action abort. 이번은 이전 Wall observation expired/future 또는 wait timeout과 다른 직접 오류. controller4615가 sensor_hold_robot_20261024/install/farm_wall_controller/lib/libwall_controller.so 로딩 확인. statusERROR/DEVICE_FAILED,odom30개정지. 새DOCK_TEST_9bfeb40a097746428acddda96250233f FAILED/recoverytrue.
실제 로봇 후보 wall_control.hpp의 Clock reversed는 previous_now 대비now역행 또는 now<대기보정된start 또는 wallstamp<last 조건. 로그에 각 수치가 없어 실제시계역행/벽표본순서/대기시간보정 중 어떤 분기인지 미확정. 이전대기후재개 수정은 실행되고 있으며 미적용으로 단정할 근거 없음. 근거와 전체launch/저널/후보헤더/플러그인소스/실행해시는 runs/wall_alignment_diagnosis_20261026 보존. 코드·설정·프로세스·초기위치·이동 변경 없음.

### 2026-10-26 Clock reversed 보정 결함 재현
사용자 읽기추적/오프라인 재현 승인. 실제 wall_control 원본 복사본으로 정상 증가 now/wallstamp에서도 credit_wait가 start를 미래로 밀어 Clock reversed를 발생시키는 경우 재현. take→step 처리지연 변화(30ms→1ms),dt credit50ms,now증가21ms로29ms 미래. 보정없는/동일지연 대조군통과, wait→fresh도재현. 이번실기 분기 수치 부재로 직접귀속은 미확정. trace1183개 per-thread ROS역행0이나C++역행 배제불가. 운영수정/재기동/이동없음. docs/changes/WALL_CLOCK_REPRO_20261026.md 및 runs/wall_alignment_diagnosis_20261026.

### 2026-10-26 wall clock 분리 후보 검증
사용자 승인 후 runs/wall_clock_candidate_20261026에 운영미적용 후보 작성. 고정start와 active/excluded누계 분리, 현재구간credit clamp/초과폐기/내외부중복제외방지, 실제시각·stamp역행과미래검사 유지/수치진단 추가. 후보2파일만 변경, 설정/충돌/취소/WaitClock검증 유지. 신규19+기존대기10+CTest1/1 및 PC빌드통과. ARM빌드/실기미검증. 최종candidate.patch/manifest가 기준이며 make_candidate.py는초안기록. 운영적용/재기동전알릴것. WALL_CLOCK_REPRO_20261026.md 참고.

### 2026-10-26 wall clock ARM 후보 준비 완료
로봇 Downloads/wall_clock_candidate_20261026 별도ARM빌드성공, 신규19/기존10/CTest1 통과. pluginlib4종 생성/소멸 및 후보실로드 경로확인(ROSinit/node/Goal없음), 검증프로세스잔존0. 운영controller4615/기존lib/설정유지, 기존install/config/run스크립트 추가백업. 후보libSHA93761a54… 운영47499187… 불변. PC robot_validation 로그·DEPLOYMENT.md 및 WALL_CLOCK_REPRO_20261026.md. 운영교체/재기동/이동 미실시, 사용자에게 적용전 알릴것.

### 2026-10-26 wall clock 운영 적용 완료
사용자전체종료후승인. 잔존0/원본해시확인→sensor_hold루트 wall-clock-backup-1792970677370575912 추가백업→운영4파일만교체. lib93761a54… 운영경로4종plugin로드/소멸성공,재기동/ROS노드/이동없음. 설정/실행스크립트/저널불변. DOCK_TEST_9bf… recoverytrue유지로 재배치확인후 별도수동복구필요. PC runs/wall_clock_deploy_20261026 및 WALL_CLOCK_REPRO_20261026.md. 사용자만재기동한다.

### 2026-10-26 wall clock 적용 후 사용자 스테이션 재배치·복구
사용자 기존스테이션 위치/방향 확인 및 로봇복구만 승인. 잔존0 재확인→저널원본 console-backup-1792970950947683392 보존→DOCK_TEST_9bf… 복구표시false. previous_record 및 기존실패결과/시각/다른기록 동일검증. 자료 runs/wall_clock_recovery_20261026. 프로세스기동/초기위치/이동없음. 사용자PC더미7183/브리지7242/웹7267 실행중 읽기확인;중복기동금지. 사용자laun→IDLE/정지확인→vinit→zen/dzen 순서,실기전별도검증.

### 2026-10-26 wall clock 새기동 정지 점검
사용자 순서기동/웹표시 후 읽기검사 승인. controller19404 maps 운영libSHA93761a54… 후보실로드 확인, WallAlign activate로그. 로봇IDLE/readytrue/빈task/load0/odom29~31표본0. vinit08:30:03 AMCL Setting pose .104,-1.105,1.532 이후map위치약(.098,-1.107),yaw1.544. 레이저682끝점 median4.55mm/p90 29.53mm/5cm90.9%; 같은scan시각TF 표본비교이며 처리후headerage1.506s는 최신레이저지연의직접측정아님. costmap2cm/일반64x54·인계62x52,현재자세 및+.1rad가상검사통과(일반현재여유약.17m). 출력/odom 단일publisher. 전체경로안전증명아님.
준비미완료: PC더미ERROR/EXTERNAL_STOP/recoverytrue/readyfalse. 태그카메라TAG_ADAPTER_STARTED이후capture exit1, capture.log at_least_3GiB_free_required,현재여유2.807GiB. 신규빌드중간산출물build71M/probe5.4M/install24M 확인,이것만으로전체용량부족원인단정안함. 설정완화/삭제/복구/재기동/이동없음. 자료 runs/wall_clock_ready_20261026. 다음은PC더미승인복구와기록보존디스크정리/사용자카메라재기동이필요.

### 2026-10-26 더미 복구·백업 검증 후 공간 확보
사용자 PC더미복구 및 옮겨도되는 로그/빌드 PC백업후삭제 승인. 웹 dummy_recover/prepare SUCCEEDED, readytrue 및history/결과동일 검증. 더미원본 backup dummy-backups/1792971235105411977.json.
로봇사용중fd/cwd/exe/maps없음 확인한 과거로그 20261024_133841_launch_441230·20261024_073056_launch_337682 및 wall_clock_candidate_20261026/build만 PC runs/space_recovery_20261026/robot_archive.tar.gz와 verified_backup으로복사.106파일976494100bytes 전체SHA256일치검증,삭제직전로봇manifest재일치후3경로삭제. 여유2.807→3.712GiB. 운영install/소스/설정/원복백업/현재런치로그/trace 유지. 주행PID19387/19390/19391/19404/19413유지,카메라잔존0. 프로세스기동/종료·이동없음. 사용자 foreground tag_capture_session 명령으로재기동예정;laun/vinit재실행불필요. 검증manifest/삭제receipt/더미전후기록은동PC폴더.

### 2026-10-26 카메라 재기동 후 #59 반복 준비
사용자 카메라 기동 후 실제 세션 20261026_083600__v2zw6vc 확인. 원본/rect/검출 수신 1357→2124 증가, 약8Hz/수신age .02~.07초, control_ready=true/fault없음. scan-sync control 수확→adapter·AMCL, correction adapter→AMCL, events AMCL→adapter 연결 확인. 현재visible태그없음: 주행 중 AMCL보정 적용은 미검증. 로봇IDLE/ready/odom31정지, 더미IDLE/ready/recoveryfalse, 웹harvest ready/차단없음. 웹#59 ID 25fabab7b348_SEC01_TASK001/W001 대조 후 사용자승인 dummy_repeat 1회300초 SUCCEEDED, 만료 2026-10-26T08:45:37.173427+09:00. 더미저널 바이트불변. 자료 runs/repeat_ready_20261026. 코드·설정·프로세스기동/종료·이동명령 변경없음. 사용자가 웹주행 전송, 인계는 별도확인.

### 2026-10-26 08:43 #59 주행 실패
사용자웹전송 관찰. 일반controller goal1792971781.509→collision ahead1792971816.869/abort, 관제NAVIGATION_FAILED status6/error106/harvested0. 이후odom31정지 및 사용자현장정지확인. window미도착/더미저널반복허용전과바이트동일/새도착기준미저장(설치본communication은시작시무효화·SUCCESS에서만저장). 태그이벤트 accepted1/rejected76, inactive_or_task_begin 기록; 적용이벤트없고 TAG_CORRECTION_APPLIED없음. 태그거절과충돌의인과미확정. 로그 runs/window59_20261026_0843. 사용자초기정합오류가능성제기후직접재배치·재시작예정;원인확정아님. 에이전트코드·설정·기동종료·초기위치·이동조작없음. 인계미실시.

2026-10-26 사용자 재기동/vinit 후 로봇 새boot c67e6587… IDLE/odom30정지, 더미ready/recoveryfalse. 이전반복만료확인→#59 1회300초 재허용성공(만료 08:53:34 KST). 관제harvest ready이나 paused.harvest=true: 사용자웹대기열재개필요, 에이전트관제변경/이동없음. runs/repeat_ready_20261026/after_reinit*.json.

### 2026-10-26 08:49 재시작 #59 성공
사용자웹전송, 새boot c67e6587…/launch084654 기준. 접근1792972151.111→2204.214 완료, window2205.550→2216.867 완료. AMCL TAG_CORRECTION_APPLIED1792972208.908/scan2208752025913 및adapter applied1 확인(초기접근중 control거절110개와구분). 보존task_event 2de0dbb7… arrival acceptedtrue, actual(1.580559,-.011071,-.018841),오차 .031241m/.018841rad. 관제SUCCESS 08:50:19, 더미신규attempt66a6fa… SUCCESS2/실패0/이전이력보존. 새도착기준은설치본SUCCESS전remember_window 호출계약과이번성공event로확인(내부객체직접덤프아님). 최종IDLE/ready/loaded2/odom31정지,더미ready/recoveryfalse. 이번수확은PC더미,실팔미검증. 자료 runs/window59_20261026_0849. 인계미요청,사용자dock_transfer전송대기. 코드/설정/프로세스변경없음.

### 2026-10-26 08:58 인계 벽 정렬 진행도 실패
사용자 dock_transfer 전송 DOCK_TEST_155cf97ddafc4253a633704317e0883b / TRANSFER_TEST_aaa7c521adaa431ba82e2b139975f848. 인계전용goal1792972711.030→2725.682 도달. 벽관측대기후2728.822 벽goal시작,TF대기2739.903→2741.119 및2746.353→2747.328 재개. 2753.323 Failed to make progress/abort. 이번직접실패는Clock reversed/관측waittimeout이아닌진행도검사이며대기제외와의연관은추가분석필요. 저널08:59:15 FAILED/recoverytrue/activefalse. 상태ERROR DEVICE_FAILED/loaded2/odom31정지 확인,현장정지질문전달. DOCK_READY미도달,배출/복귀미실행. 로그 runs/dock_20261026_0858. 코드/설정/재기동/이동/복구변경없음.

### 2026-10-26 벽 진행도 실패 읽기 대조
사용자현장정지확인. 실제WaitingProgressChecker .005m/.01745rad/10초;실패wall24.501초,이전성공24.101초. 성공bag대기누계3.568초/odom임계갱신최대9.598초(실checker재현아님). WaitClock min(delta,dt) 후전체last_total갱신으로대기과소제외결함 산술재현10초→5초,이전성공버전에도존재. 이번trace에pose/velocity/credit없어직접원인귀속미확정. 운영수정/재기동/이동없음. docs/changes/WALL_PROGRESS_AUDIT_20261026.md 및 runs/wall_progress_audit_20261026.

2026-10-26 사용자스테이션재배치/복구승인. 새laun39805/boot1ca79c… 실행중,TRANSFER_RECOVERY_REQUIRED 및POSE_UNAVAILABLE 확인. 임의종료안함;사용자laun/zen/dzen종료요청후로봇저널복구대기. PC더미만backup1792974200413140288.json→recover/prepare성공(IDLE/ready/recoveryfalse),history불변 및복구표시외필드검증. #59재허용은로봇복구·준비후진행예정. 코드설정/이동변경없음.

### 2026-10-26 사용자 전체종료 후 인계 복구 완료
사용자스테이션재배치 및 laun/zen/dzen종료확인. 도구잔존0 확인후 DOCK_TEST_155cf97ddafc4253a633704317e0883b 복구표시만해제. 원본백업 /home/vic/.local/state/manyfarm/harvest_01/console-backup-1792974315463965635; previous_record전체일치/FAILED결과·시각·ID보존/다른기록불변 검증. 재조회잔존0·복구필요0. 코드설정변경/재기동/초기위치/이동없음. 사용자laun→IDLE확인→vinit→zen/dzen, 준비후#59허용예정. 자료 runs/repeat_ready_20261026/*robot_reconcile*.json.

2026-10-26 재기동092601 사용자vinit/zen/dzen완료후읽기확인: AMCL초기값반영,실제추정(.082963,-1.104237,1.543157),IDLE/ready/odom31정지. 레이저689점 map끝점median4.67mm/p9022.99mm/5cm90.42%(전체경로증명아님). 카메라7.5Hz,더미ready/recoveryfalse/웹차단없음. #59 1회300초허용성공,만료 09:33:04 KST. 자료 runs/repeat_ready_20261026/latest* 및permit_0928.json. 코드설정/이동변경없음.

### 2026-10-26 09:31 인계 TRANSPORT_CLEAR 후 복귀 실패
사용자전체시퀀스성공설명과달리수확최종FAILED확인. DOCK_TEST_ec1de… 벽정렬/DOCK_READY/더미배출성공,TRANSPORT_CLEAR09:33:44.675정상수락→후진이탈완료→guard:align95.57초대기후이동범위초과. transfer_complete/transport_clear=true,restore_complete=false. 코드설정변경없음. 상세 docs/changes/TRANSPORT_CLEAR_AUDIT_20261026.md, 자료 runs/transport_clear_audit_20261026.


## 2026-10-26 회전 검사 대기·재개 후보 (운영 미적용)

사용자 승인으로 로봇 현장 원본을 백업하고 PC runs/align_recovery_candidate_20261026에 별도 후보 작성. align 영역 밖 costmap 변경의 재검사 무효화 방지, 장애물·정지 자세 변화의 정지 대기, 취소·정지 보호 유지. 공통 arc_clearance 예외 하위형 추가는 후보에만 존재하며 실물·시뮬 원본 미수정. 오프라인 91개 통과, 로봇 빌드·ROS/실기 미검증. 설정·운영 프로세스·이동·commit/push 없음. 상세/백업/원복/로그: docs/changes/ALIGN_RECOVERY_CANDIDATE_20261026.md.


- 2026-10-26 사용자 승인 후 align 후보 ARM64 별도 빌드2패키지·설치모듈9개/entrypoint 로드·오프라인91개 통과. 운영 소스/설치본/설정10파일 추가 백업 및 PC전송SHA확인. 운영 교체·재기동·이동 없음. PC 기존 테스트의 상대경로 직접로드 한계를 정정하고 로봇 후보 설치본으로 재검증. 적용·원복계획 및 초기실패 포함 로그: docs/changes/ALIGN_RECOVERY_CANDIDATE_20261026.md. 실기미검증/commit·push없음.

- 2026-10-26 사용자 종료 확인·적용 승인 후 align 후보 운영 소스4/설치본4 적용 완료. 원본·설정·캐시·런치로그 추가백업/PC전송SHA확인. 운영 모듈9+진입점 로드, 오프라인44개 통과. 설정·복구기록 불변, 재기동·이동 없음/실기미검증. 상세 ALIGN_RECOVERY_CANDIDATE_20261026.md. commit/push 없음.

- 사용자 스테이션 재배치 확인 후 robot_agent로 로봇 미완료1건 복구표시 해제·이전실패/원본백업 보존. 코드설정불변/PC더미불변/기동이동없음. 사용자 laun→IDLE/정지확인→vinit→zen→dzen 순서 대기. 상세 ALIGN_RECOVERY_CANDIDATE_20261026.md.

- 2026-10-26 사용자 일반 주행 다회 재시도 요청: 별도 collision retry 후보 작성, PC17개 통과. 기본off/선택5회·정지2초, 충돌검사·취소유지. 운영미적용/실제Action문구·상위시간제한통합검증남음. 상세 docs/changes/NAVIGATION_COLLISION_RETRY_20261026.md.

- 2026-10-26 일반주행 재시도 후보 통합검증: 실제 PC Nav2는106/error_msg빈값 반환, 분류보완. 충돌대기를 전체주행시계에서 제외. 운영 TF복구off/단일출력 계약 유지하도록 수확전용선택·기존runtime zero콜백 분리. 단위18+소유권2, 격리ROS/FSM5시나리오 및 실제Nav2오류1건 확인. 로봇Nav2버전차/ARM빌드/전체노드조립·실기미검증, 운영미적용. 상세 NAVIGATION_COLLISION_RETRY_20261026.md.

- 2026-10-26 재시도 후보 ARM2패키지빌드·모듈11/진입점로드·단위20·격리ROS/FSM5 통과. 로봇Nav2 1.3.11 실제격리controller에서106/빈문구 재현. 운영원본/설정백업·PC전송SHA검증·시험프로세스종료. harvest 전용retry5 설정은제안파일만준비. 운영미적용/재기동·이동없음,전체노드조립·실기미검증. 상세 NAVIGATION_COLLISION_RETRY_20261026.md.

- 2026-10-26 14:47 사용자 승인·잔존프로세스 없음 확인 후 일반주행 retry 후보 소스6/설치6 및 수확전용5회 설정 운영적용. 기존핫픽스/기록 추가백업·PC전송SHA확인. 운영11모듈/진입점로드·수확retry5/공통retry0/TF복구off 확인. 인계설정·복구저널불변. 재기동·이동없음/실기미검증. 상세 NAVIGATION_COLLISION_RETRY_20261026.md.


### 2026-10-26 전진 곡선 대체·지속 대기 후보 (운영 미적용)
사용자 “다시 안멈추게 고쳐와” 요청. 로봇 운영 소스 읽기 백업 후 runs/forward_recovery_candidate_20261026에 별도 후보 작성. 기본 RPP 경로 방향 회전이 막혔을 때 동일 충돌 검사를 통과한 전진 곡선만 선택하는 새 플러그인, 수확 전용 선택형 지속 대기 연결. 횟수 소진/30초 준비 지연으로 종료하지 않되 취소·소유권·기타 오류/실행 제한 유지. 합성 Nav2 costmap 복합1+기존C++12, Python18+4, 격리 Action/실제 Harvest FSM6 시나리오 통과. 지속 대기에서 6회 abort 후7번째 성공, 사용자 취소 전달 확인. PC 빌드 성공; ARM/운영 로드·실물 통과는 미검증. 원본 설정·운영 프로세스·이동·commit/push 변경 없음. 상세 docs/changes/FORWARD_RECOVERY_CANDIDATE_20261026.md. 실제로 막힌 모든 경우에도 계속 움직이는 변경은 아니다.


- 2026-10-26 전진/지속대기 후보 ARM3패키지 빌드 및 로봇 Nav2 1.3.11 검증 완료. 후보 pluginlib3종/설치Python10모듈, C++1+12/Python18+4/격리FSM6 통과. 운영292파일 추가백업·PC전송SHA/내용 검증 및 불변 확인, 운영미적용·재기동/이동없음. 사용자 과도한 변경 지적으로 A(기존 controller 유지·종료 방지 Python4+설정)와 B(새 전진 플러그인 추가)를 명시 분리. 실제 코너 통과·전체노드 기동 미검증. 상세 FORWARD_RECOVERY_CANDIDATE_20261026.md.

- 2026-10-26 사용자 기존 성공 전진·회전 복원/최소 수정 요청으로 새 플러그인 적용 보류. 성공 보존 일반Nav2 설정↔현재 실행값 전체 동일, 성공 runtime baseline↔현재 normal 출력분기 AST 동일 확인. 되돌릴 전진 제거 변경은 미발견. 입력 위치/셀 차이는 있으나 최신실패 controller 내부 기하 기록이 부족해 직접원인·수정완료 미확정. 추가추측수정/운영적용/이동없음. 상세 FORWARD_RECOVERY_CANDIDATE_20261026.md 및 runs/success_motion_compare_20261026.

- 2026-10-26 전진 전환 판단 수집 도구 준비/별도 로봇 Downloads 배치. 기존 코드·설정·프로세스 유지, 수집 미기동. 실제 RPP경로점/회전선택/raw출력·TF/odom/scan/costmap full/update 및 실행params/launch로그 보존. foreground/Ctrl+C/5분·용량한도, CAPTURE_READY 후 사용자웹전송. PC 더미7183/브리지7242/웹7267 실행중, 로봇잔존없음, 위치답변대기. 상세 FORWARD_TRANSITION_CAPTURE_20261026.md.

- 2026-10-26 사용자 재시작 정리 승인 및 스테이션 재배치 확인. 로봇 수확 관련 잔존0/미완료 복구표시0, 저널 전후SHA불변. PC 더미7183/브리지7242 정확한argv확인후SIGINT정상종료·잔존0. 더미저널전후PC백업, records/history동일/recoveryfalse 확인. 미니웹7267 유지. 코드·설정·초기위치·이동·프로세스기동 없음. 근거 runs/restart_cleanup_20261026. 사용자 PC더미→PC브리지→로봇laun 후 IDLE/정지 확인, 이후vinit/zen/dzen. 수집 도구는 아직 미기동.


### 2026-10-26 16시 성공 시험 및 사용자 전체 재시작 준비
기존 운영 코드/설정 그대로 #59 window SUCCESS·PC더미2개 완료. bag에서 코너 전진약 .054m/s+회전 -.111rad/s 전환 확인. 인계 곡선/벽 정렬 완료 후 WAIT_DOCK_STABLE/odom정지 확인, 배출/복귀 미완료. 자료 runs/forward_trial_live_20261026. 사용자 운송측 문제로 전체 재시험 및 스테이션 재배치·종료 요청. 확인한 런치/자식·로봇브리지2·PC더미/브리지 SIGINT 종료, 로봇도구 잔존0 검증. 종료 중 카메라 adapter254/세션exit1 로그 보존(정상종료로 보고하지 않음). 기존 도구로 DOCK_TEST_41a42af980b54373b3aea229f1370b92 복구표시 해제, 원본 previous_record·나머지기록 불변 검증. 로봇 backup console-backup-1793000090681272873 및 PC runs/restart_full_20261026_1615 보존. 더미 recoveryfalse/전기록terminal, 변경불필요. 미니웹7267만 유지. 관제에는 인계Action실행중 차단이 남아 사용자웹정리 필요. 신규 주행/인계 구독 전용 PC전경수집 watch.bash/watch.py 준비, Python컴파일/Bash문법검사 통과; 실제 재기동 후 구독은 미검증. 1시간/5Hz동작표본·상태/Action/rosout 포함, 원본scan/costmap 전체bag 아님. 수집·운영재기동·초기위치·이동은 미실행, 사용자가 시작. 코드/설정·commit/push 변경없음.


### 2026-10-27 로봇 운영 소스 PC 동기화 완료
사용자 인계·복귀 성공/다음 좌표 실패 보고. 로봇 마지막 저널 DOCK_TEST_c5ff0375c7af4e5a88c5748affd06a5d 10/26 22:05 SUCCESS 확인. 운영 overlay 소스와 실기 프로필을 PC에 반영하고 미적용 전진 후보/예찰 변경 제외. 신규 시험코드/자료는 Git 밖 vmany_artifacts/robot_sync_20261027에 보존, 미니웹 운영 도구 유지. 원본 백업·86모듈설치대조·별도PC4패키지빌드·재시도18/벽시각19/CTest1통과. 로봇 코드설정/프로세스/이동 변경없음. 다음 좌표 이동은 미해결이며 전체 운영완료로 확대하지 않음. 상세 [ROBOT_PC_SYNC_20261027](changes/ROBOT_PC_SYNC_20261027.md). 커밋/스테이징/push는 사용자 담당.


### 2026-10-27 로봇 프로젝트 실행 경로 전환 완료
사용자 승인으로 성공 overlay 운영 코드를 로봇 프로젝트에 반영·ARM4패키지빌드하고 laun을 project install/상대경로프로필로 전환. 기존70모듈SHA·모든 생성서버설정 동일, 플러그인4로드/소멸·CTest1 통과. 기존 Downloads 성공본과 변경전src/install/별칭 백업 보존. 다른별칭/브리지/저널 불변. 신규 PC 도우미도 저장소에 포함. 실기기동/이동/commit/push 없음. 디스크여유2.7GiB로 기존카메라3GiB시작검사보다부족, 기록임의삭제없음. 상세 docs/changes/PROJECT_RUNTIME_MIGRATION_20261027.md.


### 2026-10-27 성공 기준 고정 및 커밋 준비
사용자 실기 확인과 관제 결과 대조: 15:20:06 인계·복귀 SUCCESS, 15:20:32 다음 #60 수확 SUCCESS. 현재 5cm·6도 완료 판정/일반 주행6도 프로필을 유지하고 추가 동작 변경 없음. PC 수확 운영 파일과 로봇 소스 일치, 설치74모듈 동일. 실제 팔/운송 도킹·이격 미검증(PC 더미·수확 단독). 시험자료와 실행본은 Git 밖 success_freeze_20261027_152308에 보존, 기존 백업 유지. 다른 담당 scout/burger 차이는 미병합. 시뮬 동작 변경 없음. commit/push/스테이징 미수행. 상세: docs/changes/HARVEST_SUCCESS_FREEZE_20261027.md.


### 2026-10-29 후진 복귀 컴포넌트 분리 — PC 적용, 시뮬 전환 미적용
사용자 운송 구조 참고 구현 승인으로 공통 StationReturn에 미션/정리 경계와 client_factory, RoutePlan 역순 함수, Nav2 선택형 오류 분류를 추가했다. 실물 복귀는 수확 Mission + 준비/후진/정리 States + Controller를 사용한다. 기존 retry_count=5와 출력 소유자를 연결하고 같은 구역의 태그 토큰을 방향 흔들림 동안 유지한다. 노드18·방향·도착허용치·후진 C++·기존 인계·운송·sim/ 파일은 변경하지 않았다. 시뮬은 기존 기본 경로를 유지하며 새 컴포넌트 연결 계약은 docs/changes/STATION_RETURN_REAL_PC_20261028.md 마지막 절에 정리했다. 이번 직접 오프라인64개 통과. 기존 시간 시험10개 fixture 오류는 변경 전후 동일 재현, 누락 기본값만 시험 runner에 보완 시 전후12개 통과. 실물/Isaac·태그 경계 ACK는 미검증. PC만 수정, 배포·재기동·commit/push·외부 전달 없음. 기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4, 기존 미커밋 변경 보존.


### 2026-10-29 후진 복귀 로봇 적용·빌드 완료
사용자 배포/빌드 승인으로 실제 import 경로의 공통3파일+격리 release 수확4파일 적용.
farm_common/farm_navigation/harvest_robot 빌드 성공, PC·소스·설치본7파일 해시 일치,
로봇 설치본 오프라인 컴포넌트8개 통과. 기존 인계·설정·Jetson 변경 보존.
팔 상태 생략true/재시도5회, dinit14번·12번 반대 방향, 목표18번·0번 방향 확인.
14→18 설치본 경로 계산 통과는 실물 주행 성공이 아님. 재기동·명령은 사용자 담당, 미수행.
PC 백업 /home/eunbi/vmany_artifacts/robot_backups/station_components_20261029_031355/.
상세 검증·원복은 docs/changes/STATION_RETURN_REAL_PC_20261028.md 마지막 절.
commit/push·sim/변경 없음. 시뮬 전달 자료는 코드 확정 후 작성한다.


### 2026-10-29 미니관제 복귀 버튼·03:21 주행 분석
PC trial_console에 설정 기반 스테이션 복귀/내 복귀 취소/수락·진행·결과 표시 추가. 현재 목표18, farm_map_v1, 팔 ready와 독립. PC 서버 재시작·새로고침 필요, 로봇 재빌드 불필요. 단위+격리 ROS17개 및 JS 검사 통과, 실물 버튼 미검증. 운영 프로세스/로봇 코드 미변경.
사용자03:21 복귀83.45초 SUCCESS, 재시도 발동 없음. 태그 단일토큰·9회 모두적용·세션거절0, 직선 반복정렬0. 직선 벽 간격 추정16.4→21.1cm, 코너 지도 기준 최대편차20cm로 주행 품질 문제는 남음. 자료 /home/eunbi/vmany_artifacts/station_return_analysis_20261029/run_0321/, 상세 docs/changes/STATION_RETURN_REAL_PC_20261028.md 최신절. 물리 외곽/실제전송Path와 지도/footprint추정을 구분. sim/인계/관제 미변경, commit/push 없음.

### 2026-10-29 후속: 팔 없이14번 이동 PC 구현

최신 PC 추가분: navigation_trial.py, node.py real 조건부 연결, station_return_real.py 준비 wrapper, 실물 시험 YAML navigation_trial_config 및 미니관제 move_trial/취소. 기존 dinit14/방향 설정 재사용. PC 단위8+복귀35+콘솔19/JS 검증 통과. **로봇에는 아직 이번 이동 endpoint를 배포/빌드하지 않았고 어떤 운영 프로세스도 재기동하지 않았다.** 이전 배포된 복귀 기능과 구분한다. 팔 상태 미수신 생략은 기존 시험 프로필 설정을 재사용하지만 이전 팔 실패/blocked를 지우지 않는다. sim/인계 파일은 이번에 수정하지 않았다. 상세 분석·제안·원복은 docs/changes/STATION_RETURN_REAL_PC_20261028.md 마지막 절. 코너 개선/태그 설정 보정은 미적용이며 추가 재주행 결과 없음. commit/push 없음.

### 2026-10-29 03:52 배포 상태 갱신

사용자 승인으로14번 이동을 기존 jetson_reply_20261027_1741 release에 적용/harvest_robot 단독 빌드 완료. source3/config1, 예상 외 파일 변경0, 설치본 mock 시험8개 통과. **사용자 재기동 대기**이며 실제 Action 기동/주행은 미검증. PC 콘솔 재시작·새로고침도 사용자 수행. 인계/시뮬/코너 미변경, commit/push 없음. PC 백업 navigation_trial_20261029_035228. 상세는 STATION_RETURN_REAL_PC_20261028.md 최신절. 앞의 “이동 endpoint 미배포” 기록은 이 업데이트로 대체한다.

### 2026-10-29 04:00 사용자 시험 분석

14번 이동03:59:31 SUCCESS, 복귀04:00:00~04:01:15 SUCCESS(75.43초) 확인. 후진 태그10회/단일세션, 직선 반복정렬0이나 벽간격 추정17.2~23cm와코너19.08cm 이탈 지속. 태그 적용 주변 mapY 수cm변화/벽거리 거의불변 사례; 기존pixel_bias 모델 재검증 후보. 코너정렬↔후진18회로 이전문제 반복. 분석만/운영코드미변경, 코너수정아직금지. PC run_0400에27파일해시검증보관, 원본삭제없음. 기록은전진완료후시작; 이후04:02 충돌재시도는별도주행이므로후진결과에섞지말것. 상세변경문서최신절참조.

### 2026-10-29 코너 구현 전 선행 조건 불충족

사용자는 코너 PC 수정 전 꼭짓점 회전공간 확인을 요청했다. 정확한 기존 arc_clearance 검사에서 정적map+local10/102 충돌 → 꼭짓점 제자리회전안 미적용. 반경20cm 후진원호 대안으로 PC구현 범위 변경 질문을 보냈고 답변 대기. 새 컨트롤러를 만들지 않되 기존ArcController 시작계약/1cm편차/독립서버 연결 검증 필요; 인계 후보를 무검증으로 운영 복귀에 붙이지 말 것. 운영 코드/설정/로봇/인계/sim 미변경.
태그 추가검증: 기존 fit_wall 재사용 도구 robot/tools/station_return/review_tag_bias.py 신설,03:21 9표본+04:00 10표본 전부매칭. 방향보정은개선/거리항은상대벽위치잔차악화 반복. 거리계수부호재검증후보이며현재계수미수정. 재현자료 corner_tag_review, 상세변경문서최신절. 이번 작업을 코너 수정 완료라고 보고하면 안 된다.

### 2026-10-29 원호 코너 승인 후 PC 구현·검증 완료

사용자 원호 방식 승인 수신. harvest_robot에 station_corner_plan/config/navigation + 실물 station_return.launch.py 추가, RealStationReturn 선택형 연결과 패키징/시험 갱신. 기존 공통·인계·sim·원본 실물 YAML·태그 계수는 이번에 수정하지 않았다. wrapper에서만 반경20cm/전용 서버/태그 기본true 선택; 기존 laun은 아직 기존 실행이다. 기존 재시도5회와 태그 세션 유지,18번 목표/최종판정/dockedfalse 유지. 원호 속도 기존0.01m/s.
PC56개/C++2프로그램, DOMAIN231 loopback 실제 Nav2 configure/activate/preflight/합성 원호 및 조립 실행, 격리 harvest_robot 빌드 통과. 과거 map1+local102개에 새159점 원호 검사 모두 통과(여유하한 최소4.12cm). 전체 실물 주행·진입 정밀성·추종 여유·태그 동시 검증은 남아 있다. 직선 거리 보정 모델은 아직 수정하지 않았다. 로봇 배포/빌드/재기동/명령·commit/push 없음. 근거 corner_arc_pc 폴더, 상세 변경/실행 선택/원복은 STATION_RETURN_REAL_PC_20261028.md 최신절. 이전 승인 대기 기록을 이번 상태로 대체한다.

### 2026-10-29 복귀 원호5cm/s PC 적용·검증 (이전31초 설명 갱신)

사용자 인스턴스별 공통 상한 분리 명시 승인. ArcController configure에 arc_max_linear_vel/arc_max_angular_vel 추가, 기본0.01/0.15 그대로. 실물 station_corner_config만 desired/linear상한0.05m/s·angular상한0.30rad/s. 기존 인계·sim·태그·경로·충돌/1cm추종제한 불변. 새 test_arc_speed+CMake 및 설정시험 갱신. PC Python56/CTest3, 실제Nav2 격리 5cm/s 약6.2초(외란없음편차약2mm), RPM, 장애물106거절/출력0, 미지정기본1cm/s, 조립실행 통과. /tmp 격리2패키지 빌드 완료. 실물/Isaac 미검증, 로봇 배포·빌드·재기동·명령/commit/push 없음. 근거 corner_speed_pc, 상세 STATION_RETURN_REAL_PC_20261028.md 최신절. 기존 laun은 여전히 미변경이며 향후 별도 배포 요청 필요.

### 2026-10-29 04:55 원호 복귀 로봇 배포·빌드 완료

사용자 배포/빌드 승인, 재기동은 사용자 담당. 기존 런치 실행 중이므로 source/install 덮어쓰기 대신 station_corner_20261029_045549 overlay에2패키지 배포/ARM빌드.94소스SHA·CTest3·오프라인11+실제14→18 경로/팔생략true/5cm/s/prefix 확인. 기존 인계/sim/원본release/laun·zen·dzen 유지. 새 사용자 명령은 `bash /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.bash /home/vic/vmany-runtime-staging/station_corner_20261029_045549`. 이전 런치는 사용자가 종료해야 함; --check에서기존충돌PID확인. 초기화는실제14번·12번등짐·IDLE정지에서dinit, 기록은collect.bash --seconds180 후CAPTURE_READY, 미니관제복귀. 명령전체/반복14이동비교는station_return/README 최신절.
PC백업 robot_backups/station_corner_20261029_045549. 과거종료기록2개54파일PC해시검증이관후로봇원본만제거, 최신기록유지/여유약3.35GiB. 기록기station_corner토픽추가. 운영프로세스·재기동·주행·새bag미실행. 실제새서버활성/추종미검증, commit/push없음. 상세STATION_RETURN_REAL_PC_20261028.md 최신절.


### 2026-10-29 05:16 복귀 연결부 결함 수정·새 overlay 적용
실제 위치→그래프 투영 연결부를 원호 코너로 오인하여 시작 전 실패하던 결함을 수정했다. 선택된 그래프 edge_ids로 본선 코너만 분할하고 실측 시작점을 기존 후진 접근에 유지한다. 인계/공통/sim·태그/속도/허용치 미변경. PC60개, 로봇 설치본15개(실측+오차36사례), ARM빌드2패키지/CTest3 통과. 새 실행 경로 `/home/vic/vmany-runtime-staging/station_corner_20261029_0516`; 기존 launch_corner.bash에 이 경로를 전달한다. 기존 실행 PID261360 보존, 사용자 재기동·실물 시험 대기. 상세/백업/원복은 STATION_RETURN_REAL_PC_20261028.md 마지막 절. commit/push 없음.


### 2026-10-29 05:19 실물 복귀 실패 확인
새0516 overlay 실제시험은 원호 진입 전 StationReverse 정밀 접근에서 실패했다. 지도/18번 목표/지도 bag 데이터는 정상(이전 기록과 동일). 진입점5mm 판정+기존 후진 근접 방향 정렬/최저속도5cm/s 조합에서 반대 회전이 발생, 약94초에 INVALID_PATH103. 원호 자체는 미실행. 기존PC60시험은 기하/계약 검증이며 이 실물 폐루프 성공을 보장하지 않는다. 재주행 전 접근 조립 수정·검증 필요. 이번 읽기분석만 수행, 인계/sim/배포/재기동 미변경. 근거와 수치는 STATION_RETURN_REAL_PC_20261028.md 최신절 및 PC run_0519.


### 2026-10-29 접근 감속·위치/방향 분리 수정 및0555 배포
실물 복귀 접근만 기존 저속 이탈 최저속도0.006m/s로 감속하고, 일반 위치반경4cm 완료→실제정지→동일시각 map/odom으로 고정한 방향차→별도 Spin/충돌검사→정지→원호 순서로 분리했다. 기존 인계/공통/sim·18번 최종 판정·태그/원호속도 불변. PC62개, 기록흔들림 실제Nav2 폐루프3조건/이전실패대조/Spin동적충돌거절, 실제기록 공간검사 통과. 로봇새 `/home/vic/vmany-runtime-staging/station_approach_20261029_0555` 빌드2패키지/CTest3/설치본17개 통과. 재기동·실물시험 사용자 대기. 최종읽기확인 수확프로세스0개, 에이전트는 종료하지 않음. 종료capture3개83파일 PC해시검증이관, 로봇여유3.267GiB. 명령 README/근거·백업·원복 STATION_RETURN_REAL_PC_20261028.md 최신절. commit/push 없음.


### 2026-10-29 06:00 실물 결과: 접근/정렬/태그 확인, 원호 미완료 과제
사용자0555실행본 시험은101.98초뒤SUCCESS/docked=false. 접근6mm/s감속·4cm위치완료후정지·별도8.24도Spin/잔여.30도 확인. 태그동일세션9회적용/거절0 유지. 그러나원호시작에arc deviation exceeded106이빈메시지로돌아와충돌재시도1회로처리됐고,Nav2성공후정지까지1.84cm/7.39도추가이동,원호정지오차1.365cm/5.456도accepted=false에도경고후최종직선진행. 전체SUCCESS를원호정상검증완료로확대하지않는다. 다음은원호시작/끝감속·106분류·원호전용정지후판정검토. 이번읽기분석/문서만,코드/배포/재기동변경없음. 근거run_0600와STATION_RETURN_REAL_PC_20261028.md최신절.

### 2026-10-29 카메라OFF·접근 중복정렬 수정 배포

사용자 승인으로 공통ReverseRPP 기본false 선택기능 추가, 실물코너접근만true.
새 /home/vic/vmany-runtime-staging/station_no_camera_20261029 빌드3패키지,
ARM CTest5/PC Python54 및 실제Nav2 흔들림2조건·충돌거절 확인. 실물 미시험.
도구 launch_corner.py/collect.py/timing_capture.py 적용, --without-camera 선택.
기존실행PID 유지·사용자 재기동 담당. 종료기록만PC검증백업후정리, 여유약3.47GiB.
명령 README 최신절, 상세 STATION_RETURN_REAL_PC_20261028.md. commit/push 없음.

### 2026-10-29 16:11 시험 전후진 전체 비교

이전0555 양방향SUCCESS/태그각10회, TF/odom수신지연유사. 상세
[전후진 비교](changes/STATION_FORWARD_REVERSE_COMPARISON_20261029.md)에 실행설정전체표와
거리모델방향차이·원호끝출력잔류근거기록. 운영수정없음. 후속은직선거리모델과
제어출력을분리검증하고원호기하오차와제동추가회전을분리할것. 최신선택기능시험으로
오인하지말것. 원호완료accepted=false는남아있으며최종SUCCESS와구분한다.


### 2026-10-29 단계별 카메라 비교 시험 준비
기존0555로 전진 카메라ON→14번 정지 후 camera_phase.py --stop→후진OFF 비교. 사용자 실행 도구만 배포, 운영 종료/재기동/주행 미수행. 주행·인계·sim 미변경. 현재 카메라는 이미 오류 종료되어 사용자 재기동 필요. PC 백업 검증 후 종료 기록만 정리해 당시3.47GiB 확보. 1차 결과 후2차 준비,2차 코드 미적용. 상세 STATION_RETURN_REAL_PC_20261028.md 최신절. commit/push 없음.


2026-10-29 카메라 도구 의존 배포 보완: process_agent.py가 로봇에 없어 기본 조회 실패. 기존 PC 모듈을 추가 배포·해시 대조 후 로봇 실제 조회 CAMERA_ON/exit0 확인. 종료/재기동 미수행. 상세 STATION_RETURN_REAL_PC_20261028.md 최신절.


### 2026-10-29 17:11/17:14 카메라 단계 비교 결과
기존0555 전진·후진SUCCESS/정상기록,후진카메라실제OFF 확인. 그러나전진보정7요청모두거절(적용0): 세션교체begin이AMCL이전종료barrier보다3.33ms앞서지속거절. ON/OFF는프로세스부하비교만성립. 후진odom age p95약20ms로감소했으나벽간격17→21cm 이격지속,원호정지오차accepted=false 지속. 코드미변경/2차미적용. 상세STATION_RETURN_REAL_PC_20261028.md 최신절,PC run_1711. commit/push 없음.


### 2026-10-29 2차 후진 접근 시험 배포 준비 완료
사용자 공통·격리배포 승인. ReverseRPP 기본OFF 곡률선행점선택을 실물접근만ON, HarvestWork의0.4m/종점연장값을읽어재사용. 전진·인계·sim·태그·속도·허용치불변. PC62+CTest5,기록/오차/충돌재현,ARM3패키지빌드/CTest5통과. 새 station_work_curvature_20261029; 사용자재기동대기. 위치흔들림후접근오차5.75~7.01cm경고는남음,실기성공미검증. 기존0555유지. 명령/근거/원복 STATION_RETURN_REAL_PC_20261028.md 최신절. commit/push없음.


### 2026-10-29 2차17:43 실기 결과
새설정적용/후진카메라OFF 확인. 후진84.72초SUCCESS,진입방향9.88→2.08도/별도Spin없음. 그러나벽간격17.94→21.46→23.71cm로미개선,원호정지1.14cm/5.91도accepted=false지속. 전진태그이번9적용(1차0)이라조건차이명시. 사용자육안차이적음피드백과일치. 추가튜닝없음,PC run_1740/상세변경문서최신절.


### 2026-10-29 추가주행없는 상세분석의 새 단서
2차재구성경로횡오차RMS1.42cm,명령각속도예측MAE.0013rad/s/부호98%일치. 16:11·17:11/14·17:40/43 전후진6구간의라이다벽거리변화는odom속도/벽방향과약1.99~2.05도등가각도차이를반복. odom내부위치/속도방향은일관. 센서/TF각도와실제주행방향의공통기준차이가우선후보지만장착오류확정아님,2도설정미적용. 자료run_1740/deep_analysis,상세STATION_FORWARD_REVERSE_COMPARISON_20261029.md최신절. 분석/문서만,추가주행/코드수정없음.


### 2026-10-29 도킹 기준 자세 측정 준비
사용자 요청으로 정지30초 구독 전용 dock_reference.bash를 PC/로봇에 준비했다. 라이다 원본/필터·TF/static·odom·속도 기록 및 실제 메시지 수 확인. 원하는 최종 주차 자세의 사용자 측정 대기이며 목표값/도킹 구현 미확정. 주행·인계·sim 및 운영 프로세스 미변경, commit/push 없음. 검증/명령/원복은 docs/changes/STATION_RETURN_REAL_PC_20261028.md 마지막 절.


### 2026-10-29 도킹 기록기 터미널 정지 수정
사용자 실행 후 30초 종료 불가 보고. 18:42:50 기록 PID458353은 T(stopped), timeout은 별도 PGID458352, 운영 터미널 전경 스크립트 PGID458328. recorder.log 경고 한 줄, bag 디렉터리 없음: 이번 측정 데이터 미수집.
timeout 별도 그룹에서 rosbag 키보드 입력의 job-control 정지가 원인에 부합. 도구에 timeout --foreground 및 rosbag --disable-keyboard-controls 적용·로봇 반영. 기본 30초·기록 토픽 유지.
PC/로봇 Bash 문법과 옵션 지원 확인. 새 SHA256 ade23a63a93ed7cc730c6b087a6598a80188f237069be4d29bc8cf64ac03fffd. 실제 터미널 재실행 종료는 사용자 확인 대기. 이전 문법 검증을 자동 종료 실기 검증으로 보지 않는다.
기존 기록기 종료는 사용자에게 해당 PID TERM 후 CONT 명령 안내. assistant 프로세스 종료/기동 없음. 운영·인계·sim 미변경, commit/push 없음.


### 2026-10-29 도킹 기준 측정 확보
18:51 정지30초 기록 성공. 사용자 실측 뒤22/좌25.4/우24.6cm, 라이다 기준 뒤0.520243/좌0.496220/우0.494075m(base 원점). 세 벽295프레임 모두 추출, odom884개 정지. 목표 설정/도킹 구현 미적용. 상세 및 PC 산출물은 STATION_RETURN_REAL_PC_20261028.md 마지막 절.


### 2026-10-30 실물 스테이션 라이다 도킹 PC 구현
사용자 “ㄱㄱ” 승인으로 기존 공통 벽 관측/제어를 기본 OFF 스테이션 모드로 확장하고 실물 복귀 FSM에 도킹 단계를 연결했다. 20261029_185143_427562432 측정 자세(실측 뒤22/좌25.4/우24.6cm)를 사용한다. 기존 인계 파일/설정·sim/ 및 로봇은 이번에 수정하지 않았다. 기본 launch는 도킹 미선택, 명시 docking_config 인자로만 조립된다. 도착 허용치3종은 null 미확정이며 임의 운영값을 넣지 않았다. PC 별도 빌드/CTest2(90폐루프 포함)/Python98/기록295프레임/격리 Nav2 수렴·충돌·취소 검증. 실물 저속 응답과 도킹 정확도 미검증, 로봇 배포/재기동·commit/push 없음. 상세 파일/검증 한계/원복: docs/changes/STATION_DOCKING_PC_20261030.md.


### 2026-10-30 도킹 완료 허용치 승인 반영
사용자 “오케이 일단 그렇게 해보자”에 따라 실물 도킹 선택 설정의 앞뒤/좌우 허용치를 각각 0.005m, 방향 허용치를 0.017453292519943295rad(1도)로 확정했다. 정지 속도와 0.5초 유지 조건은 기존값을 유지한다. 이전 절의 null/미확정은 당시 기록이며 현재 설정은 확정값이다. 도킹 미선택 기본 실행은 유지한다. 이번 수정은 설정·해당 시험·문서만이며 기존 인계·sim/·주행 제어 코드는 변경하지 않았다. 로봇 배포/재기동·commit/push/원격 조회 없음.


2026-10-30 확정 허용치 PC 재시험: 실제 Nav2/가상 센서로 정상17.44초·오차36.19초 완료, 충돌106·취소 정지 확인. 관측 단절은 정지 후 진행 없음105로 실패하여 대기 시계 연결 누락 재현. Python47/CTest2 통과. 로봇 미적용. 상세 STATION_DOCKING_PC_20261030.md 최신절.


2026-10-30 사용자 승인으로 실물 도킹 관측 대기를 기존 PauseClock/WaitingProgressChecker/Nav2Client 실행 시계에 연결했다. 새 정지 조건 없음. PC 15초 관측 단절 후 같은 Goal로 재개·완료32.27초, 대기 중 취소·정상 접근 확인, Python48 통과. 기존 인계/공통 C++/sim 미변경, 로봇 미배포. 상세 STATION_DOCKING_PC_20261030.md 최신절.


2026-10-30 사용자 승인으로 station_docking_20261030 로봇 격리 배포 완료. 기존 station_work_curvature underlay 유지, ARM4패키지 빌드/CTest2/설정·설치 경로·manifest154 검증 통과. 팔 수신 생략true. 기존 실행본/인계/시뮬 미변경, 재기동·주행 미수행. 사용자 run.bash→실제14번 배치 때만dinit→record.bash→미니관제복귀. 18도착 후 도킹 자동 연결, 별도 도킹만 요청은 없음. 상세 STATION_DOCKING_PC_20261030.md 최신절.


2026-10-30 18:53 첫 도킹 실기: 새release/설정/서버 정상선택,18도착 후 오른쪽 벽 지지율 부족으로 목표 생성 실패,60초 준비 후RETURN_FAILED. PC 기록634프레임 뒤/좌 모두통과·우0,우 후보지지율 중앙73.9%(기준80%). 도킹속도출력없음. 임의완화/코드변경없음. 상세 STATION_DOCKING_PC_20261030.md 최신절.


2026-10-30 사용자 승인으로 PC 도킹 기준을 뒤+왼쪽 두 벽으로 선택하도록 수정. 공통 선택 미지정은 기존 세 벽 유지, 인계/sim 및 충돌/허용치 불변. 실물기록634중 초기4 제외630개 목표생성·오류0, Python82 통과. 아직 로봇에는 미배포(현재로봇은세벽). 상세 STATION_DOCKING_PC_20261030.md 최신절.


2026-10-30 두 벽 수정본 로봇 격리배포 완료: station_docking_two_wall_20261030, ARM4패키지빌드44초/CTest2/설치기하·설정·manifest155 확인. 기존세벽실행본 보존,재기동/주행 미수행. 실제14번배치때만dinit→새record.bash→미니관제복귀. 현재18번이면14초기좌표 보내지않음. 실기미검증. 상세 STATION_DOCKING_PC_20261030.md 최신절.


2026-10-30 19:40:34 두 벽 도킹 실물 첫SUCCESS/docked=true 수신 확인. station_docking_two_wall_20261030, 도킹약15.9초, 정지후 라이다 추정오차0.576mm/0.168mm/0.287도 accepted=true. 실제 외곽간격/반복성은별도. 팔상태생략시험으로팔준비·전체수확성공아님. 상세 STATION_DOCKING_PC_20261030.md 최신절.
