

<!-- HARVEST_MIDSTART_20261011 -->
## 수확 직선 구간 중간 시작 수정 — 2026-10-11

- 승인: 사용자 “수정해”. 전달받은 TF recovery 작업 복사본 기준. 현재 로봇 Git HEAD/원격 미조회, commit/push 없음.
- 문제: StagedNavigation 첫 요청은 항상 진입점(실물 11번)을 먼저 요청해 작업 구간 중간에서 역방향 경로/회전을 유발할 수 있었다.
- 변경: harvest_robot/node.py, staged_navigation.py, 새 corridor_navigation.py와 실물 harvest_real.json의 work_corridor_nodes=[10,14]. 좌표는 graph.geojson에서 읽는다.
- 명시된 구간 내부에서 현재 위치/방향과 전방 목표를 검증하고 SECTION_RESUME → WINDOW_MOVE. 기존 HarvestWork FollowPath/충돌 감지/정지/도착 검사 재사용. 작업 경로는 현재 위치→목표 직선. 구간 밖에서는 기존 진입 단계 유지. 실패 후 다음 요청도 현재 위치로 재판단.
- 뒤쪽/동일 위치 목표는 WORK_TARGET_NOT_AHEAD로 이동 요청 전에 거절한다. 방향 및 횡오차에는 기존 허용값을 사용한다. 진행 중 타이머/감시/중단 조건 추가 없음.
- 이탈은 기존 Navigator를 별도로 유지한다. 중간 시작용 설정이 없는 환경은 기존 동작. farm_navigation/예찰/카메라/TF 설정/제어기/costmap은 수정하지 않는다.
- 직접 검증: 실제 Navigator/경로 보간/단계 이동 코드에 ROS 입출력만 대체한 오프라인 시험 10개 통과. 중간 전방, 뒤쪽, 방향 불일치, 구간 밖 진입, 10번 끝점, 연속 요청, 실패 후 재요청, 목표 방향, 기존 단계 흐름, 급격한 횡방향 경로를 검사. Python 문법 검사 통과.
- 실물 Jazzy 빌드 및 폐루프 주행/물리 충돌 여부 미검증. Wi-Fi/DDS 정체 원인 해결과는 별도 수정이다.
- 설치: install.py가 대상 파일 해시 확인, 실행 중 로봇 검사, 저장소 밖 백업 후 적용. 문서는 기존 내용에 이 절만 추가한다. 다른 소스 버전이면 덮어쓰지 않는다.
- 복원: 설치기의 backup 경로에 있는 restore_manifest.json 기준으로 해당 파일만 복원하고 harvest_robot 재빌드. 새 corridor_navigation.py는 복원 목록의 false 항목이며 제거한다. 설정만 끄려면 work_corridor_nodes를 제거하고 재시작한다.
- 다음: 로봇 정지/실행 종료 후 적용·harvest_robot 빌드. RViz 실제 초기 위치 지정, ready 확인, 현재 위치 앞쪽 작업 하나로 실물 확인. 완전 해결을 선행 선언하지 않는다.

- v2: 17:46 수신한 로봇 소스와 대조. staged_navigation.py의 끝 빈 줄 1개 외 로직 차이 없음, node.py/harvest_real.json 바이트 일치. 확인한 staged_navigation.py 해시만 설치 허용 목록에 추가. 패치 소스 및 보호 검사 유지.
