# 2026-10-27 로봇 운영본 → PC Git 소스 정리

기준 HEAD: cf870daa00e7b752a39bbb3c84fc61c412cb2de7, feat/harvest-handoff-real-20261018. 사용자 승인: 인계 완료·복귀까지 확인한 로봇 소스를 PC에 맞추고 시험 자료는 Git 밖에 보존. 커밋은 사용자가 직접 수행한다. 기존 PC 미커밋 변경은 사전 백업 후 유지했다.

## 확인한 실행과 범위

로봇 프로젝트는 Git 저장소가 아니며 새 init/clone을 하지 않았다. 조회 시 수확 운영 프로세스는 없었다. 마지막 20261026_215909_launch_237467 로그와 인계 저널을 확보했다. DOCK_TEST_c5ff0375c7af4e5a88c5748affd06a5d / TRANSFER_TEST_1f01cc263424453498c0dc3fa3dc19d2는 2026-10-26 22:02:49 시작, 22:05:06 SUCCESS, active=false/recovery_required=false다. 인계 후 복귀는 사용자 현장 확인 및 저널 SUCCESS로 확인했다. 다음 좌표 이동 실패는 사용자 보고이며 이번 작업에서 원인을 검증하지 않았다. PC 더미 팔 통신과 실제 팔 검증을 구분한다.

## 반영 대상

| 구분 | 반영 내용 |
|---|---|
| farm_navigation, harvest_robot, farm_wall_controller | 로봇 Downloads/sensor_hold_robot_20261024/src의 실제 운영 코드. 센서 대기·시각 분리·align 재검사·재시도 5회 지원 |
| farm_bringup harvest.launch.py | 로봇 프로젝트 설치본과 일치하는 인계 footprint_padding 전달 |
| farm_tag_camera_runtime, tag_camera 도구 | 이미 PC에 있던 운영 영상 종료 처리 유지. 로봇 프로젝트 원본과 일치 확인 |
| 실기 실행 프로필 | 아래 5개 파일에 실제 운영 값 보존. Downloads 절대 경로만 프로젝트 상대 경로로 변환 |
| trial_console | 기존 사용 중인 미니 웹은 운영 보조 도구로 유지. 후보 생성기·패치·시험만 외부 이동 |

예찰/Burger/다른 담당자 코드 차이는 복사하지 않았다. 적용 보류한 ForwardRecoveryController와 지속 재시도 후보도 반영하지 않았다. 기존 default 환경 설정을 덮어쓰지 않았다. 아래 프로필을 명시 선택해야 이번 실기 설정을 사용한다.

- robot/config/environments/harvest_handoff_real.yaml
- robot/config/harvest/harvest_handoff_real.json
- robot/config/localization/harvest_handoff_real.yaml
- robot/config/robots/vicpinky/transfer/handoff_fsm.json
- robot/config/robots/vicpinky/transfer/wall_alignment_wait_v2.json

실기 구성은 ARRIVAL_THEN_ARM, arm/discharge Action, navigation_collision_retry_count=5, 인계 padding=.01, 센서 회복 대기, wall observation_age=.45 및 태그 bias profile을 포함한다. 값은 현장 운영 원본과 동일하며 경로만 이식했다.

## 향후 PC 소스 배포 후 실행 참고 (이번에는 실행하지 않음)

로봇에 빌드·배포한 뒤 기존 Jazzy/드라이버/프로젝트 환경을 source하고 다음 인자를 사용한다. 현재 로봇 alias는 여전히 기존 Downloads overlay를 사용하며 이번 작업에서 바꾸지 않았다. PC x86 설치본을 로봇 ARM에 복사하지 않는다.

```bash
ros2 launch farm_bringup harvest.launch.py \
  project_root:=/home/vic/vmany/main/farm_project mode:=real \
  environment_config:=robot/config/environments/harvest_handoff_real.yaml \
  devices:=true navigation:=true tag_correction:=true tag_camera:=true \
  handoff_config:=robot/config/robots/vicpinky/transfer/handoff_fsm.json
```

PC 더미 서버와 Zenoh 후보 바이너리, 장비 드라이버는 외부 의존성이다. 이번 Git 정리가 이들 바이너리·더미를 저장소에 포함하거나 자동 설치한다는 뜻은 아니다. 해당 실행 설정과 원본 출처는 백업에 보존했다.

## 백업·제외

PC Git 밖 `/home/eunbi/vmany_artifacts/robot_sync_20261027/`:
- pc_before.tar.gz, git_diff_before.patch: 작업 전 PC 추적/미추적 소스와 미커밋 내용.
- robot_source.tar.gz, operating_overlay.tar.gz, latest_execution.tar.gz: 로봇 프로젝트/운영 overlay/마지막 실행 로그와 설정.
- install_match.json: 설치본 대조86개 모두 일치. sync_manifest.json: 반영 파일 전후 SHA256.
- excluded/: 신규 후보 생성기/시험 코드 및 runs 원본 약3.3GB.
- validation/: 별도 PC 빌드·검사 로그.

기존 Git에 이미 추적된 옛 runs111파일은 불필요한 삭제 변경을 피하려고 그대로 유지하고 외부에도 보존했다. 이번 신규 시험 디렉터리는 외부 실제 데이터로 옮기고 기존 경로에는 Git 무시 대상 링크만 남겨 문서·도구 참조를 유지했다. 신규 테스트 코드/로그/bag/빌드/설치본/백업은 커밋 대상에 포함하지 않는다. Git 이력에서 과거 자료를 제거하거나 rewrite하지 않았다.

원복은 pc_before.tar.gz와 sync_manifest.json의 대상만 대조 복원한다. 프로젝트 전체나 다른 사람 변경을 일괄 되돌리지 않는다. 로봇 원본은 이번 작업에서 변경하지 않았다.

## 이번 직접 검증

- 운영 Python/런치86개 로봇 소스↔설치본 바이트 일치. 반영 파일 SHA256 및 AST 검사 통과.
- PC 별도 colcon 빌드4패키지 성공: farm_navigation/harvest_robot/farm_wall_controller/farm_tag_camera_runtime. 기존 PC 운영 install은 변경하지 않았다.
- 빌드된 navigation/harvest 전체 Python 모듈 import 및 소스 일치, 노드 생성 없음.
- 현재 PC 소스로 충돌 재시도18개, wall clock19개, 기존 wall_control CTest1/1 통과.
- 새 상대경로 프로필 로드·인계 서버 구성 생성, TransferArc/WallAlign/Retreat/WindowCorrection 보존 확인. 검증 스크립트 첫 namespace 가정 오류는 반환 prefix를 사용해 수정 후 통과했고 운영 소스 수정은 없었다.
- git diff --check 통과. 새 실기 이동/재기동/전체 ROS 시퀀스 검증 없음. 커밋/스테이징/push 없음.
