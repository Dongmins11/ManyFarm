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


## ROBOTARM-PERFORMANCE-20261006-021 — GUI 검사 종료와 CPU 물리 병목 분석

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 성능 계측·문서 정정. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd.
- 대상:`ROBOTARM_PHYSICS_20261006.md` §11 및 CCD 설명, `docs/PROJECT_STATE.md` §17, 이 이력. 임시 계측 도구/JSON/로그는 ignored `sim/runs/robotarm/perf_20261006/`와 `cpu_microbenchmark_20261006/`에 저장했다.
- 전후:GUI 검사 종료와12FPS 원인 미확인 →사용자 JSON15 checks 통과/유한 검사 후 의도된 종료 확인. 현재 물리/진단 생략/과실 고정480Hz/과실 고정60Hz의 GUI 비교를 각각 실행해8.30/8.27/22.22/89.52FPS 측정. 마지막60Hz 대조군은 초기 reset 영향으로 카메라Z 약8.05mm 차이가 있고 이전 운영 버전 성능이 아니다.
- 결론:현재 조건 frame120.44ms 중 CPU 물리 실행/결과 동기화100.63ms(83.5%). runtimeCPU/GPUDynamicsfalse, GPU평균11.9%.288개 동적 과실과 전역480Hz가 부하를 늘렸으며 추가 상태 진단만 제거해서 해결되지 않는다.
- 정정:실행 시sceneCCD=true를 확인했다. 기존 “scene CCD false 유지” 설명은 잘못됐다. 설정 자체를 변경하지 않고 Teacher와의 차이를 기록했다.
- 검증:4개 GUI 비교 정상 종료, 물리1tick/렌더 시간 불변 검사 및 대조군288kinematic/변위0 확인. 준비30/측정120프레임씩. 순수 NumPy 수식288개0.495ms/tick. 초기 SDK getter 계측 실패 기록 보존 후 임시 도구만 수정했다. 전체fleet/정책 수확/장기 성능·최적화 적용은 미실행.
- 실물/시뮬 영향:운영 코드·자산·물성·공통/실물 실행 변경 없음. 분석용 고정/60Hz는 별도 프로세스 메모리/session 안에서만 적용하고 종료했다. 이번 문서는 미커밋·원격 미반영.
- 복원:이번 문서 항목만 비교 복원한다. 기존 사용자 변경 및 원본 JSON/전달 묶음은 보존한다.

## ROBOTARM-ADAPTIVE-20261006-022 — 수확 활동에 따른 물리 주기·주변 과실 선택

- 일자/구분:2026-10-06 KST / 사용자 승인 sim 구현·실제GPU/ROS 검증. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 이후 미커밋. 승인 문구 “물리주기도 동적으로 … 수확중 수확로봇 인근 …”. 공통 업무 코드 변경 없음.
- 대상: runtime `physics_schedule.py`, `harvest_regions.py`, `harvest_physics.py`, `run_fleet.py`, `run_sim.py`; devices `fruit_attachment.py`, `harvest_activity.py`, `ros_adapter.py`, `package.xml`; config `robotarm_physics.json`, `harvest.json`; 새 검사도구 `check_adaptive_harvest.py`와 단위시험4개. 상세문서 `ADAPTIVE_HARVEST_PHYSICS_20261006.md`, 기존 물리/실행문서 연결, PROJECT_STATE §18, DECISIONS D-015, 검증JSON 갱신.
- 전후: 전체288개 항상동적/480Hz → 유휴60Hz·부착과실 고정, 수확중480Hz·오른팔 실제장착점0.8m/유지1.0m 영역합집합만 활성. 분리과실은 고정하지 않고0.6초 정지 후60Hz/움직이면480Hz. 부착과실의 움직임/분리타이머 동안 freeze 유예. 현재pose·앵커·기준자세·분리상태 보존. kinematic중CCDoff, 활성화시 원복·PhysX flush로 전환 순서 보장.
- 시간/동시성:60Hz 프레임당1~8물리tick과 렌더1회. 매tick 힘갱신, reset없이dt변경, 실제누적시각으로odom/clock/센서. 활동은 로봇별세션/seq/유효기간 검사, 다른 활동이 남으면 고주기 유지. 미래복수수확기 영역합산은 단위시험이며 현재 실제GPU는 예찰+수확각1대.
- 연결 경계:공통이동완료를 팔작업으로 추정하지 않는다. 내부set_activity와 sim전용Bool heartbeat를 추가했으며 실제팔정책/공통FSM 연결은 후속이다. 과실정답은 물리영역선택에만 사용하고 목표/수확성공으로 전달하지 않는다.
- 직접검증:단위/USD107개(skip0),sim3패키지빌드,실제ROS bridge13항목. GPU선택물리19항목/종료0,기존전체288개기준15항목/종료0. 근거리3개활성,3N분리41.667ms,0.20714m하강,60Hz복귀. 원본USD SHA256불변. fleet6초2개조건에서clock360/상태각180/RGB-D89/라이다10Hz/카메라pose시각검사 통과.
- 관측된 한계:동일0.08m/s 개방루프명령에서 고정60Hz와60→480→60Hz의 최종world위치 약2.6cm차이. 시계정상과 궤적동일성은 별개다. 바퀴drive/명령을 보정해 차이를 감추지 않았다. 짧은headless측정 실시간배율0.725대0.483. 이전GUI성능과 직접비교 불가.
- 중간문제:시험초기mount가 과실반경밖이어서 최초검사실패, 실제장착점기준 초기배치로 시험만 수정한뒤 통과. 초기kinematic+CCD경고는 batchflag전환순서로 해결. 실패로그 보존. 기존visual참조/Kit종료UI경고와 검사실패를 구분한다.
- 실물영향/미실행:실물·공통·원본자산 수정없음. 정책파지/적재·Nav2폐루프주행정밀도·다수수확기/운송·전체E2E·실물 미검증. 같은Scene고주기는 여전히 전역CPU비용이다. 독립세트주기는 별도인스턴스가 필요하다.
- 로그:`sim/runs/robotarm/adaptive_20261006/`, 각 결과의physics_log_directory. 검증요약:`sim/docs/changes/ADAPTIVE_PHYSICS_VALIDATION_20261006.json`. 문서/코드 로컬적용·sim패키지빌드 완료, 커밋/푸시 미실행.
- 복원:`adaptive.enabled=false`로 전체과실/기준480Hz모드 복귀. 영역처리유지/주기고정시험은idle_hz와harvest_hz를 동일값으로 설정. 전체코드복원은 이번파일만 비교복원하며 기존사용자문서/인수자료/백업을 보존한다. USD는 저장하지 않았다.

## TEACHER-INTEGRATION-20261006-023 — 도착 후 순차 수확 실현성·공통 변경 검토

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 구현 검토·승인 제안. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 및022 미커밋 구현. 요청은 도착 후Teacher에과실좌표제공→시도별물리성공/실패Feedback→대상처리후Result. 사용자선택으로빨강·노랑각1회/일반실패다음진행/녹색및차체추가이동제외 확정.
- 대상: `TEACHER_HARVEST_INTEGRATION_REVIEW_20261006.md`, `proposals/HARVEST_ARM_COMMON_CONTRACT_20261006.md`와 `.proposal` 스키마3개, `changes/TEACHER_INTEGRATION_REVIEW_20261006.json`, PROJECT_STATE §19, DECISIONS D-016/O-008, 이 이력. 검사스크립트/원본JSON은ignored sim/runs/robotarm/policy_integration_review_20261006 아래다.
- 직접검증: 정책4개/각run.json SHA256, 현재설치공식ActorCritic strict load·정규화·합성82D입력5개→6D유한/결정적출력. 전달/농장팔·박스 FK9자세/9link 강체변환 최대오차2.22e-16,실제USD정적8link 최대5.96e-7. 농장288root간격/자세/현재planner기하 정적비교. ROS Jazzy rosidl parser로 제안3종문법통과. 물리수확성공/타입생성·통신을시험한것은아니다.
- 주요발견: 좌표만이아닌82D+접촉/진행상태 필요. 원본환경은scene/physics소유하므로farmWorld어댑터 필요. 첫실패batch종료/실패후assign거절/미수집분리과실복귀거절과복귀25ms/계산50ms불일치를보완해야한다.0.8m물리영역과Teacher도달범위는별개,주변장애물은정책관측에서제외됨. 농장root최소132.77mm,18cm미만34쌍/66개.
- 제안: 공통harvest_robot가후보순서/누적결과/취소/Window종료를소유, sim이후보발견/단일과실Teacher/실제결과·정지·다음시도준비ACK를제공. 외부HarvestTask필드유지,내부HarvestCandidate/GetHarvestCandidates/PickFruit추가. 대상파일/실물영향/검증안을제시하고사전확인질문을보냈으며아직미승인이다. 부분실패를수량으로반환하면서대상처리완료SUCCESS로보는안도확인대기.
- 승인/실물영향: sim Teacher 정답입력은이번사용자의명시지시로허용,예찰/실물입력으로확대하지않는다. 공통/실물실행소스·기존모델·자산·물성·운영설정 수정없음. 새ROS타입등록/빌드/팔GPU실행/전체수확E2E미실행. 추가정책파일은필수누락아니며담당자에게검증된연속도달범위·실패복구·독립추론접점이있으면요청하는문구만작성했다. 실제외부메시지는전송하지않았다.
- 다음: 공통범위/부분성과종결의미 확인 후 독립9g재현→농장단일과실→실패후순차진행→Action·취소→동시Nav2검증. 기존022의주행응답차이를해결완료로취급하지않는다.
- 복원:이번검토문서/제안/상태기록만비교복원한다. 기존미커밋022/사용자AGENTS·README/받은원본은보존한다. 이번검토는미커밋·원격미반영이다.


## SIM-COMMON-20261006-024 — 최소 공통 연결과 sim Teacher 실행

| 항목 | 내용 |
|---|---|
| 기준 | main/1666a23 이후 미커밋. 앞선 동적 물리·검토 및 사용자 변경 보존 |
| 승인 | 사용자 “대부분 로봇팔 구동 코드는 sim 전용 … 공통에서 도착하자마자 result를 날리면 그 부분을 sim 코드에 연결”. 앞선 빨강/노랑 각1회·Teacher규격·좌표정답사용 승인 유지 |
| 공통 대상 | harvest_robot의 node/mission/communication/contract 및 새 arm_client. 상세는 docs/changes/HARVEST_ARM_HOOK_20261006.md |
| sim 대상 | teacher_policy/state/device/_teacher_vendor, arm_session/arm_ros, ros_adapter/package/setup, run_fleet/physics_schedule, harvest/harvest_task/teacher_policy 설정, 정책4개+run자산, 시험/도구/문서 |
| 변경 전후 | 도착 후 수확0 즉시반환→시뮬 내부Action 실제완료·정지대기. 지역활성→후보확정→20Hz정책→물리복귀/안착→누적결과. 메시지신규타입/공통Window실행기 제안은 미채택 |
| 성과 의미 | 정상 후보전체처리SUCCESS, 실제안착·실패수량 별도. 취소는정지확인, 미확인은차단. 과실/관절teleport·재부착·가짜성공없음 |
| 실물 영향 | 실물설정/모델/장치·공통주행/비전·외부메시지 불변. legacy도착전용설정 유지. 현재새팔장치는sim만 선택 |
| 직접 검증 | 178단위/USD 중176PASS/ROS2skip, 별도실ROS/UDP2PASS,4패키지build. 최종Isaac fixture 실제정책/복귀/실패수량/정지/정상종료 PASS. 원본FK·CPU재생 대조. 자세한 숫자와 취소 결과는 실행보고서 |
| 성능 한계 | 실제농장3과실 적재0. ENTRYtimeout/bad_detach 후복귀. 적재성능PASS와구분. 다중과실/기존적재실물보존/Nav2전체E2E/실물/카메라/다수로봇 미검증 |
| 중간 실패 | SDK sensor/filter길이오류 수정, testerSIGINT/짧은Kit종료대기-11 수정. 최종프레임종료+60초대기 code0확인, 중간실패로그보존 |
| 결과 | sim/runs/robotarm/teacher_integration_20261006, teacher/<session>/<job>; 요약 sim/docs/changes/TEACHER_RUNTIME_VALIDATION_20261006.json |
| 되돌림 | 실행중지후 harvest_task completion_policy=ARRIVAL_ONLY_NO_HARVEST, harvest runtime.harvest_arm.enabled=false. 소스복원은 이번변경만, 다른미커밋변경초기화금지. 동적물리별도설정유지 |

[실행·검증 보고서](TEACHER_HARVEST_RUNTIME_20261006.md). 커밋·푸시는 수행하지 않았다.

## SIM-TEMP-CONTROL-20261007-025 — 임시 예찰→수확 관제 CLI

- 사용자 요청: 나중에 삭제할 사이클 확인용 관제를 sim 안에 추가. 공통/실물 소스 변경 없음.
- 추가: `sim/tools/temporary_control.py`, `sim/tests/test_temporary_control.py`. 실행 가이드 §7 및 PROJECT_STATE §21 갱신.
- Section 입력→ScoutArea 성공 최종 목록→원본 HarvestTask 순차 요청→수량 출력. 실패/취소 부분 예찰 목록 제외, 중복 ID 사전 거절, 수확 작업 실패 시 큐 중단. Ctrl+C 자기 Goal 취소/종료 대기, 정지 미확인 차단. JSONL은 sim/runs/temporary_control.
- 직접 검사: ROS 설치 메시지를 이용한 단위검사 6개, --help 로딩, diff 공백 검사. 실제 네트워크 Action/Isaac/Nav2 전체 사이클은 이번에 실행하지 않음.
- 기준 main/1666a23 이후 미커밋. 기존 미커밋 변경 보존. 커밋·푸시 없음.
- 되돌림: 위 임시 도구/시험과 가이드 §7 제거. launch와 로봇 실행은 변경하지 않았음.

## SIM-RVIZ-20261007-026 — FollowPath 추종 경로 표시

- 사용자 요청에 따라 sim의 scout_harvest/scout/harvest.rviz에 로봇별 `/received_global_plan` Path를 추가했다. 예찰 초록, 수확 주황, 선폭0.045m·높이0.12m. 기존 planner `/plan` 표시는 비활성화하고 이름으로 구분했다.
- 현재 GeoJSON 경로는 FollowPath로 직접 전달되므로 planner `/plan`만 구독하면 추종 경로가 표시되지 않을 수 있다. RPP가 발행하는 변환/가지치기 구간을 표시하며 전체 원본 Goal Path나 전체 그래프와 동일하다고 설명하지 않는다. 기존 route_markers 표시는 유지한다.
- 공통/실물/주행 코드·주기·도착 허용오차 변경 없음. 설치된 RPP 라이브러리의 토픽 이름과 YAML3개 설정을 확인했다. 실제 RViz 화면·이동 중 수신 검증은 미실행.
- RViz만 설정 재로드하면 적용. 되돌림은 이번 Path 항목 제거와 기존 plan Enabled 복원. 기준1666a23 이후 미커밋, 커밋·푸시 없음.

## SIM-NAV-20261007-027 — 베드 평행 접근 분석·공통 변경 승인 대기

- 사용자 베드 앞 정렬/평행 주행 요청.16개Section 모두 정차선과 기존 수확 graph가60mm 불일치함을 정적 확인. 실제6개 수확로그 최종60mm 구간이 목표 yaw와90도 차이. geometry.json에 저장.
- sim/docs/proposals/HARVEST_PARALLEL_APPROACH_20261007.md에 sim 수확 graph 정렬과 공통 선택적 진입/최종방향 검사·이미 도착 처리의 파일/영향/검증안을 작성. 실행 코드/설정/graph 미변경, 공통 승인 대기.
- 실제 새 주행 미실행. 기존 변경 보존, 커밋·푸시 없음. 되돌림은 이번 제안/분석 기록만 제거.

## SIM-COMMON-20261007-028 — 수확 평행 접근 적용

- 사용자 “수정해”로027 제안 승인. common farm_navigation3파일+parallel_approach.py, sim 생성기/task/survey/harvest graph/runtime/Nav2 설정 변경. 상세 docs/changes/HARVEST_PARALLEL_APPROACH_20261007.md.
- 주행선60mm 정렬, 넓은 기존 진입부 도착/정렬 후 평행 주행, 다른 구간 이동 전 정방향 이탈. 이미 도착 시 정지 재검사. 좁은 구간 복구 조건 불충족은 실패. 실물 옵션기본false/설정 불변.
- 신규7검사/371경로/build PASS. 기존도착검사9PASS/1구형메시지fixtureERROR. 실제 신규 Isaac 주행/회전충돌 여유 미검증. 사용자 실행 중인 프로세스는 재시작하지 않았음.
- 재시작 후 station에서 첫 Goal 재전송 필요. 기준1666a23 이후 미커밋·원격 미반영. 복원은 이번변경만 대상으로 한다.

## SIM-DRIVE-20261007-029 — 수확 회전·제동 보정

- 사용자 진입 정렬0.2486rad 실패 및 “해결해” 요청. sim base_sim/wheel_servo, harvest.json, nav2_harvest.yaml, harvest_runtime.yaml, drive_diagnostics, 물리 시험도구/단위시험/보고서 수정. 공통·실물 소스 및 원본USD 불변.
- 엔코더 각도차 속도 PI 보정과 정지시 적분 초기화·반대방향 제동. 수확만 활성화, 저속정렬0.06rad/s/각가속0.1/yaw gate0.01; 최종0.05rad 도착 기준 유지. 느린회전 대응 progress120/goal600초.
- 실제 Isaac 기존추가회전0.2534rad 재현. 최종 양방향 저속제동 추가회전0.00319/0.01317rad, 목표각도 후정지 오차0.00510/0.00932rad PASS/code0. 신규servo4+평행7검사/371경로/3패키지build PASS. Nav2 전체 경로·관제E2E·480Hz 동시주행 미실행.
- 비교시험 gain/solver/휴면 설정은 최종코드에서 제거. 중간시험 snapshot 공유 충돌 발견 후 별도 출력으로 수정. 해당 실패 및 중지한 비정상종료는 PASS 제외. 운영 snapshot 기반 평가가 시험 중 섞였을 가능성은 상세보고서에 기록.
- 상세 sim/docs/HARVEST_BRAKING_20261007.md, 결과 changes/HARVEST_BRAKING_VALIDATION_20261007.json. 사용자 운영프로세스 재시작은 하지 않았다. 적용은 all launch 재시작. 원복은 servo설정 제거 및 이번 속도/대기설정 복원. 미커밋·푸시 없음.

## SIM-NAV-20261007-030 — 실제 Nav2 코너 회전 시작 실패 보정

- 사용자18:06실패로그 직접 확인: controller_server Failed to make progress. 구동로그539072...에서첫코너전제자리 각명령약±.005rad/s. 이전 일정.06rad/s시험은 Nav2피드백결합 검증이 아니었다.
- sim nav2_harvest.yaml의 RPP.max_angular_accel만.10→1.2. 정렬속도.06/도착기준/PI/충돌검사 유지. 실제 전체Nav2 재검증 미실행. 설정생성일치/371경로검사 PASS.
- 실행중은 ros2 param set으로 적용가능. 사용자프로세스에는 자동 명령을 보내지 않았다. 원복은각가속도.10이나 기존정지문제재현가능. 미커밋·원격미반영.

## SIM-HARVEST-UI-20261008-031 — 배치·480Hz 수확 시험 패널

- 일자/기준: 2026-10-08 KST, main/7d9ae40ec8e0d0bebf0e0552f8a6ee85ddfc9bc3 이후 미커밋. 시작 Git 상태 clean. 원격 재조회·커밋·푸시 없음.
- 승인 근거: 사용자 “로봇팔 480hz 물리 연산 기준 … UI … 배치 버튼(수확가능한 열매가 있는 무작위 적정 위치) … 수확 버튼(480hz 전환, 인근 파프리카 물리)”. 시뮬 전용 시험 범위다.
- 파일: tools/harvest_test_ui.py; runtime harvest_test_placement.py/harvest_test_ui.py/run_fleet.py; devices arm_session.py/teacher_device.py의 읽기 전용 상태·장착점 조회; tests/test_harvest_test_{placement,ui,ui_launcher}.py; HARVEST_TEST_UI_20261008.md, RUN_GUIDE, PROJECT_STATE, 이 이력.
- 전후: 고정 fixture/CLI 위주 → 실제 Isaac GUI의 Place robot/Harvest/Stop 버튼으로 반복 관찰 가능. 기존 정차선/측정 팔 장착/Teacher 범위/원본 바닥지도 footprint 검사 후 미시도 부착 빨강·노랑 후보가 있는 배치를 선택한다. 차체 전체의 시험용 순간 배치이며 Nav2 성공으로 기록하지 않는다.
- 실행: python3 sim/tools/harvest_test_ui.py. 단독 수확 장치·사용 가능한 별도 UDP 포트·snapshot/로그 생성. ROS/빌드 불필요, 외부 UDP 제어 무시. 원본 fleet/지도/USD/Teacher/물성 보존. 공통·실물 코드 변경 없음.
- 물리/제어: 기존 ArmSession/Teacher/HarvestPhysics/AdaptivePhysicsTicks 재사용. 실제 정지/HOME/후보 재확인, 60→480→안정후60Hz, 주변 활성·20Hz 정책·실제 성공수량 유지. 활동 중 배치/중복 수확 차단. 적재 후 차체만 순간이동하거나 취소 후 비HOME 상태로 재배치하지 않는다.
- 직접 검증: 관련75검사 PASS(skip0); 새 배치10/UI13/실행기8 포함. Isaac5.1 GUI/RTX4070SUPER seed713 SEC10 Bed01/Pepper0017 yellow: 정책400회, 주변5/288 활성, 실제복귀/정지확인 및480→60Hz·활성0, 종료0. 처리SUCCESS지만 실제 적재0/실패1(target_timeout). 수확성능 개선 PASS가 아니다.
- 화면 검증: 최초 ReviewCamera 선택/한글 글리프 문제를 발견했다. Perspective를 명시 선택해 작업 팔과 과실/바구니를 보여주고 패널은 영문으로 제공한다. 최종 GUI 재실행·창 캡처에서 카메라/버튼/단계/480Hz/활성5개 표시 확인. UI 창 닫기 버튼을 제거하고 전체 Isaac 종료로 정리, timeline reset은 프레임 시작에서 감지한다.
- 로그/보고: sim/runs/harvest_test_ui/validation_20261008/{result.json,unittest.log,isaac.log,final_gui.png,final_gui_run.json}; 연결된 physics/teacher 경로는 result.json. 최종 GUI는 직접 조작하도록 실행 상태로 남겼다.
- 미검증/다음: 사용자 수동 클릭·다양한 seed의 실제 성공률·동시 운영 시뮬·Nav2 포함 E2E는 미검증. 적정 배치의 근거리/바닥 검사는 팔 IK/모든 동적 장애물 회피 인증이 아니다. 다음은 사용자가 버튼으로 반복 관찰하고 기존 Teacher 농장 성능을 별도 개선하는 일이다.
- 되돌림: 독립 도구/패널/기하/시험 추가 파일, run_fleet 선택 연결과 devices 읽기 API 및 문서 항목만 비교 복원한다. 전체 reset 금지. 배포 패치는 변경 파일만 sim/runs/harvest_test_ui/harvest_test_ui_20261008.tar.gz, 적용 명령은 실행 가이드에 기록했다.

## SIM-PHYSICS-INSPECT-20261008-032 — 충돌 메뉴·과실 물리 관찰

- 사용자 요청: Show By Type에 없는 Physics collision 표시 추가, 중력/connector 연결과 랜덤 회전 유지 여부 확인. 031 미커밋 변경을 보존하고 추가. 기준main/7d9ae40, 이번 원격 조회·커밋·푸시 없음.
- 대상: runtime 신규 harvest_physics_inspector.py 및 run_fleet/run_sim/harvest_test_ui; devices fruit_attachment 진단 snapshot/teacher_device 읽기 접촉 API; inspector 신규4검사/UI 추가2검사/접촉 추가1검사; 물리 진단 가이드·기존 UI가이드·PROJECT_STATE·이력.
- 전후: PhysX GUI 확장 미활성/수확 때만 확인 → GUI 실행에서 공식 omni.physx.ui 활성화, Show By Type > Physics > Colliders 메뉴와 패널 Hide/Selected/All 제공. Physics only 관찰은 팔정책 없이 기존 주변영역480Hz를 사용한다. 전역물성/원본USD/정책/실물·공통 코드는 변경하지 않았다.
- 계측: 선택 과실의 active/kinematic/gravity/collider flag, 초기 PhysX질량, 실제 pose/속도·root dz·tip 변위·회전각, 이전 tick 적용 줄기 힘, SDK 선택과실별 손가락 접촉력. mg는 Scene중력×질량 계산값임을 명시. 앵커/꼭지/COM/중력 표시만 추가하며 물리 joint를 생성하지 않는다.
- 발견: 현재 connector와 과실의 자유회전 native joint가 아닌 world 고정 앵커 spring + 초기 랜덤 quaternion 복원 토크다. 유휴부착과실은 kinematic. 중력이 작동해도 수직으로 완전히 정렬되지 않는 이유이며 성공0의 단일 원인을 확정하지 않는다.
- 직접검증: 99개 실행98PASS/1USD미설치skip/실패0. 실제GUI seed713 Bed01/Pepper0017 yellow, 팔정책 없이8초480Hz/주변5개: root하강10.788mm, 회전8.360°, 남은COM-꼭지기울기35.099°, mgZ -0.088290N/적용줄기Fz +0.088290N. collider1/1 convexDecomposition, 안정후60Hz/활성0, 종료0. 새GUI 재실행에서 와이어/표시와 선택과실별접촉0/0 확인. 이번 직접 수확접촉/파지 성공 검증은 아니다.
- 로그: sim/runs/harvest_test_ui/physics_inspection_20261008/{result.json,unittest.log,gui.png,final_gui.png}; 실행별 physics_inspection.jsonl. 최종 진단창은 열어두고 기존 사용자시험창/로그는 건드리지 않았다.
- 다음/한계: Harvest 중 실제집게 접촉력과 충돌형상 대조; 자유진자 connector 모델이 필요하면 별도 물리 모델 설계/Teacher 영향검증. 이번에 angular_k 완화/자세 초기화/가짜 성공은 하지 않았다.
- 복원: 032의 inspector/관찰 토글/읽기 API/GUI 확장 활성화와 해당 문서 항목만 비교 복원한다. 031 및 사용자 변경은 유지한다. 패치는 변경 파일만 포함, 적용 명령은 UI 가이드와 동일하다.

## SIM-TEACHER-DIAGNOSTIC-20261008-033 — 로봇암팀 요청 재현·회신 로그

- 승인/기준: 사용자 “robotarm/SIM_TEAM_TEACHER_DIAGNOSTIC_REQUEST 확인 … 자료 보고 회신 로그 확보”. main/7d9ae40 이후031/032 및 사용자 미커밋 변경을 보존했다. 공통·실물 코드/운영 설정·정책·물성·원본 robotarm 자료 변경 없음.
- 대상: sim teacher_policy.py에 기본off forward hook 계측; 신규 runtime teacher_diagnostics.py; run_fleet/check_teacher_harvest 선택적 --teacher-diagnostic-trace 연결; 신규 test_teacher_diagnostic_trace.py; 회신 문서·PROJECT_STATE·이 이력. 산출물은 sim/runs/robotarm/receiver_diagnostic_20261008.
- 전후: 기존 sample/최종action 위주 로그 → 실제 원본/시간보정/정규화82D와 전문가 raw action, 후처리/clip/최종6D, 상태 플래그, 실제 관절 target buffer·시뮬/벽시계·물리step·dt·초기/복귀/정지 연속 기록 및 USD/PhysX 설정. 추가추론/정규화 재학습 없음. USD 자동계산·무제한 Infinity는 최종계측에서 문자열로 저장하며 초기 노랑 원본은 보존하고 portable사본 추가.
- 전달본 직접 확인: 최초143434 TAR hash7b33...일치; 새해제본2148개검사 후 cache경로보정. 정책4개+run.json·전달평가소스불변. prepare/cache차이12파일은diff로보존.
- 실제 GPU 독립진단: 받은 무카메라 어댑터·전달실행기로 red182/yellow183각5회. 성공3+4/실패2+1, 두프로세스0종료. 송신10개trace1069tick가 SHA256까지일치. 카메라/YOLO포함원본스크립트E2E는미실행.
- 실제 GPU 농장: 기존headless fixture 노랑400POLICY timeout, 빨강42POLICY bad_detach, 실제적재0/2; 두job복귀/정지확인·종료0. 정책dt=.050000002608s, 각24physics step=480Hz. 원본관측/명령/PhysX전달 각19검사통과. taskSUCCESS/검증passed와수확성공을분리.
- 발견: 빨강양손접촉3.754/3.982N 있으나 파지확인0.05s<0.25s, 총변위46.790mm·지속41.667ms 이탈(인장0N), 정상파지전분리. 노랑최소거리74.99mm/양측접촉없음. farmUSD자기충돌false·solver32/1 vs전달소스true·12/4, 초기과실랜덤회전/고정차체차이. 단일원인으로확정하거나이번에수정하지않음.
- 검증: 실제가중치등Teacher/ArmSession60개+fleet entrypoint2개PASS, skip0; 새로운계측11개포함. 추가추론없이action/target·normalizer불변검사. diff --check/구문검사 및 회신manifest검증.
- 오류/한계: GUI2회는Teacher/recorder생성전World.__init__.render nativeOmniGraph SIGSEGV(-11). startup_error 로그별도보존, 성공/수확실패분모제외. 이번viewport영상미확보. 동일초기조건farm대조·Nav2·실물미실행.
- 회신: sim/docs/TEACHER_DIAGNOSTIC_REPLY_20261008.md, TAR+SHA256+MANIFEST. 원본stdout/trace/결과·설정·모델계약·관련source포함,checkpoint/RGB-D/전체해제본제외. 발송·커밋·푸시·원격재조회없음.
- 복원: 진단 플래그를 생략하면 기존제어경로다. 추가계측/CLI연결/시험·문서만비교복원하며031/032·사용자변경은유지한다. 다음은 담당자와같은q/목표pose/TF/threshold조건으로최초관측/action차이와solver·접촉영향을분리하는비교다.

## 2026-10-08 — AprilTag 태그 배치와 수확 PCWEB400 가상 카메라

- 구분/승인: 사용자 직접 요청의 sim bed 배치·수확 카메라/bringup 연결·공용 코드 인수 확인. 후속 답변으로 각 면100~114 반복/구간ID와 함께 식별 확정. 기준main/450bf5f, 기존 미커밋 수확 작업 보존.
- 대상: `assets/apriltag/`, 수확URDF, `farm_sim_config/config/{apriltag_layout,apriltag_map,harvest,scout,scout_fleet}.json`, 런타임`apriltag_scene.py` 및`run_sim/run_fleet`, 장치`camera_sim/camera_ros/ros_adapter`, generator·USD/렌더검증도구, 관련시험·상태/결정/실행문서.
- 전후: 태그없음/수확camera.disabled → session layer16벽240개(15원본반복), 수확측면optical센서 및RGB/CameraInfo발행. 기존공통bringup의sim장치선택으로연결해공통소스변경불필요. 실제웹캠depth없음. 예찰센서장착·경로·원본USD·실물설정은유지.
- 검증:19PASS,USD벽범위/크기/TF검사PASS,실제IsaacID104렌더검출/공유메모리전달PASS,3패키지build/371경로PASS. 첫Kit종료지연으로해당시험만정리, 최종렌더결과저장후종료timeout124. 최종반복IDUSD검사재실행. 전체DDS·이동검출/보정·실물미시험. [상세](APRILTAG_INTEGRATION_20261008.md),로그`sim/runs/apriltag_20261008/`.
- 코드인수: 로컬공용코드에AprilTag검출/보정없음. [요청서](APRILTAG_NAVIGATION_REQUEST_20261008.md)작성,발송없음. 공통수정승인대상diff는이번작업에없으며후속소스인수후검토한다.
- 실물영향: 없음. 실물harvest장치bringup은여전히미구현. 카메라장착은실측기반추정이며정밀실물검증완료가아님.
- 복원: 장치JSON의apriltag_map제거/harvest.camera.enabled=false후재시작,URDF추가광학링크/조인트제거. 기존미커밋수확변경을통째로되돌리지않는다. 미커밋·원격미반영.

## SIM-PEPPER-ROTATION-20261008-035 — 수확 비교용 랜덤 기울기 0도

- 사용자 요청: 기존 seed/최대각도 회전 스크립트를 찾아0도로Isaac적용. 기준 main/450bf5f 및 기존 미커밋·AprilTag 변경 보존.
- 도구: sim/tools/randomize_pepper_rotation.py → scout_dataset.stage.randomize_current_stage_and_save. 기존 구현 그대로 사용; sim/config/scout_dataset.json fruit_rotation.max_degrees만30→0, seed734유지.
- 실제 Isaac headless stage에서 기존 runpy 스크립트를 실행해 farm_with_plants_v5.usd 저장·정상종료0. 288개 jitter XYZ=0, world local-Z 기울기 전0.964~41.171°→후모두0°. 위치/원래xform op/ID 유지. 원래 yaw는보존하며모든quaternion이identity라는뜻은아님.
- 백업: sim/assets/envs/output/farm_with_plants_v5.usd.before_rotation_20261008_142400_041527. 설정백업/실행스크립트/stdout/전후288개검증은 sim/runs/pepper_rotation_zero_20261008.
- 실물·공통·물성·정책변경없음. 기존실행창의메모리상태는유지. 별도UI는초기화SIGSEGV(-11)로종료해ready미확인(gui.log/gui_result.json). 맵저장프로세스종료0과구분. 기존Isaac재시작으로새맵로드필요. 이번수확성공률재시험은아직수행하지않음.
- 복원: 위USD백업을원래파일로복사하고설정max_degrees=30(seed734)복원한뒤Isaac재시작. 커밋·푸시없음.

## SIM-HARVEST-UI-STARTUP-20261008-036 — 시험 GUI 시작 종료 수정

- 사용자 오류 수정 요청, 기준 main/450bf5f 및 기존 미커밋 보존. 대상: 런타임 `run_fleet.py`, `run_sim.py`, `harvest_physics_inspector.py`, `physics_schedule.py`, inspector 회귀 검사 및 상태 문서.
- 조기 PhysX UI 확장 활성화 상태에서 World 초기 render가 native SIGSEGV로 종료됐다. 확장 등록을 World/장치 초기화 뒤로 이동했다. 이후 드러난 dt 오류는 layers 확장이 USD 편집 대상을 session→root로 변경해, 더 강한 session의480Hz가 root에 쓴60Hz를 덮은 문제였다. 확장 활성화 성공/실패 모두 기존 edit target을 복원하며 dt 불일치 메시지에 실제/기대값을 추가했다. 충돌 메뉴와 엄격한 주기 검사는 유지한다.
- 실제 Isaac5.1 GUI: 일반3초/180tick 종료0, 물리 관찰14초/840render/4200tick 종료0. 1.520833초에480Hz·주변5과실 활성,9.520834초에60Hz·0과실 복귀. 일반 무기한 시험창 재실행 및 패널/60Hz 화면 확인 후 열어둠. 로그·화면 `sim/runs/harvest_ui_startup_fix_20261008/`.
- 관련 검사39개 PASS(레이어 복원 성공/실패, 주기, UI, launcher, fleet entrypoint). 넓은 harvest 패턴 검사112개에서는 별도 geometry 단일 테스트의48개 subtest 실패 및 sandbox UDP 차단3오류가 있었다. UDP 관련 launcher8개는 허용 환경에서 전부PASS. 경로 기하 실패는 이번 시작 수정 범위에서 수정하지 않았다. run_sim 실제 GUI 및 수확 성공률은 이번 미검증.
- 실물/공통/Teacher/물성/0도맵 변경 없음. 복원은 이번 확장 호출 이동·edit target 보존·오류 메시지만 역적용하며 기존 사용자 변경을 통째로 되돌리지 않는다. 수정 파일 묶음 `sim/runs/harvest_ui_startup_fix_20261008/changed_files.tar.gz`는 현재 미커밋 파일 전체를 포함한다. 커밋·푸시 없음.


## SIM-TEACHER-ARM-ALIGNMENT-20261008-037 — 학습 오른팔 물리 정렬

- 승인: 사용자 “로봇팔 물성치, 충돌 판정 … 다 학습환경에 맞춰서 수정”. main/450bf5f 및 기존 미커밋 보존. sim 전용, 실물/공통/전달 정책 소스 변경 없음.
- 대상: `teacher_arm_alignment.py`, `robotarm_asset_setup.py`, `harvest_physics.py`, `teacher_device.py`, `teacher_diagnostics.py`, `run_fleet.py`(종료 전 최초 예외 보존), `robotarm_physics.json`, 기준 팔usdc/manifest, 추출/대조 도구2개, 회귀 검사, 물리 확인/진단 회신·상태·결정 문서.
- 변경: convexHull→전달 convexDecomposition 메시15개; 여섯몸체 질량/COM/관성·집게카메라 합성; 자기충돌true/solver12·4, 학습GPU/TGS/접촉설정, material, 팔 collider1mm override제거, 학습4링크 접촉센서. 이동 차체·왼팔/바퀴 구동 구조 유지. 원본USD 미저장/세션적용. [상세 비교와 환경 차이](HARVEST_PHYSICS_INSPECTION_20261008.md).
- 검증: 독립 전달1회 종료0, 농장GUI3초 종료0, USD/PhysX115항목 일치(최종GUI 반복확인), 회귀56PASS. 수확480Hz/주변5과실 및60Hz복귀/정상종료0. 수확 적재0/1: arm_collision→return_contact_2.779N→safe_stopped=true. 수확성공률 개선/전체학습환경 동일성 검증 아님. 최종 GUI 열어둠.
- 최초 통합2회는 SDK 확장속성 API 부재로 초기예외, 종료native오류가 원인을 가림. typed USD attribute fallback 및 종료전 예외기록 후 해결, 세 번째부터 정상. 실패로그도 보존.
- 결과 `sim/runs/arm_physics_alignment_20261008/`, 설정/초기 코드 백업 포함. 복원: teacher_alignment.enabled=false 후 새실행(기존 팔 물리 경로). 전체 파일 reset 금지. 변경파일묶음/적용명령은 상세문서에 기록. 커밋·푸시/외부발송 없음.


## SIM-FRUIT-RENDER-SYNC-20261008-038 — 과실 물리/화면 위치 동기화

- 승인: 사용자 내부 적재 로그와 초기 위치 화면의 차이 조사 요청. main/450bf5f 및 기존 미커밋 보존.
- 대상: devices 신규 fruit_pose.py 및 fruit_attachment.py, runtime fruit_asset_setup.py, pose 신규검사/asset 설정검사, 물리진단·회신·PROJECT_STATE·이력 문서.
- 원인/수정: 사용자 정의 matrix op로 고정된 과실은 동적 PhysX만 이동하고 표시 root/mesh는 정지했다. 초기 배치/재고정 모두 pose를 보존한 표준 translate/orient/scale로 작성한다. 내부 SUCCESS만으로 화면 운반을 확인했다고 한 판단을 정정했다.
- 검증: 실제GUI 통제 이동·낙하23sample 최대 물리/표시 오차0.550647m→0.000590m(root0m). 최종5초/300render/1763physics/종료0. 초기3probe는 완료 후 잔류종료를 수동 정리했으며 최종 정상종료와 구분. 단위·USD43PASS. 새 일반GUI480→60Hz 및 화면 확인. 전체수확 성공 재검증은 미실행.
- 실물영향 없음. 정책·마찰·질량·성공기준·원본맵 불변. 결과/백업/변경파일묶음 sim/runs/fruit_render_sync_20261008. 복원은 before.py와 이번함수/검사 차이만 비교하며 기존변경 유지. 적용명령은 물리진단문서 마지막 절.
- 다음: 새GUI에서 실제 파지→운반→적재 관찰. 문서갱신, 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-OPT-20261008-039 — 단독 시험 UI의480Hz 비용 축소 (정적화는040에서 철회)

- 승인: 사용자의 PhysX step 최적화 요청. sim 런타임3개 파일(physics_schedule, harvest_test_ui, run_fleet)과 관련 검사만 변경. 실물·공통·원본USD·학습 팔 물성/충돌/주기 불변.
- 변경: 미사용 선별기/정찰 로봇43강체를 표시·충돌 형상 보존한 정적 배경으로 전환. USD 위치/속도 쓰기를 렌더 프레임의 마지막 tick에 수행. 힘/물리/접촉은480Hz 유지. 두 변경 모두 시험 UI에만 활성화.
- 실측: 동일seed713의480Hz GUI 수확에서 물리 step195.84→102.43ms, FPS4.28→7.01. 실제 적재0/1, 복귀 접촉 실패는 남음. GPU backend 유지; CPU/MBP10.51FPS 비교는 미적용.
- 검증: 관련37검사PASS, 운영GUI 종료0·표시 위치136표본/배경형상불변·PhysX오류0. 독립 sleep/재활성/480→60→480 시험 종료0(최대 위치오차1.92e-8m). Stop→재배치→240Hz 재수확 확인. [상세 수치·재현·범위](HARVEST_TEST_UI_20261008.md), 로그 sim/runs/physx_optimization_20261008.
- 복원: run_fleet의 configure_test_background 호출과 batch_usd_writeback 활성화만 역적용. 기존 사용자 변경/물성정렬/과실표시수정 보존. 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-RESTORE-20261008-040 — 네 로봇 동시 운용 요구에 따른 정적화 철회

- 사용자 정정: 예찰·수확·운송·선별팔은 최종적으로 모두 동시에 움직여야 하므로 다른 로봇 정적화는 부적절함.
- 변경: harvest_test_ui의 configure_test_background, run_fleet의 해당 호출, 전용 test_harvest_test_background.py 제거. USD 쓰기 프레임 단위 처리만 유지. 이전 GUI 세션 종료 후 새 stage로 실행. 원본USD/실물/공통코드 불변.
- 수치 정정: 7.01FPS/PhysX102.43ms는 두 로봇을 정적화한 폐기 조건이다. 로봇 물리 유지 시 기존 비교4.28→4.67FPS이며 네 로봇 동시 운용 실측은 미실행. fetch_results는 계산 완료 대기/결과 반영을 포함하므로 readback 주병목 단정도 철회.
- 검증: 스케줄러15·UI17·진입점2개PASS. 실제 물리 복원 로그는 sim/runs/physx_optimization_20261008/restored_scene.json 및 restored_ui.log. [현재 범위와 기록](HARVEST_TEST_UI_20261008.md).
- 사용자 변경 보존, 커밋·푸시·외부발송 없음. 정적화는 다시 적용하지 않는다.

## SIM-HARVEST-PHYSX-PROFILE-20261008-041 — GPU 커널과 대기 FPS 간극 실측

- 승인/기준: 사용자 “병목을 더 확실하게 파악 … 기존 Nav2 약70FPS와 현재대기22FPS 간극 확인”. main/450bf5f 및 기존 미커밋 보존. 운영 소스·설정·정책·원본USD·실물·공통 코드 변경 없음.
- 대상: `sim/runs/physx_bottleneck_20261008/`의 격리 계측 wrapper/결과와 `HARVEST_TEST_UI_20261008.md`, `HARVEST_PHYSICS_INSPECTION_20261008.md`, `docs/PROJECT_STATE.md`, 이 이력. CPU/MBP 전환·좌표기록 생략/캐시는 임시 대조 실행만 적용.
- 전후: fetch_results 경과시간만으로 CPU/GPU원인을 분리하지 못함 → Nsight CUDA/NVTX/OSRT와 PhysX profile zone으로428tick분리. USD쓰기없는fetch17.843ms 중GPU커널15.924ms, GPU→CPU복사0.0619ms/tick. 상위관절커널각15408회=428×36,1block×32thread. GPU solver최대반복32/4의 장면전체영향을 공식107.3소스/실제커널로 확인. 기존팔115항목속성검사한계를명시.
- 대기 비교: 동일ReviewCamera1280×720/센서OFF/각새프로세스. 모든기존로봇97동적/3관절계·과실형상4829유지, GPU29.80FPS→CPU50.23FPS. 좌표기록생략진단GPU31.95/CPU59.53FPS. 원본맵대조는43동적/2관절계/29convex/CPU,실제59.56FPS(60cap)·물리1.81ms. sleep제외처리용량138.49를실제FPS로사용하지않음. 원본맵SHA전후동일.
- 수확 비교: CPU480Hz작업13.01FPS,seed713적재0/1,RETURN_FAILED/2.839N·실제정지확인·정상종료0. 성공률개선/물리backend동등성으로해석하지않음. 상세현재GPU대조와좌표캐시결과는연결보고서참고.
- 검증/한계: 실제Isaac5.1 GUI격리대조와Nsight원본보존. 최초Nsight실행은optional SDK cooking API선택오류로capture전종료1,수정후최종종료0; 실패로그보존. CPU IP sampling권한제한은우회하지않음. 실제Nav2경로주행·과거사용자70FPS정확조건·최종4로봇동시미션·다지점수확회귀는미실행.
- 복원: 이번에는운영변경없음. 진단wrapper를사용하지않으면기존기본GPU/수확480/대기60Hz. 추가문서만해당절비교복원하고원본로그는보존한다. 다음은환경조건완화보다CPU480Hz접촉/관측/성공률회귀우선. 문서갱신,커밋·푸시·외부발송없음.

## SIM-HARVEST-REPORT-20261008-042 — 최적화 종합 자료와 Git 반영

- 승인: 사용자 “최근커밋 이후 수정사항 커밋메세지에 간략하게 … 480hz 물리 연산 적용 후 … 보고서 작성용 md”, 후속으로 commit+pull+push까지 명시. 기준 main/450bf5f 이후 미커밋 변경 전체를 보존·반영한다.
- 대상: `HARVEST_OPTIMIZATION_REPORT_MATERIAL_20261008.md`, `changes/HARVEST_OPTIMIZATION_EVIDENCE_20261008.json`, PROJECT_STATE 링크, 이 이력, sim/.gitignore의 회전 전 로컬백업 제외 규칙.
- 변경: 초기 CPU480Hz→지역 활성화/주기전환→UI/정확성 수정→Hz비교→USD쓰기→정적화 철회→Nsight/CPU/원본맵 대조를 종합했다. 핵심 JSON8개를 출처SHA256과 함께 버전관리 경로에 복사해 원격 보고서 작성에 사용할 수 있게 했다. raw runs/회전 전 백업은 로컬 보존한다.
- 범위: 이번 종합 과정에서 운영 로직·물성·backend를 추가 변경하지 않았다. 최근 미커밋에는 별도 승인된 AprilTag 작업도 포함하며 보고서에서 물리 최적화와 구분한다. 맵과 팔자산은 기존 LFS로 저장한다.
- 검증: 원본 JSON8개 hash/내용 및 Markdown 내부링크 대조 PASS, Python43개 구문 PASS, 기존 전달 CSV의 CRLF를 보존한 변경공백 검사 PASS. Isaac Python에서 수확/물리/진단58개, ROS Jazzy 환경에서 AprilTag4개 PASS(skip0). 최초 검사는 테스트 import 경로 누락, 이전 진단 대역의 PhysX view 누락, Isaac 환경 OpenCV API 차이로 실패했다. import 경로/실행 환경을 맞추고 `test_teacher_diagnostic_trace.py`의 대역 view만 보완해 통과했다. 운영 소스 변경은 없다. 성능/수확 숫자는 앞선 실제 시험 기록이며 보고서 작성 중 재측정값으로 표현하지 않는다. 최종 커밋·원격 반영 상태는 Git 결과를 따른다.
- 복원: 이 종합자료/링크/백업 제외 규칙만 필요에 따라 역적용한다. 이전 변경을 통째로 reset하거나 raw 로그·복원용 USD를 삭제하지 않는다.



## SIM-SCOUT-URDF-20261013 — PDF 장착 모델 반영

- 기준 main/a393f1a, 사용자 URDF 수정 요청 및 첨부 PDF 기준. sim scout 원본/portable URDF에 기둥·상판/홀더 근사 외형·봉·D435/파이캠 TF 추가. 기존 기본 링크/물성 불변, 공통·실물 소스 변경 없음.
- 변경 전 센서/장착 없음 → D435(-49,55,595)mm/하향1도, 파이캠(-32,63,117)mm, 기둥 상단620mm. PDF A/B/C 구분 유지; 추가 질량/관성은 미정.
- 직접 검증: XML/트리/기존 노드 보존/좌표·방향 계산. ROS·Isaac·실물 미실행. 기존 USD/실행 설정은 자동 변경되지 않으며 PC 적용/원격 반영 없음.
- [상세·한계·복원](SCOUT_URDF_MOUNT_20261013.md). 패치 역적용으로 복원하며 사용자 변경이 있으면 먼저 병합.


## SIM-SCOUT-USD-20261013 — 장착 USD 및 단독/fleet 연결

- 승인: 사용자 “usd까지 반영한다음 커밋푸쉬해”. 기준 main/a393f1a. 앞선 URDF 수정본까지 함께 반영.
- 대상: scout_mount_20261013.usda/하위 .gitattributes, build_scout_mount_usd.py, scout_mount.py, run_sim.py/run_fleet.py, scout.json/scout_fleet.json, test_scout_mount_usd.py 및 관련 상태·결정/보고서.
- 전후: URDF만 수정 → 실제 sim 진입점에서 기존 base_link에 장착 USD 참조·D435 transform 적용·파이캠/PDF TF 발행. 기존 Camera 광학/구동 joint/본체 질량 유지. 공통·실물 변경 없음.
- 직접 검사: OpenUSD26.8 합성 stage4PASS(비활성 prim 검증 결함 수정 후 통과), Python 구문PASS. 원본 농장 LFS binary 미확보로 실제 농장 합성/Isaac/PhysX/ROS/주행은 미검증.
- 복원: scout_mount_asset 설정 제거 및 재시작. 원본 USD는 세션 방식으로 보존. [상세·한계](SCOUT_URDF_MOUNT_20261013.md) 최상단 절을 따른다. 원격 게시 승인은 받았으며 최종 Git ref 결과로 게시 여부 확인.
