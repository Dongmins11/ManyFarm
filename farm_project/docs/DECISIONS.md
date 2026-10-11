# 설계 결정 및 미확정 사항

<!-- HARVEST_VERIFIED_BASELINE_20261011 -->
## 수확 실물 성공 상태 고정 — 2026-10-11 17:51 KST

- 사용자 확인: 중간 위치에서 회전 없이 목표로 이동했고 관제 웹에 작업 완료가 표시됨. 단일 요청 성공이며 반복 신뢰성, 태그 보정 정확도, 실제 수확 동작까지 검증한 것은 아님.
- 사용자 지시: 현재 성공한 코드·설정을 반드시 유지. 이후 코드·설정·실행 옵션 변경은 이유와 범위를 설명하고 사용자 확인 후 적용. 조회·로그 분석부터 진행.
- 통신 ROS_DOMAIN_ID=77 / rmw_fastrtps_cpp, 태그 카메라 별도 환경 유지. navigation.tf_recovery_enabled=false (timeout_s=10.0 값은 남아 있으나 비활성). 이전 문서의 TF 복구 ON 설명보다 이 상태가 최신.
- SEC_01 work_corridor_nodes=[10,14]. 구간 내 위치·방향 및 전방 목표 조건을 만족하면 SECTION_RESUME로 진입점 복귀를 건너뛰고 현재 위치에서 작업 목표로 이동. 구간 밖 기존 진입 및 충돌 감지 유지.
- 중간 출발 관련 4개 파일은 성공 후 로봇에서 받은 harvest_working_20261011.tar.gz와 전달 v2의 SHA256이 일치함. PC의 미커밋 관제 호환·상태 발행·TF 복구 소스 및 기존 테스트는 보존.
- launch 중복 방지와 제한 시간 진단 도구를 로봇 적용본으로 보존. Wi-Fi/DDS 정체와 TF 끊김의 재발 방지는 해결 완료로 판정하지 않음.
- Git: Robot3FinalProject/main, feat/apriltag-localization, 사용자 출력 HEAD 25cdf88 + 미커밋 변경 기준. PC 경로 /home/eunbi/vmany/main/farm_project. 로봇 /home/vic/vmany/main/farm_project는 Git 미연결. PC VS Code에서 기존 Fix: 형식으로 커밋·push 예정; 이 문서 생성 시점 원격 반영 미완료.
- 승인 범위: 성공한 로봇 소스·설정을 PC에 백업하고 Git에 보존. PC 문서는 최신 이력을 보존하며 로봇의 오래된 문서로 덮어쓰지 않음. 로봇 실행·설정 변경 없음. 시뮬 신규 변경 없음; 앞선 Action 규격 변경의 다중 구역 영향은 기존 호환 문서 참조.
- 패키지 적용 전 PC 파일 해시 확인 및 저장소 밖 백업. PC 재빌드 불필요. 복원은 적용 시 표시된 backup의 restore_manifest.json과 원본 파일을 기준으로 해당 파일만 복원. Git pull/reset 및 로봇 재배포는 이번 백업 작업에 포함하지 않음.


관련 구현 기록: docs/changes/HARVEST_RUNTIME_TOOLS_20261011.md, docs/changes/HARVEST_MIDSTART_20261011.md.

<!-- MOTOR_INSTALLED_20261010_1751 -->
> **모터 영구 설정 설치 확인 — 2026-10-10 17:51 KST**
> 사용자 로봇 출력: udev 규칙 검사 Success 1 / Fail 0,
> serial=BG02QM7Y, latency_timer=1, rule_installed=True,
> CHECK_OK 및 INSTALL_OK 확인.
> 아래의 설치 미실행 표기는 설치 전 기록이며 이 확인으로 갱신한다.
> 재부팅·USB 재연결 후 지속성 확인은 아직 미실행이다.


기준: 2026-10-06 / `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`.
과거 대화와 저장소의 승인·변경 기록에서 확인한 결정을 요약한다. 이 문서 작성이 새 기능 구현 승인이나 기존 승인 범위 확장을 뜻하지 않는다.

## 1. 확정되어 적용할 원칙

| ID | 결정 | 근거·적용 상태 |
|---|---|---|
| D-001 | 실물·시뮬은 공통 로봇 업무 코드를 사용하고 환경 데이터·장치 연결을 분리한다. | 루트 AGENTS, 예찰 인수인계, 현행 bringup |
| D-002 | 새 시뮬 전용 코드·설정·시험·로그는 sim 안에 둔다. 공통 코드를 sim으로 복제하지 않는다. | 10/2 사용자 요청, 루트 및 sim/AGENTS |
| D-003 | 공통 코드 변경은 이유·대상·구체안·실물 영향·검증 방법을 제시하고 승인받는다. | 루트 AGENTS. 이번 문서 패키지는 실행 코드 변경을 포함하지 않음 |
| D-004 | Isaac, 로봇별 장치+Nav2+서버, RViz, 관제는 실행 단위를 분리한다. 시뮬 전용 all launch가 필요한 조합을 구성한다. | LAUNCH-SPLIT-20261002-006 및 현행 launch |
| D-005 | 8베드·16Section 확장을 유지하고 좌표·경로·station은 설정에서 로드한다. | sim/AGENTS, task.yaml, 복원 기록 |
| D-006 | 현재 수확은 목표 이동 후 SUCCESS/수확량 0. 팔 작업을 생략한다. | HARVEST-SIM-008, HARVEST-COMMON-009 및 contract.py |
| D-007 | 수확 업무 서버는 공통 harvest_robot에, Isaac 과실 정답 평가는 sim의 별도 노드에 둔다. | HARVEST-COMMON-20261002-009 |
| D-008 | ScoutArea 한 Goal은 한 Section. 수확 작업은 성공 Result에서 등록한다. 실패/취소 부분 목록은 자동 수확 전송하지 않는다. | PROTOCOL-20261006-014 및 현행 ScoutArea.action |
| D-009 | HarvestTask.msg는 task_id/window_id/goal_pose/expected_count. Window ID는 원문 그대로 전달한다. | PROTOCOL-20261006-014 및 contract.py |
| D-010 | 시뮬 정답 pose·과실은 평가·디버깅·합성 라벨에만 사용한다. 실제 배포 제어 입력으로 사용하지 않는다. | 초기 기획, sim/AGENTS, SceneTruth/평가 구조 |
| D-011 | 캐스터 보정은 고정 보조 구체 접촉면의 저마찰 모델링이다. 구동 바퀴·미션·Nav2를 함께 바꾼 수정으로 설명하지 않는다. | CASTER-FIX-20261006-013. 사용자 이동 정상 보고는 프로토콜 기록에도 남아 있음 |
| D-012 | 코딩은 로컬 Codex, 설계·논의·자료 작성은 ChatGPT 프로젝트에서 진행하고 저장소 문서로 인계한다. | 2026-10-06 사용자 요청. 운영 절차는 CODEX_HANDOFF.md |
| D-013 | 받은 로봇팔 묶음을 기준으로 농장 과실·오른팔 물리와 오른팔 기준 수확 이동 좌표를 먼저 적용한다. 과실은 Teacher 폭70mm/높이75mm·9g로 통일하고 기존 위치·회전·색·ID를 유지한다. | 2026-10-06 사용자 구현 요청 및 과실 크기 선택. sim/docs/ROBOTARM_PHYSICS_20261006.md |
| D-014 | 주행용 수확 로봇과 캐스터 보정을 유지한 채 오른팔 drive·집게 접촉·박스 바닥을 세션에 적용한다. 기준 줄기 물리는480Hz, 렌더60Hz다. 운용 주기/활성 영역은 이후 D-015를 따른다. 학습 정책·공통 수확 FSM 연결은 후속 단계이며 물리 분리를 수확 성공으로 보고하지 않는다. | D-013 구현. 공통 로봇/메시지와 실물 설정 변경 없음 |
| D-015 | 수확 활동이 없으면60Hz·부착 과실 고정, 팔 작업 중이면480Hz·오른팔 주변 영역의 합집합만 활성화한다. 시간·센서 주기는60Hz 프레임 기준으로 분리한다. 분리 과실은 동적으로 유지하고 정지 후 저주기로 복귀한다. | 2026-10-06 사용자 동적 주기/근거리 물리 승인. 구현·GPU 검사 완료. 실제 예찰 주행에서 주기 변경에 따른 약2.6cm 위치 차이를 확인했으며 동시 주행 무영향/정책 수확 완료로 간주하지 않음. sim/docs/ADAPTIVE_HARVEST_PHYSICS_20261006.md |
| D-016 | sim Teacher 수확 검증에 시뮬 과실 pose/내부 상태를 제공한다. 현재 정차 위치에서 도달 가능한 빨강·노랑을 각각1회 시도하고 일반 실패 뒤 다음 대상으로 진행한다. 녹색·차체 추가 이동은 제외한다. | 2026-10-06 사용자 좌표 제공 요청 및 “제안대로: 빨강·노랑, 과실당1회” 선택. D-010의 sim Teacher 검증 경로에 대한 명시적 예외이며 예찰/실물/Student로 확대하지 않는다. 실행 통합과 공통 변경·부분 성과 Result 의미는 아직 승인/구현 대기. sim/docs/TEACHER_HARVEST_INTEGRATION_REVIEW_20261006.md |

`D-001`~`D-011`의 상세 근거는 기존 문서·코드를 따른다. 이미 승인된 구체 작업은 같은 이유로 재승인 요청하지 않되, 새로운 기능·다른 파일·영향으로 확대하지 않는다.

### D-017 — 전달 Teacher를 시뮬 전용으로 연결 (2026-10-06)

- **사용자 확정 범위:** “대부분의 로봇팔 구동 코드가 시뮬레이션 전용 … 공통코드에서 도착하자마자 result를 날리는 형태면, 그부분은 수정해서 sim 전용 로봇팔 동작 코드에 연결”. D-016의 넓은 공통 Window 실행기·신규 후보조회/PickFruit 제안은 채택하지 않는다.
- 공통 harvest_robot은 기존 Navigator의 도착/정지 확인 후 설정된 내부 HarvestTask Action을 요청하고, 누적 피드백·실제 결과·취소 정지를 전달한다. 외부 HarvestTask 필드, farm_interfaces, 실물 설정·주행·비전은 유지한다. legacy ARRIVAL_ONLY_NO_HARVEST도 명시적으로 유지한다.
- sim의 별도 `sim/harvest_arm` endpoint는 기존 형식을 재사용한다. 지역 과실 활성화, 현재 팔 TF 기준 정답 좌표, 실제 접촉 관측, 4개 Teacher 추론, 물리 복귀·성공 판정·대상 순서는 모두 sim에 둔다. 정답 사용은 이번 Teacher에만 허용한다.
- 현재 정차의 연속 근거리 조건을 만족하는 빨강/노랑을 각1회 시도한다. 녹색·추가 차체 이동·실패 재시도는 하지 않는다. 일반 실패는 실제 복귀/집게 열림 확인 후 계속하며 접촉·이웃 분리·정지 미확인은 작업을 중단한다. `SUCCESS`는 후보 전체 처리 완료이고 수량은 실제 안착/실패 수다. 예상 수량 달성 자체를 성공으로 꾸미지 않는다.
- 현재 과실의 실제 충돌 외곽·바구니 내부·저속·손가락 비접촉·0.6초 안착을 성과로 집계한다. Teacher 엄격 성공은 별도 진단이다. 앞서 안착한 과실이 탈출하면 `FAILED/PREVIOUS_DEPOSIT_LOST`; 이미 발행한 누적 수량은 역행시키지 않는다.
- 상세 구현·실행·직접 검증/미검증은 [시뮬 Teacher 실행 보고서](../sim/docs/TEACHER_HARVEST_RUNTIME_20261006.md)를 따른다. main/1666a23 이후 미커밋이며 이번 변경의 커밋·푸시는 요청받지 않았다.

## 2. 과거 논의와 현행 구현을 구분할 사항

| 주제 | 현재 판단 |
|---|---|
| 토마토/파프리카 | 초기 문서는 토마토, 현행 Goal 검사는 PAPRIKA. 초기 명칭을 코드에 재도입하지 않음 |
| 수확 FollowPath 미사용 논의 | 과거 요청·논의가 있었지만 현재 코드와 10/2 이관 기록은 FollowPath 기반. 이번 문서는 이를 설명할 뿐 주행 정책을 바꾸지 않음. 변경하려면 의도·영향 확인 |
| Nav2 Route Server 전환 | 이전 검토 사항. 현행 코드가 ComputeRoute를 사용한다고 기술하지 않음 |
| 실시간 카메라와 합성 데이터 | 현행 시뮬 실시간 640×384/15, 합성 데이터 1280×720, 실물 설정 1280×720/6. 서로 다른 프로파일 |
| Window 이름 | SEC/Segment/Window 명명 설계와 현행 세션 접두사 포함 ID를 구분. 통신은 실제 받은 ID 보존 |
| 교통 제어 | 공용 경로 데이터·향후 실행 경계는 있으나 교통 제어 운영 구현과 동일하지 않음 |

## 3. 미확정·후속 작업

다음은 구현 승인 목록이 아니라 확인할 과제다.

| ID | 과제 | 먼저 확보할 내용 |
|---|---|---|
| O-001 | 최신 규약으로 전체 예찰→수확 큐 연결 | 동일 인터페이스 빌드 여부, 실제 Result/Goal 로그, 외부 관제 실행 방식 |
| O-002 | RobotStatus 발행 | 관제 필수 여부, 발행 주기·상태 의미·boot_id/sequence 계약, 담당 구현 범위 |
| O-003 | 실물 수확 연결 | 장치 bringup, TF·odom·cmd_vel, 실물 지도·graph·Nav2·환경 프로파일 |
| O-004 | 실물 비전 모델 갱신 | 사용할 모델 버전과 실제 worker 환경·파일 배치 경로 |
| O-005 | 예찰 중복 검출·Window 누락 | 최신 커밋·seed·scene·survey.json·정답 비교 결과로 재현 |
| O-006 | 운송·분류·도킹·교통 제어 | 팀 담당자 소스·통신규약·인계 조건·통합 시험 범위 |
| O-007 | 수확 팔 실제 작업 | 현장 재탐지, IK/정책, 파지·분리·적재 성공 조건. 현재 이동 전용 범위와 구분 |
| O-008 | D-017 시뮬 Teacher 물리 수확 평가 | 공통 변경은 최소 Action 연결만 승인·적용. 현재 정차 빨강/노랑 각1회 실행은 sim에 구현. 실제 농장 성공률, 실패 복귀, 최신 Nav2 도착을 포함한 전체 시험은 최신 PROJECT_STATE §20 및 실행 보고서를 따른다. |

## 4. 다음 결정 기록 양식

```text
결정 ID / 일자(KST):
상태: 제안 / 사용자 확정 / 구현 완료 / 검증 완료 / 폐기
논의한 문제:
결정 내용과 이유:
적용 범위: 공통 / 실물 / 시뮬 / 문서
승인 근거: 사용자 요청 또는 기존 승인 기록의 정확한 위치
실물·시뮬 영향:
구현 대상 파일:
완료 조건:
구현 커밋 / 아직 미커밋인 파일:
검증한 환경·명령·결과 / 미실행:
남은 문제:
```

확정 전 제안을 코드의 요구사항으로 취급하지 않는다. 구현 완료와 실제 시험 완료를 구분하고, 최신 상태는 PROJECT_STATE.md와 연결한다.

### D-018 — 수확 평행 접근 (2026-10-07)

사용자가 HARVEST_PARALLEL_APPROACH_20261007 제안에 “수정해”로 승인했다. 오른팔 정차선과 sim 수확 graph를 일치시키고, 환경 데이터의 진입/이탈 지점에서 정렬을 확인한다. 공통 기능은 parallel_approach=false 기본이며 sim harvest만 활성화한다. 실제 양쪽 도착 조건·정지 재측정을 만족한 재요청만 이동을 생략한다. 좁은 구간 자동 회전/후진 복구는 하지 않는다. 실제 신규 주행/회전 공간 검증은 PROJECT_STATE §24의 미검증 항목이다.


### D-REAL-RUNTIME-20261008 — 실물 실행 파일의 Git 관리

- 2026-10-08 사용자 “괜찮은것같아. 작업 진행해줘” 승인. 네 브랜치 feat/apriltag-localization에서만 카메라 실행 파일·캘리브레이션을 프로젝트에 포함하고 경로를 전환한다.
- 기존 드라이버 워크스페이스는 유지하고 정확한 원본 커밋과 현장 패치를 보존한다. OS·ROS 패키지·장치 규칙은 별도 설치 환경이며 이번 변경이 전체 시스템 이미지 재현을 보장하지 않는다.
- PC /home/eunbi/vmany/main에서 Git 관리, 로봇 /home/vic/vmany/main으로 소스 동기화, 로봇에서 빌드한다. 역방향 변경은 PC 반영 후 커밋한다. 양쪽 변경을 확인하지 않은 덮어쓰기·--delete 동기화는 하지 않는다.
- 실물 검증 전 외부 카메라 폴더는 삭제하지 않는다. 시뮬 코드·업무 FSM·주행/태그 보정 계산은 이번 범위에 포함하지 않는다.

### D-REAL-SHELL-20261008 — 실물 실행 별칭 Git 이관 — 2026-10-08

- 승인 근거: 사용자의 남은 외부 의존성을 Git 폴더에 맞춰 반영해 달라는 요청.
- 실물 bringup/navigation 별칭 원본은 robot/config/robots/vicpinky/shell.bash에서 관리하고 로봇 .bashrc가 source한다.
- 기존 드라이버 워크스페이스와 ROS 환경 로딩을 유지한다. 셸 설정은 별칭만 정의하며 source만으로 로봇을 실행하지 않는다.
- 비활성 로그 함수는 이식하지 않는다. 보정 잠금은 기존·새 코드의 중복 실행 방지를 위해 이번 변경에서 유지한다.
- PC 별칭 정의와 로봇 새 셸 연결은 사용자 출력으로 확인했다. 실제 bringup/navigation 구동 검증은 이번에 하지 않았다.

### D-APRILTAG-LOCK-20261008 — AprilTag 잠금 경로 전환 — 2026-10-08

- 사용자 “기존 코드는 사용안하는거지” 및 “수정해줘”에 따라 기존 시험 코드와의 잠금 호환을 종료한다. 앞선 잠금 유지 결정을 대체한다.
- 운영 체크아웃의 project_root/runs/locks에 robot_id별 고정 잠금 파일을 생성한다. 실행별 세션 폴더에는 두지 않는다.
- 같은 로봇의 보정은 지정한 운영 체크아웃에서만 실행한다. 예찰 코드·주행 및 보정 알고리즘은 이번 변경 범위가 아니다.


## AprilTag 실행 연결 검토 — 2026-10-08

- 기준 feat/apriltag-localization / aa18b2c, 사용자 전체 검토·다른 코드 보존 요청. 이번 수정 미커밋·원격 미반영.
- 충돌 2곳 결합(사용자 적용본과 동일), Route Server 빈 배열 제거, 실물 Nav2 종료 기준 4cm/2.5도(미션5cm/3도 유지), 캡처 종료 실패 전파 및 사전 검사 추가.
- 예찰·공통 farm_navigation 소스·팔/시뮬 알고리즘 불변. sim 기록의 기존 충돌 표시 미수정.
- 직접 오프라인 72검사 및 사전 검사 PASS. 설치 ROS/실물 재검증 미실행. detector/rectify -11은 미해결.
- 상세 대상·검증·복원·다음 실행: docs/changes/APRILTAG_RUNTIME_REVIEW_20261008.md.


## ComputeRoute 설치 메시지 호환 — 2026-10-08 후속

- 사용자 로봇에서 두 패키지 빌드 성공. 설치 사전 검사에서 ComputeRoute.Result에 error_msg가 없는 것을 확인했다. 실제 필드는 planning_time/path/route/error_code이고 Feedback은 비어 있다.
- route_server.py는 status와 error_code로 실패를 판정·보고하며 error_msg는 존재할 때만 추가한다. 성공 경로 처리와 오류 거절은 유지한다. 검사도 필수 필드를 path/error_code로 맞췄다.
- 이전 가짜 응답에만 있던 error_msg를 제거하고 실제 필드 형식으로 검사했다. 태그42개·수확31개 오프라인 검사 PASS. 실물 재기동·ComputeRoute 호출은 아직 미검증이다.
- 예찰·공통 farm_navigation·팔 코드 변경 없음. 이번 파일만 백업에서 복원 가능. 미커밋·푸시 없음.


## 수확 작업 FollowPath 전환 — 2026-10-08

- 사용자 scout_new 기준 재확인 후 “지금 확인한 사항대로 코드 다시 수정” 승인. 이전 미적용 corridor 패치는 사용하지 않는다.
- 실물 harvest_real.json은 route_then_follow. 진입 ComputeRoute+FollowPath 유지, 작업·출구는 공통 RouteGraph Dijkstra/path_builder/Nav2Client FollowPath 재사용.
- harvest node·launch 조건·section 입력 검사 연결 수정. 기존 route_then_pose는 명시적 이전 환경 호환, graph_only와 시뮬 설정은 유지. 새 C++ planner/BT/10cm 이탈 제한 추가 없음.
- 예찰·공통 farm_navigation·지도·graph·20cm 명목 배치·Nav2/보정 계산·속도·팔 정책·메시지 변경 없음.
- 직접 오프라인 수확41개 + 태그44개 검사 및 정적 검사 PASS. ROS 빌드/Action/실물 검증 미실행. 태그 보정 후 흔들림·시간 보상 경고·카메라 종료 -11 해결 완료로 주장하지 않는다.
- aa18b2c 조회본에 이전 runtime/ComputeRoute 호환 수정이 적용된 작업본 기준. PC/로봇 직접 적용·commit/push 없음. 상세 docs/changes/HARVEST_FOLLOW_PATH_20261008.md. 복원은 백업의 이번 파일만 사용한다.

## 공용 실물 지도·그래프와 14번 주행 연결 — 2026-10-09

- 사용자 승인: 최근 Confluence 지도/그래프 명세와 예찰 적용본에 수확을 맞추고 14번까지 시험 준비. 예찰 소스/설정은 변경하지 않는다.
- 기준: feat/apriltag-localization에 사용자 적용한 harvest_follow_path_fix 이후 수정본. PC 현재 HEAD/미커밋 상태를 직접 조회한 것은 아니며 적용 시 대상 해시를 검사한다.
- 실물 예찰이 읽는 maps/many_farm의 지도·전체 21노드/46엣지를 수확도 직접 참조한다. 지도 바이트는 기존 수확 지도와 동일. 그래프는 300cm 기준으로 변경되며 x=1.188, 14=(1.188,-4.02). 과거 x=1.198/13번 종료 시험과 구분한다.
- map_id는 실제 scout_real.yaml의 many_farm_v1을 따른다. 수확 환경·장치·작업·보정 설정만 동기화한다. 문서의 farm_map_v1 표기와 차이는 상세 보고서에 남겼다.
- approach_planner=graph로 진입도 기존 공통 RouteGraph의 선분 투영/다익스트라→FollowPath를 사용. Route Server 미사용이며 해당 노드/관리자를 띄우지 않는다. 기존 명시적 route_server 환경은 유지한다.
- 진입11번 완료/정지→작업14번의 단계 구조는 유지한다. 예찰·farm_navigation·Nav2 설정·태그 좌표/카메라/외부파라미터·보정 계산·실물 드라이버·시뮬 실행 설정 변경 없음.
- 오프라인 수확48/AprilTag46 PASS, 모든 노드쌍441 및 방향엣지 중간점→11/14 92개 연결 검사 포함. 로봇 ROS 빌드/실제14번 주행/회전 여유·20cm 실측 유지·보정 효과는 미검증. 종료 -11과 AMCL 시각 경고는 별도 미해결.
- 상세: docs/changes/HARVEST_SHARED_MAP_20261009.md. 원복은 적용 도구의 runs/review_backups/shared_map_* 백업에서 이번 파일만 복구한다. commit/push·로봇 동기화·실제 이동은 하지 않았다.

## 수확 11번 진입 제어 분리 — 2026-10-09

- 기준: feat/apriltag-localization / 9fefb4828e18215282cdf262d7d7a83a0f9244ef. 사용자 “그렇게하자”로 진입 접근 제어만 수정 승인.
- 실물 harvest_real.json의 approach_controller_id=HarvestApproach. SECTION_APPROACH만 선택하고 WINDOW_MOVE/SECTION_EXIT는 기존 RPP다. 설정이 없는 기존 환경은 기존 controller_id를 사용한다.
- 추가 프로파일은 기존 RPP에 고정 곡률 참조 0.4m와 마지막 선분 방향 연장을 적용한다. Path/목표 좌표를 연장하지 않는다. 공통 Navigator/Nav2Client의 기존 controller_id 전달을 사용한다.
- 11번 정밀 도착·정지, Nav2 4cm/2.5도 및 미션 5cm/3도, 충돌 검사·costmap·footprint·태그 계산·지도·그래프는 그대로다. 실측 차체 옆면–화단 벽 20cm 기준을 새 중심 간격으로 치환하지 않았다.
- 수확 56개·AprilTag 46개 오프라인 검사와 check_runtime PASS. 녹화 경로 340개에 대한 Jazzy 참조점 계산 비교 완료. 실제 ROS 제어기/실물 재주행은 미실행이다.
- 이 변경은 진입 끝점에서 반대 방향으로 돌아가는 계산 원인을 줄이는 수정이다. 충돌 예측 실패 전체·태그 정확도·종료 -11 해결 완료로 해석하지 않는다.
- 상세: docs/changes/HARVEST_ENTRY_CONTROL_20261009.md. 복원은 approach_controller_id 키 제거로 기존 RPP 선택 후 수확 노드를 재시작한다. 문서/코드 전체 복원은 저장소 밖 적용 백업의 이번 파일만 사용한다. commit/push·로봇 동기화·실행은 자동 수행하지 않는다.

## 수확 작업 좌표 접근 안정화 — 2026-10-09

- 기준: feat/apriltag-localization / 7689f3648007c643f01a2dcaee160ae6fcbefcdd. 사용자 19:02 단계별 수정·검증 진행 요청으로 적용본 준비.
- 목표 동작: 태그로 위치 추정을 보조하면서 주행 중 차체 옆면–벽 20cm 기준 경로를 유지하고, 각 수확 좌표에서는 큰 회전 없이 감속·정지한다. 20cm는 실측 기준이며 제어기의 보장값이 아니다.
- 1단계 변경: 진입 HarvestApproach 유지, 모든 WINDOW_MOVE에 HarvestWork 선택, SECTION_EXIT는 기존 RPP 유지. work_controller_id가 없는 환경은 기존 선택을 유지하며 graph_only/route_then_pose에는 새 작업 설정을 적용하지 않는다.
- 수확 node.py와 staged_navigation.py에서 작업·이탈 연결을 분리하고 종료 시 별도 Action client를 닫는다. Nav2Client/Navigator/RouteGraph를 그대로 사용하며 예찰·공통 주행·FSM·메시지·팔 코드를 수정하지 않았다.
- 속도·도착 허용치·실제 목표 yaw·충돌 검사·costmap·지도·태그 계산 불변. RPP 기존 프로파일도 그대로이며 HarvestWork만 고정 곡률 참조 0.4m/마지막 선분 연장 기능을 사용한다.
- 오프라인 수확 60개/AprilTag 46개 검사 및 check_runtime PASS. 실패 로그 작업 Path 1,019개 참조점 계산 비교: 819개 동일, 끝점 근처 200개 연장. ROS 전체 제어기·실물 주행 검증을 대체하지 않는다.
- 이번 파일의 로봇 동기화·빌드·실물 실행은 미실행. Git commit/push는 자동 수행하지 않았다.
- 후속: 새 설정 단일 목표 1회에서 끝점 동작 확인 후 짧은 연속 작업 좌표 시험. 같은 증상이 재현되면 반복 전 로그 분석. 태그 시각 경고·costmap 적정성·카메라 종료 -11은 별도 미해결.
- 복원: work_controller_id 키 제거 후 수확 노드 재시작으로 작업 제어기 RPP 선택. 전체 복원은 ~/vmany_backups/harvest_work_*의 이번 파일만 사용한다.
- 상세: docs/changes/HARVEST_WORK_CONTROL_20261009.md.

## 수확 태그 보정 라이다 시각 연결 — 2026-10-09

- 사용자 “그 방법대로 연결해보도록 하자” 승인. 원격 7689f36 및 이후 적용한 HarvestWork 기준이다.
- 수확 real+tag_correction=true에서 farm_tag_amcl을 선택하고 작업 토큰·라이다 시각을 맞춰 보정한다. 공유 launch의 기본값은 기존 nav2_amcl로 유지한다.
- 예찰/scout_new·공통 주행 알고리즘·지도·벽 간격 20cm·제어기·costmap·도착 허용오차·드라이버는 변경하지 않았다.
- 직접 검사: 태그/launch 50개, 수확 60개, 실제 ROS 22개 PASS. CMake/ament 빌드·설치 PASS. 주행 녹화의 보정 12/12 적용, 보정 관련 TF 경고 12→0; 수동 초기 위치 경고 1회는 별도다.
- 로봇 arm64 빌드·실물 폐루프 주행·벽 간격 정확도·카메라 종료 -11 해결은 미검증. PC 백업은 저장소 밖에 유지하며 commit/push·로봇 복사·실행은 하지 않았다.
- 복원은 실행 종료 후 correction_transport: initialpose로 전환한다. 상세 계약·검증·다음 작업: docs/changes/HARVEST_TAG_SCAN_SYNC_20261009.md. 전달물 RUN.md에 로봇 빌드·독립 ROS 검사·RViz·실행·로그 명령을 포함했다.

## 수확 태그 화면 위치 편향 비교 시험 — 2026-10-10

- 승인: 사용자 “지금 중요한건 태그로 인한 보정이 잘 들어가느냐야…주행 해 볼수 있도록 준비해”. 관측 보상 전후를 비교하는 선택적 실물 시험이다.
- 기준: scan_sync 적용본과 사용자가 전달한 로봇 node.py의 SHA256 42ce10c433bd5ce05f2bf2696d4ee1299fe3a09748cc82244fbe28e2833f7eba. 현재 PC HEAD/원격을 직접 조회한 것은 아니다. 적용 시 코드 해시를 검사하고 기존 문서에 이 절만 추가한다.
- 새 pixel_bias.py·시험 프로파일·시험 실행/기록 도구, tag adapter의 선택적 관측 보상 연결을 추가했다. 기본 설정은 OFF. trial.bash launch on에서만 실행 당시 환경 복사본으로 ON을 선택한다.
- 촬영 시각의 태그 map pose에 화면 가로 위치 기반 벽 법선/각도 편향을 보상하고 기존 odom 이송·잔차 제한·scan_sync AMCL 적용을 거친다. 원본 관측·보상량·실제 수신 적용을 별도로 기록한다. 기존 공분산은 축소하지 않았다.
- 학습 자료는 20261010_162411 녹화의 74개 관측/태그 100–105. 화면 중심 x=388.045–889.780px 범위만 사용하며 범위 밖/미검증 태그는 해당 보정만 생략한다. 주행 중단 조건을 추가하지 않는다.
- 예찰/scout_new·farm_navigation·launch·지도·카메라 캘리브레이션/장착값·제어기·costmap·도착 조건·실물 드라이버는 변경하지 않았다. 20cm는 차체 옆면–벽 실측 기준으로 유지한다.
- 단일 녹화에서 태그 하나씩 제외해 학습한 오프라인 비교에서 거리/각도 RMS가 감소했다. 기준은 라이다 평면이며 독립 실측 정답이 아니다. 별도 주행에서의 개선·20cm 유지·실제 ROS 연결은 이번 패치로 아직 검증하지 않았다.
- 직접 검증: 태그 기존/신규 오프라인 검사, 녹화 프레임의 production _solve/_send 연결, 보상 OFF 동일성, 단위/부호/시각 이송 순서, 범위 밖 보정만 생략. 상세 결과는 HARVEST_TAG_BIAS_VALIDATION_20261010.json 및 전달물 VALIDATION.md.
- 다음 시험은 10번 부근 동일 초기 자세에서 ON 한 번, 필요 시 OFF 한 번 비교. goal 도구가 주행 로그/rosbag을 수집한다. 적용 수와 실제 벽 간격 추세를 함께 평가한다. 단순 SUCCESS로 정확도 완료 처리하지 않는다.
- 복원: 기존 harvest_real.yaml로 실행하거나 trial.bash launch off. 기존 설정 파일을 수정하지 않으며 저장소 밖 ~/vmany_backups에 적용 전 파일을 보관한다. commit/push·로봇 복사·빌드·주행은 자동 실행하지 않았다.


## 수확 태그 기준 고정 및 모터 지연 영구 설정 — 2026-10-10

- 사용자 승인: 태그 보정 정상 수행을 기록하고 추가 반복 주행 없이 다음 단계로 전환. 모터 latency_timer 16→1을 영구 설정하도록 요청.
- 기준: PC 제공 HEAD 7689f3648007c643f01a2dcaee160ae6fcbefcdd + harvest_git_review_20261010_174503.tar.gz의 미커밋 변경. 기존 변경을 보존했다.
- 실제 ON 주행: 14번 SUCCESS, 요청/queued/applied 10/10/10, 전달 식별자·pose 일치. 라이다 대비 관측 오차 감소. 물리적 20cm 유지·카메라 정상 종료는 미완료.
- 사용자 관찰: 출발 간격 약20cm, 주행하면서 벽에서 점차 멀어짐. 태그/그래프 벽 기준 1cm 차이 및 base–차체 간격은 후속 정합 항목.
- 새 상세 기록: docs/changes/HARVEST_TAG_HANDOFF_20261010.md. 원본 수치와 이번 재계산을 분리했다. 원본 로그·패치 파일명/해시를 보존했다.
- 새 설정/도구: robot/config/robots/vicpinky/udev/99-vicpinky-motor-latency.rules, robot/tools/vicpinky_motor_latency.py. FTDI 0403:6001 / BG02QM7Y만 latency_timer=1. 기존 /dev/motor·권한 규칙 유지.
- 이번 변경은 문서·실물 모터 설정에 한정. 예찰·기존 공유 launch·주행·보상 알고리즘·지도·제어기·costmap 불변. 시뮬 실행 영향 없음.
- 검증: 이번 로그 재분석 및 전달물 오프라인 검사는 HARVEST_GIT_FREEZE_20261010.md 참조. 새 udev 규칙의 로봇 설치/재부팅·재연결은 미실행이며 설치 도구의 CHECK_OK 후에도 실제 재부팅 검증과 구분한다.
- 복원: 새 설치 도구 remove는 자기 규칙만 제거하고 현재 모터 latency_timer=16 복원. PC 문서 복원은 /home/eunbi/vmany_backups 적용 백업과 비교해 이번 변경만 되돌림.
- commit/push·로봇 설치 미실행. 은비가 VS Code에서 반영 후 Confluence에서 확정 커밋을 연결한다.

## 관제 좌표 수신 연결 준비 — 2026-10-10

- 사용자 승인: 관제에서 좌표를 받아 이동하도록 연결 준비. 후속 확인에 따라 수확 ROS_DOMAIN_ID=156 유지. README의 일반 실물 77을 수확에 일괄 적용하지 않는다.
- 기준: main 저장소 feat/apriltag-localization 25cdf88, Control/web_integration 337c2d5, Frontend/main 5909f0d. PC/로봇 설치본은 이번에 직접 조회하지 않았다.
- 수확 서버는 기존 HarvestTask Goal의 section_id를 요구한다. 관제 터미널 ManualHarvest·RosAdapter 및 웹 ControlQueue 송신부와 각 관제 저장소의 Action 정의를 이 형식에 맞추는 패키지를 준비했다. HarvestTask.msg/ScoutArea와 예찰 scout_new는 변경하지 않는다.
- 수확 주행·태그 보정·지도·제어기·costmap·모터·launch 변경 없음. 관제 미션의 좌표·yaw·ID·배열/사용자 선택 순서를 그대로 전달한다. real 완료 정책은 ARRIVAL_ONLY_NO_HARVEST: SUCCESS는 이동 완료, harvested_count=0.
- 직접 검증: Control 오프라인 68개 PASS, 웹 실제 큐의 Section/좌표/ID 전달·도착 수량0·재전송 거절 검사 1개 PASS. 생성 ROS 메시지/CDR·DDS·실물 연동은 미실행.
- 관제 문서의 Domain 기준은 README 77 / FULL_PIPELINE 156으로 다르다. 웹 Git 기본 설정은 real=77이며 환경 변수로 변경 가능하다. 현재 웹 worker는 환경당 단일 Domain이므로 로봇별 별도 Domain 연결이 구현됐다고 주장하지 않는다. 수확156을 유지하고 관제의 실제 수확 연결 Domain을 실행 시 확인한다.
- 적용·빌드·PC RViz·초기 위치·Goal·rosbag·로그 수집·로봇→PC 복사는 docs/changes/HARVEST_CONTROL_LINK_20261010.md를 따른다. 백업은 /home/eunbi/vmany_backups만 사용하며 파일 해시 불일치 시 전체 적용 전 중단한다. commit/push·실물 실행은 수행하지 않았다.


<!-- HARVEST_CONTROL_READY_20261010 -->
## 관제 좌표 수신 정합 수정 — 2026-10-10

사용자 “좌표받아서 갈수있도록 코드 분석해서 준비” 승인 범위. 준비본·미커밋이며 PC/로봇 설치와 실주행은 별도다.
기준 Git: main feat/apriltag-localization 25cdf88 / Frontend main 5909f0d.

이 기록은 앞서 HARVEST_CONTROL_LINK_20261010.md의 Domain156 및 예찰에 many_farm_v1/SEC_01을 보내라는 안내를 정정한다.
현재 통신 Domain은77(사용자 변경 완료 보고), 카메라 별도 환경은 유지한다.
관제/예찰 통신은 farm_map_v1/SEC01 그대로다. 예찰과 수확 환경 YAML은 같은 maps/many_farm/many_farm.yaml 및 graph.geojson을 참조한다.
수확 내부 many_farm_v1/SEC_01과 태그 기준은 보존하고 harvest_real.json control_aliases에 위 두 ID의 명시적 대응을 추가한다.
contract.py에서 지도/구역을 검사하고 mission.py에서 구역을 해석한다. 원본 Goal·좌표·yaw·작업 ID는 변경하지 않는다.
등록되지 않은 지도/구역 거절 유지. 별칭 설정 없는 시뮬 등은 기존 계약 유지.
Frontend control_core.py와 HarvestTask.action의 section_id 전송을 맞춘다. Control 키보드 관제 패치도 포함하나 웹은 Frontend 패치가 필요하다.
각 저장소에 패치 적용 및 인터페이스 재빌드/프로세스 재시작이 필요하다. 이전 패키지의 project 문서4개 적용만으로 관제 수정이 완료된 것이 아니다.
예찰 scout_new·지도·그래프·태그 보상·Nav2·footprint·제어기·모터 설정은 수정하지 않는다.
수확의 현재 SUCCESS는 도착/정지 성공이며 실제 수확량은0이다. 물리적20cm 유지 및 카메라 종료 문제는 동결 기록의 후속 과제다.
직접 검사 및 미실행 범위는 전달물 VALIDATION.md, 배포/실행/로그는 RUN.md를 따른다.
복원: PC /home/eunbi/vmany_backups의 이번 파일만 비교 복구하고 harvest_robot 재빌드. 관제 인터페이스를 되돌리면 의존 노드도 함께 재빌드한다. commit/push 자동 수행 없음.

### 공유 DM의 통신 문서 대조 및 Status 추가

공통11796484(v18), 수확4358169(v37), 인계16908315(v10)를 직접 읽었다.
/harvest_01/status RobotStatus를 실물 이동 전용 정책에서1초마다 발행한다. boot_id는 프로세스마다 새 UUID, sequence는 발행마다 증가한다.
관제 map_id=farm_map_v1, 실제 최신 map→base TF, 현재 task_id, IDLE/NAVIGATION_MOVE/ERROR와 ready를 보고한다.
ready는 작업/종료/정지 미확정 여부, 유효 TF, FollowPath 서버 발견을 반영하며 실제 Goal의 기존 preflight 검사를 대체하지 않는다.
이동 전용 단계에서는 transfer_required=false, loaded_count=0으로 보고한다. 이는 수확/적재 기능이 없는 현재 운용 값이며 실제 적재 센서 검증 완료를 의미하지 않는다.
문서 규약상 수확 인계가 필요하면 true를 유지하고 인계 완료+적재 해소 확인 후 false로 바꿔야 한다. 실제 dock_transfer/transfer_event/배출장치/FSM은 이번에 구현하지 않았으며 가짜 완료 신호를 발행하지 않는다.
배터리 입력은 설정 battery_topic의 sensor_msgs/BatteryState.percentage(0–1)를 사용한다. 현재 실제 드라이버의 topic/percentage 제공 여부는 확인되지 않았다.
미수신/NaN/5초 만료 시 battery_percent=0.0은 미측정 자리값이며 error_code/error_message에 BATTERY_UNAVAILABLE을 명시한다. 이 값으로 잔량0%를 표시하거나 저전압 동작을 트리거하면 안 된다. 프로토콜에 unknown 필드가 없다는 한계가 남아 있다.
위치 미확인도 POSE_UNAVAILABLE+ready=false로 보고한다. 상태 발행 실패/태그 누락을 새 주행 중단 조건으로 연결하지 않는다.
인계 문서의 harvester_01 표기는 최신 수확 문서 및 Git의 harvest_01과 다르므로 현재 endpoint는 harvest_01을 유지한다.
수확 프로토콜 문서에는 section_id가 빠져 있고 현재 수확 Git은 요구한다. 이번 전달물은 Git의 확장 필드를 유지하며 Frontend도 맞추는 방안이다. 문서와 완전히 일치한다고 주장하지 않으며 인터페이스 변경 사항을 관제 담당자에게 전달해야 한다.


<!-- HARVEST_RECEIVER_COMPAT_20261010 -->
## 기존 관제에 수확 수신부를 맞춤 — 2026-10-10

사용자 승인: 관제를 수정하지 말고 수확 쪽을 맞출 것. 앞선 ready 패키지 PC 적용·로봇 빌드 완료 보고 후 후속 수정이다.
앞선 HARVEST_CONTROL_LINK / HARVEST_CONTROL_READY의 frontend.patch 전달·관제 재빌드 지시는 철회한다. 이 패키지에는 관제 패치가 없다.
기준 관제: Frontend main 5909f0d 원본. 수확: feat/apriltag-localization 25cdf88 + 앞선 ready 적용본.
수확 farm_interfaces/HarvestTask.action에서 추가 section_id를 제거해 원래 Frontend Action과 바이트 동일하게 맞춘다. HarvestTask.msg/ScoutArea/예찰 소스는 변경하지 않는다.
수확 실물 설정의 default_section_id=SEC_01을 명시하고 단일 구역 설정에서만 Section 없는 Goal을 처리한다. 여러 구역/설정 누락은 추측하지 않고 거절한다. Window ID 파싱 없음.
관제의 farm_map_v1을 기존 내부 many_farm_v1에 연결하는 명시적 별칭과 Status 1Hz는 유지한다.
실제 받은 좌표/yaw/task_id/window_id/expected_count 보존. 기존 태그/지도/제어기/footprint 불변.
시험용 harvest_graph_goal.py도 section_id 없는 형식으로 맞춘다. 좌표 생성 기준은 기존 그래프이며 이번 관제 실행에서는 이 시험 Goal을 사용하지 않는다.
현재 실물 단일 구역 연결만 지원한다. 다중 구역 시뮬 등 기존 확장 Section 의존 클라이언트는 이번 Action 변경 영향이 있으므로 그 환경에 바로 배포하지 않는다. 후속 다중 구역 설계 없이 ID를 파싱하지 않는다.
실물에서 현재 팔 정책은 ARRIVAL_ONLY_NO_HARVEST. 도착 SUCCESS와 실제 수확/운송 인계를 구분한다.
검증: 원본 Frontend ControlQueue에서 생성한 Section 없는 Goal2개 → 수확 계약/미션/실제 RouteGraph → 원본 관제 Result 처리 PASS. 실제 DDS/ROS 빌드/이동은 이번 환경에서 미실행.
관제는 재빌드/수정하지 않는다. 로봇은 farm_interfaces와 의존 패키지를 재빌드하고 재시작한다. 이미 ready를 빌드한 상태도 적용기가 허용한다.
백업은 PC /home/eunbi/vmany_backups만 사용한다. 코드 원복은 이번 백업과 비교하고 관련 인터페이스를 다시 빌드해야 한다. commit/push 자동 수행 없음.


<!-- HARVEST_TF_RECOVERY_20261011 -->
## 수확 TF 오류 복구 대기 — 2026-10-11

- 승인: 사용자가 TF 장애 시 정지 상태로 최대 10초 대기·회복 후 재개에 “그렇게 해보자”라고 승인.
- 기준: harvest_receiver_compat 적용 소스 복사본. 로봇 13:02 주행 로그에서 SECTION_APPROACH TF_ERROR 확인. 현재 PC Git HEAD/미커밋 변경은 직접 조회하지 않았으며 배포 시 기존 파일 SHA256을 검사한다.
- 공통 farm_navigation의 nav2_client/navigator/pose_provider/navigation_types 및 새 tf_recovery.py, 수확 실물 harvest_real.yaml 수정.
- 기본 복구 OFF. 수확 실물 설정만 ON/10초. 예찰·시뮬은 기존 정책 유지. Action 형식·카메라·태그 검출·보정·경로 좌표는 유지.
- Nav2 FollowPath가 ABORTED + TF_ERROR로 종료 응답을 준 경우만 재시도. 미확정/취소/장애물/진행 실패는 자동 재시도하지 않는다. error_code도 실패 로그에 남긴다.
- 자신의 Nav2 Goal 종료 확인 후 cmd_vel_nav와 cmd_vel에 0을 반복 발행. 최신 0.1초 전 map→base TF 연결과 최신 odom의 정지를 확인하면 같은 경로를 재전송한다. 기존 goal_timeout_s도 전체 재시도에 적용한다.
- TF 오류 응답 이후 연속 복구 구간 최대 10초. 실제 제어 Feedback이 다시 발생한 뒤 새 TF 오류가 발생하면 새로운 구간으로 본다. Feedback 없는 반복 실패는 제한을 초기화하지 않는다.
- 외부 HarvestTask는 계속 실행 중이며 성공을 조작하지 않는다. 기다리는 중에도 취소·종료 검사. TF_RECOVERY_WAIT/RESUME/TIMEOUT을 rosout에 기록한다.
- 직접 검증: verify.py 7개 오프라인 검사 통과 (2.4초 회복, 10초 만료, 취소, 반복 TF 실패 제한, 다른 오류 즉시 실패, 설정 검증, 운영 Nav2Client TF 분류·동일 경로 재전송). ROS I/O는 대역. compileall 통과.
- 전체 기존 통합 시험은 복사본에 지도 YAML 등 런타임 자산이 없어 실행 완료하지 못했다. 실제 로봇 colcon·주행·정지 응답 시간은 미검증. 지연 원인 자체를 해결하는 변경은 아니다.
- 반영: 전달 패키지만 생성. commit/push·로봇 배포·빌드 미실행. 적용 도구가 문서에 이 내용을 추가한다.
- 되돌리기: 실물 환경 navigation.tf_recovery_enabled를 false로 설정 후 launch 재시작. 완전 복원은 PC vmany_backups의 적용·배포 백업을 사용한다.
