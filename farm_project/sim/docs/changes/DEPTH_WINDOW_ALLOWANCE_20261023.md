# 예찰 깊이 전용 ±2cm 여유 — 2026-10-23

- 기준: main/0832b6f1827d912d827667e4c50aacf3a3f4e549 및 기존 미커밋 변경.
- 승인: 사용자 “그정도면됐고 y축오차에 따른 윈도우 생성 허용 범위를 좀더 넓히자”, 축 구분 질문에 **“베드 깊이 방향에 ±2cm 추가”** 선택. 직전 위치 추정 개선 수준은 수용했다. 맵 Y(진행 방향) 확대가 아니다.

## 적용

공통 b_planner.Config에 depth_tolerance=0 기본값 추가, survey_core에서 harvest.depth_tolerance_m을 연결했다. 신규 anchor 검사/윈도우 편입 및 extend_plan의 기존 창 편입·재검증·관측 목록 갱신에 모두 같은 깊이 여유를 적용한다. 기존 range_tolerance는 유지하며 깊이 축에서만 추가 여유를 합산한다. 기본값0으로 기존 실물/기타 프로파일 동작을 유지한다.

시뮬 task.yaml의 SEC01~16에 depth_tolerance_m=0.02를 지정하고 공식 rebuild_route_data.build 경로로 scout_survey.json만 재생성했다. 다른 생성 파일·실물 설정·팔 실행 필터·물리 장면·과실 배치는 수정하지 않았다. 직전 시험의 런타임 설정에서 patrol_file로 병합된 patrol_segments를 제외하면, 파생 설정의 차이는 새 깊이 여유 필드뿐임을 확인했다.

- 실제 작업 상자/명목 윈도우 깊이: 10cm, 중심 ±5cm 유지.
- 예찰 생성/편입의 깊이 판정: 중심 ±7cm, 총14cm.
- 진행 방향·높이 여유 및 수확 로봇 목표 경로: 유지.
- 각 윈도우와 survey 기록에 depth_tolerance_m을 남기고 acceptance_corners_map_m의 깊이 축만 확장했다. 공통 scout_new/scout_node 및 legacy survey_server의 기존 window_tolerance 마커도 깊이 여유가 있을 때 표시한다. corners_map_m는 실제 명목 상자를 유지한다. ROS Action/메시지 정의 변경 없음.

변경 파일: scout_robot/scout_robot/{b_planner.py,survey_core.py,survey_server.py}, scout_new/scout_node.py의 마커 조건1줄, 시뮬 task.yaml/scout_survey.json. 기존 survey_core 정렬 및 scout_node 교통 관련 미커밋 변경은 보존했다.

## 검증

- 신규 깊이 여유 회귀6개 PASS: 양쪽 경계, 기본0/음수·비유한값 거부, 높이·진행 방향 비확대, 기존 창 편입, 재검증 유지/탈락,16SEC의 물리10cm/판정14cm 및 다른 축 보존.
- 기존 프로토콜6개/윈도우 순서1개 PASS. 총13개. tests는 독립 프로세스로 실행해 기존 전역 stub 간섭을 피했다.
- validate_route_data.py PASS: 16SEC/80관측/371계획 경로 및 연결성 확인. 실제 Isaac 주행 시험과 구분한다.
- 저장된 등록 과실 좌표/기존 Plan을 복원해 extend_plan으로 판정만 재생했다. 원시 영상 검출·과실 ID 연결·주행·수확은 재실행하지 않았다. 기본0 재생이 각 기록의 expected와 일치함을 먼저 확인했다.
- 08_capture_sync의 깊이 범위 밖 F0009: expected12→13, hold1→0. 기존9개 창의 목표·깊이/위치·물리 작업 상자는 그대로 유지.
- 최근09/10/11/12/13의5개 기록: expected13→13, hold0→0. 창 위치/기존 작업 상자 보존.

원본 재생/결과: sim/runs/depth_window_allowance_20261023/{replay.py,replay_result.json}. 공유 수치·소스 SHA256: DEPTH_WINDOW_ALLOWANCE_20261023.json. 이번 수정 후 실제 Isaac/수확/실물 재시험은 미실행이다.

## 복원

시뮬16개 section의 depth_tolerance_m을0으로 바꾸고 예찰 파생 파일만 같은 build 경로로 재생성하면 이전 판정으로 돌아간다. 전체 git reset이나 다른 작업자의 변경 되돌리기는 하지 않는다. 미커밋/미푸시.
