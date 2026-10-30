# 뚜껑 고정 후 사이클 재시험 시작 — 2026-10-29

기록 시각: 2026-10-29T22:38:36.072898+09:00

- 사용자 “사이클 다시 적용” 요청으로 attempt02 실행. **종료: 인계 후 수확로봇 window 복원 실패. 전체 사이클 실패**.
- Domain13/SUBNET, CPU 물리60Hz/render30Hz. 뚜껑 고정 sim USD 적용. 이전 attempt01의 추적 대상 공통/시험 소스 SHA256은 모두 동일; 새 뚜껑 모델과 진단 코드 해시는 이번 source_manifest.json에 보존.
- 예찰·수확 재사용: sec01_reuse_cycle_20261029_attempt01. 이전 수확9/9윈도우 성공, 집계7개/예상13개, 장면 바구니10개. 7/10 불일치는 기존 실적 그대로 보존하며 새 수확으로 집계하지 않음.
- 초기 실제 도착 전용 확인 후 운송 MOVING_STARTED 확인. 다음은 도킹·인계→선별장 도킹·레인투입→이탈→선별→양 로봇 복귀.
- 기존 시험 도구 흐름 유지. 관제 프론트엔드 프로세스는 종료/변경하지 않음. 시험은 기존 직접 액션 방식이며 교통관제 전체 연동 검증과 구분.
- 실행 명령: `python3 sim/tools/run_single_cycle.py sim/runs/transport_full_resume_20261029_attempt02 --resume-harvest sim/runs/sec01_reuse_cycle_20261029_attempt01 --resume-scene sim/runs/transport_resume_inputs_20261029/harvest_scene.json` (ROS overlays/Domain13/SUBNET 적용).
- 로그: `sim/runs/transport_full_resume_20261029_attempt02/`; monitor: `python3 sim/tools/cycle_monitor.py sim/runs/transport_full_resume_20261029_attempt02`.
- 자동 재시도 없음. 실행 도구가 단계 결과를 기록하며 종료 시 관련 시험 프로세스를 정리한다. 이번 요청으로 새 소스 수정/커밋/푸시 없음.

## 최종 결과 — 인계 후 window 복원 거절

- 2026-10-29 22:46:52 KST 수확 DockTransfer 실패. `DEVICE_FAILED / restore: WINDOW_REALIGN_REQUIRED: 짧은 전진으로 window 완료범위 확보 불가 (전방=-0.0796m, 횡오차=-0.0319m)`.
- 운송 TransportPickup SUCCESS(22:45:29 KST). 수확 결과 transfer_complete=true / transport_clear=true / restore_complete=false. 과실 인계 및 운송 이격은 완료, 수확로봇의 원래 작업 위치 복원만 실패했다.
- probe_handoff_window.py는 양쪽 인계 결과가 SUCCEEDED여야 after_handoff()로 진행한다. 복원 실패를 확인해 시험 종료 및 프로세스 정리를 수행했으므로 선별장 이동·선별·양 로봇 스테이션 복귀는 미실행이다. 종료 SIGINT/프로세스 오류는 최초 원인과 분리한다.
- 이번에는 이전 뚜껑으로 인한 선별장 이탈 회전 단계까지 도달하지 않았다. 105/시간 초과 오류도 아니다.

### 위치 대조

| 항목 | 값 |
|---|---:|
| 저장 윈도우 목표 | (-6.01500, 3.26605)m |
| 실패 직전 map→odom×odom→base 위치 | (-5.98340, 3.18637)m |
| 가장 가까운 USD 실제 위치 | (-6.00939, 3.23919)m |
| 지도 추정 위치→목표 거리 | 8.57cm |
| 실제 위치→목표 거리 | 2.74cm |
| 지도 추정 위치↔실제 위치 차이 | 5.89cm |
| 실행 return_position 허용범위 | 5.0cm |

실제 위치는 허용범위 안인데 지도 추정은 밖이었다. handoff_window.correction_path()는 반경 밖일 때 전진3mm~6cm, 횡오차1.5cm 이하만 허용하므로 뒤쪽7.96cm/횡3.19cm 목표를 거절했다. 기존 2026-10-28 LOCALIZATION_REPEAT08에서 관측한 실제 위치 정상/지도 위치 오류에 따른 복원 실패와 같은 양상이다.

USD와 odom 기록 시각 차이는 약0.283sim초이며 실패 직후 정지 구간의 근접 표본 비교다. 이 값은 근사 대조이며 완전 동시 표본이라고 주장하지 않는다. 위치추정 차이 자체는 확인했지만, 이번 실행의 AMCL·태그 관측·TF 갱신 중 어느 요소가 얼마씩 기여했는지는 추가 추적이 필요하다.

- 근거 `sim/docs/test_results/20261029_transport_full_resume_lid_hold/restore_position.json`, `action_results.json`.
- 이번 확인에서 판정/공통 코드 수정, 성공 처리 우회, 자동 재실행 없음. 다음은 복원 시작부터 종료까지 map→odom/태그 보정 이력 추적. 커밋·푸시 없음.

## 후속 원인 분리 — AMCL 보정 중 오차 증가

저장된 AMCL pose·바퀴 odom을 같은 sim시각의 USD 실제 위치와 대조했다. USD 표본 간 위치는 선형 보간하고 yaw는 unwrap 후 보간했다. odom은 최초 공통 시각에 실제 위치로 오프라인 정합했으며 제어 입력으로 주입하지 않았다.

| sim시각 | 구간 | AMCL 실제 위치 오차 |
|---|---|---:|
| 9.35초 | 마지막 window 도착 | 0.09cm |
| 302.25초 | 인계 후 복원 중 | 2.04cm |
| 317.75초 | 복귀 회전 후반 | 3.35cm |
| 320.15초 | 복귀 회전 후반 | 3.93cm |
| 323.95초 | 복귀 회전 후반 | 5.33cm |
| 328.05초 | 복귀 끝 무렵 | 5.94cm |

전체 odom 오차 최대4.93mm, 마지막3.42mm. 따라서 이번 약6cm 차이는 주로 실제 바퀴 이동 누적 오차보다 AMCL 지도 위치 추정 측에서 생겼다. 초기 pose가 처음부터6cm 틀어진 것도 아니다. map→odom 숫자의 마지막 재구성만 보고 추정한 것이 아니라 amcl_pose 자체를 관측 시각의 USD와 대조했다.

태그 보정 노드는 tag_correction=true로 실행됐고 start 로그도 있다. 다만 어댑터 기록은 관측31건 모두 selected=null, correction_requests=0이다. 작업 lease는 시작 후 약11sim초까지였고 인계·복원 동안 재개되지 않았다. 공통 mission.py는 수확 작업 finally에서 tag_control.end()를 호출하며, node.py의 before_move는 WINDOW_MOVE에서만 section을 넘긴다. 인계·복원에는 별도의 태그 작업 lease 연결이 없다. 따라서 노드 실행 여부와 실제 태그 보정 적용 여부를 구분해야 한다. 이번 인계 구간에서는 AMCL+odom으로 위치를 추정했다.

실행 수확 Nav2 기본값은 shared harvest_nav2.yaml의 update_min_d=0.05m/update_min_a=0.2rad, alpha1~5=0.2, likelihood_field, sigma_hit=0.2m, max_beams=60. 이 수치만으로6cm 오류의 단독 원인이라고 주장하지 않는다. 라이다 관측과 지도 형상 불일치/제약 부족, 주변 운송로봇 관측, motion noise의 기여를 개별 분리한 시험은 아직 없다.

앞선 운송 뚜껑 수정과 비교해 추적 대상 공통/시험 소스 해시는 동일하다. 기존 수확 인계 복원 위치추정 문제의 재발이며, 뚜껑 고정 과정에서 위치추정 코드를 변경한 결과가 아니다.

사용자 조건상 인계에서는 태그 보정을 사용하지 않는다. 다음 조치는 이 조건과 성공 기준을 유지한 채 해당 회전 구간 라이다-지도 정합 및 AMCL 갱신/운동모델의 영향을 검증하는 것이다. 태그 재활성화 제안은 철회했다. 이번 요청에서는 분석만 했으며 공통 코드/설정 변경·추가 실행은 없다.

추가 근거: localization_timeline.json / tag_adapter_events.jsonl.
