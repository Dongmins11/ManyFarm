# scout_robot

real/sim 공통 예찰 로봇 코드입니다.

- `route.py`: map 좌표(미터)의 GeoJSON 경로점과 연결 관계 읽기.
- `route_preview.py`: 경로와 카메라 방향 표시. 이동 명령 없음.
- `drive_route.py`: 명시적으로 실행하면 Nav2에 경로점을 순서대로 전달. 실패 시 중단, Ctrl+C 시 자신의 목표 취소.
- `config/scout.rviz`: 예찰 로봇 지도·LiDAR·경로 표시 설정.

현재 범위는 1번 베드 주행입니다. 관제 ScoutArea 서버, 정차 관측 계획,
YOLO, 수확 작업 생성은 다음 단계이며 구현된 것으로 간주하면 안 됩니다.
실행법은 프로젝트 `docs/navigation_stage.md`를 보세요.
