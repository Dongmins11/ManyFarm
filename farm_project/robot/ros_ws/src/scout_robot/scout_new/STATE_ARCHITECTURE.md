# Scout 상태 구조와 실행 로직

## 이번 수정의 기준

Mission의 큰 순차 실행 함수를 제거하고 각 State가 행동 요청과 완료 판단을 담당하도록 바꿨다. Node·Mission·Communication은 유지하고 StateController를 추가했다. Python의 `_` 멤버·snake_case를 유지했다.

[예찰 로봇 State 설계](https://robot3final.atlassian.net/wiki/spaces/3/pages/8421416/State)의 상태명을 사용한다. 현재는 기존 구현의 **정지 후 관측·촬영 지점 단위 Segment**를 유지한다. 문서의 이동 중 관측·Window 단위 Segment 알고리즘으로 변경한 것이 아니다.

## 책임 분배

| 파일 | 책임 |
|---|---|
| scout_node.py | 설정 → ROS 자원 → 객체 연결. Controller 이벤트 처리 타이머 생성 |
| scout_communication.py | 실제 ScoutArea Goal 승인·취소·피드백·최종 액션 상태 |
| scout_mission.py | MissionContext 생성, 현재 구역 데이터, 진행 기록, 자원 수명, 결과 구성 |
| scout_state_controller.py | 현재 State, enter/exit, 완료 이벤트 분배, 공통 중단 및 오래된 응답 차단 |
| states/*.py | 각 단계의 실제 시작 행동·완료 처리·다음 상태 판단 |
| farm_navigation | 공통 경로·Nav2 이동·정지·TF 도착 검증. I/O 스레드에서 호출 |
| observer.py | 기존 영상 워커 RPC 및 프로세스 종료. I/O 스레드에서 호출 |
| mission_types.py | 실제 작업의 공유 데이터. 데모용 요청·합성 결과가 아님 |

## Unity와 비교한 생명주기

```python
def enter(self) -> None:
    super().enter()
    self._controller.run_async(self, self._capture, self._on_captured)
    # 관측을 요청하고 반환한다. 여기서 while로 결과를 기다리지 않는다.

def _on_captured(self, response: JsonObject) -> None:
    # 실제 영상 응답을 받은 뒤 다음 처리를 요청한다.
    ...
```

Unity에서 행동을 시작하고 완료 이벤트를 받아 다음 State를 요청하는 흐름과 같다. Controller의 request_transition을 거쳐야 상태가 바뀐다. State가 다른 State.enter를 직접 호출하지 않는다.

```text
현재 State.enter
  → 실제 기능 요청
  → enter 반환

기능 작업 완료
  → Controller 이벤트 큐
  → 현재 작업·State의 응답인지 확인
  → 해당 State의 완료 함수
  → 전환 요청
  → Controller: 현재 exit → 다음 enter
```

Navigator와 영상 RPC의 기존 대기 코드를 완전히 새 비동기 드라이버로 교체한 것은 아니다. 이 대기는 단일 I/O 작업 스레드에 격리했고, State는 Future 완료 콜백으로 결과를 받는다. 작업 전체를 실행하는 순차 Mission 루프는 없다.

ROS 액션 execute 콜백은 전체 Result Future 하나만 기다린다. 이는 상태 로직 실행이 아니다. 다른 executor 스레드와 Controller 타이머가 ROS 응답·상태 전환을 처리하므로 MultiThreadedExecutor를 유지해야 한다.

## 단계별 실제 로직

### IDLE — IdleState

명령을 기다린다. Communication이 유효한 Goal을 예약하면 Controller의 시작 이벤트로 Mission 데이터가 준비되고 NAVIGATION_MOVE로 진입한다.

### NAVIGATION_MOVE — NavigationMoveState

enter에서 이번 이동 목적을 확인한다. 처음에는 Nav2 준비·허용오차 확인과 영상 워커 준비를 요청한다. 준비 완료 콜백에서 실제 이동을 요청한다.

이동 목적은 세 가지다.

- section_start: 베드 시작점 이동 → 카메라 정보 조회 → 관측 지점 계획 → 첫 관측 지점 이동.
- observation: 촬영 지점 이동 → Nav2 성공·odom 정지·TF 도착 오차 확인 → SEGMENT_PROGRESS.
- section_exit: 설정에 따른 경로 끝 추가 이동 → SECTION_COMPLETE에 복귀해 다음 구역 판단.

현재의 이동 완료 기준은 기존 정지 관측 동작에 맞춰 유지했다. 문서의 “주행 시작 시 바로 SEGMENT_PROGRESS”와는 다르다.

### SEGMENT_PROGRESS — SegmentProgressState

enter에서 정지 확인 시각 이후의 새 RGB-D 프레임 추론을 요청한다. 응답 후 현재 정지 상태를 확인한다. 다음 등록 작업에서 관측 시각의 TF로 map 좌표를 계산하고, 구역 밖 검출을 제외하고, 기존 Survey.ingest로 ID·좌표·윈도우를 갱신한다.

등록 완료 콜백에서 Observation을 공유 데이터에 보관하고 SEGMENT_COMPLETE를 요청한다. 최종 완료 피드백은 이 상태에서 보내지 않는다.

### SEGMENT_COMPLETE — SegmentCompleteState

enter에서 관측 이미지 표시·저장과 map_detections.json 저장을 요청한다. 저장 성공 알림을 받은 뒤 Mission에 지점 완료 기록을 요청한다. survey.json 저장이 끝나면 다음 지점 여부를 판단한다.

- 다음 지점 존재: SEGMENT_COMPLETE 피드백 → 다음 지점 이동.
- 마지막 지점: 구역 전체 Survey의 수확 작업 목록을 구성 → SECTION_COMPLETE.

과실 0개도 지점 완료로 처리한다. 기존 알고리즘과 구역별 작업 목록 확정 시점을 유지한다. 마지막 지점은 구역 보고에 합쳐서 중복 피드백을 만들지 않는다.

### SECTION_COMPLETE — SectionCompleteState

모든 지점의 처리가 완료됐는지 확인한다. 이미 구성된 HarvestTask 목록으로 Mission에 구역 완료를 기록시키고 저장 성공 후 SECTION_COMPLETE 피드백을 보낸다.

finish_at=route_end이면 출구 이동을 요청한다. 출구 이동 후 이 상태로 돌아와도 구역 피드백은 다시 보내지 않는다. 다음 구역이 있으면 새 구역 데이터를 선택하고 이동을 요청한다. 없으면 Controller에 전체 완료를 요청한다.

### DOCKING — DockingState

문서 상태와의 대응을 위해 파일은 마련했지만, 현재 ReturnToStation 액션과 정밀 도킹 장치 계약이 없다. 정상 예찰 흐름에서는 진입하지 않는다. 임의로 진입시키면 연결 미구현 오류로 거절하며 성공을 흉내 내지 않는다.

## AnyState 공통 처리

AnyState라는 독립 State를 실행하지 않는다. Controller.update가 정상 완료 이벤트보다 먼저 작업 취소·노드 종료를 확인하고, I/O 및 상태 콜백 오류도 같은 중단 경로로 보낸다.

```text
공통 중단 접수
  → 정상 이벤트·전환 차단
  → 현재 State에 중단 통지
  → 진행 중 I/O가 취소를 확인하고 반환
  → Nav2 Goal 종료 확인
  → 영상 워커 종료
  → State.exit
  → IDLE 및 작업 결과 전달
```

실제 정리는 진행 중 작업과 같은 단일 I/O 큐에서 뒤이어 수행한다. 그래서 capture 도중 worker.close가 동시에 실행되지 않는다. 중단 확인 전에 결과를 반환하거나 새 작업을 수락하지 않는다.

장치 종료 확인이 실패하면 작업은 끝내되 새 요청은 차단한다. 자동 복구와 오류별 재시도는 이번 구현에 추가하지 않았다. 과실 0개는 오류로 취급하지 않는다.

## 늦게 도착한 응답 처리

각 작업 요청은 현재 State 객체와 세대 번호를 함께 기억한다. 상태가 바뀌거나 중단되면 번호가 바뀐다. 이전 상태·이전 미션의 완료 콜백은 현재 상태를 진행시키지 못한다.

정상 exit는 콜백 유효 범위를 종료한다. 장치 중단은 공통 중단 절차에서 별도로 수행하므로, 정상 상태 전환마다 로봇을 무조건 멈추거나 워커를 꺼버리지 않는다.

## 읽는 순서

1. scout_node.py의 _initialize_components: 네 객체와 타이머 연결.
2. scout_communication.py의 accept/execute: 작업 접수와 결과 전달.
3. scout_state_controller.py의 start/update/request_transition: 전환의 단일 경로.
4. navigation_move_state.py의 enter/_on_arrived.
5. segment_progress_state.py의 enter/_on_captured/_on_registered.
6. segment_complete_state.py의 저장 완료와 다음 지점 판단.
7. section_complete_state.py의 다음 구역·미션 종료 판단.
8. Controller의 _stop/_finish/_cleanup: 공통 중단 흐름.

빌드·launch의 선택 방식과 기존 시뮬/실물 분기는 변경하지 않는다. 실물 설정·장치 연결 및 실제 주행·관측을 포함한 전체 검증은 별도로 필요하다.

## 공통 주행 이관

2026-10-01부터 Navigator 구현은 farm_navigation에 있다. State는 NavigationResult의 stamp_ns를 받는다. 기존 시뮬 그래프에 베드 간 연결이 없어 기본 환경은 navigate_to_pose를 유지하며, 연결된 그래프를 준비하면 follow_path로 선택한다. 교통 제어와 최종 scout_new 위치 교체는 아직 수행하지 않았다. 자세한 내용은 farm_project/docs/navigation_common_structure.md를 참고한다.
