# 공통 주행 재시도 선별 통합 — 2026-10-27

- 기준 main 68e5ef7, 원격 실물 5ff5b50. 사용자 “당장 필요한 작업 하고있자” 승인. 작업자 정리본 수령 전 최소 범위만 반영.
- 변경: farm_navigation의 collision_recovery.py, navigation_types.py, nav2_client.py, navigator.py 및 test/test_collision_recovery.py.
- 종료된 FollowPath의 ABORTED + NO_VALID_CONTROL(106) 중 빈 오류문구 또는 collision ahead만 선택 재시도. 105/다른 오류는 재시도하지 않는다. 같은 경로와 충돌검사 유지.
- 최소 정지2초, 정지·TF 준비 확인 최대30초, 설정 횟수 소진 시 실패. 매 반복 취소 검사. 대기시간만 전체 실행 제한에서 제외하고 기존 거리/속도 기반 제한시간을 보존.
- 기본 collision_retry_count=0. 실물·시뮬 설정 활성화 없음. 출력 소유자 정지 콜백 연결 API 제공, 미연결 시 기존 정지 publisher 사용. 기존 교통 request_stop의 비활성 구성 동작을 유지.
- 교통 미커밋 변경 보존. 인계 전용 PauseClock/벽 정렬/센서 대기, 신규 실물 프로필/실행도구는 가져오지 않음. 이 작업으로 양 브랜치 전체 동일성 또는105 해결을 주장하지 않음.

## 직접 검증

ROS Jazzy 환경에서 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, 소스 farm_navigation을 PYTHONPATH에 추가한 /usr/bin/python3 pytest:
- test_collision_recovery.py, test_nav2_route_timeout.py, test_nav2_execution_clock.py, test_parallel_approach.py: **32 passed**.
- 재시도 상한/기본 비활성/잘못된 설정/취소/준비시간초과/다른오류 미재시도, 실제 Nav2Client 재시도 연결의 대기 제외와 경로 예산 유지 검증.
- 첫 시도는 PYTHONPATH 덮어쓰기로 ROS 모듈 누락, 두 번째는 교통 시험 farm_interfaces 생성 모듈 누락으로 수집 실패. 환경 경로를 보존하고 미빌드 교통 검사는 제외해 위32개 통과. 교통 검증 완료로 간주하지 않음.
- 실제 Isaac/ROS Action 통합 주행, colcon 재빌드, 실물 검증 미실행. 재시도는 아직 활성화하지 않았으므로 운영 성능 변화 없음.

## 다음 단계/복원

작업자 정리 브랜치 수령 시 변경6파일을 선별 대조하고 인계 출력 소유권과 교통 연결을 함께 검증한 뒤 시뮬 재시도 활성화 여부를 결정한다. 활성화 전 실제 ABORTED106 분류·105 미재시도·정지 출력·취소를 ROS Action 통합으로 확인한다. 실제 시뮬은 Domain13/SUBNET CPU/headless 유지.
이번 변경만 역적용하며 기존 교통 수정 전체를 되돌리지 않는다. 변경 전 미커밋 diff는 sim/runs/recovery_integration_20261027/before.patch. 미커밋/미푸시.
