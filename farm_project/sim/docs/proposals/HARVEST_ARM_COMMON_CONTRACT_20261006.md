# 도착 후 팔 작업 연결: 공통 변경 승인 제안

> **대체된 제안:** 최신 사용자는 대부분을 sim에 두고 공통은 도착 후 팔 작업 연결만 추가하는 좁은 범위를 승인했다. 아래의 공통 Window 실행기·새 `HarvestCandidate`/`GetHarvestCandidates`/`PickFruit` 타입은 적용하지 않는다. 옆의 `.proposal` 스키마도 역사적 초안이며 `farm_interfaces`에 등록하지 않았다. 현재 구현은 기존 `HarvestTask`를 내부 endpoint에 재사용한다. [현행 Teacher 수확 실행 문서](../TEACHER_HARVEST_RUNTIME_20261006.md)를 따른다.

작성: 2026-10-06. 읽기 검토 기준은 `main` / `1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd`와 현재 작업 트리다. **이 문서와 제안 스키마만 작성했으며 공통 소스는 수정하지 않았다.**

사용자는 이번 시뮬 Teacher 실행에 과실 정답 입력을 쓰는 것을 이미 승인했다. 이를 다시 확인받을 항목으로 두지 않는다. 추가 확인 대상은 공통 실행 흐름·내부 인터페이스·부분 성공 처리 의미다. [AGENTS.md](../../../AGENTS.md)의 “공통 코드 변경은 적용 전에 사용자에게 이유, 대상 파일, 구체적인 변경안, 실물·시뮬 영향, 검증 방법을 제시하고 명시적으로 확인받는다”를 적용한다.

## 현재 코드에서 확인한 연결 공백

| 근거 | 현재 동작과 필요한 변화 |
|---|---|
| `robot/ros_ws/src/harvest_robot/harvest_robot/node.py:34` | `ARRIVAL_ONLY_NO_HARVEST`만 허용한다. 팔을 사용하는 완료 정책과 내부 장치 client 구성이 필요하다. |
| `robot/ros_ws/src/harvest_robot/harvest_robot/mission.py:18` | 공통 Navigator로 이동한 뒤 바로 반환한다. 그 뒤 공통 Window 대상 처리 단계를 연결해야 한다. |
| `robot/ros_ws/src/farm_navigation/farm_navigation/navigator.py:88` | 이미 정지·실제 도착 위치·방향 검사를 완료한 뒤 반환한다. 이 계산을 시뮬에 복제할 필요가 없다. |
| `robot/ros_ws/src/harvest_robot/harvest_robot/communication.py:35` | 시작·도착 Feedback 수량을 항상 0으로 보낸다. 처리한 과실의 누적 결과로 바꿔야 한다. |
| 같은 파일 `:62`, `:77` | 이동 반환을 즉시 SUCCESS로 만들고 일반 예외를 NAVIGATION_FAILED로 분류한다. 팔 결과·실패 단계·취소 확인을 구분해야 한다. |
| `robot/ros_ws/src/harvest_robot/harvest_robot/contract.py:19` | 실패·취소를 포함해 항상 수확량/실패량 0을 생성한다. 종료 전에 확정한 누적 수량을 보존해야 한다. |
| `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/arm_sim.py` | 미구현 자리만 있다. 현재 팔 정책 실행·취소·결과를 제공하지 않는다. |
| `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py:72`, `:86` | Bool 활동은 물리 활성화 요청일 뿐이다. 상태 패킷도 바퀴 2축만 검사·발행하며 팔 명령/응답 경로가 없다. |

실제 외부 Action 파일명은 **`HarvestTask.action`**이다. `Harvest.action`은 현재 저장소에 없다. `HarvestTask.msg`는 `task_id/window_id/goal_pose/expected_count`만 포함하며, `goal_pose`는 정차 위치이지 과실 pose가 아니다. Window ID를 분해해 과실이나 구역을 추정해서는 안 된다.

## 책임과 실행 순서

1. 공통 `HarvestMission`이 기존 이동·정지·도착 검사를 완료한다.
2. 공통 Window 실행기가 내부 후보조회 서비스를 호출하고 이번 작업의 대상 목록을 확정한다. 순서, 처리 중 ID, 최종 수량, 중복 방지와 Window 종료를 공통 코드에서 관리한다.
3. 공통 실행기가 대상 한 개마다 내부 **`PickFruit` Action**을 요청한다. 최초 구현은 후보당 한 번 시도하며 재시도 정책을 장치 어댑터에 숨겨 넣지 않는다.
4. 시뮬 장치가 그 한 과실에 대한 Teacher 접근·파지·분리·운반·놓기·안착 동작과 관측을 수행한다. 다른 후보를 고르거나 Window 완료를 결정하지 않는다.
5. 공통 실행기가 확인된 단일 과실 Result로 누적 수량을 갱신하고 기존 외부 Feedback을 보낸다. 마지막에 기존 외부 Result를 반환한다.

시뮬 후보조회는 승인된 `isaac_truth` 소스를 사용한다. **물리 활성화 반경 0.8m와 실제 Teacher 수확 가능 범위를 동일시하지 않는다.** 후보는 실제 오른팔 장착점으로 변환한 과실 root 좌표 및 별도로 확인한 Teacher 대상 조건으로 필터한다. 현재 audit의 임시 박스 판정은 정책 도달성이나 수확 성공 근거가 아니다.

공통 코드가 후보의 선택·재시도·누적 결과·취소·Window 종료를 소유한다. 이 업무 FSM을 `sim/`의 별도 실행기로 복제하지 않는다. 시뮬 담당 범위는 후보 발견, 단일 과실 Teacher 실행, 물리 관측, 요청에 대응하는 상태/종료 확인이다.

## 최소 공통 변경 대상

| 파일 | 변경 내용 |
|---|---|
| `robot/ros_ws/src/harvest_robot/harvest_robot/node.py` | 기존 이동 전용 모드는 명시적으로 유지하고, 새 팔 작업 모드의 endpoint·timeout·구성 검증과 client를 조립한다. 실물 backend 부재는 시작/수락 전에 실패시킨다. |
| 같은 디렉터리 `mission.py` | 도착 후 공통 Window 실행기를 호출한다. 이동/팔 실행/종료 확인의 오류를 구분하며 진행 중 팔 취소를 기다린다. |
| 같은 디렉터리 `communication.py` | 확정 누적 수량 Feedback, 단계별 오류, 실제 팔 종료 이후 ROS terminal 상태, 부분 결과 보존. 기존 task_id 중복 방지 동작과 연동한다. |
| 같은 디렉터리 `contract.py` | 결과에 검증된 수량을 전달하고 음수·역행·중복 완료를 거절한다. 예상 수량은 Goal 원본을 유지한다. |
| 신규 `window_executor.py` | 후보 목록과 후보별 최종 결과, 순차 시도, 취소, Window 완료를 관리한다. Teacher 내부 동작 단계는 복제하지 않는다. |
| 신규 `arm_client.py` | 후보 Service/PickFruit Action client, Goal UUID 상관관계, 응답·실행·취소 timeout과 정지 확인을 담당한다. |
| 신규 `farm_interfaces/msg/HarvestCandidate.msg` | 장치가 발견한 후보 ID/과실 root pose/class를 정의한다. |
| 신규 `farm_interfaces/srv/GetHarvestCandidates.srv` | 실제 도착 후 후보 snapshot을 요청·반환한다. 기존 `GetHarvestTasks.srv`는 예찰 task 목록 서비스이므로 전용하지 않는다. |
| 신규 `farm_interfaces/action/PickFruit.action` | 대상 한 개의 실행/피드백/실제 결과/정지 확인을 정의한다. |
| `farm_interfaces/CMakeLists.txt`, `package.xml` | 위 3개 타입 생성 및 명시적인 `builtin_interfaces` 의존성을 추가한다. |

`HarvestTask.action`, `HarvestTask.msg`의 **외부 필드는 변경하지 않는다.** `HarvestStateController`는 현재 작업을 스레드에 예약하고 결과를 기다리는 구조를 재사용할 수 있으며, 별도 복제 FSM은 필요 없다.

검토한 `farm_bringup/launch/harvest.launch.py`는 이미 `harvest_config`와 공통 Node를 연결하고 시뮬 장치 launch를 포함한다. endpoint를 환경의 harvest 설정으로 선택하면 **공통 launch의 필수 변경은 없다.** 현재 `mode=real,devices=true`의 “실물 장치 미구현” 거절을 유지한다. `devices=false`도 새 팔 모드에서는 명시적인 실물 후보/팔 endpoint가 준비되지 않으면 실패해야 하며 sim backend로 대체하지 않는다.

시뮬 구현 범위는 `arm_sim.py`, 장치 ROS bridge/로컬 패킷 계약, Isaac runtime 장치 등록, sim 설정·launch·시험이다. 필요하면 단일 과실 Action/Service 전용 시뮬 노드를 기존 장치 launch에 추가한다. Isaac 프로세스는 기존 한 개를 사용한다.

## 내부 후보조회 계약

제안 스키마는 옆의 `HarvestCandidate.msg.proposal`, `GetHarvestCandidates.srv.proposal`이다. 승인 전 ROS 패키지에 등록하지 않는다.

- 요청은 robot/map, 기존 HarvestTask, **외부 Action Goal UUID인 `task_run_id`**, 실제 정지 확인 시각을 전달한다. 비즈니스 `task_id`를 재시도마다 바꾸지 않는다.
- 응답은 장치 `source_epoch`(Isaac session), `snapshot_id`, 관측 시각, `workspace_id`, 관측 소스와 후보 목록을 반환한다. 예전 audit 파일을 재사용하지 않고 현재 Isaac thread에서 일관된 snapshot을 만든다.
- `valid=true`는 최신 snapshot을 정상 생성했다는 의미다. 후보 목록이 비어 있는 정상 응답과 데이터 불가·stale 응답을 구분한다.
- 후보 `candidate_id`는 같은 source epoch/task 실행에서 안정적이어야 한다. 갱신 조회를 할 경우 같은 물체에 새 ID를 붙여 중복 수확하지 않는다. `root_pose`는 frame ID와 촬영/관측 시각이 있는 오른팔 장착 기준 pose이며 모든 값·회전·프레임을 검증한다.
- 현재 Task에는 Window 경계 polygon이 없다. 최초 구현의 후보 범위는 **확인된 정차 위치의 오른팔 Teacher workspace**로 정의하고, 그 정의 버전을 `workspace_id`로 기록한다. 임의로 원래 예찰 Window 전체를 복원했다고 주장하지 않는다. 실제 허용 mask는 Teacher/기하 검토 결과를 적용한다.
- 예상 수량은 후보 수/목표 수/성공 수로 복사하지 않는다. 최초 후보 snapshot의 각 대상을 공통에서 한 번 처리한 뒤 Window를 종료하는 안이며, 자동 반복 재탐색·재시도 확대는 별도 동작 변경이다.

## 단일 과실 실행 계약과 취소

제안 스키마는 `PickFruit.action.proposal`이다. 내부 Action Goal UUID를 해당 단일 시도의 ID로 사용하고 중복 `attempt_id` 필드를 외부에 추가하지 않는다. 로그에는 외부 Goal UUID, 내부 Goal UUID, task/window/candidate, source epoch와 snapshot을 연결한다.

- 장치는 현재 source epoch와 대상 snapshot의 유효성을 확인한 뒤 수락한다. 임무/후보 불일치·stale·팔 busy·연결 단절은 임의의 다른 과실로 바꾸지 않고 거절/오류로 반환한다.
- `attempt_started`는 실제 동작 시작 여부다. 수락 거절이나 전송 오류를 실패한 과실 한 개로 더하지 않는다.
- `harvested=true`는 사용자 요청에 따라 **실제 박스 안착 완료**가 확인된 경우만 가능하다. 권장 판정은 줄기 분리·집게 해제·과실 collider 전체의 지정 박스 내부 포함·속도 한도와0.6초 안착 유지다. 원본 Teacher의 유효 파지/분리/보유 판정은 정책 전환에 유지하고, RL 성공 플래그와 물리적 최종 도착지는 각각 기록한다. 단순 분리, 목표 도달, 정책 타임아웃 또는 예상 수량은 성공 근거가 아니다. 누적 수량은 각 시도 판정 시점의 성과이며 이후 운송까지의 보존을 인증하지 않는다.
- `safe_stopped=true`는 종료/취소 후 명령 중단과 검증된 정지 상태의 ACK다. cancel 서비스가 수락됐다는 응답만으로 팔 정지를 확정하지 않는다. 파지 중 취소에서 그리퍼를 임의로 열어 떨어뜨리지 않도록 단일 과실 제어기의 중단 동작을 명시한다.
- `ready_for_next=true`는 다음 대상에 필요한 복귀 자세·빈 집게 상태까지 확인됐음을 뜻한다. 안전하게 멈췄지만 물체를 잡은 채인 상태와 구분한다. 일반 실패라도 다음 준비가 확인되지 않으면 Window를 중단하며 다른 과실을 즉시 보내지 않는다.
- 외부 취소/종료: 새 대상을 보내지 않음 → 진행 중 PickFruit 취소 요청 → 실제 terminal Result와 정지 확인 → 이미 확정한 수량을 보존하여 CANCELED. 정지 ACK를 받지 못하면 `CANCEL_UNCONFIRMED`, FAILED/abort와 기존 `blocked`를 설정해 새 작업을 막는다.
- 팔 작업 중 베이스 움직임, backend session 교체, 관측 중단, transport timeout은 작업 중단으로 처리한다. ROS Action timeout과 장치 통신/취소 timeout은 steady clock으로 두어 시뮬 일시정지에서 무한히 기다리지 않는다.
- 외부/내부 늦은 응답은 UUID/epoch로 격리한다. 취소된 시도 뒤에 늦게 온 성공을 새 작업 수량에 더하지 않는다. 정지 여부가 불명확한 시도를 자동 재전송하여 실제 동작을 중복하지 않는다.
- 실제 수확이 확인된 뒤 안전 종료 중 취소되면 `harvested=true`와 종료 상태를 함께 보존할 수 있다. 공통 누적 수량은 이미 확정된 관측을 잃지 않아야 한다.

Adaptive 물리 활동은 단일 과실 장치가 실제 실행을 시작할 때 켜고 종료/취소 정지 확인 후 끈다. 현재 sim Bool lease를 사용하면 실행 소유자가 갱신해야 한다. 도착 이벤트만으로 팔 작업이나 성공을 추정하지 않는다.

## 외부 Feedback/Result와 부분 성공 선택

외부 Feedback은 기존 `robot_id/task_id/success_count/failed_count/timestamp` 그대로, 수확 처리 시작 및 후보 하나의 최종 결과가 확정될 때 발행한다. 내부 Teacher `stage`나 시도 ID를 외부 필드에 추가하지 않는다. 상세는 `task_events` 진단에 남긴다. 외부 Result도 기존 `expected_count/harvested_count/failed_count/error_code/error_message`를 사용한다.

기존 `HarvestTask.action`은 “대상 한 개 처리 완료 때 누적 수량”과 “실패/취소에서도 실제 수확 성공/실패 수량 보존”을 명시한다. 그러나 **일부 성공+일부 실패의 Window result_code는 정의하지 않았다.** 현재 도착 전용 SUCCESS/0개 구현으로 팔 작업의 의미까지 확정할 수는 없다.

| 확인할 선택 | 의미와 관제 영향 |
|---|---|
| **권장: 처리 완료 SUCCESS** | 확정 후보를 모두 처리하고 팔 종료까지 확인하면 SUCCESS. 예: 성공2/실패1 → SUCCESS, harvested_count=2, failed_count=1. 미완료 중단·장치/프로토콜 오류는 FAILED, 취소 확인은 CANCELED. 관제는 SUCCESS를 “전량 수확”으로 읽지 않고 수량을 함께 표시해야 한다. |
| 하나라도 실패면 FAILED | 위 예시는 FAILED/PARTIAL_HARVEST. 관제의 FAILED 재시도 정책이 전체 Window를 다시 보내면 이미 성공한 후보의 중복 방지가 필요하다. 정상적으로 처리한 Window도 실패 큐에 남을 수 있다. |

권장안은 Window 처리의 종결 여부와 개별 과실 성과를 분리하고 기존 수량 필드를 활용한다. **사용자 확인 전 적용하지 않는다.** 예상값 5개에 관측된 후보가 3개였다는 차이만으로 실패 2개를 만들어내지 않는다. 정상 빈 후보 응답의 결과도 권장안에서는 처리 완료 SUCCESS/0개로 설명하되, `expected_count>0`과의 차이는 진단에 명시한다. 이 의미까지 사용자/관제가 받아들이는지 확인해야 한다.

## 검증과 추가 인수 항목

승인 뒤 필요한 검증:

- 공통 단위시험: 도착 실패 시 팔 호출 없음, 도착/정지 후만 후보 조회, 2성공+1실패의 선택한 의미, 빈 후보/자료 없음 구분, 예상 수량 보존, 중복 Feedback/Result와 늦은 UUID, 부분 성공 후 취소 수량 보존, 종료 미확인 blocked.
- 타입/ROS 시험: 새 내부 타입 빌드·직렬화, 기존 외부 타입 필드/해시 유지, Service+Action 통신, 거절·busy·취소·timeout·session 교체·backend 미존재. 실물 장치 없는 real 설정은 즉시 실패하고 sim endpoint를 사용하지 않음.
- Isaac 시험: 공통 서버→후보→단일 Teacher→실제 파지/분리/안착→공통 누적 결과, 취소 시 실제 안전 중단, 활동 heartbeat와480/60Hz 전환. truth 소스와 정책 버전·실패 증거를 기록한다.
- 관제 회귀: 현재 외부 HarvestTask Goal/Feedback/Result가 그대로 연결되는지, 부분 성과를 표시·다음 Window 전송에 어떻게 사용하는지 확인한다. 현재 checkout에는 이를 검증할 운영 `farm_control` 클라이언트가 없다.

추가 파일/정보:

- 이번 sim 실행 제안 작성에 원본 정책 파일을 다시 받을 필요는 없다. 받은 번들의 RL/기하/자산은 root의 별도 검토 대상이다.
- 받은 `src/harvest_robot/README.md`는 ROS2 런타임 어댑터·실물 안전 제어가 포함되지 않았다고 명시한다. `perception_ros.py`와 SO101 bench bridge가 실제 PickFruit 실행·안전 취소 server를 대신하지 않는다.
- 실물까지 실행하려면 작업자가 사용하는 관절 명령/상태 인터페이스, 제어기·모터 한계와 stop ACK, detector/TF 입력 및 과실 ID 유지 방식, 실제 단일 과실 완료/실패 증거 계약을 받아야 한다. 없는 상태에서 실물 완료를 주장하지 않는다.
- 외부 관제와 부분 성공 의미까지 보장하려면 해당 HarvestTask client/validator와 SUCCESS·FAILED 후 재전송 정책을 확인해야 한다. 제공되지 않은 관제 동작을 추정해서 바꾸지 않는다.

이번 산출물은 승인 검토용이며 신규 스키마 파일은 `.proposal` 확장자로만 저장했다. ROS Jazzy rosidl parser로3종 문법 검사는 통과했으나 타입 등록·빌드·통신 시험은 아니다. 공통·시뮬 실행 소스의 후속 구현 및 테스트는 아직 하지 않았다.
