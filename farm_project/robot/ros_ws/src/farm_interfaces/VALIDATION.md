# 2026-10-02 단일 Section / Result 작업 목록 적용

현재 규격은 아래와 같다. 이후의 2026-10-01 및 09-21 내용은 이전 규격 검증 이력이다.

- ScoutArea.Goal: section_ids 배열 대신 section_id 문자열 하나.
- ScoutArea.Result: section_id와 harvest_tasks[] 추가; completed_section_ids 제거.
- ScoutArea.Feedback: completed_section_count 제거. 배열은 진행 기록이며 등록에 사용하지 않는다.
- HarvestTask.msg: task_id/window_id/goal_pose/expected_count만 전송.
- HarvestTask.Action Result: window_id 추가. Goal의 Window와 다르면 후속 전송 차단.
- 정상 Result는 배열 순서대로 등록. 실패·취소 부분 목록은 보존하고 수동 전송 보류.
- 내부 Section은 Goal에서 가져오고, 내부 sequence는 배열 순서, 미제공 Segment는 빈 값.
- 기본 수동/전체 관제/mock 모두 Result 목록을 사용하며 GetHarvestTasks를 생성·호출하지 않는다.
  과거 srv 파일은 보존되어 있으나 현재 흐름의 의존성이 아니다.
- 전체 관제는 한 실행에 Section 하나의 mission_config를 요구하며 기존 Status/Window/구역 검사를 유지한다.
- DockTransfer/TransferEvent/ReturnToStation 구현 추가는 이번 범위에 포함하지 않는다.

검증: 두 패키지 빌드 성공, 생성 타입의 정확한 필드 목록과 CDR 왕복 통과,
단위 시험 64개 및 localhost ROS 통합 시험 43개 통과.
Feedback 선행/중복/누락에도 Result에서만 등록, 정상·무작업·잘못된 좌표/ID/합계,
실패 부분 목록 보류, FIFO 수동·자동 수확, 수확 Window 불일치, 거절·취소·늦은 Result를 확인했다.
외부 시뮬레이션이나 실물 로봇에 Goal을 보내지는 않았다.

[빌드 로그](/home/user/Documents/ChatGPT/ManiFarm/scout-result-validation-2026-10-02/build.log),
[단위 시험](/home/user/Documents/ChatGPT/ManiFarm/scout-result-validation-2026-10-02/unit.log),
[ROS 시험](/home/user/Documents/ChatGPT/ManiFarm/scout-result-validation-2026-10-02/ros.log),
[인터페이스 검사](/home/user/Documents/ChatGPT/ManiFarm/scout-result-validation-2026-10-02/interfaces.log).
이전 실패 및 중단 로그도 같은 디렉터리에 보존한다.
실행은 [RUN_GUIDE.md](../../docs/RUN_GUIDE.md), 팀 전달은 [ROBOT_TEAM_HANDOFF.md](../../docs/ROBOT_TEAM_HANDOFF.md)를 따른다.

---

# 2026-10-01 예찰 프로토콜 적용 검증

기준: 사용자가 제공한 예찰 통신 프로토콜 텍스트.

- SECTION_COMPLETE는 빈 배열·빈 segment_id·segment_expected_count=0으로 완료만 알린다.
  수동 모드는 기존 Task·수확 상태·결과를 유지하고 목록 검증 완료로 간주하지 않는다.
- GetHarvestTasks.Response에서 found를 제거했다. error_code=NONE / section_complete로 판단한다.
  오류 응답은 원인을 기록하며, 정상 예찰 중 응답은 전체 모드에서 제한된 횟수로 재조회한다.
- 기본 예찰 Goal의 Section은 SEC_01~03. 파라미터로 다른 이름을 지정할 수 있다.
- 예찰 Feedback 공백 제한은 기본 0.0(해제), mock Status는 1 Hz.
- farm_interfaces 및 farm_control 빌드 성공, 생성된 Service의 필드 목록/CDR 왕복 통과.
- 단위 시험 72개, localhost ROS 통합 시험 48개 통과.
- 정상·빈 Segment·잘못된 ID/좌표·잘못된 Section 완료 본문·수확 거절/실패·목록 오류와
  Enter 시작 → Task 등록 → h 수동 FIFO 전송 → Feedback/Result 기록을 확인했다.
- 기본 모드는 Status·GetHarvestTasks 없이 동작하며, Section 완료만으로 누락 없는 목록임을 보장하지 않는다.
- 외부 시뮬레이션·실물 연결 시험은 수행하지 않았다. 양쪽 장비에서 동일 인터페이스로 재빌드해야 한다.

[빌드 로그](/home/user/Documents/ChatGPT/ManiFarm/scout-protocol-validation-2026-10-01/build-events.log),
[단위 시험 로그](/home/user/Documents/ChatGPT/ManiFarm/scout-protocol-validation-2026-10-01/unit-tests.log),
[ROS 통합 시험 로그](/home/user/Documents/ChatGPT/ManiFarm/scout-protocol-validation-2026-10-01/ros-tests.log),
[인터페이스 검증](/home/user/Documents/ChatGPT/ManiFarm/scout-protocol-validation-2026-10-01/interfaces.log).

재현 명령(워크스페이스 루트에서 실행):

```bash
source /opt/ros/jazzy/setup.bash
colcon build --packages-select farm_interfaces farm_control --symlink-install
source install/setup.bash
python3 src/farm_interfaces/examples/verify_interfaces.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s src/farm_control_skeleton/tests/unit -v
FARM_RUN_ROS_TESTS=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s src/farm_control_skeleton/tests/ros -v
```

---

# 2026-10-01 수확 Action 규격 갱신

현재 HarvestTask.action은 Goal의 harvest_task 중첩 구조와 간소화된 Feedback/Result를 사용한다.
아래 2026-09-21 기록은 이전 규격의 검증 이력이다.

```bash
source /opt/ros/jazzy/setup.bash
cd ~/farm_ws
colcon build --packages-select farm_interfaces farm_control --symlink-install
source install/setup.bash
python3 src/farm_interfaces/examples/verify_interfaces.py
```

예제는 생성된 Goal/Feedback/Result의 정확한 필드 목록과 CDR 직렬화 왕복을 검사한다.
수확 Goal의 sequence/위치/ID/예상 개수가 원본 Task와 같고 수신 순서를 유지하는지 확인한다.
관제와 수확 서버는 반드시 같은 정의로 재빌드해야 한다.

---

# 2026-09-21 Segment별 전달 수정 검증

| 항목 | 결과 |
|---|---|
| 기존 msg/action/srv 5개와 수정본의 자료형·필드 순서 대조 | 동일 — 주석·전송 의미만 수정 |
| SEGMENT_COMPLETE 예제 JSON | Task 2개, sequence 1·2, 동일 Section·Segment, expected_count 합 5 |
| SECTION_COMPLETE 예제 JSON | 빈 배열, 빈 segment_id, Section 전체 예상량 6, 완료 Segment 3개 |
| Python 검증 예제 문법 검사 | 통과 |
| 함께 수정한 관제 내부 테스트 | 21개 통과 — 복수 Task 누적, 중복·충돌, 순서 역전, 조회 복구, 배정 조건, Feedback 변환 등 |
| 관제 모의 실행 | Segment별 2개·1개·0개 누적 후 Task 3개를 각각 한 번씩 순차 배정 |
| ROS 빌드·CDR 왕복·Action 네트워크 통신 | 이번 환경에서 미실행 |

`verify_interfaces.py`는 실제 생성된 ROS 타입을 사용한다. 예제에서 첫 Segment의 Task 두 개를 읽고, 다음 Segment의 Task 하나(sequence 3)와 빈 Segment를 구성하여 0개·1개·2개 배열과 수확 Goal 매핑을 확인한다. 마지막 SECTION_COMPLETE에는 Task 배열을 다시 넣지 않는다.

사용자 PC의 빌드된 환경에서 다음 명령이 PASS 세 줄을 출력하는지 확인한다.

```bash
source /opt/ros/jazzy/setup.bash
cd ~/farm_ws
colcon build --packages-select farm_interfaces --symlink-install
source install/setup.bash
python3 src/farm_interfaces/examples/verify_interfaces.py
```

메시지 필드가 동일하더라도 양측 노드의 전송 의미를 함께 맞춰야 한다. 기존 예찰 코드가 SECTION_COMPLETE에서만 배열을 보내면 수정된 관제 흐름과 맞지 않는다. 예찰 Action Server와 조회 Service 구현은 이 인터페이스 패키지에 포함되어 있지 않다.
