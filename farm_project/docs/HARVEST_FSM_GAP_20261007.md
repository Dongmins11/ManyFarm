# 수확 FSM과 현재 코드 차이 — 2026-10-07

## 확인 기준

- Confluence [수확로봇 State 설계](https://robot3final.atlassian.net/wiki/spaces/3/pages/9306124/State): v2, 2026-09-14.
- Confluence [수확로봇 통신 프로토콜](https://robot3final.atlassian.net/wiki/spaces/3/pages/4358169): v36, 2026-10-02.
- 코드: `feat/apriltag-localization` 기반 `1afa48a`, 공통 예찰 실행 구조는 main `1666a23` 참고.
- 이번 변경은 실행 통합과 부족한 부분 파악이다. 수확 FSM 전체나 팔·도킹을 가짜 완료로 구현하지 않는다.

## 현재 상태

현재 `HarvestNode → HarvestCommunication → HarvestStateController → HarvestMission → Navigator`는 **이동 전용 시험 서버**다. 실제 State는 `NavigationState`, `TerminalState` 두 개뿐이다. 목표 도착 후 `ARRIVAL_ONLY_NO_HARVEST` 정책으로 SUCCESS와 수확량 0을 반환한다. 이는 문서의 “해당 Window 수확 완료”와 다른 시험 계약이다. 관제의 실제 수확 완료 통계에 연결하면 안 된다. 이번 환경 파일과 실행 안내도 이 범위를 명시한다.

| FSM 요구 | 코드에서 확인한 구현 | 부족한 부분 / 연결 위치 |
|---|---|---|
| IDLE / 작업 수락 | Communication의 busy·blocked·stopping·ID/좌표 검증 | 명시적 IdleState, 실제 준비 상태와 Status 연결 |
| NAVIGATION_MOVE | 공통 Navigator로 XY/yaw 전달, FollowPath, 정지·도착 확인, 취소 | FSM 문서는 NavigateToPose, 현재 HarvestNode는 follow_path만 허용. 모드 전환은 별도 결정 필요. 제한 재시도 정책도 없음 |
| PRECISION_ALIGN | 없음 | 센서/제어기, 정렬 허용오차, BASE_STABLE 확인 및 RESCAN 전이. AprilTag 위치추정 보정은 이 상태를 대신하지 않음 |
| RESCAN | 없음 | 정지 이후 시각의 RGB-D Target List, 미검출 종료, 이전 Target 폐기 |
| HARVEST | 없음. 팔 호출 없이 수확량 0 | Arm Manager 연결, Target별 결과/재시도/누적 Feedback, 모든 Target 처리 후 Result |
| REACH_FAILED 추가 접근 | 없음 | Arm SAFE·미파지 확인 후 제한 이동, 이후 RESCAN으로 되돌아감 |
| 적재/운송 요청 | 없음 | load_ratio, transport_requested, Task 유지 중 1회 요청 |
| DOCKING | 서버/상태 없음 | dock_transfer 수신, Arm/Gate 안전조건, 회전·마커 노출, DOCK_READY, DOCK_STABLE 대기 |
| UNLOADING | 없음 | Gate 실제 상태·IR 배출/clear 확인, TRANSFER_COMPLETE, TRANSPORT_CLEAR 상관관계 확인 |
| RESTORE_POSE | 없음 | Gate Closed·운송 이격 후 자세 복구·정지 확인 |
| ERROR / ESTOP / 복구 | 예외 시 자기 Nav2 Goal 취소, 취소 미확인 시 blocked | HW 오류·E-stop 입력, 관제 상태 보고, Reset/Recovery와 일반 Task 실패 구분 |
| 관제 Status 1Hz | `task_events` 진단만 있음 | `/harvest_01/status`의 현재 FSM·ready·배터리·적재·오류 보고. 진단 Topic은 대체물이 아님 |
| Station 복귀 | 공통 Navigator는 재사용 가능 | return_to_station Action 서버와 Station 정밀 도킹 없음 |

## 문서 간 먼저 맞춰야 할 명칭

- FSM의 `DockTask`, `HARVEST_DOCK_READY`와 최신 통신 규약의 `dock_transfer`, `DOCK_READY`가 다르다. 통신 구현에는 최신 명세 이름을 사용하되 FSM 문서와 매핑을 합의해야 한다.
- 내부 `HARVEST/UNLOADING/RESTORE_POSE`와 외부 Status `HARVESTING/TRANSFERRING/RESTORING`, 그리고 인계 대기 상태는 1:1 동일 문자열이 아니다. 내부 State와 외부 상태 매핑을 정의해야 한다.
- FSM은 비상정지를 ERROR로 설명하지만 최신 Status는 ESTOP을 별도로 정의한다. ERROR로 뭉개지 말고 외부 보고 규칙을 확인해야 한다.
- FSM은 Station 복귀를 일반 이동 재사용으로 설명하지만 최신 통신은 `return_to_station` Action 및 정밀 도킹을 요구한다. 이동부를 공유하면서 작업 인터페이스를 따로 구현해야 한다.
- `NO_TARGET`은 FSM 예시이며 최신 Result의 SUCCESS/FAILED/CANCELED 외 새 result_code로 임의 추가하지 않는다. error_code/작업 완료 정책을 합의해야 한다.

## 권장 구현 순서

1. 이번 변경: 예찰과 같은 실물 환경 선택 및 장치/Nav2/미션 실행, 선택적 태그 캡처 자동 연결. 미션 의미는 이동 시험으로 유지.
2. 상태/통신 계약 확정: StateController/States를 예찰처럼 비동기 enter/완료 전이 구조로 확장하고 1Hz Status·ERROR/ESTOP을 연결.
3. 정밀 정렬 → 재탐지 → Arm 실제 결과 연결. 이 단계에서만 수확 완료 SUCCESS 의미로 전환.
4. DockTransfer/TransferEvent → 배출·이격·복구 및 Station 복귀 연결.

다음 Task와 DockTask 선택은 관제 책임이다. 태그 프로세스가 다음 작업을 결정하거나 주행을 직접 명령하지 않는다. 새 하드웨어 완료 신호·수확 수량을 추정하여 성공으로 처리하지 않는다.
