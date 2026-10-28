# 운송 AMCL 20cm 오차 원인 분리·수정

2026-10-28 KST. 기준 main ea25693 + 기존 미커밋 HCR 통합/지도 갱신. 사용자 “AMCL 오차좀 잡아봐 … 시뮬레이션 코드에” 요청에 따른 시뮬 설정·시험 환경 수정. 실물/공통 코드, 주행 성공 판정, 도킹 거리/속도/시간 제한은 변경하지 않았다.

## 결론

**시뮬 운송 AMCL의 관측 갱신 간격을 줄이고, 운송 단독 시험에 잔존한 미실행 예찰 모델을 제외했다.** 지도 갱신 후에도 남았던 선별장 회전 후 오차는 실제 시험에서 **20.30cm → 3.46cm**로 감소했다. 전체 접근·도킹·이격·선별·스테이션 이동 중 AMCL 측정 439회의 평균 오차3.19cm, 최대7.66cm다. 모든 시점에서5cm 이내였다는 의미는 아니다.

복귀 경로 시작 거절은 해소됐고 스테이션 위치까지 이동했다. **마지막 제자리 방향 전환에서 진행 검사105가 발생하여 ReturnToStation 액션은 실패**했다. 전체 사이클 성공으로 보고하지 않는다.

## 원인 분리

1. attempt10의 실제 scan1,102개와 바퀴 odom을 격리 토픽에서 원본 `/opt/ros/jazzy` AMCL로 재생했다. 물리 시뮬레이터·기존 adapter·실시간 TF 발행 큐를 빼도 AMCL 출력23개가 원래 시험과 최대4×10⁻¹⁵m 차이로 일치했다. 이번20cm는 실시간 발행 지연/순서로 설명되지 않는다. 모든 시뮬 TF 문제가 영구적으로 없다는 보증은 아니다.
2. 실제 위치로 투영한 scan이 지도와 더 잘 맞는다. 최종유효320개 중97.5%가 점유셀 중심5cm 안에 있었고, AMCL 추정 위치 투영은58.44%였다. 동일 likelihood 거리 계산의 최종실제pose 점수9.264, 추정pose7.984. 지도와 센서가 맞는 위치가 있는데도 필터가 그 위치로 충분히 수렴하지 못했다.
3. 운송 설정은 **25cm 이동 또는0.2rad(11.46°) 회전**해야 관측을 갱신한다. 기존 수확 설정의 이동 갱신0.05m와 다르다. 이번운송은태그보정없는 원본nav2_amcl이며, 이전태그사용수확시험과같은조건이 아니다. transport 값0.25/0.2는 인수실물브랜치9686aca의 `robot/config/robots/waffle/transport_nav2.yaml`과 같았고, 최근시뮬롤백으로새로생긴값은아니다.
4. 회전 중 실제 바퀴 odom 증분 위치오차는13개 갱신 구간에서 평균0.463mm였다. 동일구간 기존 AMCL 운동모델의 병진 표준편차는 평균9.59cm다. 서로 다른 통계량이며 이것만으로 노이즈 계수를 보정하지 않았다. 긴 복귀에서는 실제 바퀴누적 오차도 커지므로 운동 노이즈를 무작정 줄이는 방식은 채택하지 않았다.
5. 운송 단독 fleet인데 원본 USD의 `/World/scout_robot_camera_fixed`가 기존 위치 X≈−6.3/Y≈12.1에 남아 있었다. 지도 밖으로 크게 어긋난 최종8개 ray의 반사점이 해당 모델 경계와 일치한다. 실제운영예찰로봇이 아니라 초기씬에남은미실행모델이다. 이 모델만제외한 실제attempt14에서는 선별장회전후12.08cm로감소했지만 충분하지않았다. 1회 비교이므로 개별 기여도/개선율은 통계확정아니다.

원본 알고리즘 검토: [Nav2 Jazzy 운동 모델](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_amcl/src/motion_model/differential_motion_model.cpp), [라이다 likelihood 모델](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_amcl/src/sensors/laser/likelihood_field_model.cpp). 소스 검토만으로 원인을 확정하지 않고 동일 입력 재생과 실제 시험으로 확인했다.

## 동일 입력 재생 비교 — 운영 설정과 분리

모든 재생은 원래 scan/바퀴 odom을 사용한다. 정답 좌표를 AMCL/주행 입력으로 넣지 않았다. map/TF/clock은 `/amcl_diagnostic` 토픽으로 격리했다.

| 변경 | AMCL 갱신 횟수 | 마지막 위치오차 | 채택 |
|---|---:|---:|---|
| 원본 설정 | 23 | 20.31cm | 기준 |
| sigma_hit 0.2→0.05만 변경 | 23 | 29.71cm | 미채택 |
| alpha4 0.2→0.002만 변경 | 23 | 14.92cm | 미채택 |
| update_min_d 0.25→0.05m, update_min_a 0.2→0.05rad | 98 | 2.00cm | 실제시뮬검증 후 채택 |

갱신 간격 변경은 기존 센서 측정/확률모델을 더 자주 적용한다. sigma/alpha/입자수/beam수/측정값/초기위치/도착 허용치는 유지한다. sigma 축소는 이 경우 오히려 악화하므로 적용하지 않았다.

## 적용 파일·실물 차이

- `sim/ros_ws/src/farm_sim_config/config/nav2_transport.yaml`: AMCL 두 갱신 임계값만0.05로 변경. 기존실물0.25m/0.2rad와의 **의도적인 시뮬 차이**다. 동일설정이라고 보고하지 않는다. 실물파일은그대로다.
- `sim/tools/run_sorter_cycle_trial.py`: 운송단독시험에서 원본씬을 참조하는 임시USD레이어로 미실행예찰모델만 제외. 원본USD는수정안함. fleet에실제예찰로봇이있으면제외를거부한다. `--keep-unused-scout`는이전잔존조건비교전용. 실물원본대비AMCL차이를fixture의 `numeric_control_changes`에기록한다.
- `sim/tools/replay_sorter_localization.py`: 실제센서재생/원본AMCL/선택적진단override/출력·입자로그. 운영프로파일은수정하지않는진단도구. TF장착은기존운송URDF에서읽는다.
- `sim/tools/analyze_amcl_diagnosis.py`: 측정stamp에맞춘AMCL/실제pose/바퀴odom평가.
- `sim/tests/test_sorter_trial_scene.py`: 실행대상예찰로봇제외거부/파일보존검사.

## 실제 시험과 실패 기록

| 실행 | 변경/결과 |
|---|---|
| attempt11 | 진단USD레이어문법오류로시작실패. 수정/로그보존. 로봇주행실패아님 |
| attempt12 | 진단USD의단위/upAxis메타데이터누락으로시작실패. 수정후오프라인USD로드검사PASS |
| attempt13 | 잔존모델제외. 도킹·투입후이격에서 `BACKOUT_RAW_SCAN_STALE: age=0.417s limit=0.300s`. 회전후비교미도달. 당시격리재생이동시에실행중이었으며부하기여는미확정. 이후동시ROS재생종료하고단독재시험 |
| attempt14 | 잔존모델만제외. 도킹·투입·이격·선별성공, 회전후12.08cm. 복귀시첫교차로에서진행검사105 |
| attempt15 | 잔존모델제외+갱신간격수정. 도킹·투입·이격·선별성공, 회전후3.46cm. 첫교차로통과·스테이션도달후마지막방향전환에서진행검사105 |

attempt15 Domain13/SUBNET·CPU60Hz/render30Hz. 회전후wheel odom오차1.33cm. 전체AMCL평균3.19cm/최대7.66cm/마지막4.93cm. 반복성/모든SEC/다른로봇까지개선보장미검증. 마지막바퀴odom을초기위치에만정합한누적오차는약99cm, 누적방향오차약0.227rad(13°)로별도계측됐다. AMCL은이를보정하고있지만, 장거리운송바퀴/접촉물리의추가검토과제다. 이를TF표시오차로취급하지않는다.

TF freshness14,319회중미래TF5회기록. 이번도킹/이격액션은성공했으나기존시계경계의모든오류가사라졌다는보고는하지않는다.

## 남은105: 최종 회전과 진행 검사 충돌

최종스테이션목표는(2,13.25), yaw=−π/2다. 로봇은북향으로도착한뒤남향으로거의180°회전해야한다. 현재원본설정은 회전명령0.3rad/s, `SimpleProgressChecker`의이동반경0.1m·허용10초다. 이검사는각도변화를진행으로보지않는다.

attempt15 약257초부터linear0/angular−0.3을계속실행했다. 실제yaw는약1.35rad→−0.81rad로변하고있었지만, 약10초동안10cm병진이없어 `Failed to make progress`로중단됐다. 180°를0.3rad/s로도는시간만약10.47초이며가감속/물리추종까지필요하다. **이번직접실패는복귀경로접수때의20cm AMCL오차가아니다.** 회전완료후최종위치검사통과까지확인된것도아니다.

```text
[controller_server] Failed to make progress
ReturnToStation: FAILED / NAVIGATION_FAILED
Nav2 실패: status=6, error_code=105
```

원본진행판정/속도/시간제한은이번수정에서완화하지않았다. 다음공통주행검토는제자리회전의각진행을검사에포함하는방식이며, 단순히성공을강제하거나위치허용치를늘리는해결로취급하지않는다.

## 검증·자료·재현

- 지도4개+활성예찰보존1개, 총5PASS. 도구py_compile/diff체크PASS. 원본실물설정변경없음. 생성된실행AMCL0.05/0.05확인. USD m/Z축및예찰비활성검사PASS.
- 실제attempt15는Return실패로runner exit1, 시험소유프로세스정리완료. 선별입력2/빨강1·노랑0/노랑잔류1은기존성능이슈이며이번개선범위아님.
- 자료 `sim/docs/test_results/20261028_amcl_diagnosis/`: 재생별설정/결과, 실제AMCL시계열, 최종회전명령, 결과·환경/변경수치증빙.
- raw `sim/runs/amcl_diagnosis_20261028/`, `sim/runs/hcr3a_farm_cycle_20261028/attempt11`~`attempt15`. attempt15 session `9d214ebe3ce74e3187127b384a4f2dd2`.

```bash
cd ~/main/farm_project
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/local_setup.bash
source sim/ros_ws/install/local_setup.bash
source sim/runs/hcr3a_intake_20261028/ros/install/local_setup.bash
ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET \
  /usr/bin/python3 sim/tools/run_sorter_cycle_trial.py sim/runs/NEW_TRIAL --sorting
# 실제 시험을 종료한 뒤에만 격리 재생:
ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET \
  /usr/bin/python3 sim/tools/replay_sorter_localization.py \
  sim/runs/hcr3a_farm_cycle_20261028/attempt10 sim/runs/NEW_REPLAY
```

되돌림: 시뮬AMCL두값을0.25m/0.2rad로복원, 잔존모델비교는`--keep-unused-scout`. 지도갱신은유지한다. 현재미커밋·미푸시. 기존미커밋코드보존.
