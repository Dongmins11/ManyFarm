# 수확 인계 브랜치 + 실물 운송 통합 워크스페이스

## 기준과 범위

- 기준: `feat/harvest-handoff-real-20261018`, commit `48d2d1c812a968058254ddb2355ee5dfc9b96c68` (최초 통합 기준 5ff5b50에서 업데이트).
- 운송 원본: `transport_robot_snapshot_20261027/robot_home`의 실제 운용 소스 복사본.
- 별도 폴더에서 통합했다. 원본 PC/로봇을 수정하거나 로봇에 배포하지 않았다. Git 원격 push/merge도 하지 않았다.
- 수확·예찰·farm_navigation·지도·공유 모델·sim은 기준 브랜치와 내용이 같다. sim은 수정·빌드·실행하지 않았다.
- 공통 인터페이스에는 운송 정의를 추가했다. 기존 정의는 유지했다.

## 구성과 소유권

| 경로 | 역할 |
|---|---|
| farm_project/robot/ros_ws/src/transport_robot | 운송 FSM·관제 이벤트·접근 전환·운송 도착 정책 |
| farm_project/robot/ros_ws/src/farm_docking | 기존 마커·라이다·정밀 접근·제어권 + 초기 마커 미확보 정책 |
| farm_project/robot/ros_ws/src/transport_device_bridge | 기존 UART 기구 완료 응답 연결 |
| farm_project/robot/ros_ws/src/farm_bringup | transport 전용 launch 추가, 수확/예찰 launch 보존 |
| farm_project/robot/config | 운송 설정 추가, 브랜치 지도 유지 |
| hardware_ws/src | 로봇에서 복사한 드라이버·롤백 모델 소스. 별도 하드웨어 underlay용 |
| dev_tools/legacy_waffle_commands | 기존 시험 명령 보관용. 옛 절대경로를 사용하므로 그대로 실행하지 않는다 |
| tests | 새 연결·정책 및 현재 도킹 후 준비 대기 순서 검증 |
| reports | 빌드·시험 로그, 보존/변경 목록 |

`TransportNavigator`는 운송의 기존 엄격한 도착 판단과 취소/정지 절차를 보존한다. 경로·Nav2 액션·위치·정지 감시는 브랜치의 farm_navigation을 재사용한다. 공통 Navigator를 운송 것으로 교체하지 않았다. 기존 SorterApproach/HarvestApproach와 ExclusiveNavigator가 관측→Nav2 취소→정지→정밀주행 전환을 맡는다. 관측 콜백이 직접 속도를 발행하지 않는다.

운송 Nav2는 전용 transport_navigation.launch.py를 통해 smoother 출력을 motion/nav로 연결한다. motion_gate만 차체 cmd_vel을 발행한다. tf_recovery_enabled=false, collision_retry_count=0을 운송 설정에서 명시해 기존 정책을 유지한다. 다른 로봇 설정은 변경하지 않았다.

## 지도·티칭 주의점

선택한 수확 **브랜치**는 운송과 PGM/YAML이 같고 그래프 노드가 다르다. 앞선 분석의 origin/main 지도와 구별해야 한다.

| 노드 | 운송 이전 | 이번 브랜치 기준 |
|---|---|---|
| 3 | (1.446,-0.720) | (1.446,-0.720) |
| 15 | (2.181,-1.333) | (2.341,-1.383) |
| 17 | (2.981,-1.333) | (2.981,-1.383) |
| 20 | (1.446,-1.120) | (1.446,-0.920) |

선별장 접근 방향은 15→17에서 계산한다. 이격 기준 map yaw는 사용자 확정대로 0rad(0°)를 유지한다. 스테이션 방향은 기존처럼 그래프에서 계산한다. 5↔12는 운송 인메모리 그래프에서만 차단하며 원본 GeoJSON은 변경하지 않는다.

마커 상대 티칭·카메라 외부 보정·속도·PID·와플 footprint는 보존했다. 따라서 티칭 물리 위치가 새 그래프 노드와 일치한다고 보증하지 않는다. 특히 20번의 20cm 차이와 17번의 5cm 차이는 실물 시험에서 확인해야 한다. 이전 init 별칭의 하드코딩 좌표는 그대로 사용하지 않는다.

## 유지한 업무 흐름

- 스테이션: 3번 진입 → 마커32/티칭 접근 → 20→3 방향 회전 완료 → 다음 미션은 추가 CLEAR 없이 출발.
- 선별장: 15→17 접근 관측 → 마커40 거리 도킹(0.17m) → UNLOAD_READY 대기 → OpenCR DONE → 이격/17→15 정렬 → 대기.
- 수확: 이동 중42 확보 → Nav2 취소/정지 →42 정밀 접근 → DOCK_READY 대기(300s) →41 확인/현재 odom 방향 유지 → 라이다 대상 면 추적(0.20m) → 수령/이격.
- 기존 관제 이벤트 중계·작업 ID·복구 정책을 유지한다. 로봇 간 직접 이벤트 중계를 새로 추가하지 않았다.
- 이름에 trial이 남은 선별장 프로파일도 현재 운영 흐름에서 참조한다. 삭제하지 않는다.

## 승인된 초기 마커 미확보 처리

harvest_approach_42, sort_01_distance_trial만 opt-in이다. 기본값은 정지 재관측 3초 → 0.02m/s로 0.05m 후진 → 원방향 기준 좌15°/우15°/원위치 탐색, 전체30초 제한이다. ID가 보이는 것만으로 완료하지 않고, 실측 정지와 기존 목표/방향 확보가 모두 확인되어야 정밀 접근으로 넘긴다. ID만 보이고 목표 조건을 만족하지 못하면 제한된 탐색을 이어간다. 목표 확보 이후에는 이 정책을 재실행하지 않는다. 최종41 라이다·기존 주행 중 가림/odom 연속 접근 정책은 유지한다.

새 기본값은 오프라인 검증값이며 실측 확정값이 아니다. 기존 센서 최신성·제어권·footprint 검사는 후진/탐색에도 적용된다. 취소·장애물·센서 오류는 기존 실패/복구 흐름으로 전달한다.

## PC 빌드와 단위시험

새 터미널에서 이 README가 있는 폴더로 이동한 뒤:

```bash
bash scripts/build.sh
bash scripts/test.sh
```

ROS Jazzy와 프로젝트 의존성이 설치되어 있어야 한다. 현재 한글 포함 프로젝트 경로에서 ROS IDL 생성 경로 해석이 실패하여 build.sh가 소스를 `/tmp/transport_handoff_build_20261027/src`로 동기화한 뒤 빌드한다. 원본 프로젝트와 sim은 수정하지 않는다. build/install 결과는 해당 /tmp 폴더에 있고, 삭제되거나 재부팅으로 사라지면 재빌드한다. `TRANSPORT_INTEGRATION_BUILD_ROOT`로 ASCII로 구성된 공백 없는 별도 경로를 지정할 수 있다. 소스 수정 후 build.sh를 다시 실행해야 빌드 복사본에 반영된다.

## 이후 실물에서 실행할 명령 — 이번에는 실행하지 않음

실물 장치·카메라 환경을 준비하고 별도 하드웨어 underlay를 빌드한 로봇에서:

```bash
# 필요한 경우: export TRANSPORT_HARDWARE_SETUP=/실제/하드웨어/install/setup.bash
source scripts/env.bash
ros2 launch farm_bringup transport.launch.py \
  project_root:="$TRANSPORT_PROJECT_ROOT" \
  environment_config:=robot/config/environments/transport_docking_trial.yaml \
  mode:=real
```

기존 명령 셸의 PYTHONPATH/AMENT_PREFIX_PATH가 섞이지 않도록 새 터미널을 사용한다. env.bash는 이전 transport_protocol/transport_docking overlay를 자동 source하지 않는다. DOMAIN77/CycloneDDS/LOCALHOST는 운송 기존 설정을 유지한다. 외부 관제는 해당 환경의 Zenoh 연결이 필요하다.

하드웨어 underlay는 hardware_ws에서 별도로 빌드한다. 부모 통합 탐색 제외용 COLCON_IGNORE가 있으므로 `colcon build --base-paths src`로 명시한다. 본 작업에서 하드웨어 드라이버는 재빌드/실행하지 않았다. 현재 모델 소스만 보존했다.

카메라 Picamera2 가상환경·libcamera 및 ~/.ros/camera_info 보정 파일, 장치 접근 권한, OpenCR 펌웨어는 이 소스 통합만으로 설치되지 않는다. 센서 설정의 경로를 대상 로봇에 맞춰 확인한다. 이 워크스페이스는 시스템 이미지가 아니다.

## 검증 결과 및 한계

- 로봇 워크스페이스 17패키지 빌드 통과(시뮬레이션 제외).
- 단위시험 98개: 기존 71개 + 실제 메서드 회귀시험27개. 최신 빌드/시험 로그: reports/build_late_goal_fix.log, reports/test_late_goal_fix.log.
- 인터페이스 및 주요 런타임 클래스 import 통과. ROS 노드를 생성하지 않았다.
- transport launch --show-args 통과. 실제 브링업/센서/모터는 실행하지 않았다.
- source_audit.json: 수확·예찰·공통 주행·지도·모델·sim 보존 확인.
- 로봇 배포, 실물 주행, 관제 E2E, 하드웨어 underlay 빌드, 시뮬레이션 검증은 하지 않았다.
- 마지막 마커 기반 라이다 면 선택 및 새 초기 재탐색의 실물 성공은 사용자 시험이 필요하다.

## 2026-10-27 리뷰 수정

초기 목표 확보, 종료 예외, 취소 결과 보존, 거리 도킹 복구, 정밀주행 검사 책임, 관측 만료 전달과 설정 단일화를 수정했다. 초기 재탐색 설정 원본은 robot/config/docking/waffle_profiles.yaml이다. 환경 YAML의 중복 정의는 제거했다.

[수정 근거·재검토 결과·남은 문제](farm_project/docs/changes/TRANSPORT_REVIEW_FIXES_20261027.md)를 확인한다. 기존 실물 성공과 이번 PC 시험을 동일하게 간주하지 않는다. 로봇 배포 및 실기 검증은 하지 않았다.

접수 응답 5초 초과 시에도 정밀주행 접수 Future를 보존한다. 늦게 accepted가 오면 즉시 취소를 요청하고 terminal/stopped 결과까지 추적한다. 확인 전 새 정밀주행 및 수동 복구 통과를 막는다. 거절은 pending을 해제하며, 종료 확인만으로 다음 업무를 자동 실행하지 않는다. 사용자 확인에 따라 기존 마커 상대 티칭값은 유지한다.

## 로봇 별도 배포 — 2026-10-27

배포 경로: `/home/wmany/transport_handoff_integration_20261027`. 실물 소스만 전송하고 `farm_project/sim`은 제외한다. 빌드 경로는 재부팅에도 남는 `robot_build`다. 기존 운영 소스·별칭은 변경하지 않는다. 기존 turtlebot3_ws/device_ws 하드웨어 underlay를 사용하되 운송/정밀주행/기구 브릿지 실행 코드는 새 통합 overlay를 사용한다.

로봇 터미널에서 기존 브링업이 종료된 상태로:

```bash
bash ~/transport_handoff_integration_20261027/scripts/bringup_robot.sh
```

다른 로봇 명령 터미널의 통합본 환경은 다음으로 불러온다(자동 기동 없음).

```bash
source ~/transport_handoff_integration_20261027/scripts/robot_env.bash
```

기존 `bringup` 별칭은 새 통합본으로 바꾸지 않았다. 위 스크립트를 명시적으로 사용한다. 이번 배포 검증의 로그는 reports/robot_build.log, reports/robot_test.log, reports/robot_verify.log를 확인한다. 배포 검증과 실물 주행 성공은 구별한다.

배포 검증 완료: 로봇 ARM 17패키지 빌드, 로봇 시험90개, 소스501개/빌드소스376개 해시 일치 및 새 모듈 경로 확인. PC 전체94개 중 시뮬레이션 fixture를 참조하는 시험 묶음4개는 로봇에서 제외한다(`scripts/test_robot.sh`). 브링업/주행은 실행하지 않았다.

## 최신 수확 업데이트 통합 및 브랜치 게시

48d2d1c의 수확 코드2개·설정2개를 함께 반영했다. 정지 후 복귀 완료5cm·6도, 이동 중 방향 제한은 기존 범위를 유지한다. 운송 티칭·속도·후진0°는 유지했다. 최신 검증은 PC17패키지/98시험, 로봇 변경패키지 재빌드/94시험, 소스501개·빌드소스376개 해시 일치다. 로봇 PC전용 sim fixture 시험4개 제외는 동일하다. 최신 로그는 로컬 reports/*upstream*.log에 있으며 Git에는 올리지 않는다.

게시 브랜치는 `feature_dongmin`이며 최신 수확 커밋의 이력을 유지한다. main 및 기존 수확 브랜치는 변경하지 않는다. scripts는 빌드/실행/회귀시험 도구, tests는 회귀시험, dev_tools는 과거 시험 명령 보관용으로 운영에 자동 연결되지 않는다. hardware_ws는 재현용 하드웨어 소스와 라이선스를 포함하며 중첩 .git 이력은 제외한다. build/install/log, reports, 백업 및 런타임 데이터는 게시하지 않는다.
