# 실기 성공본 PC 반영 및 커밋 준비 — 2026-10-23

## 확인 범위

사용자 요청: 로봇 실기 성공 코드를 PC Git 작업 트리에 맞추고 시험 산출물을 분리한다. commit/push 및 staging은 사용자가 VS Code에서 직접 수행한다.
기준 Git 루트 `/home/eunbi/vmany/main`, branch `feat/harvest-handoff-real-20261018`, HEAD `4b5c5b13605216d1b8b163ea988805572a6a908a`와 기존 미커밋 변경.

실기 성공은 21:15 body-only 인계 COMPLETED 및 동일 프로세스에서 21:30:43 그래프14 목표 일반 주행 SUCCESS 각1회다. 팔은 NOT_TESTED. 웹 관제 실제 다음 window 전송, 반복 신뢰성, 다른 로봇 실기 검증은 미완료다. 노드14 이동은 SECTION_RESUME/WINDOW_MOVE 직선 FollowPath이며 그래프 전체 경로 추종을 입증하지 않는다.

## 출처와 반영

로봇 harvest PID129702(21:04:46 시작), 기존 설치본 실행. startup trace의 runtime/planning/navigation/PoseProvider/ActionHandoff 해시와 해당 파일의 현재 소스·설치본을 대조했다. 관련 설치 대응84개 Python/launch 파일 바이트 일치(setup.py4개는 설치 대응 대상 아님).
로봇 원본은 변경하지 않았다. PC의 기존 미커밋 원본과 diff를 먼저 외부 백업하고 파일25개를 반영했다. PC와 로봇이 이미 같은 launch, 컨트롤러, Vic Pinky 설정은 다시 덮어쓰지 않았다. controller 목록 및 기존 costmap/footprint 설정 유지.

| 범위 | 반영 내용 |
|---|---|
| harvest_robot | 현장 window 연결, TF 전용 문맥 선택, 센서 갱신 시 출력 보호, 정지/취소/세션 보호, 재진입 정책10mm 선택, body-only 실행 및 내부 계측 |
| farm_common/action_handoff.py | 외부 check의 condition 밖 실행 현장 핫픽스 |
| farm_navigation | pose_provider 동일시각 조회/진단, parallel_approach 핫픽스 |
| 수확 설정 | harvest_real heading 한계 및 handoff_body_trial 프로필 |

이번 성공에 관계없는 scout_robot/scout_new·burger/scout 설정 차이는 가져오지 않았다. 독립 시험용 wall_trial_runtime.py와 robot/tools/transfer 기존 도구도 로봇의 더 오래된 버전으로 되돌리지 않았다. PC 기존 추적 시험 파일은 삭제하지 않았다. runtime이 import하는 handoff_body_trial/input_trace/locking과 그 설정은 실행 의존성이므로 유지한다.

## 실행 조건

**코드 일치만으로 실행 옵션이 자동 적용되지는 않는다.** 성공 실행은 `HANDOFF_TF_EXECUTOR=dedicated`, `HANDOFF_INPUT_TRACE=<로봇 로그 디렉터리>` 환경과 `handoff_config:=robot/config/robots/vicpinky/transfer/handoff_body_trial.json`을 사용했다. 기본 launch 전체를 dedicated/body-only로 강제 변경하지 않았다.
ROS Jazzy, domain77, CycloneDDS, LOCALHOST; 기존 드라이버 `/home/vic/vicpinky_ws` overlay와 프로젝트 overlay, Zenoh ON. 기존 launch/environment는 `/home/vic/Downloads/handoff_completion_fix/`에 있고 성공 프로세스 재기동 설정은 `/home/vic/Downloads/handoff_input_trace_20261023/reentry_policy_v1/deployment/`에 있다. 환경 전체/인증정보는 Git에 복사하지 않았다. 실제 위치를 확인하지 않고 초기 스테이션 좌표를 재발행하면 안 된다.

## 외부 보관과 원복

보관 루트: `/home/eunbi/vmany_artifacts/handoff-success-20261023-commit-prep` (Git 루트 밖, 새 git init 없음).
- `pc_dirty_before.tar.gz`, `git_diff_before.patch`: 반영 전 미커밋 원본 보존.
- `robot_source_snapshot.tar.gz`, `source_install_equality.json`, `sync_manifest.json`: 로봇 출처/파일별 전후 SHA256.
- `moved_files.json`: 이동한 원본과 보관 위치 매핑.
- `separated/farm_project/runs/handoff_diagnostics/`: 실기 기록, 후보, 시험 코드.
- `separated/farm_project/robot/ros_ws/src/harvest_robot/test/`: 이번 미추적 handoff 시험8개.
- `separated/farm_project/robot/tools/transfer/`: 미추적 진단 도구/사전검사.
- `separated/handoff-backup-0w1frryw`, `separated/interfaces-build-backup-pvMpkS`: Git 상위루트에 노출되던 백업.

기존 문서의 runs 상대 경로 기록은 작성 당시 위치이며, 현재 보관 위치는 위 separated/farm_project 접두어를 사용한다. 원복 시 sync_manifest 대상만 백업과 대조하고 복원한다. 프로젝트 전체를 덮어쓰지 않는다.

## 이번 오프라인 확인

PC 반영본으로 인계64개, 재진입18개, 출력/취소/정지20개 통과. 격리 colcon 빌드 farm_common/farm_navigation/harvest_robot/farm_bringup4패키지 통과. 기존 PC 운영 install은 바꾸지 않았으며 빌드 위치는 `/tmp/handoff-success-pc-build`다.
첫 출력 검사 호출은 잘못된 gate 파일 경로로20개 실행 오류, 최초 재진입 검사 이동본은 fixture BASE 경로 누락으로1개 실패했다. 두 검사 도구 경로만 수정 후 전체 통과; 제품 코드를 시험에 맞춰 바꾸지 않았다. 소스 대조에서 pytest가 생성한 pyc를 잘못 포함한1건은 캐시 제외 후 관련 소스·설정130파일이 로봇 스냅샷과 모두 일치함을 재확인했다.
기존 미추적 시험만 외부 분리했다. 기존 추적 회귀시험/시험용 공통 라이브러리 전체 삭제는 이번 범위가 아니다. 실기 성공 기록을 이번 PC 빌드 결과로 대체하지 않는다.

최종 Git 후보44파일(기존 변경 포함), staged0. 미추적 시험·로그·백업은 후보에 없음. `git diff --check` 통과. VS Code에서 검토·스테이징 후 사용자 직접 커밋한다.
