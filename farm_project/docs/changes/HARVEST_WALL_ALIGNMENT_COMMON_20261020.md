# 공통 벽 접근·정렬 제어기 — 2026-10-20

## 승인·기준

사용자 승인: 별도 공통 제어기 구현, 기존 공통 구조·개발 원칙 준수, 검증되지 않은 내용을 완료로 설명하지 않는다.
대상은 벽 접근·정렬 및 독립 시험 연결이다. 인계 FSM/Jetson/복원/기본 주행 연결은 이번 범위 밖이다.
원격 작업 브랜치 feat/harvest-handoff-real-20261018은 6f21119edb2ac3bfa25cb3eb45fad8d6dd03018b와 동일함을 API 비교로 확인했다.
통합 브랜치는 fb5c61a 기준이며 작업 브랜치보다 3커밋 뒤다. main은 공통 조상2a397da 이후 서로 다른 변경이 있어 자동 병합하지 않는다.
사용자 PC의 기존 미커밋 곡선/벽 수집/감시 변경을 보존한다. 원격 Git 조회와 PC 파일의 현재 상태를 동일시하지 않는다.
AGENTS, CODEX_HANDOFF, PROJECT_STATE, DECISIONS, HARVEST_COMMON_REAL_INTEGRATION_20261018을 검토했다.

## 확정 목표와 측정 근거

- 곡선 직후 원본: harvest_arc_wall_20261020.tar.gz, wall_reference/20261020_113848_30283. 중심 거리0.5247769m, 벽 법선각1.474706도 (전방±30도,82프레임).
- 목표 수동 배치: harvest_wall_target_20261020.tar.gz, wall_reference/20261020_114657_32626. 중심 거리0.4325130m, 법선각3.778490도 (82프레임).
- 사용자는 수동 배치의 각도까지 복제하지 않고 벽 정면을 바라보도록 승인했다. 목표 중심 거리0.4325m/각도0rad.
- 실제 외곽60x50cm에서 정면 자세의 앞쪽 간격 계산값0.1325m. 절대 측위 정확도나 안전거리 인증이 아니다.
- 벽 직선은 벽을 따라 이동한 좌표를 결정하지 못한다. 목표 위치를 현재 추정값으로 덮어쓰지 않는다.

## 코드 소유권·변경 파일

- 새 farm_wall_controller: wall_control.hpp 순수 P 제어, wall_input.hpp 관측 계약, wall_plugins.cpp Nav2 Controller/GoalChecker.
- 새 farm_navigation/wall_observation.py: 기존 wall_reference.scan_points/fit_wall 호출, 고정 프레임의 벽 직선 연속성 확인. 벽 검출 알고리즘 복제 없음.
- 새 farm_navigation/wall_observer_node.py: 기존 PoseProvider로 scan 시각 TF 조회, 관측 PoseStamped 발행. Goal/속도 발행 없음.
- 새 farm_navigation/wall_trial_support.py: 독립 서버 설정 투영과 벽 시험 속도 범위. 기존 곡선 CommandGate는 후진·왼쪽 제한이므로 수정하지 않는다.
- 새 farm_navigation/wall_trial_runtime.py: 독립 서버·관측기 시험 실행. 기존 Nav2Client.execute/cancel, MotionMonitor, MeasuredVelocityGuard 재사용.
- 새 robot/tools/transfer/wall_alignment_trial.bash/json: 실물 연결과 이번 목표/시험 후보값. 운영 harvest_real.json에 자동 반영하지 않는다.
- C++/Python 관련 시험 추가. 기존 Nav2 override/지도/태그/일반 주행/arc 파일은 변경하지 않는다.
- sim 전용 구현을 만들지 않는다. 시뮬은 동일 코드에 해당 환경의 목표/센서/TF/use_sim_time을 공급한다. 제공 실물 목표를 sim에 자동 적용하지 않는다.

## 동작 및 ROS 계약

wall_observation은 시험 사설 namespace의 geometry_msgs/PoseStamped다. header.stamp는 원본 scan 시각, frame_id는 고정 odom이다.
position은 측정 벽 직선상의 한 점, orientation의 yaw는 로봇에서 벽을 향하는 단위 법선 방향이다. 차체 목표 Pose가 아니다.
Controller는 현재 odom 자세와 고정 벽 직선을 비교하므로 scan 이후 차체 움직임을 무시한 base 오차를 반복 사용하지 않는다.
새 wall_goal은 경로 끝점 도착이 아니라 벽 거리/각도/정지속도/유지시간으로 판정한다. 일반 GoalChecker로 교체하면 Controller가 거절한다.
기존 Nav2Client.preflight는 경로 끝점 의미이므로 전역 판정을 변경하지 않는다. 시험 어댑터가 전용 plugin ID와 적용 파라미터를 확인한 뒤 공통 execute/cancel만 사용한다.
FollowPath의 경로는 요청의 운반 형식이다. wall 제어기만 선택하며 다른 controller ID로 재사용하지 않는다.

RPP를 상속해 기존 Nav2 parameter/costmap/lifecycle 및 collision_checker를 사용하지만 속도 계산은 새 P 제어다.
footprint 충돌 검사는 isCollisionImminent로 매 명령 수행하고 carrot 거리로 검사범위를 잘라내지 않는다.
본체 cmd_vel에 직접 발행하지 않는다. private raw_cmd_vel → 명시 실행 gate → 기존 cmd_vel_nav/smoother를 사용한다.
동시 Action 감시와 explicit exclusive 및 곡선 시험과 같은 로컬 파일 lock을 사용한다. 이것은 임의 외부 cmd_vel 발행자를 통제하는 시스템 전체 중재기가 아니다. 운영 FSM 연결에는 기존 ActionHandoff 소유권 연결이 별도 필요하다.

## 시험 후보값 — 실물 검증값 아님

- 거리±0.005m, 각도±1도, P거리0.4/s, P각도0.8/s, v상한0.01m/s, w상한0.05rad/s.
- 정렬 우선 진입4도/해제2도, 초기 각도 및 회전 변화15도 제한, 이동0.20m/실행40초 제한.
- 벽 관측 최대0.3초, 같은 벽의 고정 좌표 변화0.015m/3도 제한. 안정5프레임 후 발행.
- 목표 오차/정지속도 조건0.5초 유지 뒤 Nav2 성공. 이후 기존 MotionMonitor로 다시0.8초 정지 확인한다.
- 측정속도 감시: 선속도절댓값0.025m/s, 각속도0.10rad/s 초과0.1초 또는0.15rad/s 초과 즉시 차단. 명령 한계와 구분한다.
- I/D 미사용. P가 구동 최소속도에 막혀 잔여 오차를 남기는지 실물에서 확인해야 한다. 허용치를 넓혀 성공 처리하지 않는다.
- 목표보다5mm 이상 가까우면 정지/실패. 자동 후진/새 벽 선택/자동 재시도 없음.

## 검증 상태

직접 실행 완료:
- g++ C++17 -Wall -Wextra -Werror: 순수 제어 계산33개 assertion 통과. 이상적 차동구동 모델에서 초기각±0.12/±0.025/0rad 다섯 조건 목표 수렴 포함.
- Python unittest14개 통과: 벽 기하·좌표변환·시각/후보 불연속·설정 원본 보존·전진/양방향 명령 gate.
- 실제 기록164프레임을 새 관측 추적기로 재생: 두 수집 각82프레임 모두 통과. 이는 기록 재생이며 실시간 센서 처리 성공이 아니다.
- Python/Bash 구문, XML 등록, payload 적용·기존 파일 보존 검사.

미실행:
- 이 작성 환경에는 /opt/ros가 없다. Nav2 플러그인 실제 colcon 빌드/로딩, ROS action 동작·취소·충돌 차단, Isaac, 실물 전진/정렬은 검증하지 않았다.
- verify_pc.bash가 독립 install 경로에 새 패키지만 빌드하고 configure/inactive 검사한다. 차체 Goal/이동을 보내지 않는다.
- PC configure 성공도 실제 collision 회피나 wall 도착 성공으로 확대하지 않는다. 로봇 배포/실행 명령은 이 패키지 적용 절차에 포함하지 않는다.

## 복원 설계 보존 (미구현)

인계 전 윈도우ID/목표좌표와 실제 곡선 출발위치·방향을 저장한다. 복원시 저장한 방향벡터와 현재 방향의 내적+2D외적으로 부호 있는 각도를 비교한다.
윈도우 좌표는 복귀 목표이며 현재 위치추정의 대체값이 아니다. 벽에서 후진 후 전진곡선 복원과 그래프 재진입은 별도 구현·검증한다.

## 적용·되돌림

PC apply_pc.py는 기존 파일을 덮어쓰지 않고 새 파일 존재·기존 공통 의존성 해시를 검사한다. 문서3개는 백업 후 항목만 추가한다.
자동 commit/push/merge/deploy 없음. 커밋은 사용자 VS Code에서 진행한다.
되돌릴 때 새 wall 파일만 제거하고 문서 추가항목을 되돌린다. 기존 곡선/일반 주행은 이 변경으로 수정되지 않는다.


## 벽 정렬 PC ROS 빌드·로딩 확인 — 2026-10-20

- 사용자 실행 출력 확인: farm_wall_controller colcon build 성공, CTest 1개 실패0, WallController/WallGoalChecker configure 후 inactive 확인.
- PC 빌드: /home/eunbi/harvest_wall_pc_9xD536, 로딩 로그: /home/eunbi/harvest_wall_load_9quz5wa6/controller.log.
- Python14개·C++33 assertion 통과. Action Goal·차체 이동은 없었다.
- 아직 ROS 접근 완료/취소/충돌 차단 및 실물 벽 접근은 미검증. 로봇 배포 결과는 다음 출력으로 구분한다.
