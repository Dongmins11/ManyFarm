# 기존 주행 서버를 유지하는 곡선 시험 — 2026-10-19

## 승인 및 근거

사용자 승인: 기존 주행을 건드리지 않고 곡선 시험을 연결하고 검증한다. 첫 시험 반경 0.10m, 후진하면서 왼쪽 90도 회전이다. 운영 인계 미션에 자동 연결하지 않는다.

확인한 작업 브랜치 원격 HEAD: 6f21119edb2ac3bfa25cb3eb45fad8d6dd03018b. PC의 곡선 시험 코드는 미커밋 전달본이며 로봇은 Git 없이 선택 복사한다. main 후속 HEAD e735dc9 및 통합 fb5c61a를 확인했으나 이번 시험에 병합하지 않았다.

기존 런치의 baseline_bea8f332420945cfa11ec055cc36af9b는 12번 도착 성공. 진입 56.3초, 작업 이동 21.7초, 최종 위치 오차 0.0244m. 곡선 플러그인을 기존 controller_server에 추가한 런치는 진입 중 collision ahead/106으로 실패했다. 두 실행의 수집된 기존 controller/smoother 명시값은 같지만 실패 원인은 확정하지 않았다. baseline의 local costmap 파라미터 수집은 빈 값이므로 전체 실행 설정 동일성 증거로 쓰지 않는다.

## 변경 파일과 구조

- `farm_navigation/arc_isolation.py` 추가: 실제 실행 중 costmap 설정을 보존해 별도 namespace의 곡선 서버 설정 생성. 기존 ArcController/trial_profile 재사용. 명령 제한 및 시간 초과 gate.
- `tools/transfer/arc_isolated.py`, `.bash` 추가: 기존 서버의 ListParameters/GetParameters로 현재 값을 조회. 실제 LaserScan 구독 주소 사용. 독립 controller_server를 configure/선택 activate하고 종료 시 해당 프로세스만 정리한다. 원본 파일 및 기존 노드에는 파라미터 변경·lifecycle 요청을 보내지 않는다.
- `tools/transfer/arc_trial.py`: 선택적 독립 액션·파라미터·costmap 주소 연결. 일반 모드 인터페이스 유지. 상태 구독은 transient local로 기존 진행 중 Goal도 받는다.
- `test/test_arc_isolation.py`: 입력 불변·센서 주소·형상 보존·YAML 왕복·명령 범위·다른 동작·명령 끊김 검증.

독립 server는 `/harvest_01/arc_trial_<임의8자리>/raw_cmd_vel`에만 출력한다. 기존 controller_server 플러그인 목록과 BT는 유지한다. `check`는 configure만 하고 종료한다. `plan`은 독립 costmap을 활성화해 최신 장애물/footprint로 경로를 검사하지만 FollowPath Goal과 실제 속도를 보내지 않는다.

`execute --exclusive --reference PLAN.json`은 기존 작업/복귀/주행/인계 액션이 유휴인 상태를 전제로 한다. 새 서버의 FollowPath를 공통 Nav2Client로 요청하며 검사된 명령만 기존 `/harvest_01/cmd_vel_nav`로 전달한다. 기존 smoother/드라이버는 그대로 사용한다. 후진 외 명령·범위 초과·기존 액션 활성·odom/costmap 지연·속도 입력 0.3초 끊김 시 차단하고 0을 보낸다. 수신 시작 전 5초 응답 제한. 정상/실패 종료 모두 gate를 닫고 자기 Goal만 취소한다. 원래 서버를 취소·정지시키는 코드는 없다.

기존 controller·local costmap·smoother 전체 파라미터를 전후 비교하고 기록한다. plan과 execute 사이 설정 hash 및 출발 odom 자세(5mm/0.02rad)도 비교한다. 임시 서버는 종료되므로 일반 주행 전에 남겨둘 필요가 없다.

## 검증과 한계

- 오프라인 단위 시험 18개 통과. 기존 곡선 계산·충돌 경계·프로파일 시험 18개 통과. 합계 36개.
- 제공 실물 runtime 파라미터를 입력한 별도 서버 YAML 생성 및 기존 입력 불변 대조.
- 파이썬/셸 구문 및 전달 패치 적용 검증.
- 작업 환경에는 ROS 설치가 없어 이번 독립 서버 ROS configure/activate·실물 곡선 동작은 미실행이다. 로봇 `check`와 `plan`을 먼저 실행해 연결·설정 보존을 확인해야 한다.
- 서버 격리는 기존 실패 원인 규명 완료를 뜻하지 않는다. 별도 costmap은 기존 수치를 쓰되 별도로 갱신되므로 기존 costmap과 셀 단위로 동일하다고 보장하지 않는다. 센서·TF를 공유하며 추가 CPU 부하는 실물 확인 대상이다.
- 시험 중 관제/다른 터미널에서 Goal·수동 속도를 보내지 않는다. 이것은 운영 ActionHandoff 소유권을 대체하는 정식 미션 연결이 아니다. 이미 확인되지 않은 수동 속도 발행자와의 자동 중재를 주장하지 않는다.
- 프로세스/기기 전체 장애와 실제 모터 정지는 기존 smoother timeout 및 장치 경로의 영향을 받는다. 물리 정지 검증을 소프트웨어 단위 시험으로 대체하지 않는다.

## 적용/복원

기존 trial.bash, nav2.yaml, 지도, 태그, BT, C++ ArcController는 이번 패치에서 변경하지 않는다. 기존 성공 런치와 Zenoh를 유지하고 독립 시험 도구만 실행한다. 반영 전 PC/로봇 대상 파일을 PC에 백업한다. 자동 커밋·푸시·로봇 이동 없음. 복원은 백업한 arc_trial.py를 되돌리고 새 독립 도구를 사용하지 않으면 된다. 기존 주행은 원래 trial.bash로 실행한다.
