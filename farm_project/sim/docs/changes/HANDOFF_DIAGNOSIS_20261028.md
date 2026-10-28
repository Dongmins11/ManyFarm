# 인계 복귀·제어권 만료 원인 진단 — 2026-10-28

기준 main `ea25693` + 기존 D-067~070 미커밋 통합. 사용자 요청: “확인해 왜문제발생하는지”. 이번 변경은 시뮬 시험 계측과 분석 자료뿐이다. 공통 제어/판정, 실물 설정, USD, 인계 하한은 변경하지 않았다. 미커밋·미푸시.

## 결론

1. `WINDOW_REALIGN_REQUIRED`의 직접 원인은 **역원호 복귀 후 지도 추정 위치가 저장 윈도우와 어긋나, 허용된 짧은 전진만으로 복구할 수 없다는 판정**이다. 실제 차체 이동 오차와 지도 위치 보정 오차는 분리해야 한다. 추가 시험에서 odom 오차보다 AMCL 보정 오차가 훨씬 컸다.
2. `LEASE_EXPIRED`는 **실시간 0.6초 안에 제어권 갱신이 처리되지 않아 정지**한 것이다. 이전 실패의 영상/제어 지연과 동시 발생은 확인했으나, 영상 계산이 만료의 단일 원인이라는 증거는 없다. 추가 2회에서는 재현되지 않았다.
3. 추가 실제 시험은 2회 모두 도킹·가상 인계·수확 원위치 복귀 성공. 위치 추정 흔들림은 성공 시험에도 남아 있다. 수정 완료/전체 사이클 완료로 판단하지 않는다.

## 실제 시험 범위

- ROS Domain 13 / SUBNET / CPU 물리60Hz. 직전과 같은 실행 생성 도구·원본 공통 코드·임시42 마커. 태그 위치 보정은 기존 시험과 동일하게 false.
- 기존 성공 예찰 결과의 SEC01 첫 윈도우 앞에서 시작. 실제 HarvestTask → Frontend worker/이벤트 서비스 → TransportPickup/DockTransfer → 복원.
- 두 회 모두 expected=1, harvested=0, 팔 실행가능 대상 없음으로 윈도우 액션 성공. 인계는 승인된 바구니 정렬/정지 기반 가상 검증이며 실제 과실 배출 성능을 검증한 것이 아니다.
- 신규 예찰, 전체 SEC01, 선별장/스테이션 복귀, 교통 연동은 이번 범위 아님.
- attempt1은 Python3.12 계측 이벤트 등록 오류로 준비 실패. `PY_UNWIND`를 전역 이벤트로 등록하도록 고쳐 재실행했다. attempt3 최초 명령은 ROS 환경 누락을 실행 전 검사에서 거절했고, Domain13/SUBNET 지정 후 실행했다. 로봇 동작 실패와 구분한다.

| 시험 | 종료 시각 KST | 도킹/인계/복원 | AMCL 표본 최대 Y 오차 | 마지막 AMCL 표본 Y 오차 | 최대 영상 처리 구간 | 최대 갱신 콜백 시작 간격 |
|---|---|---|---:|---:|---:|---:|
| attempt2 | 16:10:37 | 양쪽 SUCCESS | 5.46cm | -1.89cm | 26.80ms | 164.94ms |
| attempt3 | 16:14:34 | 양쪽 SUCCESS | 4.63cm | -1.26cm | 21.20ms | 160.57ms |

이 표의 마지막 AMCL 표본은 Action 최종 판정 시각과 동일하지 않다. 마지막 값만으로 최종 성공/실패를 재판정하지 않는다. 종료 정리 때 gate exit1/precision SIGINT(-2), ROS destroy 예외는 별도로 보존했다. Isaac/probe exit0, 시험 프로세스 정리 완료.

## 위치 오차의 발생 경로

공통 `harvest_robot/handoff_window.py:26`은 먼저 지도 위치가 윈도우 반경(실행값5cm) 안인지 확인한다. 밖이면 전진3mm~6cm·횡오차1.5cm 이내의 보정만 허용한다. 후진이나 큰 횡이동이 필요하면 `WINDOW_REALIGN_REQUIRED`다.

이전 pickup9에서 차체는 인계 전후 약6.3mm 차이로 복귀했으나, 최종 지도 추정은 실제 차체보다 Y 약4.4cm 뒤틀렸다. 목표는 지도상 뒤쪽5.89cm/횡2.44cm로 계산돼 실패했다. 목표 윈도우 자체와 최초 정지점의 차이도 있으므로 6.3mm를 목표점 도착 오차로 해석하면 안 된다.

추가 attempt2에서 같은 시각의 USD 위치, 바퀴 odom, AMCL/TF를 대조했다. 전체 주행 표본의 odom 최대 평면 오차는 attempt2 4.26mm, attempt3 3.96mm였다. 아래는 초기 자세에 정합한 odom과 해당 시각 지도 위치의 실제 위치 대비 오차다. 단위cm.

| sim 초 | odom X/Y | map X/Y |
|---:|---:|---:|
| 20 | -0.01 / 0.00 | +0.02 / -0.55 |
| 45 | +0.28 / -0.08 | +1.93 / -2.71 |
| 65 | +0.23 / -0.34 | +2.77 / -4.26 |
| 100 | +0.23 / -0.35 | +2.77 / -4.27 |
| 120 | +0.24 / -0.07 | +2.88 / -5.45 |
| 145 | -0.14 / +0.13 | +1.23 / -1.87 |

**이 표본에서 큰 오차의 주원인은 바퀴 odom 누적이 아니라 AMCL 지도 보정이다.** 오차는 인계 진입 회전부터 커졌고 복귀 회전 중 일부 줄었다. 최종 AMCL 자체의 Y 표준편차도 약11.9/12.2cm다. 이는 실제 오차12cm라는 뜻이 아니라 위치 추정기가 보고하는 불확실성이다.

### 왜 AMCL 보정이 흔들리는가

- 실물 기준 공통 AMCL 설정은 alpha1~5=.2, sigma_hit=.2m, max_beams60, 위치 갱신5cm/각도.2rad다. 긴 베드 벽이 반복되는 현 시뮬 환경에서, 수cm Y 이동을 라이다만으로 강하게 구분하기 어렵다는 증거가 있다.
- 5cm 격자 지도와 실제 라이다의 오프라인 거리장 점수를 비교했다. attempt2 sim19.95초에서 실제 자세 점수0.9908, Y -5cm에서0.9856, +5cm에서0.9906이다. 실제로 5cm 틀린 위치도 비슷한 일치도로 보인다. 회전 중 운동 오차 모델로 커진 위치 분포가 라이다로 충분히 좁혀지지 않는 설명과 부합한다.
- 이 점수는 전체 유효 빔/평면 투영의 평균 exp(-거리²/(2×.2²)) 진단값이다. AMCL의60빔 선택·입자 가중치·재표본화까지 재현한 값이 아니며 alpha 또는 sigma 단독 원인을 확정한 A/B 시험도 아니다.
- 실제 자세에서 라이다/지도 일치도가 높아, 큰 고정 센서 좌표 오프셋이나 지도 전체 이동은 이번 증거와 맞지 않는다. 로봇 동적 장애물의 영향은 아직 분리하지 못했다.
- 코드 경로상 odom·scan은 같은 물리 표본 시각을 보존한다. AMCL map→odom 시각의 +1초는 transform_tolerance에 따른 의도된 미래 유효 시각이며 그것 자체를 시간 오류로 분류하지 않았다. 모든 TF 문제를 배제했다는 뜻은 아니다.

따라서 **공통 복귀 판정과 위치 추정 불확실성 사이의 문제**다. AMCL/복귀 규칙은 공통이므로 실물에서도 같은 조건이면 발생할 수 있다. 다만 현재 오차 크기는 시뮬 지도·장면·odom 특성에서 측정한 값으로, 실물 재현을 입증하지 않았다. “시뮬 물리만 잘못됐다” 또는 “공통 코드 버그로 확정”이라고 단정하지 않는다.

## 제어권 만료 경로

- `farm_docking/motion_gate.py`: TTL .6초, `time.monotonic()` 기준. `clients.py`: 별도 Node/SingleThreadedExecutor/스레드에서 .15초마다 갱신. 시뮬 시간/실제 시간 혼용으로 만료되는 구조는 아니다.
- 이전 pickup10에서 control_tick612.6ms, consume_image600.7ms, scheduling_gap622.8ms가 같은 구간에 기록됐다. 이어 갱신 요청이 LEASE_EXPIRED로 거절됐다. 로그의 갱신 콜백 간격.434초만으로 gate에서 마지막 갱신이 받아들여진 시각을 복원할 수는 없다.
- consume_image 측정은 `_profile_lock` 대기를 포함한다. 600.7ms를 ArUco 순수 계산 시간으로 부르는 것은 부정확하다. 갱신이 별도 스레드이므로 Python 실행 대기, OS 스케줄링/자원 경합, gate 서비스 처리 지연 등을 구분해야 한다.
- 추가 계측은 Python 함수·네이티브 호출의 경과시간/스레드 CPU시간, 갱신 콜백 시각을 기록한다. 공통 함수를 교체하거나 결과를 바꾸지 않는다. 파일 쓰기는 비동기 큐로 분리했다.
- 추가2회는 영상 최대26.8/21.2ms, 갱신 시작 간격 최대164.94/160.57ms로 TTL 만료가 없었다. 계측 변경이 실행 타이밍에 영향을 줄 수 있으므로 이를 수정 효과나 재현 불가능의 증명으로 사용하지 않는다. 정확한 지연 발생 지점은 미확정이다.

## 다음 조치

위치 문제는 저장된 scan/odom과 AMCL 운동·측정 오차 설정의 적합성을 먼저 비교하는 것이 적절하다. 실제 odom은 mm 수준인데 추정 분포는 cm 이상으로 커진다. 성공 반경을 넓히거나 정답 위치를 주입하면 이 문제를 숨기므로 적용하지 않았다. 공통 복귀 정책 변경이 필요하면 파일/변경안/실물 영향을 별도로 제시한다.

제어권 문제는 현재 계측을 유지하고 다음 실패 시 gate 수신/갱신 완료 시각까지 연결해야 한다. 재현 없이 TTL을 늘리거나 영상 스레드가 원인이라고 단정하지 않는다.

## 자료·변경·재현

- 변경: `sim/tools/probe_handoff_window.py`에 AMCL/scan/map→odom/staticTF/monotonic 기록 추가. `sim/tools/trace_docking_freshness.py`에 비동기 시간 계측 추가. 공통/실물 동작은 변경 없음.
- 공유: `sim/docs/test_results/20261028_handoff_diagnosis/summary.json`, attempt2/3 AMCL 분석 JSON·TXT, `analyze_localization.py`.
- 원시 로그: `sim/runs/handoff_diagnosis_20261028/attempt{1,2,3}/`. drive 세션 attempt2=`42e4b7bea95347f99ca9543dbd1502c8`, attempt3=`7352786eacbf4b15a7d745ec427ece80`.
- 실행: ROS 환경 source 후 Domain13/SUBNET에서 `python3 sim/tools/run_handoff_window_trial.py sim/runs/<새경로> --pickup --scout-result sim/runs/sec01_16_round3_20261023_151213/SEC01_attempt_0002/result.json`.
- 분석: 프로젝트 루트에서 `python3 sim/docs/test_results/20261028_handoff_diagnosis/analyze_localization.py sim/runs/handoff_diagnosis_20261028/attempt2 sim/runs/drive_diagnostics/42e4b7bea95347f99ca9543dbd1502c8/harvest_01.jsonl`.
- 검증: 계측 도구 py_compile, Python3.12 모니터 이벤트 등록 확인, Isaac실행2회/오프라인분석2회. 추가 단위시험/실물시험 미실행. 계측만 되돌릴 때 해당 두 도구의 이번 추가 부분을 역적용하며 이전 누적 구현을 보존한다.

## 변경 파일 패키지

`sim/runs/handoff_diagnosis_20261028/handoff_diagnosis_changes.zip`은 이번에 만진 파일의 현재 버전만 포함한다. 두 시험도구와 PROJECT_STATE/CHANGELOG에는 앞선 미커밋 통합 내용도 있으므로 ea25693 단독 환경에 이 ZIP만 적용해 전체 구동할 수 있는 패키지는 아니다. 현재 동일 작업 기준에 적용하며 로그 원본/Frontend는 포함하지 않는다.

```bash
unzip -o "$HOME/Downloads/handoff_diagnosis_changes.zip" -d /home/ysy/main/farm_project
```
