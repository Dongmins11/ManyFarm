# 수확 인계 후진 곡선 시험 코드 — 2026-10-19

## 승인·기준

사용자: 기존 정상 코드·드라이버를 수정하지 않고 공통 구조에서 반경 10cm 후보를 구현·검증하도록 승인.
원격 기준: feat/harvest-handoff-real-20261018, 6f21119edb2ac3bfa25cb3eb45fad8d6dd03018b.
PC 미커밋 변경은 접근 불가. 이번 패치는 새 파일만 추가하며 기존 파일을 덮어쓰지 않는다.
커밋·푸시·로봇 배포·실제 Goal 전송은 수행하지 않았다.

## 이유와 공통 연결

기존 Spin은 제자리 회전이며 23.1도/26.3도 부근에서 703으로 중단됐다.
기존 StationReverse에는 제자리 정렬이 있으므로 이번 원호 시험에 재사용하지 않는다.
기존 공통 Nav2Client → FollowPath → 새 선택형 ArcController → 기존 velocity_smoother → 기존 드라이버를 사용한다.
ArcController는 기존 RPP의 경로 변환·파라미터·취소 상태·Nav2 footprint 충돌 검사를 재사용한다.
작은 원호의 끝에서도 접선을 유지하는 선행점 계산만 별도 공통 구현한다.
시뮬과 실물이 같은 모듈·플러그인을 사용할 수 있지만 이번 실행 래퍼는 실물 현장 시험용이다.
시뮬/예찰/다른 로봇의 기본 런치·제어기 선택은 바뀌지 않는다.
ActionHandoff나 운영 인계 FSM에는 아직 연결하지 않았다. 팔·배출·접근·복귀 동작은 이번 시험 범위 밖이다.

## 파일

- farm_navigation/transfer_arc.py: 원호 생성, 자세 오차·완료 판정, 새 제어기 프로파일 추가.
- farm_navigation/arc_clearance.py: 실제 발행된 패딩 포함 사각 footprint로 경로 전체 사전 검사.
  lethal/unknown 셀을 검사하고 셀 반대각선 및 샘플 사이 이동량을 여유에서 차감한다.
- farm_arc_controller: 새로운 공통 Nav2 플러그인. 기존 파일/플러그인은 수정하지 않음.
- tools/transfer/arc_trial.py, arc_trial.bash: 현재 설정을 읽어 runs의 시험용 복사본에 새 ID만 추가.
  기존 trial.prepare의 현장 태그/지도 설정과 launch_guard를 재사용한다.
- 새 단위 시험 및 이 변경 문서. 기존 문서는 이번 보존 요청에 따라 직접 덮어쓰지 않는다.

## 제어와 보호

- 기본 반경 0.10m, 후진하며 왼쪽 90도. 중심은 뒤·오른쪽 각각 0.10m 이동한다.
- 기본 목표 선속도 0.01m/s, 제어기 각속도 상한 0.15rad/s.
- 곡선의 기준 위치 오차 0.01m 초과, 반대 방향/초과 회전 시 실패.
- Goal checker 위치 0.005m·방향 0.04rad, 종료 후 위치 0.008m·방향 0.05rad 및 odom 정지 확인.
- 실제 footprint·padding·충돌 검사·local resolution은 변경하지 않는다.
- 실행 중 Nav2의 현재 costmap 충돌 검사 사용. 사전 검사는 실제 실행 검사의 대체가 아니다.
- odom/costmap/footprint 수신 및 시각 신선도 확인. 다른 Action 실행을 감시한다.
- 별도 --execute --exclusive와 같은 출발 자세에서 성공한 PLAN_ONLY 기록이 있어야 실행.
- 계획마다 .used 표식을 남겨 부분 실패 후 같은 계획으로 다시 회전하지 못하게 한다.
- 실행 후 성공/오류/Ctrl+C 모두 자신의 Goal 취소·종결과 실제 정지를 확인한다.
- trial의 Action 감시는 관제와 원자적 작업 예약이 아니다. 시험 중 관제/다른 터미널은 Goal을 보내면 안 된다.
- kill -9/프로세스·전원 장애까지 새 도구가 보장하지 않는다. 기존 드라이버에 명령 만료 검사가 없다는 점은 그대로이며,
  Nav2·smoother를 통하지 않고 cmd_vel을 직접 발행하지 않는다. 실제 실행의 비상 정지는 현장 장치로 확보한다.
- 새 제어기와 경로 설정은 이번 시험 한정이다. 예찰이나 자동 인계에 기본 적용하지 않는다.

## 드라이버 근거

사용자 제공 vicpinky_drive_sources.tar.gz의 bringup.py: WHEEL_BASE=.4288m, WHEEL_RAD=.0825m.
Twist를 좌우 바퀴 RPM으로 계산하고 정수 반올림, 최대 28RPM 비례 제한한다.
zlac_driver.py는 우측 모터 배선 방향을 내부에서 반전한다. 상위 코드에서 추가 반전하지 않는다.
반경 10cm에서는 왼바퀴 후진·오른바퀴 전진. 드라이버는 수정하지 않는다.
고정 v=-.01,w=.1이면 이상적 RPM 반올림 후 반경 .12864m이므로 위치 피드백으로 선행점을 보정한다.

## 실제 수행한 검증

- Python 단위 시험 18개 통과: 원호 좌표/회전 변환/경로 간격/후진 접선/NaN 등 잘못된 입력/
  이탈/역회전/부분완료/각도 wrap/기존 설정 보존/중복 ID/unknown/lethal/셀 경계/지도 범위.
- C++17 g++ -Wall -Wextra -Werror 빌드 및 테스트 통과.
- 정수 RPM을 반영한 이상적인 차동 구동 폐루프: 반경 .10/.15/.20m 모두 종료 조건 도달.
  최대 이탈 각각 .00134629/.00015930/.00396216m.
  모터 지연·마찰·바퀴 미끄러짐·실제 가감속·ROS 지연은 포함하지 않았다.
- 사용자 재시작 후 정지 snapshot 재생: 반경 .10/.15/.20m의 사전 보수 여유 약
  .00139/.01346/.02331m. 이는 패딩 포함 footprint 밖 여유이며 실제 시험 안전 인증이 아니다.
  10cm 후보는 추가 여유가 작다. 최신 실제 사전 검사에서 거절되면 검사나 footprint를 줄이지 않는다.
- Python 문법·bash 문법 검증 통과. 새 파일만 추가하는 패치 적용 검증 수행.

## 미실행 검증과 다음 단계

이 작업 환경에는 /opt/ros와 rclpy/Nav2가 없다. ROS Jazzy 플러그인 빌드·로딩·실제 ROS Action 취소 시험,
Isaac 및 실물 동작 시험은 미실행이다. 오프라인 통과를 실물 검증 완료로 해석하지 않는다.
PC에서 verify_arc_pc.bash로 새 패키지를 격리 빌드한다. 로봇 복사·빌드는 그 결과 후 별도 진행한다.
기존 로그/설정의 성공 기준은 보존한다. 실물은 원래 12번 도착 자세에서 새 계획을 만든다.
현재 26도 돌다 멈춘 자세에서 바로 90도 원호 시험을 실행하지 않는다.

## 현장 실행 순서(PC 빌드와 로봇 배포 후)

1. 기존 런치/브리지 종료, 기존 실제 스테이션 출발 자세 복원.
2. robot/tools/transfer/arc_trial.bash launch (이 런치만 실행).
3. AMCL active 확인 후 기존 /tmp/init_station_newmap.py로 초기 위치 설정.
4. 기존 CycloneDDS·Domain77·LOCALHOST 환경에서 Zenoh 브리지 실행, 관제 표시 확인.
5. 기존 성공한 HarvestTask로 12번 도착, SUCCEEDED 및 실제 정지 확인.
6. arc_trial.bash plan. 자동 이동 없음. 로그의 계획·사전 여유 검토.
7. arc_trial.bash execute --exclusive --reference <6번의 JSON>. 실제 곡선 이동 요청.
8. 결과와 실제 정지 확인. 부분 실패 시 즉시 재요청/자동 복귀하지 않는다.

기존 trial.bash로 실행하면 추가 플러그인을 선택하지 않으므로 기존 정상 동작을 유지한다.
