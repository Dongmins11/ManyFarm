# 수확 복귀 컴포넌트 통합 및 설정 선택 (2026-10-31)

기준: 로컬 `c197799` + 기존 미커밋 변경, 실물 `cf4023b6fa99497d992410620986272cd927128b`.
승인: 사용자 “우리코드 분석해서 실물 수치를 그대로 쓸지 시뮬레이션용으로 수정할지 결정하고 반영해”. 기존 전진/후진 선택, 시뮬 스테이션 마커 생략, 시뮬 시간 사용 지시를 함께 유지한다. 진행 중 시험은 중단하지 않았다.

## 결정과 최종 값

| 항목 | 실물 기준 | 시뮬 적용 | 이유 |
|---|---|---|---|
| 복귀 단계 | Mission / Controller / States | 같은 원본 컴포넌트 | 상태·완료·취소·정리 책임을 통일 |
| 주행 속도 | RPP/StationReverse 0.1m/s, RPP 방향 정렬 0.1rad/s | 동일 | 기존 최종 병합 설정도 일치, 변경 없음 |
| Nav2 도착 | 4cm / 2.5° | 동일 | 완화하지 않음 |
| Navigator 최종 검사 | 5cm / 6° | 복귀에만 동일 | 일반 수확 주행 설정은 건드리지 않음. 전체 사이클 생성기는 기존에도 6°였음 |
| 충돌 재시도 | 5회, 소유한 출력으로 정지 후 재시도 | 인계 포함 사이클 5회 | 기존 인계 출력 소유자 연결 시에만 활성화 |
| 단독·교통 프로필 | 실물 성공본의 출력 소유자 전제와 다름 | 기존 0회 유지 | 해당 출력 연결 없이 5회 설정 시 노드 초기화 실패. 무조건 재시도하지 않음 |
| 태그 갱신 | 0.2초, 같은 구역 토큰 유지 | 0.2시뮬초, 같은 정책 | 방향 변화만으로 태그 세션을 재생성하지 않음 |
| 스테이션 | node18, (0.046,-1.12), +90° | node8002, (-2,13.25), -90° | 지도·모델 위치 차이 |
| 경로 방향 | 실물 원본 후진 | 기존 짧은 전진/후진 선택 유지 | 사용자 기존 명시 요구. 전진도 최종 스테이션 방향·정지까지 확인 |
| 코너 원호 | 전용 launch 기본 반경0.20m, 후진 좌회전/최대90° | 활성화하지 않음 | 시뮬 임의 코너 모두 지원하지 않음. 기존 RPP·충돌 검사 유지 |
| 벽 도킹 | 뒤/왼쪽 측정거리 약0.520/0.496m, 5mm/1° | 활성화하지 않음 | 실물 구조물 측정값. 시뮬에는 같은 스테이션 벽 배치가 없음 |
| 팔 상태 생략 | 차체 단독 프로필 true | 가져오지 않음 | 기존 팔 준비·인계 문맥 무효화 검사 유지 |
| 성공 의미 | 실제 선택 도킹과 정리 완료 | 기존 위치·최종방향·정지·정리 후 SUCCESS/docked=true | 물리 도킹을 했다는 의미로 확대하지 않음 |

최종 YAML 상속·override와 전체 사이클 생성 경로를 직접 실행해 확인했다. 원격 shared_nav2 + 실물 overrides와 시뮬 해석 결과의 복귀 관련9개 제어값은 일치한다. 근거: `sim/runs/return_components_20261031/effective_settings.json`, `prepared_cycle/runtime/harvest_runtime.yaml`.

## 소스 반영·보존·제외

- `harvest_robot/station_return_states.py`: 원격 원본 그대로. Controller만 전환, 작업은 별도 worker, 세대가 지난 완료는 무시.
- `harvest_robot/station_return_mission.py`: 원본 유지 + 선택형 경로 선택 콜백·시계 주입. 미주입 기본은 원본 후진/단조시간 그대로. 실물 도킹 객체를 주입한 동작도 보존.
- `harvest_robot/station_return_components.py`: 공통 Action과 원본 Mission/Controller 조립. 기존 `plan_station_return` 사용, 기존 출력 소유권을 확인한 정지만 재시도 경로에 연결. 별도 속도 제어/복귀 업무 복제 없음.
- `farm_common/station_return.py`: 원격의 `_run_mission`, `_cleanup_mission`, `_mission_docked`, client_factory 경계 도입. 로컬 전진/후진 선택·시뮬 시계 유지. 태그 종료 예외에도 Nav2 정리를 실행하고 정리 실패를 성공으로 반환하지 않음. 예찰 기본 경로는 동일.
- `farm_navigation/route.py`: 원본 reverse_plan. `nav2_client.py`: 원본 선택형 후진 충돌 오류 분류, ABORTED + NO_VALID_CONTROL 경계 유지. 최근 시뮬 시간 수정 및 로컬 TF 대기/준비 변경 보존.
- `harvest_robot/node.py`: 명시 `station_return_components` 프로필에서만 새 조립 사용. 기본/실물 프로필의 기존 연결을 자동 전환하지 않음.
- `sim/config/harvest_runtime.yaml`, `harvest_traffic_runtime.yaml`: 선택 및 복귀 검사값. `prepare_harvest_handoff.py`: 출력 소유자 포함 실행에서 기존 실물 재시도5회를 복귀에도 주입.
- 실물 전용 RealStationReturn, 코너·벽 도킹 구현/C++ 옵션/전용 launch·장착값은 이번 활성화 대상에서 제외. 실물 브랜치 전체75파일을 병합한 작업이 아니다. 원격 실물 실행이나 설정을 덮어쓰지 않았다.

## 검증

회귀48PASS. farm_navigation/farm_common/harvest_robot 및 farm_sim_config 빌드 성공. Controller 원본 바이트 일치 검사 통과.

- 원본 상태 전환·오류 분류 테스트를 sim/tests로 가져와 import 및 기존 시뮬 clock 주입 테스트만 맞춤. 원문은 runs/source에 보존.
- 전진/후진 선택, 최종 yaw 전달, 도킹 선택/미선택, 준비·주행·취소·정리 실패, 태그 종료 실패 시 Nav2 취소 및 소유권 반환, 태그 유지와 시뮬 시간, 기존 예찰·수확 공통 복귀, Nav2 시간 회귀를 검사.
- 전체 사이클 설정 생성만 실행: 실제 ROS Goal 또는 Isaac 주행을 실행하지 않음.
- 실제 시뮬 귀환/실물 주행 동등성 검증은 미완료. 실행 중 노드는 기존 코드, 다음 새 노드·새 설정 생성부터 적용. 기존 실행 폴더 설정을 소급 수정하지 않음.
- 후속 사용자 커밋·푸시/시험 승인. 커밋 대상만 HEAD에 겹친 독립 소스로도 48PASS 확인. 기존 전진/후진 선택과 인계 실물 재시도·도착값 연결은 의존 변경으로 함께 포함하며, 무관한 TF 대기·준비·촬영 수정은 작업 트리에 보존한다. 실제 시험 결과는 후속 실행 로그로 구분한다.

## 되돌리기

시뮬 프로필의 `station_return_components`를 false로 바꾸고 설정/수확 패키지를 재빌드하면 기존 공통 복귀 경로를 사용한다. 이번 훅 추출의 정리 예외 보완과 기존 전진/후진 선택은 유지된다. 변경 전 소스는 runs/source의 `.before`에 있다. 이전에 진행하던 다른 변경을 reset/checkout으로 제거하지 않는다.
