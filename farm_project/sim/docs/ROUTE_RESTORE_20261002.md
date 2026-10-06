# 연결 경로·station 데이터 복원

후속 변경: 이 문서는 데이터 복원 당시 기록이다. 이후 예찰 station 자동 배치·AMCL 연동을 적용했으며 현재 동작은 `STATION_SPAWN_20261002.md`를 따른다.

사용자 요청으로 인수본에 남아 있던 과거의 분리 그래프 대신 기존 연결 데이터를 복원했다. 모든 변경은 `sim/` 안에 있다. 공통 코드·실물 설정·메시지·USD 자산은 변경하지 않았다.

## 복원 기준과 결과

- 원본: `farm_scout_harvest_count_v0.8.5.zip`의 `task.yaml`, `scout_harvest.geojson`, `count_test_farm_map.yaml/png`.
- 운송 대기점·선별장 용도: `sim_route_design_v1.zip`의 설계 정보. 좌표는 최신 그래프의 8003/8004 노드와 일치한다.
- 연결 그래프 원본은 바이트 그대로 복원했다. 227개 노드, 516개 방향 엣지이며 모든 노드가 서로 도달 가능하다.
- `SEC01`~`SEC16`, 구역별 5개씩 총 80개 고정 관측점, 8개 물리 베드 대응, 수확 진입/이탈 노드·방향을 보존했다.
- 최신본의 왼쪽 팔 좌표계와 예찰/수확 동일 진행 방향을 보존했다. 과거 오른쪽 팔/역방향 설정으로 되돌리지 않았다. 작업 영역은 여전히 임시 직육면체이며 IK 검증 결과가 아니다.
- 구형 시험 전용 `test`, `harvest_robot` 실행 설정과 테스트 서버·FSM·액션 정의는 가져오지 않았다.

| 대상 | 노드 | map XY (m) | yaw | 상태 |
|---|---:|---|---|---|
| scout_01 | 8001 | (-5, 13.25) | -π/2 | 최신 task의 값 복원 |
| harvest_01 | 8002 | (-2, 13.25) | -π/2 | 최신 task의 값 복원 |
| transport_01 | 8003 | (2, 13.25) | 미정(null) | 기존 설계안 |
| sorting_station | 8004 | (5, 13.25) | 미정(null) | 기존 설계안 |

## 수정할 원본과 현재 실행 설정

경로는 프로젝트 루트 기준이다. 아래 설정·지도는 모두 `sim/ros_ws/src/farm_sim_config/` 안에 있다.

| 파일 | 용도 |
|---|---|
| `config/task.yaml` | 구역·관측점·베드·station 데이터 원본. 출처 해시 포함 |
| `maps/scout_harvest.geojson` | 모든 역할의 연결 경로 원본 |
| `maps/count_test_farm_map.yaml/png` | 원본과 함께 보관된 지도. 이름은 출처 보존용 |
| `maps/graph.geojson` | 현재 예찰용 파생 그래프: scout 허용 엣지만 포함 |
| `maps/harvest_graph.geojson` | 수확용 파생 데이터. 현재 수확 런타임에는 연결하지 않음 |
| `maps/transport_graph.geojson` | 운송용 파생 데이터. 현재 운송 런타임에는 연결하지 않음 |
| `config/scout_survey.json` | 현재 공통 StraightBed가 읽는 베드 정의 |
| `config/scout_patrol.json` | 현재 공통 patrol이 읽는 고정 관측 순서 |
| `config/scout_runtime.yaml` | 복원 지도·예찰 그래프·patrol을 선택하는 활성 환경 파일 |

공통 RouteGraph는 `allowed_roles`를 해석하지 않는다. 역할별 파생 그래프에서 허용 엣지를 미리 선별했다. 원본의 resource 메타데이터는 교통 제어 구현을 뜻하지 않는다.

공통 StraightBed의 시작/끝은 원본 `survey_geometry` 좌표와 정확히 같도록 유지했다. scout 파생 그래프에 `SECxx_START/END` 32개 경계 노드를 기존 직선 엣지를 나누어 넣었다. 통로 추가나 관측 좌표 이동은 없다. 따라서 scout 파생 그래프는 211노드/452방향 엣지이며 원본의 227/516과 수가 다르다.

앞으로 원본 수정 후 다음을 실행한다. 파생 파일만 직접 수정하면 검증에서 불일치로 처리한다.

```bash
python sim/tools/rebuild_route_data.py
python sim/tools/validate_route_data.py
```

## 이번에 적용한 범위와 남은 연결 작업

현재 예찰은 `SEC01`~`SEC16`과 `SEC01_G01` 등의 고정 Segment ID를 읽는다. 구형 `BED_01` 등의 Goal 이름은 이 시뮬 프로파일에서 사용하지 않는다. 공통 ScoutArea 메시지의 `section_ids` 배열 형식은 그대로다. 각 구역 완료 후 명령 대기이며 자동 station 복귀를 추가하지 않았다.

**station은 데이터 복원까지 완료했다. 현재 단일 로봇 Isaac 실행부는 task.yaml의 station을 읽어 자동 배치하지 않는다.** USD 시작 위치와 AMCL 초기 위치는 기존 값을 유지했다. 예찰 주행 모드도 `navigate_to_pose`를 유지한다. 연결 그래프가 복원됐다는 사실과 실제 이동이 그래프를 따라 실행된다는 것은 구분해야 한다. task.yaml의 `navigation_backend`는 복원 원본의 값이며 현재 모드 선택은 scout_runtime.yaml의 `navigation.mode`가 담당한다.

다음 실행 통합에서는 station 시작 배치와 AMCL 초기 위치를 함께 연결하고, 경로 위 시작 위치 확인 후 FollowPath를 전환해야 한다. 수확·운송 실행과 자동 복귀·도킹·교통 제어도 이번 데이터 복원 범위에는 포함되지 않는다. 공통 코드 변경이 필요하면 먼저 승인을 받는다.

## 검증과 패치

- 현재 공통 환경 로더, RouteGraph, StraightBed, apply_patrol, patrol_design으로 검사했다.
- 모든 80개 관측점의 station 출발·복귀와 구역 간 연속 이동, 수확 진입/이탈, 운송의 선별장 접근을 포함한 371개 경로 계산이 통과했다.
- 원본 16개 구역 전체 내용, 베드 대응, 예찰·수확 station 값이 보관본과 동일하다. 원본 지도와 그래프 파일도 동일하다.
- 원본 그래프 227개 노드 모두 지도 범위 안의 free 픽셀에 있다. 로봇 footprint 여유나 동적 장애물 통과 시험은 아니다.
- 기존 파일 해시와 비교해 이번 작업의 변경은 전부 sim 내부임을 확인했다.
- ROS/Isaac 실행·실제 주행·colcon 빌드는 수행하지 못했다. 검사 결과는 `ROUTE_RESTORE_VALIDATION_20261002.json`에 있다.

패치는 인수본의 현재 공통 코드 기준이며, 직전 설정 분리 패치의 sim 내부 파일도 포함한다. `robot/`, `control/`, 루트 스크립트는 포함하지 않는다. 예전 harvest-scout 패치 전체를 덮어쓰지 않는다. 시뮬 실행은 `farm_sim_runtime scout.launch.py`, 단독 비전은 `python sim/tools/run_scout_vision.py`를 사용한다.

적용 전 시뮬을 중지하고 변경 대상 파일을 백업한다. 원복할 때는 이번 패치로 새로 생긴 파일을 제거하고 기존 파일을 백업에서 복원한다. `sim/runs/`의 실행 결과는 삭제하지 않는다.
