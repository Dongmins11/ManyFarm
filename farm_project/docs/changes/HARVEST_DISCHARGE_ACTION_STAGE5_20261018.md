# 공통 배출 Action 연결 5단계 — 2026-10-18

## 승인과 기준

사용자가4단계 오류 배열 패치 PC 적용 및15개 PASS를 전달한 뒤 실제 Action 연결 진행 승인. 기준8466ac1 + 적용1~4단계이며 GitHub 작업8466ac1/통합fb5c61a/main2a397da 후속 변경 없음 확인. 로봇 배포 승인과 구분한다.

## 변경 파일과 책임

| 파일 | 변경 |
|---|---|
| farm_interfaces/action/Discharge.action | 단일 열기→배출→닫기 계약, 확정 Goal/Feedback/Result |
| farm_interfaces/CMakeLists.txt | 새 Action 생성 등록; 기존 형식 유지 |
| harvest_robot/discharge_client.py | start/poll, 서버·Goal 승인·terminal·결과 검증, 현재 phase 수신, 자신의 요청 취소 및 늦은 승인 회수 |
| harvest_robot/discharge_devices.py | prepare_arm/stop 서비스와 배출 Action 조합; 복원은 성공 증거 확인만 수행 |
| harvest_robot/configuration.py | 명시 방식/주소/응답·취소 제한시간 검증 및 ROS 파라미터 변환 |
| harvest_robot/transfer_communication.py | 공통 어댑터 조립, 새 인계마다 관제 transfer_id로 증거 초기화 |
| harvest_robot/test/test_discharge_client.py | Future 대역 + 실제 공통 관제 연결 시험12개 |
| robot/tools/discharge/ros_discharge_smoke.py | PC 전용 실제 ROS 서버·클라이언트 송수신4개 시나리오, 모터 없음 |
| robot/tools/discharge/run_ros_discharge_smoke.bash | Jazzy/별도 인터페이스 빌드/CycloneDDS77 LOCALHOST 적용 |
| PROJECT_STATE/DECISIONS/sim CHANGELOG/본 문서 | 승인·현재 상태·검증 한계 |

실제 경로는 robot/ros_ws/src 아래 각 패키지다. 공통 TransferMission/회전 정책은 복제하거나 수정하지 않았다. 다른 로봇의 기존 인터페이스도 변경하지 않는다. farm_interfaces 의존성과 런치 transfer_parameters 전달이 기존에 있어 package.xml/launch 변경은 불필요하다.

## 현재 wire 계약

Goal: string transfer_id. Feedback: string phase(OPENING/DISCHARGING/CLOSING).
Result: string transfer_id, string[] error_codes, string error_message.
전체 성공: 현재 인계 ID 일치 + Action SUCCEEDED + error_codes=[]. 오류 없음에 NONE 원소를 사용하지 않는다.
오류: OPEN_FAILED, DISCHARGE_FAILED, CLOSE_FAILED, INTERNAL_ERROR. 복수 실패는 모두 전달. 취소/통신 단절/실패 상태에서는 빈 배열을 개별 동작 성공 증거로 해석하지 않는다.

phase는 클라이언트의 현재 phase 및 선택적 콜백에 보관한다. 기존 관제 DockTransfer Feedback은 DOCK_READY/TRANSFER_COMPLETE를 그대로 사용하며 새 필드를 임의 추가하지 않는다. 오류 배열은 기존 DeviceResult.detail과 관제 error_message로 원문 전달되고 관제 상위 error_code는 기존 DEVICE_FAILED/STOP_UNCONFIRMED 등의 체계를 유지한다.

## 설정 선택과 미설정 경계

기존 discharge_mode=device_services가 기본이다. 새 방식은 transfer에서 discharge_mode=action, rotation_mode=nav2_spin을 명시하고 discharge_action에 endpoint/response_timeout_s/cancel_timeout_s를 모두 지정한다. 기존 rotation 설정도 모두 필요하다.
새 방식 device_services 키는 prepare_arm과 stop 두 개다. 주소는 현장 확인 후 넣는다. 기존 전체 Trigger 방식과3단계4개 서비스 방식은 그대로 보존한다. 실물/시뮬 프로파일에는 새 설정을 넣지 않았다.

prepare_arm은 현재 준비 확인 확장 지점이지 새 접힘 명령을 설계한 것이 아니다. stop은 물리 정지 완료 확인이 필요하다. 둘 다 미설정이면 인계를 수락하지 않는다. 실물에서 이미 검증한 주행·태그가 미완료라는 뜻이 아니다.

장치 Action 내부 감지/AI 여부는 보류. 취소 후 젯슨이 닫을지 멈출지도 임의 가정하지 않는다. 클라이언트는 자신의 Goal 취소를 요청하고 terminal을 기다리지만 이 사실을 물리 정지 확인으로 사용하지 않는다. 별도 stop 응답까지 성공해야 정지 확인이 된다. Action 취소 실패여도 stop 요청은 시도하며 자동 재요청/복원 없음. 종료 미확인은 공통 저널 복구 차단으로 이어진다.

## 검증

직접 실행한 오프라인 시험57개:
- test_discharge_client.py 12: Feedback은 완료 아님, 단일 요청, 복수 오류, 거절/서버 없음, 승인 지연 시간초과 후 취소, ACK만 있고 terminal 없음, 전송 예외, 이전 응답, stop 시도, 설정 검증, 실제 TransferCommunication 성공/실패 연결.
- test_discharge_result.py 15: 빈 오류 배열 계약, 모순된 응답, 취소/시간초과, 공통 미션/회전.
- test_transfer_rotation.py 12: 기존 제자리 회전 연결 회귀.
- test_harvest_load.py 18: 기존 서비스 방식/적재량/관제 연결 회귀.
Python compile 및 Bash 구문 검사 통과. 동일 시험을 여러 번 실행한 횟수는 합산하지 않는다.

이번 환경에는 rclpy가 없어 ROS 빌드 및 실제 송수신을 실행하지 못했다. PC에 제공하는 smoke는 다음4개를 실행한다: 정상, 배출·닫기 동시 실패, Goal 거절, 취소. 시험 서버는 고유 /test_only/discharge_<uuid> 주소를 사용하며 운영 endpoint를 입력받지 않는다. 실제 Action 메시지를 사용하지만 모터/수확/주행/관제 서버를 호출하지 않는다. 취소 응답은 시험 서버의 모의 동작일 뿐 젯슨 물리 계약이 아니다.

run_ros_discharge_smoke.bash는 /home/eunbi/harvest_stage5_ros_XXXXXX 아래 별도 build/install/log에 farm_interfaces만 빌드한다. 기존 robot/ros_ws/install은 변경하지 않는다. PC 내부 노드끼리 통신하므로 이 시험만을 위해 Zenoh 브리지를 추가로 켤 필요는 없다. 이 결과는 Zenoh 기기간 검증이 아니다.

## 적용/남은 작업

직전4단계 errors 패치까지 적용된 PC에서5단계 증분 패치 적용 후 verify_stage5.bash 실행. 이어서 PC 새 터미널에서 bash /home/eunbi/vmany/main/farm_project/robot/tools/discharge/run_ros_discharge_smoke.bash 실행. 필요한 source/unset/export는 스크립트에 포함한다.
사용자 2026-10-18 17:47 KST 제공 로그로 이번 패치 PC 적용 및 ROS 시험 통과를 확인했다. Jetson·Isaac·실물 시험, 공통 통합 코드의 로봇 배포, 운영 주소/시간/준비·정지 서비스 확인은 남아 있다. commit/push 없음. 되돌림은 이번 증분 패치만 git apply -R --check 후 -R; 운영 설치에서 사용했다면 호환 버전으로 다시 빌드한다. 기존 패치와 현장 설정을 덮어쓰지 않는다.


## 사용자 PC 검증 결과 확인 — 2026-10-18 17:47 KST

- 작업 브랜치 feat/harvest-handoff-real-20261018에서 패치 적용 및 diff 검사 성공.
- 오프라인12+15+12+18=57개 PASS. 이전 작성 환경 시험과 중복 합산하지 않는다.
- farm_interfaces 1개 패키지 빌드 성공(제공 출력: 패키지13.3초, 전체13.5초).
- 실제 ROS Action 송수신: mock-success/mock-errors/mock-reject/mock-cancel 모두 PASS.
- PC 실행 로그 경로: /home/eunbi/harvest_stage5_ros_zdqlxg/ros_smoke.log. 파일 자체를 원격 열람한 것이 아니라 사용자가 제공한 터미널 출력을 근거로 기록한다.
- 확인 범위는 PC 로컬 서버·클라이언트 간 실제 ROS 통신이며 물리 장치는 모의다. Jetson과의 기기간 통신·Zenoh 연결, 전체 수확 서버 빌드, 실물 모터·센서·정지는 확인하지 않았다.
- 사용자 PC 변경은 미커밋 상태. GitHub 원격 반영과 로봇 배포는 미수행.

담당자 전달 문서: ../JETSON_ARM_COMMUNICATION_HANDOFF_20261018.md. 문서만 갱신했으므로 코드 시험을 반복하지 않는다.
