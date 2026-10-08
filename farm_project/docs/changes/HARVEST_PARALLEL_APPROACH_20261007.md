# 수확 평행 접근 — 승인 후 적용

사용자가 sim/docs/proposals/HARVEST_PARALLEL_APPROACH_20261007.md 제안에 “수정해”로 승인했다. 기준1666a23 이후 미커밋, 기존 사용자 변경 보존.

## 변경

- 공통 farm_navigation/navigation_types.py: parallel_approach 기본false. navigator.py: 실제 양쪽 오차가 충족된 재요청은 정지 후 재측정; 외부에서 진입할 때 진입부 목표/yaw까지 이동·정지·도착 검사 후 평행 작업 구간을 요청한다. 다른 베드로 갈 때 현재 구간을 정방향으로 빠져나간 뒤 다음 진입부로 이동한다.
- route.py: 환경 graph metadata의 parallel_approach_corridors 로드. 새 parallel_approach.py: 목표 구간/방향 선택, 좁은 구간 횡오차/방향/전방 조건 검사. 조건이 맞지 않으면 APPROACH_RECOVERY_REQUIRED로 중단한다. 자동 후진·좁은 구간 제자리 회전·역방향 그래프 엣지를 만들지 않는다. path_builder.py는 기존 보간을 그대로 사용한다.
- sim rebuild_route_data.py: 수확 파생 graph만 오른팔 기하의 x선으로60mm 평행 이동. 원본 graph 연결/방향, station 위치, scout/transport 파생 graph 유지. 연결 구간도 이동한 끝점으로 재생성하며 엣지 cost 갱신. task.yaml harvest_route.x_m와 scout_survey 파생 메타데이터 동기화. 좌표 상수 대신 장착/작업 기하에서 생성한다.
- harvest_runtime.yaml에서만 선택 기능true, nav2_harvest의 goal_checker.stateful=false. 최종 도착/충돌 기준 완화 없음. 실물/공통 기본 설정 불변.

## 확인 결과와 제한

- 새 검사7개 PASS:16개Section 마지막 구간 방향/직선 거리, 오프라인 목표 거절, 자세/횡오차/지나친 목표 거절, 기본옵션, 도착 재측정/정지 중 이탈, 진입→평행 요청 순서.
- validate_route_data.py:371개 연결 경로,16Section/80관측점, 원본/파생 일치 PASS. compileall/diff검사 및 farm_navigation 빌드 PASS.
- 기존 test_scout_arrival 10개 중9개 PASS,1개 ERROR: 예전 fixture의 section_ids 필드가 현행 survey_server의 section_id와 다르다. 이번 변경 경로를 실행하기 전 실패이며 이 작업에서 기존 시험을 수정하지 않았다.
- 실제 Isaac/Nav2 신규 주행, 진입부 회전 swept footprint와 장애물 여유, AMCL/물리 정지 변위는 아직 미검증. 기존 y=±10.7/±1.3 진입·이탈 위치를 사용하며 물리적으로 안전한 공간이라는 인증은 하지 않는다. Nav2 충돌 검사는 유지한다.
- 이미 좁은 구간에서 크게 틀어진 자세나 지나친 목표는 자동 복구하지 않는다. 조건을 충족하지 않으면 복구 필요 실패. 처음 확인은 launch 재시작 후 station 출발로 한다.
- 기존 외부 HarvestTask Goal 좌표/ID는 그대로 유효하다. 처음부터 예찰하지 않고 저장된 Goal 재전송 가능. 정책 적재0/3 문제와는 별개다.

## 적용/되돌림

빌드는 완료했다. 실행 중 노드는 재시작 필요. all launch를 종료하고 기존 명령으로 재시작한 뒤 첫 수확 Goal을 재전송한다. 새 주행 JSON의 approach_route/approach_arrival/route를 확인한다. 다음 Section이면 exit_route/exit_arrival도 기록한다.

되돌릴 때는 이번 공통 옵션/도구/파생 graph 변경만 복원한다. 전체 git reset은 다른 미커밋 변경을 지우므로 사용하지 않는다. 커밋·푸시 미실행.
