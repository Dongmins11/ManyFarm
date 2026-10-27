# 벽 정렬 진행도 실패 대조 — 2026-10-26

사용자 승인: 기존 성공과 실패 대조, 실제 코드의 TF 대기시간 제외 확인. 운영 코드·설정 수정, 재기동, 이동 없음. 기존 미커밋 변경 보존.

## 직접 확인
- 실패 DOCK_TEST_155cf97ddafc4253a633704317e0883b. 곡선 1792972711.030→2725.682 성공, 벽 goal2728.822→2753.323 Failed to make progress(24.501초). TF 대기2739.903→2741.119(1.216초),2746.353→2747.328(.976초). 로그 두 구간 합2.192초는 모든 대기 누계가 아니다.
- 실제 controller27385 maps의 운영 libwall_controller.so SHA93761a5469dedaa12da56b36659249c6a9f2942ce683bb74545447cf168946b7. 생성 로그/실시간 파라미터 WaitingProgressChecker, wall_progress 이동 .005m/회전 .01745rad/10초. wall_alignment timeout40초와 다른 검사. wait_until_fresh=true. 대기시계publisher1/controller_wait publisher1은 현재 조회값이며 실패시점의 DDS조건을 소급 보증하지 않음.
- 기존 성공 DOCK_TEST_7974ad4fddfa4ceb9ce89f28bf81d961: 2026-10-24 벽 goal1792835117.746→5141.847(24.101초), DOCK_READY5142.746.
- 성공 bag 해당구간 odom723/raw_nav482/벽관측200/대기누계433. 대기누계 증가3.568초. odom 순회로 .005m/.01745rad 임계 재설정 모사 시 최대 간격9.598초. 위치 변화 약.071m, yaw변화-.03837rad. 이 계산은 controller가 실제 소비한 TF pose와 검사시각을 복원한 것이 아님.

## 대기 제외 경로
runtime._watchdog→_publish_pause_clock: gate/worker/벽 관측 대기 및 소유권·취소 조건을 확인해 0출력, PauseClock.update→handoff_wait_clock [session,seq,total,ROSstamp].
WaitingProgressChecker.check→WaitClock.take→baseline_time += credit→기존 PoseProgressChecker.check.
WallController/GoalChecker의40초와 Python 상위실행시계는 별도 소비자다. 최신 clock reversed 수정은 Wall Control의 active elapsed 계산을 바꿨으며 wait_plugins.cpp와 WaitClock 공통 소비식은 그대로다.
수신 시 header age[-.1,.2],수신이후<=.2,단일publisher,session/seq/누계검사. take는 min(누계증분,이번check간격,.2,상한)을 반환하고 last_total을 전체total로 전진한다. 최초유효수신·stale수신·큰누계증분 구간의 차액은 후속check로 이월하지 않는다. Python PauseClock.update도 매갱신 누적을 .2초로 제한한다.

## 확인된 계산 결함과 한계
운영 wait_clock.hpp SHA4dff4b55…/wait_plugins.cpp SHAe0db6209…와 PC후보동일 확인. 실제credit계산식 추출 C++ 오프라인 재현: 연속대기누계 .1초마다갱신/check .05초, 10초대기→credit5초(5초손실). 모든수신fresh/단일publisher/동일session을 전제로 해도 발생. ROS 서버 실험이 아닌 산술재현이며 실기손실량이5초라는 뜻은 아님.
이 손실식은 성공시점 pause_budget 후보에도 있었음. 현재와의차이는명시무제한일때30초누계상한해제뿐이며 wait_plugins.cpp는동일. 성공당시실시간파라미터덤프가없으므로기존후보설정과실제실행설정의완전일치를주장하지않음.
이번 기존trace5607행은callback stamp/TFstamp/watchdog/단계시간만보존. 위치·속도·wall observation수치·progress baseline/실소비credit없음. wall구간watchdog434회/max gap.149847초: watchdog >.2초공백은관측안됨. DDS콜백지연/credit손실/벽미세정렬교착까지배제하지못함.
따라서 확정은 진행도checker실패와대기과소제외가능코드이며, 실제실패직전 마지막진행시점·손실량·벽정렬정체원인은미확정. Clock reversed재발이나상위FSMtimeout으로분류하지않음.

## 다음 조사/수정 판단
기존자료만으로직접귀속불가. 향후승인시 progress check마다 now/baseline/pose delta/누계증분/credited/fresh이유와wall오차·phase·출력·controller_wait를같은구간에수집하면실제정체와보정손실구분가능. 지금은추가운영계측적용없음. 단순10초확대나충돌/정지보호해제하지않음.

자료: runs/wall_progress_audit_20261026/{operating.txt,failure_trace.jsonl,success_samples.json,success_summary.json,credit_repro.cpp}. 이전성공bag runs/pause_budget_handoff_20261024,실패로그 runs/dock_20261026_0858. Git commit/push없음.
