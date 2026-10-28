# 동일 조건 인계 반복시험 — 2026-10-28

사용자 요청 “다시 테스트해봐 재현조건이뭐야”. 기준 main `ea25693` + 이전 미커밋 통합. KST 16:36~16:43, 실제 Isaac 시험3회. 공통·실물·시뮬 제어 설정과 판정 변경 없음. 시험 도구에 gate 수신 시각 계측만 추가했다. 미커밋·미푸시.

## 결과

**1회 성공, 2회 수확로봇의 인계 자세 정렬 후 최종 검사 실패.** 이번 재현은 `rotate_to_transfer: 정지 후 목표 오차 초과`이며 Nav2 105나 운송로봇 자체 실패가 아니다.

| 시험 | 결과 | 실패 시각 KST | 거리 측정(목표43.25±0.5cm) | 각도 오차(허용±0.5°) | 도착 반환 후 실제 차체 각도 변화 |
|---|---|---|---:|---:|---:|
| 1 | 도킹·가상인계·복원 양쪽SUCCESS | — | — | — | — |
| 2 | 수확 DEVICE_FAILED, 운송 취소 | 16:41:15 | 43.334cm | 0.541° | -0.194° |
| 3 | 수확 DEVICE_FAILED, 운송 취소 | 16:43:09 | 43.569cm | 0.606° | -0.174° |

거리/각도는 최종 결과 시각 근처의 외부 wall_observation + odom 기록 재구성이다. 내부 validator가 읽은 정확한 표본은 저장되지 않았으며, 결과 시각과 차이는 각각 -4.9ms/+4.2ms다. 차체 변화는 USD 실제 자세를 odom 시각에 맞춰 비교했고 최대 표본 시각 차이는33.4ms였다. 측정 위치와 한계를 구분한다.

## 재현 조건과 경로

1. 기존 SEC01 첫 윈도우를 사용한다. 초기 차체는 생성 도구가 해당 윈도우 앞15cm에 배치한다. 예찰을 새로 하지 않고 실제 HarvestTask부터 실행한다.
2. 수확 윈도우 완료 후 운송42번 마커 접근, 수확로봇 원호 회전/벽 정렬을 수행한다.
3. 벽 정렬 제어기가 목표 도달을 반환한다. 이때 외부 기록 각도 오차는 시험2 약0.346°, 시험3 약0.435°로 허용범위 안이다.
4. 정지 명령 후 최종 정지/목표 확인을 기다리는 약2.5초 동안 차체가 미세하게 움직인다. 시험2/3 모두 바퀴 목표 및 차체 명령은0이다.
5. 각도 오차가0.541°/0.606°로 증가해±0.5° 기준을 넘는다. 공통 Navigator의 정지 후 validator가 거절하며 DockTransfer는 DEVICE_FAILED를 반환한다. 아직 DOCK_READY 전이므로 시험 helper가 대기 중 운송 작업을 취소한다.

동일 설정3회에서2회 발생한 **간헐적 재현**이며 항상 실패하는 조건을 확보했다는 뜻은 아니다. 실행 생성 설정은 경로 참조를 정규화하면3회 동일하다. runtime/journal/transfer.json만 실제 작업 ID/종료 상태에 따라 다르다. 명령값을 조작하거나 외부 지연을 주입하지 않았다.

### 이번에 확인한 원인 범위

- 벽 정렬 완료 검사는 지도 AMCL이 아닌 라이다 벽 관측과 odom을 사용한다(`handoff_planning.py` wall validate, `handoff_runtime.py` wall_error).
- 실제 USD 차체 방향도 바뀌었다. 따라서 이번 실패는 **지도 위치 추정만 흔들려서 발생한 오류가 아니다. 시뮬 차체의 정지 후 잔류 움직임이 허용치 경계를 넘긴 증거**가 있다.
- 실물의0.5° 판정을 완화하지 않았다. 다음 우선 조치는 시뮬 바퀴/차체가0명령 이후 왜 미세 회전을 계속하는지 확인하는 것이다. 마찰·접촉·조인트 감쇠 중 어느 항목이 원인인지는 이번 시험만으로 확정하지 않았다.
- 제어기 도착 반환과 정지 후 검사가 시점이 달라 서로 다른 결과를 낼 수 있다. 두 곳의 수치가 달라서 발생했다고 단정하지 않는다.

## 이전 두 오류는 어떻게 됐는가

### WINDOW_REALIGN_REQUIRED

이번 실제 시험에서는 미재현. 다만 복원까지 도달한 것은1회이며 나머지2회는 그 전에 벽 정렬에서 중단됐다. 따라서3회 모두 복원 검사를 통과했다고 계산하면 안 된다.

기존 pickup9의 마지막 지도 위치를 실제 공통 correction_path에 넣은 오프라인 재생에서는 같은 오류가 발생했다. 목표 거리6.38cm, 전방 투영-5.90cm/횡오차-2.44cm다. 반경5cm 밖이며 허용된 짧은 전진으로 도달할 수 없어 거절된다. 실제 실패 순간과 마지막 status 표본의 작은 시각 차이 때문에 기존-5.89cm와0.1mm 정도 차이가 난다. 오프라인 판정 재생과 Isaac 재현은 구분한다.

### LEASE_EXPIRED

이번3회 운송42번 접근에서 미재현. 41번 도킹/이격은1회만 도달했다. gate의 실제 갱신 요청을 기록했으며 갱신 거절0건, 만료까지 최소 여유446.0/446.2/447.0ms였다. 영상 처리 구간 최대24.70/41.76/17.04ms.

공통 Lease에 시각 인자를 넣은 오프라인 경계 확인은 마지막 정상 갱신 후599ms 성공,600ms/601ms LEASE_EXPIRED였다. 실제 지연을 주입한 시험은 아니다. **0.6초 이상 갱신 처리 공백이 만료 조건**인 것은 확인했지만, 과거 공백의 발생 원인은 아직 확정하지 못했다.

추가 과거 로그 대조: pickup10의 약600ms 제어 지연 구간(동일 부팅 monotonic 시각101953.3~101954.2초)에 Isaac은51개 프레임/시뮬0.833초를 진행했다. 최대 프레임38.7ms, 최대 프레임 간격38.8ms였다. 시뮬레이터 전체가600ms 정지한 증거는 없으며 운송 제어 프로세스/갱신 처리 구간을 추적해야 한다. 이 대조만으로 CPU/GIL/IO 중 하나를 확정하지 않는다.

## 고정 조건·계측·한계

- ROS Domain13/SUBNET, headless CPU60Hz. 원본 USD 바구니/차체, 기존 시뮬 wheel ki1/정지target0. 실물 제어값·판정 유지.
- 기존 임시42번 마커 배치·태그 지도 보정 false·교통 미연결 시험을 유지했다. 첫 회 실행 중 AMCL 실제 파라미터도 저장했다.
- 실제 HarvestTask는3회 모두 expected1/harvested0(실행가능 대상 없음). 성공 인계는 정렬/정지 기반 가상 배출 검증이다. 전체SEC01·신규예찰·실제 과실 배출·선별장·스테이션 복귀 시험이 아니다.
- 추가 계측: `sim/tools/trace_motion_gate.py`는 sys.monitoring으로 실제 공통 MotionGate/Lease의 요청 수신/판정 시각·기한·결과를 비동기 기록한다. 함수 교체·정답 주입·정책 변경 없음. `run_handoff_window_trial.py`의 gate 시작만 이 계측 진입점으로 연결했다. 계측 자체의 미세 실행시간 영향은 배제할 수 없다.
- py_compile 및 실제3회 실행으로 계측 동작 확인. 기존 공통/실물 회귀시험은 변경하지도 실행하지도 않았다.
- 매회 종료 정리 완료. gate exit1/precision SIGINT(-2)는 기존 종료 예외이며 업무 실패와 별도로 보존했다. 실패2회의 probe exit1은 시험 실패 결과다.

## 자료와 재실행

- 원시 로그: `sim/runs/handoff_repeat_20261028/attempt{1,2,3}/`.
- 공유 자료: `sim/docs/test_results/20261028_handoff_repeat/summary.json`, 실패2/3 벽/정지 표본, 오프라인 판정 재생, 실제 AMCL 파라미터.
- 소스 해시: `sim/runs/handoff_repeat_20261028/source_sha256.json`. drive 세션은 각 attempt/drive_session.json에 연결.
- 재실행(프로젝트 루트, 새 결과 경로 지정):

```bash
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/local_setup.bash
source sim/ros_ws/install/local_setup.bash
export ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
python3 sim/tools/run_handoff_window_trial.py sim/runs/handoff_repeat_manual_NEW \
  --pickup --scout-result sim/runs/sec01_16_round3_20261023_151213/SEC01_attempt_0002/result.json
```

이번 변경 파일 ZIP은 현재 미커밋 통합 환경용이며 ea25693 단독 실행 패키지가 아니다. 원시 로그는 제외한다. 계측을 되돌릴 때 runner의 gate 실행을 기존 `ros2 run farm_docking motion_gate`로 복원하고 추가 trace 도구만 제거한다. 다른 누적 변경은 보존한다.

```bash
unzip -o "$HOME/Downloads/handoff_repeat_changes.zip" -d /home/ysy/main/farm_project
```

## 후속 비교 — 이전 판정 정합 수정과 같은 사례인가

사용자 “저번에 같은이슈 해결…같은사례인지 확인”에 따라 기존 수정/실물 인계 원본/현재 실행 경로를 비교했다. **이전 TF 수정이 사라진 것은 아니다. 그러나 Nav2 성공 후 별도의 늦은 검사로 다시 실패시키는 구조가 새 인계 경로에 존재한다. 물리 문제만으로 분류한 앞선 설명은 불충분하다.**

### 보존된 수정

- D-049 / `e145d9d`: ControllerServer가 제어기와 GoalChecker에 같은 제어 주기 pose를 주고, 목표 TF도 그 pose 시각으로 변환한다. 현재 controller_server.cpp/.hpp는 해당 커밋과 byte 동일하다.
- 현재 설치 환경의 `build/nav2_controller/test/test_goal_transform_time --gtest_color=no`를 재실행해6/6 PASS. TF 누락 시 의도된 예외 검사도 포함한다. 새 Isaac 시험은 수행하지 않았다.
- D-029: 일반 주행은 Nav2 성공·실제 정지 후 잔여 자세 오차를 경고/측정값으로 남긴다. 현재 일반 경로에서도 유지된다.

### 인계 경로의 추가 판정

실물 브랜치 `origin/feat/harvest-handoff-real-20261018`의 검토 기준 `e135cde`에는 이미 별도 arrival_validator가 있으며, 거절 시 `정지 후 목표 오차 초과`를 발생시킨다. 이 예외는 기록된 커밋 `5d47a23`에서 도입됐고 10/28 통합 시 원본을 유지했다. 이번에 원격 fetch를 한 것은 아니며 이전에 확보한 커밋을 비교했다.

| 항목 | 벽 정렬 Nav2 단계 | 인계의 정지 후 최종 단계 |
|---|---|---|
| 위치/각도 기준 | 거리43.25±0.5cm, 각도±0.5° | 같은 벽 설정/같은 수치 |
| 정지 속도 | 선속도<.005m/s, 각속도<.02rad/s | 같은 속도 기준 |
| 완료 시점 | 유효 벽 관측 시각으로 .5초 범위/정지 유지 | Nav2 결과 후 새로 정지 .8초 확인하고 재검사 |
| 입력 | 해당 제어 주기 pose + 플러그인 구독 벽 관측 | 최신 벽 관측 + 그때 읽는 odom 시각의 pose |
| 범위 밖이면 | 제어가 남아 있으므로 보정 계속 | 이미 제어가 끝났으므로 예외로 액션 실패 |

- `farm_wall_controller/wall_plugins.cpp`는 controller와 checker가 각각 WallInput/Control을 가진다. 같은 wall 설정을 사용하지만 관측 객체를 공유하지는 않는다. D-049는 pose 전달을 맞추며 별도 구독 관측까지 같은 표본으로 고정하지 않는다. 이 관측 차이가 이번 실패를 직접 유발했다는 증거는 아직 없다.
- `handoff_planning.py` wall validate는 전달받은 정지 stamp로 pose를 먼저 읽지만, 실제 벽 판정은 wall_error를 다시 호출한다. `handoff_runtime.py::_wall_error_once`는 최신 wall_value와 pose(0)를 별도로 읽는다. 최종 판정까지 한 시점의 표본을 전달하는 구조가 아니다.
- `navigator.py:185`의 예외는 별도 arrival_validator가 있는 인계 경로에만 적용된다. 따라서 D-029 일반 경로의 수정이 삭제된 것은 아니지만, 인계에서는 기존의 “완료 후 잔여 오차로 중단” 패턴이 다시 나타난다.
- WallController/Control/handoff_planning 원본 파일은 e135cde와 byte 동일하다. 실제 실물 배포/발생 여부는 확인하지 않았다. 시뮬 전용 판정 코드라고 설명하면 안 된다.

이번 로그에서는 완료 반환 후 실제 차체 변화도 확인됐으므로 **정지 잔류 움직임 + 서로 다른 시점의 완료 판정 + 종료 후 재보정 없이 실패하는 처리**가 결합한 문제다. 이전 RPP의 과거 TF를 사용한 오류와 완전히 같은 결함은 아니지만, 판정 시점·완료 책임을 맞춰야 한다는 점에서는 같은 유형이다.

권장 검토: 공통 인계에서 정렬 제어가 최종 정지·허용범위 유지 확인까지 담당하도록 하고 동일 시점의 관측/자세로 완료를 결정한다. 허용오차 확대, 과거 성공 표본 재사용, validator 무조건 제거는 적용하지 않았다. 이 방향의 구체 코드 변경은 아직 제안/승인/구현하지 않았다. 현재 요청 범위는 비교이며 동작 코드는 그대로다.

근거: `sim/docs/test_results/20261028_handoff_repeat/arrival_policy_comparison.json`. 이번 문서 비교 패키지 `sim/runs/handoff_repeat_20261028/arrival_policy_review_changes.zip` 적용:

```bash
unzip -o "$HOME/Downloads/arrival_policy_review_changes.zip" -d /home/ysy/main/farm_project
```
