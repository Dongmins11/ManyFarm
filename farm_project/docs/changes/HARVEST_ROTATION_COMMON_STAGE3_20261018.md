# 공통 인계 제자리 회전 3단계 — 2026-10-18

## 승인과 기준

사용자는 파일별 제안 후 복원도 반대각도의 제자리 회전으로 수행하고, 오차가 남으면 이동/추가 회전 보정 없이 실패 처리하는 방식을 승인했다. 준비는 왼쪽90도, 복원은 오른쪽90도다. 범위는 PC 코드와 모의 시험이며 로봇 배포/실제 구동 승인이 아니다.

기준: feat/harvest-handoff-real-20261018 /8466ac1 + 적용 완료된1·2단계. 사용자 PC의2단계43개 통과 로그 확인. 작업 환경은 원격 원본과 대조한 부분 작업본이다. 로봇 현재 파일/설치는 직접 확인하지 않았다. main2a397da, 통합fb5c61a, 작업8466ac1 기준 유지.

## 파일과 책임

경로는 farm_project/ 기준이다.

| 파일 | 변경 |
|---|---|
| robot/ros_ws/src/farm_navigation/farm_navigation/spin_client.py 신규 | Nav2 Spin 상대각 Goal, 제한시간, 승인/결과 확인 및 자신의 지연 승인 Goal 취소. Harvest 전용 업무를 알지 않음 |
| robot/ros_ws/src/harvest_robot/harvest_robot/transfer_rotation.py 신규 | 차체 Spin과 비차체 장치 어댑터 조합. 원래 위치·방향 기록, 정/역회전, 위치 이탈·최종 방향·정지 확인. 실패 시 보정 이동 없음 |
| 위 패키지의 transfer_devices.py | 기본5개 서비스 매핑 유지. 새 조합에서는 비차체4개 동작 매핑을 명시 선택 |
| 위 패키지의 transfer_communication.py | 기존 서비스 방식/공통 Spin 방식 설정 선택. 기존 인계 미션·저널·소유권 연결 유지 |
| 위 패키지의 configuration.py | 회전 방식/필수값 검증 및 기존 런치 경로에 ROS 파라미터 전달 |
| 위 패키지의 node.py | 기존 NavigationSettings를 인계 조립에 전달 |
| farm_navigation/test/test_spin_client.py 신규 | 승인·충돌 실패·늦은 승인·취소 ACK/terminal 구분 등7개 |
| harvest_robot/test/test_transfer_rotation.py 신규 | 정/역회전·정지·오차·운송 이벤트·장치 복원·실제 공통 통신 조립 등12개 |

문서: PROJECT_STATE §73/74, DECISIONS D-043, sim/docs/CHANGELOG 및 이 문서. 총12개 파일. 기존 Nav2Client/TransferMission/공통 ActionHandoff 구현은 변경하지 않는다.

## 연결과 순서

기존 인계 순서: prepare_arm → rotate_to_transfer → DOCK_READY → DOCK_STABLE → discharge → TRANSFER_COMPLETE → TRANSPORT_CLEAR → restore.

새 어댑터도 같은 순서를 따른다. 준비 회전 직전에 기존 MotionMonitor로 정지를 확인하고 PoseProvider로 map 기준 위치·방향을 기록한다. 준비 회전은 +angle_rad, 복원 회전은 -angle_rad를 단 한 번씩 보낸다. 복원 Goal은 오차를 역산한 보정각이 아니다. 기록한 원래 방향은 마지막 검증에만 사용한다.

- Spin 성공 이후에도 정지와 최종 방향/위치 검사를 통과해야 단계 완료다.
- 회전 대기 중 최신 위치를 조회하여 허용 위치 이탈 시 중단한다. 실제 swept footprint/충돌 판단은 Nav2가 담당한다.
- TRANSPORT_CLEAR 이후 비차체 restore_devices 성공을 먼저 확인하고 반대 회전을 수행한다. 게이트/팔 복원 실패 시 차체를 돌리지 않는다.
- 실패/취소 시 자신의 Spin 취소·terminal, 실제 정지, 장치 stop을 모두 확인한다. 확인 실패를 성공으로 바꾸지 않는다. 재시도/복원 회전/이동 보정은 하지 않는다.
- 기존 실패 저널과 blocked를 유지한다. 회전 도중 프로세스가 종료되면 저장된 인계 미완료 기록으로 자동 재개를 막는다. 원래 방향은 메모리에만 있으며 재시작 자동 복원 기능이 아니다.

## 설정 선택: 운영값 미입력

기존 설정은 변경하지 않았다. 기본 transfer.rotation_mode는 device_services이며 원래5개 Trigger 매핑을 사용한다. 실제 실물/시뮬 프로파일에서 새 회전은 활성화하지 않았다.

nav2_spin 선택 시 transfer.rotation에 다음 항목을 모두 명시해야 한다.

| 키 | 의미 |
|---|---|
| endpoint | 실제 실행 환경에서 확인할 Nav2 Spin Action 주소. 자동 추정하지 않음 |
| angle_rad | 준비 회전 양수 상대각(rad). 사용자 합의90도=pi/2; 복원에는 코드가 정확히 음수를 사용 |
| time_allowance_s | Spin에 전달할 제한시간. 운영값 미확정 |
| position_tolerance_m | 원래 위치에서 허용할 최대 평면 이탈. 운영값 미확정 |
| yaw_tolerance_rad | 준비/복원 후 허용 방향 오차. 운영값 미확정 |

ROS 파라미터는 transfer_rotation_mode 및 JSON 문자열 transfer_rotation이다. 공통 harvest.launch.py가 기존 transfer_parameters를 통해 전달하므로 별도 런치 복사본은 없다. 기존 NavigationSettings의 응답/취소 제한과 위치/정지 관측 설정을 재사용한다. 속도·가속도는 기존 Nav2 behavior_server가 담당하며 이번 패치는 변경하지 않는다.

새 방식의 device_services 키는 prepare_arm/discharge/restore_devices/stop이다. restore_devices는 차체 회전이 포함되지 않은 게이트·팔 등 장치 복원 연결 지점이다. 기존 restore 서비스(차체 복원까지 포함)를 그대로 재사용하면 중복 회전할 수 있으므로 기존5개 매핑을 새 방식에 넣으면 거절한다. 실제 서비스 이름이나 완료 조건을 새로 확정한 것이 아니며 담당자 확인 후 연결해야 한다. 매핑이 비어 있으면 인계 Goal을 계속 거절한다.

팔/박스 Action 규격 확정 후 비차체 장치 어댑터를 교체한다. prepare_arm/배출 준비/적재함 닫힘을 가짜 성공으로 대신하지 않는다. 박스 open 성공과 실제 배출 완료는 동일하지 않다.

## 검증

오프라인 총62개 PASS: Spin7 + 회전/통신 조합12 + 기존 집계/인계18 + 팔 연결6 + Status8 + 팔 클라이언트/관제 전달11. 테스트의 test_only 주소와 허용값은 시험 fixture 전용이다.

검증 사항: 정확한 정/역각, Action 거절·충돌 오류, 늦게 승인된 자신의 Goal 취소, 다른 Goal ACK 거절, ACK만 있고 terminal 없는 상황, 오래된 odom 대역, 위치·방향 오차, 장치 복원 실패, 이격 이벤트 전 복원 안 함, 회전 실패 시 DOCK_READY 안 함, 미설정 장치 Goal 거절. 기존 서비스 기반 흐름과 적재량 초기화도 유지 확인.

구문/git diff --check 및2단계 상태에 증분 패치 적용 검사·파일 일치 확인. 실제 ROS/colcon/Isaac/Jetson/모터/관제 네트워크 시험은 수행하지 않았다. 시간 제한은 PC 어댑터의 monotonic 상한을 사용하므로 시뮬 일시정지가 길어지면 실패 처리된다. 이는 실제 시뮬 통합 검증 대상이다.

참고한 Jazzy Spin 형식: https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_msgs/action/Spin.action (10/18 조회, blob91288cbf20507ed81c17aed6e042caf4153dd88c). target_yaw/time_allowance와 error_code를 사용한다. 충돌 검사 무시 필드를 만들거나 임의 cmd_vel을 발행하지 않는다.

## 남은 실물 확인과 복원

로봇은 공통 구조 통합 전일 수 있다. 배포 전 현재 브랜치/미커밋/실행 설정을 백업·대조하고 전체 통합본 빌드부터 별도 검증한다. 실제 Spin 주소, behavior_server 활성 상태와 cmd_vel 경로, 회전 속도, 협소 공간의 footprint/센서 범위, 위치·방향 허용값, 태그·TF 관측과 정지 확인을 현장에서 확인해야 한다. 기존 주행값·지도·태그·CycloneDDS/Domain77/LOCALHOST/Zenoh 설정은 보존한다.

현재 사용자 PC 적용 전/원격 미반영. 복원은3단계 패치만 git apply --reverse --check 후 역적용한다.1·2단계와 기존 사용자 변경을 reset하지 않는다.
