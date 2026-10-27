# 일반 주행 전진 곡선 대체·지속 대기 후보 — 2026-10-26

사용자 “다시 안멈추게 고쳐와” 요청으로 별도 후보 작성. 운영 적용·재기동·이동 승인은 수행하지 않았다. 기준 Git HEAD cf870daa00e7b752a39bbb3c84fc61c412cb2de7, 기존 미커밋 변경 보존. 실제 기반은 로봇 sensor_hold_robot_20261024의 farm_navigation/harvest_robot 및 프로젝트 farm_nav2_controller 원본이다. PC 소스를 최신으로 간주하지 않았다.

## 직접 확인한 실패와 수정 범위

14:51 일반 SECTION_APPROACH에서 최초 collision ahead 후 5회 재시도 모두 같은 오류. 첫 재시도 약0.55초, 나머지는 목표 수신 직후 중단, retries=5 소진. 로그 runs/retry_trial_20261026/launch.log. 장애물 셀/위치 추정의 당시 원인은 아직 확정하지 않았다. 재시도가 전진 회피를 생성하는 구현은 아니었다.

| 후보 대상 | 변경 | 유지 사항 |
|---|---|---|
| farm_nav2_controller/forward_recovery_controller.hpp, cpp | 별도 ForwardRecoveryController. 기본 RPP의 NoValidControl 중 경로 방향 회전 상황에서만 전진 곡선 대체 계산 | 기존 RPP 우선, costmap/footprint 충돌 검사, 속도 규제, 회전 속도·가속 제한, TF 예외 |
| CMakeLists.txt, controller_plugins.xml | 새 플러그인 추가 | 기존 플러그인 보존 |
| farm_navigation/collision_recovery.py | 선택 시 횟수 소진·30초 준비 대기로 작업 종료하지 않음. 최초 5회 이후 5초 간격으로 재검사 | 취소/소유권 검사 매 순환, 대기 중 zero, 종료된 Goal만 재전송 |
| navigation_types.py, nav2_client.py | 기본 false인 collision_keep_waiting과 기존 대기 제외 시계 연결 | 기존 사용자 기본 정책, 실제 실행 제한·취소·다른 오류 분류 |
| harvest_robot/node.py | 수확 전용 navigation_collision_keep_waiting 선택 | 다른 로봇 기본값, 인계 전용 동작/스테이션 복귀 설정 |
| harvest_candidate.json, nav2_addition.yaml | 접근에 HarvestForwardRecovery 선택 및 지속 대기 true의 제안 | 기존 controller 목록/항목 보존, 일반 costmap·인계 설정 불변 |

전진 후보는 전방 carrot에 대해 기존 RPP 곡률과 속도 규제를 사용하며, 기존 회전 속도·가속 한계를 넘지 않도록 곡률을 유지하여 속도를 낮춘다. 기존 예측 거리로 동일 충돌 검사기를 통과한 경우만 반환한다. 취소 중/후진/최종 목표 자세 정렬에는 대체하지 않는다. 새 경로 계획기나 임의 좌표 이동은 아니다. 현장 코너가 이 곡선으로 통과되는지는 미검증이다.

계속 움직이는 보장은 아니다. 모든 궤적이 막히면 정지 대기한다. 지속 대기 선택은 횟수·준비 지연에 따른 종료를 없애며, 실제 실행 시간·진행도 실패·다른 Action 오류·출력 소유권 상실 등까지 무시하지 않는다. 대기 시간만 전체 실행 시간에서 제외한다.

## 백업·산출물

PC `runs/forward_recovery_candidate_20261026/`:
- baseline/robot_sources.tar.gz, harvest.json, harvest_nav2.yaml: 로봇 원본 읽기 복사
- src/: 후보 전체 패키지, manifest.json 및 candidate.patch
- harvest_candidate.json, nav2_addition.yaml: 선택 제안. 실행본에 병합하지 않음
- tests/: 직접 실행 로그. build/install: PC 전용, 로봇 ARM 실행 금지

운영 파일은 미수정이므로 현 상태 원복 작업은 불필요하다. 기존 성공 백업 유지. 후보 포기 시 해당 후보를 선택하지 않는다. commit/push 없음.

## 직접 검증

- PC Nav2 헤더/라이브러리로 farm_nav2_controller 빌드 성공.
- 실제 RPP/CollisionChecker와 합성 1cm costmap: 기본 회전 거절, 후보 전진 곡선 통과 사례 확인(cell169,173; v≈0.01414m/s, w=0.05rad/s). 이 셀은 합성 시험 좌표이며 현장 장애물 위치가 아니다. 전방 전체 점유 시 거절, 최종 yaw 정렬 및 취소 시 선속도0 확인. C++ 1개 복합 시험 통과.
- 기존 settling C++ 12개 통과.
- 기존 재시도/Action 분류 Python18개, 신규 지속 대기 Python4개 통과. 30초 초과 입력 준비 대기 후 복귀, 5회 초과 재개, 취소 및 소유권 상실 확인.
- localhost/domain193의 별도 Action 대역 + 실제 후보 Nav2Client/HarvestMission/StateController: 6개 시나리오. 6회 abort 후 7번째 Goal 성공, goal_timeout1초에서도 대기 포함 약15.84초 후 정상 완료. 대기 제외 시계 확인. 기존 제한 재시도·다른 오류·실행 제한·취소 회귀 포함.
- 전체 후보 Python AST 검사.
- 첫 빌드 명령의 colcon log-base 위치 오류 후 수정. 초기 C++ fixture에서 TF timeout 스레드 경고 발생, 합성 정적 TF fixture의 transform_tolerance=0으로 고친 최종 시험에서 경고 없이 통과. 운영 TF 조건은 변경하지 않았다.

검증 한계: 합성 costmap과 Action 대역은 각각 검사했으며 전진 플러그인+실물 센서+전체 수확 FSM 동시 E2E는 미실시. 로봇 ARM/Nav2 1.3.11 빌드·플러그인 로드, 전체노드 조립, 실제 코너 통과는 후속 검증 필요. 사용자 실행 프로세스는 기동·종료·재시작하지 않았으며 실제 이동 명령 없음.


## 로봇 ARM 빌드·버전 검증 및 운영 적용 준비

사용자 승인으로 로봇 `/home/vic/Downloads/forward_recovery_build_20261026`에 별도 빌드. PC Nav2 1.3.13과 로봇 1.3.11 차이를 확인하고 로봇 헤더/라이브러리로 3패키지 빌드 성공(2분44초). 후보 설치 Python10모듈의 경로와 소스 SHA 일치, 새/기존 플러그인3종의 pluginlib 로드·소멸 및 /proc/self/maps 후보 라이브러리 경로 확인. ARM lib SHA256 `1281a1ba5452de24249a8823b25b67ae024c8250c1f6b6e24d5f9e93c5b54d54`.

로봇 domain193/localhost 장치 없는 검증: 실제 Nav2 합성 costmap 복합1, 기존 C++12, 설치본 Python18+4, 실제 후보 client/Harvest FSM과 Action 대역6 시나리오 통과. 지속 대기는6회abort후7번째 성공(15.41초/실행예산1초), 취소는 약0.375초에 전달. 테스트 프로세스 종료 확인. 실제 모터·센서·전체 주행 E2E와 전체 HarvestNode 기동 검증은 미실시.

운영 소스/설치본/설정/저널292파일 백업 후 불변 확인. PC `robot_operating_backup.tar.gz` 전송SHA `f65bb655e6d177be47723e408ac85c75c05d339f2f91053dd3fe829192952789`, 내부292파일도 manifest와 대조. 기존 백업 유지. PC robot_verification/ 및 robot_verification_bundle.tar.gz에 로그 보존. 운영 교체·프로세스 기동/종료/재기동·이동·commit/push 없음.

### 적용 범위 분리
사용자가 “기존 성공 동작에서 멈추지 않게 하는데 왜 많이 바꾸는가”라고 지적했다. 에이전트가 종료 방지와 새 전진 동작을 함께 묶어 범위를 키웠음을 설명했다. A는 Python4파일과 수확 선택 설정만으로 횟수·준비 대기 종료를 막고 기존 controller/Nav2 설정을 유지한다. A용 harvest_wait_only.candidate.json을 별도 준비. B는 전진 곡선 대체까지 추가하는 플러그인/설정 변경이다. 둘 다 운영 미적용이며 전체 B 적용을 기본으로 간주하지 않는다. A만으로 지속 충돌 상황을 물리적으로 통과할 수 있다고 주장하지 않는다. 적용·원복 절차 ROBOT_APPLY_PLAN.md 참고.


## 2026-10-26 사용자 범위 정정: 기존 성공 동작과 최소 수정 우선

사용자는 정지 대기만이 아니라 기존처럼 전진·회전 통과를 원하며 성공 코드 대비 변경 원인을 먼저 확인하도록 요청했다. 새 ForwardRecoveryController는 기존 동작 복원이 아니라 새 동작 선택이므로 운영 적용 준비 완료를 실기 문제 해결과 혼동하지 않는다. 해당 후보 적용은 보류한다.

직접 대조: runs/turn_direction_audit_20261024/previous_general_nav_params.yaml(이전 성공 실행 보존본)와 현재 일반 controller 실제 argv의 /tmp/tmptzsxpirm은 YAML 전체 값 차이0. 10/26 08:49 성공 launch에서도 HarvestApproach 기본RPP 사용 확인. 당시 trace의 handoff_runtime SHA가 align 후보 baseline의 실제 파일 SHA와 일치; 현재 runtime과 source==normal 분기의 AST 동일(원본 msg 그대로 발행). 전체 forward 메서드 hash는 인계 분기 수정으로 달라 일반 분기 자체와 구분한다. 08:49 성공과14:51 실패의 graph revision/코너 경로는 같고 출발 추정 위치는 다르다.

기존 10/24 성공 raw command 기록에서도 제자리 회전과 전진·회전이 교대한다. 10/24 기록의 실제 RPP 오프라인 비교는 TF 변화에 따라 경로각 -4.49→+16.56도, 회전 선택 false→true 전환을 재현했다. 이는 이번14:51 실패 직접 재현으로 재사용하지 않는다. 현재 정지 pose로 재구성한 carrot각 -6.456도는6도 기준 직밖이지만 실패 당시 내부 carrot 자체를 측정한 값이 아니다. 새 내부trace에는 입력 시각만 있으며 속도·costmap 기하가 없으므로 이번 실패 순간의 정확한 판단 재현에는 한계가 있다.

이번 범위에서는 되돌릴 일반주행 회귀 변경이 확인되지 않아 추가 코드/임계값 후보를 추측으로 만들지 않았다. 운영 적용·재기동·이동 없음. 자료 runs/success_motion_compare_20261026(성공/실패 trace, parameter_diff.json, normal_branch.txt, comparison.json). 현재 조사 결과는 원인 확정/수정 완료가 아니다. 다음 근거는 실제 controller 경로점·전진 명령·동일 시점 costmap과 자세를 연결해야 하며, 사용자에게 자동 재주행을 요청하지 않는다.
