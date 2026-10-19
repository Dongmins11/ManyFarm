# 공통 팔 Action 연결 2단계 — 2026-10-18

## 기준과 승인

사용자 “알겠어 진행해줘”: PC 공통 코드 수정 및 모의 시험. 기준 작업 브랜치 feat/harvest-handoff-real-20261018 / 8466ac1 + 적용 완료된 1단계 v2. 1단계는 사용자 PC에서29개 통과 로그 확인. 원격 main2a397da, 통합fb5c61a, 작업8466ac1은 후속 변경 없음. 작업 환경은 GitHub 원본과 대조한 부분 작업본이며 사용자 PC/로봇에 직접 접근하지 않았다.

## 파일별 변경

경로는 robot/ros_ws/src/harvest_robot 기준이다.

| 파일 | 변경 이유와 동작 |
|---|---|
| harvest_robot/arm_client.py | configured_arm_settings로 완료 정책에 따라 기존 클라이언트 설정 선택. 미설정 주소 거절. server_is_ready는 연결 조회만 수행 |
| harvest_robot/node.py | sim 전용 제한 제거. 양 환경에서 같은 클라이언트 사용. Status의 이동 전용 제한 제거. 접힘 확인 상태 초기화 |
| harvest_robot/mission.py | 도착 후 전체 Action을 기다리는 기존 흐름 유지. 팔 실행부터 정상 SUCCESS까지 이동 허용 상태 추적 |
| harvest_robot/communication.py | 결과/수량 전송 후 팔 접힘 미확인인 경우 기존 blocked를 설정. 이후 수확/인계/복귀의 기존 거절 조건 재사용 |
| harvest_robot/status.py | ARM 단계는 HARVESTING. 팔 서버 미연결은 ARM_NOT_READY, ready=false. 비정상 종료 후 접힘 미확인은 ARM_TRAVEL_NOT_READY |
| test/test_arm_connection.py | 환경 공통 설정, 미설정 거절, 개별 성공·실패 보고와 좌표 전체 완료의 구분, 실패·취소 후 이동 허용 안 함 |
| test/test_status_reporting.py | 수확 상태, 서버 미연결, 접힘 미확인 검증 추가 |
| sim/tests/test_harvest_arm_client.py (farm_project 기준) | 기존 공통 통신 시험에 실패 Feedback 전달 및 비정상 종료 차단 검증 추가 |

문서: docs/PROJECT_STATE.md §72/73, docs/DECISIONS.md D-042, sim/docs/CHANGELOG.md, 이 문서. 총12개 변경 파일.

## 설정 및 연결 경계

- 기존 실물 harvest_real.json의 ARRIVAL_ONLY_NO_HARVEST를 유지한다. 실제 팔 endpoint를 넣거나 운영 팔 실행을 활성화하지 않는다. 시뮬 프로파일도 변경하지 않는다.
- ARRIVAL_THEN_ARM 선택 시 기존 arm_action.endpoint 및 timeout 설정을 읽는다. 양 환경에서 같은 경로다. 이 연결은 현재 farm_interfaces/HarvestTask 형식 전제이며 Jetson 팀과 합의된 규격을 의미하지 않는다.
- 사용자 합의: 각 과실 시도마다 성공/실패 Feedback, 성공량만 집계. 공통 클라이언트는 받은 Feedback을 매번 전달한다. 장치가 보고하지 않은 개별 사건을 재구성하지 않는다. 실제 Jetson 발행 주기/전달 보장은 이후 검증한다.
- 한 Action은 현재 좌표 전체 수확을 담당한다. 중간 성공, 실패, 호출 임계값 달성은 Action 완료가 아니다. 기존 Result 수량 검증과 취소 ACK/terminal 대기를 유지한다.
- 정상 SUCCESS는 좌표 전체 작업 및 접힘 완료 후 발행해야 한다는 사용자 계약을 전제로 한다. 별도 접힘 센서를 읽었다는 뜻이 아니다. 시작 시 이미 접힌 자세라는 전제도 유지한다.
- 비정상 종료 후 접힘 미확인은 다음 이동을 차단한다. 서버 미응답 등 팔 실행 단계에서 정상 완료를 확인할 수 없는 경우도 보수적으로 차단한다. 자동 해제 서비스나 재시작 복구는 만들지 않았다. 프로세스 재시작으로 안전 확인을 대신해서는 안 된다.
- HARVESTING은 기존 관제 문서의 state를 사용한다: https://robot3final.atlassian.net/wiki/spaces/3/pages/4358169 (10/18 조회). Status는 관제용 로봇 상태이며 Jetson에서 받는 팔 Status Topic 구독을 구현한 것이 아니다. 팔 서버 발견은 물리적 안전 자세 증명이 아니다.

## 미확정 항목의 추가 위치

- Jetson 수확 Action 이름/형식/좌표 필드: arm_client.py 장치 연결 경계와 환경 arm_action 설정. 기존 형식과 다르면 이 경계의 어댑터로 변환하며 미션을 복사하지 않는다.
- Jetson 팔 Status Topic: 형식 합의 후 별도 장치 구독 어댑터에서 읽고 status.py의 관제 투영에 연결. 현재 데이터 필드/이름을 생성하지 않았다.
- 박스 개방 Action: transfer_devices.py의 장치 연결 확장 지점. 개방 성공과 배출 완료 판정은 분리해서 합의해야 한다. 이번 코드에 추가하지 않았다.
- 인계 회전: 후속 공통 주행 어댑터 작업. 이번에는 회전/모터 명령을 만들지 않았다.

## 검증 및 실물 확인 사항

직접 실행: PC 오프라인 총43개 PASS = test_arm_connection6 + test_status_reporting8 + test_harvest_arm_client11 + test_harvest_load18. git diff --check 통과. 1단계 적용 상태에 2단계 패치 적용 검사 및 모든 변경 파일 결과 일치 확인.

ROS 빌드, ROS 노드 기동, 실제 DDS/Zenoh 통신, Isaac 실행, Jetson 모터, 로봇 주행은 미실행이다. 모의 Future/ROS 객체와 함수 호출을 사용했다. 기존 실물 주행 검증을 이번 통합 코드 검증으로 간주하지 않는다.

로봇 적용은 별도 승인 후 현재 브랜치·미커밋·실행 설정부터 확인한다. 공통 통합 미배포 가능성을 고려해 전체 차이를 대조하며 검증된 주행값/지도/태그/CycloneDDS·Domain77·LOCALHOST/Zenoh를 보존한다. 기존 현장 시작 순서도 유지한다.

## 전달 및 복원

1단계 위에 적용하는 증분 패치다. 미커밋1단계를 유지한 채 git apply --check 후 적용한다. 원격 commit/push 없음. 되돌림은 git apply --reverse --check 후 2단계만 역적용하며 다른 변경이 있으면 먼저 대조한다.
