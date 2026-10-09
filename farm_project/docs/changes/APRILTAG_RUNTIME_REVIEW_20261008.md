# AprilTag·수확 실행 연결 검토 — 2026-10-08

기준: `feat/apriltag-localization`, 원격 `aa18b2cba0d6b632972d233e93ad657311839003`.
승인 근거: 사용자 “다른 사람 코드는 건드리지말고, 확실하게 전부 검토해서 실행 가능한 상태로 만들어와”.
이 보고서의 수정은 미커밋이며 원격 반영하지 않았다. 사용자 PC/로봇에 자동 적용하지 않았다.

## 범위와 보존

원격에서 관련 코드·설정·문서 122개와 지도 PGM을 확보하고 Git blob 바이트와 대조했다.
실행 의존 경로, 보정/미션 수명, 경로 계산·작업 좌표 연결, 실패/취소, 지도·캘리브레이션 해시,
카메라 환경 분리, 패키지 선언과 설치 진입점 연결을 검토했다.
`scout_robot`, 예찰 설정, `farm_navigation` 소스, 다른 작업자의 팔/시뮬 알고리즘은 변경하지 않았다.
`harvest_robot/node.py`는 사용자가 이미 적용한 두 충돌의 결합과 동일하며 양쪽 초기화/정리를 유지한다.
`test_navigator_dispatch.py`는 이 브랜치가 추가한 검사로, 공통 경로 모듈을 지나치게 가짜로 대체하던 부분만 제거했다.
기존 sim CHANGELOG의 병합 충돌 표시는 다른 작업 기록이므로 자동 해소하지 않았다.

## 확인한 실패와 수정

| 실패 | 근거 | 수정 |
|---|---|---|
| harvest_node import 불가 | 사용자 SyntaxError와 원격의 충돌 2곳 | 정책 검증·태그 초기화·route/work/arm 정리를 모두 유지해 병합 |
| route_server 생성 불가 | 사용자 `operations: No parameter value set`, YAML 빈 배열 | `operations: []` 제거, Nav2 기본 등록 사용 |
| 미션 preflight 거절 | 공통 `validate_goal_checkers`는 Nav2 기준이 미션 기준보다 엄격해야 함. 원본은 둘 다 5cm/3도 | 실물 Vic Pinky Nav2만 4cm/2.5도, 미션 최종 기준 유지 |
| 종료 실패가 성공으로 표시 | capture_session finally의 자식 종료 코드가 반환값에 반영되지 않음 | 실패 반환 및 session.json clean_shutdown/shutdown_errors 기록 |
| 실행 전 검사가 이 문제를 놓침 | 기존 검사는 실물 설정 비교에서 >=만 검사, 문법·실제 종료 흐름 누락 | 실제 공통 도착 검사 재사용, 충돌/빈 배열/실제 프로세스 종료 회귀 검사 및 check_runtime 추가 |

Nav2 Jazzy upstream에서 `operations` 기본값은 AdjustSpeedLimit/ReroutingService다.
이 클라이언트는 ComputeRoute만 사용하며 ComputeAndTrackRoute를 호출하지 않는다.
기본 플러그인 등록과 실제 tracking operation 실행은 구분한다.
참고: https://api.nav2.org/nav2-jazzy/html/operations__manager_8cpp_source.html,
https://api.nav2.org/nav2-jazzy/html/route__server_8cpp_source.html.
설치된 로봇 바이너리의 실제 기동은 별도 재검증이 필요하다.

4cm/2.5도는 공통 코드의 엄격 검사에 맞추기 위한 명시적 여유이며 물리 성능 보증값이 아니다.
속도·충돌 검사·진행 판정·최종 미션 허용치·좌표·그래프·태그 보정 수식은 변경하지 않았다.

## 이번 환경에서 직접 실행한 검증

- 태그 패키지 unittest 42개 PASS, 수확 연결 unittest 30개 PASS: 총 72개.
- 충돌 표시, 빈 operations, 기존 동일 허용치의 실패 재현.
- 실제 독립 자식 프로세스에 SIGINT를 전송해 자식 종료 0/1의 상위 반환값과 JSON 기록 확인.
  ROS 검출기 충돌 재현 시험은 아니다.
- 오프라인 check_runtime PASS: 실행 소스 Python 35개 구문, 지도/모델/캘리브레이션,
  실물 화단 설정, controller/goal/progress checker 선택, 실제 공통 도착 검사, Route Server YAML, 카메라 plan.
- 원본 지도 PGM SHA256 `a9f852637490aaff50c7115a543e2780a60ecf654747b3e777319251e151949e` 확인.
- 카메라 드라이버·trial_io 원본 해시, ROI·시간 보상·보정량 보존 검사 PASS.
- `git diff --check` PASS.
- 이 환경에는 ROS가 없다. `--ros`는 설치 모듈 부재로 FAIL하는 것을 확인했고 이를 PASS로 처리하지 않았다.
  colcon/ROS launch/DDS/실물 이동/보정 성능/설치 C++ 종료는 이번에 실행하지 않았다.

## 적용·현장 확인

수정 묶음의 apply_review.py는 정확한 기준 파일 또는 이미 수정된 동일 파일만 허용한다.
먼저 모든 파일을 확인한 뒤 백업하고 적용한다. 다른 변경과 다르면 쓰기 전에 중단한다.
Git 작업 트리 전체 reset/clean/stash, commit/push는 수행하지 않는다.

1. PC에 적용 후 72개 검사와 오프라인 사전 검사를 실행한다.
2. 로봇 관련 실행을 종료한 상태에서 변경 파일만 동기화한다. 다른 폴더 삭제/전체 덮어쓰기는 하지 않는다.
3. robot overlay에서 `harvest_robot`, `farm_tag_localization`을 재빌드하고 source한다.
4. 프로젝트 루트에서 `python3 robot/tools/tag_camera/check_runtime.py --ros`를 실행한다.
5. RViz를 준비하고 기존 launch 후 실제 초기 위치를 설정한다. AMCL/controller/planner/BT/route가 active인지 확인한다.
6. 기존 승인된 HarvestTask 시험에서 도착·취소·보정 ON/OFF를 확인한다. 임의 목표를 자동 전송하지 않는다.

현재 발생한 planner inactive는 초기 TF 대기 60초 만료로 설명된다. 늦은 초기 pose 수신만으로
실패한 lifecycle 전체가 재시작된다고 가정하지 않는다. 기존 launch 재시작과 초기 위치 설정 순서를 사용한다.
실제 로봇 위치를 확인하지 않고 기본 좌표를 주입하거나 시작 거리 제한을 완화하지 않는다.

## 남은 문제와 되돌림

- detector/rectify SIGINT 후 -11: 원인 미확인. 해당 외부 패키지는 수정하지 않았다.
  이번 변경은 실패 보고 누락만 고친다. 기존 capture.log/process_exits.json을 유지한다.
- 실제 새 Git 통합 좌표 이동과 태그 효과는 미검증이며, 실행 준비 검사 PASS와 구분한다.
- 여러 체크아웃에서 보정을 동시에 실행하지 않는다. 현재 잠금은 프로젝트별이다.
- 복원은 apply_review가 출력한 백업에서 이번 변경 파일만 대상으로 한다.
  이미 다른 수정이 추가된 파일은 먼저 비교한다. 불완전한 원격 충돌본으로 node.py를 되돌리지 않는다.


## ComputeRoute 설치 메시지 호환 — 2026-10-08 후속

- 사용자 로봇에서 두 패키지 빌드 성공. 설치 사전 검사에서 ComputeRoute.Result에 error_msg가 없는 것을 확인했다. 실제 필드는 planning_time/path/route/error_code이고 Feedback은 비어 있다.
- route_server.py는 status와 error_code로 실패를 판정·보고하며 error_msg는 존재할 때만 추가한다. 성공 경로 처리와 오류 거절은 유지한다. 검사도 필수 필드를 path/error_code로 맞췄다.
- 이전 가짜 응답에만 있던 error_msg를 제거하고 실제 필드 형식으로 검사했다. 태그42개·수확31개 오프라인 검사 PASS. 실물 재기동·ComputeRoute 호출은 아직 미검증이다.
- 예찰·공통 farm_navigation·팔 코드 변경 없음. 이번 파일만 백업에서 복원 가능. 미커밋·푸시 없음.
