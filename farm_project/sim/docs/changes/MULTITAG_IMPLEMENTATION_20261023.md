# 예찰 복수 태그 관측 적용·검증 — 2026-10-23

- 기준: main / 0832b6f1827d912d827667e4c50aacf3a3f4e549 및 기존 미커밋 작업. 다른 교통/주행/팔 변경은 보존했다.
- 승인: 사전 복수 태그 제안과 설명 후 사용자 “예찰은 거리가 머니까 복수태그 적용해도 괜찮을듯 반영해봐”. D-055.
- 공통 소스: farm_tag_localization의 observer.py, runtime.py, node.py, pixel_bias.py. 새 회귀 test/test_multitag.py.
- 활성화: sim/ros_ws/src/farm_sim_config/config/tag_localization/scout_observation_model.json의 model_ids.tag_multi. 실물·수확 프로파일은 미변경/비활성.

## 동작

동일 프레임/활성 구간에서 기존 단일 태그의 품질·거리·높이·기울기·불확실성 검사를 통과한 태그 2개 이상을 사용한다. 등록 변환으로 모든 코너를 같은 태그 평면에 놓고 IPPE+LM으로 6D 자세를 구한다. 중심 간격 최대값은 최대 태그 변 길이 2배 이상이어야 한다. 태그 ID 순서로 계산하여 검출 순서에 의존하지 않는다.

전체 및 태그별 RMS, 차체 높이/기울기, 각 태그의 거리 범위, 동일 공분산 모델을 다시 검사한다. 두 해가 유지되거나 조건이 안 맞으면 기존 단일 태그를 선택한다. 복수 후보·거부 이유·원본 태그 ID·태그별 RMS·별도 모델 ID를 기존 observation 로그에 남긴다. 단일 태그 pixel-bias 프로파일을 복수 관측에 적용하지 않는다.

기존 6D 공분산 상한을 유지하며 태그 수로 축소하지 않는다. 이 상한은 신규 실물 측량으로 검증된 정확도 보장이 아니다. AMCL 보정 gain/최대 이동량·TF 소유·Nav2 설정·Action 성공 판정은 변경하지 않았다. 추가 의존성 없음. 정답 위치는 사후 평가에만 사용했다.

## 회귀시험

ROS 환경 source 후 `/usr/bin/python3`으로 각 test 파일을 분리 실행. 76개 PASS(새 복수 태그 11개 포함). 기존 test_launch_contract.py의 15개는 harvest_robot.configuration stub에 transfer_parameters가 없어 ImportError. 해당 launch 조립 시험은 통과로 계산하지 않았다. 수확 launch/관련 stub은 이번 위치 추정 수정 범위 밖이라 수정하지 않았다. 로그: `sim/runs/multitag_validation_20261023/unit_tests.log`.

새 시험: 합성 등록 기하 복원, 단일 태그 fallback, 검출 순서, 인쇄 방향 회전, 중복 ID/잘못된 코너, 활성 구간/시각 모델, 비평면/간격 부족, 거리 거부, 공분산 유지, 모호한 두 해 유지, joint 거부 후 단일 fallback, 단일 bias 차단, 실물/수확 비활성.

## 저장 원시 촬영 재생

운영 관측기에 원시 코너/K/등록 태그/장착값만 입력했다. 사후 실제 물리 로그를 보간한 위치와 대조했으므로 이동 중 시간 보간 오차가 남는다. 05/06 전체 원시 촬영 각각 667/433 프레임 중 복수 선택 116/67, 품질 거부 후 fallback 3/1. 계산 평균 1.19/1.12ms, p95 3.50/4.22ms. 해당 PC 오프라인 수치이며 실시간 전체 파이프라인 지연이 아니다.

복수 선택된 동일 프레임의 평균 절대 오차:

| 로그 | 표본 | 단일 X/Y mm | 복수 X/Y mm | 단일/복수 yaw ° |
|---|---:|---:|---:|---:|
| 05 geometry | 116 | 13.56 / 24.99 | 5.45 / 10.83 | 1.120 / 0.606 |
| 06 caster | 67 | 13.72 / 17.68 | 6.26 / 13.48 | 0.685 / 0.567 |

선택 가능했던 표본의 비교이며 모든 프레임/다른 SEC/실물의 개선을 보장하지 않는다. 원본 `sim/runs/multitag_validation_20261023/{replay_result,replay_accuracy}.json`, 재현 replay.py/replay_accuracy.py.

## 실제 Isaac 예찰

Domain13 / SUBNET / CPU physics / headless / 실제 공통 ScoutArea. SEC01 전체 예찰 07_multitag 첫 시도 SUCCESS. 5개 구간/9개 윈도우/expected13, 실제 평가 대상13개 모두 윈도우에 대응했다(3cm 평가 매칭). holds 없음, 105/Action 오류 없음. 수확 동작은 시험하지 않았다. 시작02:26:43UTC~성공02:29:27UTC(준비 포함 약164초).

운영 observation 68회 중 복수 선택12회, 유효 태그 부족54회, 복수 품질 거부2회는 단일 fallback. 총 보정 요청61회. 실제 전송된 관측의 compute_s 최대113ms로 오프라인 평균보다 컸다. 이벤트와 원시 촬영 로그를 보존했다.

직전 캐스터 수정06 대비 이번07의 차체 법선 평균 절대11.17→10.66mm, 과실 깊이 평균 절대12.27→11.74mm. yaw 평균 절대는0.407→0.446°로 소폭 증가했다. 각1회 실행이며 전체 예찰 성능 향상 폭이 크거나 통계적으로 확정됐다고 볼 수 없다. 실물/다른SEC/수확은 미검증. 평가 정답은 제어/위치 추정에 주입하지 않았다.

원본 result/events/telemetry 및 artifacts는 `sim/runs/multitag_validation_20261023/07_multitag`, 집계 comparison.json/live_multitag_summary.json, 소스 사본·SHA256는 source/에 보존했다. 공유용 수치 `sim/docs/changes/MULTITAG_IMPLEMENTATION_20261023.json`. 실행은 종료하고 시험 프로세스를 정리했다.

## 복원 및 남은 범위

복수 기능만 해제하려면 시뮬 예찰 model_ids.tag_multi 키를 제거한다. 공통 변경을 되돌릴 때는 위 4개 소스의 이번 diff와 새 test만 대상으로 하고 다른 미커밋 작업을 보존한다. 코드/설정은 미커밋·미푸시. 실물 및 여러 SEC 반복 검증은 별도 필요하다.


## 후속 분석 — 첫 촬영 전 보정 공백 (추가 적용 전)

사용자 “너무 소폭감소인데 더 개선못하나” 요청으로 원본 로그/공통 호출 순서를 확인했다. 첫 촬영 stamp61.433336537초, 최초 태그 사용권 수신61.583336545초, 첫 태그 관측62.033336569초. 첫 촬영 전에는 태그 관측이 없었다. 첫 촬영3점의 위치 추정 기여 깊이 오차 평균34.62mm가 전체 절대 오차 합의약59.0%를 차지한다. 나머지4촬영12점은평균6.02mm. 이는 동일 카메라 점을 실제/추정 차체 자세로 재변환한 차이이며, 센서의 과실 측정 자체까지 포함한 전체 좌표 오차와 구분한다.

공통 scout_new/states/navigation_move_state.py는 observation 이동 중에만 TagControl.begin(section)을 호출하고 navigate 반환 finally에서 end한다. section_start 접근에서는 보정을 열지 않는다. segment_progress_state.py의 정지 촬영 단계에는 태그 보정 대기/확인이 없다. 첫 촬영을 개선하려면 접근 중 반복ID 권한을 열기보다, 구간 도착 후 정지 촬영 전에 해당 구간 태그 관측/AMCL 적용 결과를 확인하는 것이 우선이다. 이후 새 시각의 영상을 촬영해야 기존 오래된 map 변환을 재사용하지 않는다. 태그가 없으면 제한 대기 후 기존 정책으로 진행하며 가짜 성공/새 Action 실패를 만들지 않는다.

추천 공통 변경안(미적용): segment_progress_state.py의 정지 촬영 전 사용권을 열고, farm_navigation/tag_control.py에서 현재 token/구간/시각과 일치하는 실제 AMCL 적용 이벤트를 확인한 뒤 새 capture를 요청한다. 사용권은 finally에서 닫고 취소/실패 시에도 닫는다. 미지원 태그/관측 부재는 제한 시간 후 사유를 기록하고 기존 예찰로 진행한다. 필요한 적용 확인 횟수/대기 상한은 저장 로그의 수렴 시간으로 먼저 결정하며 임의의 정답 위치/허용범위 완화는 하지 않는다. 관련 공통 상태/TagControl 회귀를 추가하고 SEC01 전후 반복으로 첫 촬영과 전체 오차를 분리 평가한다. 실물/시뮬 공통 촬영 타이밍에 영향이 있으므로 기존 AGENTS의 구체안 확인 절차에 따라 별도 승인 후 적용한다.

복수 관측은68회중12회에만선택됐고, 태그부족54회는usable1개48회/0개6회였다. 입력이2개 이상이어도 품질 조건이 성립하지 않으면 단일 fallback이므로 필터를 무턱대고 완화하지 않는다. 정량 근거 MULTITAG_CAPTURE_TIMING_20261023.json. 이번 후속 분석에서는 운영 소스/설정을 추가 수정하거나 시험을 재시작하지 않았다.
