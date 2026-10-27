# 로봇 프로젝트 기준 터미널 실행

`bash robot/tools/terminal/run.bash launch`는 프로젝트의 `robot/ros_ws/install/local_setup.bash` 및 `robot/config/environments/harvest_handoff_real.yaml`, `robot/config/robots/vicpinky/transfer/handoff_fsm.json`을 사용한다. 기존 운영 명령의 중복 차단·flock·TF executor·계측·로그 기록은 유지했다. `launch --check`는 명령 확인만 하며 노드를 시작하지 않는다.

환경은 기존 셸 overlay 경로를 제거하고 Jazzy → 기존 드라이버 workspace → 프로젝트 설치본 순으로 구성한다. 로봇 laun 별칭은 이 run.bash를 가리킨다. 기존 열린 터미널의 옛 run.bash도 launch만 여기에 전달한다. vinit/zen/dzen/vstat는 기존 연결을 유지하며 초기위치 발행·브리지는 자동 실행하지 않는다.

원복은 프로세스를 종료한 뒤 `/home/vic/vmany-runtime-backups/project_runtime_20261027/rollback_project_routing.py`로 연결만 복원한다. 원본 백업과 해시 검사 후 실행하며 이후 별칭 변경이 있으면 거절한다. 과거 저널을 덮어쓰지 않는다. 상세 검증은 docs/changes/PROJECT_RUNTIME_MIGRATION_20261027.md.
