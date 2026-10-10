# 수확 태그 Git 기준 고정 — 2026-10-10

## 기준과 이번 범위

사용자 PC HEAD 7689f3648007c643f01a2dcaee160ae6fcbefcdd, feat/apriltag-localization, 17:45:03 제공 작업본 기준이다. 패키지 적용 전부터 존재한 HarvestWork·scan_sync·pixel_bias 변경은 보존한다. 이번 추가는 문서, 모터 전용 udev 규칙, 설치/확인 도구다. 예찰/공유 launch/주행 코드·제어 설정은 이번 패키지에서 수정하지 않는다.

## 기존 변경을 검토할 묶음

| 묶음 | 주요 경로 | 의미 |
| --- | --- | --- |
| 작업 제어 | harvest_real.json, nav2.yaml, harvest_robot/node.py·staged_navigation.py·test | 기존 HarvestWork 선택·작업 제어 분리 |
| 시각 연결 | farm_tag_amcl/, farm_bringup/launch·package.xml, farm_tag_localization/runtime.py·node.py·test, check_runtime.py | 기존 scan_sync 연결 |
| 편향 보상 | pixel_bias.py, bias_trial_20261010/, bias_trial/, test_pixel_bias.py | 선택적 시험 보상 |
| 기록 | docs/, 패키지 README, sim/docs/CHANGELOG.md | 단계별 변경·검증 기록 |
| 이번 신규 | vicpinky/udev/, robot/tools/vicpinky_motor_latency.py | 모터 한 대의 latency_timer 영구 설정 |

scout_navigation.launch.py는 이름과 달리 기존 수확 launch에서도 재사용하는 파일이며, 받은 변경은 tag_scan_sync=false 기본값과 실물 수확의 AMCL 선택 연결이다. 변경을 삭제하거나 새로 수정하지 않는다. 파일명만 보고 이번 태그 변경에서 제외해 연결을 깨뜨리지 않는다. 실제 scout_new 코드는 수정하지 않는다.

## 직접 확인한 검증

- PC node.py·pixel_bias.py와 ON 주행 inputs 스냅샷 바이트 동일.
- ON 로그 요청/queued/applied 10/10/10, 요청→적용 식별자 및 pose 대조와 라이다 재계산: 상세 인계 문서 참조.
- 신규 Python 도구·전달용 적용/배포 도구 구문 검사 PASS.
- 모터 도구 오프라인 5개 검사 PASS: 설치→재적용→확인→복원, 다른 시리얼 거절, 다른 기존 규칙 보존, 심볼릭 링크 보존, 현재값만 1이고 규칙이 없는 상태를 영구 설정 성공으로 오인하지 않음.
- 위 모터 검사는 임시 sysfs 모형과 udev 명령 대역을 사용했다. 실제 udev 파서/이벤트 검증은 로봇 install에서 수행한다. 이 환경에는 udevadm 및 로봇 하드웨어가 없다.
- 기존 59개 태그 검사·ROS/C++ 빌드 기록은 해당 변경 문서의 과거 이력이다. 이번 문서/새 시스템 설정 변경에서 전체를 재실행했다고 주장하지 않는다.

## 적용·확인

전달물 apply.py는 모든 대상 파일을 먼저 비교하고 하나라도 제공 이후 변경됐으면 아무 파일도 수정하지 않고 중단한다. 같은 전달물 재적용은 무변경이다. 백업은 /home/eunbi/vmany_backups에만 생성한다. git add/commit/push는 하지 않는다.

deploy_motor.py는 새 도구와 규칙 두 파일만 로봇에 전송한다. 동명 파일 내용이 다르면 전송 전 중단한다. 같은 내용은 유지한다. 전송 후 sudo install을 요청하며 모터 이동 명령·ROS 재시작은 없다. 실행 중인 수확 주행은 종료한 뒤 설치한다.

## VS Code commit/push 전

1. 이번 적용 결과와 기존 변경을 함께 diff로 확인한다. 동일 명명 신규 파일의 충돌은 덮어쓰지 않는다.
2. 로봇 INSTALL_OK가 확인되면 PROJECT_STATE 및 VICPINKY_MOTOR_LATENCY 문서에 설치 확인 시각/결과를 추가한다. 재부팅 검증은 별도이며 다음 정상 재부팅 때 check한다.
3. VS Code에서 이번 태그/HarvestWork/scan_sync 및 신규 영구 설정·문서 파일을 확인해 stage한다. 관련 없는 다른 작업자의 변경은 제외한다. 변경 목록만 보고 전체 git add .를 자동 수행하지 않는다.
4. 새 docs와 farm_tag_amcl·bias_trial의 미추적 파일도 함께 확인한다. rosbag, runs, build, install, log, 백업은 stage하지 않는다.
5. git diff --check 및 git diff --cached --stat를 확인하고 은비가 commit/push한다. 제안 제목: 수확 태그 보정 검증 기준 고정 및 모터 지연 영구 설정.
6. push 완료 SHA로 Confluence 「04. 개발 → ROS2」 새 문서를 작성하고 이 인계 문서·코드·프로파일을 고정 커밋 URL로 연결한다. 지금은 Confluence 페이지 미생성이다.

원본 로그·패치는 인계 문서의 파일명/SHA256으로 식별한다. PC 실제 보관 경로는 확인되지 않아 임의 경로를 원본 위치로 기록하지 않았다.

## 복원

모터: VICPINKY_MOTOR_LATENCY_20261010.md의 remove 명령. 문서: PC 적용 백업의 대상 파일과 비교해 이번 추가만 되돌린다. 사용자 미커밋 전체를 reset/clean하거나 원격으로 되돌리지 않는다.
