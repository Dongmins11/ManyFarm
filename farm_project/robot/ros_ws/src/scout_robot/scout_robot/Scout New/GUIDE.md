# Unity와 비교하며 읽기

현재 구현 설명은 [STATE_ARCHITECTURE.md](scout_new/STATE_ARCHITECTURE.md)에 통합했습니다.
이전에 Mission.execute와 State.execute 순차 실행을 설명하던 문서는 교체했습니다.

| Unity에서 떠올릴 역할 | 현재 코드 |
|---|---|
| 초기화와 컴포넌트 연결 | ScoutNode |
| 퀘스트의 목표·진행도·결과 데이터 | ScoutMission |
| 네트워크 명령 수신·상태 보고 | ScoutCommunication |
| 현재 상태·ChangeState·공통 중단 조건 | ScoutStateController |
| Enter에서 행동 시작, 완료 이벤트에서 다음 상태 결정 | 각 State |
| 실제 이동·센서 기능을 호출하는 컴포넌트 | Navigator / Observer |

ROS 타이머가 Controller.update를 호출합니다. Unity의 Update처럼 반복해서 이벤트를 처리하지만,
게임 프레임이나 물리 주기를 재현하는 것은 아닙니다. 이동·영상 대기는 별도 I/O 스레드가 맡습니다.
Mission 기록과 관제 전송은 별개입니다. 기록은 Mission 데이터에 반영하고, 전송은 Communication.feedback으로 수행합니다.
