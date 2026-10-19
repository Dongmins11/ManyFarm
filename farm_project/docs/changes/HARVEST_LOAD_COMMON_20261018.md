# 공통 수확 성공량 누적과 운송 호출 상태 연결 — 2026-10-18

## 기준·승인
- 기준 원격: feat/harvest-handoff-real-20261018, 8466ac1b01c0cae08c52bbd87ded54eeec57e13d.
- integration fb5c61a / main 2a397da 후속 변경 없음 확인.
- 사용자 승인: 단계별 계획 제시 후 “1단계 부터 진행하자”.
- PC·로봇에 직접 접근하지 못했다. 원격에서 필요한 파일만 받은 별도 부분 작업본에서 구현했다. 원격 commit/push 및 사용자 PC·로봇 적용은 수행하지 않았다.

## 동작
- 공통 HarvestLoad는 좌표별 Action 누적 성공값의 증가분만 전체 적재량에 더한다.
- 실패 수량은 기존 관제 Feedback/Result에 보존하지만 적재량에는 더하지 않는다.
- 다음 좌표 시작은 작업별 수량만 초기화한다. 부분 성공 후 취소/실패도 확정 수량을 유지한다.
- 최종 Result는 기존 ArmActionClient의 progress 콜백을 통해 반영된다. 같은 누적값은 중복 합산하지 않는다.
- transfer.load_source=arm_feedback이면 집계값을 기존 loaded_count/transfer_required에 연결한다.
- load_source 미지정은 external_topic으로 기존 입력을 보존한다. arm_feedback과 loaded_count_topic의 동시 설정은 거부한다.
- request_count가 양수면 해당 개수에서 호출 필요 상태를 설정한다. 0이면 기존 capacity_count의 ceil(80%)를 사용한다. 둘 다 0이면 호출 판단을 비활성화한다.
- 호출 필요 상태는 수확을 중단하거나 새 Action을 보내지 않는다. 기존 Status로 관제에 보고한다.
- 관제는 현재 좌표 수확 완료 후 DockTransfer를 보낸다. 수확 중 인계 Goal 거절과 ActionHandoff는 유지한다.
- 기존 물리 인계 완료 경계(transfer_complete, restore_complete, recovery_required=false)에서 집계와 호출 상태를 초기화한다. 열기 응답만으로 초기화하지 않는다.

## 파일별 변경
- harvest_robot/harvest_load.py: ROS 독립 집계 모듈.
- harvest_robot/node.py: 공통 집계 인스턴스 생성.
- harvest_robot/communication.py: 실행 시작/종료와 성공·실패 수량 연결. 관제 형식 유지.
- harvest_robot/configuration.py: load_source/request_count 검증 및 ROS 파라미터 변환.
- harvest_robot/transfer_communication.py: 입력 방식 선택, 호출 기준, 물리 인계 완료 초기화 연결.
- robot/config/harvest/harvest_real.json 및 sim/.../config/harvest_task.json: arm_feedback 입력 선택. request_count=0으로 운영 임계값 미확정 유지.
- harvest_robot/test/test_harvest_load.py: 집계·호출·기존 인계 실행 경계 검사.
- sim/tests/test_harvest_arm_client.py: 기존 통신 fixture에 집계를 연결하고 성공/실패/취소 수량 보존 검사.

## 검증
부분 작업본에서 아래 두 묶음 29개 통과. ROS/장치 I/O는 대역이다.
- test_harvest_load.py: 18개. 연속 좌표, 실패 제외, 중복, 역행/범위, 입력 선택, 임계값 및 비활성 기준, 정상 인계 초기화, 실패/취소 보존과 기존 실행 권한 보호.
- test_harvest_arm_client.py: 11개. 기존 팔 클라이언트/미션/통신 결과 전달 및 이번 집계 연결.
- git diff --check 통과.
- ROS 빌드·Isaac·실제 Jetson·관제 수신·실물 인계 미실행. 기존 133개 전체 시험은 반복하지 않았다.

## 설정과 남은 확인
- 실물 completion_policy=ARRIVAL_ONLY_NO_HARVEST 유지. 팔 활성화는 2단계다.
- 시뮬의 transfer.enabled 미설정(OFF) 유지. 수확 집계는 수행하지만 인계 서버/호출 Status 경로는 해당 기능을 켜는 후속 연동에서 확인한다.
- 두 환경의 운영 호출 개수는 미정이다. 시험의 3개/용량10개는 테스트 입력이며 운영 설정에 반영하지 않았다.
- 이 단계의 누적량은 프로세스 메모리에 유지한다. 재시작 후 박스에 남은 수확량을 자동 복구하는 기능은 구현하지 않았다. 적재 상태 재동기화는 별도 예외·재시작 정책으로 결정해야 한다.
- Nav2·지도·태그·CycloneDDS/Zenoh·Action 메시지·인계 물리 동작은 변경하지 않았다.
- 관련 계약: Confluence 수확↔운송 인계 통신구조 16908315, 수확 프로토콜 4358169, 10/14 구현 기록 38731796.

## 적용·되돌림
제공 패치는 8466ac1의 변경 파일에 git apply --check 후 적용한다. 전체 파일 덮어쓰기를 하지 않는다.
되돌릴 때도 git apply -R --check로 이번 패치만 역적용 가능한지 확인한다. 로봇 배포나 실제 동작 명령은 별도 단계다.
