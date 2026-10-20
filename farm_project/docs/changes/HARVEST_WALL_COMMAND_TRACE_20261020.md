# 벽 실제 속도 전달 기록 — 2026-10-20

PC 격리 ROS 시험에서 실제 WallController→공통 gate→실제 Nav2 smoother의 비영 출력 각61개, 0.05rad/s, 직진0, 취소status5 확인. 이것은 실제 로봇 미구동 원인 확정이 아니다.

이번 변경은 wall_trial_runtime.py 한 파일에 기록만 추가한다. controller_raw, gate_forwarded, cmd_vel_nav_observed, cmd_vel_observed 및 기존 odom samples를 동일 결과 JSON에 보관한다. 토픽별 실제 발행/구독 노드도 저장한다. 오류 발생/중단 후에도 기록 요약을 출력한다. phase를 실제 요청 시 EXECUTING으로 표시한다.
제어 알고리즘·속도·진행시간·관측300ms·충돌·실행/정지 경로 변경 없음. 측정 입력 구독은 BEST_EFFORT로 수신 호환성을 확보한다. 기록은 메모리에서 최대10000개, 종료 후 파일 저장. 전부0/미수신을 같은 것으로 해석하지 않는다. 다른 발행자와 저수준 모터의 영향은 메시지 수신만으로 확정하지 않는다.

검증: 실제 forward 함수 추출 실행 4개(정상/명령 초과/관측 실패/비활성). 구문/해시/적용 재적용 검사. ROS 런타임에서 이 기록 보완본은 아직 실행하지 않았다.

run_pc.bash는 PC검사/적용, 로봇 원본PC백업/적용까지만. run_trial_pc.bash는 새 plan을 생성하고 성공/원본설정유지/정상종료 확인 후 해당 plan으로 실제 정렬 1회 실행. 속도 상향 없음. 기존 주행런치/Zenoh 유지, 팔 접힘 및 정지 상태, 주변 확인 후 시험한다.
기록용 원본은 PC/로봇 각 출력된 백업의 wall_trial_runtime.py. 필요시 해당 파일만 복원. Git 커밋/드라이버 변경 없음.
