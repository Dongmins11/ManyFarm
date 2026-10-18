# 시뮬레이션 인계: 공통 수확·인계·팔 통신 — 2026-10-18

## 전달 목적과 코드 기준

실물 담당이 추가한 수확량 집계·팔 연결·제자리 인계 회전·배출 Action을 시뮬에서도 같은 공통 코드로 사용하기 위한 인계다. 별도 실물 미션 복사본을 시뮬에 만들지 않는다.

- 저장소 Robot3FinalProject/main, 작업 feat/harvest-handoff-real-20261018.
- 통합 fb5c61a644521518ecd967f4b7014f5a2aaff7cc를 포함하는 작업 기준8466ac1b01c0cae08c52bbd87ded54eeec57e13d 위에1~5단계 변경을 전달한다.
- 조회한 main은2a397da842300823cec077210ac7857024a6f66a. 전달 코드는 main에 자동 병합하지 않는다.
- 전달 ZIP의 base_to_final.patch는8466ac1 기준 전체 증분이다. 1단계부터 개별 ZIP을 순차 적용할 필요가 없다. 반대로 이미 일부 단계가 적용된 작업본에 전체 패치를 재적용하면 안 된다.
- 변경 파일 스냅샷은 code/ 아래에 있으며 검토용이다. 기존 저장소에 덮어쓰지 않는다. 새/기존 파일 모두 manifest에 SHA-256을 기록한다.
- 작성 시점 은비 PC의 변경은 미커밋 상태였다. 커밋 도구 실행 후 생성되는 최종 전달 ZIP의 COMMIT.txt가 실제 커밋 근거다. 작성 환경의 임시 Git 해시는 원격 프로젝트 커밋이 아니다.

## 공통 구현과 환경별 책임

| 대상 | 공통 구현 | 시뮬 담당 작업 |
|---|---|---|
| 수확량 | harvest_load.py가 성공 증가분만 누적, 기존 transfer_required 판단에 연결 | 시뮬 작업량에 맞는 request_count/capacity_count 설정 합의 |
| 팔 수확 | arm_client/mission/communication이 좌표 전체 완료까지 주행 차단 | 기존 시뮬 팔 서버와의 연결 확인, 과실별 성공·실패 Feedback 계약 정합 |
| 인계 | 기존 TransferMission/ActionHandoff의 배타 실행·관제 이벤트 순서 유지 | DOCK_STABLE/TRANSPORT_CLEAR를 시뮬 관제 흐름과 연결 |
| 회전 | farm_navigation SpinClient + transfer_rotation, 지정 상대각과 반대각 | 시뮬 Spin 주소·각도·제한시간·오차 허용값을 해당 환경 설정에 명시 |
| 배출 | DischargeClient/DischargeDevices/DischargeEvidence | 같은 Discharge Action을 제공하는 시뮬 장치 서버 구현/연결 |
| 준비·정지 | 명시 장치 서비스 응답으로 확인 | 시뮬 장치의 준비 및 실제 시뮬 동작 정지 완료와 연결 |

robot/ros_ws/src 아래에 있다는 이유로 실물 전용 코드라고 해석하지 않는다. 시뮬 장치 구현/프로파일은 sim/ 아래에 두고, 업무 흐름은 공통 모듈을 그대로 사용한다. 다른 로봇의 기존 작업 흐름은 바꾸지 않았다.

## 업무 순서와 보존할 의미

1. 현재 좌표의 수확 가능한 대상 전체를 한 팔 작업 단위로 처리한다. 과실 하나가 끝난 것과 좌표 전체 완료를 구분한다.
2. 매 과실 시도에서 성공·실패 모두 Feedback이 필요하며 성공량만 적재량으로 집계한다. 기존 내부 클라이언트는 누적 수량 증가분을 반영한다. 개별 시도 보고를 보장하려면 서버에서도 시도마다 Feedback을 보내야 한다.
3. 호출 임계량에 도달하면 기존 Status의 transfer_required로 관제에 알리면서 수확을 계속한다. 수확→운송 직접 호출 Action을 추가하지 않는다.
4. 관제는 다음 좌표 작업을 보류하고 현재 좌표 전체 수확이 종료된 뒤 DockTransfer를 요청한다. 수확 진행 중 인계 요청 거절 정책은 그대로다.
5. 준비·제자리 회전·정지 후 DOCK_READY, DOCK_STABLE 수신 후 배출 Action 한 번.
6. 열기·배출·닫기 전체 성공 Result 후 TRANSFER_COMPLETE. TRANSPORT_CLEAR 전에는 복원하지 않는다.
7. 복원 때 닫기 재요청 없이 성공 증거를 확인하고 반대 상대각 Spin. 원래 방향을 향해 주행하면서 맞추거나 추가 보정 회전을 하지 않는다.
8. 복원까지 정상 완료한 뒤 적재량 초기화. 실패하면 적재량/복구 차단 보존.

실물 확정 배치는 준비 왼쪽90도, 복원 오른쪽90도다. 시뮬 장치 배치가 다르면 회전 설정의 적합성을 담당자와 확인한다. 실물 좌표/지도/태그값을 시뮬에 복사하지 않는다.

## 배출 Action 규격

타입 farm_interfaces/action/Discharge. 정의 원본 robot/ros_ws/src/farm_interfaces/action/Discharge.action.

| 구간 | 필드 | 타입 |
|---|---|---|
| Goal | transfer_id | string |
| Feedback | phase | string |
| Result | transfer_id | string |
| Result | error_codes | string[] |
| Result | error_message | string |

phase: OPENING, DISCHARGING, CLOSING. Result ID는 Goal 그대로 반환.
정상: Action SUCCEEDED + error_codes=[]. 전체 열기·배출·닫기 완료가 정상이다.
오류: OPEN_FAILED, DISCHARGE_FAILED, CLOSE_FAILED, INTERNAL_ERROR. 배출·닫기 동시 실패는 두 코드 모두 전달. NONE 원소나 별도 discharge_complete/closed bool을 사용하지 않는다.

Feedback/접수만으로 완료하지 않는다. 시뮬 장치의 실제 동작 완료에 Result를 연결해야 한다. 시험 도구의 일정 시간 후 성공 응답을 시뮬 동작 완료 검증으로 대신하지 않는다. 실패/취소/미수신에 오류 코드가 없다고 물리 상태를 추정하지 않는다.

상세 규격 및 역할은 JETSON_ARM_COMMUNICATION_HANDOFF_20261018.md도 참고할 수 있다. Jetson 모터 역할에 해당하는 부분은 시뮬 장치가 담당한다. Jetson의 실제 감지 방식과 AI 사용은 보류 상태이며 시뮬에 동일 센서 알고리즘을 강제하지 않는다.

## 환경 설정과 현재 비활성 상태

시뮬 설정: sim/ros_ws/src/farm_sim_config/config/harvest_task.json.
현재 전달본은 적재량 입력 arm_feedback, request_count=0이며 실제 호출 임계값을 확정하지 않았다. request_count가 양수면 개수 기준, 0이면 capacity_count의80% 기준, 둘 다0이면 호출 판단 OFF다. 실물에서 적게 시연하려는 수량을 시뮬 기준으로 복사하지 않는다.

새 배출 방식 활성화에는 다음 항목이 필요하다. 운영값은 이 문서에서 임의 지정하지 않는다.
- transfer.enabled와 기존 관제/복구 설정 확인.
- rotation_mode=nav2_spin, 기존 rotation 객체의 endpoint/angle_rad/time_allowance_s/position_tolerance_m/yaw_tolerance_rad 명시.
- discharge_mode=action, discharge_action의 endpoint/response_timeout_s/cancel_timeout_s 명시.
- device_services에는 prepare_arm/stop 두 실제 시뮬 서비스 주소. 빈 매핑이면 수락하지 않는다.
- 수확 완료 정책/팔 endpoint는 기존 시뮬 설정을 대조하고 필요한 범위만 조정.

전달본은 시뮬 인계 OFF와 기존 운영 설정을 보존한다. 기존 서비스 방식 device_services는 기본으로 유지한다. 새 방식을 선택하지 않은 환경은 기존 흐름을 사용한다. PC ROS 시험의 /test_only 주소와 허용값을 시뮬 운영값으로 복사하지 않는다.

## 검증 결과와 시뮬 담당 확인 항목

은비 PC 2026-10-18 제공 로그: 오프라인57개 PASS, farm_interfaces 빌드 성공, PC 실제 ROS Action 정상/복수오류/거절/취소4개 PASS. 로그 /home/eunbi/harvest_stage5_ros_zdqlxg/ros_smoke.log. 이 수치는 이번 변경 관련 묶음이며 전체 저장소 테스트가 아니다.

미검증: Isaac 장치 연동, 시뮬 전체 미션, 전체 로봇 ROS 빌드, Jetson·Zenoh 기기간 통신, 실제 로봇 구동.
시뮬에서는 변경 영향에 맞춰 다음을 확인한다.
- 과실별 성공/실패 보고와 성공량 집계, 호출 뒤에도 현재 좌표 수확 지속.
- 좌표 전체 완료 뒤 인계, 정상 단일 배출 요청과 이격 후 반대각 복원.
- 배출/닫기 실패 및 취소/연결 손실 시 완료·주행 차단, 수량 보존.
- 정상 인계 복원 완료 후 수량 초기화, 다음 작업 재개.
- 기존 장치 방식과 공유 주행·태그 설정 회귀는 실제 변경한 범위만 검사.

prepare_arm은 새로운 접힘 명령을 설계한 것이 아니다. 정상 시작/완료는 접힌 자세라는 합의를 유지하며 실제 시뮬 준비 확인과 연결한다. stop 성공은 실제 시뮬 동작 정지를 뜻해야 한다. Action 취소 ACK/terminal과 물리 정지 확인은 구분한다.

## 코드 인수 방법

권장: 최종 커밋 전달 ZIP의 Git bundle을 별도 검토 브랜치/작업트리로 받아 검토한다. bundle은8466ac1을 선행 조건으로 가지므로 수신 저장소에 이 커밋이 필요하다. 원격 작업 브랜치 fetch로 가져오되 자신의 작업 브랜치를 강제로 전환/초기화하지 않는다.

은비 PC 커밋 도구가 만드는 README에 실제 commit hash와 fetch/worktree 명령을 기록한다. 변경 전 AGENTS와 현재 main/통합/작업 브랜치 후속 변경, 미커밋 파일을 확인한다. main 또는 후속 시뮬 코드에 바로 덮어쓰거나 무조건8466ac1로 되돌리지 않는다. 이후 병합에서 충돌하면 설정·업무 의미를 대조해 해결한다.

대안: base_to_final.patch를8466ac1 기반 별도 깨끗한 작업트리에서 git apply --check 후 적용한다. ZIP의 code/는 검토용 파일 스냅샷이며 전체 실행 저장소가 아니다. Git bundle/patch는 기존 지도·모델 LFS 객체까지 새로 전달하는 것이 아니다.

추가 합의: 수확량 측정 방법/시뮬 호출 기준, Jetson 최종 수확 Action 형식, 팔 Status Topic, 취소·정지·복구 계약. 이번 전달이 해당 미정 사항까지 구현 완료했다는 뜻은 아니다.
