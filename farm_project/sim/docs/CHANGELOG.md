# 시뮬레이션 통합 변경 이력

시뮬 전용 변경과 시뮬 통합에 필요한 공통 변경을 기록한다. 공통 변경은 사용자 승인 전 적용하지 않는다.

## SIM-DOC-20261002-001 — 인수 검토 및 작업 규칙 기록

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 문서·작업 규칙. 실행 코드·설정 변경 없음 |
| 기준 자료 | 사용자 첨부 `farm_project.zip`, `SUMMARY_인수인계서.md`, 프로젝트 기획·시뮬레이션 파트 문서 |
| 승인 근거 | 이번 사용자 요청: 변경사항 검토, 시뮬 전용 변경의 폴더 분리, 공통 코드 사전 확인 및 변경 기록 |
| 대상 파일 | `AGENTS.md`에 규칙 추가, `sim/AGENTS.md`, 이 문서, `sim/docs/INTEGRATION_REVIEW_20261002.md` 추가 |
| 이유 | 실물 담당자 소스를 기준으로 시뮬 통합을 시작하면서 실물·공통 코드에 대한 영향과 승인 범위를 명확히 하기 위함 |
| 변경 전후 | 기존 구현 합의를 보존하고 시뮬 수정 위치, 공통 변경 승인, 변경 기록 기준을 추가 |
| 실물 영향 | 실행 소스·설정·모델·메시지·실물 자산 변경 없음 |
| 직접 검증 | 기존 오프라인 시험 44개 통과. 두 환경 설정 로드 성공. 시뮬 그래프 128노드/112엣지/16개 약연결 성분, 실물 18노드/40엣지/1개 약연결 성분 확인 |
| 미실행 | ROS 2 빌드·통신, 새 State 흐름 전체 시험, VisionRuntime 시험, YOLO 실행, Isaac Sim 통합, 실물 주행 |
| 복원 | `AGENTS.md`의 이번 추가 절만 제거하고 이번에 추가한 `sim/AGENTS.md`와 문서 2개를 제거. 다른 변경이 누적된 뒤에는 해당 기록의 변경분만 되돌릴 것 |

원본 ZIP SHA-256:

`ca092228082a9e47b6fa79de8878408923f82d9ca9dbfa328811811a65728b24`

공통 실행 코드 수정 승인을 받은 항목: 없음.

## SIM-CONFIG-20261002-002 — 시뮬 설정 실제 분리

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 시뮬 설정·진입점·출력 경로. 공통 ROS 실행 소스 및 실물 설정 변경 없음 |
| 승인 근거 | 사용자 후속 요청: “시뮬레이션 설정은 sim 폴더안에 있어야돼. 명확히 분리해” |
| 승인 범위 해석 | 시뮬 전용 설정 이동, 필요한 기존 경로 참조 갱신. 공통 업무 로직 변경 승인으로 확대하지 않음 |
| 설정 이동 | `robot/config/vision/scout.json` → `sim/ros_ws/src/farm_sim_config/config/scout_vision.json`. 이전 경로의 설정 파일·링크는 제거 |
| 환경 선택 | `scout_survey.json`이 새 영상 설정을 참조. `scout_runtime.yaml`에 시뮬 `rviz_config` 추가 |
| RViz 분리 | `sim/.../farm_sim_config/config/scout.rviz` 추가. `sim/.../farm_sim_runtime/launch/scout.launch.py`에서 공통 bringup과 별도로 선택하여 한 번 실행 |
| 비전 진입점 | `sim/tools/run_scout_vision.py`에서 기본 설정 선택. 기존 루트 스크립트는 인자를 그대로 전달하는 호환 진입점으로 변경 |
| 외부 참조 갱신 | `scripts/run_scout_vision.py`, `tests/test_scout_survey.py`만 시뮬 외부 실행/시험 파일로 변경. 기존 시험은 survey의 `vision_config`를 읽도록 수정 |
| 출력 분리 | 예찰·단독 비전·합성 데이터 기본 출력을 각각 `sim/runs/scout_survey`, `sim/runs/scout_vision`, `sim/runs/scout_dataset`으로 변경 |
| 평가 도구 | `--survey latest`는 시뮬 결과 폴더만 검색. 기존 결과는 명시 경로로 읽을 수 있음 |
| 패키징 | 새 설정·launch는 기존 glob으로 설치. 시뮬 runtime의 실행 의존성만 추가 |
| 실물 영향 | `robot/ros_ws/src/`, 실물 설정·모델·센서 값·메시지·공통 알고리즘은 유지. 기존 실물 launch와 기존 결과 데이터도 유지 |
| 검증 | 기존 오프라인 44개 통과. sim/real 환경 로드 성공. 수치·ID·모델 선택·그래프 참조 보존. 공통 ROS/실물 설정/모델 124개 파일 원본 동일. 실행 객체를 대체한 launch 구성 4조건·외부 설정 거절 4조건, 비전 함수만 대체한 신·구 CLI 인자 전달 6조건 통과. 변경 Python 문법 및 패키지 XML 확인 |
| 미실행 | ROS 2 빌드 및 실제 launch, Isaac·YOLO·실물 실행 |
| 복원 | 적용 전 설정·진입점·시험·sim 패키지 파일로 되돌리고 이번 추가 파일만 제거. 기존 비전 설정은 `sim/runs/config_backups/`에서 복원 가능. 새 결과 폴더는 삭제하지 않음 |

추가/수정 파일의 상세 위치와 실행 명령은 `sim/README.md`를 참고한다. 기존 `INTEGRATION_REVIEW_20261002.md`는 변경 전 인수 검토 기록이며 현재 설정 위치는 이 변경 항목이 우선한다.

## 다음 변경 기록 양식

```text
변경 ID / 일자:
구분: 시뮬 전용 / 공통 / 실물 / 문서
상태: 제안 / 승인 대기 / 승인 완료 / 적용 완료 / 검증 완료
기준 버전: Git commit 또는 전달 파일 식별값
대상 파일:
변경 이유와 재현 조건:
구체적인 변경안 / 변경 전후 동작:
실물 영향:
시뮬 영향:
사용자 승인 일자·요청 내용·승인 범위:
적용 결과:
검증 명령·결과·미실행 범위:
시험 로그 / 보고서 경로:
되돌리는 방법:
```


## SIM-DATA-20261002-003 — 연결 경로·로봇 station 복원

- 승인 근거: 사용자 요청 “어제 업데이트한 경로 데이터 yaml … 경로끼리 연결, 각 로봇 station … sim 파트 데이터 다시”.
- 이유: 인수본에는 과거의 분리 그래프와 FOV 자동 관측 설정이 남아 있어 이후 업데이트한 연결·station·고정 촬영점 데이터가 누락돼 있었다.
- 대상: sim의 task.yaml, 연결 원본/역할별 GeoJSON, 원본 점유 지도, scout_survey/scout_patrol/scout_runtime/scout.json, 재생성·검증 도구, 문서와 작업 규칙. 상세 목록은 패치 ZIP에 포함된 파일 목록 기준.
- 출처: farm_scout_harvest_count_v0.8.5.zip의 최신 연결 데이터. 운송/선별장 용도는 기존 sim_route_design_v1 설계. 보관본 자체와 실제 git 커밋 비교는 구분한다.
- 변경 전후: 16개 분리 성분 → 연결 원본 227노드/516방향 엣지. BED_01~16/FOV 자동 관측 → SEC01~16/고정 관측점 80개. 예찰·수확 station 좌표·방향 복원, 운송/선별장 설계 좌표 복원(방향 미정).
- 호환: 공통 로더가 role 메타데이터를 읽지 않아 역할별 파생 그래프를 생성. 원본 베드 경계는 scout 파생 그래프의 기존 엣지를 분할해 보존. 공통 코드 복제나 변경 없음.
- 실물 영향: 이번 변경은 전부 sim/ 내부. 공통 코드·실물 설정·모델·USD 자산 변경 없음.
- 검증: 현재 공통 로더와 기하 계산/순찰 로더에서 16구역·80관측점 유효, 371개 역할별 경로 계산 통과. 원본 그래프/지도 동일, 원본 구역·베드·예찰/수확 station 동일, 227개 원본 노드의 지도 free 픽셀 확인.
- 미실행/유지: ROS/Isaac/colcon 미실행. station 자동 배치, AMCL station 초기화, FollowPath 전환, 수확/운송 실행부 연결은 미적용. 기존 navigate_to_pose 유지. 자동 station 복귀 없음.
- 복원: 패치 적용 전 백업 사용. 이번에 추가된 파일은 제거하고 기존 파일만 백업본으로 돌린다. sim/runs 결과는 보존한다.
- 보고: sim/docs/ROUTE_RESTORE_20261002.md 및 ROUTE_RESTORE_VALIDATION_20261002.json.


## SIM-RUNTIME-20261002-004 — Isaac 실행 대상 station 자동 배치

- 승인 근거: 사용자 “robot의 station 자동 배치는 isaacsim 실행용 코드에 포함”. FollowPath 설명 요청은 모드 전환 지시로 해석하지 않았다.
- 대상: sim runtime의 station_spawn.py/run_sim.py/scout.launch.py, scout.json, task.yaml, station_spawn.json, nav2_scout.yaml, 재생성·검증 도구, sim/tests/test_station_spawn.py 및 sim 문서.
- 변경 전후: USD 저장 위치에서 시작 → task 기반 station JSON의 예찰 station XY/yaw로 물리 시작 전 배치. 기존 body 높이·센서 상대 위치 유지. USD session layer만 사용하며 원본 저장 없음.
- 위치추정: AMCL 초기 pose를 같은 station 원본에서 생성. launch에서 서로 다르면 오류. 물리 reset 후 배치 검증. 주행 중 정답 pose 주입 없음.
- 범위: 현재 단일 예찰 런타임에 적용. 수확/운송 실행부 생성·구동 및 FollowPath 전환은 미적용. 공통 코드·실물 설정·USD 자산 변경 없음.
- 검증: 좌표/설정 시험 6개, launch 구성 4개 및 AMCL 불일치 거절 검사 통과. 경로 371개 검사 통과. nav2는 초기 pose 외 설정 값 유지.
- 한계: ROS/Isaac/USD API 실실행, 물리 구동, colcon 빌드 미검증.
- 복원: 이전 sim 파일 백업을 복원하고 새 station_spawn.py/json 및 시험 파일을 제거한다. sim/runs 결과는 보존. 배치만 끄려면 station_spawn.enabled=false와 실제 시작 위치의 AMCL 초기 pose를 함께 맞춘다.
- 상세: sim/docs/STATION_SPAWN_20261002.md.


## SIM-NAV-20261002-005 — 실물과 동일한 FollowPath/RPP 설정

- 승인 근거: 사용자 “시뮬설정도 실제랑 동일하게 세팅해”.
- 대상: sim의 scout_runtime.yaml, nav2_scout.yaml, task.yaml, 재생성된 scout_survey.json, 문서·작업 규칙. 공통 코드/실물 파일 변경 없음.
- 전후: navigate_to_pose → follow_path, controller_id FollowPath → RPP, goal checker general_goal_checker → goal_checker. 실물과 navigation 파라미터 동일(base_frame 제외).
- 제어 설정: 인수본 실물의 controller_server·velocity_smoother 값을 적용(use_sim_time/odom_topic 제외). controller 10Hz, RPP 0.15m/s·lookahead 0.15m, goal 0.03m/0.05236rad, progress 0.1m/10s. local/global inflation도 RPP 비용 모델에 맞게 실물과 동일하게 설정.
- 유지: 시뮬 지도·graph·관측점·station, TF·센서·장치·시간, AMCL station 초기 pose, 로봇 반경/센서 costmap 레이어. 모든 Nav2 값을 무조건 복사한 것은 아님.
- 실행 동작: 공통 RouteGraph가 연결 그래프 경로를 계산하고 Nav2 FollowPath 액션에 controller_id=RPP로 전달한다. 교통 제어·자동 복귀·도킹 추가 없음.
- 검증: 양 환경 설정 로드, 주행값/선택 controller/goal/progress ID 일치, 공통 goal checker 검사 통과. 371개 경로 계산 및 station 시험 6개 통과. 이번 수정이 sim 내부로 한정됨을 파일 해시로 확인.
- 한계: ROS/Isaac 실주행·colcon 빌드 미실행. 인수본 설정과 동일하다는 의미이며 담당자의 현장 실행값은 별도 확인 대상.
- 원복: 적용 전 시뮬 설정 백업 복원. 주행 모드 한 줄만 바꾸면 제어 튜닝까지 원복되지는 않는다.
- 상세: FOLLOWPATH_ALIGNMENT_20261002.md, FOLLOWPATH_VALIDATION_20261002.json.


## LAUNCH-SPLIT-20261002-006 — 로봇/Isaac/RViz 독립 실행 및 시뮬 전체 실행

- 승인: 사용자 “그럼 그렇게 수정해 … 시뮬레이션용 전체실행 런치 … 만들어줘 … 실행 절차 … 작성”. 공통 launch 변경을 포함한 실행 구조 분리 승인으로 적용.
- 공통 대상: farm_bringup의 scout.launch.py, scout_navigation.launch.py, 새 rviz.launch.py, tests/test_launch_composition.py, 공통 실행 안내/루트 README/AGENTS.
- 시뮬 대상: sim 런타임의 scout/scout_devices launch, 새 isaac/all launch, setup.py의 launch 파일 설치 패턴, 안내 문서.
- 변경 전후: 로봇 launch에서 Isaac/RViz를 함께 시작 → 로봇 단독 기본은 장치+Nav2+예찰 서버, Isaac과 RViz는 독립 실행. 시뮬 all은 독립 launch 세 개를 조합.
- 실물 영향: 기존 survey=true 실행은 장치·Nav2·서버 구성 유지. RViz는 별도 실행. survey/navigation 기본값이 true로 변경됨. start_isaac/rviz=true는 명시적으로 이관 안내 오류. navigation 전용 sim 실행도 환경 프로파일을 선택하도록 보완.
- 유지: 실물 설정·공통 미션/FSM/주행 계산/메시지·USD 및 station 배치 구현 변경 없음. 수확/운송/관제 구현을 임의 추가하지 않음.
- 검증: launch 기록 객체 기반 9개 시험 통과. 시뮬 전체의 Isaac/어댑터/예찰서버/RViz 각 1개, 독립 실행 경계, 실물 장치 포함 및 Nav2/서버, 모드별 RViz 시간/TF, 옵션 및 잘못된 구형 옵션 거절 확인. 직접 ROS/Isaac 구동·실물·colcon 빌드는 미실행.
- 실행 안내: docs/RUN_GUIDE_20261002.md. 실물 담당자 변경표, 각 장비 실행, 시뮬 전체/세 터미널 실행, 시험 관제, 종료·재시작 범위, 다중 로봇 미구현 항목을 명시.
- 복원: 적용 전 공통/시뮬 launch와 setup.py 백업 복원. 새 launch·구성 시험·안내 파일 제거. 실행 결과는 삭제하지 않음.


## SIM-LAUNCH-20261002-007 — 활성 robot_venv의 비전 Python 자동 선택

- 사용자 확인: 비전 의존성이 robot_venv에 설치되어 있어 별도 vision_python 인자가 불필요해야 함.
- 대상: sim 런타임의 launch_environment.py, all/scout launch. 공통/실물 코드 변경 없음.
- 전후: 인자/환경변수 미지정 시 빈 경로 → FARM_VISION_PYTHON 우선, 없으면 VIRTUAL_ENV/bin/python, 활성 venv도 없으면 launch Python 사용. 명시적인 vision_python 인자는 계속 우선함.
- venv 심볼릭 링크는 resolve하지 않아 가상환경을 유지. 잘못된 활성 venv 경로는 명시적 오류.
- 검증: 우선순위 및 경로 선택 검사, 기존 launch 구성 시험 9개 통과. 실제 ROS/Isaac/추론 실행은 미검증.
- 원복: 이전 all/scout launch 복원 후 새 launch_environment.py 제거.

## HARVEST-SIM-20261002-008 — 수확 이동 Action 및 시뮬 bringup

- 상태: 사용자 승인 후 적용, 오프라인 검증 완료. ROS/Isaac 실실행 미검증.
- 승인 근거: 수확 코드/bringup·sim/real 구분·sim 내부 작성 요청과 후속 “action 추가해. 진행해도 돼”, “그렇게 result 보내면 됨”. 사전 제안한 공통 인터페이스 추가와 이동 완료/수확량 0 계약을 적용했다.
- 공통 대상: farm_interfaces/action/HarvestTask.action 신규, CMakeLists.txt 등록만. 기존 HarvestTask.msg 및 주행/예찰/실물 설정 유지.
- 시뮬 대상: farm_sim_harvest 신규 서버/미션/통신/상태/평가; runtime harvest launch/fleet 실행/all 조합/clock relay; harvest 자산/설정/지도 선택/RViz; 데이터 생성·검증·시험·안내.
- 전후: 수확 실행부 없음 → 같은 공통 Navigator와 harvest 역할 graph로 window XY/yaw 도착 후 SUCCESS/harvested_count=0. 팔 작업 없음. expected와 실제 USD pose의 과실 박스 판정은 별도 로그. real 장치 연결은 미구현 오류, 실물 가상 구동 대체 없음.
- 출처: 제공된 v0.8.5 수확 물리 자산/주행좌표 변환/시뮬 센서 및 GT 수집 부분만 이식. 예전 서버·관제·공통 로직은 복원하지 않음. 실제 팔 도달성 대신 기존 임시 박스이며 인수 후 보정 필요.
- 실행 영향: harvest=true일 때 두 로봇 포트·TF 분리 및 독립 clock 하나. scout 단독 기본 동작 유지. fleet scout profile이 중복 clock을 막음. 새 Action 사용자는 robot workspace 재빌드 필요.
- 검증: sim 단위/구성 20개, 기존 launch 9개, 기존 경로 371개, 수확 엣지 내부 목표 경로 48개 통과. 공통 변경 2개 외 모든 변경 sim 내부 확인. ROS/colcon/Isaac/실물 미실행.
- 수정 안내·실물 인수 경계·로그·원복: HARVEST_RUN_GUIDE_20261002.md. 적용 전 파일 백업 복원 및 신규 파일 제거 후 재빌드, sim/runs 결과 보존.

## HARVEST-COMMON-20261002-009 — 수확 서버의 공통 위치 정정

- 승인: 수확 서버와 bringup을 공통 위치로 옮기고 평가만 sim에 남기자는 구체적 제안에 대한 사용자 “그래임마 정신차려”.
- 이유: 008에서 수확 서버 전체를 sim 전용 패키지에 배치한 것은 동일 서버를 sim/real에서 공유하는 기존 합의에 맞지 않았다. 008의 서버 위치 설명은 이 항목으로 대체한다.
- 공통 변경: robot/ros_ws/src/harvest_robot 신규(Node/Communication/Mission/StateController/계약), farm_bringup/launch/harvest.launch.py 실제 조합 및 package.xml 의존성. 기존 farm_navigation과 HarvestTask 계약 유지.
- sim 변경: farm_sim_harvest는 audit_node/evaluation만 유지. 작업 설정과 평가 설정 분리, fleet 평가 경로 갱신, sim harvest launch가 공통 launch+평가를 조합. 이전 sim 서버 소스 5개 제거용 백업 이관 도구 추가.
- 전후: sim 서버가 평가 함수를 호출 → 공통 서버는 Action/주행 처리와 환경 독립 task_events 진단 발행만 담당, sim 평가 노드는 비동기 구독하여 비교 로그 생성. 서버에서 sim import/Isaac snapshot 접근/평가 대기 제거.
- 실물 영향: real 설정과 외부 드라이버가 있으면 devices=false로 같은 서버 실행 가능. 미구현 실물 장치 기본 분기는 오류. 실물 맵/드라이버/팔 작업을 가짜 구현하지 않음. 공통 workspace 재빌드 필요.
- 검증: 오프라인 31개, 기존 경로 371개, 수확 내부 좌표 경로 48개 통과. sim/real 동일 서버, 시간 선택, 평가 분리, 중복 launch 없음 확인. 실제 ROS/Isaac/colcon/실물 미실행.
- 전달/원복: HARVEST_COMMON_MIGRATION_20261002.md. 이전 수확 패치를 대체하는 합본 패치, 이관 도구로 옛 서버만 백업 후 제거. 결과 로그는 보존.

## SIM-FLEET-20261002-010 — Isaac fleet 진입점 누락 수정

- 증상: 17:09 실행 로그에서 Isaac Python이 시작 직후 exit 0으로 종료, OnProcessExit에 의해 모든 ROS 노드가 SIGINT로 종료됨.
- 원인: run_fleet.py에 main 함수는 있으나 직접 실행 시 호출하는 __main__ 진입점 누락. 기존 문법/launch 구성 검사는 함수 호출 여부를 검증하지 못했음.
- 대상: sim runtime/run_fleet.py, sim/tests/test_fleet_entrypoint.py, 이 변경 기록. 공통/실물 파일 변경 없음.
- 변경: 직접 실행 시 main() 호출 추가. 종료 연동은 그대로 유지.
- 검증: 수정 전 --help가 출력 없이 exit 0인 현상 재현. 수정 후 실제 subprocess --help에서 옵션 출력, 필수 인자 누락 시 exit 2 확인(2개 통과). Isaac 물리 구동은 해당 환경이 없어 미검증.
- 적용: 패치 압축 해제 후 sim workspace의 farm_sim_runtime 재빌드, 환경 다시 로드 후 기존 전체 실행 명령 사용.
- 원복: run_fleet.py 마지막 __main__ 블록과 새 시험 파일을 되돌림. 결과 데이터는 변경하지 않음.

## SIM-TF-20261002-011 — 카메라 없는 수확 로봇 상태 패킷 수락

- 증상: HarvestTask는 수락됐으나 harvest_01/base_footprint TF가 없어 NAVIGATION_FAILED.
- 원인: ros_adapter.valid가 고정 TF 3개를 강제. fleet 런타임은 카메라 없는 harvest에 base/link·lidar TF 2개를 전송하여 모든 패킷이 거절됐음. odom·scan·TF 발행에 도달하지 못함.
- 변경: camera.enabled에 따라 2/3개를 선택하고 설정의 부모/자식 프레임 쌍과 일치하는지 검사. 공통 서버·실물·Nav2 변경 없음.
- 검증: 실제 valid 메서드를 ROS 없이 실행, harvest 2개/scout 3개 수락 및 누락/다른 로봇 프레임 거절 4개 통과. ROS/Isaac 직접 실행 미검증.
- 적용: farm_sim_devices 재빌드 및 전체 launch 재시작. 확인: harvest_01/odom → harvest_01/base_footprint TF 출력.
- 복원: 이전 ros_adapter.py 복원 후 시뮬 패키지 재빌드. 시험 로그 데이터 유지.

## DRIVE-DIAG-20261006-012 — 수확 무응답 구동 진단

- 근거: cmd_vel 0.12m/s, wheel odom 약 0, 로봇 정지 및 Failed to make progress. 전달 경로/물리 구동 중 원인 미확정.
- 범위: sim runtime/run_fleet.py와 신규 drive_diagnostics.py. 공통/실물/게인/구동 제한 변경 없음. 앞선 main 호출 수정 포함.
- 변경: ROS→Isaac 수신 패킷과 gate 수락/거절 누적, 실제 적용 cmd, 공통 kinematics로 계산한 관절 목표, 관절 실측 속도/인덱스, 실제 pose를 1Hz로 기록. 적용된 USD 바퀴 drive 설정 기록.
- 산출: sim/runs/drive_diagnostics/<세션>/<robot_id>.jsonl 및 <robot_id>_setup.json. 목표 속도는 apply_action에 전달한 입력으로 계산한 값이며 PhysX 내부 target readback은 아님.
- 정적 검사: 제공 자산의 바퀴 stiffness=0, damping=625. 별도 자산의 검사이며 사용자 실행 중인 scene 적용 상태의 증명은 아님.
- 검증: 실제 common wheel_targets를 사용한 목표 rad/s, 수락/거절 카운터, JSON 출력/1Hz 제한, USD 관절 추출 검사 통과. Isaac 물리 실행 미검증. 근본 원인 수정 완료가 아닌 진단 계측 패치.
- 원복: 적용 전 run_fleet.py 복원, drive_diagnostics.py 제거 후 runtime 재빌드. 기록은 보존.



## DOC-HANDOFF-20261006-015 — Codex·ChatGPT 최신 인수인계 문서 패키지

- 일자: 2026-10-06 (Asia/Seoul).
- 구분: 문서·작업 지침. 실행 코드·환경 설정·ROS 정의·USD·모델 변경 없음.
- 승인 근거: 사용자 요청 “필요한 인수인계용 파일 최신버전으로 작성해서 전달해줘”. 문서 작성·전달 범위이며 공통 실행 코드 변경 승인으로 확대하지 않음.
- 기준 코드: `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`, Robot3FinalProject/main의 main 브랜치.
- 상태: 다운로드 적용용 문서 패키지 작성. 사용자 PC 적용·GitHub 반영은 별도 확인 필요.
- 대상: `AGENTS.md`, `README.md`, `docs/CODEX_HANDOFF.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF_SOURCES_20261006.json`, `sim/docs/RUN_GUIDE_20261006.md`, 이 변경 이력.
- 변경 이유: 초기 토마토 기획과 10/2 예찰 인수 기록만으로는 10/6 수확·통신·다중 로봇 실행 상태를 전달하기 어려움. 코드·문서·사용자 확인의 시점을 구분하기 위함.
- 변경 내용: 최신 구조·메시지·로그·실행 인자·미구현 영역 정리. 루트 AGENTS의 복원 전 그래프 설명과 README의 수확 미구현 포괄 설명을 정정. 인수인계 읽기·갱신 규칙과 ChatGPT 프로젝트에 추가할 지침을 문서화.
- 현재 규칙 유지: 시뮬 전용 작업은 sim 내부, 공통 코드 변경 승인, sim 정답 평가와 실제 제어 분리, 코드 및 사용자 미커밋 변경 보존.
- 직접 검증: 기준 커밋의 관련 소스·설정 정적 대조; 8베드/16Section/80관측점, 원본/예찰/수확 그래프의 노드·엣지·약연결성 계산; 최종 패키지의 링크·경로·필드·Bash 구문·ZIP 내용 검사. 상세 결과는 전달 시 검증 기록 기준.
- 미실행: 사용자 PC의 git 상태, colcon 빌드, ROS 네트워크·관제 연동, Isaac 물리 실행, 실물 실행. 과거 시험 횟수를 이번 재실행 결과로 쓰지 않음.
- 실물 영향: 실행 동작 변경 없음. 새 세션에서 갱신된 문서 확인 절차가 적용됨.
- 되돌리기: 적용 전 문서 백업과 비교하여 이번 문서 변경만 복원. 이번에 새로 추가된 문서의 제거 여부는 이후 편집 유무를 확인한 뒤 결정. 실행 코드·데이터를 되돌릴 이유는 없음.
- 관련 과거 기록: 캐스터 보정은 `sim/docs/changes/CASTER-FIX-20261006-013.md`, 통신규약은 `docs/changes/PROTOCOL-20261006-014.md`에 별도로 존재한다. 여기에서 해당 변경을 새로 적용한 것으로 기록하지 않는다.


## DOC-STATE-20261006-016 — 로컬 코드·문서·기존 로그 대조

- 일자/구분: 2026-10-06 KST / 문서. 적용 완료, 정적 검토 완료.
- 승인 근거: 사용자 요청 “인수인계서, 변경 이력, docs/changes와 현재 코드를 대조해서 docs/PROJECT_STATE.md를 작성해 … 이번에는 문서만 작업해”.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e 및 시작 시 미커밋 인계 문서. fetch 후 origin/main과 0/0. 기존 AGENTS/README/이력 수정, 미추적 인계 파일과 백업 보존.
- 대상: docs/PROJECT_STATE.md, 이 변경 이력. 코드·설정·시험·모델·USD 변경 없음.
- 전후: 인계 패키지의 원격 기준 요약 → 실제 로컬 Git 상태, 실행 요약, 구형 설명과 코드의 차이, 저장된 수확 성공 2건/실패 6건의 증거·한계 보강. 로컬 장면 USD는 포인터가 아닌 바이너리 객체임을 정정.
- 실물/시뮬 영향: 실행 동작 변경 없음. 최신 프로토콜 E2E 검증 완료로 확대하지 않음.
- 직접 검증: Git fetch·차이 조회, 관련 문서/launch/메시지/미션 정적 대조, GeoJSON 규모·약연결성 및 16Section/80관측점/8베드 계산, 기존 survey/audit JSON 열람, USD 헤더·크기·캐스터 패치 체크섬 비교, 문서 링크·기존 파일 보존 검사.
- 미실행: 기존 단위/경로 검사의 재실행, colcon/ROS/CDR/Isaac/실물/최신 프로토콜 E2E.
- 로그: 새 런타임 로그 없음. 기존 증거 위치와 다음 통합 시험 조건은 PROJECT_STATE §11·§13.
- 복원: 문서의 이번 보강과 이 항목만 이전 내용과 비교해 복원. 시작 시 미커밋 변경은 유지. commit/push 미실행, 원격 미반영.

## ROBOTARM-REVIEW-20261006-017 — 로봇팔 인수 자료 검토 및 반영 승인 대기

- 일자/구분: 2026-10-06 KST / 문서 검토. 실행 코드·설정·USD 반영은 승인 대기.
- 승인 근거: 사용자 “main에 robotarm 폴더에 … 확인해보고 sim에 반영할 내용 정리해서 나한테 확인받고 적용해”. 이번에는 검토서 작성만 수행하고 적용 전 확인 절차를 따른다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e. 이번 fetch 후 origin/main과 0/0. 기존 미커밋 문서·백업 및 robotarm 원본 4개 보존.
- 대상: 신규 `sim/docs/ROBOTARM_INTEGRATION_REVIEW_20261006.md`, 이 변경 이력. 실행 파일·공통/실물 코드·기존 설정·자산 변경 없음.
- 전후: 인수 명세 4개만 존재 → 현재 sim과의 차이, 필수 추가 인수, 단계별 대상 파일·영향·검증·승인 경계를 문서화.
- 주요 발견: 정책 4개/run.json/profile/runtime/RL 소스/전용 자산/검증 원본 미수신. 오른팔 Teacher와 기존 왼팔 Window/audit 불일치. 현재 60Hz와 Teacher 실효 480Hz/정책20Hz 차이. 활성 농장 과실 288개 하위에 rigid body/mass/collision API 없음. 현재 과실 크기와 root 의미 대조 및 박스 바닥 물리 준비 필요.
- 직접 검증: 문서/JSON/현행 코드 정적 대조, 후보18개 범위·HOME 거리·18cm 간격 조합 계산(최대3개), 파일 목록/SHA256, Git 상태·fetch·커밋 차이, 설치 pxr를 사용한 USD 정적 TF/기하/물리 API 검사.
- 미실행: 정책 추론, Isaac SimulationApp/PhysX, ROS/colcon, 실제 수확 및 실물 시험. 문서의 적재3/6은 담당자 과거 기록이며 이번 검증 결과가 아님.
- 제안: A sim 인수 설정·검사 도구 → 원본 수령 후 B 독립9g 평가 → C 농장/오른팔 기하 정합 → 별도 공통 승인 후 D 실제 팔 작업 연결. 이번 승인 요청은 A이며 B~D 동작을 자동 승인받은 것으로 취급하지 않음.
- 실물/시뮬 영향: 문서만 추가되어 실행 영향 없음. Teacher 내부 상태 입력은 독립 평가 범위로 한정하며 기존 공통 제어 정답 주입 금지를 유지.
- 결과/다음 작업: 상세 검토서의 A 범위를 사용자에게 제시. 승인 후 설정·검사 도구를 구현하고 누락 원본 확보 후 물리 재현 진행. 새 런타임 로그 없음. commit/push 미실행.
- 복원: 이번 검토서와 이 항목만 되돌린다. 기존 이력과 시작 시 미커밋 변경을 보존한다.

## ROBOTARM-RECEIPT-20261006-018 — 전체 전달 묶음 수령 및 이식 문제 검토

- 일자/구분: 2026-10-06 KST / 수령 검사·문서. 사용자 요청 “파일 받아서 robotarm 폴더안에 넣어놨어 파악해봐”. 앞선 전체 자료 수신 후 일괄 작업 요청에 따라 017의 A 단독 반영은 보류.
- 기준: 농장 main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e, 이번 fetch 후 origin/main과0/0. 전달 소스 base abe9e13357e1be549500712b62c5582649d444ab + 현재 수정본.
- 대상: 신규 `sim/docs/ROBOTARM_BUNDLE_RECEIPT_20261006.md`, 기존 검토서의 최신 문서 연결, `docs/PROJECT_STATE.md` §14, 이 이력. `sim/runs/robotarm/received_20261006_143434/`에 검토용 원본 추출 및 검사 JSON2개. 실행 소스·정책·기존 자산·프로파일은 수정하지 않음.
- 전후: 문서4개만 수령 → 소스·정책·자산·환경·YOLO·평가 원본 확보 및 무결성 확인. 새 평가/농장 통합 완료는 아님.
- 직접 검증: archive SHA256, 안전한 상대경로/일반파일 검사, manifest2148 및 정책4/run.json 해시 일치, 기존4개 파일 동일, 미수신LFS 포인터0. USD/URDF 참조·박스 바닥·팔/차체/캐스터 정적 대조, 환경metadata 비교, 과거episode JSON 집계, 동작코드 분석.
- 발견: prepare 경로 치환 뒤 converter asset hash가 달라져 USD 재생성 경로 발생. 복귀는12×1/480s이나 제어·dwell은50ms 사용. 전달 current USD는 고정차체 평가용, 농장 주행 USD 통째 교체 불가. 비전 환경 일부 버전 차이. 상세는 수령 검토서.
- 미실행: prepare/캐시변환/설치/정책로딩/Isaac·ROS·실물·학습. 원본3/6 성공은 과거 기록이며 수신PC 결과가 아님.
- 실물/시뮬 영향: 문서·검토용 추출만 수행, 현재 운영 동작 영향 없음. source 원본/기존 미커밋 문서·백업 보존. commit/push 없음.
- 후속: 이식·비전환경·복귀시간 보완을 포함해 독립9g 재현 및 농장 통합 범위를 확정. 공통 업무 변경은 기존 구체안 승인 절차 유지.
- 복원: 이번 문서 항목만 비교 복원. 원본 archive/기존 자료를 삭제하지 않으며 검토용 추출본은 운영에서 참조하지 않음.

## ROBOTARM-PHYSICS-20261006-019 — 농장 과실·오른팔 물리 및 수확 목표 좌표 적용

- 일자/구분: 2026-10-06 KST / sim 코드·설정·독립 자산·시험·문서. 구현 및 GPU 기초 물리/진입점 시험 완료, 정책 파지·적재와 실제 Nav2 주행은 미실행.
- 승인 근거: 사용자 “전달받은 파일들 기반으로 아이작심에 적용 … 농장 맵 … 물성치 … 오른쪽 팔 … 예찰로봇 좌표 … 오른쪽 암 기준 … 그것부터 작업”. 추가 선택 “Teacher 규격으로 통일”. 017/018의 검토 대기는 이 sim 1단계에 한해 구현 요청으로 대체했다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e와 기존 미커밋 변경. fetch 후 origin/main과 동일. 받은 전체 묶음 및 공통/실물 실행 파일은 보존했다.
- 과실: `sim/assets/fruit/teacher_9g/`, `fruit_asset_setup.py`, `fruit_attachment.py`, `stem_physics.py`, 생성 도구. 농장288개를70mm폭/75mm높이·9g로 통일하고 마찰/감쇠/접촉·줄기 response5·40ms 지속 분리를 적용했다. 기존 ID·색·위치·회전 보존. 선속도3m/s·각속도20deg/s를 source runtime까지 대조해 적용. 받은 runs 폴더에 대한 운영 의존 없음.
- 오른팔: `robotarm_asset_setup.py`, `sim/assets/robots/harvest_physics/`.6축 힘 drive·그리퍼 접촉·HOME·박스 바닥4타일. 주행용 USD를 교체하지 않고 기존 바퀴/캐스터/왼팔/rigidbody/전체 articulation 물성은 보존했다. 고정차체 Teacher와 전체 solver/self-collision이 같은 환경이라고 주장하지 않는다.
- 좌표: `task.yaml`, 생성 `scout_survey.json`/`harvest_audit.json`, `rebuild_route_data.py`, `scout_vision.json`.16구역 오른팔 mount `[.19,.185,.713]`, 작업중심 `[.19,.5,.838]` 및 크롭 높이를 동기화. `harvest_runtime.yaml` 연결한계.09m/도착.02m·.05rad, `nav2_harvest.yaml` 내부허용.015m·.04rad. 원본 graph·베드 좌표 변경 없음.
- 실행: `robotarm_physics.json`, scout/scout_fleet/harvest.json, `harvest_physics.py`, run_sim/run_fleet, isaac.launch.480Hz 물리 한 tick마다 외력을 갱신하며60Hz 렌더를 별도 호출. 원본 USD 저장 없이 session layer에서 적용. 단독 runner도 실제 project_root를 받는다. 실행별 setup/물리 분리 로그를 저장하고 정책·수확 성공으로 사용하지 않는다.
- 직접 검증: 관련 단위54개+USD 정적7개=61개 통과(skip0), 원본 줄기 Torch와256개 상태 수치 대조,371개 경로,48개 오른팔 Goal과 정적 map 연결선, sim3패키지 colcon 빌드. GPU RTX4070SUPER/Isaac5.1에서288과실2초 자연이탈0, 선택 과실3N 외력으로40ms 이상 지속 후 분리·0.6초 낙하를 확인. 실제 fleet 진입점2초에서288결합 유지, RGB-D29프레임, 로봇별 상태60개. 상세값과 명령은 `ROBOTARM_PHYSICS_20261006.md`.
- 중간 문제: sandbox CUDA 접근 실패는 GPU 권한 환경에서 재시험. fast_shutdown 기본값이 결과 기록 전 프로세스를 끝내는 문제는 정상 종료/종료 전 보고서 기록으로 수정. 최초 낙하0.2초 검사는 분리 직후 상승속도 때문에 실패하여 초기속도/궤적을 기록하고0.6초 관측으로 보완했다. 최종시험은 누락된 과실 속도 제한까지 적용한 후 다시 통과. 중간 JSON 보존.
- 남은 차이/미실행: 실제 Nav2 정밀 정지·동적 장애물/footprint 검사, 전체 예찰→수확 E2E, 정책4개 독립 재현/20Hz 추론·파지·박스 적재, 실물 시험. 원본 농장 빈 visual 참조와 종료 UI extension 경고는 보고서에 구분했다. 공통 수확 Action은 현재 이동+수확0 계약 유지.
- 문서: 신규 `sim/docs/ROBOTARM_PHYSICS_20261006.md`, RUN_GUIDE 최신 절, PROJECT_STATE §15, DECISIONS D-013/D-014 및 이력 갱신. 실물 소스·설정·모델·공통 업무/메시지 변경 없음.
- 로그: `sim/runs/robotarm/physics_smoke_gpu_20261006/result.json`, 같은 이름 `.log`, `fleet_physics_smoke_20261006.log`, `asset_setup_static_final_20261006.log`, `physics/98d899878bda4638a1aa82bbaa51f46b/`.
- 종료 보완: 정상 app.close 후에도 Kit 스레드가 남는 현상을 확인해 CLI에서 파일·앱 정리와 출력 flush 후 검사 결과의 종료코드로 종료한다. 이전 시험 중 결과 기록을 마치고 남은 프로세스4개만 종료했다. 보완 후 물리 검사와 fleet 진입점을 재실행해 각각 종료코드0을 확인했다. 물리/장치 검증 성공과 종료 문제가 있었던 중간 실행을 구분한다.
- 복원: 신규 물리 프로파일 enabled=false로 물리 override를 임시 비활성화할 수 있다(480Hz와 좌표 변경은 별도). 전체 복원은 이번 sim 실행/설정 변경만 비교해 되돌리고 task 원본 기준으로 생성 설정을 함께 재생성한다. 기존 캐스터 패치·인계 문서·사용자 변경을 전체 reset하지 않는다. 소스 농장 USD는 변경하지 않았으므로 복구 저장이 필요 없다. commit/push 미실행, 원격 미반영.

## ROBOTARM-VERIFY-20261006-020 — 인장력 비교 검사 및 커밋·푸시 요청

- 승인: 사용자 “테스트하고 커밋푸쉬 … 정상적용 확인 … 어느정도 인장력 … 강화학습 환경을 적용한거야?”.019 구현과 관련 문서를 테스트 후 게시한다. 별도 AGENTS/README 등 기존 수정, 수신 archive·백업은 작업 트리에 보존한다.
- 대상: `check_harvest_physics.py`에0.1N 유지1초/무외력 회복0.5초 비교·GUI 카메라·실제COM/관성 및 초기tick 기록 추가. `stem_physics.py`/`fruit_attachment.py`에 힘 clamp 전후 및 분리 조건 진단 추가, 줄기 회귀1개 추가. 물리 수식·계수·판정·공통 코드는 변경하지 않는다.
- 검증:62개 테스트(skip0),371개 경로,sim3패키지 빌드 통과. GPU15항목/종료코드0,288과실 유지→0.1N 유지→3N 실제 분리·0.6초간0.90448m 하강 확인. 원본 USD와 주행 구성 보존.
- 중요한 중간 관측:0.5N·1초 유지 예상은 실패했다.116.7ms 뒤 인장축32.32mm, 원시0.51955N, 후크조건41.667ms로 분리됐다. 전달 수식의 거리 분리 조건이며 단순 힘 임계값 실패가 아니다. 별도1kg 무중력 GPU 시험에서 두 외력 호출은 합산됨을 확인했다. 실패 JSON을 보존하고, 물성을 바꾸지 않고 유지 확인 하중을0.1N으로 명시했다.
- 문서/증거: `ROBOTARM_PHYSICS_20261006.md` §10, PROJECT_STATE §16, `sim/docs/changes/ROBOTARM_PHYSICS_VALIDATION_20261006.json`. 원본 로그 `sim/runs/robotarm/precommit_20261006/`. 최초 격리 빌드의 underlay 의존경로 누락은 기존 install을 지정한 최종3패키지 빌드로 해결했으며 실패/성공 로그 모두 보존.
- 경계: 받은9g 평가 환경을 적용했으며 원 체크포인트의35g 학습조건 전체 재현·학습정책 적용·실물 파괴력 측정으로 해석하지 않는다. 정밀Nav2 이동·정책 파지·적재는 미실행.
- 복원:019 물성은 유지하고 이번 진단/검사 도구 추가만 별도로 되돌릴 수 있다. 기존 사용자 파일과 받은 원본은 삭제하지 않는다. commit/push는 이번 사용자 요청으로 승인됐으며 실행 결과는 최종Git 원격 일치로 확인한다.



## COMMON-TAG-20261006-001 — 선택적 태그 AMCL 연결

- 승인: 사용자 “이 브랜치에서 태그보정 패키지 연결작업 진행해줘”(2026-10-06). `feat/apriltag-localization`, main `1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd` 기준.
- 이유: 성공한 실물 태그 기하·타이밍 보상을 기존 수확 미션에 연결하되 보정 준비/기록 대기로 주행을 막지 않음.
- 공통 변경: `harvest_robot/node.py`, `mission.py`, 새 `tag_control.py`; `farm_bringup/launch/harvest.launch.py`, `farm_bringup/package.xml`. 새 `farm_tag_localization` 패키지와 `robot/config/localization` 참고 자산 추가.
- 동작: 기본 OFF. 선택 시 미션 이동 시작·종료 신호와 독립 initialpose 어댑터 연결. AMCL 단독 TF 유지. real harvest TF remap을 기존 namespaced Nav2와 일치시킴. 기존 구동·취소·장애물 처리·경로·속도·시뮬 자산은 변경하지 않음.
- 새 맵 자산 등록은 미완료이며 configured=false. 이전 태그 좌표를 새 맵에 확정하지 않음. 실물 장치 실행기나 mini_fleet 코드를 이식하지 않음.
- 검증: 계약 시험 17개, Python 컴파일 통과. 이전 성공 기록 982행 재생에서 기하 채택 41행의 q/p 동일(1e-12 허용오차, 같은 OpenCV 5.0.0).
- 미검증: ROS/colcon 빌드, 실제 통신·주행·새 맵 정확도. 로컬 ROS 설치 없음.
- 복원: 실행 시 tag_correction:=false로 선택 기능 제외. 코드 복원은 이 변경 커밋을 revert하여 공통 수정과 추가 패키지를 함께 되돌림.
- 상세 설정/입력 계약: `robot/ros_ws/src/farm_tag_localization/README.md`.

## 2026-10-07 — 사용자 브랜치 실물 AprilTag 결과 반영

- 구분: 실물 Vic Pinky 설정 및 태그 패키지 진단/문서. 시뮬 실행 로직/설정 변경 없음.
- 승인 근거: 사용자가 본인 브랜치에 실험 결과를 반영하도록 명시 요청.
- 대상: robot/config/robots/vicpinky/nav2.yaml, robot/config/localization/harvest_real.yaml 및 reference_20261007, farm_tag_localization.
- 변경: RPP/FollowPath 정렬3→6도, 전진0.15→0.10m/s, 회전0.35→0.10rad/s, 진행0.5m/10초→0.1m/20초. ROI60x80 의미를 진단에 명시. 새 실험지도 후보자산/해시 저장, 자동활성화없음.
- 실물 영향: 해당YAML을선택해새로기동한환경에서 적용. 충돌감지·목표도착허용치·기존미션/지도/그래프 유지. 외부mini_fleet실험의실물성공과프로젝트통합완료를구분.
- 검증: 계약19개, 동일환경검출3779행대조(q/p787행일치). ROS/Isaac/프로젝트실물E2E 미실행.
- 복원: 이번커밋 revert. 태그변환/보정수식 변경없음. 상세 결과는 farm_tag_localization/FIELD_RESULTS_20261007.md.



## REAL-COMMON-20261007-001 — 수확 실물 실행 통합 및 FSM 차이 검토

- 승인: 2026-10-07 사용자 “예찰쪽 ... 참고해서 구조 맞춰서”, “내 브랜치 파일 수정”, “컨플루언스 ... FSM도 참고해서 ... 부족한 부분 파악”.
- 대상: 공통 `farm_bringup/launch/harvest.launch.py`, 의존성; `farm_tag_localization`의 캡처 세션 실행기/설치/시험; 실물 harvest 환경·장치·카메라·지도 설정; 실행/FSM 문서.
- 변경: 기존 real devices 미구현 오류를 기존 farm_real_devices의 vicpinky 분기로 연결. 성공 캡처 외부 실행본을 환경 설정으로 선택, 세션 폴더 자동 연결 및 자기 자식 종료. 태그 수식·미션·공통 Navigator는 유지.
- 실물 영향: 수확 프로파일만 10/07 지도 원본/시험 경로 사용. 예찰 코드·지도·설정 미변경. 카메라 실행본은 별도 설치된 성공본 의존. capture 실패는 Nav2 취소로 연결하지 않음.
- sim 영향: 기존 sim 장치 실행 및 외부 capture_directory 경로 유지. 실물 USB 자동 캡처는 sim에서 실행하지 않음. Isaac/RViz 자동 실행 없음.
- 검증: 태그 계약30개, 지도 해시·모델 생성·10→13 경로 및 controller/goal checker 일치, Python 컴파일. ROS/colcon/실물 주행은 미실행.
- 복원: 이번 통합 커밋만 revert. 기존 1afa48a의 실험 수식/프로파일 반영과 main 변경은 유지.
