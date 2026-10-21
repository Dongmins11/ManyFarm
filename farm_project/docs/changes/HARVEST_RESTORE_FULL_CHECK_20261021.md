## 전체 실행 연결 검사 후보 — 2026-10-21 패키지

사용자 PC의 실제 arc_trial.py 별도 프로세스 9항목이 통과했다. 성공 기록은 /home/eunbi/Downloads/harvest_restore_runtime_check_xHZnQV이며 runtime SHA256은 ae9a8c0b98ece07e4ee0a0f1104dbb9de705d259b87b2ccf6bb719d57a0de97f다. 벽 종료 fixture와 smoother 파라미터 대역을 사용한 결과이므로 전체 연결/실물 결과로 확대하지 않는다.

사용자 ‘준비해’ 승인으로 Downloads 후보에서 실제 restore_sequence.py → arc_isolated 감독/벽 실행 → 기존 Navigator/Controller → 실제 velocity_smoother 연결 검사를 준비했다. 기본 실물 Bash의 domain 77 및 설치 경로는 그대로 유지한다. 명시 HARVEST_PC_CHECK=1에서는 domain 95/localhost/FastDDS, Downloads 후보·독립 플러그인 설치 경로와 Python 모듈 위치를 확인하고 사전 로딩 환경을 사용한다. PC에서 실물 domain으로 빠지는 것을 막는다. 실물 restore_sequence.bash 차단은 유지한다.

검사 순서: departure/wall/retreat/align/return 각 plan/execute 10항목 및 footprint 장애물 departure plan 거절 1항목. 기존 상태/증명 파일을 실제 순서 도구가 생성한다. 벽 종료 위치를 강제 설정하지 않고 이상 평면 환경의 LaserScan을 기존 WallTracker/WallController가 처리한다. 실제 CLOSED_LOOP velocity_smoother 출력을 이상 모델에 적분한다. 지도·TF는 PC 검사 전용이며 실물 지도/모터 성능을 검증하는 것이 아니다.

기존 성공 후보/상세 결과를 새 검사 폴더의 preserved_success에 복사하고 파일 해시를 기록한다. 이전 v4와 두 C++ 패키지 소스 일치 시 독립 설치본을 재사용하며 벽 플러그인만 새 Downloads 설치본으로 빌드한다. 기존 제어기, arc_trial, 공통 주행 코드, 충돌/속도/정지 기준과 성공 벽 설정은 변경하지 않았다.

직접 수행: 오프라인 회귀 238개 PASS, Bash/Python 구문 검사, 성공 핵심 5파일 해시 보존, 실제 wrapper의 잘못된 domain 진입 차단. 실제 ROS 전체 연결은 이 환경에 Jazzy가 없어 미실행이다. 사용자 PC 실행 결과 전에는 완료로 간주하지 않는다. 프로젝트 적용/로봇 접속/실물 이동/커밋/원격 Git 검증 없음. 후보 삭제로 되돌릴 수 있다.
