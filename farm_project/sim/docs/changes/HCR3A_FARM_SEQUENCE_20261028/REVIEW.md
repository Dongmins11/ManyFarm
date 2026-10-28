# 농장 선별장·HCR 통합 시퀀스 (2026-10-28)

기준: main ea25693 + 기존 미커밋 통합 변경. 이번 작업은 sim 전용이다.
사용자 요청은 성능 튜닝을 뒤로 미루고 농장 선별소 배치와 운송 도킹 이후 선별을 연결하는 것이다.
도킹 제어 순서 변경 제안에는 “실물과 동일한 방식”으로 답변했다. 사전 방향 정렬 활성화 제안은 적용하지 않았다.

## 연결 구조

`BucketUnload → 실제 도킹/정지 → WAITING_FOR_UNLOAD → UNLOAD_READY → 가상 레인 투입 → 원본 이격/회전 → SortBatch → ReturnToStation`

- 농장 World 하나에서 기존 선별장만 세션 layer로 비활성화하고 원본 HCR 레인·보관부·팔을 함께 배치한다. 농장 USD 원본은 저장/수정하지 않는다.
- `/World/HCRStation`, `/World/HCRRobot`, `/World/SortingCamera`를 농장 실행 루프에 연결했다. CPU60Hz/렌더30Hz 유지. 원본 단독 시험240Hz와 같은 물리 주파수라고 주장하지 않는다.
- 실제 RGB A–D 판단, 원본 `hcr_sim.control.Sorter`, Modbus ACK/BUSY/DONE, 승인된 `hcr_sorting` 공통 ROS 서버를 사용한다. 카메라 ROI·색상 임계값·선택 순서·HOME/보관 확인·수량 집계 규칙을 변경하지 않았다.
- 팔은 전달본의 기능 근사 모델이며 파지는 기존 보조 고정 방식이다. 위치/속도 목표, 원본 게인/접촉 설정을 농장 장치에 연결했다.
- 배출 기구/기울임/낙하 시험은 제외한다. 현재 실제 도킹·정지와 해당 작업의 하역 요청이 확인되면 운송 바구니 안의 기존 red/yellow 과실 prim을 레인으로 이동시킨다. 원래 ID를 유지하며 복제하지 않는다. 투입 후 레인 안에 안정됐는지 검사한다.
- 초기 적재2개는 **시험 fixture**다. 실제 예찰·수확·운송 인계를 완료했다고 보고하지 않는다.
- 실행기는 공용 ROS 액션을 연결하는 시뮬 시험 도구다. Frontend에 SortBatch 자동 지시를 추가한 것은 아니다.

## 실물 제어 보존과 배치

- 운송 인수 기준: `9686aca909cb52191862ee3500c62fadf7a8ed38`의 `waffle_profiles.yaml`, `transport_docking_trial.yaml`.
- `sort_01_distance_trial.distance_heading_trial`는 원본과 동일하다. `align_before_lidar` 미지정=false. 라이다 설정 차이는 로봇별 `scan_frame` namespace뿐이다.
- 도킹 거리17cm±0.5cm, 전방 측정 편차3cm, 속도·시간 제한을 유지한다. 증거: `real_policy_comparison.json`.
- 선별장 투입면은 기존 접근 edge 9001→8004에 직교한다. 레인/보관부/바구니 형상을 변경하지 않는다. 임시 마커40은 기존 투입대 전면에 둔다. 실측 장착값은 아니다.
- 최초 투입면은 접근점보다0.5m 앞에 있어 원본 이격 후에도 차체가 경로 밖에 남았다. 실물 이격 기준 라이다 거리0.422m + 기존 URDF 센서 전방좌표−0.064m = **0.358m**로 전체 모델 배치만 맞췄다. 접근/복귀 노드와 경로를 새로 만들거나 허용 범위를 넓히지 않는다. 최종 위치는 `placement.json`.

## 직접 확인한 결과와 실패 기록

원시 자료: `sim/runs/hcr3a_farm_cycle_20261028/`.

| 시험 | 시작 조건 | 결과 |
|---|---|---|
| attempt02 | 기존 접근 edge 시작 | 전방 라이다 편차1.347m로 도킹 실패 |
| attempt03 | 같은 접근, 충돌면 진단 추가 | 동일 투입대 사선 관측으로 편차0.043m, 기준0.030m 초과 |
| attempt04 | 투입면을 접근 edge에 직교 배치 | 정지 차체107.74°, 접근방향101.15°. 일부 빔은 투입대, +3~5° 빔은 뒤쪽 invisiblewall_01. 편차1.446m로 실패 |
| attempt05 | 도킹 직전 edge 내부 초기 배치 | 실제 도킹·투입2개·이격·선별 SUCCESS(red1/yellow0). 노랑1개 잔류. 운송 복귀는 그래프 최대 시작거리0.15m 위반으로 실패 |
| attempt06 | 투입면0.358m 배치·원본 관절 속도 목표/접촉값 반영 | 도킹·투입·이격·선별 재성공. 실제 차체는 접근점0.99cm 안에 복귀. 위치 추정 오차 약24.7cm로 스테이션 복귀 거절 |
| attempt07 | 최종 배치, 기존 접근 edge 시작 | 실제 도킹·투입 성공. 이격 중 `Final approach odom TF stale`로 중단. TF age=−0.016666668초, 검사3533회 중1회 미래 TF 거절. 선별은 미시작 |
| attempt08 | attempt07과 같은 설정 반복 | 도킹·투입·후진 성공 후 회전 준비에서 `Departure exit odom stale`. 같은 age=−0.016666668초. 선별 미시작 |
| attempt09 | 시뮬 TF 발행 수정, 전체 접근 edge 시작 | BucketUnload SUCCESS → SortBatch SUCCESS(red1/yellow0). TF 검사5851회 거절0. 이후 스테이션 복귀는 위치 추정 오차25.6cm로 거절 |

attempt04는 제어가 라이다 초기 검사를 하기 전에 방향을 보정하지 않는 조건에서 발생했다. 이 로그만으로 실물 재현을 확정하지 않는다. 전체 접근 실패를 도킹 직전 분리 시험 성공으로 덮지 않는다.

원본 SUCCESS는 ROI에서 처리할 색상이 일정 시간 없음을 뜻하며 전체 투입 과실 잔량0을 보장하지 않는다. 빨강1개 실제 보관/HOME/관제 수량 일치는 확인했다. 노랑 미검출 개선 및 연속 성능 평가는 사용자가 뒤로 미룬 범위다.

attempt06 실제 차체 `(-7.0071, 13.2569)`, 추정 `(-6.9773, 13.5020)`. 배치 수정 후에도 남은 복귀 거절을 모델 배치 문제로 단정하지 않는다. 정지 상태 마지막 status/진단 샘플을 비교했으며 엄밀한 동시각 표본은 아니다. 상세 `return_diagnostics.json`. 위치 추정 오차 원인(지도·관측·주행 영향)은 이번 자료만으로 확정하지 않았다.

attempt07의 `stale` 문구는 오래된 TF였다는 뜻으로 해석하면 안 된다. 진단상 노드 현재 시각보다1물리프레임(16.7ms) 미래여서 거절됐다. 별도 `/clock`·TF 수신 순서 영향이 의심되며 timeout 초과나 선별팔 오류가 아니다. 실패를 무시하거나 공통 freshness 판정을 완화하지 않았다. `freshness_trace.jsonl`/summary에 보존했다.

### 시뮬 TF 발행 순서 수정

attempt08에서도 재현되어 `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py`를 추적했다. 이전 TF 선발행 구현은 UDP 수신 즉시 TF를 보내고 odom/scan만 `/clock` 대기시켜 TF가 미래로 보일 수 있었다. 기존 `state_clock_delay_s`의 전반부는 시계 전달에, 후반부는 TF 선전달에 사용하도록 수정했다. 현재0.1초 설정이면 TF는 측정시각+0.05초 이후, odom/scan은 기존대로+0.1초 이후 발행한다. 측정 stamp/좌표·시간 지연 설정·공통 `0 <= age <= limit` 판정은 유지한다. 시뮬 장치 발행 수정이며 실물 드라이버는 불변이다.

미래 표본 대기·TF→odom 순서·다중 표본·세션 교체·시계 정지/만료 검증8PASS. 과실 이동 검증4PASS, 실행 진입점2PASS, 두 sim 패키지 빌드 PASS. 실제 수정 후 결과는 최종 결과 절에 기록한다.

## 실행과 제한

프로젝트 루트에서 ROS Jazzy, robot/sim install, `sim/runs/hcr3a_intake_20261028/ros/install/local_setup.bash` 선별 overlay를 source한다.

```bash
ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET \
  python3 sim/tools/run_sorter_cycle_trial.py \
  sim/runs/hcr_farm_new_run --sorting --dock-entry-fixture
```

`--dock-entry-fixture`를 빼면 기존 접근 edge 시작부터 시험한다. 출력 디렉터리는 새 경로여야 한다. 성공/실패 결과, ROS 피드백, 실제 RGB, 원래 과실 ID·좌표·수량, 라이다 충돌면을 보존한다. 종료 시 자신이 시작한 프로세스를 정리한다.

시뮬 pause 중 작업중인 HCR은 성공 처리하지 않고 장치 오류로 정지한다. reset은 기존 농장 규칙대로 프로세스를 재시작해야 한다. 실제 pause/reset 중단 시험은 아직 수행하지 않았다. 다중 배치 재투입·관제 UI 전체 흐름·실물 재현은 별도 검증 대상이다.

## 최종 결과

요청한 **농장 배치 + 기존 접근 경로 → 운송 도킹 → 기존 과실 가상 투입 → 이격 → 실제 선별/HOME/관제 수량 결과**를 attempt09에서 직접 확인했다. 도킹 요청부터 선별 결과까지 약96.95초(실제 시간)다. 선별 결과1개와 물리 보관1개가 일치하며 노랑1개 잔류를 별도 기록했다. 성능 개선·완전 처리율 시험은 미완료다.

스테이션 복귀까지 포함한 runner 전체 결과는 **실패**로 유지했다. 실제 이격 완료 차체는 접근점0.96cm 안에 있지만 추정은 실제보다25.6cm 벗어나 `max_start_distance_m=0.15`를 초과한다. 다음 주행 과제는 이 복귀 위치 추정 오차의 원인 분리다. 이번 수정 후 TF 미래 거절0회는 한 번의 통합 시험 결과이며 장기 안정성 보증은 아니다. 초기 사선 라이다 진입 실패도 원시 로그에 유지한다.

검증: 시계/TF8 + 과실 이동4 + 진입점2 = **14PASS**, Python 문법 검사, sim2패키지 빌드, 관련 tracked diff 공백 검사 PASS. 도킹 전 가상 투입 요청은 거절됐다. 도킹 정책/정밀 제어 소스는 인수 커밋과 byte 동일(`common_source_audit.json`). Domain13/SUBNET/CPU60Hz 유지. 프로세스 종료 자료에 probe=1은 복귀 실패, gate/precision 중단 코드는 시험 종료 SIGINT이며 선별 프로세스 crash로 해석하지 않는다.

변경 범위는 `changed_files.json` 및 문서3개(PROJECT_STATE/DECISIONS/CHANGELOG)다. 실행·설정·자산·시험 모두 sim 안에 있다. 커밋/푸시는 요청되지 않아 수행하지 않았다. 다운로드 파일과 복원/실행 방법은 DELIVERY.md를 참고한다.
