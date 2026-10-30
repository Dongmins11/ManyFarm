# 수확 완료 상태 재사용 — 인계·선별·복귀 시험

- 요청: “인계 선별 복귀까지 이어서 진행”. 코드/설정 추가 변경 없이 직전 도킹 성공 설정을 사용한다.
- 기준: main/18d0e00 및 기존 미커밋 변경. Domain13/SUBNET, headless CPU물리60Hz/render30Hz.
- 직전 도킹 단독시험은 세션 종료 상태여서 도킹 중간 액션을 복원하지 않는다. 검증된 기존 도구로 수확 완료 상태를 재구성하고 윈도우 도착을 실제 재검증→운송 출발→42접근→수확 인계자세→41도킹→가상과실인계→수확차체복원→선별장이동/도킹/레인투입/선별→운송복귀→수확복귀 순서로 실행한다.
- 원본 수확결과: `sim/runs/sec01_reuse_cycle_20261029_attempt01`.
- 초기 과실 스냅샷: `sim/runs/transport_resume_inputs_20261029/harvest_scene.json`. 과거 수확집계7/실제 적재10은 별도로 기록하며 새 수확 실적으로 계산하지 않는다.
- 현재 실행: `sim/runs/transport_full_resume_20261029_attempt01/`. 소스 해시/복사본과 조립 설정, 원시 이벤트·액션결과·물리 집계를 보존한다.
- 직전 성공 설정: sim 전환여유0.1m, 실제도킹허용1.2m, 초기복구/최종접근 시뮬 시간. 이번에는 `--stop-after-docking`을 지정하지 않는다.
- 시험 종료: 인계·선별장 도킹·레인투입 성공, 하역 후 이격 회전 실패. 선별 및 두 로봇 복귀 미실행.

## 실행

```bash
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/local_setup.bash
source sim/ros_ws/install/local_setup.bash
source sim/runs/hcr3a_intake_20261028/ros/install/local_setup.bash
export ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
python3 -u sim/tools/run_single_cycle.py sim/runs/transport_full_resume_20261029_attempt01 --resume-harvest sim/runs/sec01_reuse_cycle_20261029_attempt01 --resume-scene sim/runs/transport_resume_inputs_20261029/harvest_scene.json
```

새 시험은 반드시 새 결과 폴더를 사용한다. 추가 소스 변경/커밋/푸시는 이번 실행에서 수행하지 않았다.

## 실제 결과

| 단계 | 한국시간 | 결과 |
| --- | --- | --- |
| 운송 출발 | 21:08:39 | MOVING_STARTED |
| 42 접근 완료 | 21:14:33 | WAITING_FOR_TRANSFER |
| 과실 가상 인계 | 21:16:11 | 기존 과실10개, 겹침71.88% |
| 운송 인계·이격 완료 | 21:16:28 | TransportPickup SUCCESS |
| 수확 인계·위치 복원 완료 | 21:17:50 | DockTransfer SUCCESS, restore_complete=true |
| 선별장 출발 | 21:17:50 | BucketUnload 시작 |
| 선별장 도킹 시작 | 21:21:49 | DOCKING_STARTED |
| 선별장 도킹·레인 투입 | 21:22:57~59 | UNLOAD_READY 접수, 같은 과실10개 투입 성공 |
| 이격 후 회전 시작 | 21:23:20 | ALIGN_EXIT_DIRECTION |
| 회전 이탈 실패 | 21:23:42~43 | CLEARANCE_FAILED / Distance exit rotation position drift |
| 선별/운송복귀/수확복귀 | 미실행 | BucketUnload 실패로 후속 단계 차단 |

전체 시험은 실패다. 선별 결과0개는 선별 시도 실패율이 아니라 미실행 상태다. 레인에는 빨강6/노랑4 기존 과실10개가 투입됐다. 투입 기구/인계 기구의 실제 배출 물리 검증은 제외된 가상 인계 방식이다.

## 실패 분석

공통 `precision_server.py`의 `run_distance_exit`가 회전 시작 odom XY 대비 변위가 `max_translation_m=0.05`를 초과하면 실패시킨다. 이번 값은 원본 설정 그대로이며 추가 완화하지 않았다. `prepare_distance_exit`는 map의 그래프8004→9001 방향을 odom 목표각으로 바꾸되, 변위 검사는 odom 좌표만 사용한다.

- 회전 명령: 선속도0, 각속도−0.3rad/s. 바퀴 목표는 좌우+1.309/−1.309rad/s.
- 초기에는 실제각속도 약−0.26rad/s로 정상 회전했다.
- 21:23:30 전후부터 실제각속도 약−0.009rad/s로 급감하고, 선속도 약−0.007m/s로 뒤로 밀렸다. 측정 바퀴도 목표와 달리 양쪽 모두 음수 방향이었다.
- 실패 직후 가장 가까운 진단표본: odom변위5.122cm, 실제world 차체변위5.237cm. 약2mm 이내로 같은 움직임을 가리킨다. 따라서 단순 AMCL 추정 튐으로 발생한 실패가 아니다. 시간초과·Nav105도 아니다.
- 물리 접촉/구동 제약이 의심되지만 접촉 물체/힘 로그가 없어 원인 확정은 못했다. 다음은 해당 선별장 이격 자세에서 단독 회전 재현 및 차체·바구니·선별장 충돌형상/접촉점 확인이다. 5cm 조건을 늘려 우회하는 변경은 하지 않았다.
- 이번 실행은 실패 시 기존 시험기 정책대로 종료했으며 자동 재시도하지 않았다. 도킹 성공 단독시험 결과는 유지된다.

## 증거·변경 상태

- 보고용 증거: `sim/docs/test_results/20261029_transport_full_resume/`.
- `summary.json`: 단계별 성공/미실행 및 정량 변위.
- `transport_exit_drive.jsonl`: 회전 전후 실제pose/바퀴목표/실측/odom. 원본은 `sim/runs/drive_diagnostics/e9e295d160894efaa372b3a4489a3f95/transport_01.jsonl`.
- `result.json`, `post_sorter/result.json`, `precision.log`, `harvest.log`, `transport.log`, `post_sorter_milestones.json`, `sorting/physical_report.json` 보존.
- 소스/설정 추가변경 없음. 기존 미커밋 변경 유지, 커밋·푸시하지 않음. 시험 재현은 새 폴더로 위 명령 실행. 보고서/증거만 추가했으므로 실행 동작 복원 변경은 없다.

보고서와 증거 ZIP: `sim/runs/transport_full_resume_20261029_evidence.zip`.

```bash
cd /home/ysy/main/farm_project
unzip -o sim/runs/transport_full_resume_20261029_evidence.zip
```
