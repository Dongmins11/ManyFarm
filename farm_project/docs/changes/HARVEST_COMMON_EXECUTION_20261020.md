# 곡선·벽 시험 공통 실행 변경


## 2026-10-20 곡선·벽 시험 공통 실행 정리 (사용자 구현 승인)

- 기준 HEAD: `6f21119edb2ac3bfa25cb3eb45fad8d6dd03018b` + 사용자가 보존한 `harvest_wall_fixed_020_DCbtgs` 미커밋 파일.
- 사용자 실물 성공 기준: 벽 `1792501145755309910/result.json`, 곡선 `1792501043548632613/1792501048277488101_arc.json`. 벽 최대 전진 0.02m/s, 각도 허용 0.5도, 각도 보정 0.04276056667386108rad, 펄스 없음.
- RoutePlan의 선택형 headings와 기존 build_path를 이용해 곡선/벽 점·차체 방향을 그대로 전달한다. 기존 XY 경로 보간·후진 처리 기본값은 유지한다.
- 기존 Navigator에 explicit_routes, stop_output, settling_check, arrival_validator를 명시적으로 선택한다. 실행 → 출력 차단 → 기존 MotionMonitor 정지 → 호출자 최종 판정으로 연결한다. 기본 주행의 오차 기록 정책은 유지한다.
- Nav2Client/arrival의 기존 preflight에 WallGoalChecker 명시적 검사를 추가한다. 실제 파라미터 원본 이름은 wall_alignment.*이며 wall_goal.*로 잘못 읽지 않는다.
- 기존 trial 두 곳에서 직접 Path 작성/Action 실행을 제거하고 공통 Navigator를 호출한다. 관측·충돌·속도 제한·독립 서버·reference 사용 방지는 유지한다. arc 종료도 기존 wall_shutdown의 실행기 종료 순서를 재사용한다.
- 실물 시험 설정 두 JSON은 robot/config/robots/vicpinky/transfer 단일 원본으로 이동한다. 모든 값은 기존 성공본과 동일하다. 설치/소스 혼합 append를 해당 시험 진입점에서 제거했으므로 로봇 적용 시 farm_navigation 재빌드가 필수다. 이번 PC 스크립트는 Downloads에 독립 설치만 만든다.
- 수확 test_follow_work의 AST 시험 환경에 누락된 configured_arm_settings·HarvestLoad 두 이름을 실제 구현으로 연결한다. 운영 HarvestNode 변경 없음. 수정 전 원본도 같은 15개 NameError가 발생함을 확인했다.
- 공통 변경은 승인한 시험 연결 범위다. 기존 FSM·관제·팔·인계·복귀 연결과 운영 활성화는 하지 않는다. C++ 제어기·arc_clearance·기존 Nav2·드라이버·태그 설정은 변경하지 않는다.
- 검증: 변경 전/후 해시, Python 회귀 162개, 기존 C++ 곡선 검사 및 벽 861 assertions(이상 모델). 실제 ROS가 없는 작성 환경이므로 ROS 액션/설치/실물 회귀를 완료했다고 표시하지 않는다. 전달 run_pc.bash에 실제 ROS 격리 계약 검사를 포함했다.
- 되돌리기: Downloads/harvest_before_common_*/before.tar.gz와 manifest.json의 before 목록 사용. 새 설정 경로를 삭제하고 옛 tools 설정 파일을 함께 복원한 뒤, 이미 설치했다면 farm_navigation도 다시 빌드한다. 다른 사용자 변경을 통째로 되돌리지 않는다.
- commit/push/로봇 배포/실물 실행 없음. 다음 작업은 PC ROS 검사 결과 확인 후 로봇의 동일 설치본·무이동 plan 검증이다.


## 2026-10-21 PC ROS preflight 수정

사용자 PC의 독립 설치·실제 ROS 타입 검사까지 통과했으나, WallGoalChecker에 일반 checker의 미선언 xy_goal_tolerance 등을 함께 요청하여 실제 ROS 계약 검사가 실패했다. 오프라인 대역이 누락 항목을 None으로 돌려주는 방식이어서 이를 놓쳤다. plugin 종류를 먼저 읽고 Simple/Stopped의 기존 키 또는 wall_alignment.*만 조회하도록 수정했다. 필수 벽 키가 없는 경우의 실패는 유지한다. 테스트 대역에 미선언 항목 전체 실패를 반영하여 수정 전 오류를 재현하고 수정 후 공통 주행/명시적 경로 26개를 통과했다. 일반 Simple/Stopped 검사와 허용오차 초과 거절도 확인했다. PC 실제 ROS 재검사는 전달 스크립트에서 수행하며 이 수정본의 실물 검증은 미완료다. 제어기·주행 수치·FSM 변경 없음. 원본/로그/독립 빌드 경로는 Downloads 하위다.
