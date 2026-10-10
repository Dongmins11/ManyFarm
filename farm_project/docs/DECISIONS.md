# 설계 결정 및 미확정 사항

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
