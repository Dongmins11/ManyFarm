# 2026-10-27 로봇 프로젝트 운영 경로 전환

사용자 승인: 기존 성공 코드/백업 유지, 로봇 프로젝트 기준으로 정리하고 laun을 프로젝트 설치본에 연결, 동작 변경 없이 빌드·검증. 기준 HEAD cf870daa00e7b752a39bbb3c84fc61c412cb2de7 위 미커밋 정리본.

## 적용
- 로봇 실행 프로세스 없음 확인 후 project robot/ros_ws/src의 farm_navigation/harvest_robot/farm_wall_controller를 실제 운영 overlay와 일치시켰다. farm_bringup 런치도 동일한 운영본을 유지했다.
- 프로젝트 workspace에서 위4패키지 ARM 빌드 성공(46.1초). 별도 Downloads overlay는 삭제/변경하지 않고 원복용 보존.
- 인계/수확/태그 설정은 PC와 같은 상대 경로 프로필5개를 설치. 값 변경 없이 경로만 프로젝트로 연결.
- robot/tools/terminal/{run.bash,environment.bash,terminal.py} 추가. 기존 터미널 도우미의 순서/중복 차단/flock/입력/로그/전용TF 환경을 유지하고 launch 경로만 변경. 환경은 이전 셸 overlay 검색 경로를 초기화하고 Jazzy/드라이버/project local_setup을 source한다.
- 로봇 Downloads/manyfarm_terminal_20261024/aliases.bash의 laun만 새 경로로 변경. 기존 열린 셸의 옛 run.bash는 launch 요청만 새 경로로 전달한다. 다른 별칭·.bashrc·브리지 설정·복구기록 변경 없음.

## 직접 검증
- 변경전 로봇/PC before.tar.gz SHA256 c8255a17d5c48a674d243f9fa77e4de07d5beba688c8532b1fac46a503b81dca 일치.
- 기존 overlay 모듈70개와 프로젝트 설치 모듈의 SHA256 전부 동일. 운영 소스 파일 비교도 시험/cache/bak 제외 모두 동일.
- 기존/신규 환경의 수확·handoff·wall·태그 설정과 생성 controller/costmap/behavior 서버 bundle 전체 동일.
- WallController/WallGoalChecker/WaitingProgressChecker/WaitingSpin 로드/소멸 성공 및 /proc/self/maps에서 project install/libwall_controller.so 확인. 노드/Goal 생성 없음.
- 로봇 기존 wall_control CTest1/1 통과. 이전 overlay를 먼저 source한 환경에서도 project 환경 재설정 후4패키지 prefix 전부 project install 선택.
- 기존 alias 진입점 launch --check가 프로젝트 환경/인계 설정을 선택하며 충돌 PID 없음 확인.
- 최초 검증은 이전 overlay에 없는 프로젝트 추가 모듈 motion_reference까지 비교하려다 import 실패. 기존 overlay 실제70모듈 기준으로 수정하여 통과. 마지막 소스 대조는 pytest cache 차이를 검출해 코드/cache 범위를 분리 후 통과. 운영 코드 오류를 숨기거나 수정한 것이 아님.

## 백업과 원복
로봇 `/home/vic/vmany-runtime-backups/project_runtime_20261027`, PC `/home/eunbi/vmany_artifacts/project_runtime_20261027`에 원본/검증/라우팅receipt/원복도구 보존. 프로세스 종료 후 로봇에서 `python3 /home/vic/vmany-runtime-backups/project_runtime_20261027/rollback_project_routing.py` 실행 시 변경후해시를 검사하고 기존 laun 연결2파일만 복원한다. 실행하지 않았다. 소스/설치본 전체 원본도 before.tar.gz에 있으나 무관한 파일/저널을 일괄 덮어쓰지 않는다.

## 남은 범위
이번 작업에서 로봇 재기동·초기위치·이동·실기 재시험은 하지 않았다. 동일성/빌드/무기동 검증은 통과했지만 경로 전환 후 실기 검증 완료를 뜻하지 않는다. 로봇 디스크 여유는 작업 전후 약2.7GiB이며 기존 카메라3GiB 시작 검사보다 적다. 기록을 임의 삭제하지 않았으므로 카메라 기동 전 공간 확보는 별도 필요하다. 다음 window 이동 실패는 미해결. commit/push 없음.


### 2026-10-27 공간 확보 완료
사용자 승인으로 최신8개 터미널시험 폴더를 보존하고 이전119개 로그폴더와 설치본이 참조하지 않는6개 CMakeFiles 중간폴더를 PC로 백업 후 제거. 1122항목/원본2,242,692,718바이트 목록·크기·SHA256 및 tar 내용을 전부 대조했고 삭제직전 원본 재검증 완료. PC `/home/eunbi/vmany_artifacts/space_cleanup_20261027/robot_logs_build.tar.gz`, SHA256 dcd1108628769447ce7182b8ada40ae5bb1477fc38e171b70791896cc64353b8. manifest/verified/removal/protected_check 보존. 성공소스/설정/설치본/기존overlay/원복백업 해시불변 확인. 여유2,805,272,576→5,050,974,208바이트(약4.70GiB). install이build생성파일을심볼릭참조하므로build전체삭제하지않음. 로봇운영프로세스기동/이동/코드설정변경없음.
