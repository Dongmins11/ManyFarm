# 시뮬 수확 AMCL alpha4 적용 후 실제 인계 복원 시험

## 결과 — 인계·윈도우 복원 성공, 후속 사이클 진행 중

2026-10-29 23:54:14 KST, 수확 DockTransfer가 SUCCESS를 반환했다. transfer_complete/transport_clear/restore_complete 모두 true이며 운송 TransportPickup도 SUCCESS다. 이전 attempt02의 WINDOW_REALIGN_REQUIRED는 이번 한 번의 시험에서 발생하지 않았다. 전체 사이클 성공과 반복 안정성은 아직 확인하지 않았다.

| 항목 | 이전 attempt02 | 적용 후 attempt03 |
|---|---:|---:|
| 수확 AMCL alpha4 | 0.2 | 0.002 |
| 복원 마지막 AMCL/실제 위치 오차 | 5.94cm | 1.29cm |
| 도착 확인부터 복원까지 AMCL/실제 최대 오차 | 5.94cm | 2.39cm |
| 수확 인계·복원 결과 | DEVICE_FAILED / WINDOW_REALIGN_REQUIRED | SUCCESS / restore_complete=true |

새 시험 마지막 AMCL 표본은 sim318.350016603초, 추정(-6.023695,3.254537), 같은 시각 실제(-6.012072,3.260151)다. 해당 표본의 목표 거리 추정1.44cm/실제0.66cm로 기존5cm 범위 안이다. 이 표본은 액션 결과보다 먼저 기록됐으므로 액션 결과 시각의 정확한 위치로 표현하지 않는다. 실제 위치는 로그 사후 평가에만 사용한다.

## 적용 범위와 검증

- 사용자 “그건 시뮬레이션 설정이지? 변경해서 적용하고 재시험해봐” 승인. 기준 main 18d0e000d4c98e3478e0a8510d84948561fc7d5f + 기존 미커밋 변경.
- 변경 파일: sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml. overrides.amcl.ros__parameters.alpha4=0.002 추가. 회전이 병진 오차를 만들 수 있다는 AMCL 운동모델의 계수이며 도착허용오차가 아니다.
- 공통 robot/config/navigation/harvest_nav2.yaml 해시 유지, 실제 병합 파라미터 차이는 alpha4 한 항목뿐. 실행 노드 /harvest_01/amcl에서도 alpha4=0.002, update_min_a=0.2 확인.
- 태그 보정은 인계·복원 중 미사용. 태그 로그에는 초기 도착 구간 lease/관측만 있고 보정 요청/적용 이벤트는0건이다. 도킹 상대 마커 검출은 유지한다.
- Domain13/SUBNET, headless CPU물리60Hz/render30Hz. 기존 뚜껑 고정·바구니 형상·5cm 완료 기준 유지. 실물 설정과 공통 업무 코드는 이번에 변경하지 않았다.
- 성공한 SEC01 예찰/9윈도우 수확 데이터 재사용. 기존 집계7개/바구니 실제10개 차이는 보존하며 새 수확 성능으로 계산하지 않는다. 기존 과실10개를 가상인계했다.
- 기록 재생에서는 마지막0.85cm였으나 실제 재시험에서는1.29cm다. 실제 센서/주행 궤적 차이가 있으므로 동일한 오차 재현이나 모든 구간의 해결을 주장하지 않는다.

## 후속 진행과 자료

- 같은 시험 프로세스에서 운송 선별장 이동·도킹·선별·양 로봇 복귀를 계속 진행 중이다. 현 시점에는 이 후속 단계의 성공을 확인하지 않았다. 관제 HTTP/교통관제 전체 흐름 시험이 아닌 기존 직접 액션 시험이다.
- 원시 로그: sim/runs/transport_full_resume_20261029_attempt03/. 세션245e670a6ec74fdcbc67164ec8578197.
- 요약 증거: sim/docs/test_results/20261029_harvest_alpha4_live/ (파라미터 diff/실행값/소스해시/양쪽 Result/시각정합 위치 비교/태그 로그).
- 분석 명령: python3 sim/runs/transport_full_resume_20261029_attempt03/analyze_localization.py. 이후 복귀 주행도 포함될 수 있으므로 위 공유 자료는 인계복원 완료 시점의 스냅샷이다.
- 모니터: python3 sim/tools/cycle_monitor.py sim/runs/transport_full_resume_20261029_attempt03
- 복원: nav2_harvest.yaml에 이번 추가한 overrides 블록만 제거. 커밋/푸시 미실행.

## 2026-10-30 후속 결과

00:08:14 KST 수확 스테이션 복귀도SUCCESS, 전체 액션 연쇄 종료/프로세스 정리 완료. 다만 선별은10개중1개이며 잔류9개다. 전량 선별 성공은 아니며 검출 영역 원인은 SORTER_DETECTION_ONLY_20261030.md에 별도 기록했다.
