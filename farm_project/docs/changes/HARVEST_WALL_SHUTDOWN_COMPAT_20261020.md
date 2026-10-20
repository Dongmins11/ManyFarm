# 벽 시험 종료 API 호환 수정 — 2026-10-20

직접 원인: 로봇 rclpy의 Executor.shutdown은 wait_for_threads 키워드를 지원하지 않았지만 이전 코드가 이를 무조건 전달했다. Jazzy 최신 브랜치 소스만으로 설치 API까지 동일하다고 판단한 오류다.
wall_shutdown.py 한 파일에서 inspect.signature로 실제 API를 확인한다. 지원할 때만 wait_for_threads=True를 전달하고, 미지원 API는 timeout_sec만 전달한다. 종료 반환값과 spin thread 종료 확인 후에만 객체 제거하는 조건은 유지한다. 예외를 잡아 무조건 성공으로 바꾸지 않는다.

구형/신형 API 각각 정상, executor 미종료, spin 미종료 총6개 모의 검사 및 구문 통과. 실제 설치 ROS executor에 타이머 콜백을 한 번 실행시킨 뒤 같은 종료 함수를 검증하는 smoke_ros.py를 배포 단계에 추가했다. 이 실제 ROS 검사가 성공해야만 벽 plan 8초 검사로 진행한다. Goal/속도 발행 없음.

계산 개선 후 사용자 로봇 출력: fit 2.98~27.79ms, 관측 나이 최대245.17ms, 관측 오류 없음. 그러나 종료 예외와 core dump로 전체 시험 실패. 본 수정의 실물 종료 성공은 아직 미확인이다.

기존 주행·곡선·costmap·태그·지도·속도·거리·300ms 설정 수정 없음. 공통 구현 한 곳 수정. 정확한 이전/이후 해시만 적용, PC/로봇 원본 백업 및 문서 갱신, Git 커밋 없음. 복구는 출력된 백업의 wall_shutdown.py만 원래 경로에 복원한다.
