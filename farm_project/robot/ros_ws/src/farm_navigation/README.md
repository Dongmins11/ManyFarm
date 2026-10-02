# 공통 주행 라이브러리

각 로봇 Node가 생성해서 사용하는 라이브러리다. 별도 실행 노드나 관제 작업 서버가 아니다.

- 경로 계산: 방향 그래프의 엣지 중간 목표까지 탐색.
- 실행: NavigateToPose 또는 FollowPath. 자동 fallback 없음.
- 위치: TF 조회. 위치추정과 TF 발행은 별도 계층.
- 정지: odom 최신성과 속도를 확인. 장치 odom을 재계산하지 않음.
- 결과: 요청 ID·계획 ID·정지 확인 시각·도착 오차.

자세한 구성과 환경별 실행은 [구조 문서](../../../../docs/navigation_common_structure.md)를 참고한다.
