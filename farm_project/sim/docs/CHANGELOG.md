# 시뮬레이션 통합 변경 이력

시뮬 전용 변경과 시뮬 통합에 필요한 공통 변경을 기록한다. 공통 변경은 사용자 승인 전 적용하지 않는다.

## CAMERA-RETRY-METRICS-20261021 — 실적 손실 비중단·1회 재탐색·성능 집계

- 승인: 사용자 비대상 이탈/평가 ID 연결을 Action 실패로 삼지 말고60초 실패 후1회 재탐색/재시도하며 actual/expected/harvested를 평가하라는 지시, D-051.
- 대상: farm_sim_devices/student_session.py, sim 전달 student60_mission.py의 opt-in 복귀, sim harvest.json/harvest_task.json 외부 대기 제한, run_section_campaign.py/campaign_performance.py 및 관련 sim 시험. 기존 공통 TF 수정/실물 설정/모델 가중치는 유지한다.
- 전후: ID 불명·비대상 과실 이탈·목표 낙하/60초 실패가 전체 중단으로 이어지던 경로를 분리했다. 카메라만으로 시도하고 익명 레이저 통과를 집계하며, 측정 복귀 후 새 관측으로 한 번 재시도한다. 재시도 소진/대상 없음은 수확 실패 실적이며 다음 대상으로 진행한다. 실제 복귀·정지/통신/주행 실패는 Action 실패를 유지한다. 평가 ID는 접촉 정지 기준에도 사용하지 않는다.
- 평가: 수확 전 실제 장면의 작업범위 red/yellow, 예찰 expected, 레이저 harvested를 별도 집계한다. 성능 사건과 Action 실패·평가 진단을 분리한다. 설정 복사20초 실패는 진단만 남긴다. 외부 sim 대기 제한만7200/7260/7500벽시계초로 조정하고 개별 수확60시뮬초는 유지한다.
- 검증: 관련81개 통과, diff/컴파일 정상.09:52 KST SEC07 2회차부터 기존 성공 예찰을 재사용해 실제 시험 재개. 실제 Isaac의 시간초과/비대상 이탈 전 시나리오 검증은 진행 중이다. 상세 PROJECT_STATE §88 및 기존 캠페인의 policy_camera_retry_once_20261021.
- 실물 영향/복원: 공통/실물 배포 변경 없음. 전달 미션 새 옵션은 기본False로 기존 사용자 동작을 보존한다. 시험 정리 후 이번 sim 변경만 역적용하고 원본/캐시는 보존한다. 미커밋·미푸시.

## OVERNIGHT-REPORT-20261021 — 야간 시험 중간 집계

- 승인: 사용자 결과 보고 요청. 운영 코드/설정 및 진행 중 시험은 변경하지 않았다.
- 09:27 KST: SEC01~05 완료, SEC06 5회차 마지막W008 진행. 전체18시도 중 성공5/실패12/진행1. 성공한 최종 시도39window에서 예상56/수확34.
- 누적 실패: 주행105 1건(야간 지시 전), 파라미터 수집2건, 팔/시뮬9건. SEC01 3건의 선행 원인은 비대상 과실 이탈이며 이후 정지 확인 실패로 종료. SEC03 평가 ID 매칭2건, SEC06 같은 목표의 시간초과/낙하 감시4건. 상세/한계/원본 위치는 PROJECT_STATE §87.
- 원본 및 보고 스냅샷 보존, 예찰 캐시 재사용 실제 확인. 실물 영향 없음, 복원 대상 운영 변경 없음. 문서만 미커밋·미푸시이며 시험은 계속 진행한다.

## SCOUT-CACHE-OVERNIGHT-20261020 — 성공 예찰 재사용과 SEC01~16 야간 실행

- 승인: 사용자 성공 예찰 보존/수확부터 재시작 및 밤샘16SEC 순차 진행 요청, D-050.
- 대상: `tools/run_section_campaign.py`, `tests/test_section_campaign.py`, 기존 상태/결정 문서. 시뮬 시험 실행 도구만 변경하며 공통·실물·운영 미션/팔/주행 판정에는 영향이 없다.
- 전후: 이전에는 실패할 때마다 전체 재시작 후 예찰부터 실행했다. 이제 성공 예찰 원본을 캠페인별/SEC별 캐시에 저장하고 재시작 후 모든 window를 수확부터 실행한다. 현재4회차의 성공8window/예상12개를 보존했고 진행 중 작업을 중단하지 않았다.
- 야간 실행: 현재 SEC01 감독자 종료 후 같은 캠페인에서 SEC02~16으로 이어지는 독립 서비스를 활성화했다. Domain13/SUBNET, 시간 제한 없는 시험/읽기 전용 기록, 자동 절전 방지를 확인했다. 시도별 실패·수량·로그를 유지하고 성공한 SEC만 다음으로 넘긴다. 전체 완료 후 종료한다.
- 검증: 캐시/재시도/SEC01→SEC02~16 재개 회귀6개, 실제 ROS 메시지 왕복 보존, 셸 문법, diff 검사 통과. 실제 캐시 재시작 E2E/16SEC 완주 확인 전이며19:20 KST 현재 W001·W002 완료/W003 진행이다. 상세 PROJECT_STATE §86 및 runs/sec01_goal_time_fix_20261020_183345.
- 복원: STOP으로 시험 정리 후 이번 실행기/시험 diff만 역적용한다. 원본/캐시 데이터는 보존한다. 미커밋·미푸시.

## SEC01-GOAL-TIME-RETEST-20261020 — W001 수확 완료 및 W002 명령 전달 중단 기록

- 승인: 사용자 재시험 진행 지시. D-049 공통 시각 수정본·Domain13/SUBNET으로 기존 캠페인을 계속한다. 이번에는 운영 코드/설정 변경 없이 계측·문서만 추가했다.
- 결과: 2회차 예찰9window/예상13개 성공. W001 도착→팔 실행→박스 센서1개→접힘 확인→Action SUCCESS. W002는0.6704m 이동을 시작했으나 최종 cmd_vel 출력이 재개되지 않아105, 팔 미실행이다. RPP는전진0.1m/s를 계속 내고 회전 상태는false였으므로 이전 도착 시각 불일치와 구분한다.
- 증거: 두 ROS 기록기에서 W002 cmd_vel0메시지, sim transport6294수신 유지/거절0/마지막0명령을 확인했다. 원본·수량·실패를 보존하고 전체 재시작 후 재시도 중이다. smoother 내부/DDS 책임은 아직 미확정이며 읽기 전용 endpoint·lifecycle 기록을 추가했다. 상세 PROJECT_STATE §85.
- 영향/복원: 실물 및 공통 운영 동작 변경 없음. 시험을 끝내려면 해당 캠페인 STOP과 기록기 서비스 종료를 사용하고 원본 로그를 보존한다. 자료 runs/sec01_goal_time_fix_20261020_183345. 전체 SEC01 성공·105 전면 해결을 주장하지 않는다. 미커밋·미푸시.

## COMMON-GOAL-TIME-20261020 — 추종과 도착 판정 시각 일치

- 승인: 사용자 “당연히 일치시켜야지 뭐하는거야?”, D-049. 이전 계측으로 확인된 공통 시간 불일치를 수정한다.
- 대상: 공통 `robot/ros_ws/src/nav2_controller`의 공식1.3.12 원본과 제한된 controller_server.cpp/.hpp 수정·회귀 시험, `scripts/build.sh`. 원본 출처·해시/Apache-2.0 라이선스 보존. sim 전용 코드나 실물과 다른 성공 조건을 추가하지 않는다.
- 전후: 이전에는 경로 생성 시각의 목표를 변환하다 과거 TF가 없으면 latest를 사용했다. 이후에는 실제 제어에 사용한 로봇 pose를 최종 판정에 전달하고 그 stamp로 목표를 변환한다. 같은 시각 TF 실패는 기존102 경로로 전달한다. 도착/진행 허용치·stateful·경로 연장·물리·수확 정책 변경 없음.
- 실물 영향: real/sim 모두 공통 workspace overlay의 ControllerServer를 사용한다. 실물에도 재빌드·환경 로딩·재시작이 필요하며 실제 장치 배포/주행은 이번에 하지 않았다.
- 검증: 원본 별도 빌드에서3.94cm/5.10cm 불일치로 실패 재현, 수정본6회귀+11원본 기능 시험 통과, 기존 설정 검사39통과. lint통과, cppcheck17항목은 도구 버전 정책으로skip. 실제 SEC01은 새 캠페인183345에서 재시험 중이며 첫 시도는 주행 전 param dump20초 시간초과로 실패했다. 105 해결/전체 완주는 아직 미확정. 상세 PROJECT_STATE §84.
- 자료/복원: runs/nav2_goal_time_fix_20261020 및 runs/sec01_goal_time_fix_20261020_183345. 수정 전 캠페인18회차는 로그 보존 후 STOP. 복원은 이번 공통 overlay 소스/build/install만 제거하고 공통 workspace 재빌드·새 환경에서 기본 Nav2 prefix 확인 후 재시작한다. 미커밋·미푸시.




## NAVIGATION-PARITY-20261020 — 실물 담당 브랜치와 주행 성공/실패 판정 비교

- 승인/목적: 사용자 Hyaline-52 실물 브랜치와 공통·실물·시뮬 주행 정밀 비교 요청. 운영 소스/설정 변경 없이 분석한다.
- 비교: 원격 최신 real6f21119, 이전afdcc05, main e735dc9+기존 sim override. 최신 real와 운영 소스/인터페이스130개 동일, 목표·진행 판정 기준 동일. 실제 제어 설정은 접근 lookahead0.1/0.4m, RPP stateful/끝점 연장, costmap/footprint 등 차이가 있다. 현재 main real도 실물 성공 설정과 다르다.
- 증거/결론: PROJECT_STATE §81 및 runs/navigation_parity_20261020. 실패4회차 명시 controller 파라미터101개 일치, controller_server 실제105 기록, 기존 오프라인 시험38개 통과. 실물 런타임/바이너리·동적 설정은 미확인. 같은 판정만으로 공통 코드 결함을 확정하지 않는다.
- 변경: 문서/분석 산출물만 추가. 공통/실물/sim 운영 동작 영향 없음. 되돌릴 경우 이번 문서 절과 비교 산출물만 제거하며 원본 시험 로그는 보존한다. 미커밋·미푸시.

## SIM-ROS-DISCOVERY-20261020 — 후속 시험 Domain13/SUBNET

- 승인: 사용자 “다음부터 시험할때 ROS Domain 13, 통신 범위 SUBNET”.
- 대상: `tools/run_section_campaign.py`, `tools/continue_section_campaign.sh`, 기존 감독자 시험 fixture. 기본 Domain74→13, discovery LOCALHOST→SUBNET; 새 manifest에 discovery 범위를 기록한다. 현재 실행은 유지하며 후속 새 실행부터 적용한다. 공통/실물 설정 영향 없음.
- 검증: 기존 감독자 회귀 시험과 셸 구문 확인. 실제 Domain13 관제 연결 시험은 아직 미실행이다. 복원은 해당 기본값/셸 인자만 역적용한다. 미커밋·미푸시.

## SEC01-RETEST-20261020 — SEC01 단독 통합 재시험

- 승인: 사용자 SEC01 재시험 요청. 소스·설정은 추가 수정하지 않고 D-044~046 적용본을 실행한다. 실물 영향 없음.
- 기존 navfix 캠페인은 STOP 정상 종료·자료 보존. 새 `sim/runs/sec01_retest_20261020/`에서 SEC01 예찰→전체 window 수확, 실패 시 전체 Isaac/ROS 재기동·동일 SEC 재시도를 시작했다. SEC02 이후는 실행하지 않는다.
- 10:28:20 KST 준비/10:28:29 예찰 Goal 전송과 실제 Nav2 수정 파라미터를 확인했다. 아직 SEC01 완료를 주장하지 않는다. 서비스 `farm-sec01-retest-20261020`, 상세 PROJECT_STATE §79. STOP 파일로 중단 가능. 미커밋·미푸시.

## STUDENT-AVAILABLE-TARGETS-20261020 — 예찰 예상량과 무관하게 팔 관측 목록 수확

- 승인: 사용자 “로봇팔 입장에서 할수있는만큼만 하고 넘어가야지 다음윈도우로”. D-040의 예찰 기대개수 일치 전제는 이번 요청으로 폐기한다.
- 대상/전후: `farm_sim_devices/student_session.py`에서 expected_count 양수/영상 작업가능 개수의 동등성 조건을 제거했다. 기존3초 관측시간 후 팔 카메라로 확인된 익은 과실 중 기존 작업 범위를 통과한 목록만 실행한다. 적거나 많아도 수량 불일치로 실패하지 않는다. 목록0은 측정 정지/접힘 확인을 거쳐 SUCCESS/수확0/실패0으로 반환한다. 원래 expected_count는 요청·결과·로그의 참고값으로 보존한다. 실제 수확량은 기존 평행3빔 통과로만 센다. 주행·충돌·팔 제어/정지 실패는 기존 오류로 전달한다.
- 영향: 공통 메시지/미션/실물/전달 vendor·가중치·작업 범위를 변경하지 않았다. 기존 공통 Action은 예상량과 실수확량이 달라도 SUCCESS를 전달하므로 시뮬 Student 어댑터만 수정했다. 기존 inventory_timeout_s 설정 이름은 호환을 위해 유지하며 현재 목록 확정 관측시간으로 사용한다.
- 검증: assignment11·팔 세션19·팔 ROS9·캠페인 감독자1, 총40시험 통과. 예상량보다 적음/많음/예상0/작업범위 밖/관측0과 원래 예상9→실제0/1/2의 ROS 결과 보존을 검사했다. 실제 Isaac/ROS에서 예상1·작업가능0 요청은 sim4.4초에 SUCCESS/수확0/실패0/safe_stopped=true를 반환했다. 로그 `sim/runs/inventory_policy_20261020/zero_action.log`, 원본 `sim/runs/harvest_test_ui/20261020T002245_w_1q7wfa/`.
- 이번 변경 추가 검증 기록: 실제0대상 시험의 최초 검증기는 ArmActionClient 반환 dict에 없는 expected_count를 조회해 해당 검사만 false였다. 원본 요청(request.json)의 expected_count=1로 정정한 독립 검증 `sim/runs/inventory_policy_20261020/zero_action_verified.json`에서10검사 통과를 확인했다. 최초 보고서는 보존했다. 새 서비스 `farm-section-campaign-20261020`는09:24 KST 시작했고 새 manifest의 Student 소스 SHA가 수정본과 일치함을 확인했다.
- 반복 시험: 기존 `section_campaign_20261019`의 실패46건과 정책 교체를 위한 중단47회차는 보존한다. 구정책·신정책 자료를 섞지 않도록 새 `section_campaign_20261020`에서 SEC01부터 같은 반복 조건으로 재개한다. 실행기가 Student 세션 소스 SHA도 manifest에 기록하도록 보완했다.
- 복원: 이번 student_session.py/시험/실행기 변경만 역적용한다. 새 캠페인은 STOP 요청 후 종료 확인/서비스 중지한다. 미커밋·미푸시.

## SECTION-CAMPAIGN-20261019 — 16개 SEC 예찰·전체 window 수확 반복 시험

- 승인/목적: 사용자 요청에 따라 SEC01~SEC16 각각 예찰 성공 후 반환된 모든 window를 수확한다. 중간 실패 시 자료를 보존하고 Isaac·ROS 전체를 종료/재기동하여 같은 SEC의 예찰부터 반복한다. 재시도 횟수 제한은 없다.
- 대상: `sim/tools/run_section_campaign.py`, `sim/tools/continue_section_campaign.sh`, `sim/tests/test_section_campaign.py`. 공통 로봇 소스·운영 파라미터·실물 설정을 변경하지 않는다. 기준 HEAD `e735dc9`.
- 시험 조건: 독립 ROS domain74/localhost, headless, RViz OFF, 태그 보정 ON, 현행 D435 Student 및 평행3빔, 기존 station 시작. 비교 가능한 독립 시도를 위해 성공 후 다음 SEC도 전체 스택을 새로 시작한다. 예찰 SUCCESS + 반환된 모든 수확 Action SUCCEEDED/SUCCESS/failed_count=0일 때 SEC 성공이다. 예상 수량과 실수확 수량의 일치를 별도로 강제하지 않으며 window0은 empty_harvest로 표시한다.
- 자료: `sim/runs/section_campaign_20261019/` 아래 시도별 Action 전체 요청/피드백/결과, cmd_vel_nav/cmd_vel/odom/AMCL/TF/clock/ROS 경고, 실제 Nav2 파라미터, 프레임 성능, 호스트 GPU/프로세스 상태, ROS/Isaac 로그 및 기존 예찰/구동/팔/평가 산출물 사본. 실패 자료는 덮어쓰거나 삭제하지 않는다. 원본 설정 해시·실행 명령·PID·시각을 기록하고 summary/failure_analysis JSON으로 집계한다.
- 지속 실행: 사용자 transient service `farm-section-campaign-20261019`가 현재 감독자 종료 후 배타 잠금을 얻어 체크포인트를 인계한다. 중단된 시도는 시스템 실패와 별도 표시하고 같은 SEC를 재시도한다. STOP 파일이 있으면 중단한다. 저장공간10GiB 미만이면 증거 보존을 위해 BLOCKED로 중단한다.
- 검증: Python 컴파일/셸 구문/기존 ROS·비전 import/16SEC 설정 확인. 감독자 시험은 실패2회→같은 SEC 재시도→16SEC 완료/18시도·36프로세스 종료 호출·재개 시 성공SEC 재실행 없음/실패 자료 보존을 검증했다. 이는 실제 로봇 성공률 시험과 구분한다. 실제 첫 SEC01 예찰은 17:40 KST 시작; 캠페인 전체 완료는 아직 미확인이다.
- 복원: 캠페인 폴더에 STOP 파일을 만들고 시험 종료/로그 보존을 확인한 후 사용자 서비스를 중지한다. 새 실행기/시험 파일 및 이 기록만 되돌린다. 실행 결과는 증거로 보존한다. 미커밋·미푸시.

## HARVEST-COMPLETION-PROFILE-20261016 — 이동 전용 실행 경로의 팔 생략 수정

- 요청/범위: 팔 작업 없이 완료되는 현상 확인 요청. 실제 런치·서버 파라미터·로그로 ARRIVAL_ONLY_NO_HARVEST 선택 확인.
- 대상/전후: 실제 사용 중인 `runs/navigation_smoke_20261014/harvest_runtime.yaml`의 harvest_config 참조를 이동 전용 시험 JSON→현행 canonical harvest_task.json으로 변경. 다음 시작부터 ARRIVAL_THEN_ARM을 선택한다. 이전 이동 전용 JSON은 증거로 보존했다. 공통/실물 변경 없음.
- 검증: 공통 환경 로더로 수정 경로를 읽어 팔 작업 정책/팔 활성화/60Hz 확인. 기존 실행 중 서버는 재시작하지 않았으며 사용자 작업 중단·Goal 전송 없음. 재시작 후 시작 로그와 실제 수확 완료는 아직 이번 실행에서 미확인.
- 복원/반영: `runs/harvest_completion_20261016/harvest_runtime_before.yaml` 또는 참조 한 줄 복구. PROJECT_STATE §67과 실행 가이드에 재시작 필요 명시. 미커밋/원격 미반영.

## WHEEL-TIRE-FIX-20261016 — 저속 회전 접촉 단면 수정과 정지 유지 보완

- 승인: 사용자 “진행해 … 원인을 … 설명해” 실행 요청. 기존60Hz 통합과 사용자 변경 보존, 공통/실물 수정 없음.
- 대상: `assets/robots/harvest_count_test/harvest_robot.usd`, `farm_sim_devices/wheel_servo.py`, `tests/test_wheel_servo.py`, `tools/rebuild_harvest_tire_collisions.py`, 진단 결과와 PROJECT_STATE §66/DECISIONS D-039/이 기록.
- 전후: 평평한50mm 원통 충돌선에서 같은 +0.05rad/s 4초 입력0.970° 정체→같은 외경/폭의 둥근 native 원통 묶음10.425° 회전. 평평한 단면 분할 대조군0.953°로 개수 증가 효과를 배제했다. 정지 유지 때 매 tick 적분 초기화→정지 전환에서만 초기화/유지 중 외란 오차 적분. 원래 kp1/ki4/상한2 유지(kp8 후보 탈락·복구).
- 검증: 바퀴 단위5개/자산 범위 검사 통과.46sim초 전후진·회전·정지 특성 기록, 실제 Nav2 양방향 정렬/0.5m 이동3개 정상 완료, 실제 Teacher 팔 Action2/2 적재·복귀·safe_stopped. 중속 급정지 피크2° 목표는 약3.4°로 미달한 계측 한계를 명시했다. 전체 농장 연속 미션·실물·밀집3개 복귀·접촉 취소는 이번 인증 범위 아님.
- 복원: `runs/wheel_contact_20261016/before_apply`의 자산과wheel_servo.py만 원위치 복사. 기존60Hz 통합을 되돌리지 않는다. 미커밋/원격 미반영. SHA와 결과/시행착오는 같은 runs의applied.json/verification_final.json을 따른다.

## WHEEL-CONTACT-DIAG-20261016 — 무부하/접지 분리 및 후보 탈락 기록

- 승인: 사용자 sim 전용 구동·접지 개선 방향 승인. 대상은 `sim/runs/wheel_drive_20261016/` 진단 실행 사본/집계와 PROJECT_STATE §64 정정·§65, DECISIONS D-038, 이 문서다.
- 전후: 속도 보정 상한 부족을 근본 원인으로 단정했던 설명을 철회했다. 무부하 정상 추종/접지 정체, 접촉 폭 영향, 질량 증대·유한 force drive·직접 토크 PI 후보 미통과를 확인했다.
- 운영/실물 영향: 이번 진단은 운영 소스·USD·설정 및 공통/실물 변경 없음. 사용자 확인 결과 공식 공개 자료에 필요한 질량/감속비/출력축 토크 사양 없음. PI 상한 확대, 타이어 폭 축소, 임의 질량/토크 변경은 운영에 반영하지 않았다.
- 검증/복원: 실제 Isaac CPU60Hz 격리 시험의 관절 위치 차분·차체 회전·정지 구간 집계. 전체 Nav2/실물 회귀는 미실행. 시험 출력과 문서만 있어 운영 복원 대상 없음. 미커밋/원격 미반영.

## HARVEST-105-20261016 — 실제 정체 원인 분리

- 요청/범위: 사용자105 발생 당시 움직이지 못한 원인 확인 요청. 운영 소스·설정·공통 코드·자산 수정 없음. 기존 프로세스 종료 이후 별도 포트·scene으로 접촉/구동 비교 시험만 실행했다.
- 결과: 실제 명령 수신 정상, 바퀴 PI 보정±2rad/s 포화와 차체 정체 확인. 실패 자세에서 동일 +0.05rad/s 10초 입력에 기본0.919°/보정 상한20 시험26.448° 회전. 내부 충돌 제거·GPU·drive gain/type 변경만으로는 미해결. 마찰 감소/solver 반복 증가로 개선돼 현행 접지·구동 보정 조합의 한계로 확인. 운영 상한20 적용은 하지 않았다.
- 검증/제약: 유효8개 격리 시험의14sim초 trace/contact와 실제 수신/휠/차체 로그 집계. 최초 마찰 시험은 instance 편집 오류로 제외하고v2로 재시험. 종료 지연으로 소유한 시험 프로세스만SIGTERM 정리. 전체 Nav2 재주행/실물 미실행. 수치와 다음 검증은 PROJECT_STATE §64.
- 파일/복원: `sim/runs/harvest_105_20261016/`의 진단 산출물, PROJECT_STATE §64 및 이 기록만 추가. 운영 복원 대상 없음. 문서·결과 미커밋, 원격 미반영.


## TEACHER60-ACTION-20261016 — 수확 Action과 팔 실행/국소 물리 연결 확인

- 승인: 사용자 수확 액션에60Hz Teacher 팔 움직임 연결, 향후 카메라 정책 교체, 근처 과실만 물리 적용 요청.
- 대상: `farm_sim_runtime/{fleet_config.py,launch/harvest.launch.py}`, `sim/tools/check_teacher_action.py`, `check_teacher_harvest.py`, sim 액션 설정/통신 시험과 실행 문서. 기존 공통 `HarvestMission`/`ArmActionClient` 및 sim 팔 실행 연결을 재사용하며 공통·실물 소스 변경 없음.
- 전후: 기존 ARRIVAL_THEN_ARM/내부 팔 Action 기본값은 유지하고 팔 OFF·endpoint 불일치·국소 물리 OFF를 시작 전에 거부한다. 미래 카메라 모델 교체는 관측/정책/대상 선정 어댑터 경계로 명시하며 새 추상화나 Student 대역을 넣지 않는다.
- 검증: 실제 ROS→UDP→Isaac로2개 적재·물리 복귀·접힘·정지 및 ROS SUCCESS/2개 수량 확인. 활성 과실0→4→2/전체288. 취소 시험 상세와 로그는 [PROJECT_STATE §63](../../docs/PROJECT_STATE.md#63-수확-action의60hz-teacher-팔-실행과-주변-과실-물리--2026-10-16). 관련 최종62개, sim3패키지 build PASS. 전개 중 취소는 실제 정지/CANCELED 확인, 접촉 중 취소는 CANCEL_UNCONFIRMED로 미해결. 외부 주행→팔 호출은 단위시험, 이번 실제 Nav2 미실행.3개 밀집 복귀 문제는 미해결.
- 복원/영향: 이번 사전검사와 검증 도구/문서 변경만 역적용하면 §62 상태다. 이전60Hz 모델/정책 통합을 되돌리지 않는다. 공통·실물 영향 없음. 새 launch는 재시작 필요. 미커밋·원격 미반영.

## TEACHER60-R2-20261016 — 60Hz Teacher 통합,480Hz 폐기

- 승인: 사용자 “그렇게 적용하고480hz는 폐기하자”. 기준 `7b0e1a4` 위 미커밋 작업. sim 전용 변경이며 공통·실물 파일 변경 없음.
- 대상: `assets/robotarm_teacher/`, `assets/robots/harvest_physics/teacher_arm_reference.*`, sim config5개, `farm_sim_devices`의 Teacher/줄기/장치/세션과 `_teacher_vendor`, runtime 물리 스케줄/자산/UI/진단, 해당 시험·fixture·import/replay 도구 및 실행 문서. 이전4개 체크포인트·staged_teacher/kernel 제거.
- 전후: 기존480Hz/response5·분리 정책 실행을 전달60Hz r2의 JIT+원본 단계 제어/response6/마찰2.2/단일 바닥/실제 속도 제한으로 교체. 유휴·수확60Hz/정책20Hz/렌더30Hz. 낮은순·물리 복귀 후 다음 목표, 적재 보존. SDK qd 잔류에 대한 정지 판정은 실측 q 변화·hold 오차·bounded qd를 함께 검사한다.
- 검증: 전달 SHA/내부1438개 일치, 독립 GPU26/32 재현,239tick 원본 명령 비교 최종목표 최대4.06e-6rad. 농장 단일1/1·연속2/2 적재/복귀/접힘/정지 PASS.3개 배치는 첫 적재 후 복귀 중 비목표 분리로 안전 정지(1개 적재/뒤2개 미시도),3개 순차 성공은 미완료. 상세와 최초 fixture 불일치 기록은 [PROJECT_STATE §62](../../docs/PROJECT_STATE.md#62-60hz-teacher-r2-적용과480hz-폐기--2026-10-16) 참조. 관련108개+84subtests, 추가 과실/배치17개+9subtests, USD 팔11개·과실19개 PASS. sim3패키지 빌드 PASS. 로그 `sim/runs/teacher60/`.
- 실물 영향/한계: 직접 영향 없음. 공유 Isaac scene 시간은60Hz로 고정되므로 기존 주행 사용자 확인과 이번 주기 변경 후 전체 연계 재검증을 구분한다. Student·실물·전체 Nav2 연계·실측 분리력 대응은 미검증. 기존 실행 세션은 유지했고 재시작이 필요하다.
- 복원/전달: sim 소스·자산·설정을 기준 커밋 버전으로 함께 복원 후3패키지 재빌드. 새 모델과480Hz를 혼용하지 않는다. 변경 파일과 삭제 목록만 담은 `sim/runs/teacher60/teacher60_changes.tar.gz` 및 패치 적용 방법은 같은 디렉터리 `PATCH_README.txt`. 현재 workspace에는 이미 적용했으므로 재적용 불필요. commit/push 없음.

## HARVEST-PROGRESS-AUDIT-20261014 — 최근 수확 주행 두 건 실패 진단 (미해결)

- 요청: 최근 수확 주행 중 제자리회전 후 ABORTED 원인 확인 및 현재 작업 커밋·푸시. 운영 코드·설정 변경이나 추가 주행 없이 기존 로그를 대조했다.
- 대상: `smoke_33b0484b8905`(16:41:21 KST), `smoke_48ad6a58d594`(16:50:29 KST). 두 건 모두 목표 (-6.015, 3.5278)로 WINDOW_MOVE 중 Nav2 `105: Failed to make progress`. 장치 세션은 각각 `4f43c6d8925a4201b06a6051bb44d861`, `c4518e851e42419897b6c52d236b6312`; 원본은 로컬 `sim/runs/drive_diagnostics/<session>/harvest_01.jsonl` 및 `sim/runs/harvest_motion/`에 있다(실행 로그는 Git 제외).
- 확인: 목적지 약 3.7m 앞, 실제 위치 x≈-6.02/y≈7.21에서 두 번 모두 정체했다. 두 번째 주행 sim 185.388초에 전진 0.1m/s·회전 -0.00372rad/s 명령, 좌우 바퀴 목표 약 -1.2rad/s였으나 측정 오른쪽 +0.468/왼쪽 -1.876rad/s. 제자리 보정 명령보다 실제 차체 방향 이탈이 먼저이며, 이후 진행 검사(10cm/20 ROS초) 실패로 중단됐다. 도착 판정/다음 주행 시작 조건의 실패가 아니다.
- 태그: 첫 실패 Goal 중 보정 요청 없음. 두 번째 마지막 태그 보정은 sim≈181.02초, 물리 방향 이탈은 ≈184.9초 이후. 태그 보정이 직접 회전을 유발했다는 근거는 없다.
- 미확정: 반복 위치의 물리적 접촉·걸림 또는 구동/물리 응답 이상을 의심하나, 접촉 대상·힘이 기록되지 않아 특정 충돌이나 시뮬 전용 결함으로 확정하지 않는다. 다음 검증은 해당 위치의 접촉 쌍/힘·바퀴 구동 힘을 동시 기록하는 재현 시험이다. 기존 0.313/0.35 성공 시험은 이 위치를 지나지 않아 이번 문제를 검증하지 못했다.
- 실물 영향/복원: 이번 추가는 진단 기록뿐이며 주행 동작 변경 없음. 이 항목 삭제로 문서만 복원 가능. 본 커밋은 누적 통합 작업의 체크포인트이며 수확 실패 해결 완료를 뜻하지 않는다.

## SHARED-NAVIGATION-CODE-20261014 — 공통 구현 한 벌과 변경 가능한 설정

- 승인: 사용자 “똑바로 통합해”와 후속 “같은 코드를 … 동일한 파일”, “설정값은 … 바꿀 수 있어야”, “sim … 전용 파일만” 지시. 초기 편집의 설정 override 금지를 제거했다. 공통/실물/시뮬 연결 변경 범위이며 기존 미커밋 작업을 보존했다.
- 공통 실행: `farm_navigation/configuration.py`의 설정 병합/공통 Nav2 로딩, `harvest_robot/configuration.py`의 수확 기본값 로딩, `farm_tag_localization/{launch_support,ros_capture,detection}.py`의 태그 연결/기록/검출 변환을 양쪽에서 호출한다. sim 태그 구현은 공통 import wrapper만 남긴다. 실물 USB 도구도 공통 태그 ID/크기/검출 override 경로를 사용한다. 수확 태그 구역 신호는 공통 단계 callback으로 전달한다.
- 데이터: `robot/config/navigation/`과 `robot/config/localization/common_observation_model.json`을 한 원본으로 참조한다. 기존 sim/real Nav2 파일은 해당 참조와 환경 데이터, 필요한 `overrides`만 관리한다. 공통 기본값 변경은 양쪽에 반영되며 환경별 수치 변경도 허용한다. BT/기존 모델 경로는 링크로 호환한다. 지도 생성기는 로컬 튜닝값을 삭제하지 않고, 실물 시험 manifest는 참조한 공통 파일까지 기록한다.
- 기본값 영향: 수확 RPP/SimpleGoalChecker 및 끝점 선분연장을 전달 `bf10fcd` 기준으로 정렬했다. 4cm/2.5°·0.10m/s·CLOSED_LOOP·진행20ROS초·Goal300wall초가 공통 기본값이다. 이전 실험 Settling/Stopped 소스는 보존하지만 기본 선택에서 제외했다. 종료 잔차 비차단(D-029)과 예찰 RPP.stateful=false는 유지한다. CPU 물리·휠 PI·센서 교정은 이번에 바꾸지 않았다.
- 검증: 공통4/sim3 패키지 빌드, 주행20·수확90·태그80·sim 통합32·launch9 검사 PASS. 추가 관련 fixture41개 및 경로371개 PASS(일부 시험은 앞 검사와 중복). 별도 real/sim 셸에서 주요9개 모듈의 실제 원본 파일 경로가 동일함을 확인했다. CPU/GUI/RViz/카메라3개/태그ON 전체 실행 결과는 PROJECT_STATE §52와 [검증 JSON](changes/SHARED_NAVIGATION_CODE_20261014.json)에 기록한다.
- 한계/적용: 실물 PiCam 자료 미확보를 configured:false로 명시했고 실제 모터 펌웨어/응답 동등성은 미검증이다. 실물 주행/배포는 하지 않았다. 사용 중인 팔OFF smoke 프로파일도 공통 참조로 갱신했다. 소스/설정 적용에는 launch 재시작이 필요하다. 이번 참조·로더·호출 변경을 함께 역적용해 복원하며 다른 누적 변경은 유지한다. commit/push 없음.


## SIM-REAL-NAVIGATION-AUDIT-20261014 — 추가 수정 전 동등성 감사

- 사용자 실물/시뮬 차이 검증 요청. 운영 코드·설정 수정/재주행 없이 실제 선택 프로파일·공통 호출·전달 이력·최신 실패 로그를 대조했다. [감사 JSON](changes/NAVIGATION_SIM_REAL_AUDIT_20261014.json), PROJECT_STATE §51에 근거·값·한계를 기록했다.
- 공통 구현 사용과 동작 일치를 혼동한 설명을 정정한다. 수확 도착/새 출발/진도/timeout/끝점 추종/속도/smoother 차이, 전달본의 진입·작업 끝점 정책 미반영, 실물 예찰 기본 태그 연결 미완료를 확인했다. 하위 바퀴PI도 공유 구현이 아니며 실물 응답 정합 미검증이다. 필요한 지도·장치 차이로 이 정책 차이를 정당화하지 않는다.
- 최신 실행은 첫 진입Goal에서 회전 지속 후 취소, 태그보정0회. 직전 작업점 도착 수정과 다른 단계이며 이번에 원인 확정/수정 완료로 기록하지 않는다. 기존 각 성공 기록은 유지하되 반복 신뢰성/실물 검증의 증거로 확대하지 않는다.
- 이번 대상은 감사 JSON/현행 문서뿐이며 문서 추가만 역적용 가능하다. 기존 미커밋 작업 보존, commit/push 없음.

## SIM-HARVEST-ARRIVAL-STATE-20261014 — 작업 도착 판정을 실물과 일치

- 사용자 수확0.313 도착 회전 반복 보고 및 기존 원인 확인·조치·CPU 검증 지시에 따른 시뮬 설정 수정. 원본은 SECTION_APPROACH 성공 뒤 WINDOW_MOVE에서 전진0/±0.06rad/s 회전을 지속하다 사용자 취소됐다. 태그 요청 직전 map XY11.34mm→보정 후26.47mm로15mm 도착 범위를 벗어났다.
- 대상: `sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml`의 기본 SimpleGoalChecker.stateful=false→true. RPP의 위치 도착 기억과 완료 판정을 맞춘다. 실물 vicpinky 설정은 이미true이므로 수정하지 않았다. 위치 도착 확인 후 방향 정렬을 마치며 새 Goal은 이력을 초기화한다. 진입 전용 Stopped checker·허용 수치·공통 코드/PID·물성·센서·timeout은 유지한다. 작업·이탈의 기본 checker에 적용되며 출발 차단/자동 뒤돌기 추가 없음.
- 직접 CPU/태그ON/카메라3개/GUI/RViz 시험:0.313→0.35 두 Goal 모두SUCCESS, 두 번째는 재진입 없이SECTION_RESUME→WINDOW_MOVE, 태그 보정11회. 정지 후 map 거리16.20/15.48mm, 방향0.411/1.192°. 예찰 서버는 정차했으며 예찰 미션 재실행·실물·16구역·장시간 반복은 미검증이다.
- 검사: 관련 Python20개 PASS, 설치 SimpleGoalChecker 직접 재생7 assertions PASS, config 빌드/소스·설치 일치. 전후 YAML mapping 차이는 stateful 한 항목뿐이다. [검증 JSON](changes/HARVEST_ARRIVAL_STATE_FIX_20261014.json), PROJECT_STATE §50/D-031 및 `sim/runs/harvest_arrival_fix_20261014/` 참고.
- 실행/복원: 기존 및 시험 런치 종료, CPU 런치 재시작 필요. 종료 중 Isaac SIGTERM/예찰 detector -11은 미션 성공과 별도로 기록했다. 이번 stateful 한 항목/주석만 역적용해 복원하며 다른 미커밋 작업은 보존한다. 문서 갱신, commit/push 없음.

## SIM-SCOUT-PROGRESS-FIX-20261014 — 예찰 도착 상태 고정 수정

- 승인: 사용자 “원인 확인 - 조치 - 보고”. CPU에서105를 재현하고 실물·시뮬 공통 RPP 동작을 최소 수정했다. 대상은 `sim/ros_ws/src/farm_sim_config/config/nav2_scout.yaml`, `robot/config/robots/burger/nav2.yaml`의 RPP.stateful=false 및 공통 `farm_nav2_controller/test/test_settling_controller.cpp`의 대조시험2개다.
- 전후: 한번 XY 범위에 들어가면 밖으로 나가도 회전/전진0 유지 → 현재 위치가 밖이면 경로 추종 재개. CPU 재현은 태그 적용 전에도 발생했다. 따라서 태그만의 오류라는 설명은 하지 않는다. 도착/진행 허용치·물리·PI·태그·수확 프로파일·종료 잔차 비차단 정책은 변경하지 않았다.
- 직접 Isaac 검증: CPU/태그ON/카메라3개/RViz/GUI 동일 조건, 원래 station 배치. 수정 전 첫 관측에서105/ABORTED, 수정 후SEC01 5개 관측 전체SUCCESS/SUCCEEDED 및 태그 보정129회. 전후 각1회이며 실물 배포/주행·전체16구역·장시간 반복은 미실행이다. 수정 후 정지 잔여 위치25.13~40.32mm는 그대로 기록하며 정밀도 인증으로 확대하지 않는다.
- 오프라인: 설치 RPP 직접 회귀 포함 C++12개+관련 Python14개=26개 PASS. 공통 controller/시뮬config 빌드 PASS, 소스/설치config 일치, 수정 전 YAML 대비 RPP 한 항목만 변경 확인. [검증 JSON](changes/SCOUT_PROGRESS_FIX_20261014.json), PROJECT_STATE §49/D-030 및 `sim/runs/scout_progress_fix_20261014/` 참고.
- 적용/복원: 기존 실패 런치와 시험은 종료했다. CPU 런치를 재시작해야 새 설정을 읽는다. 실물 설정 로컬 반영, 실제 장치 검증은 별도다. 두 RPP 설정 추가·신규 시험만 역적용하며 기존 미커밋 변경은 보존한다. commit/push 없음.

## SIM-SCOUT-PROGRESS-20261014 — 예찰 Nav2 105 로그 조사

- 사용자 로그 확인 요청. CPU/태그ON/RVizON 실행의 SEC01 세 번째 목표에서 Nav2 FAILED_TO_MAKE_PROGRESS(105)를 확인했다. 종료 오차 추가 검사 이전의 실패다.
- 약7.4sim초 동안 전진 명령0·실제 위치 변화0.0183mm, map 추정은 목표에서36.64~54.36mm로 도착3cm 밖이었다. 실행 중 RPP.stateful=true와 progress10cm/10초를 읽기 전용 확인했다. 위치 보정 후 RPP의 XY 도착 상태 고정이 추종 재개를 막는 조건이 가장 유력하지만 내부 latch는 직접 기록되지 않았다.
- 예찰은 기존 RPP이며 수확 진입 plugin을 사용하지 않는다. CPU만의 문제/태그 오차/저속 물리 기여는 아직 미분리다. 운영 코드·파라미터 변경, 새 주행/재현 시험은 하지 않았다. 대상은 분석 JSON과 PROJECT_STATE §48뿐이며 [증거](changes/SCOUT_PROGRESS_FAILURE_20261014.json)에 세부값을 남겼다. 문서 변경만 역적용 가능, commit/push 없음.

## SIM-ARRIVAL-GATE-REMOVAL-20261014 — 종료 잔여 오차로 다음 이동을 차단하지 않음

- 요청/승인: 사용자 “어제 작업종료 오차로인해 다음주행 시작조건 막는거 빼라고했잖아”. 이전 추가 오차 검사 유지 판단을 정정한다(D-029, PROJECT_STATE §47).
- 대상/전후: 공통 `farm_navigation/navigator.py`의 정지 후 도착·재측정·진입·이탈 오차 초과 4개 예외를 경고로 바꾼다. 측정값/`accepted=false`는 그대로 기록하고 다음 이동 잠금을 남기지 않는다. Nav2 실패·정지 미확인·TF 오류는 기존대로 실패다. 현재 예찰·수확, 실물·시뮬 공통 경로에 반영한다. 제동 개선·물성·허용 수치와 새 경로 검사는 변경하지 않았다.
- 검사: `sim/tests/test_recorded_arrival_overshoot.py`와 `test_parallel_approach.py`에서 오차 기록·후속 요청·중간 단계 진행 및 실제 실패 대조를 검증한다. CPU 26.82mm 기록에서 실제 수확 단계기/작업 경로 생성기로 다음 전방 30cm Window가 재진입 없이 실행됐다. 같은 이전 목표 재시도와 다음 목표 이동을 구분하며 별도 종단 제어가 필수라는 이전 설명은 철회한다.
- 결과: 기록 재생/평행 접근 11개 + 공통14개 + 수확 단계18개 =43개 PASS, farm_navigation 빌드 및 수정 소스 런타임 import 확인. Isaac/실물 재주행은 미실행이며 과거 실제 실패 결과는 그대로 보존한다. 로그는 `sim/runs/arrival_gate_removal_20261014/`.
- 적용/복원: ROS 런치 재시작 필요. 해당 Navigator 수정 전 백업/이번 diff만 복원하고 다른 미커밋 변경은 유지한다. commit/push 없음.

## SIM-STOPPED-ARRIVAL-20261014 — 공통 진입 정지 제어와 도착 판정 수정

- 요청/승인: 사용자 “아니그래서 어떻게 조치할거야 일단 해결은 해야될거아니야”에 따라 D-027 개선 실행. 시뮬·실물의 같은 공통 주행 제어를 수정하며 물성/PI/최종 허용치는 유지한다. 실제 실물 배포·주행은 미실행이다.
- 변경: 공통 farm_nav2_controller RPP subclass는 기존 경로·충돌 검사 후 최종 XY/yaw 안에서0속도 명령을 내린다. farm_navigation은 Stopped checker 사전검사와 속도 masking 검증을 지원한다. harvest_robot/node.py의 optional approach_goal_checker_id로 진입에만 새 controller/checker를 선택하고 작업·이탈은 기존 설정을 보존한다. sim nav2_harvest.yaml/harvest_task.json, real vicpinky/nav2.yaml/harvest_real.json, farm_bringup 의존성 및 check_runtime.py를 연결했다.
- 호환/검사: 복수 checker의 일반 NavigateToPose/ThroughPoses 호환을 위해 기본 BT의 기존 일반 checker ID만 명시한 환경별 XML4개와 상대경로 해석을 추가했다. sim/tests 및 기존 진입/작업 테스트, 공통 C++ 단위검사를 갱신했다. 기존 default설정 생략 동작은 유지한다.
- 전후: 회전 중 목표각 통과 성공 → 목표 자세 안에서 제동 명령 → 속도까지 검사 → 기존0.8초 정지·최종 pose 검사. 설정만 바꾼 후보는 진입 또는 작업 회전 반복이 재발하여 폐기했다. 좁은 작업 구간에 새로운 XY 재접근/복구 회전을 추가하지 않았다.
- Isaac 직접 검증: 최종 구성 CPU/GPU 각1회 진입 정렬 완료; 전체 HarvestTask 결과는 다음과 같다. cpu_brake_01 전체결과 FAILED: 진입 6.85mm/0.279°, 작업 도착 26.82mm/0.426°; gpu_brake_01 전체결과 SUCCESS: 진입 6.87mm/0.221°, 작업 도착 11.31mm/0.778°. 팔OFF/expected_count0, 원래 카메라·태그·GUI 조건 유지. 후보의 성공·취소·무효 배치 기록도 모두 JSON에 구분 보존한다. [검증 JSON](changes/STOPPED_ARRIVAL_FIX_20261014.json), PROJECT_STATE §46 참고.
- 남은 문제: CPU 작업 지점은 Nav2 종료 뒤26.82mm map 오차로 최종검사가 거절했다. 그 사이 태그 보정도 적용됐으나 요청 변화는진행축각0.3mm수준이어서 전체 원인으로 단정하지 않는다. 안전한 기존 직선 재접근 검사도 목표방향9.777°로 거절하므로 자동 재시도하지 않는다. 진입 과회전과 별도인 작업 종단제어 문제이며 전체 미션 완전 해결로 기록하지 않는다.
- 검증: 관련86개 PASS, 정적 runtime5그룹 PASS, 공통/시뮬5패키지 빌드 PASS. 전체 geometry의 기존 연결선48 subcase 실패는 HEAD 시험에서도 동일하다. 실물 동작·모든 구간·장시간 반복·팔 수확은 미검증이며 목표 범위 밖의 원본 RPP/시뮬 저속 물리 응답 원인을 해결했다고 주장하지 않는다.
- 실물 영향/복원: 로컬 실물 프로파일도 새 공통 package가 필요하므로 실물 아키텍처에서 소스 빌드해야 한다. sim/runs/rotation_fix_20261014/*before 및 before_* 백업/이번 diff로만 복원하고 기존 미커밋 작업은 보존한다. commit/push 없음.

## SIM-ARRIVAL-REGRESSION-20261014 — 공통 주행 검증 방향과 실패 조건 보존

- 요청/범위: 사용자 “그래 그 방향성으로 가야지”. 시뮬 모델 오류와 실물에서도 가능한 공통 제어 실패를 분리하고, 성공을 위한 시뮬 튜닝으로 실패를 가리지 않는 D-027을 기록했다. 운영 코드/설정 변경 없음.
- 변경: `sim/tests/test_recorded_arrival_overshoot.py`가 기존CPU/GPU 성공3·실패3의 실제 도착 좌표를 공통 Navigator 종료 경계에 재생한다. 정지 확인 뒤 같은 시각 pose 사용, 과회전 거절/성공 대조군 유지, 실패 후 새 이동 우회 차단을 확인한다. 기존 증거와 허용치는 그대로다.
- 검증: ROS Jazzy 환경에서 `python3 -m unittest sim.tests.test_recorded_arrival_overshoot -v` 1검사/6기록조건 PASS. I/O를 대체한 오프라인 회귀이며 물리/Nav2 재실행·과회전 수정·실물 검증이 아니다. 회전 공간 검증 없는 공통 자동 재정렬은 도입하지 않았다.
- 실물 영향/복원: 실물·공통 실행 코드 및 USD/PI 변경 없음. 시험 제거만으로 되돌릴 수 있으며 기존 실패 증거·다른 미커밋 변경은 보존한다. 상세 PROJECT_STATE §45. commit/push 없음.

## SIM-ROTATION-ROOT-CAUSE-20261014 — 진입 정렬 과회전 분석

- 구분/요청: 사용자 “6도 이상의 오차 … 원인 분석”. 분석 문서·격리 시험 산출물만 추가. 운영 코드/설정·USD·허용치 변경 없음. 기존 main/62a80ed 미커밋 변경 보존, commit/push 없음.
- 결과: 6~7°는 실제 차체 과회전이며 최종2.865° 허용치 초과를 상위 도착 검사가 정상 차단한다. 저속 구동 응답 저하→시뮬 PI 누적→회전 속도 상승→측정 속도를 따르는 RPP 감속 제한→회전 중 Nav2 순간 도착 판정→제동 중 추가 회전의 흐름을 기존 실패3회에서 확인했다. GPU 실패는 첫 기록된0명령 뒤에도 최대4.77° 더 회전했다. 정확한 물성/접촉 원인은 미확정이며 정지 후 PI 적분 잔류는 아니다.
- 격리 검증: ROS/Nav2 없이−0.06rad/s를8sim초 명령했다. 기본 스테이션−90°에서 CPU23.57°/GPU26.41°, 실패 방향−71.03°에서는 진입 위치CPU0.80°/스테이션CPU0.69° 회전, 두 후자는 PI 적분 상한2.0 도달. 방향에 따른 시뮬 구동 응답 차이를 확인했다. 각1회이며 전체 Nav2 실패 재현 시험은 아니다. PI 제거 시 정상 방향에서도 CPU1.61°/GPU0.09°에 그쳐 단순 제거는 해결책이 아니다. 모든6조건14sim초 계산 완료, app.close 대기로 종료−15, 시험 프로세스 잔류 없음.
- 원인 범위: 명백한 cmd 월드축/로봇축 혼동 없음. 기존6회 정지 map/world yaw 차이≤0.184°, 실패 태그 적용0회. CPU/GPU 선택이나 태그 변경만으로 해결할 근거 없음. 다음은 방향별 바퀴 구동력·접촉력 계측, 시뮬 PI 포화/제동 수정 검증 후 동일 Nav2 반복 시험이다. 허용치를 풀지 않는다.
- 근거/복원: [분석 요약](changes/ROTATION_OVERSHOOT_ANALYSIS_20261014.json), [추적 그래프](changes/ROTATION_OVERSHOOT_20261014.png), `sim/runs/rotation_root_cause_20261014/`. 상세는 `docs/PROJECT_STATE.md` §44. 문서/JSON 검증 완료; 실행 코드 변경이 없어 복원할 운영 변경 없음.

## SIM-DOC-20261002-001 — 인수 검토 및 작업 규칙 기록

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 문서·작업 규칙. 실행 코드·설정 변경 없음 |
| 기준 자료 | 사용자 첨부 `farm_project.zip`, `SUMMARY_인수인계서.md`, 프로젝트 기획·시뮬레이션 파트 문서 |
| 승인 근거 | 이번 사용자 요청: 변경사항 검토, 시뮬 전용 변경의 폴더 분리, 공통 코드 사전 확인 및 변경 기록 |
| 대상 파일 | `AGENTS.md`에 규칙 추가, `sim/AGENTS.md`, 이 문서, `sim/docs/INTEGRATION_REVIEW_20261002.md` 추가 |
| 이유 | 실물 담당자 소스를 기준으로 시뮬 통합을 시작하면서 실물·공통 코드에 대한 영향과 승인 범위를 명확히 하기 위함 |
| 변경 전후 | 기존 구현 합의를 보존하고 시뮬 수정 위치, 공통 변경 승인, 변경 기록 기준을 추가 |
| 실물 영향 | 실행 소스·설정·모델·메시지·실물 자산 변경 없음 |
| 직접 검증 | 기존 오프라인 시험 44개 통과. 두 환경 설정 로드 성공. 시뮬 그래프 128노드/112엣지/16개 약연결 성분, 실물 18노드/40엣지/1개 약연결 성분 확인 |
| 미실행 | ROS 2 빌드·통신, 새 State 흐름 전체 시험, VisionRuntime 시험, YOLO 실행, Isaac Sim 통합, 실물 주행 |
| 복원 | `AGENTS.md`의 이번 추가 절만 제거하고 이번에 추가한 `sim/AGENTS.md`와 문서 2개를 제거. 다른 변경이 누적된 뒤에는 해당 기록의 변경분만 되돌릴 것 |

원본 ZIP SHA-256:

`ca092228082a9e47b6fa79de8878408923f82d9ca9dbfa328811811a65728b24`

공통 실행 코드 수정 승인을 받은 항목: 없음.

## SIM-CONFIG-20261002-002 — 시뮬 설정 실제 분리

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 시뮬 설정·진입점·출력 경로. 공통 ROS 실행 소스 및 실물 설정 변경 없음 |
| 승인 근거 | 사용자 후속 요청: “시뮬레이션 설정은 sim 폴더안에 있어야돼. 명확히 분리해” |
| 승인 범위 해석 | 시뮬 전용 설정 이동, 필요한 기존 경로 참조 갱신. 공통 업무 로직 변경 승인으로 확대하지 않음 |
| 설정 이동 | `robot/config/vision/scout.json` → `sim/ros_ws/src/farm_sim_config/config/scout_vision.json`. 이전 경로의 설정 파일·링크는 제거 |
| 환경 선택 | `scout_survey.json`이 새 영상 설정을 참조. `scout_runtime.yaml`에 시뮬 `rviz_config` 추가 |
| RViz 분리 | `sim/.../farm_sim_config/config/scout.rviz` 추가. `sim/.../farm_sim_runtime/launch/scout.launch.py`에서 공통 bringup과 별도로 선택하여 한 번 실행 |
| 비전 진입점 | `sim/tools/run_scout_vision.py`에서 기본 설정 선택. 기존 루트 스크립트는 인자를 그대로 전달하는 호환 진입점으로 변경 |
| 외부 참조 갱신 | `scripts/run_scout_vision.py`, `tests/test_scout_survey.py`만 시뮬 외부 실행/시험 파일로 변경. 기존 시험은 survey의 `vision_config`를 읽도록 수정 |
| 출력 분리 | 예찰·단독 비전·합성 데이터 기본 출력을 각각 `sim/runs/scout_survey`, `sim/runs/scout_vision`, `sim/runs/scout_dataset`으로 변경 |
| 평가 도구 | `--survey latest`는 시뮬 결과 폴더만 검색. 기존 결과는 명시 경로로 읽을 수 있음 |
| 패키징 | 새 설정·launch는 기존 glob으로 설치. 시뮬 runtime의 실행 의존성만 추가 |
| 실물 영향 | `robot/ros_ws/src/`, 실물 설정·모델·센서 값·메시지·공통 알고리즘은 유지. 기존 실물 launch와 기존 결과 데이터도 유지 |
| 검증 | 기존 오프라인 44개 통과. sim/real 환경 로드 성공. 수치·ID·모델 선택·그래프 참조 보존. 공통 ROS/실물 설정/모델 124개 파일 원본 동일. 실행 객체를 대체한 launch 구성 4조건·외부 설정 거절 4조건, 비전 함수만 대체한 신·구 CLI 인자 전달 6조건 통과. 변경 Python 문법 및 패키지 XML 확인 |
| 미실행 | ROS 2 빌드 및 실제 launch, Isaac·YOLO·실물 실행 |
| 복원 | 적용 전 설정·진입점·시험·sim 패키지 파일로 되돌리고 이번 추가 파일만 제거. 기존 비전 설정은 `sim/runs/config_backups/`에서 복원 가능. 새 결과 폴더는 삭제하지 않음 |

추가/수정 파일의 상세 위치와 실행 명령은 `sim/README.md`를 참고한다. 기존 `INTEGRATION_REVIEW_20261002.md`는 변경 전 인수 검토 기록이며 현재 설정 위치는 이 변경 항목이 우선한다.

## 다음 변경 기록 양식

```text
변경 ID / 일자:
구분: 시뮬 전용 / 공통 / 실물 / 문서
상태: 제안 / 승인 대기 / 승인 완료 / 적용 완료 / 검증 완료
기준 버전: Git commit 또는 전달 파일 식별값
대상 파일:
변경 이유와 재현 조건:
구체적인 변경안 / 변경 전후 동작:
실물 영향:
시뮬 영향:
사용자 승인 일자·요청 내용·승인 범위:
적용 결과:
검증 명령·결과·미실행 범위:
시험 로그 / 보고서 경로:
되돌리는 방법:
```


## SIM-DATA-20261002-003 — 연결 경로·로봇 station 복원

- 승인 근거: 사용자 요청 “어제 업데이트한 경로 데이터 yaml … 경로끼리 연결, 각 로봇 station … sim 파트 데이터 다시”.
- 이유: 인수본에는 과거의 분리 그래프와 FOV 자동 관측 설정이 남아 있어 이후 업데이트한 연결·station·고정 촬영점 데이터가 누락돼 있었다.
- 대상: sim의 task.yaml, 연결 원본/역할별 GeoJSON, 원본 점유 지도, scout_survey/scout_patrol/scout_runtime/scout.json, 재생성·검증 도구, 문서와 작업 규칙. 상세 목록은 패치 ZIP에 포함된 파일 목록 기준.
- 출처: farm_scout_harvest_count_v0.8.5.zip의 최신 연결 데이터. 운송/선별장 용도는 기존 sim_route_design_v1 설계. 보관본 자체와 실제 git 커밋 비교는 구분한다.
- 변경 전후: 16개 분리 성분 → 연결 원본 227노드/516방향 엣지. BED_01~16/FOV 자동 관측 → SEC01~16/고정 관측점 80개. 예찰·수확 station 좌표·방향 복원, 운송/선별장 설계 좌표 복원(방향 미정).
- 호환: 공통 로더가 role 메타데이터를 읽지 않아 역할별 파생 그래프를 생성. 원본 베드 경계는 scout 파생 그래프의 기존 엣지를 분할해 보존. 공통 코드 복제나 변경 없음.
- 실물 영향: 이번 변경은 전부 sim/ 내부. 공통 코드·실물 설정·모델·USD 자산 변경 없음.
- 검증: 현재 공통 로더와 기하 계산/순찰 로더에서 16구역·80관측점 유효, 371개 역할별 경로 계산 통과. 원본 그래프/지도 동일, 원본 구역·베드·예찰/수확 station 동일, 227개 원본 노드의 지도 free 픽셀 확인.
- 미실행/유지: ROS/Isaac/colcon 미실행. station 자동 배치, AMCL station 초기화, FollowPath 전환, 수확/운송 실행부 연결은 미적용. 기존 navigate_to_pose 유지. 자동 station 복귀 없음.
- 복원: 패치 적용 전 백업 사용. 이번에 추가된 파일은 제거하고 기존 파일만 백업본으로 돌린다. sim/runs 결과는 보존한다.
- 보고: sim/docs/ROUTE_RESTORE_20261002.md 및 ROUTE_RESTORE_VALIDATION_20261002.json.


## SIM-RUNTIME-20261002-004 — Isaac 실행 대상 station 자동 배치

- 승인 근거: 사용자 “robot의 station 자동 배치는 isaacsim 실행용 코드에 포함”. FollowPath 설명 요청은 모드 전환 지시로 해석하지 않았다.
- 대상: sim runtime의 station_spawn.py/run_sim.py/scout.launch.py, scout.json, task.yaml, station_spawn.json, nav2_scout.yaml, 재생성·검증 도구, sim/tests/test_station_spawn.py 및 sim 문서.
- 변경 전후: USD 저장 위치에서 시작 → task 기반 station JSON의 예찰 station XY/yaw로 물리 시작 전 배치. 기존 body 높이·센서 상대 위치 유지. USD session layer만 사용하며 원본 저장 없음.
- 위치추정: AMCL 초기 pose를 같은 station 원본에서 생성. launch에서 서로 다르면 오류. 물리 reset 후 배치 검증. 주행 중 정답 pose 주입 없음.
- 범위: 현재 단일 예찰 런타임에 적용. 수확/운송 실행부 생성·구동 및 FollowPath 전환은 미적용. 공통 코드·실물 설정·USD 자산 변경 없음.
- 검증: 좌표/설정 시험 6개, launch 구성 4개 및 AMCL 불일치 거절 검사 통과. 경로 371개 검사 통과. nav2는 초기 pose 외 설정 값 유지.
- 한계: ROS/Isaac/USD API 실실행, 물리 구동, colcon 빌드 미검증.
- 복원: 이전 sim 파일 백업을 복원하고 새 station_spawn.py/json 및 시험 파일을 제거한다. sim/runs 결과는 보존. 배치만 끄려면 station_spawn.enabled=false와 실제 시작 위치의 AMCL 초기 pose를 함께 맞춘다.
- 상세: sim/docs/STATION_SPAWN_20261002.md.


## SIM-NAV-20261002-005 — 실물과 동일한 FollowPath/RPP 설정

- 승인 근거: 사용자 “시뮬설정도 실제랑 동일하게 세팅해”.
- 대상: sim의 scout_runtime.yaml, nav2_scout.yaml, task.yaml, 재생성된 scout_survey.json, 문서·작업 규칙. 공통 코드/실물 파일 변경 없음.
- 전후: navigate_to_pose → follow_path, controller_id FollowPath → RPP, goal checker general_goal_checker → goal_checker. 실물과 navigation 파라미터 동일(base_frame 제외).
- 제어 설정: 인수본 실물의 controller_server·velocity_smoother 값을 적용(use_sim_time/odom_topic 제외). controller 10Hz, RPP 0.15m/s·lookahead 0.15m, goal 0.03m/0.05236rad, progress 0.1m/10s. local/global inflation도 RPP 비용 모델에 맞게 실물과 동일하게 설정.
- 유지: 시뮬 지도·graph·관측점·station, TF·센서·장치·시간, AMCL station 초기 pose, 로봇 반경/센서 costmap 레이어. 모든 Nav2 값을 무조건 복사한 것은 아님.
- 실행 동작: 공통 RouteGraph가 연결 그래프 경로를 계산하고 Nav2 FollowPath 액션에 controller_id=RPP로 전달한다. 교통 제어·자동 복귀·도킹 추가 없음.
- 검증: 양 환경 설정 로드, 주행값/선택 controller/goal/progress ID 일치, 공통 goal checker 검사 통과. 371개 경로 계산 및 station 시험 6개 통과. 이번 수정이 sim 내부로 한정됨을 파일 해시로 확인.
- 한계: ROS/Isaac 실주행·colcon 빌드 미실행. 인수본 설정과 동일하다는 의미이며 담당자의 현장 실행값은 별도 확인 대상.
- 원복: 적용 전 시뮬 설정 백업 복원. 주행 모드 한 줄만 바꾸면 제어 튜닝까지 원복되지는 않는다.
- 상세: FOLLOWPATH_ALIGNMENT_20261002.md, FOLLOWPATH_VALIDATION_20261002.json.


## LAUNCH-SPLIT-20261002-006 — 로봇/Isaac/RViz 독립 실행 및 시뮬 전체 실행

- 승인: 사용자 “그럼 그렇게 수정해 … 시뮬레이션용 전체실행 런치 … 만들어줘 … 실행 절차 … 작성”. 공통 launch 변경을 포함한 실행 구조 분리 승인으로 적용.
- 공통 대상: farm_bringup의 scout.launch.py, scout_navigation.launch.py, 새 rviz.launch.py, tests/test_launch_composition.py, 공통 실행 안내/루트 README/AGENTS.
- 시뮬 대상: sim 런타임의 scout/scout_devices launch, 새 isaac/all launch, setup.py의 launch 파일 설치 패턴, 안내 문서.
- 변경 전후: 로봇 launch에서 Isaac/RViz를 함께 시작 → 로봇 단독 기본은 장치+Nav2+예찰 서버, Isaac과 RViz는 독립 실행. 시뮬 all은 독립 launch 세 개를 조합.
- 실물 영향: 기존 survey=true 실행은 장치·Nav2·서버 구성 유지. RViz는 별도 실행. survey/navigation 기본값이 true로 변경됨. start_isaac/rviz=true는 명시적으로 이관 안내 오류. navigation 전용 sim 실행도 환경 프로파일을 선택하도록 보완.
- 유지: 실물 설정·공통 미션/FSM/주행 계산/메시지·USD 및 station 배치 구현 변경 없음. 수확/운송/관제 구현을 임의 추가하지 않음.
- 검증: launch 기록 객체 기반 9개 시험 통과. 시뮬 전체의 Isaac/어댑터/예찰서버/RViz 각 1개, 독립 실행 경계, 실물 장치 포함 및 Nav2/서버, 모드별 RViz 시간/TF, 옵션 및 잘못된 구형 옵션 거절 확인. 직접 ROS/Isaac 구동·실물·colcon 빌드는 미실행.
- 실행 안내: docs/RUN_GUIDE_20261002.md. 실물 담당자 변경표, 각 장비 실행, 시뮬 전체/세 터미널 실행, 시험 관제, 종료·재시작 범위, 다중 로봇 미구현 항목을 명시.
- 복원: 적용 전 공통/시뮬 launch와 setup.py 백업 복원. 새 launch·구성 시험·안내 파일 제거. 실행 결과는 삭제하지 않음.


## SIM-LAUNCH-20261002-007 — 활성 robot_venv의 비전 Python 자동 선택

- 사용자 확인: 비전 의존성이 robot_venv에 설치되어 있어 별도 vision_python 인자가 불필요해야 함.
- 대상: sim 런타임의 launch_environment.py, all/scout launch. 공통/실물 코드 변경 없음.
- 전후: 인자/환경변수 미지정 시 빈 경로 → FARM_VISION_PYTHON 우선, 없으면 VIRTUAL_ENV/bin/python, 활성 venv도 없으면 launch Python 사용. 명시적인 vision_python 인자는 계속 우선함.
- venv 심볼릭 링크는 resolve하지 않아 가상환경을 유지. 잘못된 활성 venv 경로는 명시적 오류.
- 검증: 우선순위 및 경로 선택 검사, 기존 launch 구성 시험 9개 통과. 실제 ROS/Isaac/추론 실행은 미검증.
- 원복: 이전 all/scout launch 복원 후 새 launch_environment.py 제거.

## HARVEST-SIM-20261002-008 — 수확 이동 Action 및 시뮬 bringup

- 상태: 사용자 승인 후 적용, 오프라인 검증 완료. ROS/Isaac 실실행 미검증.
- 승인 근거: 수확 코드/bringup·sim/real 구분·sim 내부 작성 요청과 후속 “action 추가해. 진행해도 돼”, “그렇게 result 보내면 됨”. 사전 제안한 공통 인터페이스 추가와 이동 완료/수확량 0 계약을 적용했다.
- 공통 대상: farm_interfaces/action/HarvestTask.action 신규, CMakeLists.txt 등록만. 기존 HarvestTask.msg 및 주행/예찰/실물 설정 유지.
- 시뮬 대상: farm_sim_harvest 신규 서버/미션/통신/상태/평가; runtime harvest launch/fleet 실행/all 조합/clock relay; harvest 자산/설정/지도 선택/RViz; 데이터 생성·검증·시험·안내.
- 전후: 수확 실행부 없음 → 같은 공통 Navigator와 harvest 역할 graph로 window XY/yaw 도착 후 SUCCESS/harvested_count=0. 팔 작업 없음. expected와 실제 USD pose의 과실 박스 판정은 별도 로그. real 장치 연결은 미구현 오류, 실물 가상 구동 대체 없음.
- 출처: 제공된 v0.8.5 수확 물리 자산/주행좌표 변환/시뮬 센서 및 GT 수집 부분만 이식. 예전 서버·관제·공통 로직은 복원하지 않음. 실제 팔 도달성 대신 기존 임시 박스이며 인수 후 보정 필요.
- 실행 영향: harvest=true일 때 두 로봇 포트·TF 분리 및 독립 clock 하나. scout 단독 기본 동작 유지. fleet scout profile이 중복 clock을 막음. 새 Action 사용자는 robot workspace 재빌드 필요.
- 검증: sim 단위/구성 20개, 기존 launch 9개, 기존 경로 371개, 수확 엣지 내부 목표 경로 48개 통과. 공통 변경 2개 외 모든 변경 sim 내부 확인. ROS/colcon/Isaac/실물 미실행.
- 수정 안내·실물 인수 경계·로그·원복: HARVEST_RUN_GUIDE_20261002.md. 적용 전 파일 백업 복원 및 신규 파일 제거 후 재빌드, sim/runs 결과 보존.

## HARVEST-COMMON-20261002-009 — 수확 서버의 공통 위치 정정

- 승인: 수확 서버와 bringup을 공통 위치로 옮기고 평가만 sim에 남기자는 구체적 제안에 대한 사용자 “그래임마 정신차려”.
- 이유: 008에서 수확 서버 전체를 sim 전용 패키지에 배치한 것은 동일 서버를 sim/real에서 공유하는 기존 합의에 맞지 않았다. 008의 서버 위치 설명은 이 항목으로 대체한다.
- 공통 변경: robot/ros_ws/src/harvest_robot 신규(Node/Communication/Mission/StateController/계약), farm_bringup/launch/harvest.launch.py 실제 조합 및 package.xml 의존성. 기존 farm_navigation과 HarvestTask 계약 유지.
- sim 변경: farm_sim_harvest는 audit_node/evaluation만 유지. 작업 설정과 평가 설정 분리, fleet 평가 경로 갱신, sim harvest launch가 공통 launch+평가를 조합. 이전 sim 서버 소스 5개 제거용 백업 이관 도구 추가.
- 전후: sim 서버가 평가 함수를 호출 → 공통 서버는 Action/주행 처리와 환경 독립 task_events 진단 발행만 담당, sim 평가 노드는 비동기 구독하여 비교 로그 생성. 서버에서 sim import/Isaac snapshot 접근/평가 대기 제거.
- 실물 영향: real 설정과 외부 드라이버가 있으면 devices=false로 같은 서버 실행 가능. 미구현 실물 장치 기본 분기는 오류. 실물 맵/드라이버/팔 작업을 가짜 구현하지 않음. 공통 workspace 재빌드 필요.
- 검증: 오프라인 31개, 기존 경로 371개, 수확 내부 좌표 경로 48개 통과. sim/real 동일 서버, 시간 선택, 평가 분리, 중복 launch 없음 확인. 실제 ROS/Isaac/colcon/실물 미실행.
- 전달/원복: HARVEST_COMMON_MIGRATION_20261002.md. 이전 수확 패치를 대체하는 합본 패치, 이관 도구로 옛 서버만 백업 후 제거. 결과 로그는 보존.

## SIM-FLEET-20261002-010 — Isaac fleet 진입점 누락 수정

- 증상: 17:09 실행 로그에서 Isaac Python이 시작 직후 exit 0으로 종료, OnProcessExit에 의해 모든 ROS 노드가 SIGINT로 종료됨.
- 원인: run_fleet.py에 main 함수는 있으나 직접 실행 시 호출하는 __main__ 진입점 누락. 기존 문법/launch 구성 검사는 함수 호출 여부를 검증하지 못했음.
- 대상: sim runtime/run_fleet.py, sim/tests/test_fleet_entrypoint.py, 이 변경 기록. 공통/실물 파일 변경 없음.
- 변경: 직접 실행 시 main() 호출 추가. 종료 연동은 그대로 유지.
- 검증: 수정 전 --help가 출력 없이 exit 0인 현상 재현. 수정 후 실제 subprocess --help에서 옵션 출력, 필수 인자 누락 시 exit 2 확인(2개 통과). Isaac 물리 구동은 해당 환경이 없어 미검증.
- 적용: 패치 압축 해제 후 sim workspace의 farm_sim_runtime 재빌드, 환경 다시 로드 후 기존 전체 실행 명령 사용.
- 원복: run_fleet.py 마지막 __main__ 블록과 새 시험 파일을 되돌림. 결과 데이터는 변경하지 않음.

## SIM-TF-20261002-011 — 카메라 없는 수확 로봇 상태 패킷 수락

- 증상: HarvestTask는 수락됐으나 harvest_01/base_footprint TF가 없어 NAVIGATION_FAILED.
- 원인: ros_adapter.valid가 고정 TF 3개를 강제. fleet 런타임은 카메라 없는 harvest에 base/link·lidar TF 2개를 전송하여 모든 패킷이 거절됐음. odom·scan·TF 발행에 도달하지 못함.
- 변경: camera.enabled에 따라 2/3개를 선택하고 설정의 부모/자식 프레임 쌍과 일치하는지 검사. 공통 서버·실물·Nav2 변경 없음.
- 검증: 실제 valid 메서드를 ROS 없이 실행, harvest 2개/scout 3개 수락 및 누락/다른 로봇 프레임 거절 4개 통과. ROS/Isaac 직접 실행 미검증.
- 적용: farm_sim_devices 재빌드 및 전체 launch 재시작. 확인: harvest_01/odom → harvest_01/base_footprint TF 출력.
- 복원: 이전 ros_adapter.py 복원 후 시뮬 패키지 재빌드. 시험 로그 데이터 유지.

## DRIVE-DIAG-20261006-012 — 수확 무응답 구동 진단

- 근거: cmd_vel 0.12m/s, wheel odom 약 0, 로봇 정지 및 Failed to make progress. 전달 경로/물리 구동 중 원인 미확정.
- 범위: sim runtime/run_fleet.py와 신규 drive_diagnostics.py. 공통/실물/게인/구동 제한 변경 없음. 앞선 main 호출 수정 포함.
- 변경: ROS→Isaac 수신 패킷과 gate 수락/거절 누적, 실제 적용 cmd, 공통 kinematics로 계산한 관절 목표, 관절 실측 속도/인덱스, 실제 pose를 1Hz로 기록. 적용된 USD 바퀴 drive 설정 기록.
- 산출: sim/runs/drive_diagnostics/<세션>/<robot_id>.jsonl 및 <robot_id>_setup.json. 목표 속도는 apply_action에 전달한 입력으로 계산한 값이며 PhysX 내부 target readback은 아님.
- 정적 검사: 제공 자산의 바퀴 stiffness=0, damping=625. 별도 자산의 검사이며 사용자 실행 중인 scene 적용 상태의 증명은 아님.
- 검증: 실제 common wheel_targets를 사용한 목표 rad/s, 수락/거절 카운터, JSON 출력/1Hz 제한, USD 관절 추출 검사 통과. Isaac 물리 실행 미검증. 근본 원인 수정 완료가 아닌 진단 계측 패치.
- 원복: 적용 전 run_fleet.py 복원, drive_diagnostics.py 제거 후 runtime 재빌드. 기록은 보존.



## DOC-HANDOFF-20261006-015 — Codex·ChatGPT 최신 인수인계 문서 패키지

- 일자: 2026-10-06 (Asia/Seoul).
- 구분: 문서·작업 지침. 실행 코드·환경 설정·ROS 정의·USD·모델 변경 없음.
- 승인 근거: 사용자 요청 “필요한 인수인계용 파일 최신버전으로 작성해서 전달해줘”. 문서 작성·전달 범위이며 공통 실행 코드 변경 승인으로 확대하지 않음.
- 기준 코드: `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`, Robot3FinalProject/main의 main 브랜치.
- 상태: 다운로드 적용용 문서 패키지 작성. 사용자 PC 적용·GitHub 반영은 별도 확인 필요.
- 대상: `AGENTS.md`, `README.md`, `docs/CODEX_HANDOFF.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF_SOURCES_20261006.json`, `sim/docs/RUN_GUIDE_20261006.md`, 이 변경 이력.
- 변경 이유: 초기 토마토 기획과 10/2 예찰 인수 기록만으로는 10/6 수확·통신·다중 로봇 실행 상태를 전달하기 어려움. 코드·문서·사용자 확인의 시점을 구분하기 위함.
- 변경 내용: 최신 구조·메시지·로그·실행 인자·미구현 영역 정리. 루트 AGENTS의 복원 전 그래프 설명과 README의 수확 미구현 포괄 설명을 정정. 인수인계 읽기·갱신 규칙과 ChatGPT 프로젝트에 추가할 지침을 문서화.
- 현재 규칙 유지: 시뮬 전용 작업은 sim 내부, 공통 코드 변경 승인, sim 정답 평가와 실제 제어 분리, 코드 및 사용자 미커밋 변경 보존.
- 직접 검증: 기준 커밋의 관련 소스·설정 정적 대조; 8베드/16Section/80관측점, 원본/예찰/수확 그래프의 노드·엣지·약연결성 계산; 최종 패키지의 링크·경로·필드·Bash 구문·ZIP 내용 검사. 상세 결과는 전달 시 검증 기록 기준.
- 미실행: 사용자 PC의 git 상태, colcon 빌드, ROS 네트워크·관제 연동, Isaac 물리 실행, 실물 실행. 과거 시험 횟수를 이번 재실행 결과로 쓰지 않음.
- 실물 영향: 실행 동작 변경 없음. 새 세션에서 갱신된 문서 확인 절차가 적용됨.
- 되돌리기: 적용 전 문서 백업과 비교하여 이번 문서 변경만 복원. 이번에 새로 추가된 문서의 제거 여부는 이후 편집 유무를 확인한 뒤 결정. 실행 코드·데이터를 되돌릴 이유는 없음.
- 관련 과거 기록: 캐스터 보정은 `sim/docs/changes/CASTER-FIX-20261006-013.md`, 통신규약은 `docs/changes/PROTOCOL-20261006-014.md`에 별도로 존재한다. 여기에서 해당 변경을 새로 적용한 것으로 기록하지 않는다.


## DOC-STATE-20261006-016 — 로컬 코드·문서·기존 로그 대조

- 일자/구분: 2026-10-06 KST / 문서. 적용 완료, 정적 검토 완료.
- 승인 근거: 사용자 요청 “인수인계서, 변경 이력, docs/changes와 현재 코드를 대조해서 docs/PROJECT_STATE.md를 작성해 … 이번에는 문서만 작업해”.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e 및 시작 시 미커밋 인계 문서. fetch 후 origin/main과 0/0. 기존 AGENTS/README/이력 수정, 미추적 인계 파일과 백업 보존.
- 대상: docs/PROJECT_STATE.md, 이 변경 이력. 코드·설정·시험·모델·USD 변경 없음.
- 전후: 인계 패키지의 원격 기준 요약 → 실제 로컬 Git 상태, 실행 요약, 구형 설명과 코드의 차이, 저장된 수확 성공 2건/실패 6건의 증거·한계 보강. 로컬 장면 USD는 포인터가 아닌 바이너리 객체임을 정정.
- 실물/시뮬 영향: 실행 동작 변경 없음. 최신 프로토콜 E2E 검증 완료로 확대하지 않음.
- 직접 검증: Git fetch·차이 조회, 관련 문서/launch/메시지/미션 정적 대조, GeoJSON 규모·약연결성 및 16Section/80관측점/8베드 계산, 기존 survey/audit JSON 열람, USD 헤더·크기·캐스터 패치 체크섬 비교, 문서 링크·기존 파일 보존 검사.
- 미실행: 기존 단위/경로 검사의 재실행, colcon/ROS/CDR/Isaac/실물/최신 프로토콜 E2E.
- 로그: 새 런타임 로그 없음. 기존 증거 위치와 다음 통합 시험 조건은 PROJECT_STATE §11·§13.
- 복원: 문서의 이번 보강과 이 항목만 이전 내용과 비교해 복원. 시작 시 미커밋 변경은 유지. commit/push 미실행, 원격 미반영.

## ROBOTARM-REVIEW-20261006-017 — 로봇팔 인수 자료 검토 및 반영 승인 대기

- 일자/구분: 2026-10-06 KST / 문서 검토. 실행 코드·설정·USD 반영은 승인 대기.
- 승인 근거: 사용자 “main에 robotarm 폴더에 … 확인해보고 sim에 반영할 내용 정리해서 나한테 확인받고 적용해”. 이번에는 검토서 작성만 수행하고 적용 전 확인 절차를 따른다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e. 이번 fetch 후 origin/main과 0/0. 기존 미커밋 문서·백업 및 robotarm 원본 4개 보존.
- 대상: 신규 `sim/docs/ROBOTARM_INTEGRATION_REVIEW_20261006.md`, 이 변경 이력. 실행 파일·공통/실물 코드·기존 설정·자산 변경 없음.
- 전후: 인수 명세 4개만 존재 → 현재 sim과의 차이, 필수 추가 인수, 단계별 대상 파일·영향·검증·승인 경계를 문서화.
- 주요 발견: 정책 4개/run.json/profile/runtime/RL 소스/전용 자산/검증 원본 미수신. 오른팔 Teacher와 기존 왼팔 Window/audit 불일치. 현재 60Hz와 Teacher 실효 480Hz/정책20Hz 차이. 활성 농장 과실 288개 하위에 rigid body/mass/collision API 없음. 현재 과실 크기와 root 의미 대조 및 박스 바닥 물리 준비 필요.
- 직접 검증: 문서/JSON/현행 코드 정적 대조, 후보18개 범위·HOME 거리·18cm 간격 조합 계산(최대3개), 파일 목록/SHA256, Git 상태·fetch·커밋 차이, 설치 pxr를 사용한 USD 정적 TF/기하/물리 API 검사.
- 미실행: 정책 추론, Isaac SimulationApp/PhysX, ROS/colcon, 실제 수확 및 실물 시험. 문서의 적재3/6은 담당자 과거 기록이며 이번 검증 결과가 아님.
- 제안: A sim 인수 설정·검사 도구 → 원본 수령 후 B 독립9g 평가 → C 농장/오른팔 기하 정합 → 별도 공통 승인 후 D 실제 팔 작업 연결. 이번 승인 요청은 A이며 B~D 동작을 자동 승인받은 것으로 취급하지 않음.
- 실물/시뮬 영향: 문서만 추가되어 실행 영향 없음. Teacher 내부 상태 입력은 독립 평가 범위로 한정하며 기존 공통 제어 정답 주입 금지를 유지.
- 결과/다음 작업: 상세 검토서의 A 범위를 사용자에게 제시. 승인 후 설정·검사 도구를 구현하고 누락 원본 확보 후 물리 재현 진행. 새 런타임 로그 없음. commit/push 미실행.
- 복원: 이번 검토서와 이 항목만 되돌린다. 기존 이력과 시작 시 미커밋 변경을 보존한다.

## ROBOTARM-RECEIPT-20261006-018 — 전체 전달 묶음 수령 및 이식 문제 검토

- 일자/구분: 2026-10-06 KST / 수령 검사·문서. 사용자 요청 “파일 받아서 robotarm 폴더안에 넣어놨어 파악해봐”. 앞선 전체 자료 수신 후 일괄 작업 요청에 따라 017의 A 단독 반영은 보류.
- 기준: 농장 main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e, 이번 fetch 후 origin/main과0/0. 전달 소스 base abe9e13357e1be549500712b62c5582649d444ab + 현재 수정본.
- 대상: 신규 `sim/docs/ROBOTARM_BUNDLE_RECEIPT_20261006.md`, 기존 검토서의 최신 문서 연결, `docs/PROJECT_STATE.md` §14, 이 이력. `sim/runs/robotarm/received_20261006_143434/`에 검토용 원본 추출 및 검사 JSON2개. 실행 소스·정책·기존 자산·프로파일은 수정하지 않음.
- 전후: 문서4개만 수령 → 소스·정책·자산·환경·YOLO·평가 원본 확보 및 무결성 확인. 새 평가/농장 통합 완료는 아님.
- 직접 검증: archive SHA256, 안전한 상대경로/일반파일 검사, manifest2148 및 정책4/run.json 해시 일치, 기존4개 파일 동일, 미수신LFS 포인터0. USD/URDF 참조·박스 바닥·팔/차체/캐스터 정적 대조, 환경metadata 비교, 과거episode JSON 집계, 동작코드 분석.
- 발견: prepare 경로 치환 뒤 converter asset hash가 달라져 USD 재생성 경로 발생. 복귀는12×1/480s이나 제어·dwell은50ms 사용. 전달 current USD는 고정차체 평가용, 농장 주행 USD 통째 교체 불가. 비전 환경 일부 버전 차이. 상세는 수령 검토서.
- 미실행: prepare/캐시변환/설치/정책로딩/Isaac·ROS·실물·학습. 원본3/6 성공은 과거 기록이며 수신PC 결과가 아님.
- 실물/시뮬 영향: 문서·검토용 추출만 수행, 현재 운영 동작 영향 없음. source 원본/기존 미커밋 문서·백업 보존. commit/push 없음.
- 후속: 이식·비전환경·복귀시간 보완을 포함해 독립9g 재현 및 농장 통합 범위를 확정. 공통 업무 변경은 기존 구체안 승인 절차 유지.
- 복원: 이번 문서 항목만 비교 복원. 원본 archive/기존 자료를 삭제하지 않으며 검토용 추출본은 운영에서 참조하지 않음.

## ROBOTARM-PHYSICS-20261006-019 — 농장 과실·오른팔 물리 및 수확 목표 좌표 적용

- 일자/구분: 2026-10-06 KST / sim 코드·설정·독립 자산·시험·문서. 구현 및 GPU 기초 물리/진입점 시험 완료, 정책 파지·적재와 실제 Nav2 주행은 미실행.
- 승인 근거: 사용자 “전달받은 파일들 기반으로 아이작심에 적용 … 농장 맵 … 물성치 … 오른쪽 팔 … 예찰로봇 좌표 … 오른쪽 암 기준 … 그것부터 작업”. 추가 선택 “Teacher 규격으로 통일”. 017/018의 검토 대기는 이 sim 1단계에 한해 구현 요청으로 대체했다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e와 기존 미커밋 변경. fetch 후 origin/main과 동일. 받은 전체 묶음 및 공통/실물 실행 파일은 보존했다.
- 과실: `sim/assets/fruit/teacher_9g/`, `fruit_asset_setup.py`, `fruit_attachment.py`, `stem_physics.py`, 생성 도구. 농장288개를70mm폭/75mm높이·9g로 통일하고 마찰/감쇠/접촉·줄기 response5·40ms 지속 분리를 적용했다. 기존 ID·색·위치·회전 보존. 선속도3m/s·각속도20deg/s를 source runtime까지 대조해 적용. 받은 runs 폴더에 대한 운영 의존 없음.
- 오른팔: `robotarm_asset_setup.py`, `sim/assets/robots/harvest_physics/`.6축 힘 drive·그리퍼 접촉·HOME·박스 바닥4타일. 주행용 USD를 교체하지 않고 기존 바퀴/캐스터/왼팔/rigidbody/전체 articulation 물성은 보존했다. 고정차체 Teacher와 전체 solver/self-collision이 같은 환경이라고 주장하지 않는다.
- 좌표: `task.yaml`, 생성 `scout_survey.json`/`harvest_audit.json`, `rebuild_route_data.py`, `scout_vision.json`.16구역 오른팔 mount `[.19,.185,.713]`, 작업중심 `[.19,.5,.838]` 및 크롭 높이를 동기화. `harvest_runtime.yaml` 연결한계.09m/도착.02m·.05rad, `nav2_harvest.yaml` 내부허용.015m·.04rad. 원본 graph·베드 좌표 변경 없음.
- 실행: `robotarm_physics.json`, scout/scout_fleet/harvest.json, `harvest_physics.py`, run_sim/run_fleet, isaac.launch.480Hz 물리 한 tick마다 외력을 갱신하며60Hz 렌더를 별도 호출. 원본 USD 저장 없이 session layer에서 적용. 단독 runner도 실제 project_root를 받는다. 실행별 setup/물리 분리 로그를 저장하고 정책·수확 성공으로 사용하지 않는다.
- 직접 검증: 관련 단위54개+USD 정적7개=61개 통과(skip0), 원본 줄기 Torch와256개 상태 수치 대조,371개 경로,48개 오른팔 Goal과 정적 map 연결선, sim3패키지 colcon 빌드. GPU RTX4070SUPER/Isaac5.1에서288과실2초 자연이탈0, 선택 과실3N 외력으로40ms 이상 지속 후 분리·0.6초 낙하를 확인. 실제 fleet 진입점2초에서288결합 유지, RGB-D29프레임, 로봇별 상태60개. 상세값과 명령은 `ROBOTARM_PHYSICS_20261006.md`.
- 중간 문제: sandbox CUDA 접근 실패는 GPU 권한 환경에서 재시험. fast_shutdown 기본값이 결과 기록 전 프로세스를 끝내는 문제는 정상 종료/종료 전 보고서 기록으로 수정. 최초 낙하0.2초 검사는 분리 직후 상승속도 때문에 실패하여 초기속도/궤적을 기록하고0.6초 관측으로 보완했다. 최종시험은 누락된 과실 속도 제한까지 적용한 후 다시 통과. 중간 JSON 보존.
- 남은 차이/미실행: 실제 Nav2 정밀 정지·동적 장애물/footprint 검사, 전체 예찰→수확 E2E, 정책4개 독립 재현/20Hz 추론·파지·박스 적재, 실물 시험. 원본 농장 빈 visual 참조와 종료 UI extension 경고는 보고서에 구분했다. 공통 수확 Action은 현재 이동+수확0 계약 유지.
- 문서: 신규 `sim/docs/ROBOTARM_PHYSICS_20261006.md`, RUN_GUIDE 최신 절, PROJECT_STATE §15, DECISIONS D-013/D-014 및 이력 갱신. 실물 소스·설정·모델·공통 업무/메시지 변경 없음.
- 로그: `sim/runs/robotarm/physics_smoke_gpu_20261006/result.json`, 같은 이름 `.log`, `fleet_physics_smoke_20261006.log`, `asset_setup_static_final_20261006.log`, `physics/98d899878bda4638a1aa82bbaa51f46b/`.
- 종료 보완: 정상 app.close 후에도 Kit 스레드가 남는 현상을 확인해 CLI에서 파일·앱 정리와 출력 flush 후 검사 결과의 종료코드로 종료한다. 이전 시험 중 결과 기록을 마치고 남은 프로세스4개만 종료했다. 보완 후 물리 검사와 fleet 진입점을 재실행해 각각 종료코드0을 확인했다. 물리/장치 검증 성공과 종료 문제가 있었던 중간 실행을 구분한다.
- 복원: 신규 물리 프로파일 enabled=false로 물리 override를 임시 비활성화할 수 있다(480Hz와 좌표 변경은 별도). 전체 복원은 이번 sim 실행/설정 변경만 비교해 되돌리고 task 원본 기준으로 생성 설정을 함께 재생성한다. 기존 캐스터 패치·인계 문서·사용자 변경을 전체 reset하지 않는다. 소스 농장 USD는 변경하지 않았으므로 복구 저장이 필요 없다. commit/push 미실행, 원격 미반영.

## ROBOTARM-VERIFY-20261006-020 — 인장력 비교 검사 및 커밋·푸시 요청

- 승인: 사용자 “테스트하고 커밋푸쉬 … 정상적용 확인 … 어느정도 인장력 … 강화학습 환경을 적용한거야?”.019 구현과 관련 문서를 테스트 후 게시한다. 별도 AGENTS/README 등 기존 수정, 수신 archive·백업은 작업 트리에 보존한다.
- 대상: `check_harvest_physics.py`에0.1N 유지1초/무외력 회복0.5초 비교·GUI 카메라·실제COM/관성 및 초기tick 기록 추가. `stem_physics.py`/`fruit_attachment.py`에 힘 clamp 전후 및 분리 조건 진단 추가, 줄기 회귀1개 추가. 물리 수식·계수·판정·공통 코드는 변경하지 않는다.
- 검증:62개 테스트(skip0),371개 경로,sim3패키지 빌드 통과. GPU15항목/종료코드0,288과실 유지→0.1N 유지→3N 실제 분리·0.6초간0.90448m 하강 확인. 원본 USD와 주행 구성 보존.
- 중요한 중간 관측:0.5N·1초 유지 예상은 실패했다.116.7ms 뒤 인장축32.32mm, 원시0.51955N, 후크조건41.667ms로 분리됐다. 전달 수식의 거리 분리 조건이며 단순 힘 임계값 실패가 아니다. 별도1kg 무중력 GPU 시험에서 두 외력 호출은 합산됨을 확인했다. 실패 JSON을 보존하고, 물성을 바꾸지 않고 유지 확인 하중을0.1N으로 명시했다.
- 문서/증거: `ROBOTARM_PHYSICS_20261006.md` §10, PROJECT_STATE §16, `sim/docs/changes/ROBOTARM_PHYSICS_VALIDATION_20261006.json`. 원본 로그 `sim/runs/robotarm/precommit_20261006/`. 최초 격리 빌드의 underlay 의존경로 누락은 기존 install을 지정한 최종3패키지 빌드로 해결했으며 실패/성공 로그 모두 보존.
- 경계: 받은9g 평가 환경을 적용했으며 원 체크포인트의35g 학습조건 전체 재현·학습정책 적용·실물 파괴력 측정으로 해석하지 않는다. 정밀Nav2 이동·정책 파지·적재는 미실행.
- 복원:019 물성은 유지하고 이번 진단/검사 도구 추가만 별도로 되돌릴 수 있다. 기존 사용자 파일과 받은 원본은 삭제하지 않는다. commit/push는 이번 사용자 요청으로 승인됐으며 실행 결과는 최종Git 원격 일치로 확인한다.


## ROBOTARM-PERFORMANCE-20261006-021 — GUI 검사 종료와 CPU 물리 병목 분석

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 성능 계측·문서 정정. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd.
- 대상:`ROBOTARM_PHYSICS_20261006.md` §11 및 CCD 설명, `docs/PROJECT_STATE.md` §17, 이 이력. 임시 계측 도구/JSON/로그는 ignored `sim/runs/robotarm/perf_20261006/`와 `cpu_microbenchmark_20261006/`에 저장했다.
- 전후:GUI 검사 종료와12FPS 원인 미확인 →사용자 JSON15 checks 통과/유한 검사 후 의도된 종료 확인. 현재 물리/진단 생략/과실 고정480Hz/과실 고정60Hz의 GUI 비교를 각각 실행해8.30/8.27/22.22/89.52FPS 측정. 마지막60Hz 대조군은 초기 reset 영향으로 카메라Z 약8.05mm 차이가 있고 이전 운영 버전 성능이 아니다.
- 결론:현재 조건 frame120.44ms 중 CPU 물리 실행/결과 동기화100.63ms(83.5%). runtimeCPU/GPUDynamicsfalse, GPU평균11.9%.288개 동적 과실과 전역480Hz가 부하를 늘렸으며 추가 상태 진단만 제거해서 해결되지 않는다.
- 정정:실행 시sceneCCD=true를 확인했다. 기존 “scene CCD false 유지” 설명은 잘못됐다. 설정 자체를 변경하지 않고 Teacher와의 차이를 기록했다.
- 검증:4개 GUI 비교 정상 종료, 물리1tick/렌더 시간 불변 검사 및 대조군288kinematic/변위0 확인. 준비30/측정120프레임씩. 순수 NumPy 수식288개0.495ms/tick. 초기 SDK getter 계측 실패 기록 보존 후 임시 도구만 수정했다. 전체fleet/정책 수확/장기 성능·최적화 적용은 미실행.
- 실물/시뮬 영향:운영 코드·자산·물성·공통/실물 실행 변경 없음. 분석용 고정/60Hz는 별도 프로세스 메모리/session 안에서만 적용하고 종료했다. 이번 문서는 미커밋·원격 미반영.
- 복원:이번 문서 항목만 비교 복원한다. 기존 사용자 변경 및 원본 JSON/전달 묶음은 보존한다.

## ROBOTARM-ADAPTIVE-20261006-022 — 수확 활동에 따른 물리 주기·주변 과실 선택

- 일자/구분:2026-10-06 KST / 사용자 승인 sim 구현·실제GPU/ROS 검증. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 이후 미커밋. 승인 문구 “물리주기도 동적으로 … 수확중 수확로봇 인근 …”. 공통 업무 코드 변경 없음.
- 대상: runtime `physics_schedule.py`, `harvest_regions.py`, `harvest_physics.py`, `run_fleet.py`, `run_sim.py`; devices `fruit_attachment.py`, `harvest_activity.py`, `ros_adapter.py`, `package.xml`; config `robotarm_physics.json`, `harvest.json`; 새 검사도구 `check_adaptive_harvest.py`와 단위시험4개. 상세문서 `ADAPTIVE_HARVEST_PHYSICS_20261006.md`, 기존 물리/실행문서 연결, PROJECT_STATE §18, DECISIONS D-015, 검증JSON 갱신.
- 전후: 전체288개 항상동적/480Hz → 유휴60Hz·부착과실 고정, 수확중480Hz·오른팔 실제장착점0.8m/유지1.0m 영역합집합만 활성. 분리과실은 고정하지 않고0.6초 정지 후60Hz/움직이면480Hz. 부착과실의 움직임/분리타이머 동안 freeze 유예. 현재pose·앵커·기준자세·분리상태 보존. kinematic중CCDoff, 활성화시 원복·PhysX flush로 전환 순서 보장.
- 시간/동시성:60Hz 프레임당1~8물리tick과 렌더1회. 매tick 힘갱신, reset없이dt변경, 실제누적시각으로odom/clock/센서. 활동은 로봇별세션/seq/유효기간 검사, 다른 활동이 남으면 고주기 유지. 미래복수수확기 영역합산은 단위시험이며 현재 실제GPU는 예찰+수확각1대.
- 연결 경계:공통이동완료를 팔작업으로 추정하지 않는다. 내부set_activity와 sim전용Bool heartbeat를 추가했으며 실제팔정책/공통FSM 연결은 후속이다. 과실정답은 물리영역선택에만 사용하고 목표/수확성공으로 전달하지 않는다.
- 직접검증:단위/USD107개(skip0),sim3패키지빌드,실제ROS bridge13항목. GPU선택물리19항목/종료0,기존전체288개기준15항목/종료0. 근거리3개활성,3N분리41.667ms,0.20714m하강,60Hz복귀. 원본USD SHA256불변. fleet6초2개조건에서clock360/상태각180/RGB-D89/라이다10Hz/카메라pose시각검사 통과.
- 관측된 한계:동일0.08m/s 개방루프명령에서 고정60Hz와60→480→60Hz의 최종world위치 약2.6cm차이. 시계정상과 궤적동일성은 별개다. 바퀴drive/명령을 보정해 차이를 감추지 않았다. 짧은headless측정 실시간배율0.725대0.483. 이전GUI성능과 직접비교 불가.
- 중간문제:시험초기mount가 과실반경밖이어서 최초검사실패, 실제장착점기준 초기배치로 시험만 수정한뒤 통과. 초기kinematic+CCD경고는 batchflag전환순서로 해결. 실패로그 보존. 기존visual참조/Kit종료UI경고와 검사실패를 구분한다.
- 실물영향/미실행:실물·공통·원본자산 수정없음. 정책파지/적재·Nav2폐루프주행정밀도·다수수확기/운송·전체E2E·실물 미검증. 같은Scene고주기는 여전히 전역CPU비용이다. 독립세트주기는 별도인스턴스가 필요하다.
- 로그:`sim/runs/robotarm/adaptive_20261006/`, 각 결과의physics_log_directory. 검증요약:`sim/docs/changes/ADAPTIVE_PHYSICS_VALIDATION_20261006.json`. 문서/코드 로컬적용·sim패키지빌드 완료, 커밋/푸시 미실행.
- 복원:`adaptive.enabled=false`로 전체과실/기준480Hz모드 복귀. 영역처리유지/주기고정시험은idle_hz와harvest_hz를 동일값으로 설정. 전체코드복원은 이번파일만 비교복원하며 기존사용자문서/인수자료/백업을 보존한다. USD는 저장하지 않았다.

## TEACHER-INTEGRATION-20261006-023 — 도착 후 순차 수확 실현성·공통 변경 검토

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 구현 검토·승인 제안. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 및022 미커밋 구현. 요청은 도착 후Teacher에과실좌표제공→시도별물리성공/실패Feedback→대상처리후Result. 사용자선택으로빨강·노랑각1회/일반실패다음진행/녹색및차체추가이동제외 확정.
- 대상: `TEACHER_HARVEST_INTEGRATION_REVIEW_20261006.md`, `proposals/HARVEST_ARM_COMMON_CONTRACT_20261006.md`와 `.proposal` 스키마3개, `changes/TEACHER_INTEGRATION_REVIEW_20261006.json`, PROJECT_STATE §19, DECISIONS D-016/O-008, 이 이력. 검사스크립트/원본JSON은ignored sim/runs/robotarm/policy_integration_review_20261006 아래다.
- 직접검증: 정책4개/각run.json SHA256, 현재설치공식ActorCritic strict load·정규화·합성82D입력5개→6D유한/결정적출력. 전달/농장팔·박스 FK9자세/9link 강체변환 최대오차2.22e-16,실제USD정적8link 최대5.96e-7. 농장288root간격/자세/현재planner기하 정적비교. ROS Jazzy rosidl parser로 제안3종문법통과. 물리수확성공/타입생성·통신을시험한것은아니다.
- 주요발견: 좌표만이아닌82D+접촉/진행상태 필요. 원본환경은scene/physics소유하므로farmWorld어댑터 필요. 첫실패batch종료/실패후assign거절/미수집분리과실복귀거절과복귀25ms/계산50ms불일치를보완해야한다.0.8m물리영역과Teacher도달범위는별개,주변장애물은정책관측에서제외됨. 농장root최소132.77mm,18cm미만34쌍/66개.
- 제안: 공통harvest_robot가후보순서/누적결과/취소/Window종료를소유, sim이후보발견/단일과실Teacher/실제결과·정지·다음시도준비ACK를제공. 외부HarvestTask필드유지,내부HarvestCandidate/GetHarvestCandidates/PickFruit추가. 대상파일/실물영향/검증안을제시하고사전확인질문을보냈으며아직미승인이다. 부분실패를수량으로반환하면서대상처리완료SUCCESS로보는안도확인대기.
- 승인/실물영향: sim Teacher 정답입력은이번사용자의명시지시로허용,예찰/실물입력으로확대하지않는다. 공통/실물실행소스·기존모델·자산·물성·운영설정 수정없음. 새ROS타입등록/빌드/팔GPU실행/전체수확E2E미실행. 추가정책파일은필수누락아니며담당자에게검증된연속도달범위·실패복구·독립추론접점이있으면요청하는문구만작성했다. 실제외부메시지는전송하지않았다.
- 다음: 공통범위/부분성과종결의미 확인 후 독립9g재현→농장단일과실→실패후순차진행→Action·취소→동시Nav2검증. 기존022의주행응답차이를해결완료로취급하지않는다.
- 복원:이번검토문서/제안/상태기록만비교복원한다. 기존미커밋022/사용자AGENTS·README/받은원본은보존한다. 이번검토는미커밋·원격미반영이다.


## SIM-COMMON-20261006-024 — 최소 공통 연결과 sim Teacher 실행

| 항목 | 내용 |
|---|---|
| 기준 | main/1666a23 이후 미커밋. 앞선 동적 물리·검토 및 사용자 변경 보존 |
| 승인 | 사용자 “대부분 로봇팔 구동 코드는 sim 전용 … 공통에서 도착하자마자 result를 날리면 그 부분을 sim 코드에 연결”. 앞선 빨강/노랑 각1회·Teacher규격·좌표정답사용 승인 유지 |
| 공통 대상 | harvest_robot의 node/mission/communication/contract 및 새 arm_client. 상세는 docs/changes/HARVEST_ARM_HOOK_20261006.md |
| sim 대상 | teacher_policy/state/device/_teacher_vendor, arm_session/arm_ros, ros_adapter/package/setup, run_fleet/physics_schedule, harvest/harvest_task/teacher_policy 설정, 정책4개+run자산, 시험/도구/문서 |
| 변경 전후 | 도착 후 수확0 즉시반환→시뮬 내부Action 실제완료·정지대기. 지역활성→후보확정→20Hz정책→물리복귀/안착→누적결과. 메시지신규타입/공통Window실행기 제안은 미채택 |
| 성과 의미 | 정상 후보전체처리SUCCESS, 실제안착·실패수량 별도. 취소는정지확인, 미확인은차단. 과실/관절teleport·재부착·가짜성공없음 |
| 실물 영향 | 실물설정/모델/장치·공통주행/비전·외부메시지 불변. legacy도착전용설정 유지. 현재새팔장치는sim만 선택 |
| 직접 검증 | 178단위/USD 중176PASS/ROS2skip, 별도실ROS/UDP2PASS,4패키지build. 최종Isaac fixture 실제정책/복귀/실패수량/정지/정상종료 PASS. 원본FK·CPU재생 대조. 자세한 숫자와 취소 결과는 실행보고서 |
| 성능 한계 | 실제농장3과실 적재0. ENTRYtimeout/bad_detach 후복귀. 적재성능PASS와구분. 다중과실/기존적재실물보존/Nav2전체E2E/실물/카메라/다수로봇 미검증 |
| 중간 실패 | SDK sensor/filter길이오류 수정, testerSIGINT/짧은Kit종료대기-11 수정. 최종프레임종료+60초대기 code0확인, 중간실패로그보존 |
| 결과 | sim/runs/robotarm/teacher_integration_20261006, teacher/<session>/<job>; 요약 sim/docs/changes/TEACHER_RUNTIME_VALIDATION_20261006.json |
| 되돌림 | 실행중지후 harvest_task completion_policy=ARRIVAL_ONLY_NO_HARVEST, harvest runtime.harvest_arm.enabled=false. 소스복원은 이번변경만, 다른미커밋변경초기화금지. 동적물리별도설정유지 |

[실행·검증 보고서](TEACHER_HARVEST_RUNTIME_20261006.md). 커밋·푸시는 수행하지 않았다.

## SIM-TEMP-CONTROL-20261007-025 — 임시 예찰→수확 관제 CLI

- 사용자 요청: 나중에 삭제할 사이클 확인용 관제를 sim 안에 추가. 공통/실물 소스 변경 없음.
- 추가: `sim/tools/temporary_control.py`, `sim/tests/test_temporary_control.py`. 실행 가이드 §7 및 PROJECT_STATE §21 갱신.
- Section 입력→ScoutArea 성공 최종 목록→원본 HarvestTask 순차 요청→수량 출력. 실패/취소 부분 예찰 목록 제외, 중복 ID 사전 거절, 수확 작업 실패 시 큐 중단. Ctrl+C 자기 Goal 취소/종료 대기, 정지 미확인 차단. JSONL은 sim/runs/temporary_control.
- 직접 검사: ROS 설치 메시지를 이용한 단위검사 6개, --help 로딩, diff 공백 검사. 실제 네트워크 Action/Isaac/Nav2 전체 사이클은 이번에 실행하지 않음.
- 기준 main/1666a23 이후 미커밋. 기존 미커밋 변경 보존. 커밋·푸시 없음.
- 되돌림: 위 임시 도구/시험과 가이드 §7 제거. launch와 로봇 실행은 변경하지 않았음.

## SIM-RVIZ-20261007-026 — FollowPath 추종 경로 표시

- 사용자 요청에 따라 sim의 scout_harvest/scout/harvest.rviz에 로봇별 `/received_global_plan` Path를 추가했다. 예찰 초록, 수확 주황, 선폭0.045m·높이0.12m. 기존 planner `/plan` 표시는 비활성화하고 이름으로 구분했다.
- 현재 GeoJSON 경로는 FollowPath로 직접 전달되므로 planner `/plan`만 구독하면 추종 경로가 표시되지 않을 수 있다. RPP가 발행하는 변환/가지치기 구간을 표시하며 전체 원본 Goal Path나 전체 그래프와 동일하다고 설명하지 않는다. 기존 route_markers 표시는 유지한다.
- 공통/실물/주행 코드·주기·도착 허용오차 변경 없음. 설치된 RPP 라이브러리의 토픽 이름과 YAML3개 설정을 확인했다. 실제 RViz 화면·이동 중 수신 검증은 미실행.
- RViz만 설정 재로드하면 적용. 되돌림은 이번 Path 항목 제거와 기존 plan Enabled 복원. 기준1666a23 이후 미커밋, 커밋·푸시 없음.

## SIM-NAV-20261007-027 — 베드 평행 접근 분석·공통 변경 승인 대기

- 사용자 베드 앞 정렬/평행 주행 요청.16개Section 모두 정차선과 기존 수확 graph가60mm 불일치함을 정적 확인. 실제6개 수확로그 최종60mm 구간이 목표 yaw와90도 차이. geometry.json에 저장.
- sim/docs/proposals/HARVEST_PARALLEL_APPROACH_20261007.md에 sim 수확 graph 정렬과 공통 선택적 진입/최종방향 검사·이미 도착 처리의 파일/영향/검증안을 작성. 실행 코드/설정/graph 미변경, 공통 승인 대기.
- 실제 새 주행 미실행. 기존 변경 보존, 커밋·푸시 없음. 되돌림은 이번 제안/분석 기록만 제거.

## SIM-COMMON-20261007-028 — 수확 평행 접근 적용

- 사용자 “수정해”로027 제안 승인. common farm_navigation3파일+parallel_approach.py, sim 생성기/task/survey/harvest graph/runtime/Nav2 설정 변경. 상세 docs/changes/HARVEST_PARALLEL_APPROACH_20261007.md.
- 주행선60mm 정렬, 넓은 기존 진입부 도착/정렬 후 평행 주행, 다른 구간 이동 전 정방향 이탈. 이미 도착 시 정지 재검사. 좁은 구간 복구 조건 불충족은 실패. 실물 옵션기본false/설정 불변.
- 신규7검사/371경로/build PASS. 기존도착검사9PASS/1구형메시지fixtureERROR. 실제 신규 Isaac 주행/회전충돌 여유 미검증. 사용자 실행 중인 프로세스는 재시작하지 않았음.
- 재시작 후 station에서 첫 Goal 재전송 필요. 기준1666a23 이후 미커밋·원격 미반영. 복원은 이번변경만 대상으로 한다.

## SIM-DRIVE-20261007-029 — 수확 회전·제동 보정

- 사용자 진입 정렬0.2486rad 실패 및 “해결해” 요청. sim base_sim/wheel_servo, harvest.json, nav2_harvest.yaml, harvest_runtime.yaml, drive_diagnostics, 물리 시험도구/단위시험/보고서 수정. 공통·실물 소스 및 원본USD 불변.
- 엔코더 각도차 속도 PI 보정과 정지시 적분 초기화·반대방향 제동. 수확만 활성화, 저속정렬0.06rad/s/각가속0.1/yaw gate0.01; 최종0.05rad 도착 기준 유지. 느린회전 대응 progress120/goal600초.
- 실제 Isaac 기존추가회전0.2534rad 재현. 최종 양방향 저속제동 추가회전0.00319/0.01317rad, 목표각도 후정지 오차0.00510/0.00932rad PASS/code0. 신규servo4+평행7검사/371경로/3패키지build PASS. Nav2 전체 경로·관제E2E·480Hz 동시주행 미실행.
- 비교시험 gain/solver/휴면 설정은 최종코드에서 제거. 중간시험 snapshot 공유 충돌 발견 후 별도 출력으로 수정. 해당 실패 및 중지한 비정상종료는 PASS 제외. 운영 snapshot 기반 평가가 시험 중 섞였을 가능성은 상세보고서에 기록.
- 상세 sim/docs/HARVEST_BRAKING_20261007.md, 결과 changes/HARVEST_BRAKING_VALIDATION_20261007.json. 사용자 운영프로세스 재시작은 하지 않았다. 적용은 all launch 재시작. 원복은 servo설정 제거 및 이번 속도/대기설정 복원. 미커밋·푸시 없음.

## SIM-NAV-20261007-030 — 실제 Nav2 코너 회전 시작 실패 보정

- 사용자18:06실패로그 직접 확인: controller_server Failed to make progress. 구동로그539072...에서첫코너전제자리 각명령약±.005rad/s. 이전 일정.06rad/s시험은 Nav2피드백결합 검증이 아니었다.
- sim nav2_harvest.yaml의 RPP.max_angular_accel만.10→1.2. 정렬속도.06/도착기준/PI/충돌검사 유지. 실제 전체Nav2 재검증 미실행. 설정생성일치/371경로검사 PASS.
- 실행중은 ros2 param set으로 적용가능. 사용자프로세스에는 자동 명령을 보내지 않았다. 원복은각가속도.10이나 기존정지문제재현가능. 미커밋·원격미반영.

## SIM-HARVEST-UI-20261008-031 — 배치·480Hz 수확 시험 패널

- 일자/기준: 2026-10-08 KST, main/7d9ae40ec8e0d0bebf0e0552f8a6ee85ddfc9bc3 이후 미커밋. 시작 Git 상태 clean. 원격 재조회·커밋·푸시 없음.
- 승인 근거: 사용자 “로봇팔 480hz 물리 연산 기준 … UI … 배치 버튼(수확가능한 열매가 있는 무작위 적정 위치) … 수확 버튼(480hz 전환, 인근 파프리카 물리)”. 시뮬 전용 시험 범위다.
- 파일: tools/harvest_test_ui.py; runtime harvest_test_placement.py/harvest_test_ui.py/run_fleet.py; devices arm_session.py/teacher_device.py의 읽기 전용 상태·장착점 조회; tests/test_harvest_test_{placement,ui,ui_launcher}.py; HARVEST_TEST_UI_20261008.md, RUN_GUIDE, PROJECT_STATE, 이 이력.
- 전후: 고정 fixture/CLI 위주 → 실제 Isaac GUI의 Place robot/Harvest/Stop 버튼으로 반복 관찰 가능. 기존 정차선/측정 팔 장착/Teacher 범위/원본 바닥지도 footprint 검사 후 미시도 부착 빨강·노랑 후보가 있는 배치를 선택한다. 차체 전체의 시험용 순간 배치이며 Nav2 성공으로 기록하지 않는다.
- 실행: python3 sim/tools/harvest_test_ui.py. 단독 수확 장치·사용 가능한 별도 UDP 포트·snapshot/로그 생성. ROS/빌드 불필요, 외부 UDP 제어 무시. 원본 fleet/지도/USD/Teacher/물성 보존. 공통·실물 코드 변경 없음.
- 물리/제어: 기존 ArmSession/Teacher/HarvestPhysics/AdaptivePhysicsTicks 재사용. 실제 정지/HOME/후보 재확인, 60→480→안정후60Hz, 주변 활성·20Hz 정책·실제 성공수량 유지. 활동 중 배치/중복 수확 차단. 적재 후 차체만 순간이동하거나 취소 후 비HOME 상태로 재배치하지 않는다.
- 직접 검증: 관련75검사 PASS(skip0); 새 배치10/UI13/실행기8 포함. Isaac5.1 GUI/RTX4070SUPER seed713 SEC10 Bed01/Pepper0017 yellow: 정책400회, 주변5/288 활성, 실제복귀/정지확인 및480→60Hz·활성0, 종료0. 처리SUCCESS지만 실제 적재0/실패1(target_timeout). 수확성능 개선 PASS가 아니다.
- 화면 검증: 최초 ReviewCamera 선택/한글 글리프 문제를 발견했다. Perspective를 명시 선택해 작업 팔과 과실/바구니를 보여주고 패널은 영문으로 제공한다. 최종 GUI 재실행·창 캡처에서 카메라/버튼/단계/480Hz/활성5개 표시 확인. UI 창 닫기 버튼을 제거하고 전체 Isaac 종료로 정리, timeline reset은 프레임 시작에서 감지한다.
- 로그/보고: sim/runs/harvest_test_ui/validation_20261008/{result.json,unittest.log,isaac.log,final_gui.png,final_gui_run.json}; 연결된 physics/teacher 경로는 result.json. 최종 GUI는 직접 조작하도록 실행 상태로 남겼다.
- 미검증/다음: 사용자 수동 클릭·다양한 seed의 실제 성공률·동시 운영 시뮬·Nav2 포함 E2E는 미검증. 적정 배치의 근거리/바닥 검사는 팔 IK/모든 동적 장애물 회피 인증이 아니다. 다음은 사용자가 버튼으로 반복 관찰하고 기존 Teacher 농장 성능을 별도 개선하는 일이다.
- 되돌림: 독립 도구/패널/기하/시험 추가 파일, run_fleet 선택 연결과 devices 읽기 API 및 문서 항목만 비교 복원한다. 전체 reset 금지. 배포 패치는 변경 파일만 sim/runs/harvest_test_ui/harvest_test_ui_20261008.tar.gz, 적용 명령은 실행 가이드에 기록했다.

## SIM-PHYSICS-INSPECT-20261008-032 — 충돌 메뉴·과실 물리 관찰

- 사용자 요청: Show By Type에 없는 Physics collision 표시 추가, 중력/connector 연결과 랜덤 회전 유지 여부 확인. 031 미커밋 변경을 보존하고 추가. 기준main/7d9ae40, 이번 원격 조회·커밋·푸시 없음.
- 대상: runtime 신규 harvest_physics_inspector.py 및 run_fleet/run_sim/harvest_test_ui; devices fruit_attachment 진단 snapshot/teacher_device 읽기 접촉 API; inspector 신규4검사/UI 추가2검사/접촉 추가1검사; 물리 진단 가이드·기존 UI가이드·PROJECT_STATE·이력.
- 전후: PhysX GUI 확장 미활성/수확 때만 확인 → GUI 실행에서 공식 omni.physx.ui 활성화, Show By Type > Physics > Colliders 메뉴와 패널 Hide/Selected/All 제공. Physics only 관찰은 팔정책 없이 기존 주변영역480Hz를 사용한다. 전역물성/원본USD/정책/실물·공통 코드는 변경하지 않았다.
- 계측: 선택 과실의 active/kinematic/gravity/collider flag, 초기 PhysX질량, 실제 pose/속도·root dz·tip 변위·회전각, 이전 tick 적용 줄기 힘, SDK 선택과실별 손가락 접촉력. mg는 Scene중력×질량 계산값임을 명시. 앵커/꼭지/COM/중력 표시만 추가하며 물리 joint를 생성하지 않는다.
- 발견: 현재 connector와 과실의 자유회전 native joint가 아닌 world 고정 앵커 spring + 초기 랜덤 quaternion 복원 토크다. 유휴부착과실은 kinematic. 중력이 작동해도 수직으로 완전히 정렬되지 않는 이유이며 성공0의 단일 원인을 확정하지 않는다.
- 직접검증: 99개 실행98PASS/1USD미설치skip/실패0. 실제GUI seed713 Bed01/Pepper0017 yellow, 팔정책 없이8초480Hz/주변5개: root하강10.788mm, 회전8.360°, 남은COM-꼭지기울기35.099°, mgZ -0.088290N/적용줄기Fz +0.088290N. collider1/1 convexDecomposition, 안정후60Hz/활성0, 종료0. 새GUI 재실행에서 와이어/표시와 선택과실별접촉0/0 확인. 이번 직접 수확접촉/파지 성공 검증은 아니다.
- 로그: sim/runs/harvest_test_ui/physics_inspection_20261008/{result.json,unittest.log,gui.png,final_gui.png}; 실행별 physics_inspection.jsonl. 최종 진단창은 열어두고 기존 사용자시험창/로그는 건드리지 않았다.
- 다음/한계: Harvest 중 실제집게 접촉력과 충돌형상 대조; 자유진자 connector 모델이 필요하면 별도 물리 모델 설계/Teacher 영향검증. 이번에 angular_k 완화/자세 초기화/가짜 성공은 하지 않았다.
- 복원: 032의 inspector/관찰 토글/읽기 API/GUI 확장 활성화와 해당 문서 항목만 비교 복원한다. 031 및 사용자 변경은 유지한다. 패치는 변경 파일만 포함, 적용 명령은 UI 가이드와 동일하다.

## SIM-TEACHER-DIAGNOSTIC-20261008-033 — 로봇암팀 요청 재현·회신 로그

- 승인/기준: 사용자 “robotarm/SIM_TEAM_TEACHER_DIAGNOSTIC_REQUEST 확인 … 자료 보고 회신 로그 확보”. main/7d9ae40 이후031/032 및 사용자 미커밋 변경을 보존했다. 공통·실물 코드/운영 설정·정책·물성·원본 robotarm 자료 변경 없음.
- 대상: sim teacher_policy.py에 기본off forward hook 계측; 신규 runtime teacher_diagnostics.py; run_fleet/check_teacher_harvest 선택적 --teacher-diagnostic-trace 연결; 신규 test_teacher_diagnostic_trace.py; 회신 문서·PROJECT_STATE·이 이력. 산출물은 sim/runs/robotarm/receiver_diagnostic_20261008.
- 전후: 기존 sample/최종action 위주 로그 → 실제 원본/시간보정/정규화82D와 전문가 raw action, 후처리/clip/최종6D, 상태 플래그, 실제 관절 target buffer·시뮬/벽시계·물리step·dt·초기/복귀/정지 연속 기록 및 USD/PhysX 설정. 추가추론/정규화 재학습 없음. USD 자동계산·무제한 Infinity는 최종계측에서 문자열로 저장하며 초기 노랑 원본은 보존하고 portable사본 추가.
- 전달본 직접 확인: 최초143434 TAR hash7b33...일치; 새해제본2148개검사 후 cache경로보정. 정책4개+run.json·전달평가소스불변. prepare/cache차이12파일은diff로보존.
- 실제 GPU 독립진단: 받은 무카메라 어댑터·전달실행기로 red182/yellow183각5회. 성공3+4/실패2+1, 두프로세스0종료. 송신10개trace1069tick가 SHA256까지일치. 카메라/YOLO포함원본스크립트E2E는미실행.
- 실제 GPU 농장: 기존headless fixture 노랑400POLICY timeout, 빨강42POLICY bad_detach, 실제적재0/2; 두job복귀/정지확인·종료0. 정책dt=.050000002608s, 각24physics step=480Hz. 원본관측/명령/PhysX전달 각19검사통과. taskSUCCESS/검증passed와수확성공을분리.
- 발견: 빨강양손접촉3.754/3.982N 있으나 파지확인0.05s<0.25s, 총변위46.790mm·지속41.667ms 이탈(인장0N), 정상파지전분리. 노랑최소거리74.99mm/양측접촉없음. farmUSD자기충돌false·solver32/1 vs전달소스true·12/4, 초기과실랜덤회전/고정차체차이. 단일원인으로확정하거나이번에수정하지않음.
- 검증: 실제가중치등Teacher/ArmSession60개+fleet entrypoint2개PASS, skip0; 새로운계측11개포함. 추가추론없이action/target·normalizer불변검사. diff --check/구문검사 및 회신manifest검증.
- 오류/한계: GUI2회는Teacher/recorder생성전World.__init__.render nativeOmniGraph SIGSEGV(-11). startup_error 로그별도보존, 성공/수확실패분모제외. 이번viewport영상미확보. 동일초기조건farm대조·Nav2·실물미실행.
- 회신: sim/docs/TEACHER_DIAGNOSTIC_REPLY_20261008.md, TAR+SHA256+MANIFEST. 원본stdout/trace/결과·설정·모델계약·관련source포함,checkpoint/RGB-D/전체해제본제외. 발송·커밋·푸시·원격재조회없음.
- 복원: 진단 플래그를 생략하면 기존제어경로다. 추가계측/CLI연결/시험·문서만비교복원하며031/032·사용자변경은유지한다. 다음은 담당자와같은q/목표pose/TF/threshold조건으로최초관측/action차이와solver·접촉영향을분리하는비교다.

## 2026-10-08 — AprilTag 태그 배치와 수확 PCWEB400 가상 카메라

- 구분/승인: 사용자 직접 요청의 sim bed 배치·수확 카메라/bringup 연결·공용 코드 인수 확인. 후속 답변으로 각 면100~114 반복/구간ID와 함께 식별 확정. 기준main/450bf5f, 기존 미커밋 수확 작업 보존.
- 대상: `assets/apriltag/`, 수확URDF, `farm_sim_config/config/{apriltag_layout,apriltag_map,harvest,scout,scout_fleet}.json`, 런타임`apriltag_scene.py` 및`run_sim/run_fleet`, 장치`camera_sim/camera_ros/ros_adapter`, generator·USD/렌더검증도구, 관련시험·상태/결정/실행문서.
- 전후: 태그없음/수확camera.disabled → session layer16벽240개(15원본반복), 수확측면optical센서 및RGB/CameraInfo발행. 기존공통bringup의sim장치선택으로연결해공통소스변경불필요. 실제웹캠depth없음. 예찰센서장착·경로·원본USD·실물설정은유지.
- 검증:19PASS,USD벽범위/크기/TF검사PASS,실제IsaacID104렌더검출/공유메모리전달PASS,3패키지build/371경로PASS. 첫Kit종료지연으로해당시험만정리, 최종렌더결과저장후종료timeout124. 최종반복IDUSD검사재실행. 전체DDS·이동검출/보정·실물미시험. [상세](APRILTAG_INTEGRATION_20261008.md),로그`sim/runs/apriltag_20261008/`.
- 코드인수: 로컬공용코드에AprilTag검출/보정없음. [요청서](APRILTAG_NAVIGATION_REQUEST_20261008.md)작성,발송없음. 공통수정승인대상diff는이번작업에없으며후속소스인수후검토한다.
- 실물영향: 없음. 실물harvest장치bringup은여전히미구현. 카메라장착은실측기반추정이며정밀실물검증완료가아님.
- 복원: 장치JSON의apriltag_map제거/harvest.camera.enabled=false후재시작,URDF추가광학링크/조인트제거. 기존미커밋수확변경을통째로되돌리지않는다. 미커밋·원격미반영.

## SIM-PEPPER-ROTATION-20261008-035 — 수확 비교용 랜덤 기울기 0도

- 사용자 요청: 기존 seed/최대각도 회전 스크립트를 찾아0도로Isaac적용. 기준 main/450bf5f 및 기존 미커밋·AprilTag 변경 보존.
- 도구: sim/tools/randomize_pepper_rotation.py → scout_dataset.stage.randomize_current_stage_and_save. 기존 구현 그대로 사용; sim/config/scout_dataset.json fruit_rotation.max_degrees만30→0, seed734유지.
- 실제 Isaac headless stage에서 기존 runpy 스크립트를 실행해 farm_with_plants_v5.usd 저장·정상종료0. 288개 jitter XYZ=0, world local-Z 기울기 전0.964~41.171°→후모두0°. 위치/원래xform op/ID 유지. 원래 yaw는보존하며모든quaternion이identity라는뜻은아님.
- 백업: sim/assets/envs/output/farm_with_plants_v5.usd.before_rotation_20261008_142400_041527. 설정백업/실행스크립트/stdout/전후288개검증은 sim/runs/pepper_rotation_zero_20261008.
- 실물·공통·물성·정책변경없음. 기존실행창의메모리상태는유지. 별도UI는초기화SIGSEGV(-11)로종료해ready미확인(gui.log/gui_result.json). 맵저장프로세스종료0과구분. 기존Isaac재시작으로새맵로드필요. 이번수확성공률재시험은아직수행하지않음.
- 복원: 위USD백업을원래파일로복사하고설정max_degrees=30(seed734)복원한뒤Isaac재시작. 커밋·푸시없음.

## SIM-HARVEST-UI-STARTUP-20261008-036 — 시험 GUI 시작 종료 수정

- 사용자 오류 수정 요청, 기준 main/450bf5f 및 기존 미커밋 보존. 대상: 런타임 `run_fleet.py`, `run_sim.py`, `harvest_physics_inspector.py`, `physics_schedule.py`, inspector 회귀 검사 및 상태 문서.
- 조기 PhysX UI 확장 활성화 상태에서 World 초기 render가 native SIGSEGV로 종료됐다. 확장 등록을 World/장치 초기화 뒤로 이동했다. 이후 드러난 dt 오류는 layers 확장이 USD 편집 대상을 session→root로 변경해, 더 강한 session의480Hz가 root에 쓴60Hz를 덮은 문제였다. 확장 활성화 성공/실패 모두 기존 edit target을 복원하며 dt 불일치 메시지에 실제/기대값을 추가했다. 충돌 메뉴와 엄격한 주기 검사는 유지한다.
- 실제 Isaac5.1 GUI: 일반3초/180tick 종료0, 물리 관찰14초/840render/4200tick 종료0. 1.520833초에480Hz·주변5과실 활성,9.520834초에60Hz·0과실 복귀. 일반 무기한 시험창 재실행 및 패널/60Hz 화면 확인 후 열어둠. 로그·화면 `sim/runs/harvest_ui_startup_fix_20261008/`.
- 관련 검사39개 PASS(레이어 복원 성공/실패, 주기, UI, launcher, fleet entrypoint). 넓은 harvest 패턴 검사112개에서는 별도 geometry 단일 테스트의48개 subtest 실패 및 sandbox UDP 차단3오류가 있었다. UDP 관련 launcher8개는 허용 환경에서 전부PASS. 경로 기하 실패는 이번 시작 수정 범위에서 수정하지 않았다. run_sim 실제 GUI 및 수확 성공률은 이번 미검증.
- 실물/공통/Teacher/물성/0도맵 변경 없음. 복원은 이번 확장 호출 이동·edit target 보존·오류 메시지만 역적용하며 기존 사용자 변경을 통째로 되돌리지 않는다. 수정 파일 묶음 `sim/runs/harvest_ui_startup_fix_20261008/changed_files.tar.gz`는 현재 미커밋 파일 전체를 포함한다. 커밋·푸시 없음.


## SIM-TEACHER-ARM-ALIGNMENT-20261008-037 — 학습 오른팔 물리 정렬

- 승인: 사용자 “로봇팔 물성치, 충돌 판정 … 다 학습환경에 맞춰서 수정”. main/450bf5f 및 기존 미커밋 보존. sim 전용, 실물/공통/전달 정책 소스 변경 없음.
- 대상: `teacher_arm_alignment.py`, `robotarm_asset_setup.py`, `harvest_physics.py`, `teacher_device.py`, `teacher_diagnostics.py`, `run_fleet.py`(종료 전 최초 예외 보존), `robotarm_physics.json`, 기준 팔usdc/manifest, 추출/대조 도구2개, 회귀 검사, 물리 확인/진단 회신·상태·결정 문서.
- 변경: convexHull→전달 convexDecomposition 메시15개; 여섯몸체 질량/COM/관성·집게카메라 합성; 자기충돌true/solver12·4, 학습GPU/TGS/접촉설정, material, 팔 collider1mm override제거, 학습4링크 접촉센서. 이동 차체·왼팔/바퀴 구동 구조 유지. 원본USD 미저장/세션적용. [상세 비교와 환경 차이](HARVEST_PHYSICS_INSPECTION_20261008.md).
- 검증: 독립 전달1회 종료0, 농장GUI3초 종료0, USD/PhysX115항목 일치(최종GUI 반복확인), 회귀56PASS. 수확480Hz/주변5과실 및60Hz복귀/정상종료0. 수확 적재0/1: arm_collision→return_contact_2.779N→safe_stopped=true. 수확성공률 개선/전체학습환경 동일성 검증 아님. 최종 GUI 열어둠.
- 최초 통합2회는 SDK 확장속성 API 부재로 초기예외, 종료native오류가 원인을 가림. typed USD attribute fallback 및 종료전 예외기록 후 해결, 세 번째부터 정상. 실패로그도 보존.
- 결과 `sim/runs/arm_physics_alignment_20261008/`, 설정/초기 코드 백업 포함. 복원: teacher_alignment.enabled=false 후 새실행(기존 팔 물리 경로). 전체 파일 reset 금지. 변경파일묶음/적용명령은 상세문서에 기록. 커밋·푸시/외부발송 없음.


## SIM-FRUIT-RENDER-SYNC-20261008-038 — 과실 물리/화면 위치 동기화

- 승인: 사용자 내부 적재 로그와 초기 위치 화면의 차이 조사 요청. main/450bf5f 및 기존 미커밋 보존.
- 대상: devices 신규 fruit_pose.py 및 fruit_attachment.py, runtime fruit_asset_setup.py, pose 신규검사/asset 설정검사, 물리진단·회신·PROJECT_STATE·이력 문서.
- 원인/수정: 사용자 정의 matrix op로 고정된 과실은 동적 PhysX만 이동하고 표시 root/mesh는 정지했다. 초기 배치/재고정 모두 pose를 보존한 표준 translate/orient/scale로 작성한다. 내부 SUCCESS만으로 화면 운반을 확인했다고 한 판단을 정정했다.
- 검증: 실제GUI 통제 이동·낙하23sample 최대 물리/표시 오차0.550647m→0.000590m(root0m). 최종5초/300render/1763physics/종료0. 초기3probe는 완료 후 잔류종료를 수동 정리했으며 최종 정상종료와 구분. 단위·USD43PASS. 새 일반GUI480→60Hz 및 화면 확인. 전체수확 성공 재검증은 미실행.
- 실물영향 없음. 정책·마찰·질량·성공기준·원본맵 불변. 결과/백업/변경파일묶음 sim/runs/fruit_render_sync_20261008. 복원은 before.py와 이번함수/검사 차이만 비교하며 기존변경 유지. 적용명령은 물리진단문서 마지막 절.
- 다음: 새GUI에서 실제 파지→운반→적재 관찰. 문서갱신, 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-OPT-20261008-039 — 단독 시험 UI의480Hz 비용 축소 (정적화는040에서 철회)

- 승인: 사용자의 PhysX step 최적화 요청. sim 런타임3개 파일(physics_schedule, harvest_test_ui, run_fleet)과 관련 검사만 변경. 실물·공통·원본USD·학습 팔 물성/충돌/주기 불변.
- 변경: 미사용 선별기/정찰 로봇43강체를 표시·충돌 형상 보존한 정적 배경으로 전환. USD 위치/속도 쓰기를 렌더 프레임의 마지막 tick에 수행. 힘/물리/접촉은480Hz 유지. 두 변경 모두 시험 UI에만 활성화.
- 실측: 동일seed713의480Hz GUI 수확에서 물리 step195.84→102.43ms, FPS4.28→7.01. 실제 적재0/1, 복귀 접촉 실패는 남음. GPU backend 유지; CPU/MBP10.51FPS 비교는 미적용.
- 검증: 관련37검사PASS, 운영GUI 종료0·표시 위치136표본/배경형상불변·PhysX오류0. 독립 sleep/재활성/480→60→480 시험 종료0(최대 위치오차1.92e-8m). Stop→재배치→240Hz 재수확 확인. [상세 수치·재현·범위](HARVEST_TEST_UI_20261008.md), 로그 sim/runs/physx_optimization_20261008.
- 복원: run_fleet의 configure_test_background 호출과 batch_usd_writeback 활성화만 역적용. 기존 사용자 변경/물성정렬/과실표시수정 보존. 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-RESTORE-20261008-040 — 네 로봇 동시 운용 요구에 따른 정적화 철회

- 사용자 정정: 예찰·수확·운송·선별팔은 최종적으로 모두 동시에 움직여야 하므로 다른 로봇 정적화는 부적절함.
- 변경: harvest_test_ui의 configure_test_background, run_fleet의 해당 호출, 전용 test_harvest_test_background.py 제거. USD 쓰기 프레임 단위 처리만 유지. 이전 GUI 세션 종료 후 새 stage로 실행. 원본USD/실물/공통코드 불변.
- 수치 정정: 7.01FPS/PhysX102.43ms는 두 로봇을 정적화한 폐기 조건이다. 로봇 물리 유지 시 기존 비교4.28→4.67FPS이며 네 로봇 동시 운용 실측은 미실행. fetch_results는 계산 완료 대기/결과 반영을 포함하므로 readback 주병목 단정도 철회.
- 검증: 스케줄러15·UI17·진입점2개PASS. 실제 물리 복원 로그는 sim/runs/physx_optimization_20261008/restored_scene.json 및 restored_ui.log. [현재 범위와 기록](HARVEST_TEST_UI_20261008.md).
- 사용자 변경 보존, 커밋·푸시·외부발송 없음. 정적화는 다시 적용하지 않는다.

## SIM-HARVEST-PHYSX-PROFILE-20261008-041 — GPU 커널과 대기 FPS 간극 실측

- 승인/기준: 사용자 “병목을 더 확실하게 파악 … 기존 Nav2 약70FPS와 현재대기22FPS 간극 확인”. main/450bf5f 및 기존 미커밋 보존. 운영 소스·설정·정책·원본USD·실물·공통 코드 변경 없음.
- 대상: `sim/runs/physx_bottleneck_20261008/`의 격리 계측 wrapper/결과와 `HARVEST_TEST_UI_20261008.md`, `HARVEST_PHYSICS_INSPECTION_20261008.md`, `docs/PROJECT_STATE.md`, 이 이력. CPU/MBP 전환·좌표기록 생략/캐시는 임시 대조 실행만 적용.
- 전후: fetch_results 경과시간만으로 CPU/GPU원인을 분리하지 못함 → Nsight CUDA/NVTX/OSRT와 PhysX profile zone으로428tick분리. USD쓰기없는fetch17.843ms 중GPU커널15.924ms, GPU→CPU복사0.0619ms/tick. 상위관절커널각15408회=428×36,1block×32thread. GPU solver최대반복32/4의 장면전체영향을 공식107.3소스/실제커널로 확인. 기존팔115항목속성검사한계를명시.
- 대기 비교: 동일ReviewCamera1280×720/센서OFF/각새프로세스. 모든기존로봇97동적/3관절계·과실형상4829유지, GPU29.80FPS→CPU50.23FPS. 좌표기록생략진단GPU31.95/CPU59.53FPS. 원본맵대조는43동적/2관절계/29convex/CPU,실제59.56FPS(60cap)·물리1.81ms. sleep제외처리용량138.49를실제FPS로사용하지않음. 원본맵SHA전후동일.
- 수확 비교: CPU480Hz작업13.01FPS,seed713적재0/1,RETURN_FAILED/2.839N·실제정지확인·정상종료0. 성공률개선/물리backend동등성으로해석하지않음. 상세현재GPU대조와좌표캐시결과는연결보고서참고.
- 검증/한계: 실제Isaac5.1 GUI격리대조와Nsight원본보존. 최초Nsight실행은optional SDK cooking API선택오류로capture전종료1,수정후최종종료0; 실패로그보존. CPU IP sampling권한제한은우회하지않음. 실제Nav2경로주행·과거사용자70FPS정확조건·최종4로봇동시미션·다지점수확회귀는미실행.
- 복원: 이번에는운영변경없음. 진단wrapper를사용하지않으면기존기본GPU/수확480/대기60Hz. 추가문서만해당절비교복원하고원본로그는보존한다. 다음은환경조건완화보다CPU480Hz접촉/관측/성공률회귀우선. 문서갱신,커밋·푸시·외부발송없음.

## SIM-HARVEST-REPORT-20261008-042 — 최적화 종합 자료와 Git 반영

- 승인: 사용자 “최근커밋 이후 수정사항 커밋메세지에 간략하게 … 480hz 물리 연산 적용 후 … 보고서 작성용 md”, 후속으로 commit+pull+push까지 명시. 기준 main/450bf5f 이후 미커밋 변경 전체를 보존·반영한다.
- 대상: `HARVEST_OPTIMIZATION_REPORT_MATERIAL_20261008.md`, `changes/HARVEST_OPTIMIZATION_EVIDENCE_20261008.json`, PROJECT_STATE 링크, 이 이력, sim/.gitignore의 회전 전 로컬백업 제외 규칙.
- 변경: 초기 CPU480Hz→지역 활성화/주기전환→UI/정확성 수정→Hz비교→USD쓰기→정적화 철회→Nsight/CPU/원본맵 대조를 종합했다. 핵심 JSON8개를 출처SHA256과 함께 버전관리 경로에 복사해 원격 보고서 작성에 사용할 수 있게 했다. raw runs/회전 전 백업은 로컬 보존한다.
- 범위: 이번 종합 과정에서 운영 로직·물성·backend를 추가 변경하지 않았다. 최근 미커밋에는 별도 승인된 AprilTag 작업도 포함하며 보고서에서 물리 최적화와 구분한다. 맵과 팔자산은 기존 LFS로 저장한다.
- 검증: 원본 JSON8개 hash/내용 및 Markdown 내부링크 대조 PASS, Python43개 구문 PASS, 기존 전달 CSV의 CRLF를 보존한 변경공백 검사 PASS. Isaac Python에서 수확/물리/진단58개, ROS Jazzy 환경에서 AprilTag4개 PASS(skip0). 최초 검사는 테스트 import 경로 누락, 이전 진단 대역의 PhysX view 누락, Isaac 환경 OpenCV API 차이로 실패했다. import 경로/실행 환경을 맞추고 `test_teacher_diagnostic_trace.py`의 대역 view만 보완해 통과했다. 운영 소스 변경은 없다. 성능/수확 숫자는 앞선 실제 시험 기록이며 보고서 작성 중 재측정값으로 표현하지 않는다. 최종 커밋·원격 반영 상태는 Git 결과를 따른다.
- 복원: 이 종합자료/링크/백업 제외 규칙만 필요에 따라 역적용한다. 이전 변경을 통째로 reset하거나 raw 로그·복원용 USD를 삭제하지 않는다.



## SIM-SCOUT-URDF-20261013 — PDF 장착 모델 반영

- 기준 main/a393f1a, 사용자 URDF 수정 요청 및 첨부 PDF 기준. sim scout 원본/portable URDF에 기둥·상판/홀더 근사 외형·봉·D435/파이캠 TF 추가. 기존 기본 링크/물성 불변, 공통·실물 소스 변경 없음.
- 변경 전 센서/장착 없음 → D435(-49,55,595)mm/하향1도, 파이캠(-32,63,117)mm, 기둥 상단620mm. PDF A/B/C 구분 유지; 추가 질량/관성은 미정.
- 직접 검증: XML/트리/기존 노드 보존/좌표·방향 계산. ROS·Isaac·실물 미실행. 기존 USD/실행 설정은 자동 변경되지 않으며 PC 적용/원격 반영 없음.
- [상세·한계·복원](SCOUT_URDF_MOUNT_20261013.md). 패치 역적용으로 복원하며 사용자 변경이 있으면 먼저 병합.


## SIM-SCOUT-USD-20261013 — 장착 USD 및 단독/fleet 연결

- 승인: 사용자 “usd까지 반영한다음 커밋푸쉬해”. 기준 main/a393f1a. 앞선 URDF 수정본까지 함께 반영.
- 대상: scout_mount_20261013.usda/하위 .gitattributes, build_scout_mount_usd.py, scout_mount.py, run_sim.py/run_fleet.py, scout.json/scout_fleet.json, test_scout_mount_usd.py 및 관련 상태·결정/보고서.
- 전후: URDF만 수정 → 실제 sim 진입점에서 기존 base_link에 장착 USD 참조·D435 transform 적용·파이캠/PDF TF 발행. 기존 Camera 광학/구동 joint/본체 질량 유지. 공통·실물 변경 없음.
- 직접 검사: OpenUSD26.8 합성 stage4PASS(비활성 prim 검증 결함 수정 후 통과), Python 구문PASS. 원본 농장 LFS binary 미확보로 실제 농장 합성/Isaac/PhysX/ROS/주행은 미검증.
- 복원: scout_mount_asset 설정 제거 및 재시작. 원본 USD는 세션 방식으로 보존. [상세·한계](SCOUT_URDF_MOUNT_20261013.md) 최상단 절을 따른다. 원격 게시 승인은 받았으며 최종 Git ref 결과로 게시 여부 확인.

## SIM-APRILTAG-HANDOFF-20261013 — 인수 주행 병합과 시뮬 영상 보정 연결

- 기준: `main/a393f1a` + 기존 사용자 미커밋 변경. 전달 `bf10fcd`, SHA-256 120개 일치. 승인 근거는 이번 사용자의 “새로 받은 주행 기준으로 업데이트하고 변경내용 적용하고 시뮬레이션 추가 조치” 요청이다. 공통 통합도 이 요청 범위로 적용했다.
- 대상: 공통 `farm_navigation`, `farm_bringup`, `harvest_robot`, 신규 `farm_tag_localization`/`farm_tag_amcl`; 전달 실물 config/tools/문서; sim 설정·영상 어댑터·launch·생성기·관련 시험. 상세는 [통합 변경 기록](../../docs/changes/APRILTAG_HANDOFF_INTEGRATION_20261013.md), [실행 안내](APRILTAG_INTEGRATION_20261013.md).
- 전후: graph_only 수확→graph 기반 진입/직선 작업/이탈 및 정방향 중간 출발; 태그 배치/가상 영상만 존재→정류·실제 검출·구간별 등록·공통 관측기·scan-sync AMCL 연결. 기존 RPP/오른팔 정차선/Teacher 및 ARRIVAL_THEN_ARM 보존. wire Section 추가 없이 sim 목표 좌표·방향으로 유일한 구간을 선택한다.
- 반복 ID는 `(section_id, family, tag_id)`로 등록하고 진입/이탈 중에는 적용하지 않는다. 실제 ROS 영상 검사로 발견한 detector QoS 불일치와 태그 x/z축 반전을 수정했다. 검출 신뢰도나 보정 pose를 정답으로 대체하지 않았다.
- 실물 영향: 담당자 전달 주행/설정 반영, 실물은 도착 전용·TF 복구 OFF 유지. 반복 구간 기능은 기존 고유 ID와 호환하고 USB 자동 실행은 real에 한정한다. 시스템 udev/sysctl/드라이버 설치·로봇 재배포 없음.
- 검증: 공통5+sim3 패키지 빌드, 공통123/태그65/시뮬23 회귀검사(평행 접근7개 중복), 경로371개, 실제 ROS AMCL22개 PASS. 실제 launch 기동 READY·기동 오류 없음·종료0. 실제 Isaac 새 정차 렌더240태그/1280×720·공유메모리 확인 후 Kit 종료 대기 timeout124. 해당 영상의 genuine ROS 검출/Journal/공통 관측기 연결10/10프레임 확인(ID104 기준 약1.44mm/0.171°); 한 장면 결과다. 영상 재생 후 upstream 정류/검출기 SIGINT 종료 -11 미해결(전달본 기존 이슈), 모든 시험 프로세스 정리. 전체 주행/팔 E2E 미실행.
- 환경: detector/image_proc 시스템 설치는 관리자 암호로 미완료; 임시 ROS 바이너리를 `sim/runs/apriltag_integration_20261013/deps/`에 풀어 실제 시험했다. 설치 명령과 재빌드/보정 ON 방법은 실행 안내 참조. 기본 보정 OFF.
- 로그·초기 실패·수정 후 결과: `sim/runs/apriltag_integration_20261013/`. 버전관리용 [검증 요약](changes/APRILTAG_VALIDATION_20261013.json), 변경 파일 패치 및 적용 명령은 [실행 안내](APRILTAG_INTEGRATION_20261013.md)에 연결했다. 기존 사용자 URDF/문서·다른 경로 삭제 상태 보존. 세 공용 문서에는 담당자 과거 이력을 요약/연결했고 전면 덮어쓰지 않았다.
- 복원: 이번 파일만 적용 전 사본/시작 커밋과 비교해 복원 후 재빌드한다. 기존 수정 문서/실물 설정 사본은 위 로그 폴더 `before/`. 보정만 OFF할 경우 tag_correction:=false이며 단계별 주행은 유지된다. 미커밋·원격 미반영, commit/push 미수행.

## SIM-SCOUT-MERGE-20261013 — 62a80ed 로컬 병합 및 장착 TF 수신 수정

- 승인: 사용자 `62a80ed`의 예찰 URDF/USD 반영 요청, 후속 “아니요, main에 예찰 변경만 반영”. 원격 heads 직접 조회로62a80ed=main 확인. 로컬 main a393f1a→62a80ed fast-forward; 어떤 브랜치도 삭제하지 않았다.
- 반영: 기존 URDF 두 개는 이미 같았고, 누락된 USD 장착 자산/단독·fleet 실행/카메라/TF 설정과 검사를 병합했다. 공용 문서3개 충돌은 양쪽 이력을 보존했다. 미커밋 AprilTag 소스·설정은 해시로 보존을 확인했고 기존 삭제55개 상태도 유지했다.
- 추가 수정: `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py`, `sim/tests/test_adapter_tf_contract.py`. 장착이 켜진 예찰의 정적 TF 기대값3→7개. 정확한 부모/자식/namespace를 검증하며 누락·중복·미등록 프레임은 거절한다. 이 수정 없이는 새 예찰 상태 패킷 전체가 무시된다. 공통·실물·수확 설정 영향 없음.
- 검증: 수신 계약11/진입점2/OpenUSD4 PASS, sim3패키지 재빌드 PASS. 실제 농장 binary USD에서 세션 장착·D435 렌즈 위치/방향·추가 TF4개·원본 보존 확인. 실제 Kit/PhysX/주행·ROS 전체 E2E는 이번 미실행.
- 로그·적용 전 사본: `sim/runs/scout_merge_20261013/`. 실행 중인 sim에는 소급되지 않으므로 새 overlay source 및 재시작 필요. 원격 main에 이미 있던 커밋만 가져왔고 새 commit/push 없음; 추가 호환 수정은 기존 AprilTag 작업과 함께 미커밋.
- 복원: 추가 수신 수정은 두 파일만 역적용한다. 장착 비활성화는 두 scout 프로파일의 `scout_mount_asset` 선택 해제 후 재시작한다. 이번 Git 병합을 되돌리려고 기존 미커밋 작업을 reset/clean하지 않는다.

- 원본 정리(2026-10-13): 전달 폴더 120개 파일의 반영 대상 존재, SHA-256 및 Git `bf10fcd` 원본 일치, 실행 symlink 의존성 없음을 확인하고 사용자 요청으로 전달 폴더를 삭제했다. `sim/runs/apriltag_integration_20261013/SOURCE_HANDOFF.md`와 `source_cleanup.json` 보존.
- 주행 시험: `sim/runs/navigation_smoke_20261013/harvest_runtime.yaml`과 관련 파일을 준비했다. 기존 수확 설정에서 완료 정책만 `ARRIVAL_ONLY_NO_HARVEST`로 변경하여 팔 동작 없이 시험한다. 운영 기본 `ARRIVAL_THEN_ARM` 유지. 환경 로딩·수확 launch 조립(태그 OFF)·SEC01 Goal 생성 확인, 실제 주행은 실행하지 않았다. 태그 ON 실행 전 시스템 `apriltag_ros`/`image_proc` 설치가 필요하다.


### 수확 진입 경계 오류 — 2026-10-13 (공통 변경 승인 대기)

- 사용자 시험 `smoke_7616aba8822b` 로그에서 SEC01 진입 `(-6.015,10.7)`에 실제 `(-6.01767356,10.71018813)`로 도착했다. 오차 0.010533m는 허용 0.02m 이내라 ARRIVED지만, `CorridorNavigator._plan_current()`의 시작점 앞 무오차 경계 검사에서 WINDOW_MOVE가 즉시 실패했다. 태그 보정의 원인 여부를 추측하지 않으며 확인된 직접 원인은 두 판정 기준의 불일치다.
- 최소 제안: `robot/ros_ws/src/harvest_robot/harvest_robot/corridor_navigation.py`의 작업 경로 시작 검사에서 기존 구간 내부 또는 진입점 반경 `arrival_tolerance_m` 이내를 허용한다. 목표 구간, 종료 경계, 전방·횡오차·방향 검사, 진입 생략 조건은 유지한다. 양 환경 공통 영향 때문에 AGENTS의 명시 확인 전 실제 소스에는 적용하지 않았다.
- 산출물: `sim/runs/corridor_entry_review_20261013/proposal.patch`, `corridor_navigation.py.proposed`, `verification.json`. 원래 실패를 실제 기록 좌표로 재현했고 수정안의 정상 연결 및 2cm 초과/횡오차/끝점 초과/후방 목표/방향 오류 거절·진입 생략 조건 유지 8개 오프라인 확인을 통과했다. 실제 ROS/Isaac 재주행은 하지 않았다.
- 승인 후 적용·관련 회귀검사·빌드·재시작 후 동일 목표 재시험이 다음 단계다. 실행 코드/설정 변경 없음, commit/push 없음. 제안 취소 시 산출물만 폐기하면 된다.


## SIM-SHARED-TAG-20261013 — 예찰 PiCam과 공통 주행 보정

- 승인: 사용자가 “예찰도 apriltag 기준으로 주행보정 … 동일 개념의 주행 시스템을 공유”하도록 요청했다. 공통 코드 변경을 포함한 직접 승인 범위에서 적용했다. 기준 `main/62a80ed`, 기존 미커밋 변경 보존, 이번 commit/push 없음.
- 공통 연결: `farm_navigation/tag_control.py`에 보정 권한 신호를 두고 두 로봇이 재사용한다. 수확 import 호환 경로 유지. ScoutNode의 `tag_correction`과 관측 이동 상태를 연결해 진입 완료 후 해당 구역 이동에서만 활성화하고 접근/이탈/정지 관측·완료/실패/취소 때 해제한다. 기존 공통 Navigator/Nav2, 업무 FSM과 관제 메시지는 유지한다.
- 시뮬 센서: 예찰 USD PiCam optical 프레임에 실제 Camera를 생성해 별도 RGB/CameraInfo/공유메모리로 연결했다. D435 과실 영상은 유지한다. 단독/fleet 모두 동작하며 장착 TF를 중복 생성하지 않는다. USD 원본 대신 세션 레이어를 사용한다.
- 시뮬 연결: `farm_sim_runtime/tag_localization.py`가 두 로봇의 정류·검출·기록을 공통 조립한다. `all.launch.py tag_correction:=true`는 선택한 예찰·수확 모두에 적용되고 두 로봇이 같은 `farm_tag_localization`/`farm_tag_amcl`을 사용한다. namespace·보정 권한·캡처 폴더는 각각 분리한다. 실행 중인 Isaac/ROS는 재시작해야 한다.
- 자산: 동일 240개 구역 태그 지도와 계산 코드를 사용한다. PiCam URDF 외부변환, 명시적인 시뮬 pinhole 광학, 약1.1m 관측 거리와 약48px 태그 조건은 예찰 프로파일로 분리했다. 실물 PiCam 교정값이 아니며 수확 자산은 기존 SHA와 일치한다.
- 확인: 공통4·시뮬3패키지 빌드, 수확82·현행 예찰 통신6·예찰 보정수명5·시뮬 태그/카메라26·공통 launch9 검사 PASS. OpenUSD 장착7검사 PASS. 구형 `tests/test_scout_state_flow.py`는 30개 중20오류: 기존 HEAD의 `section_id` 계약에 옛 fixture가 `section_ids`를 보내는 불일치이며 이번 범위에서 변경하지 않았다.
- 실제 Isaac PiCam 1280×720 렌더·공유메모리 전달과 ROS 정류→검출→Journal→공통 관측기 5/5프레임 수신/채택을 확인했다. 초기 배치가 아니라 RGB와 함께 받은 CameraParams로 촬영 시점 좌표를 비교했다. 해당 정차 장면은 횡방향 약3.72cm·진행방향7.16cm·yaw3.41° 오차로, 시험의 축별5cm 정확도 조건을 **실패**했다. 검출 해상도 축소 해제(decimate1)로 개선되지 않았다. 작은 정면 태그의 자세 추정 민감도가 확인됐으나 이동 중 성능·전체 원인은 추가 검증 대상이다. 정밀 주행 성공으로 기록하지 않는다.
- 종료 제한: Isaac은 영상/메타데이터 저장 후 종료 대기로 timeout124. ROS 검출기도 SIGINT 시 -11 또는 종료 대기로 시험 소유 프로세스만 강제 종료한 기록이 있다. 정상 종료 시험으로 기록하지 않는다. 실물·폐루프 실제 주행은 실행하지 않았다.
- 기록: `sim/runs/shared_tag_navigation_20261013/`의 빌드/회귀 로그, 초기·촬영시점 렌더, ROS replay 결과 및 [검증 요약](changes/SHARED_TAG_NAVIGATION_20261013.json). 실행 안내는 [시뮬 통합 안내](APRILTAG_INTEGRATION_20261013.md).
- 남은 작업: 예찰 실제 카메라 교정 및 관측 모델/정면 소형 태그 정확도 개선, 이동 중 보정 평가. 기존 수확 진입 허용오차 수정은 여전히 별도 제안 상태이며 이번 변경에 적용하지 않았다.

- 복원: 이번 변경 파일에서 공통 신호 이동·예찰 연결·추가 센서/프로파일만 되돌린 후 빌드/재시작한다. 단순 보정 OFF 비교는 `tag_correction:=false`로 가능하며 이전 인수/예찰 장착 변경 전체를 reset하지 않는다.


## SIM-HARVEST-START-AUDIT-20261013 — 원본 대조·수정 초안 보류

- 사용자 추가 확인 요청: 실물 성공본은 별도 출발 조건을 제거했다고 전달받았으며, 시뮬 중단 직전에는 SEC01 태그가 카메라에 보이지 않았음. 최신 실패 `smoke_7c647822d87c`와 전달 커밋 `bf10fcd`를 대조했다. 원격 재조회·실물 접속은 하지 않았다.
- 원본 확인: `corridor_navigation.py`와 공통 `parallel_approach.py`는 전달 원본과 바이트 일치. 원본에도 구간 내부·방향·횡오차·전방 목표 검사가 남아 있다. 태그 응답/READY/검출을 기다리지 않는 동작은 원본과 현재 모두 같다. 담당자가 전달 뒤 별도 변경한 실물 실행본이 있는지는 미확인이다.
- 통합 설정 차이: 실물은 작업 허용구간10→14, 진입11번으로 시작 경계보다1m 안쪽이다. 시뮬은 진입20102번을 작업 허용구간 시작점에도 사용했다. 이 때문에 진입 도착 오차 범위의 위치가 구간 밖으로 분류된다. 조건 제거 코드 누락으로 확인된 문제가 아니라 시뮬 구간 설정이 원본의 전제를 재현하지 못한 문제다. 최근 도착 기록상 시작점 직전5.985mm·횡오차6.030mm·방향0.648°였다(실패 판정 시각보다 약41ms 앞의 도착 기록).
- 실제 구조: 진입과 작업 모두 FollowPath 경로를 사용하고 태그 관측이 AMCL 위치를 보정한다. 작업 단계 전환은 태그 검출 성공을 기다리지 않는다. 이번 실패는 작업 경로 생성 중 발생했고 태그 보정 요청/적용은0회다.
- 영상 확인: 검출 journal `sim/runs/apriltag/9462dccc81d049669fbb3a35950747d2/`에서 도착 시각83.354171s 전후1초의8프레임 모두 검출0. 앞선 접근 중7회 검출은 구역 미확정으로 제외됐다. 반복ID이므로 해당 검출을 SEC01로 단정하지 않는다.
- 기하 확인: SEC01 수확 진입y10.7, bed시작y10.0, 첫태그y9.968로 첫태그는 진행방향0.732m 앞이다. 측면 카메라의1280폭 화면에 첫태그 중심은 진입목표에서u3509px, 도착기록 위치에서u3363px로 시야 밖. 계획 직선 기준 약0.598m 이동 후 전체 태그가 화면에, 약0.662m 후 보정ROI에 들어온다. 이는 정적 투영이며 실제 RGB/가림/월드 정답 재렌더 검증은 아니다.
- 임시2cm 진행축 허용 수정은5개 신규 검사·수확87개·sim설정3개 및 빌드를 통과했으나, 사용자 원본 대조 요청에 따라 `sim/runs/corridor_entry_fix_20261013/`에 제안 패치/검사를 보관하고 소스·운영/시험 설정을 적용 전으로 복원했다. 출발 조건 완화는 현재 적용하지 않았다.
- 권장 후속: 원본처럼 진입점이 작업 허용구간 안에 놓이도록 시뮬 구간 정의를 먼저 맞춘다(SEC01은 기존 그래프의 진입 전 직선노드9002가 후보). 태그 관측 전 약0.6m 구간의 의미와 작업 시작 시 태그 가시성 요구는 별도로 정해야 한다. 현재 진입점에 단순 검출대기를 넣으면 태그가 시야 밖이라 대기 상태에 머물 수 있다.
- 근거: `sim/runs/harvest_abort_audit_20261013/{source_and_detection_audit.json,camera_geometry.json,camera_geometry.py}`. 운영 코드/설정의 최종 변경 없음, 문서/검사 산출물만 추가. 실물·시뮬 주행 명령 및 commit/push 없음.

- 승인 범위는 원본/영상 기록 확인과 직전 초안 보류다. 실제 주행 기준 추가 변경은 미적용이다. 복원할 운영 변경은 없고 산출물만 보관한다.

## SIM-HARVEST-START-ALIGN-20261013 — 실물 기준 작업 구간 적용

- 구분/승인: 시뮬 전용 설정·생성기·검사. 사용자 “실물이랑 맞춰 실물방식을 무조건 따라가”로 적용 승인. 기준 main/62a80ed 및 전달 bf10fcd, 미커밋 변경 보존.
- 대상: `sim/tools/rebuild_route_data.py`, `sim/ros_ws/src/farm_sim_config/config/harvest_task.json`, `sim/tests/test_staged_harvest_config.py`, 이동 시험용 `sim/runs/navigation_smoke_20261013/harvest_task.json`.
- 변경 전후: 이전에는 진입점=허용 시작점이라5.985mm 직전 도착도 구간 밖이었다. 기존 그래프에서 진입점에 직접 연결된 직선 직전 노드를 허용 시작으로 선택하여16구역 모두 진입점이 내부에 놓이도록 했다. SEC01은9002→20100을 허용 구간으로,20102를 진입 목표로 사용한다. 시작→진입 거리는 시뮬0.8m/1.3m(실물1m)이며 진입/이탈 목표와 그래프·좌표는 보존했다. 후보가 없거나 여러 개면 생성 실패로 처리한다.
- 실물 영향: 이번 공통·실물 코드/설정 변경 없음. 원본 구간/횡오차/각도/전방 검사를 그대로 사용한다. 태그 검출 대기 없이 작업 이동하며 유효 관측으로 보정하는 흐름도 유지한다. 임시2cm 진행축 완화 제안은 미적용이다.
- 검증: `python3 -m unittest sim.tests.test_staged_harvest_config -v` 6개 PASS. 두 실패 로그의 실제 도착 좌표를 원본 코드에 넣었을 때 이전 설정의 오류 재현/새 설정 통과,16구역 진입 전1cm 허용과 옆 방향·각도·후진·외곽 거절 유지 확인. `python3 sim/tools/validate_route_data.py` 371개 경로 계획 PASS. `colcon build --symlink-install --packages-select farm_sim_config` PASS. 실제 Isaac/ROS 재주행 미실행.
- 기록/다음: `sim/runs/harvest_start_alignment_20261013/`의 로그 및 비교 그림. 수확 launch 재시작 후 같은 SEC01 Goal로 시험한다. 진입에서 태그가 보이지 않는 기존 배치는 유지하므로 작업 이동 중 검출·보정 여부는 별도 확인한다. 문서 갱신 완료, commit/push 없음.
- 복원: 생성기의 이번 직전 노드 선택 부분을 제거하고 두 설정의 각 `work_corridor_nodes` 첫 원소만 해당 `entry_node`로 되돌린다. 팔 완료 정책·기존 태그/예찰 변경·다른 미커밋 파일은 보존한다.

## SIM-DRIVE-PERFORMANCE-AUDIT-20261013 — 약17FPS 주행 원인 조사

- 구분/승인: 사용자 “프레임드랍 원인 확인하고 무슨조치 할수있는지 리스트업”에 따른 읽기 전용 조사와 문서 기록. 실행 코드/설정/물성 변경 없음, 실제 재주행·A/B계측 미실행.
- 대상:17:20 실행 fleet/session `298ffb11e69e4a8cbaba7634ba963954`의 주행·물리·태그·Kit/ROS 로그, 현재 runtime/device 소스, 이전10/8 물리 비교 기록. 호스트 GPU/프로세스 조회 시 이미 시뮬 종료 상태였다.
- 결과: RTF0.2854 및 환산17.1248FPS 확인. 물리는60Hz, 활성과실0. GPU물리·센서3개·5simHz 전체과실 평가와 태그RGB-only 미사용depth 복사가 유지된다. 비용의 존재와 이번 실행에서 각 비용의 비중은 구분하며, 일반fleet에 세부 성능로그가 없어 주병목 비중은 확정하지 않았다.
- 추가 확인: 태그 결과 예찰3.40Hz/수확4.32Hz 및 raw영상/CameraInfo 동기 경고. 전송손실/소비지연/원본센서속도 분리 필요. 태그 저널은 영상파일을 저장하지 않는다.
- 후보/영향: CPU물리 비교(주행·접촉 회귀), 미사용 센서 실제렌더 중지와 뷰포트 축소(태그입력 유지), 평가 snapshot 필요 시 갱신, RGB-only 버퍼 낭비 제거, 영상 전달 계측. 카메라fps 또는 tag_correction만 낮춰서는 렌더 부하가 비례 감소하지 않는다. 태그 해상도·충돌/물리 정밀도 완화는 우선안에서 제외한다.
- 상세/산출물: PROJECT_STATE §41, `sim/runs/drive_performance_audit_20261013/evidence.json`. 실물 영향 없음. 되돌릴 운영 변경 없음. 문서 갱신, commit/push 없음.


## SIM-DRIVE-PERFORMANCE-20261014 — 우선순위 성능 조치

- 구분/승인: 사용자 성능 조치 제안 후 “우선순위대로 진행해”. 시뮬 실행/센서 및 제안한 공통 RGB-only 공유메모리 최적화 범위. main/62a80ed 위 미커밋 변경 보존, commit/push 없음.
- 대상: runtime `run_fleet.py`, `run_sim.py`, `launch/{all,isaac}.launch.py`; devices `camera_sim.py`, `camera_ros.py`; 공통 `rgbd_shm.py`; `sim/tests/test_rgb_only_transport.py`.
- 전후: 기존 프로파일만 사용하던 물리에 CPU/GPU 선택 추가(기본 profile 보존), 일반 fleet 성능 기록 추가, headless viewport 갱신 제외. RGB-only는 NaN 깊이 버퍼를 재사용하고 ROS RGB 발행에서 깊이 복사를 생략한다. 기존 RGB-D ABI/기본 API 유지, 실물 설정/주행 업무 정책 영향 없음.
- 검증: 관련36검사·3패키지 빌드·launch 인자 조회 PASS. 직접 Isaac 짧은 주행 GPU17.66→CPU29.05FPS, CPU+headless36.23FPS; 정상3카메라 프레임 유지. 각14sim초/조건1회, ROS/Nav2 제외 비교다. 종료 대기로 -15 정리, 팔 정책/접촉 검증 미실행. 상세 PROJECT_STATE §42 및 `sim/docs/changes/DRIVE_PERFORMANCE_20261014.json`.
- 미적용: 예찰D435 중지는34.73FPS 비교만 수행. 렌더 예약은 영상 미발행으로 철회. 평가 snapshot/충돌체 단순화 보류. 태그 화질·주기·출발 판정 그대로다.
- 기록: `sim/runs/drive_optimization_20261014/`의 before 원본·벤치 manifest/stdout/frames·빌드/검사 로그. 복원은 physics_device:=profile 사용 및 이번 성능 선택/로그/headless 설정과 RGB-only 변경만 역적용한다. 같은 파일의 기존 AprilTag 변경을 함께 되돌리지 않는다.

- 후속 실제 Nav2: CPU28.26FPS이나 진입 방향0.1069rad>0.05로 ABORTED(위치8.7mm 정상). 같은 GPU 조건17.38FPS에서 SEC01 진입·작업 이동 SUCCEEDED, 실제 AprilTag 보정4회. CPU 기본 전환 보류, 도착 기준 유지. 둘 다 팔OFF/expected0이며 예찰은 정차했다. 영상/CameraInfo 동기 경고 잔존. `e2e_cpu/`, `e2e_gpu/`; 추가 런치 검사5개 PASS. 이 결과는 이전 §40의 미실행 재주행 중 해당 SEC01 수확 이동을 보완한다.

- GPU 유지+headless 추가 비교:18.64FPS(화면ON17.66), 센서3개 프레임 유지. 물리 변경 없이 얻는 개선은 약5.5%로 제한적이다. 현재 권장 선택은 기존 물리 유지와 필요할 때 `rviz:=false headless:=true`; CPU는 주행 차이 원인 검증 후 판단한다. 종료 시 기존 tag/image_proc -11 및 Isaac SIGTERM(-15) 문제가 남아 있어 ROS launch 부모0을 모든 자식 정상 종료로 해석하지 않는다.


## SIM-DRIVE-BACKEND-REPEAT-20261014 — CPU/GPU 주행 재현성 검사

- 승인/범위: 사용자 CPU/GPU 결과가 우연인지 확인 요청. 운영 소스·설정·실물 영향 없음. 반복 도구/로그는 sim/runs 안에 작성, 기존 미커밋 변경 보존.
- 시험: 기존 조건에서 GPU→CPU→CPU→GPU 각2회 신규 실행. SEC01 fraction0.313/expected0/팔OFF, 동일 센서/제어/허용치 유지. Goal 이전 액션 발견 실패1회는 별도 제외 보존하고 신규 도메인으로 재실행했다.
- 결과: 신규는 두 backend 모두1성공/1실패. 기존 포함 CPU1/3·GPU2/3 성공. CPU 방향6.124°/6.504° 실패뿐 아니라 GPU7.314° 실패도 재현됐다. 실제 차체 과회전이 기록돼 CPU 고유 실패라는 해석은 철회한다. 성능 차이는 CPU27.76~28.26/GPU17.12~17.38FPS로 유지. 신규 성공 주행에서 GPU 태그 보정7회, CPU11회.
- 해석/제한: 3회씩으로 성공률 차이·동등성 확정 불가. 물리 backend와 실행 속도/ROS 타이밍이 함께 달라 순수 물리 원인 분리는 미완료다. 공통 정렬·정지 응답을 먼저 조사하며 도착 허용치는 유지한다. 기본 backend 변경 없음, 팔 수확 검증 없음.
- 산출물: PROJECT_STATE §43, sim/docs/changes/DRIVE_BACKEND_REPEAT_20261014.json, sim/runs/drive_repeat_20261014/. 시험 소유 프로세스 종료 확인. 부모 launch0과 자식 종료 -11/-15는 별개다. 되돌릴 운영 변경 없음. commit/push 없음.


## SIM-PROGRESS-105-DIAGNOSIS-20261015 — 반복 중단 로그 진단

- 사용자 반복105 보고에 따라 기존 예찰 SEC02 및 수확 TASK005 로그를 분석했다. 기준 main/66b8287. 운영 코드·설정과 실행 프로세스, 실물 영향 없음.
- 예찰의 회전 중 위치 진행 제한과 수확의 명령/휠 응답 진동을 구분했다. 원인 전체 확정이나 수정 완료가 아니다. 상세 근거·후속 검증은 PROJECT_STATE §53 및 changes/PROGRESS_105_DIAGNOSIS_20261015.json에 기록했다.
- 검증: 원본 JSON/JSONL 파싱 및 시간 구간 추출, 설치 FollowPath 코드 정의와 현재 공통 설정 대조. 새 Isaac/실물 시험 없음. 공통 변경 승인 요청 전 진단 단계다.
- 복원: 이번 문서 항목과 신규 진단 JSON만 제거한다. commit/push 없음.


## COMMON-ROTATION-PROGRESS-20261015 — 예찰·수확 회전 진행 판정

- 승인: 사용자 “공통코드면 수정해 회전도 진행 판정에 포함돼야지”. 대상 robot/config/navigation/{scout,harvest}_nav2.yaml. 공통 SimpleProgressChecker→PoseProgressChecker, 각도 문턱0.1rad 추가. 거리/시간/도착/속도 유지. 실물·시뮬에 같은 기준 적용.
- 검증: 설치 Nav2 검사기 직접 호출92 assertions 및 기존 공통 설정pytest6개 PASS. 환경4개 최종값/나머지 설정 불변 PASS. 상세 PROJECT_STATE §54, sim/runs/progress_checker_20261015/. 신규 Isaac/실물 주행 및 실행 프로세스 재시작은 미실행.
- 적용: 해당 Nav2 launch 재시작 후 반영. 수확 휠 응답 진동은 별개로 남는다. 복원은 두 YAML의 SimpleProgressChecker 복구 및 required_movement_angle/주석 제거. 사용자 후속 지시로 이 공통 수정과 해당 기록의 커밋·푸시를 승인받았다.


## SIM-HARVEST-PROGRESS-105-20261015 — 회전 판정 수정 후 수확 정체 분석

- 요청: 최신 수확105 원인 분석. main/8cfcc3f 기준 기존로그만 읽고 운영 코드/설정/실행은 유지했다. 실물 영향 없음.
- 최신 두 SEC02 SECTION_APPROACH 실패는 거의 같은 위치의 실제 정체다. PoseProgressChecker 로드 확인, 신선한 명령 수신/거절0, 최신 태그 보정0회, 휠 PI 보정 포화와 미미한 차체/odom 변화를 확인했다. 물리 접촉/마찰/제어 진동 인과는 추가 계측이 필요하다.
- 상세/검증: PROJECT_STATE §55, changes/HARVEST_PROGRESS_105_20261015.json, sim/runs/harvest_progress_105_20261015/analyze.py. 원본로그 파싱/통계와 실행설정 대조만 수행. 신규 주행/수정/재시작 없음. 이번 기록/JSON 제거로 복원 가능. 미커밋/푸시 없음.


## SIM-HARVEST-CONTACT-ROOT-CAUSE-20261015 — 수확105 접촉 원인 확인

- 사용자 “원인 찾아내”에 따라 격리 CPU 물리 시험5개를 수행했다. 운영 코드/설정/자산과 기존 사용자 실행은 유지했다. 실물 영향 없음.
- 최신SEC02 정체는 왼팔 손목 카메라와 Bed_04/Pepper_0003_yellow 접촉으로 재현됐다. 비수확중 과실은kinematic/충돌유지다. 해당 collider만 시험 씬에서 제외하면 동일 저속회전 응답−0.304°→−22.727°, 직진 방향변화20.789°→−0.327°. 카메라 mount 자체관통도 확인해 별도 역대조했다.
- 검증/한계: 유효5개22sim초 완료, 최초mount 시험은USD instance proxy 편집 오류로 무효. 일부종료SIGTERM−15. Nav2 E2E/실물/운영수정은 미실행. 상세 PROJECT_STATE §56, changes/HARVEST_CONTACT_ROOT_CAUSE_20261015.json, sim/runs/harvest_root_cause_20261015/. 이번기록·시험자료만 제거해 복원. 미커밋/푸시 없음.

## 2026-10-15 — 양팔 접힘 주행, 오른팔 작업 전개/복귀

- 구분/승인: 시뮬 전용 구현. 사용자 “양팔: 주행 중 접고 수확할 때 오른팔만 펼침”. 기준 main/8cfcc3f, 기존 변경 보존. 실물·공통 Nav2/미션 수정 없음. 커밋/푸시 및 사용자 실행 재시작 없음.
- 대상: farm_sim_config/config/robotarm_physics.json; farm_sim_runtime/{robotarm_asset_setup,harvest_physics,run_fleet}.py; farm_sim_devices/{teacher_device,arm_session}.py; tests/{test_arm_session,test_robotarm_asset_setup}.py. 상태/결정: PROJECT_STATE §57, D-034.
- 전후/이유: 왼팔 돌출 및 오른팔 작업 HOME으로 주행하던 방식에서 양팔 별도 접힘 자세로 시작한다. 정차→오른팔 전개→기존 작업 HOME에서 수확→오른팔 접기→양팔 실측 접힘/정지 확인 뒤 주행한다. 취소/접힘 실패 시 차체 잠금을 유지한다. 작업 HOME/정책·과실별 복귀·실물은 유지한다.
- 관련 물리: 왼팔 mount–wrist 인접 CAD 관통만 pair filtering하며 외부 충돌을 유지한다. 왼팔 유지 drive도 같은 오른팔 서보의 기존 SI 값으로 맞춰 접힘 자세의 속도 진동을 없앤다. 초기 더 깊은 접힘 후보는 팔 자체 접촉 때문에 제외했다.
- 검증: 오프라인 회귀45 PASS, 설치 USD/PhysX 정적4 PASS. 실제 CPU transition_v2는 전개5.9초/접기5.95초 및 정지 후SUCCESS. travel_final은 문제 접근 구간 직진1.009m·방향 변화−0.041°,저속 회전−13.679°; 팔 접촉 없음, 주행 중 접힘 판정 누락0회. 실제 수확 후보는 빈 목록으로 전환만 시험했으며 Nav2 전체 미션/과실 수확 E2E/실물은 미실행.22sim초 완료 시험은 앱 종료 지연으로SIGTERM 정리.
- 근거/적용/복원: docs/changes/HARVEST_ARM_TRAVEL_20261015.json 및 runs/arm_stow_20261015/. 다음 Isaac 시작 때 반영된다. 이번8개 파일의 diff만 되돌리면 이전 동작이다. travel_pose 미설정 프로파일은 기존 HOME 방식과 호환된다.

## 2026-10-15 — 박스 간섭 가능한 낮은 열매98개와 커넥터 Z 상향

- 승인/범위: 사용자 요청으로 `assets/envs/output/farm_with_plants_v5.usd`의 낮은 과실·대응 커넥터만 수정. 공통/실물·박스·충돌 설정·기존 팔 코드는 변경 없음. 기준8cfcc3f의 기존 미커밋 작업 보존.
- 변경 전후: 박스 collider 상단0.7013m와 과실 하단 offset−0.0375m,5cm 여유에서 root 최저0.79m 산정. 총288개 중98개를0.79~1.0792028165m 범위로 배정하고 커넥터도 같은ΔZ 이동. 나머지190개, 모든X/Y·회전·scale·ID·mesh 보존. 새 과실 간 AABB 겹침을 피하는 높이를 선택했다.
- 검증: 실제 runtime collider 전체의 박스 위 간격 최소5.3501cm, 신규 과실 AABB 겹침0. 씬의 변경 속성294개가 허용된 Z 이동 속성뿐임을 확인. 실제CPU22sim초에서 이전 박스 간섭 구간 직진 통과 및 박스–과실 접촉0. 기존 높은 열매와 팔의 초기 접촉은 잔존하며 전체Nav2 미션은 미검증. 상세 PROJECT_STATE §58 및 docs/changes/FRUIT_BOX_CLEARANCE_20261015.json.
- 적용/복원: 씬 재로드/Isaac 재시작 필요, 기존 실행 유지 및 커밋/푸시 없음. runs/fruit_height_20261015/farm_with_plants_v5.before.usd를 원래 씬 경로에 복사하면 이번 높이 변경만 복원된다.

## 2026-10-15 — 최신 수확 Goal timeout 진단

- 사용자 응답시간 초과 확인 요청. 코드·설정 변경 없이 최신 로그 분석만 수행했다. 수확 시작300실시간초 후 공통 Nav2Client가 결과 대기 제한으로 취소한 것이며105가 아니다.
- 시뮬 속도비0.4201로 약126sim초만 경과.16.535m 경로는0.1m/s에서 직선 이동만165.35sim초가 필요했다. 취소 직전 정상 전진 및 controller의 취소 응답을 확인했다.
- 근거: PROJECT_STATE §59, docs/changes/HARVEST_GOAL_TIMEOUT_20261015.json. 실행 완료 제한의 ROS 시간 기준 수정은 제안만 했으며 공통 소스/실물 영향 없음. 새 시험·재시작·커밋·푸시 없음. 이번 문서 항목만 제거하면 진단 기록 복원.

## 2026-10-15 — 승인된 공통 주행 sim/real 시계 분리

- 승인: 사용자 “sim이랑 real이랑 서로 다른 시간대를 쓰도록 조정”. 대상은 robot/ros_ws/src/farm_navigation의 nav2_client.py/navigation_types.py/새 test_nav2_execution_clock.py 및 harvest_robot/test/test_follow_work.py의 시계 더블이다. 기존 미커밋 작업 보존.
- 변경 전후: 주행 완료300초를 양쪽 모두 실시간으로 계산하던 방식에서 sim은 기존 use_sim_time의 /clock,real은 monotonic 실시간을 사용한다. 전체 TF 재시도 주행 예산도 일치시켰다. 통신/수락/준비/취소/TF 복구 제한은 실시간 유지. 실행 timeout 오류 문구 분리,sim 시계 역행 시 오류와 Goal 정리 상태 보존.
- 영향/검증: 공통 클라이언트를 쓰는 예찰·수확에 적용,실물 시간 기준은 기존과 동일. 새 설정/의존성 없음. 오프라인59 PASS(시계 전용12 포함),설치 rclpy 시계 API 및 소스 symlink 확인. 실제Isaac 전체 미션/실물 주행 미실행. 상세 PROJECT_STATE §60 및 docs/changes/NAVIGATION_EXECUTION_CLOCK_20261015.json.
- 적용/복원: 실행 중 로봇 노드 재시작 후 적용. 이번 공통 diff만 되돌리면 이전 실시간 주행 제한으로 복원된다. 기존 실행 재시작·커밋·푸시하지 않았다.


## 2026-10-16 — 수확 프레임 저하: 평가 경계 캐시와 실시간 pacing

- 사용자 승인으로 sim 전용 SceneTruth의 정적 로컬 경계를 재사용하고 현재 world 변환은 매번 반영한다. 기하 편집 시 무효화·종료 시 USD notice 해제. run_fleet은 렌더 지연 후 추가 대기를 줄이며 물리 tick을 생략하지 않는다. 일반 Action의 stage 성능 계측과 check_teacher_action --performance-log 연결도 추가했다. 실제 수확 계측으로 CPU Teacher의 Torch intra-op=1을 적용해 팔 계산 평균7.614→4.700ms, 동일 수확 구간13.38→15.55fps를 확인했다. 실제1,649관측 정책 출력 차이0.
- 고정60/20/30Hz·주변 과실 물리·모델·solver·카메라 설정·공통/실물 유지. 전체 센서 headless4sim초 비교에서20.56→26.28 렌더fps, 평가 tick평균3.831→0.657ms. 실제288개 경계 오차0, nativeUSD4+schedule4 PASS. 실제 GUI12fps의 개선 수치로 해석하지 않는다. 수확 PhysX 비용은 잔존한다.
- 실제2과실 수확 재검증/제외 후보/실패 시험/로그 및 원본 소스 복원법은 PROJECT_STATE §68. 현재 실행을 재시작하지 않았으며 다음 시작에 적용. 미커밋·원격 미반영.

- 최종 전체 센서4sim초는25.40fps, 카메라58/39/39로 원본과 동일. 실제 수확 비교3개 모두2/2·접힘·safe stop 통과. 최종 소스 관련13시험 PASS. 상세/패치: runs/performance_20261016/{harvest_summary.json,final_sensor_verification.json,performance_fix_20261016.tar.gz}.


## 2026-10-16 — D435 Student 기본 수확 Action 연결

- 사용자 “D435 Student 연결까지 진행” 승인. 기준2a397da 위 sim 전용 변경이며 공통/실물 미수정. 전달1330파일·모델/URDF/외형 SHA 검증, import 도구·원본 자산 보존, student_camera/student_session 및 student_policy 설정을 추가했다. 기본 backend=student_d435, Teacher 비교·복원/U20 후보 보존.
- 물리CPU60/정책20/촬영30Hz·기존 물성/바퀴·근처 과실 물리를 유지한다. 실제 손목 pose·보정/시각을 센서 rig에 연결하고 PhysX readback을 ack한다. 영상 목표 완전성·중력 순서, 실제 박스 연속 안착, 매 과실 접힘 및 최종 정지를 확인한다. 시뮬 truth는 정책 좌표 입력에 사용하지 않는다. Action 실시간 예산만1800/1860초로 확대.
- 직접 검증: 제공 독립 D4352/2 DONE/리셋0, 농장단일1/1·순차2/2(노랑→빨강)·매과실복귀·안전정지SUCCESS, 정책 중 ROS 취소CANCELED·성공0·차체잠금. 전체센서2sim초120physics tick 및 기존카메라29/19/19프레임. bounded SDK 종료 지연은 소유 프로세스 SIGTERM 정리.61 offline PASS. 물성 원본5layer SHA 동일, 카메라 외형 연결 전후2457물성속성 보존.
- 실패 원인/범위: global visuals 경로 차이 수정,3앱 동시 GPU OOM은 순차 시험, 확장 측정ROI의 인접 창은 기존 고정 작업 범위를 영상에 적용. 다양한 농장/전체Nav2 미션/U20다중/실물/양팔협조 미검증. 추가센서비용의 FPS 보장은 하지 않는다. 상세로그/검증/복원은 PROJECT_STATE §70 및 RUN_GUIDE의 D435 Student 절.
- 반영: 기존 GUI/ROS 미중단, 런치 재시작 후 적용. Teacher 복원 backend=teacher. 신규 commit/push 없음. 변경 파일 패치 student60_integration_20261016.tar.gz, 자산은 전달 원본 import 도구로 설치한다.

## Student 전달본 재확인 — 2026-10-19

- 사용자 `main/robotarm_1019` 최신화 요청으로 재검사. 압축 SHA256 `409633afa28bc4c05e1558a4df7f9c1ff9da95e412f4a608b1b8bc7d0c56cbec`는 기존 10/16 통합본과 동일하며, 압축 내 일반 파일 1,331개를 설치본과 대조해 차이 0개를 확인했다. 새 모델·실행기 변경이 없어 기존 D435 Student 연결을 유지한다.
- `harvest.json`의 오래된 Teacher 설명만 현재 Student 동작에 맞게 수정. 기본 backend `student_d435`, ARRIVAL_THEN_ARM, 물리60/정책20/촬영30Hz와 근처 과실 물리를 유지하며 공통/실물 변경 없음.
- 직접 검증: 설정·목표 대응·세션·물리 스케줄 37 PASS(추가 subtests 2). 동일 바이너리여서 native 수확은 재실행하지 않았으며 10/16의 실제 단일/순차 시험과 구분한다. 증거: `sim/runs/student60_20261019/receipt_verification.json`. 기존 실행 프로세스는 재시작하지 않았다. 미커밋·미푸시.
- 복원: harvest.json의 notes 설명만 이전 문구로 복구. 모델·제어 동작 변경 없음.


## HARVEST-COMMUNICATION-20261019 — 공통 인계 기반 및 ZIP 선택 적용

- 구분/승인: 공통·시뮬 설정·실물 비활성 설정·문서. 사용자 “필요한코드있으면 브랜치에서 가져오고 전달받은 zip을 적용해”; D-041, 시작 main/2a397da + Student 미커밋 상태.
- 대상/이유: 8466ac1의 공통 인계 기반13파일을 먼저 반영하고 ZIP의 수확량 집계·팔 이동 차단·Spin·Discharge를 적용. 상세 대상/근거는 PROJECT_STATE §71 및 runs/harvest_communication_20261019/receipt.json. 상태/결정/이력은 과거 스냅샷으로 덮어쓰지 않고 이번 로컬 적용 내용을 병합했다. 기존 두 시험의 노드 대역도 새 의존성에 맞췄다.
- 전후: 기존 도착→Student 수확은 유지하며 성공 증가분 누적과 실패/취소 후 접힘 미확인 이동 차단을 추가. transfer.enabled=false를 양 환경에 명시하므로 운송 요청·회전·배출은 켜지지 않는다. sim 클라이언트1860초, Student 모델/영상/물리와 기존 사용자 파일1348개 해시 보존.
- 실물 영향: 공통 런타임은 변경되지만 기존 이동 전용 정책·지도·태그·Nav2·Zenoh 설정 유지. 실물 프로파일에는 비활성 transfer 설정만 병합. 원격 브랜치의 전체 실물 설정/후속 현장 조정은 가져오지 않았다. 로봇 배포나 실물 재시험 없음.
- 검증: 최종 오프라인213 PASS(공통/Action183 + Student7 + 세션/스케줄23), 운영5패키지 빌드 성공. ROS 모의 배출4 PASS는 Fast DDS/domain207/동일 프로세스 범위이며 sandbox UDP 경고와 CycloneDDS 미설치 한계가 있다. 최초 시험/격리 빌드 실패 원인과 해결은 PROJECT_STATE §71. Isaac/운송/Jetson 전체 인계는 미실행.
- 복원: runs/harvest_communication_20261019/before.json·before/로 이번 대상만 복구하고 신규 파일만 제거한 뒤5패키지 재빌드. 기존 Student 작업을 덮어쓰거나 reset/clean하지 않는다. 실행 프로세스 재시작·commit/push 없음. 다음은 운송 측 미션/도킹·이격 이벤트 및 sim 장치 서버 연결이다.


## BASKET-LASER-20261019 — Student 성공을 두 레이저 하강 통과로 변경

- 구분/승인: 시뮬 전용 장치·설정·검사·문서. 사용자 “레이저센서 두개 … 통과하면 카운팅”; D-042.
- 대상: devices의 basket_laser.py(신규), student_session.py, arm_session.py의 안착 유지 훅; config의 student_policy.json/harvest.json; test_basket_laser.py(신규)/test_student_assignment.py; check_basket_laser.py(신규)/check_teacher_harvest.py; 현행 상태/결정/실행 문서.
- 전후/이유: 기존 박스 collider 포함·분리·양손가락 clear·0.6초 안정 대신, 배출 허가 후 익명 위→아래 통과를 한 번 집계한다. 단순 박스 좌표만으로 성공하지 않는다. 한 번 센 뒤 반동/반복 신호를 재집계하지 않고 취소 시 감지를 닫는다. 입구 통과 후 물리 잔류를 보장하지 않으며 전체 성공에는 기존 접힘·정지 확인이 별도로 필요하다.
- 실물 영향: 공통 메시지/적재 누적·실물 설정/드라이버 변경 없음. 원본 자산/vendor/모델 유지, Teacher 비교 경로의 기존 판정 유지. 실제 GPIO/PLC 센서 연결은 미구현이다.
- 검증: 오프라인61 PASS, 시뮬2패키지 빌드 PASS, PhysX 익명 낙하1회 PASS. 초기60Hz 동시 진입 누락은 후행 차단 해제 순서 검사로 수정했다. 기본 Action은 초기 영상 지연으로 ARM_LINK_LOST가 재현됐으며 운영 timeout을 늘리지 않았다. 최종 단일 과실 진단(통신/상태 감시만15초)은46.4667sim초에1회 집계,69.2667sim초 SUCCESS/안전정지 완료. 기본 설정 전체 통과나2과실 시험 통과로 해석하지 않는다. 제한시간 차이/증거는 PROJECT_STATE §72와 runs/basket_laser_20261019/verification.json을 따른다.
- 복원/다음: runs/basket_laser_20261019/before.json·before/와 task-only applied_changes.patch로 이번 대상만 복구한다. 기존 Student/통신 작업 보존, 실행 프로세스 재시작·commit/push 없음. 기본 환경 초기 영상 처리 지연 해결과 실제 센서 장착/입력 연결은 별도로 확인해야 한다.


## BASKET-PARALLEL-LASERS-20261019 — 평행3빔 영구 자산과 feedback/result 계수

- 구분/승인: 시뮬 소스·설정·URDF·USD·시험·문서. 사용자 “urdf랑 usd 전부 … 레이저 … feedback이나 result” 및 후속 진행 승인. D-043, main/2a397da + 기존 미커밋 작업 보존.
- 대상: `farm_sim_devices/{basket_laser,student_session}.py`, `farm_sim_config/config/{student_policy,harvest}.json`, 운영 URDF1개/USD base2개, `tools/{build_basket_laser_assets,check_basket_laser,check_teacher_harvest}.py`, 센서/Student/자산 시험과 현행 문서. 파일 목록은 runs/basket_parallel_lasers_20261019/before.json.
- 전후: 중앙 상하2빔의 방향 판정을 폐기하고190mm 입구를47.5mm 간격의 평행3빔으로 덮는다. 실제 배출 중 어느 빔 차단→모두 비차단50ms를 한 개로 집계하며 기존 feedback.success_count/result.harvested_count에 전달한다. USD의6개 헤드와 optical/빔은 영구 저장하며 실측 차체 pose를 따른다. 고정 센서 외 기존 자산 내용·질량·drive는 보존했다.
- 검증: 오프라인69 PASS, 실제 PhysX 낙하14 PASS, 운영USD4+base2 좌표 일치, 시뮬2패키지 빌드 PASS. 전체 Student ROS 단일 수확은46.6167sim초에1회 계수 후69.4167초 SUCCESS/안전정지, 실제 feedback0→1/result1, 모든29개 검사 통과. 진단 timeout15초 조건은 PROJECT_STATE §73 및 이번 runs/verification.json 참조. 턴 중단으로 끝나지 않은 첫 실행은 통과로 세지 않는다.
- 실물 영향/한계: 운영 모델 형상에만 센서 장착부를 추가했으며 실제 GPIO/PLC 입력·제품 규격·질량/관성·배포는 미확정. 종류·통과 방향·박스 잔류는 판정하지 않는다. 비교 Teacher 판정과 전달 모델 해시 기준 자산은 유지한다. 기본 초기 영상 지연 해결은 이번 범위가 아니다.
- 복원/다음: 이번 before.json·before/로 해당 파일만 복구하고 새 파일2개만 제거한 뒤 시뮬2패키지 재빌드. 기존 Student/통신 작업 보존, 사용자 실행 프로세스 재시작·commit/push 없음. 다음 정상 재시작 때 적용하며 실물 센서는 별도 입력 드라이버가 필요하다.

## SIM-ACTION-OUTCOME-20261020 — 실행 완료와 수확 실적 분리

- 승인: 사용자 “윈도우에 도착하고 팔이 실행이 됐고 수확을 시도했으면 일단 성공 … expected 수와 harvested 수가 다른걸로 … 판단”. 최신 의미는 DECISIONS D-045/PROJECT_STATE §77.
- 변경: `tools/run_section_campaign.py`의 ROS SUCCEEDED/result SUCCESS 외 failed_count==0 추가 조건을 제거했다. 예상량 부족/개별 수확 실패 수량만으로 정상 완료 window를 실패/재시도하지 않는다. 요청·피드백·결과의 수량은 보존한다. Student의 미션 중단/정지 미확인/주행 오류를 임의 SUCCESS로 변환하지 않는다. 현재 실행 worker는 시작 때 읽은 조건을 사용하며 다음 worker부터 새 시험 조건을 읽는다.
- 검증: `tests/test_student_assignment.py`에 원래 예상9/수확1/개별실패2의 정상 ROS SUCCESS 전달을 추가했다. assignment11·캠페인1시험, Python 컴파일·diff 확인 통과. 공통/실물/Student vendor 파일은 변경하지 않았다.
- 복원: 이번 실행기 조건과 추가 검증만 역적용한다. 실행 중인 캠페인/기존 로그는 유지한다. 미커밋·미푸시.

## HARVEST-ENDPOINT-105-20261020 — sim 끝점 추종과 위치 재접근 설정

- 승인/범위: 사용자 “원인이 … 시뮬레이션 세팅문제같은데 … 역할을 못하고” 원인 규명/해소 요청. 공통/실물/자산/물성을 수정하지 않고 sim 수확 Nav2 환경 override만 변경했다. DECISIONS D-046/PROJECT_STATE §78.
- 원래 설정: 실패44회차 진입 경로를 그대로 재현하여 목표38.12mm 안으로 들어온 뒤56.65mm로 이탈, 직진0/미세 회전 반복, sim188.48초에105를 확인했다. 일정 ±0.05rad/s 입력은 같은 실패 자세에서 실제+10.54°/-10.92° 회전했다. 따라서 이번 목표 근처105를 바퀴가 전혀 못 도는 물리 문제로 설명하지 않는다.
- 수정: `ros_ws/src/farm_sim_config/config/nav2_harvest.yaml`의 RPP/HarvestApproach/HarvestWork stateful=false. HarvestApproach/HarvestWork interpolate_curvature_after_goal=false. 경계 이탈 후 실제 끝점으로 재접근하도록 한다. 도착4cm/2.5°와 progress10cm/0.1rad/20초는 그대로다. stateful 해제만 한 비수렴 후보와 중간 동적 변경 후105도 모두 보존했다.
- 검증: 두 설정을 처음부터 적용한 동일 실제 경로1/1 SUCCEEDED/error0, 실제 예찰 연속3 window의 Nav2 직접 이동3/3 SUCCEEDED/error0. 이 window fixture에서는 station node_id 불일치로 공통 HarvestNode가 종료했으므로 공통 수확/팔 성공 검증으로 확대하지 않는다. 기존 BT5/staged config6/Action config7 =18검사 PASS와 canonical 환경 로더의 기준값 보존 확인. 후속 전체 캠페인으로 통합 검증을 계속한다.
- 자료/재개: `runs/navigation_105_20261020/comparison.json`과 각 case 원본. 이전 캠페인은 관리 중단/자료 보존 후 `runs/section_campaign_20261020_navfix`를 새 서비스에서 시작했다. 복원은 이번 nav2_harvest.yaml overrides만 제거한 뒤 시험 스택을 재시작한다. 미커밋·미푸시.


## 2026-10-20 — 최신 실물 주행 기준을 공통 설정에 반영 (D-048)

- 구분/승인: 공통·실물·시뮬 수확 주행 설정 변경. 사용자 “실물 기준으로 반영해” 승인. 운영 공통 소스는 변경하지 않는다.
- 대상: robot/config/navigation/{harvest_nav2.yaml,harvest_task.yaml}, robot/config/robots/vicpinky/nav2.yaml, sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml; 기존 test_entry_controller.py/test_harvest_arm_geometry.py 기대값 갱신; DECISIONS/PROJECT_STATE 갱신.
- 이유/전후: bf10fcd 시점 기본값으로 남은 접근 추종40cm→10cm, local costmap5cm→2cm, footprint70×60cm→60×50cm+padding2cm, 접근 시작점 허용10cm→20cm. 최신 실물6f21119를 공통 기준으로 삼는다. D-046 sim 전용 override를 제거해 실물과 같은 RPP 옵션을 사용한다. 실물 costmap의 절대 scan 토픽도 담당자 설정과 일치시킨다.
- 실물 영향: 현재 main real의 다음 launch에 새 공통 설정 및 scan remap 입력이 반영된다. 물리 장비에 배포하거나 프로세스를 재시작하지 않았다. 지도·장치별 연결은 기존 환경을 유지한다.
- 검증: 병합 Nav2 main real↔6f21119 차이0; sim 제어/속도 동일, 환경 연결 차이14개만 허용. 접근 설정 양쪽0.2m. 관련 기존 검사39/39 통과. 최초 ROS 환경 누락 및 이전 기대값2건 실패도 로그 보존. 실제 주행/105 해소는 미검증.
- 자료/복원: sim/runs/navigation_parity_20261020/real_baseline_apply/에 이번 변경 전 파일 before.json, 비교/검사 로그, 변경분 changes.patch를 보존한다. 이번 변경만 복원할 때 해당 패치를 역적용하며 기존 Student/시험 실행기 등 다른 미커밋 작업은 보존한다.
- 실행 중 시험에는 hot reload하지 않았다. 다음 신규 launch부터 반영되므로 기존 조건 결과와 혼합하지 않는다. 후속 시험 통신은 domain13/SUBNET. 미커밋·미푸시.


## 2026-10-20 — SEC01 105의 회전 전환 원인 계측 (운영 변경 없음)

- 사용자 회전 전환 원인 확인 요청으로 기존 시험에30분 제한 읽기 전용 ROS 기록기를 추가했다. 설정·메시지·제어 코드는 변경하지 않았다.
- 17회차 W001에서105 재현. RPP는 현재 pose 시각 TF로3.94cm를 계산해 XY 도착 상태를 기억하고 전진0으로 전환. 도착 checker가 사용하는 최신 TF로 재계산하면 같은 순간5.10cm여서4cm 도착 범위 밖이었다. 현재/최신 TF 분기는 예전 stamp의 경로 끝점과 TF helper의 외삽 fallback에 연결된다.
- 실제 tf2 BufferCore 재생 및1005샘플 거리 비교로 검증했다. 도착 checker 내부 인자는 직접 로깅하지 않았으며 source+TF 재생 근거다. 10회차에 같은 상세 토픽이 있었다고 소급하지 않는다. 주행 수정/실물 재현/105 해결 완료가 아니다.
- 자료·한계·권장 공통 수정 방향은 PROJECT_STATE §83. 모든 새 스크립트/원본 로그는 sim/runs/sec01_real_baseline_20261020_164129/에 보존; 문서만 갱신, 미커밋·미푸시.


## CAMPAIGN-TERMINAL-WATCH-20261021 — 시험 재개와 임시 터미널 감시

- 승인: 사용자 시험 계속 진행 및 bash feedback/result 기록 도구 요청. 대상 tools/watch_section_campaign.sh와 PROJECT_STATE §89.
- 동작: 기존 ActionClient의 events.jsonl에서 현재/후속 시도의 goal·feedback·result를 읽어 KST로 출력하고 캠페인 terminal_feedback.log에 기록. 30초 상태 표시, 부분 줄 대기, Ctrl+C 감시만 종료. 예찰 결과의 전체 좌표는 원본에 유지한다. ROS 메시지/공통 코드/실물 영향 없음.
- 실행: 기존 캠페인 SEC07 3회차부터 재개, 성공 예찰 재사용 확인. 감독자·기록기·절전 방지 복구.
- 검증: 문법 검사, 실제 READY/GOAL/FEEDBACK 수신 기록, 임시 fixture의 result/다음 시도/부분 줄 처리 확인. 복원은 감시 도구만 제거하며 시험·원본은 유지한다. 미커밋·미푸시.


## CAMPAIGN-CPU-PHYSICS-20261021 — 연속 시험 CPU 선택 누락 복구

- 승인: 사용자 CPU 전환 유실 지적 및 복구 요청. 대상 tools/run_section_campaign.py, farm_sim_runtime/run_fleet.py, tests/test_section_campaign.py.
- 원인:47fabb5의 새 캠페인 launch가 CPU 옵션을 누락해 기존 profile의 GPU 정렬 설정을 선택. 기존 CPU 검증 조건을 새 실행 경로에 유지하지 못했다.
- 전후: 캠페인에 physics_device:=cpu 명시, manifest 기록, Isaac의 실제 GPU dynamics/broadphase readback 출력. 모든 재시도도 CPU 유지. 일반 launch/물성/센서/공통/실물 영향 없음.
- 실행/검증: 설정 변경 STOP으로 SEC07 3회차 보존 후4회차 재개. 감독자7검사 및18회 launch CPU 유지 검증, 컴파일/diff 통과. 통합 결과는 PROJECT_STATE §90의 후속 기록 참조. 복원은 해당 옵션/진단 출력/검사만 역적용. 미커밋·미푸시.

- CPU 실배포 확인: SEC07_attempt_0004 stack.log에서 [physics_device] requested=cpu, gpu_dynamics=false, broadphase=MBP를 직접 확인했다. 성능 개선 폭/CPU 수확 완주 결과는 아직 측정 전이다.


## STUDENT-CAMERA-PERFORMANCE-20261021 — 전처리·현재 pose 렌더 공유

- 승인/범위: 사용자 가능한 카메라 성능 개선 요청. sim/farm_sim_devices의 student_camera.py/student_session.py, sim/farm_sim_runtime/run_fleet.py, sim 전달 자산의 student60_mission_session.py 및 관련 검사. 공통/실물 운영 코드 변경 없음. 기준/상세 PROJECT_STATE §91.
- 원인/변경: 정차 촬영97.4ms 중 깊이 정렬39.9ms와 리맵20.7ms가 컸다. 이미 전달된 CPU 컴파일 가속기를 warmup 후 선택적으로 사용하고, 불필요한 overlay 생성을 생략한다. RGBA를 직접 리맵한 뒤 동일 RGB를 반환한다. 물리 직후 현재 카메라 pose를 준비해 같은 시각의 일반 render를 첫 pass로 공유하며 총2pass를 유지한다. 재사용 불가 시 기존2pass, 오류는 기존 안전 정지 경로.
- 보존: CPU60Hz·촬영30Hz·정책20Hz, 원본 영상 크기/K/실측 pose/깊이 z-buffer·invalid mask, 검출·학습 가중치, 기존 Action 판정. MissionCameraSession의 새 processor 인자는 기본None으로 기존 사용자 경로 유지. 새 의존성 설치 없음.
- 검증: 기존 Student+새 전처리/시각/오류 회귀28, physics4, fleet2, vendor14 PASS. 실제 깊이80뷰와 비전 기록12개 일치. 동일 정차 카메라165촬영의 전체 frame69.7→41.3ms, RTF0.239→0.403. 실제 수확/다른 센서 부하에서의 성능은 별도. 공유 render 시간이 다른 계측 항목으로 옮겨가는 점을 명시한다.
- 기각: renderer 끄기/켜기는163.5ms로 악화해 제외. RGB/IR의 두 pass 필요성을 확인해 1pass 축소는 적용하지 않는다.
- 실행/복원: SEC07 4회차를 설정 개선 STOP으로 보존하고 격리 실제 ROS 팔 Action 확인 중. 자료 runs/camera_optimization_20261021. 완료 후 성공 예찰로 SEC07 수확 재개. 복원은 이번 카메라/processor/계측 diff만 역적용하며 CPU/캐시/주행 수정 유지. 미커밋·미푸시.

- 실검증 완료: 실제 ROS 팔 Action 29개 검증 항목 PASS, result SUCCESS/harvested1/failed0/safe_stopped=true, sim71.433초 완료. 운영 timeout 변경 없음. SDK 자연 종료0/process_exit, exception 없음. 수확 중 RTF0.2746(1sim초=3.64wall초), 복귀 RTF0.3765(2.66wall초). 단일 로봇·Nav2 없는 검증 조건이므로 기존 다중 로봇 캠페인과 동일 조건의 배속 비교는 아니다.

- 재배포 확인: SEC07_attempt_0005에서 physics_device requested=cpu/gpu_dynamics=false/broadphase=MBP 및 student_camera geometry backend=compiled_cpu를 직접 확인했다. 기존 예찰 재사용, Domain13/SUBNET·완료 SEC01~06 보존. 최종 소스 사본/해시는 runs/camera_optimization_20261021/applied 및 verification.json에 기록한다.

- 최종 연속 시험 확인(11:46 KST): SEC07 5회차는 수확 controller_server configure 응답 timeout 로그와 함께 Nav2 준비300초 실패로 원본 보존했다. 기존 감독자가 전체 스택을 자동 재시작했고 SEC07_attempt_0006은11:46:52 기존 예찰8window로 W001 Goal/feedback을 수신해 RUNNING/harvest다. 준비 오류 원인을 카메라 개선이나 DDS로 단정하지 않는다. CPU/compiled_cpu 설정 유지, 이후 SEC16까지 감독을 계속한다.


### 2026-10-21 14:12 KST SEC10 W001 접근 주행 전체 시간 초과

- 사용자 방금 NAV 실패 원인 확인 요청. 운영 변경 없이 원본과 공통 실행 경로를 분석했다. SEC07~09는 성공 완료했고 SEC10 1회차 W001의 SECTION_APPROACH에서 실패, 팔 SKIPPED다.
- 원인: 경로27.535m/희망속도0.1m/s로 직진만275.35초 필요. 실제 제자리회전 명령32.83sim초/감속48.78sim초가 더해져 공통 harvest_navigation.yaml/NavigationSettings의 goal_timeout_s=300을 초과했다. Nav2Client._wait가 ROS 시계300초에서 timeout을 발생시켰고 controller_server는 취소 성공을 기록했다.105/팔 실패/최종 도착 불일치로 분류하지 않는다.
- 근거: controller goal14:06:33.823→cancel14:12:38.773, cmd_vel_nav7300·최종cmd_vel7322메시지, odom 이동25.871m. 마지막 AMCL(-3.01386,-11.40379)로부터 남은 경로 약1.9m. 최종 프로세스 종료/-2 로그는 시험 정리 시점이다. 느린 wall시간 자체가300초를 소모한 것은 아니며 sim에서는 ROS 시간이 예산 기준이다.
- 공통/실물 영향: 동일 설정의 긴 경로/같은 속도라면 실물에서도 가능한 시간 예산 문제. 경로 길이·회전 여유를 반영한 예산 검토가 필요하며 이번에는 공통 설정/코드를 수정하지 않았다. 기존 자동 재시도로 SEC10 2회차 수확부터 진행 중, 예찰 재사용. 상세 runs/sec01_goal_time_fix_20261020_183345/SEC10_attempt_0001/failure_navigation_timeout_20261021.json. 분석 문서는 미커밋·미푸시.


### 2026-10-21 경로 길이 기반 공통 timeout 제안 — 승인 대기

- 사용자 “경로 길이에 따라 타임아웃이 달라져야할거같은데”에 따라 공통 변경안을 준비했다. AGENTS.md의 공통 소스 적용 전 구체안/명시 확인 규칙을 따른다. 운영 farm_navigation 소스/설정은 수정하지 않았다.
- 대상: nav2_client.py의 preflight에 선택 제어기 desired_linear_vel 읽기를 기존 RPC에 추가하고, 실제 FollowPath XY 누적 길이 L로 max(기존 goal_timeout_s, ceil(2*L/v+60))을 계산한다. TF 복구 바깥 예산과 각 FollowPath 결과 대기에 같이 쓴다. 실제 SEC10 조건27.535m/0.1m/s는611초. 현재300초는 하한이다.
- 영향: 공통 실물/시뮬 FollowPath에 같은 계산. 기존 진행 정체105·도착 범위·취소/응답 제한은 유지한다. 직접 경로가 없거나 제어기가 속도 파라미터를 제공하지 않으면 기존 제한 유지. 속도는 사전 점검 기준이며 동적 변경은 다음 점검 때 갱신한다.
- 검증: /tmp의 제안 소스만 별도 프로세스로 로드해 기존 시계/취소/TF 및 추가 경로 예산21검사 통과. 실제 Isaac 배포/실물 검증은 미실행. 적용 전 검토 자료 sim/runs/goal_timeout_proposal_20261021/{proposal.patch,README.md,proposed/,tests.log}. 기존 test_nav2_execution_clock.py 보완과 test_nav2_route_timeout.py 추가도 패치에 포함한다.
- 다음: 사용자 확인 후 공통 소스·검사 적용, 기존 검사/실패 경로 재시험. 승인 전 운영 적용/빌드/재시작 없음. 기존 자동 캠페인과 원본은 유지한다.


### 2026-10-21 경로 길이 기반 공통 timeout 적용 — D-052

- 사용자 “적용해” 승인 후 공통 nav2_client.py와 관련 시험2개에 제안 패치를 그대로 적용했다. `max(기존 제한, ceil(2*경로길이/설정속도 + 60))`초이며 SEC10 접근은 약611초다. 실물/시뮬 공통이며 기존105/도착/취소 조건은 유지했다.
- 적용 소스로 farm_navigation 전체 단위시험48개 PASS. 실제 ROS overlay에서 수정 함수 로드 확인. 원본 로그: `sim/runs/goal_timeout_proposal_20261021/applied_tests.log`, 적용 기록 applied_status.json. 기준 HEAD e145d9de 및 기존 미커밋 변경 보존, 이번 commit/push 없음.
- SEC10_attempt_0003은 배포를 위해 STOPPED로 정상 중단(주행 실패 아님). SEC01~09 완료 및 SEC10 성공 예찰8window/expected11을 보존한 채 attempt_0004부터 수확 재개했다. Domain13/SUBNET, CPU 물리와 기존 진단 기록기를 유지했다. 실제 장거리 접근 완료 여부 확인 중이며 실물 검증은 미실행이다.
- 되돌리기: 제안 proposal.patch의 이번3파일 변경만 역적용하고 시험 프로세스를 재시작한다. 다른 미커밋 변경은 되돌리지 않는다.

- **적용 후 실제 Isaac 확인 완료:** SEC10_attempt_0004에서 제한611초 로그 확인. SECTION_APPROACH는 약341.47시뮬초(벽시계401.85초)에 `Reached the goal!`로 완료해 기존300초 제한을 넘는 정상 주행이 성공했다. 이어 WINDOW_MOVE도 도착했고 팔 CAMERA_INVENTORY에 진입했다. SECTION 전체 수확 완료와 구별하며 캠페인은 계속 실행 중이다. 원본 stack.log/telemetry.jsonl 및 `sim/runs/goal_timeout_proposal_20261021/applied_status.json`에 도착 근거를 보존했다.


### 2026-10-21 복귀 중 불필요한 팔 카메라 중지

- 승인: 사용자 “그래 그렇게하는게 맞지”. sim 전용 student_session.py/student_camera.py 및 관련 시험2개에 한정한다. 공통/실물 제어는 변경하지 않는다.
- 원인: SEC10_attempt_0004 RETURN_STOW에서 카메라5218회 처리. 시뮬173.95초/실제688.21초 중 student_camera_s371.85초(약54%), arm_s6.30초였다. 일반 render126.03초와 카메라 내부 세부 시간은 중첩되므로 단순 합산하지 않는다.
- 변경: RETURN_STOW/FINAL_STOP에서 센서/렌더 제품을 pause한다. 다른 작업 단계에서 재개하며, 재시도 CAMERA_INVENTORY 진입 시 즉시 현재 자세로 새 촬영한다. 재개 시 누적 sequence/FK오차/촬영 기준시간은 유지하고 이전 영상 캐시는 비운다. 관절 피드백·복귀 경로·정지/레이저 판정은 유지한다.
- 검증: Isaac Python에서 student 관련30개 단위시험 PASS. 복귀/최종정지 중 중지, 탐색/수확 재개, 새 프레임 요청과 누적 계수 보존 확인. 실제 캠페인 성능 개선 배율은 아직 미측정이다.
- 배포: 기존 SEC11 시도를 STOP으로 정상 중단해 수정 모듈을 로드하는 프로세스로 재개한다. 이는 시스템 실패가 아닌 설정 적용 중단이다. 성공 SEC01~10과 예찰 캐시는 보존한다.
- 복원: 이번 stage별 카메라 활성 제어 및 reset_capture 선택 변경만 제거하고 프로세스를 재시작한다. 기존 영상 최적화/CPU 물리 변경은 유지한다. 커밋/푸시는 미실행.


### 2026-10-21 SEC01~16 전면 재예찰·수확 성능 캠페인

- 승인: 사용자 SEC01~16을 예찰부터 다시 밤새 실행, A/B/C와 누락 원인·중복·정량 비율, 오류 시 전체 재시작 후 같은 SEC 예찰부터, 동일 현상3회면 생략 지시. 공통 코드는 변경하지 않고 sim 시험 감독자/오프라인 보고서/시험을 수정했다.
- 새 캠페인: `sim/runs/sec01_16_fresh_metrics_20261021_172329`, 서비스 `farm-fresh-metrics-20261021.service`. Domain13/SUBNET, CPU 물리, 경로별 제한시간/복귀 카메라 중지 유지. `--fresh-scout --max-identical-failures 3`. 기존 캠페인은 정상 STOP 후 보존했다.
- FAILED에 한해 SEC/단계/가변 ID를 제거한 오류 서명별 누적3회면 skipped_sections 및 skip_reason.json으로 생략한다. 다른 오류는 별도 누적, STOPPED/INTERRUPTED는 실패3회에서 제외. 완료 상태 COMPLETE_WITH_SKIPS를 전체 성공과 구분한다. 기존 기본 재사용/무제한 동작은 옵션 없는 호출에 유지한다.
- A는 전체 배치 수를 별도 기록하고 비교 분모는 관측면/높이/경로 내 red/yellow다. B는 window expected, C는 레이저 통과다. A-B/B-C 개수 차이와 객체 대응 누락을 분리한다. 정답은 오프라인 평가에만 사용한다. ID 미대응을 AI 미검출로 확정하지 않고 가림/깊이/위치 오차 등 후보와 증거 미확인을 표시한다. 레이저 물체 ID 역시 확정하지 않는다.
- 원본 장면/예찰 RGB-D·좌표/윈도우 소속/팔 관측·시도·낙하·레이저·제어/주행·프레임 시간 및 코드·설정 snapshot/해시를 보존한다. 이전 비교 보고서는 previous_comparison에 복사, 전체 원본은 기존 폴더 유지. report.md/performance_summary.json/시도별 performance_report.json을 시도 종료마다 자동 갱신한다. 원본 파일 손상은 evidence_errors에 남기며 집계 전체를 막지 않는다.
- 검증: 감독자/보고서12개 단위시험 PASS. 3회 실패→생략→다음 SEC, 재개 시 생략 유지, fresh-scout 전달, 가변ID/운영중단 구분, 예찰 누락·윈도우 미생성·중복·팔 손실 분류 확인. 기존 실제 캠페인 로그로 새 보고서 생성 확인. 새 SEC01~16 결과는 아직 미완료.
- 되돌리기: 이번 감독자 옵션/실패 서명/보고서 분류 변경만 제거하고 기존 실행 옵션을 사용한다. 기존 CPU/카메라/공통 제한시간 변경은 유지한다. commit/push 미실행.


### 2026-10-22 야간 SEC01~16 완료 및 보고서 자료

- 사용자 요청으로 완료된 캠페인 원본을 조회해 `sim/docs/SEC01_16_NIGHT_TEST_REPORT_MATERIAL_20261022.md` 작성. 운영 코드 수정/재시험/커밋·푸시는 하지 않았다.
- 새 캠페인 sec01_16_fresh_metrics_20261021_172329는 KST10/21 17:23~10/22 06:50 COMPLETE,16SEC 완료/생략0,21시도 중 실패5회. SEC06 예찰105가1회 재발했고, 전방 목표 거부2회·준비 지연1회·정지 미확인1회가 있었다.
- 최종 성공 시도 기준133윈도우, A192/B180/C98, C/A51.0%. 객체별 예찰 윈도우 누락32개(최종ID 미대응23+검출 후 윈도우 없음9), 미대응 expected20개가 단순 A-B12개를 상쇄한다. 팔 대상 미선택53건은 AI 미검출로 단정하지 않는다. ID 대응/익명 레이저 및 사건 중첩의 한계를 자료에 명시했다.
- 자료의 SEC별 수치/합계/실패 목록을 summary.json, performance_summary.json 및 실패 stack.log와 대조했다. 원인 후보와 확정 관측을 구분했으며 parser evidence_errors0을 확인했다.


### 2026-10-22 시험 결과 및 검증 코드 Git 반영

- 사용자 “테스트 결과 커밋푸쉬해줘” 승인. 야간 시험에 사용한 공통 경로별 timeout/시뮬 CPU·카메라 최적화/복귀 카메라 중지/새 캠페인·보고서 코드와 결과 자료를 함께 반영한다. 별도 multirobottrafficcontrol 및 robotarm_harvest_communication 폴더는 제외한다.
- 원격 재검토용 완료 집계5개(summary/performance_summary/failure_analysis/manifest/evaluation_contract)를 `sim/docs/test_results/20261022_sec01_16/`에 보존했다. 대용량 원본 로그는 기존 로컬 sim/runs 경로에 유지하며 보고서에 상대 링크를 추가했다.
- 커밋 전 검증: farm_navigation48 + student30 + campaign12 =90개 PASS, git diff --check 통과. 실제 통합 결과는 야간16SEC 완료/실패 재시작5회 기록을 따른다. 실물 주행 시험은 미실행.

## 2026-10-22 — 공통 교통 클라이언트 및 시뮬 교통 프로파일

- 구분/승인: 사용자 공통·시뮬 적용 및 실물 인계 문서 작성 요청. 기준 main/0832b6f 이후 미커밋 변경.
- 대상: 공통 farm_interfaces/farm_navigation/예찰·수확 node/status/communication, sim farm_sim_config의 두 traffic runtime 및 traffic 등록 원본, setup.py, sim/.gitignore.
- 전후: 기존 기본 프로파일은 종전 주행 유지. traffic 프로파일에서는 등록·경로 전체 허가 후에만 Nav2 실행하며 진행 보고·반납·우회 및 초기화 중단을 수행한다. 실물 설정/실행 중 프로세스는 변경하지 않았다.
- 검증/제한/실물 인계/복원: `../../docs/changes/TRAFFIC_ROBOT_HANDOFF_20261022.md`. 실제 관제+Isaac 공동 25개 시험과 실물 주행은 미실행. 초기화 완료 이벤트는 관제 실행기 통합 지점으로 남긴다.
- 원격: commit/push 없음. 영속 ID DB는 시험 종료나 rollback 때 삭제하지 않는다.


### 2026-10-22 예찰 윈도우와 팔 실행 상자 범위 정렬

- 사용자 “팔 실행필터보다 예찰 윈도우 생성 범위가 더커서 … 해결” 요청. sim 설정만 수정했다. 공통 플래너/팔 실행 필터·실물 설정은 변경하지 않았다.
- 원인: 예찰 task.yaml의 팔 상대 높이는−0.10..0.35m 및 축별 여유0.02m였으나 실제 continuous_near_mask는 x0.265..0.365/y±0.175/z0.087..0.35m와 HOME 거리0.09<d<0.34m를 사용했다. 계획 pose로 야간 expected180개를 변환하면37개가 상자 밖(x29/z11, 중복3)이다.
- 변경:16SEC의 원본 task.yaml height_offsets 하한을0.087m, range_tolerance를0으로 정렬. 파생 scout_survey.json과 harvest_audit.json의 평가 상자도 재생성했다. 다른 생성 파일의 주석/키 순서 차이는 제외했다.
- 검증: 원본 map_detections를 관측 순서대로 공통 Survey에 재생한 결과 expected143개, 팔 상자 및 HOME 거리 필터 밖0개(부동소수 비교1e-9). 경로 검증16SEC/80관측/371경로 통과. 실제 Isaac/실물 주행은 미실행이며 실제 도착 pose·표면점/파지점 차이는 남는다.
- 근거: sim/runs/workspace_alignment_proposal_20261022/replay.json 및 aligned_replay.json. 기존 야간 결과192/180/98과 보고서는 수정하지 않는다. 새 높이 범위로 평가 분모도 달라지므로 후속 성능 비교에서는 전체 배치 수와 작업 범위 제외 수를 함께 표시해야 한다. 예상량 감소를 수확 성공 증가로 해석하지 않는다.
- 되돌리기: 위3개 sim 설정의 이번 높이/여유/기하 주석 및 파생 평가 상자 변경만 복원. 다른 작업자의 교통 제어 변경은 유지했다. 커밋·푸시 및 새 장시간 시험은 수행하지 않았다.


### 2026-10-22 전체 빨강·노랑 과실 작업 범위 확인

- 사용자 요청으로 공통 예찰 알고리즘과 sim 설정 책임을 확인했다. 공통 survey_core/b_planner는 불변, 직전 변경은 sim task/scout_survey/harvest_audit 높이·여유 설정이다.
- 야간 초기 snapshot192개(red96/yellow96) 중심점 중153개는 경로 내 정차 위치에서 현재 상자/HOME 조건 충족,39개는 초과(하한10/상한8/깊이25, 중복4). 실제 중심높이0.785711~1.071028m 대 실행높이0.800~1.063m.
-192개 모두 AABB 일부는 깊이/높이 상자와 겹침. 필터 입력은 중심이 아닌 영상 파지점이므로39개를 수확 불가능으로 확정하지 않았다. 실제 파지점/IK/충돌 검증은 미실행. 배치·팔 필터·공통 코드는 이번에 바꾸지 않았다.
- 근거 JSON은 sim/runs/workspace_alignment_proposal_20261022/all_ripe_coverage.json, 기존 시험 자료 MD §11에 한계와 결과 추가. 커밋/푸시 미실행.


### 2026-10-22 전체 빨강·노랑 작업 범위 내 재배치

- 승인: 사용자 “로봇팔 필터 조정은 성능 변수 … 밖에있는 열매들을 안으로 재배치해”. 팔 필터/예찰 범위/공통·실물 코드는 이번에 변경하지 않았다.
- 실제 장면 sim/assets/envs/output/farm_with_plants_v5.usd에서 빨강·노랑192개 중 실제 물리모델 외곽이 깊이/높이 경계 밖이거나 안쪽1mm 여유가 없는180개를 최소 이동. 중심만 벗어났던39개와 달리 외곽 기준이다. 나머지12개와 초록96개는 위치 유지. ID/색/회전/크기/개수 보존. 연결 줄기는 식물 쪽 끝 유지, 과실 쪽 끝만 이동했다.
- 깊이/높이 이동으로 새로 겹칠 수 있는7쌍은 베드 길이 방향 최소 이동으로 해소했다. 기존 AABB 겹침5쌍은 유지되며 새 겹침0쌍. 단위m, 전체 외곽 검증은 실제 runtime 과실 자산의 AABB를 사용했다.
- 검증: 저장 장면 재개방 후 재배치 후보0개.192개 모두 계획 상자 내 외곽 및 팔 box/HOME 범위를 만족하는 경로 내 정차점 존재. 실제 과실 중심을 평가 전용으로 공통 plan_harvest에 입력한 오프라인 시험에서192/192 window 소속 생성, 보류0. 원본 레이어 변경은 과실 translate180개+줄기 points180개만 확인. 실제 USD/PhysX 과실 자산 검사4개 PASS. 비전 검출/도착 오차/IK·충돌·수확 성공의 새 통합 시험은 미실행.
- 재현 도구 sim/tools/align_ripe_fruit_workspace.py는 기본 dry-run, --apply 명시 시 원본 백업 후 저장한다. 근거 및 이동 전후 좌표/해시: sim/docs/changes/FRUIT_WORKSPACE_RELOCATION_20261022.json. 원본 백업·검증 원문은 sim/runs/fruit_relocation_20261022.
- 기존 야간 시험은 이전 배치 결과이므로 그대로 보존한다. 이후 비교는 새 장면 해시/새 캠페인을 사용해야 한다. 복원은 백업 USD를 원래 장면 경로로 복사한다. 커밋/푸시 및 장시간 캠페인은 이번에 수행하지 않았다. 다른 작업자의 교통 제어 변경은 유지했다.


### 2026-10-22 역순 윈도우 전달 수정 — D-054

- 승인: 사용자 “그래 정렬해야지 순서대로가야지 …”. 실제 SEC14 W003→W004는6.1cm 역방향, SEC16은11.4cm 역방향이었다. 단순 정차 오차 추정에서 목록 자체 역순으로 원인을 확인했다.
- 공통 Survey.windows() 반환 시 실제 수확 heading의 map 방향 투영값으로 정렬한다. 윈도우 번호는 생성 ID로 유지하므로 예: W001/W002/W004/W003/W005로 전달될 수 있다. 생성 계획·멤버·예상량·좌표·구간 연결은 바꾸지 않는다. 실물/시뮬 공통 동작 변경이다.
- 검증: 실제 Survey 누적 관측에서 늦게 생성된 뒤쪽 창을4개 지도 진행 방향으로 검사(1test/4subcases) PASS, 기존 메시지 프로토콜6개 PASS. 야간 두 실패 report로 실제 task_messages 변환 후 모든 구간 전진 순서/ID·좌표·멤버·expected 보존 확인. 근거 sim/docs/changes/WINDOW_EXECUTION_ORDER_REPLAY_20261022.json. 실제 재주행은 미실행.
- 변경: robot/ros_ws/src/scout_robot/scout_robot/survey_core.py, test/test_window_execution_order.py. 이전 성공 캐시/완료 결과는 소급 변경하지 않는다. 복원은 반환 정렬을 제거하고 해당 회귀 시험을 원복한다. 다른 교통 코드/과실 재배치 변경은 유지했다. 커밋/푸시 미실행.


### 2026-10-22 영상 사용 단계에만 팔 카메라 활성화

- 승인: 사용자 “영상이 필요하지 않은 동안에는 켜져있을 이유가 없어”. sim student_session.py 및 test_student_retry.py만 이번에 수정했다. 공통/실물·전달 미션 상태기계는 변경하지 않았다.
- 기존 RUNNING 중 RETURN_STOW/FINAL_STOP만 제외하던 조건을 CAMERA_INVENTORY/HARVEST/WAIT_BOX 허용 목록으로 변경했다. TO_HOME/STOW_WAIT/PREPARE/정지·종료·주행에서는 촬영/렌더 제품을 pause한다. WAIT_BOX는 실제 영상 정책이 계속 호출되므로 유지한다.
- 같은 tick에 TO_HOME→HARVEST로 전환되는 경우, sim 미션 세션 어댑터의 step 경계에서 지연 capture_provider를 호출해 새 현재 자세 프레임을 확보한 뒤 영상 정책에 전달한다. 기존 사용자는 provider 미지정 시 원래 camera.step을 그대로 사용한다. 재개 시 누적 촬영/FK계수는 유지한다.
- 검증: student 관련32개 PASS. 상태3종×단계10종 활성 조건, 정책 첫 호출 전까지 비활성, 재개 직후 새 프레임 전달/불필요한 재개 반복 없음, 기존 재시도/레이저/복귀 완료 회귀 포함. 실제 Isaac 성능 배율은 새로 측정하지 않았으며 새 장시간 시험/커밋·푸시는 미실행. 다른 작업자 및 이전 미커밋 변경은 유지했다.
- 복원: 이번 허용 목록 및 지연 촬영 어댑터 변경만 제거한다. 이전 복귀 카메라 중지/카메라 처리 최적화/과실 재배치/윈도우 정렬은 유지한다.


### 2026-10-22 2차 SEC01~16 시험 시작

- 사용자 “2차 테스트 가자” 승인. 새 캠페인 `sim/runs/sec01_16_round2_20261022_151624`, 서비스 `farm-round2-20261022.service`로 시작했다. 성공 예찰 재사용 없이 SEC01부터 매 시도 예찰→모든 window 수확. 같은 오류 누적3회면 SEC 생략, 그 외 실패는 전체 Isaac/ROS 재시작 후 해당 SEC 예찰부터 반복한다.
- Domain13/SUBNET, CPU/headless, 기본 교통 비활성 프로파일 유지. 수정된 공통 예찰 정렬과 sim 카메라 활성 조건의 실제 ROS/Isaac Python 모듈 로드를 확인했다.
- 과실 재배치 USD(sha256 22be2e1f423ab553eee3d471f321ea2fb49761a6cab8ddfe0648d6d3182207f3), 범위 정렬/태스크 진행 방향 정렬/영상 단계 촬영 조건 적용. 장면 복사·코드 해시는 round2_contract.json, 이전 비교 결과는 round1_comparison에 보존했다. 배치가 바뀐 비교이므로 알고리즘 단독 개선 효과와 구분한다.
- A/B/C·객체별 손실/중복/성능 사건·실패/명령체인/RPP/프레임 시간 기록 및 시도 종료별 report.md 자동 갱신. 새 결과는 아직 미완료다. 시험 시작 자체에 따른 코드 변경·커밋·푸시는 하지 않았다.


### 2026-10-23 2차 예찰/복귀/진입/준비 오류 원인 분석

- 사용자4항목 분석 요청으로 운영 코드는 수정하지 않고 동결 소스·원본 로그·오프라인 수치 재현을 대조했다. 근거 sim/docs/changes/ROUND2_FAILURE_ANALYSIS_20261023.json 및 ROUND2_* 상세 JSON.
- 동일15SEC 검출 객체 대응은157→160으로 감소하지 않음. 실제 윈도우 대상은148→131로 감소. 검출 후 미소속29개는 모두 깊이 hold이며 map 변환 오차12~36mm와 여유0 조합. 실제 시뮬 차체 자세로 재변환하면29개 모두 범위 내(최근 진단 pose 최대0.45시뮬초, 정지 촬영). 이전2cm여유 재생시 expected152→184이나 실행 범위 문제를 가릴 수 있어 그대로 복원하지 않았다.
- SEC09는1차에 팔 대상이 아니던 동일 Pepper_0033_yellow가 낙하한 뒤60초 만료, 기존 고정XY/13cm상승 복귀 IK가15.7~22.6mm 오차로15mm한도를 초과. 함수는1/2차동일. 현재TCP높이1.004~1.009m는 상자여유높이0.881m보다 높았으나 추가13cm상승을 요청했다.
- SEC12/16 작업 진입 실패는 역순이 아님. 전체TF기록 실패 직전 재구성에서 목표전방12.7/9.0cm, 횡오차1.81/1.28cm, 차체방향오차−0.28/+0.04도, 목표선각둘다8.1도로3도제한초과. 함수/설정은1/2차동일. 도착5cm허용과 짧은구간 진입3도기준 불일치다.
- 준비2회는 양 로봇odom15~17초에정상, harvest Nav2 active 후 scout bt_navigator configure전이 또는 get_state서비스발견에서정체. 300초부팅지연으로 보지않는다. SHM lock오류는 성공시도에도있어 단독원인확정불가. 정확한 내부대기/DDS경로는 추가계측이 필요하다.
- 수정/실제재주행/커밋·푸시는 수행하지 않았다. 후속 우선순위는 예찰map정합, 도달가능한복귀후보, 짧은직진기준정렬, lifecycle단계계측이다.


### 2026-10-23 예찰 좌표 정합 심층 분리 조사

- 사용자 “파악할수있는만큼 … 아주예전부터” 요청. 운영 코드/설정/장면은 수정하지 않았다. 실제 USD/URDF 센서 장착과2차75개관측, 실제물리자세/encoder, 원시태그1090개, 태그투영212개를 대조했다. 상세 sim/docs/changes/SCOUT_LOCALIZATION_DIAGNOSIS_20261023.json 및 LOCALIZATION_* JSON. 재현스크립트는 sim/runs/round2_failure_analysis_20261023.
- D435 렌더광학프레임과URDF프레임의행렬차이0, PiCam실장과설정차이약1e-13. 같은실제행렬이CameraSim metadata/TF에연결됨.75개촬영/pose stamp차이0, 공통코드는촬영시각TF를조회함. 독립렌더시각계측까지완료한것은아님.
- map평면자세가과실깊이에주는오차평균약16.0mm, 실제roll/pitch를2D에서생략한깊이영향평균0.159mm(높이영향2.35mm). 현재깊이누락의주원인은장착행렬이나기울기가아닌평면위치/방향추정.29개제외점은실제자세재변환시모두깊이범위내.
- 태그보정이실제로켜져있어LiDAR단독원인으로해석하면안됨. 원시태그후보홀수SEC502개는바깥쪽평균20.50mm,짝수588개는8.29mm편향.212개투영표본에서태그변검출폭은약49px대비홀수0.863px/짝수0.348px작음. 렌더/검출코너/시각기여는아직분리미확정이며단순보정상수를적용하지않음.
- 바퀴odom은회전에서실제각도와불일치:SEC01표본실제/odom0.890,SEC03 0.936;같은직진비는약0.9985. USD바퀴간격0.159999996m로설정0.16m와일치. 접촉/미끄러짐/가속기여미확정. AMCL/태그가큰누적오차를보정해도cm잔차는남는다.
- §38(10/13)에이미PiCam태그횡3.72cm/진행7.16cm/yaw3.41도정확도미달기록이있다. 기존정합문제에예찰여유0이겹쳐expected누락이표면화된것으로확인했다. 후속은동일포즈태그ON/OFF·정지태그픽셀위상/거리·회전전용encoder/실제비교. GT는평가에만사용한다. 커밋/푸시·3차실험미실행.

### 2026-10-23 예찰 위치 정합 통제 비교 시작

- 승인: 사용자 “그래 비교해봐”. 목표는 태그 보정/정지 영상 측정/바퀴 회전 오차를 분리하는 것이며 공통 알고리즘·운영 설정·실물 코드는 수정하지 않는다.
- `sim/runs/localization_compare_20261023`에 평가 전용 실행 도구와 원본 로그를 분리. 기존 캠페인 worker에서 수확 요청만 생략한 시험 worker를 사용하며 예찰은 실제 공통 ScoutArea Action을 그대로 호출한다.
- SEC01, 매회 전체 재기동, CPU 물리·headless·Domain13/SUBNET. 태그 보정 ON/OFF/OFF/ON 순서로 반복. 마지막 예찰 완료 후 개방루프 ±0.25/±0.5rad/s 회전에서 encoder/실제 물리 자세를 평가한다. 정답은 제어 입력으로 사용하지 않는다.
- 주행 스택 종료 뒤 정지 태그 RGB/동일 프레임 CameraParams를 거리·화소 위상·각도별 수집하고 운영 apriltag_ros에 재생한다. 실행 서비스 farm-localization-compare-20261023 및 farm-localization-static-20261023. 현재 실행 중이며 최종 결과는 별도 기록한다.
- 기존 소스/설정 복원 불필요. 중단은 해당 runs/STOP 파일과 이번 시험 서비스만 대상으로 한다. 커밋·푸시 미수행.

- 재개: 사용자 컴퓨터 종료/재부팅으로 세 번째 OFF 예찰 도중 중단. 성공한01 ON/02 OFF는 보존했다.03 중단 결과를 로봇 오류와 구분한 `INTERRUPTED_HOST_REBOOT`로 기록하고 `sim/runs/localization_compare_20261023/interrupted/03_tag_off_before_reboot`에 원본 및 생성 산출물을 보관했다.03 OFF부터 전체 초기화 후 재실행하며04 ON·회전·정지 광학 시험을 이어간다. summary는 기존 성공 결과를 유지하도록 시험 runner만 수정, scan 수집은 append로 변경했다. 운영 소스/설정 영향 없음.

- 추가 진단: 사용자 “최대한 원인 찾아서 해결” 범위에서04 완료 후 정지 AMCL `request_nomotion_update` 12회 효과를 평가한다. 감독기 메인만 SIGSTOP/SIGCONT로 순차 실행을 대기시키며 로봇/Isaac는 계속 실행한다. GT 입력·운영 소스 변경 없음. 정지 RGB 비교에는 실제 기본값 DLSS 성능(AA3/execMode0), DLSS 품질(3/2), TAA(1), AA없음(0)을 추가했다. 근거는 설치된 SimulationApp 기본 anti_aliasing3 및 isaacsim.exp.base.kit의 dlss.execMode0이며 실제 렌더 설정/같은 RGB 시각의 CameraParams도 저장한다. 원인 확정 및 설정 적용 결과와 구분한다.

### 2026-10-23 태그 텍스처 축소 편향의 시뮬 전용 개선 적용/검증 중

- 승인: 사용자 “최대한 원인 찾아서 해결”. 실제 정지 영상과 같은 시각 CameraParams를 사용한 태그104 측정에서 기본 텍스처의 거리 편향 평균25.7mm, 이상적 PNG 투영은 절대1.51mm 이내. 검출기 decimate1/2, DLSS/TAA/AA없음, 기본 USD 투영 K 정렬만으로는 해결되지 않았다.
- 같은 크기/패턴을 흑백 기하 셀로 표현하면 기본 렌더 조건 평균10.6~11.3mm로 감소. 색·조명/화소 위상·평면 PnP에 따른 잔차는 남으며 완전 해결로 기록하지 않는다. DLSS 품질 변경은 평균5.0mm지만 최대21.3mm 잔차 및 다른 카메라 성능 영향이 있어 적용하지 않았다.
- 최소 적용: sim/tools/build_apriltag_assets.py에서 기존 제공 PNG의36h11 8×8셀을 생성 배치표 pattern_cells로 보존. sim apriltag_scene.py는 원래 종이/PNG/인쇄ID 위 코드 영역에만 동일 크기64개 기하 셀을10µm 띄워 표현한다. 기존 배치표에서는 기존 텍스처 방식으로 호환된다. 운영/실물 공통 알고리즘·필터·검출 설정·카메라 K/TF·장면 USD는 이번에 변경하지 않았다.
- 수정 파일: 위2개, sim config/apriltag_map.json 및 기존 sim/tests/test_apriltag_assets.py, tools/check_apriltag_scene.py. 새 설치 의존성 없음. 원본240태그의 좌표/크기/ID/텍스처 등 기존 JSON필드는 HEAD와 완전히 동일함을 비교했다.
- 검증: 패턴15개를 실제 PNG/정식36h11 사전과 대조한 기존3검사 PASS. 실제 USD 전체240태그의 기하 크기50mm·셀색/순서·면위치 및 기존 종이/광학프레임 검증 PASS. 현재 기본 렌더·CPU·Domain13/SUBNET으로 SEC01 실제 예찰 검증 중: sim/runs/localization_compare_20261023/05_geometry_tag_on. 결과 후 적용 유지 여부를 결정한다.
- 원상복구: pattern_cells 필드 없는 원래 배치표를 사용하면 기존 표현. 이번5개파일 diff만 되돌릴 수 있다. 다른 작업자의 미커밋 변경은 보존한다. 커밋/푸시 미수행.

- 적용 후 결과: 첫시도는 촬영전 TF102(요청17.116668초/latest16.750001초), 원본 보존 후 전체 재시작. 재시도 SEC01 SUCCESS, 5관측/9윈도우/expected14/실제윈도우대응11of13. 원시 태그 법선 편향−16.32mm(기존ON−22.49/−22.94), 차체 법선 절대13.02mm(기존15.85/16.23), 과실 깊이 절대17.65mm(기존17.54/21.64). 최종오차는 기존ON범위 내 단회검증으로 전체해결/확정개선이라 하지 않는다. 개선은 적용 유지하되 여러SEC/수확 재검증은 남음. TF102·AMCL잔차·회전물리는 별개 미해결이다. 보고서 SCOUT_LOCALIZATION_COMPARISON_20261023.md 및 changes/LOCALIZATION_CONTROLLED_COMPARISON_20261023.json에 원본/정량근거 보존. 커밋/푸시 미수행.
- 종료 확인: 모든 실제 예찰/렌더/검출 비교 완료 후, 첫 기하 진단의 SDK 예외로 종료 대기 중이던 단일 서비스 farm-localization-vector-20261023만 종료해 GPU 메모리를 반환했다. 예외 원본 보존. 사용자 작업 프로세스는 종료하지 않았다.

### 2026-10-23 AMCL/회전 물리 분리 및 예찰 캐스터 접촉 개선

- 승인: 사용자 “그것도 진행해” — 직전 보고의 AMCL잔차·회전물리 분리 검증. 원본 `sim/runs/localization_motion_20261023`. 공통/실물 코드와 주행 설정은 변경하지 않는다.
- Nav2/업무/카메라/LiDAR를 끈 별도 Isaac+장치 launch에서 단일 cmd_vel 발행자를 확인하고5조건 비교: 기존, 캐스터 재질마찰0(기본 평균결합), 바퀴damping10배, 캐스터마찰0+min결합, min결합+damping10배. 각조건 좌우±.25/±.5rad/s 및 전후직진/정지, 매회 전체재시작. GT는 평가에만 사용했다. 준비 시 station파일 누락/상위USD의m·Z메타데이터 누락은 별도 preparation_failure 로그에 보존 후 보완했다.
- 기존 caster는고정상자이며별도접촉재질없음. 단일발행자에서도 실제/encoder회전0.948~0.965, 낮은명령누적각추종약19% 재현. caster재질0만 적용하면0.973~0.988/명령추종51~52%. min결합까지적용하면0.9950~1.0038/저속명령추종79~80%, 고속89~90%. damping10배만으로는개선없음, min+damping10배추가이득없음.
- 적용: `sim/assets/robots/scout_robot/urdf/scout_robot_camera_fixed.usd` 캐스터 충돌체에 정/동마찰0·반발0·frictionCombineMode=min 재질만 연결. 자유롭게구르는수동캐스터를마찰없는지지접촉으로근사, 실제캐스터의완전한구름저항모델은아님. 바퀴형상/구동gain/질량/odom치수불변. 원본백업 `scout_before_caster_fix.usd`, 재현도구 `sim/tools/configure_scout_caster.py` 기본dry-run/--apply 및기존백업덮어쓰기거부.
- 실제Sdf모든spec비교 및재개방검사PASS: 새캐스터재질과해당충돌체binding외수정없음(asset_diff.json). 기존Nav2/AMCL/태그그대로SEC01 실제예찰검증중(06_caster_fix).
- AMCL: 실제동일scan·encoder·추정초기분포를실제farm_tag_amcl에별도namespace재생, GT입력없음. 기본/360빔/σhit.05 비교각3회(동일seed로수치재현,독립통계표본아님). 정지수동10프레임동안갱신1회,nomotion35회강제후에도Y잔차약142/150/204mm. 실측지도점수의5cm이동민감도X3.7%/Y0.13%,360빔도유사. 길이방향관측부족이며단순대기/빔추가/σ축소는해결책으로적용하지않음.

- 최종검증: 06_caster_fix SEC01 SUCCESS, 5관측9윈도우expected13/평가13/윈도우대응13, 차체법선11.17mm/yaw.407도/과실깊이12.27mm. 직전태그개선05는13.02mm/1.135도/17.65mm. 각1회이며다른SEC/수확미검증. 속도솔버1→8도개선없어미적용. 6물리조건모두worker_code0.
- AMCL공통후보: 동일영상복수태그의6D PnP 사전검증 및품질/불확실성/fallback/실물영향을 MULTITAG_LOCALIZATION_PROPOSAL_20261023.md에 구체화, 공통코드미적용/승인전. 정답보정/도착완화는없음. 원본/결과/소스해시는 SCOUT_MOTION_AMCL_ISOLATION_20261023.md 및changes/동명JSON. 전태그보고서의SEC01 분모12는원본13으로검산·정정했음.


### 2026-10-23 예찰 복수 태그 공통 관측 적용 (D-055)

- 승인: 사용자 “예찰은 거리가 머니까 복수태그 적용해도 괜찮을듯 반영해봐”. 공통 farm_tag_localization observer/runtime/node/pixel_bias와 회귀시험, 시뮬 예찰 모델 ID만 수정. 실물/수확 프로파일·AMCL 보정량·주행·Action 판정 불변. 기존 미커밋 교통/팔 변경 보존.
- 동일 시각/활성구간의 기존 usable 태그2개 이상을 coplanar IPPE+LM 6D로 계산. 각 태그/전체 RMS·거리·높이/기울기·동일 공분산 검증, 부족/불량/모호 시 단일 fallback. 공분산 축소 없음. 단일 pixel-bias 적용 차단. 별도 모델 ID/원본 IDs/각 RMS/거부 이유 기록.
- 회귀76개 PASS(신규11개 포함). 기존 수확 launch stub의 transfer_parameters 누락으로15개 ImportError는 별도 미통과 기록. 원시 로그재생05/06 복수선택116/67프레임, 같은표본X/Y13.56/24.99→5.45/10.83mm 및13.72/17.68→6.26/13.48mm. 정답은 사후평가에만 사용.
- Domain13/SUBNET/CPU/headless 실제 SEC01 예찰07 첫시도 SUCCESS,5구간9윈도우expected13/실제대응13of13,105없음. 복수선택12회/태그부족54회/복수품질거부2회,보정요청61회. 직전06 대비 과실깊이절대12.27→11.74mm,차체법선11.17→10.66mm이나yaw.407→.446도로 단회 개선폭 제한. 실물/다른SEC/수확 미검증.
- 상세 sim/docs/changes/MULTITAG_IMPLEMENTATION_20261023.md 및JSON, 원본 sim/runs/multitag_validation_20261023. 시험종료·프로세스정리. 복원은 시뮬예찰 model_ids.tag_multi 제거(기능OFF) 또는 이번 공통diff만 되돌림. 미커밋/미푸시.


### 2026-10-23 정지 촬영 전 실제 태그 보정 확인 (D-056)

- 승인: 구체적인 첫 촬영 전 보정 공백 개선안에 사용자 “ㅇㅋ 그렇게 ㄱ”. 공통 TagControl에 현재 token/구간/로봇/지도/시각이 맞는 실제 AMCL 적용 이벤트 확인, SegmentProgressState 촬영 전에 정지 상태에서 해당 구간 권한을 열어3회/최대8초 확인 후 새 시각 capture 요청. finally에서 사용권 종료. 적용 부재는 사유를 저장하고 예찰 진행. 접근 중 보정/이동계약/AMCL gain·공분산/Action 판정 불변.
- 신규10개 및 기존 프로토콜/이동/정렬/사용권/복수태그 총34개 독립 회귀 PASS. harvest 사용권 mock에 신규 구독 API만 추가. 다른 교통/주행/팔 미커밋 작업 보존.
- Domain13/SUBNET/CPU/headless 실제 SEC01 첫 시도 SUCCESS,105없음. 첫 촬영 위치추정 기여 과실깊이절대34.62→6.53mm,전체11.74→7.70mm,차체법선10.66→5.42mm. 단회비교. yaw평균.446→.770도로증가,검출13개/윈도우대응12of13으로 후퇴도 있음. G03 보정1회 후8초timeout,같은촬영F0009 depth_out_of_range hold. 이를 숨기거나 범위완화하지않음. 남은 방향잔차/단일태그편향·관측부족은 미해결.
- G01~05 대기2.61/2.31/8.04(timeout)/3.43/3.27초, 총19.67초. 첫촬영공백개선과전구간정확도해결을구분. 실제/추정자세로동일카메라점을재변환한오차이며 센서측정포함전체과실오차아님. 실물/다른SEC/수확미검증.
- 상세 sim/docs/changes/SCOUT_CAPTURE_TAG_SYNC_20261023.md 및JSON, 원본sim/runs/capture_tag_sync_20261023(소스사본/해시/시험/적용이벤트보존). 실행종료·시뮬정리. 복원은이번TagControl/SegmentProgressState diff와관련시험만대상. 미커밋/미푸시.


### 2026-10-23 추가 정지 없는 예찰 태그 보정 (D-057, D-056 대체)

- 승인: 시간 증가 없이 정확도/윈도우 누락을 개선한다는 제안에 사용자 “그렇게 잡고 ㄱ”. 공통 SegmentProgressState의3회/8초 촬영 전 대기 및 미커밋 TagControl 대기 API 제거. 기존 capture after_stamp 경로 복원. TagControl/NavigationMoveState에 section_start 목표pose 전달, Lease는 유한성/같은token 불변검증. 다른 교통/주행/팔 미커밋 변경 보존.
- adapter는 목표0.1~0.5m/방향30도/TF0.5초 이내의 접근에서 유효 복수 태그만 보정. 마지막0.1m 새 요청은 동결. 실제 적용된 복수태그 기준3초/odom0.3m/회전20도·동일token 안에서 단일gain0.5→0.1, 그외기존0.5. 별도 카메라/정지대기·공분산축소·PnP prior·Nav2속도/도착/Action판정 변경 없음. 실물/수확 설정 미변경(복수모델OFF에서는 접근보정OFF).
- 회귀100 PASS, 기존 수확launch stub transfer_parameters 누락15개 ImportError는 별도 미통과. Domain13/SUBNET/CPU/headless 실제 SEC01 기준07/11 2회평균137.51초/깊이위치추정기여11.60mm. 초기무대기09/10 평균140.25초/6.23mm로 시간조건미달. 마지막10cm동결 최종12/13 평균138.60초/8.14mm, 각9윈도우expected13/대응13of13,holds없음/성공실행105없음. 정확도약29.8%개선이나 실제시간평균+1.09초(+0.79%)로 **엄밀한 시간비증가조건은 아직달성/입증하지못함**. 명시적촬영대기0과시간비증가를구분한다.
- 실패도보존:12최초시도는odom/clock정상이나 scout map_server configure/harvest bt_navigator configure 준비정체로goal전종료후재기동. 둘째시도ActionFAILED102: RPP가11.350001초요청/latestmapodom10.950001초(0.4초부족),완료구간0/태그보정요청전. 이후전체재시작성공. 정확한lifecycle내부원인은미확정. 두실패는preparation_failures원본/진단에남김.
- 기준11은보존07공통소스를잠시실행후4파일finally복원(다른동시수정은해시검사로보호),최종소스해시일치검증. 최종근거sim/docs/changes/SCOUT_NO_WAIT_LOCALIZATION_20261023.md/JSON,원본sim/runs/scout_no_wait_20261023. GT평가전용. 실물/다른SEC/수확미검증. 모든시험종료/개선코드적용상태,미커밋/미푸시. 복원은이번TagControl/Node/runtime/tag_adapter/NavigationMoveState diff만대상,촬영즉시진행은기존상태유지.


### 2026-10-23 예찰 깊이 방향 ±2cm 판정 여유 (D-058)

- 승인: 사용자 “그정도면됐고 … 허용 범위를 … 넓히자”, 축 질문에 “베드 깊이 방향에 ±2cm 추가” 선택. 직전 D-057의 실제시간+1.09초/정확도 개선 수준 수용. 기존 수치를 바꾸어 시간비증가 달성을 주장하지 않는다.
- 공통 b_planner Config.depth_tolerance 기본0, survey_core harvest.depth_tolerance_m 연결. 신규 생성/기존 창 편입/재검증/관측 목록 모두 깊이 축에만 추가. 시뮬 task.yaml SEC01~16 .02 지정,공식build로 scout_survey.json만재생성. 실제 명목 작업 깊이10cm·팔필터/높이/진행방향/실물설정/과실배치/경로 불변. 판정 깊이만14cm(±7cm). 보고서·허용범위마커도 깊이 여유 반영, 기존 교통/정렬 변경 보존.
- 신규6+기존프로토콜6/정렬1 총13회귀 PASS, route검증16SEC/80관측/371경로 PASS. 저장된기존Plan/등록좌표 재생에서08case expected12→13/hold1→0,기존9창물리위치보존. 최근5기록13→13/hold0유지. 실제Isaac/수확/실물 재시험은하지않음.
- 상세sim/docs/changes/DEPTH_WINDOW_ALLOWANCE_20261023.md/JSON,원본sim/runs/depth_window_allowance_20261023. 복원은시뮬depth_tolerance_m=0및예찰파생만재생성. 미커밋/미푸시.


### 2026-10-23 작업구간 짧은 이동 실패 원인 추가 확정

- 사용자 원인 조사 요청. 운영 코드/설정 수정 없이1·2차 원본 로그, 동결 소스, 실제 차체 진단을 대조. 상세 `sim/docs/changes/APPROACH_ROOT_CAUSE_20261023.md`/JSON.
- 최초 베드 진입이 아니라 윈도우 사이 이동 전 resume_current의 straight_plan 각도 검사 실패. 중복 관측 ID가 별도 겹치는 창을 만들어 목표 간격SEC12 8.98cm/SEC16 4.70cm가 됐고, 기존 허용 횡오차를 가까운 목표선3도 조건이 거부. 팔 작업 중 실제 차체 이동은1mm 미만이며 실제 자세로도3도 초과.
- SEC12 관측 쌍9.4~9.6cm가 실제 자세 재변환 후4.1cm로 줄어6.5cm 연결 기준 내. SEC16은 재변환 후도8.6cm로 표면점 차이 기여가 남음. GT는 평가 전용,0.90~0.95시뮬초 진단 보간 한계 표시.
- 1차SEC16 attempt2에도 관련 중복/역순창으로 WORK_TARGET_NOT_AHEAD 실패 존재. 2차는 순방향 정렬됐지만 가까운 전방 목표 조건에 걸림. 판정 두 소스는1·2차SHA256 동일. ‘1차 관련 문제 없음’ 해석 정정.
- 공통 주행의 짧은 구간 경로/허용 조건 정합이 필요하며 미적용. 실물 가능성/실물 재현을 구분. Isaac 재실행·커밋·푸시 없음.


### 2026-10-23 짧은 작업구간 전방 이동 조건 수정 완료

- 승인: 사용자 “그래 해 작업”. 공통 farm_navigation/parallel_approach.py에서 목표선각 제한을 제거하고 차체yaw/횡오차/전방 조건을 독립 유지. 순수횡이동의 부동소수점 잔차는 전방1e-9m 이하 거부. 새 제어기/설정 변경 없이 기존 실제 목표·FollowPath 유지.
- 새 회귀5+기존48=53개 PASS. Domain13/SUBNET CPU/headless 실제 Isaac HarvestTask 이동 전용2회 SUCCESS: SEC12 6.72초/최종3.33cm·1.74°, SEC16 5.76초/최종2.15cm·0.25°. 시작위치는 실패추정XY, yaw는정렬. 과거전체상태/팔수확 검증과 구분.
- 기존 RPP 제자리 방향 보정 명령은 있었고 실제진단yaw 최대4.77/5.14°.3도는 시작/최종 판정이며 주행중 무회전 보장은 아님. 샘플 횡오차초과 없음, 충돌검사 유지.
- 준비프로파일 오류와SEC12 lifecycle 응답10초만료를 별도보존, 시험도구60초로 재시도성공. 종료단계Isaac−11은 Action성공후 supervisor종료 중 발생. 상세 sim/docs/changes/PARALLEL_APPROACH_FIX_20261023.md/JSON 및 sim/runs/parallel_approach_fix_20261023.
- 실물/전체SEC 수확 미검증. 중복 ID는미해결. 다른작업변경보존, 미커밋/미푸시.


### 2026-10-23 반복 시작 준비 오류 응답 손실 경로 확인

- 사용자 반복문제 지적에 저장로그/설치헤더/동일릴리스공식소스확인. SEC05 bt_navigator configure 후change_state응답송신실패가직접확인됨. 다른기간AMCL/map/planner/smoother에도동일경고. rmw_fastrtps8.4.4의응답구독자매칭실패→RMW_RET_TIMEOUT,Nav2기한없는change_state응답대기가300초전체실패로확대하는경로확인.
- SEC16 get_state서비스발견불가/Creating정체는별도형태이며동일근본원인미확정. SHM경고만으로원인단정안함. 상세sim/docs/changes/STARTUP_RESPONSE_DIAGNOSIS_20261023.md/JSON. 운영변경/신규시험/커밋/푸시없음,해결완료아님. 다음은단계별응답/스택계측과시험전용동시기동·전송비교.


### 2026-10-23 반복 시작 준비 오류 통제 재현/버퍼 포화 경로 확인

- 사용자 “확인해봐 이유가있겠지”. Isaac없는실제Nav2 map_server+manager 부하에서동일응답누락재현. 별도GetState는inactive, manager GDB는change_state 응답 무기한대기.
- 32쌍동시×6묶음: 기본20/192실패·호스트UDP수신버퍼드롭204247, DDS수신버퍼만확대0/192·드롭0, UDP전용4/192·드롭166434. 기본수신상한212992B→시험XML요청2MiB/커널상한4MiB. SHM단독원인아님. 부하시험결과를실운영실패율로해석하지않음.
- 정상전체구성기본4회성공,후보버퍼2회모두18초대양로봇active. CPU/headless Domain13/SUBNET,이동/수확명령없음. 운영프로파일·공통코드·sysctl변경없음. SEC16 Creating/get_state불가형태는동일원인확정아님. 상세sim/docs/changes/STARTUP_RESPONSE_DIAGNOSIS_20261023.md/JSON,원본sim/runs/startup_discovery_20261023.
- 다음권장: 시뮬기동에검증한DDS버퍼프로파일연결. 응답대기상한/상태기반복구는별도검토. 미커밋/미푸시.


### 2026-10-23 전체 시뮬 기동 DDS 수신 버퍼 기본 적용

- 승인 사용자 “그래 좋아 잘했어 수정해”. sim config fastdds_discovery.xml의listenSocketBufferSize2MiB를all.launch.py에서scoped자식환경에기본연결. 기존외부DDS프로파일은보존/로그표시. setup기존glob포함,실물/공통/전역환경/sysctl/기동제한불변. 개별launch직접실행은미적용.
- 신규4+기존7=11개PASS. 외부프로파일미지정일반명령으로실제CPU/headless Domain13/SUBNET전체기동2회모두양로봇active18.690/18.080초,응답누락0. DDS발견소켓64개수신상한4MiB확인. 이동/수확Goal없음.
- 상세sim/docs/changes/STARTUP_DDS_BUFFER_FIX_20261023.md/JSON,원본sim/runs/startup_discovery_20261023/full_integrated. 모든Creating정체해결보장은아님. 미커밋/미푸시,시험프로세스종료.


### 2026-10-23 사용자 요청 커밋·푸시 준비

- 사용자 “이상태로 커밋푸쉬” 승인. 예찰 창/과실 정렬·배치/태그 표현·캐스터/복수태그·추가정지없는보정·깊이±2cm·팔카메라활성·짧은전방이동·DDS기동프로파일과관련시험/보고서만선별했다. 다른작업자의교통코드/설정/문서는작업트리에보존하고혼합파일도해당부분제외.
- 이번직접회귀148개PASS,git diff --cached --check PASS. 기존 farm_tag_localization test_launch_contract의transfer_parameters mock ImportError15개는범위밖기존오류로제외명시. 결과sim/docs/test_results/20261023_regression.json. 실제Isaac결과는각상세보고서따름,실물검증미실행. 대용량sim/runs원본은로컬유지,재검토용수치/분석JSON은함께커밋.
- origin/main직접조회0832b6f로로컬기준과일치확인. git fetch는로컬refs/codex/turn-diffs 임시참조의누락객체때문에실패해원격직접조회로대체했고임시참조는변경하지않음. 이항목작성시커밋/푸시대기,최종원격반영상태는해당커밋과최종보고참조.


### 2026-10-23 3차 SEC01~16 시험 시작

- 사용자 “3차 테스트 시작” 승인. 기준92ad63a 및교통미커밋변경보존/기본교통비활성프로파일. 새캠페인 `sim/runs/sec01_16_round3_20261023_151213`. 매시도새예찰→모든반환창수확, 오류시전체재기동/동일SEC재시도,동일오류누적3회SEC생략. Domain13/SUBNET CPU/headless. 팔복귀/새모델건은보류해현재모델유지.
- A/B/C,객체대응/중복/누락원인,원시실패로그를기존평가기로기록. 추가태그소스/XML/장면/캐스터스냅샷과round3_contract.json 보존. 별도읽기전용RPP/명령체인기록기포함. 독립백그라운드감독PID1571501,종료시기록기정리.
- SEC01_attempt_0001 준비완료06:12:46UTC,예찰Goal06:12:57UTC전송. DDS기본버퍼자동적용로그확인,확인시점응답누락0. 전체시험완료아님. summary.json/result.json/events.jsonl/supervisor.log에서진행확인. 시험중코드수정/새커밋/푸시없음.


### 2026-10-23T15:51:21.851487+09:00 재부팅 후 3차 캠페인 재개

- 사용자 “컴퓨터멈춰서 재부팅함 재개”. 기존 sec01_16_round3_20261023_151213 이어실행. SEC01 attempt1은9번째창중중단,완료창8개모두SUCCESS. 원본result백업/공유scene/기존산출물보존뒤INTERRUPTED로별도분류,로봇오류3회누적에서제외.
- 기존정책유지: 매시도새예찰→모든창수확,같은오류3회SEC생략,Domain13/SUBNET CPU/headless. 감독PID14127,SEC01_attempt_0002시작. 양로봇Nav2active와DDS기본버퍼선택로그확인. 전체시험완료아님. resume_history.jsonl 및summary.json으로중단/재개추적.
- 코드/설정수정·커밋/푸시없음. 컴퓨터멈춤의원인을로봇Action실패로단정하지않음.


### 2026-10-27 3차 시험 완료 평가와 원격 업데이트 확인

- 3차 SEC01~16 전체완료: 2026-10-23 15:12:25~10-24 08:39:19KST(17시간26분54초),최종성공137창.19시도=성공16/Action실패2/컴퓨터재부팅중단1. 생략없음. 중단시도의실적은최종합계에서제외.
- A192/B195/C125,실제윈도우대응181(94.27%). 실제창누락11=예찰미대응10+검출후창누락1. 팔대응181분류122통과연결/48시도미통과/6미선택/4미시도/1ID미확정. 익명레이저C125와ID연결122차이3,이벤트중복·ID불확실성유지.
- 시작준비오류재시작/105기록0,SEC07정렬조건과SEC09팔복귀각1회실패후재시도성공. SEC07직전TF재구성yaw약3.53도로차체3도초과의심이나정확한판정TF미저장한계명시.
- 보고서sim/docs/SEC01_16_ROUND3_TEST_REPORT_20261027.md,검토용원본/집계/실패Action/SHA256은sim/docs/test_results/20261027_round3/. 전체숫자·창결과·분모/해시검증PASS. 제어코드변경/새시험없음.
- git fetch복구: 0바이트Codex임시참조백업후격리,원격main92ad63a동일확인. 실물담당브랜치4b5c5b1→cf870da(10/23 21:39KST)인계통합/TF·취소/주행판정변경확인. 공통파일이현재main과겹쳐자동병합하지않음. 다른교통미커밋작업보존. 사용자보고서/결과커밋푸시승인,이기록작성시푸시대기.


### 2026-10-27 현재 main/실물 담당 브랜치 비교

- 사용자비교요청,fetch후main68e5ef7/실물cf870da를비교. 공통조상2a397da,고유커밋6/8. 공통실행코드도달라‘설정만차이’아님. 우리Nav2시각패치·경로별제한·목표선각분리와실물의인계/TF/취소·잠금개선이분기됨.
- YAML실제병합으로VicPinky핵심RPP/footprint/costmap/도착값은일치확인. 공통기본yaml만덮으면실물브랜치sim에큰차체/0.4주시가적용되는차이있음. 양브랜치실제함수재생에서SEC12/16기하 main허용,실물기본3도/선택5도모두path_heading거부.
- 상세sim/docs/changes/REAL_BRANCH_COMPARISON_20261027.md/JSON,재현sim/runs/branch_comparison_20261027. 실물설치Nav2패치여부미확인. 소스수정/병합/주행/커밋푸시없음,교통미커밋변경보존.


### 2026-10-27 공통 주행 재시도 선별 통합 준비

- 사용자 승인으로 실물5ff5b50의 제한106재시도를 공통farm_navigation에 선별 반영. 기본0/운영 비활성, 거리 기반 제한·교통 미커밋 변경 보존. 대기시간만 총 실행 제한에서 제외. 105는 대상 아님.
- 관련32검사 통과, 교통 생성메시지 미빌드로 해당검사 미실행. 실제 주행/빌드/인계 전체 통합 미실행. 상세 sim/docs/changes/NAVIGATION_RECOVERY_INTEGRATION_20261027.md. 미커밋/미푸시.


### 2026-10-27 관제 교통·주행 시험 전달본 반영

- 사용자 traffic_and_drive_tests_sim_20261027 반영 승인. 9타입 중 기존8동일/NavigateToNode 추가, 두 시뮬 교통 프로필에 시험 서버 연결. 공통 ActionHandoff/계획·주행·허가 재사용, 작업 구간 예약/출구 차단 우회와 취소 정리 확인 보완. 기존 업무·실물 설정 보존.
- 공통4+sim2패키지 빌드,117회귀,Domain13/SUBNET 대역 주행의 실제DDS Action 성공/실패/취소·동일UUID조회 통과. 저장그래프47.5m우회 확인. Isaac/실제관제 공동시험 NOT_RUN. 상세 sim/docs/changes/TRAFFIC_DRIVE_HANDOFF_20261027.md, 공유검증 sim/docs/test_results/20261027_traffic_drive/. 미커밋/미푸시.


### 2026-10-27 교통 시험 반영분 커밋·푸시 및 실물 추가 업데이트 확인

- 사용자 커밋·푸시 승인. 기존 교통 연동과 테스트 Action, 기본 비활성106재시도 및 검증자료를 함께 반영한다. 117회귀/공통4+sim2빌드/대역DDS Action 검증 결과 유지, 실제 공동 주행 NOT_RUN. 원본 전달 폴더와 runs/build/state는 커밋에서 제외.
- fetch 후 실물 브랜치5ff5b50→48d2d1c(15:32KST) 확인: 일반 방향6도, 정지 후 복귀5cm/6도, 실행 중 최대3도 유지, PC더미 기반 인계·복귀 후 다음window 성공1회 기록. 자동병합 없음. 상세 sim/docs/changes/REAL_BRANCH_UPDATE_20261027.md.


### 2026-10-27 공용 코드 로컬/실물 사전 병합 검토

- 사용자 검토 요청. main b5ef6f2/실물48d2d1c,공통조상2a397da를3방향비교. src변경경로 로컬만66/실물만83/양쪽37(17동일/20상이). 실행코드 변경·병합 없음.
- 우선 ActionHandoff 외부check잠금밖/재시도설정검증/TF구분·조회API, 인계 API는묶음검토.106핵심동일SHA. 로컬교통·거리예산·D059·TF원본조회·예찰개선/vendorNav2보존필요. 인계유일출력검사와교통정지publisher다중생성의구성충돌확인.
- 잠금/설정실제함수오프라인경계검사실행, 운영교착/실주행재현아님. 상세sim/docs/changes/COMMON_CODE_MERGE_REVIEW_20261027.md/JSON. 문서만미커밋/미푸시.


### 2026-10-27 — 최신 운송 통합 브랜치 검토·시험 환경 설계

- 구분: 사전 검토/설계, 사용자 최신본 비교 요청 범위. main b5ef6f2 / feature_dongmin9686aca.
- 대상: sim/docs/changes/TRANSPORT_SIM_SCOPE_REVIEW_20261027.md 및 JSON, docs/PROJECT_STATE.md. 기존 미커밋 검토 문서 보존.
- 전후: 실행 동작 변경 없음. 추가 기능/실행 장애/반영 파일 경계/마커·카메라·기구·시간·관제·교통 시험 순서와 수량A~F 기록계획을 문서화. sim station복귀의 marker32 생략은 사용자 요구이며 구현 전 상태. pickup42/41와 sorter40 도킹은 유지.
- 실물 영향: 없음. 공통 코드/실물 설정 변경안은 보고서에 제안만 기록. 승인 전 적용하지 않음. 커밋/푸시 없음.
- 검증: 전체Git inventory, actual config함수 sim거절/ROS입력확인, 기존RouteGraph station-sorter 양방향6.5m, 원격FSM 대역12검사PASS. Isaac/실기/통합빌드/E2E 미실행. 로그 sim/runs/transport_scope_review_20261027/.
- 되돌리기: 새 보고서/JSON과 이번 문서 추가 항목만 제거. 기존 검토자료/코드/자산 영향 없음.


### 2026-10-27 — 인계 시험 범위 축소 (D-063)

- 사용자 지시: 과실 배출·낙하 물리/하역 기구 구현 제외, 도킹 후 두 바구니 정렬·정지 유지로 sim 인계 성공 판정. 기존 설계의 실제 과실 전달 시험/D~F 측정을 대체. 허용 오차·유지 시간은 형상 확인 후 결정. 마커 도킹/주행/이격/복귀와 A/B/C 유지.
- 운송 URDF/portable URDF/USD 및 cargo_box·바퀴·덮개·틸트 관절 존재 직접 확인. 실제 런타임 연결·시험 미실행.
- 변경: TRANSPORT_SIM_SCOPE_REVIEW_20261027.md 상단에 우선 적용되는 범위 조정, DECISIONS D-063. 문서만 변경/실물 영향 없음/커밋·푸시 없음. 되돌리기는 이번 문서 추가 항목만 제거.


### 2026-10-27 — 운송 시뮬 구현 1단계: 계약·공통 운송/도킹·복귀

- 사용자 “구현해야되는 파트 확인하고 하나씩 작업시작해” 승인으로 사전 검토 범위의 실행 코드 통합 시작. 바구니 정렬 유지 기준 D-063, 기구/낙하 구현 제외 유지.
- feature_dongmin9686aca에서 transport_robot/farm_docking 선별 도입 및 메시지8종 추가. 기존 교통·NavigateToNode·공통주행/예찰/수확 코드는 보존. sim 환경 허용·경로/시계 검증, sim return에 한정한 navigation_only 정책 구현. 실제 도착/정지 실패와 취소는 실패/취소 유지. 실물 기본 마커 도킹/하드웨어 검증 유지.
- 운송 교통 미연결 상태에서 traffic.enabled 시작 거절. 도킹 단일 출력과 충돌하는 별도 Nav2 정지 설정 거절. 도킹 비활성 close/pending 처리 보완. 기존 all.launch/fleet는 변경하지 않아 운송 자동 기동 없음.
- 검증: 3패키지 빌드/기존117+새24=141시험PASS, 최종 운송24재확인PASS, 실제DDS Domain13/SUBNET의 대역주행 성공·실패·취소·같은UUID조회·중복task거절PASS. 실제USD 읽기 확인. Isaac/실물/전체E2E NOT_RUN.
- 상세 sim/docs/changes/TRANSPORT_SIM_IMPLEMENTATION_20261027.md. 자료 sim/docs/test_results/20261027_transport_integration, 로컬로그 sim/runs/transport_integration_20261027. 공통코드 적용됨/미커밋·미푸시. 다음: 가상운송 차체·센서/마커/바구니정렬→관제인계→선별장이동→교통통합.
- 복원: 이번 추가패키지/메시지와 CMake등록, sim시험·문서만 제거하고 인터페이스 재빌드. 기존 사용자 미커밋 검토문서/전달폴더 보존.

### 2026-10-27 — 운송 가상 하드웨어 연결

- 승인: 사용자 “가상 하드웨어 연결해”. sim 장치/자산/실행/시험 및 상태 문서만 변경. 공통 주행·미션/실물 설정 추가 변경 없음.
- 운송 wheel/cmd_vel/관절 odom/PhysX scan/카메라/TF 연결. transport 기본 false, 운송 단독·3대 fleet 및 장치 launch 추가. 수확 없는 fleet의 평가 선택화, 팔 없는 운송의 공통 월드 물리 사용. 수확 평가/프로파일 검증 보존.
- station 8003 yaw를 기존 출구 edge 방향으로 원본 task/generated spawn에 같이 확정. 카메라 장착은 실물 waffle 기준, 내부 보정 미제공으로 임시 K 명시. 구독 없는 동안 렌더 OFF, 2초 wall lease. 기존 카메라 설정 유지.
- 첫 실제 구동 실패: 원통 바퀴/고정 캐스터 접촉에서 차체 정지. 진단 후 원본 보존 파생 USD의 둥근 단면·캐스터 자유 구름 근사·타이어 마찰 반영. 질량/관성/drive/바퀴 외경·폭 보존. visual instance 재개 렌더 오류도 파생 자산에서 수정.
- 직접 검증: sim 3패키지 빌드, 87 구성/ROS 시험 + 5 USD 검사 PASS. Domain13/SUBNET/CPU 실제 농장 단독 및 3대 실행, ROS 8검사 PASS, 최종60초완료/정상종료. GT 순변위0.1906m/yaw0.4390rad, 카메라 OFF/ON/OFF/ON/OFF. SDK 종료 메뉴 AttributeError2건 별도 기록. 고속/정밀도킹/E2E 미검증. 구식 mock4개 제외 사유와 수정 전 HEAD 재현 포함.
- 상세 `changes/TRANSPORT_VIRTUAL_HARDWARE_20261027.md`, 공유자료 `test_results/20261027_transport_hardware/`, 원본 `sim/runs/transport_hardware_20261027/`. 복원은 이번 sim 변경/새 설정/파생 자산만 제거. 미커밋·미푸시.

### 2026-10-27 — 담당자 브랜치 원본 보존 통합 규칙

- 사용자 지시: 병합 중 수치/판정 변경 및 코드 누락 재발 금지. 프로젝트 AGENTS.md에 원본 커밋 고정, 의존/호출 코드 포함 반영 목록, 최종 실행 설정 비교, 승인된 sim 예외 명시, 동작 검증과 미검증 구분을 추가했다.
- 이번 변경은 작업 규칙/이력 문서뿐이며 실행 코드·수치·판정을 변경하거나 추가 병합하지 않았다. 기존 통합 전체의 동등성을 새로 검증한 것은 아니다. 문서 diff/공백 검사 수행, 미커밋·미푸시. 복원은 이번 규칙과 이력 항목만 제거한다.


### 2026-10-27 — 실측 대기 없는 임시 도킹 마커 배치

- 승인: 사용자 “마커위치 추정…답변 기다리는건 지금 시간없어서 곤란해”. 원본 담당자 브랜치 수치/판정 보존 조건 유지. 실측값 아님을 PROVISIONAL_NOT_MEASURED로 표시.
- 변경: sim/assets/docking_markers의 배치표/PNG3개, runtime/docking_marker_scene.py·run_fleet.py·fleet_config.py, transport_fleet.json, 정차 렌더 도구와 USD 검사. 이전에는 도킹 마커 없음; 이후 운송3대 fleet에서만42/41/40을 모델에 부착. 원본USD/공통/실물/마커32 변경 없음.
- 검증: PNG3개·실제Isaac 정차RGB3개 모두ID검출, USD장착/부모이동/물리보존2검사 및 기존19검사 PASS,2패키지빌드 PASS. 초기GPU접근/시험clipping/mimic API 실패원인·로그보존. 최종렌더Error0. 실제주행/도킹전환/라이다/바구니정렬/E2E 미검증.
- 발견: 선별장 자산(-7,14)과 그래프8004(5,13.25) 불일치. 자동이동하지 않고 후속정합항목으로기록.
- 상세 sim/docs/changes/DOCKING_MARKER_PROVISIONAL_20261027.md, 공유 sim/docs/test_results/20261027_docking_markers/, 원본 sim/runs/docking_markers_20261027/. 되돌림:transport_fleet의docking_markers항목제거. 미커밋·미푸시.

### 2026-10-27 — 도킹·바구니 정렬 실제 검증

- 승인: 사용자 “도킹 바구니 정렬 검증 시작해”. 공통 farm_docking27파일 원본9686aca와 동일, 선택42/41프로필 숫자 변경0. Domain13/SUBNET/CPU/headless 실제센서·PrecisionMotion 실행.
- 결과:42접근 성공. 기존41임시마커/라이다면 약20cm 불일치 및TF시각오류로실패. 시험복사본만41면을 맞춘 경우 최종20cm 도킹 성공했으나 바구니겹침72.84%/중심오차10.36cm/높이차5.65cm로정렬실패. 운영마커/로봇USD/공통판정불변. 연속E2E·인계이벤트아님.
- sim수정:팔비활성 student 카메라 호출2곳None보호; 운송CameraInfo reliable선택으로공통구독연결; 평가용프레임/주기선택진단파일추가. 진단/분석/시험도구·명목개구부평가설정·회귀추가. 다른로봇기본QoS/기록주기보존. GT는파일평가만.
- TF진단:원본fresh()반환값불변 sys.monitoring으로 음수age -16.7ms 184회확인. 성공실행에서도발생; 이전실패순간내부age미계측한계명시. 해결완료아님.
- 검증:회귀24/3패키지빌드PASS. 시작오류2/카메라frame오류1/도킹실패2·성공2로그보존.42종료시SDK-11별도기록. 상세DOCKING_BASKET_ALIGNMENT_20261027.md 및 test_results/20261027_docking_alignment.
- 복원:이번sim연결diff/선택진단·평가·시험파일만제거,선행미커밋통합보존. 실물파일변경/커밋/푸시없음.

### 2026-10-27 — 최신 도킹 재시험 실패, 진행 상태 정정

- `final100/41/result.json`: status6, success=false, stopped=true, `모터 제어권 상실: LEASE_EXPIRED`. 공통 제어 스케줄 지연21030.1ms, odom/scan 수신 공백22~23초. 양 sim 어댑터에도 같은 시각 telemetry 중단 경고가 기록됐다. 지연의 근본 원인은 미확정이며,100ms 전달 대기로 안정화 완료됐다고 보지 않는다.
- 같은 실행에서 `on_odom`의 미래 시각 거절1회(-16.7ms)도 남았다. 최종100ms 설정은 검증 미완료/실패 상태. 앞선50ms 설정의41 두 회 성공과42 한 회 성공은 이전 시험 결과로만 유지한다.
- 대화 중단으로 runner가 사라진 뒤 남은 해당 시험 전용 ROS 프로세스 그룹을 확인하고 SIGINT 종료했다. Isaac은 기존 로그상 종료 완료. 최신 실패를 성공으로 집계하지 않는다.
- sim 전용 marker41 면 보정(-0.455→-0.251m), 운송 센서 시계 대기0.1s/유한 큐/영상 발행 고갈 수정. 공통27파일·수치·판정·원본 USD 보존. 회귀31PASS,3패키지빌드PASS,실행 안정화 미완료. 복원/실물 영향 없음/승인 근거는 상세 보고서 참조.

### 2026-10-27 — 72.1% 겹침 바구니 독립 낙하 시험

- 사용자 “그 조건만 … 테스트” 승인으로 원본 USD를 변경하지 않고 개방된 배출구/상단 덮개 조건의 한 알 낙하만 추가했다. 공통 코드·도킹·인계 성공 판정 변경 없음.
- 실제 성공 도킹 상대 자세에서 위치25×자세3=75조건: 수용60, 외부 낙하10, 가장자리 부근잔류5. 중심 정렬 비교75/75수용. CPU60Hz/120Hz 각150조건의 개별 분류 모두 동일. 80%는 선정한 표본 수용률이며 실제 일괄 배출 확률로 해석하지 않는다.
- 원본 자산4개 SHA256불변, 실제 CPU/MBP확인,문법/diff검사통과. Isaac 종료 잔존은 결과 저장 뒤 정리(exit143/124); 물리 결과와 별도 기록. 이번 시험 종료.
- 구현 sim/tools/check_partial_basket_transfer.py, 분석 analyze_partial_basket_transfer.py. 상세 sim/docs/changes/PARTIAL_BASKET_TRANSFER_20261027.md, 공유 sim/docs/test_results/20261027_partial_basket_transfer/, 원시 sim/runs/partial_basket_transfer_20261027/.
- 이번 한 알 시험은 동시 배출·덮개 구동·실물·전체 E2E를 검증하지 않았다. 현행72%조건의 무조건 인계 성공 전환은 하지 않음. 원복은 이번 독립 도구/자료만 제거. 미커밋·미푸시.

## 2026-10-27 — D-065 72% 도킹 승인 및 시뮬 인계·이격

- 승인: 사용자 “72% 겹친 상태를 정상도킹이라고 보고 다음단계 가자”. 완전포함 평가에서 최소72%+높이양수+기존정지0.8초로 변경, 이전 물리낙하 실패기록 보존.
- 대상: config/docking/basket_alignment_evaluation.json, transport.json/transport_fleet.json; sim_devices basket_alignment.py/mechanical_ros.py/ros_adapter.py; sim_runtime basket_monitor.py/fleet_config.py/run_fleet.py; 도킹 분석·준비·실행 probe 도구 및 신규 probe_sim_handoff.py; 관련 시험/보고서.
- 실물 영향 없음: 공통 도킹27파일9686aca원본일치, USD/과실4자산hash불변, 공통FSM·20cm도킹·25.2cm이격·오차수치 보존. 기구는 추상 상태만 변경하며 실수령량을 만들지 않는다.
- 검증: 36시험PASS,3패키지빌드PASS, 문법/diff검사. 기록재평가5.183초PASS. 새 Isaac CPU/Domain13/SUBNET 실제 DOCK41→가상인계→CLEAR 성공(72.4506%,정지1.10초,후진24.4198cm). freshness3218회거부0. SIGINT 종료 gate1/precision-2는 별도 종료오류로 기록; 업무 중 실패 없음.
- 미검증: 전체TransportPickup/TransferEvent DDS/관제/선별장 이동. 다음 운송환경·목적지 정합 후 이동 연결. 상세 changes/BASKET_HANDOFF_ACCEPTANCE_20261027.md, test_results/20261027_basket_handoff/.
- 원복: 가상기구enabled와fleet평가연결 해제, minimum_coverage=1.0 복귀. 기존공통/자산 변경없음. 미커밋·미푸시.

## 2026-10-27 — D-066 선별장 실제 위치 정합·운송 Nav2 연결

- 승인: 사용자 선별장이동연결/성공후커밋푸시 및 실제모델위치에접근점·경로맞추기 선택. 8004 (5,13.25)→(-7,13.25),yaw북쪽,연결9019→9001. 원본task/scout_harvest 및생성station/역할graph만수정,USD불변.
- 대상: transport_runtime/nav2_transport/transport_destinations/transport_sources 및도킹시험fixture; transport_navigation.launch.py와package의기존Nav2의존성선언; prepare_sorter_route_trial/analyze_sorter_route_trial와기존실행probe연결; test_sorter_navigation_config; config패키징/보고서.
- 실제실행: Domain13/SUBNET,CPU MBP60Hz,도킹→가상인계→이격→선별장CheckRoute 2회성공. Nav이동141.34/147.37초,실제오차11.19/9.82cm별도기록. 업무중오류없음. 종료뒤SDKchild-11,gate1,precision-2는잔존종료문제로보존.
- 보존/검증: 공통실행소스이번턴변경없음,활성RPP원본지정값런타임일치,원본도킹수치와27파일/4자산hash불변,75단위회귀PASS·371경로PASS·2sim패키지빌드PASS. 비활성DWB stateful런타임미선언은검증한계로명시.
- 실제도착/정지와추정오차/실과실수량미측정/관제전체업무미검증을구분. 상세 changes/SORTER_ROUTE_CONNECTION_20261027.md,공유test_results/20261027_sorter_route/. 원복은원본접근점/연결복귀후재생성및신규운송navigation조립해제. 기존도킹/바구니수정불필요.
