# Vic Pinky ↔ Jetson 로봇팔 통신 인계 — 2026-10-18

## 문서 범위와 역할

이 문서는 은비가 설계하고 PC에서 검증한 Pinky 측 통신 기준을 Jetson 담당자에게 전달하기 위한 자료다. Jetson 담당자의 구현 완료나 실물 합의 완료를 의미하지 않는다. 현재 브랜치는 feat/harvest-handoff-real-20261018, 원격 기준8466ac1 + PC의1~5단계 미커밋 변경이다. 최신 추가 코드는 아직 원격에 push하지 않았다.

- Pinky: 관제 명령 수신, 주행·수확/인계 순서 관리, Jetson Action 요청, 결과 집계·관제 전달.
- Jetson: 팔 및 적재함 모터 제어, 실제 작업과 완료/실패 판정, Action Feedback/Result 반환.
- 로봇팔은 관제와 직접 통신하지 않는다. 팔 상태의 관제 전달은 Pinky가 중계하며 Status Topic의 항목은 아직 미정이다.
- 배출·걸림 감지 및 수확량 측정 방식, AI 비전 사용 여부는 보류한다. 이 문서에서 센서나 알고리즘을 지정하지 않는다.

## 1. 배출 Action — 현재 구현된 통신 규격

타입: farm_interfaces/action/Discharge.
정의 원본: robot/ros_ws/src/farm_interfaces/action/Discharge.action.
Pinky는 Action client, Jetson은 Action server다. 양쪽에서 같은 정의를 빌드해야 한다. 운영 endpoint는 아직 지정하지 않았다.

### Goal

| 필드 | 자료형 | 의미 |
|---|---|---|
| transfer_id | string | Pinky가 전달하는 이번 인계 식별값. Result에 그대로 반환 |

한 번 요청하면 Jetson에서 열기→배출→닫기 전체를 수행한다. Pinky가 열기와 닫기를 각각 요청하지 않는다.

### Feedback

| 필드 | 자료형 | 값과 의미 |
|---|---|---|
| phase | string | OPENING: 여는 중 / DISCHARGING: 배출 및 완료 확인 중 / CLOSING: 닫는 중 |

진행 상태를 보고하는 용도다. CLOSING Feedback이나 명령 접수만으로 완료를 보고하지 않는다. 정확한 발행 주기와 장치 내부 단계 구현은 아직 지정하지 않았다.

### Result

| 필드 | 자료형 | 의미 |
|---|---|---|
| transfer_id | string | Goal과 같은 인계 식별값 |
| error_codes | string[] | 발생한 오류 목록. 정상은 빈 배열 [] |
| error_message | string | 사람이 확인할 상세 설명 |

별도 discharge_complete/closed 필드는 없다. error_code 단일 문자열도 사용하지 않는다.

| 오류 코드 | 의미 |
|---|---|
| OPEN_FAILED | 적재함 열기 실패 |
| DISCHARGE_FAILED | 배출 미완료 |
| CLOSE_FAILED | 적재함 닫기 실패 |
| INTERNAL_ERROR | Jetson 내부 처리 오류 |

배출과 닫기 모두 실패하면 두 오류를 함께 담는다. 오류가 없을 때 ["NONE"]을 보내지 않고 []를 보낸다. 이 목록에 없는 코드도 Pinky는 성공으로 처리하지 않지만, 새 코드는 양쪽 담당자가 의미를 맞춰 추가한다.

### 완료 판단과 예시

Pinky는 현재 transfer_id 일치 + Action SUCCEEDED + error_codes=[]를 모두 확인해야 전체 완료로 인정한다. SUCCEEDED는 배출뿐 아니라 닫기까지 정상 완료했다는 뜻이다.

| 장치 결과 | Action terminal | error_codes |
|---|---|---|
| 열기·배출·닫기 모두 완료 | SUCCEEDED | [] |
| 배출 실패, 닫기 완료 | ABORTED | ["DISCHARGE_FAILED"] |
| 배출 완료, 닫기 실패 | ABORTED | ["CLOSE_FAILED"] |
| 배출·닫기 모두 실패 | ABORTED | ["DISCHARGE_FAILED", "CLOSE_FAILED"] |

위 예시는 결과 표현이며 실패 후 닫기를 반드시 시도하라는 동작 지시가 아니다. 실패 시 모터 처리 순서는 Jetson 담당자와 별도로 정한다. 취소·실패·결과 미수신에서는 오류 코드가 없다는 이유로 배출이나 닫힘을 추정하지 않는다.

## 2. Pinky의 인계 순서

1. 현재 좌표의 수확 전체가 끝난 후 관제 인계 요청을 처리한다. 현재 과실 하나만 끝내고 남은 과실을 두고 인계하지 않는다.
2. 준비 확인 및 제자리 왼쪽90도 회전·정지 후 DOCK_READY 보고.
3. 관제의 DOCK_STABLE을 받은 뒤 Jetson에 배출 Action 한 번 요청.
4. 전체 성공 Result를 확인한 뒤 TRANSFER_COMPLETE 보고.
5. TRANSPORT_CLEAR를 기다린 뒤 현재 인계 성공 증거를 확인하고 제자리 오른쪽90도 복원. 추가 닫기 요청 없음.
6. 복원까지 정상 완료한 뒤 논리 적재량 초기화. 배출 완료만으로 즉시 초기화하지 않는다.

실패·취소·시간초과에는 완료 보고·복원 회전·주행을 자동 진행하지 않는다. 자동 재요청도 하지 않는다. 배출 후 복원 실패 시 남은 카운트는 복구 전 논리 기록으로, 실제 잔량을 측정한 값이 아니다.

## 3. 준비 확인·정지·취소 — 연결 합의 필요

현재 공통 어댑터는 prepare_arm과 stop을 외부 std_srvs/Trigger 서비스로 연결할 확장 지점을 갖는다. 실제 이름은 비어 있다. Jetson 담당자가 해당 서비스를 이미 구현했다고 가정하지 않는다.

- prepare_arm: 실제 준비 확인의 연결 방식과 담당 노드 합의 필요. 별도 팔 접힘 동작을 새로 요청한다는 뜻은 아니다.
- stop: success는 요청 접수가 아닌 물리 정지 완료를 의미해야 한다. 센서/모터 상태 중 어떤 근거로 확인할지 합의 필요.
- Pinky는 배출 Action 자신의 Goal에 취소를 요청하고 terminal을 기다린다. 취소 ACK 또는 CANCELED만으로 물리 정지·닫힘을 확인했다고 판단하지 않는다.
- 취소 시 Jetson이 즉시 멈출지, 어느 단계까지 수행할지, 닫기를 시도할지 아직 미정이다. 정상 성공 Result를 임의로 만들어 반환하면 안 된다.
- Action 취소와 stop 서비스가 함께 요청될 때의 처리 순서/중복 처리도 합의 필요. 현재 Pinky는 stop 요청을 먼저 보내고 Action 취소/종료를 확인한 뒤 stop 응답을 확인한다.
- Goal 중복 수락 정책, 통신 단절/재시작 후 실제 상태 확인과 복구 절차는 아직 합의가 필요하다. transfer_id 필드 자체가 Jetson의 중복 방지 구현을 대신하지 않는다.

## 4. 수확 Action — 업무 흐름 확정, Jetson용 형식은 별도

- 한 Action은 현재 좌표에서 수확 가능한 대상 전체를 처리하는 단위다.
- 과실 하나의 시도가 끝날 때마다 성공·실패 모두 Feedback을 보낸다. Pinky는 성공량만 적재량으로 집계한다.
- 호출 기준에 도달하면 Pinky가 기존 관제 Status의 transfer_required로 호출 필요를 알리고 수확은 계속한다. Jetson이 관제에 직접 운송로봇을 호출하지 않는다.
- 인계 요청이 있어도 현재 좌표 전체 수확을 마친 뒤 인계 준비한다.
- 이동할 때 팔은 접힌 상태여야 한다. 정상 수확 시작/완료 자세를 접힌 상태로 한다는 합의에 따라 수확 중 이동하지 않으며, 실패·취소 후 접힘은 추정하지 않는다.
- Pinky 공통 코드에는 기존 HarvestTask 기반 내부 팔 클라이언트가 있으나, 이것이 Jetson과 합의한 최종 수확 Action 형식은 아니다. Goal/Feedback/Result와 과실별 시도 결과 표현은 담당자와 따로 확정해야 한다.
- 수확량 측정 방식 변경 논의와 호출 임계값은 미정이다. 실제 운영 수량을 임의로 정하지 않는다.

## 5. 팔 Status Topic — 미확정

Jetson→Pinky로 상태를 받고 필요한 항목을 관제에 전달하는 방향만 정했다. Topic 이름·메시지 필드·주기·오래된 상태의 판단 기준·오류 전달 항목은 미정이며 이번 배출 Action 구현에 넣지 않았다.

## 6. 통신 환경과 실제 연결 전 확인

Pinky/은비 PC의 현장 성공 기준은 ROS2 Jazzy, CycloneDDS, Domain77, LOCALHOST, 기기간 Zenoh 브리지다. 관제 연결 주소는 tcp/192.168.0.20:7447이며 기존 주행→초기 위치→브리지 성공 절차를 유지한다.

Jetson의 OS/ROS 배포판/아키텍처·RMW·Zenoh 설치 및 연결 경로는 아직 확인하지 않았다. Pinky 환경을 Jetson의 현재 환경이라고 단정하지 않는다. Jetson과의 ROS 형식 호환 및 기기간 통신을 별도로 확인해야 한다. PC 로컬 송수신 시험은 이 검증을 대신하지 않는다.

운영 설정 위치: robot/config/harvest/harvest_real.json의 transfer. 새 방식은 discharge_mode=action 및 rotation_mode=nav2_spin, discharge_action의 endpoint/response_timeout_s/cancel_timeout_s, 실제 prepare_arm/stop 서비스 연결과 rotation 설정을 명시해야 한다. 운영값 미확정으로 아직 활성화하지 않았다. 시뮬은 해당 환경 설정에서 같은 공통 모듈을 사용한다.

## 7. 완료한 검증과 근거

2026-10-18 17:47 KST 사용자 제공 터미널 출력 기준:
- PC 패치 적용·git diff --check 성공, 관련 오프라인57개 PASS.
- farm_interfaces 1개 패키지 빌드 성공.
- 실제 ROS Action 송수신 정상/복수 오류/거절/취소4개 PASS.
- 시험 서버는 /test_only/discharge_<uuid>에서 모의 장치 결과를 반환한다. 운영 endpoint가 아니다.
- 로그 경로: /home/eunbi/harvest_stage5_ros_zdqlxg/ros_smoke.log.

전체 수확 서버 ROS 빌드·Jetson 연결·Zenoh 기기간 통신·Isaac·실물 열기/배출/닫기/정지는 미검증이다. 로봇에 공통 통합 코드 자체가 아직 배포되지 않았을 수 있으므로 로봇의 현재 설정과 전체 변경을 대조한 뒤 별도 배포·검증해야 한다. 과거 실물 주행/태그/관제 성공 기록과 이번 새 통신 검증을 구분한다.

## 8. 담당자와 다음에 정할 항목

1. Jetson 실행 환경과 ROS 형식 호환, 실제 Action endpoint 및 응답/취소/작업 제한시간.
2. 준비 확인과 물리 정지 확인의 담당 노드·연결 방식.
3. 취소·오류·통신 단절·재시작 시 모터 동작 및 복구 방식.
4. 배출 완료/걸림/닫힘 판정 방법 — 현재 보류 사항.
5. 수확 Action의 과실별 성공·실패 Feedback 형식과 수확량 측정 방식.
6. 관제에 중계할 팔 Status Topic 항목.

이 문서는 전달용으로 작성했으며 담당자에게 직접 발송하거나 Confluence/Slack에 게시하지 않았다.
