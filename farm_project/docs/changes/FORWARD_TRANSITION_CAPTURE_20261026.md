# 전진·회전 전환 재시험 수집 준비 — 2026-10-26

사용자 승인: 기존 코드/설정 유지, 필요한 로그 준비, 사용자가 기동·웹 시험. 운영 코드 변경/초기위치/이동/복구·반복 서비스 호출 없음.

도구 PC: runs/forward_transition_capture_20261026/collect.py, collect.bash.
로봇 배치: /home/vic/Downloads/forward_transition_capture_20261026/ (운영 실행경로와 분리).
로봇 foreground 명령: `bash /home/vic/Downloads/forward_transition_capture_20261026/collect.bash`.
환경은 기존 environment.bash/domain77. 웹 작업은 CAPTURE_READY 및 별도 준비 확인 이후 사용자만 발행한다. 도구를 background/systemd로 등록하지 않았다. 이번 턴 수집 자체는 시작하지 않았다.

수집: 일반 raw cmd_vel_normal→cmd_vel_nav→cmd_vel, 실제 odom, RPP lookahead/curvature point·is_rotating_to_heading·received_global_plan·collision_arc, 일반 costmap full/update·footprint, 원본/filtered scan, TF/staticTF·AMCL/map, status/task/tag events/rosout/parameter_events/initialpose. 이미지 제외. TF/센서 header stamp와 bag 수신 시각을 구분해 분석한다. 메시지의 동시 도착을 같은 controller 실행 snapshot으로 단정하지 않는다. is_rotating_to_heading은 stamp가 없어 수신시각 연결의 한계를 유지한다.

기동 시 실제 controller/harvest/amcl/smoother argv 및 params-file 읽기 사본, 설정 사본, 주요 publisher 수를 저장한다. 최신 launch console은 전후 복사한다. 필수 publisher 미발견이면 recorder를 시작하지 않는다. recorder의 필수 토픽 구독 로그를 확인한 경우에만 CAPTURE_READY. 종료시 metadata/파일 SHA manifest/result 보존. 5분(선택30~600초), bag160MiB 또는 디스크 여유3.1GiB 미만에서 recorder만 SIGINT. 시작 시3.25GiB 필요. 기존 기록 자동 삭제나 로봇 정지 명령 없음. 용량/시간 제한 종료는 작업 종료를 의미하지 않으며, 수집이 조기에 끝나면 사용자에게 알린다. 별도 터미널 Ctrl+C도 recorder만 종료.

검증: PC Python 구문/--help, Bash syntax, 로봇 배치 후 --help/Bash syntax. 전체 실행·DDS 구독·bag 저장은 다음 사용자 기동 후 확인해야 한다. 도구는 /tmp flock으로 자기 중복 기동만 차단한다.

현재 읽기 확인: 로봇 laun/harvest/controller/driver/tag/Zenoh 없음. PC 실제 host의 더미7183·bridge7242·웹7267 실행 중이므로 중복 기동 불필요. PC dummy journal recovery_required=false(서비스 readiness와 구분). 로봇 실제 위치는 질문했으며 답변 전 vinit 안내는 조건부다. 사용자 프로세스 기동·종료 없음.

재시험: 물리 스테이션 위치/방향 확인→필요한 복구표시만 미니콘솔에서 확인(자동 해제 없음)→사용자 laun→IDLE/정지 확인→사용자 vinit→zen/dzen→웹/정합/costmap/더미 준비 확인→foreground 수집 시작→CAPTURE_READY/구독 확인→동일#59 1회 반복 허용→사용자 웹#59 1회 전송. 도착·수확 완료 또는 실패 후 10초 기록하고 Ctrl+C. 실패 시 재전송/인계 없이 위치 유지. 로봇이 코너에 있다면 vinit을 실행하지 않고 재배치 여부부터 확인한다. 기존 후보 플러그인/임계값은 적용하지 않는다. commit/push 없음.
