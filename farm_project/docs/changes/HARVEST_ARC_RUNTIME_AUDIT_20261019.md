# 곡선 시험 실행 경로 보존 및 원인 확인

- 성공 실행 20261019_145603_892617_on과 실패 실행 203412/204623 비교: 기존 로봇 입력 사본 18개 동일. 최종 Nav2 설정의 차이는 추가 플러그인/판정기 및 시험 BT 경로.
- 두 실패의 직접 정지 메시지는 RPP detected collision ahead. 106의 근본 원인과 사용자 관찰 동작 변화 원인은 아직 미확정.
- PYTHONPATH로 전체 소스 farm_navigation을 launch에 우선시키는 코드를 제거. 시험 Python 프로세스에서만 설치 패키지 검색 경로 뒤에 새 모듈 경로를 추가한다. 기존 모듈은 설치본을 우선한다.
- task_events는 작업 종료 시 navigation 기록을 포함하며 transient-local QoS를 사용한다. 노드가 살아 있는 동안 기록을 읽기 전용으로 회수할 수 있다. 노드 재시작 전 수집 필요.
- arc_runtime_audit.py: ListParameters/GetParameters와 task_events 구독만 사용. 설정 변경/Goal/속도 명령/초기 위치/clear costmap 없음. 현재 Nav2 YAML 대비 실제 파라미터 차이를 저장한다. 현재 스냅샷은 실패 순간 파라미터의 증거와 구분한다.
- 검증: 26개 기존 회귀 검사, 설치/소스 내용이 달라도 기존 설치 모듈이 선택되는 별도 subprocess 검사, Python 및 shell 구문 검사 통과. ROS 수집 실행은 작성 환경에 ROS가 없어 미검증. 오류/응답 없음도 보고서에 남긴다.
- 이번 변경을 충돌 원인 해결 또는 실물 주행 성공으로 기록하지 않는다. 기존 설정/지도/태그/충돌 검사 보존.
