# 공용 코드 사전 반영 검토 — 로컬 b5ef6f2 / 실물 48d2d1c

2026-10-27 KST. 사용자 “공용코드 반영해야되는거는 미리 검토해놓자 로컬이랑 차이” 요청. fetch 후 커밋된 양쪽 소스를 공통 조상2a397da와 함께 비교했다. **실행 코드 수정·병합·주행 없음**. 검토 문서만 로컬 작성, 커밋/푸시 없음.

## 비교 범위와 해석

- 로컬 main: b5ef6f2fd428b6d4d3d5b7973053ae0026f16ea8
- 실물 origin/feat/harvest-handoff-real-20261018: 48d2d1c812a968058254ddb2355ee5dfc9b96c68
- robot/ros_ws/src 기준 조상 이후 변경 경로: 로컬만66, 실물만83, 양쪽37. 양쪽37 중 최종 내용 동일17, 실제 다른 내용20. 이것은 Git 충돌 개수나 버그 개수가 아니다. 신규 패키지/시험/vendor 파일 포함.
- 원격에 없는 로컬 파일을 ‘실물 담당자가 삭제했다’고 해석하면 안 된다. 교통 타입/클라이언트와 vendor Nav2는 로컬에서 별도로 추가한 기능이다.

## 1. 먼저 선별 반영할 공용 개선

| 우선순위 | 정확한 대상 | 차이/필요성 | 최소 반영안과 실물·시뮬 영향 | 검증 |
|---|---|---|---|---|
| 높음 | farm_common/farm_common/action_handoff.py:ActionHandoff.acquire | 로컬은 외부check를condition 잠금 안에서 호출, 실물은 밖에서 호출 후 예약 재확인. 외부check가 다른 잠금/스레드를 기다리면 잠금 순서 위험 | 해당 메서드 변경만 선별. 작업 선점/비선점 정책 유지, 양 환경 공용 | check 중 타 스레드current 조회, 취소/선점/예약 전환 경합 |
| 중간 | farm_navigation/farm_navigation/navigation_types.py:NavigationSettings.from_mapping | 로컬은 retry21 및 navigate_to_pose+retry1도 설정 수락, 실물은0~20 및FollowPath 전용으로 거절 | 설정 검증 두 조건만 반영. 기본0 유지. 기존 비활성 프로필 영향 없음, 잘못된 설정은 조기 실패 | bool/음수/21/다른mode 거절,0/5/20 허용 |
| 중간 | farm_navigation/farm_navigation/pose_provider.py | 실물은 TransformUnavailable/TransformStale 구분 및 같은 표본시각의 map/odom 쌍 조회·진단 제공 | 기존lookup/current/latest_sample 보존하며 API를 추가. 미래시각/잘못된쿼터니언/비유한값을 임시 센서 지연으로 숨기지 않음 | TF만료/미래/누락 구분, 동일stamp 쌍, 취소/시계역행, latest_sample 교통등록 회귀 |
| 인계 통합 시 | farm_navigation/{nav2_client.py,arrival.py} | 실물은 플러그인 종류를 먼저 읽고 표준·벽 완료 판정 파라미터를 나눠 조회 | 로컬 속도 조회/거리 예산은 유지하고 플러그인별 preflight+wall 검증을 함께 반영. 인계 없으면 표준 검사 유지 | 실제 GetParameters 반환과 표준/벽 설정, 기존611초 예산 |

직접 오프라인 확인: 동일ActionHandoff API의 외부check에서 다른 스레드가current를 조회할 때 로컬은check가끝나기전 완료되지않고, 실물은완료됨. **잠금 보유 차이를 확인한 경계 검사**이며 현재 운영에서 실제 교착이 발생했다는 증거는 아니다.

## 2. 로컬과 이미 같은 부분 — 다시 가져올 필요 없음

- `farm_navigation/farm_navigation/collision_recovery.py`는 양쪽 SHA256 **d22b25e5f2d2c9c249f0b578f26dfcbe13b308d953b7c440721054709fbafc9a**, 바이트 동일.
- 특정 종료된106 오류의 제한 재시도, 최소정지2초/준비30초/대기 제외 기본 구조는 이미 선별 반영돼 있다.
- 차이는 Nav2Client의 시계 주입/정지 출력 소유자 연결과 HarvestNode의 재시도 선택·활성화 경계다. 파일 전체 복사로 이미 같은 핵심 로직을 덮어쓸 필요 없음.

## 3. 로컬 수정과 충돌하므로 반드시 보존할 내용

| 대상 | 로컬 유지 항목 | 실물 파일을 통째로 적용할 경우 |
|---|---|---|
| nav2_client.py | 교통 acquire→검사→execute→movement_finished, request_stop, 경로길이/속도별 제한·사전 속도 조회 | 교통 허가 경계·비동기 취소와 긴 경로 예산이 사라짐 |
| parallel_approach.py 및 harvest corridor 호출 | 차체yaw/횡오차/전방 조건 분리(D-059) | 목표선각 제한이 다시 들어와 짧은 이동에서 APPROACH_RECOVERY_REQUIRED 재발 가능. 상세진단만 따로 가져올 것 |
| pose_provider.py | latest_sample 원본stamp 조회 | 예찰 교통 Status의 TF 보고 연결이 깨짐 |
| spin_client.py | 교통 활성 상태에서 미지원 인계 Spin 차단 | 교통으로 예약되지 않은 회전을 허용하는 결과. 인계 공간 허가 정의 전 제거 금지 |
| farm_interfaces / traffic_* / scout·harvest Node·Communication·Status |9타입/등록/정지/원 task_id·boot·sequence/테스트 서버 | 실물 브랜치에는 이 추가분이 없으므로 병합 시 명시 보존 |
| nav2_controller vendor | 제어 pose와 최종 도착TF 같은 주기 사용 및 회귀 | 실물Git에 패키지 없음. 설치된 실물 바이너리에 동일패치가 있는지는 별도확인 필요 |
| tag_localization / tag_control / scout survey | 복수태그·추가정지없는보정·윈도우정렬·깊이오차여유 | 이 변경은 로컬 독립 개선. 실물브랜치 복사로 역행하지 않게 유지 |

## 4. 새 인계 기능은 묶어서 검토해야 함

실물에만 있는 farm_arc_controller/farm_wall_controller/farm_tag_camera_runtime, harvest_robot/handoff_*·pause_clock·transient_gate·transfer_*는 단일 파일 버그 수정이 아니라 인계 실행 경로다.

함께 필요한 공용 API:
- RoutePlan.headings ↔ path_builder의 점별 차체 방향 보존.
- Navigator.explicit_routes/stop_output/settling_check/arrival_validator 및 검증된 취소 정리.
- Nav2Client/SpinClient의 선택 execution_clock ↔ PauseClock/벽 대기 시계.
- arrival.py의 WallGoalChecker 검사 ↔ wall 플러그인/설정/전용서버 런치.
- HarvestNode/Communication의 window 저장·무효화 ↔ 인계 복귀·다음window 연결.
- discharge_client의 components 조합 허용 ↔ transfer 장치/미시작 상태 구분.

이 묶음은 선택형 인계 프로필에서만 동작하도록 통합해야 한다. 현재 실물 런치는 handoff_config가있으면mode=real만허용하고 전용서버 use_sim_time=False를 사용한다. 시뮬로 바로 복사해 실행하면 안 된다. 카메라 종료용 C++ runtime도 일반 주행 필수 수정과 분리해 적용 경로를 확인한다.

### 병합 전 차단 항목: 속도 출력 소유권

- 실물 HandoffRuntime은 cmd_vel_normal/인계 raw 출력 중 하나를 릴레이하고 자신의 cmd_vel_nav publisher를 유일 출력으로 취급한다. 해당 토픽 발행자가1개가아니면거절하는검사가있다.
- 로컬 TrafficClient는 cmd_vel_nav와cmd_vel에 정지 publisher를 별도로 생성한다. 로컬Nav2Client도 TF복구 또는충돌재시도 선택시 추가정지publisher를 만든다.
- 따라서 양쪽을 그대로 합치고 함께 활성화하면 **정지 명령이0이어도 다중발행자 검사에 걸릴 구성 충돌**이 있다. 현재 로컬에는인계runtime이없으므로지금시뮬이이검사로실패했다는뜻은아니다.
- 권장: 인계릴레이를 출력 소유자로 유지하고 교통 정지와 재시도를 같은 정지 콜백에 연결. 교통 OFF/epoch변경은 기존Goal 취소까지 유지. 미지원인계의교통차단을임의해제하지않는다. 이결합설계는작업자정리본수령후확정하고공동검증한다.

## 5. 환경 설정이므로 자동 통일하지 않을 항목

실물 최신 인계 프로필의 일반 방향6도, 정지 후 복귀5cm/6도, 실행 중 최대3도는 **특정 프로필의 정책**이다. 공용 코드 수정과 시뮬 기본값 변경을 분리한다. 실물 지도·TF/센서·통신·실행경로도 유지한다. 양 환경 성능 비교에는 이조건차이를기록한다.

## 적용 순서와 통과 기준

1. 독립 개선: ActionHandoff 잠금 → 재시도 설정 검증 → TF 오류구분/조회 API. 기존 호출과 latest_sample 유지.
2. Nav2Client는 로컬 교통/거리 예산을 기준으로 시계주입·preflight를 수동 병합. 센서 대기 제외와611초 경로예산이 함께 유지돼야 함. sim은 ROS 시간, I/O·취소는 실시간 계약 유지.
3. 인계 API/플러그인/장치/런치를 한 묶음으로 통합하되 출력 소유권 충돌부터 해소. sim/real이 사용할 프로필과 장치 대응을 별도로 확인.
4. 기존117회귀 + 새잠금/TF/명시방향/정지콜백실패·취소경합 검증. 이후Domain13/SUBNET CPU/headless에서 대기/우회/취소/관제초기화와 인계 복귀→다음window를 구분해 실제 시험.

이번 작업에서 실행한 것은fetch/3방향소스비교/ActionHandoff·설정API 오프라인경계검사/동일파일SHA뿐이다. 새병합코드단위시험·빌드·Isaac·실물시험은실행하지않았다. 비교원본·실행스크립트는sim/runs/common_merge_review_20261027/. 공유용전체경로목록과검사결과는동명JSON. 로컬실행코드는b5ef6f2그대로다.
