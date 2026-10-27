# 72% 도킹 인정과 시뮬 인계·이격 시험

2026-10-27 KST. 사용자: “72% 겹친 상태를 정상도킹이라고 보고 다음단계 가자”. 결정 D-065.
기준 main `b5ef6f2`, 미커밋 작업. 실물 정밀주행 원본 `feature_dongmin`의 캐시 커밋 `9686aca`; 이번 작업에서 원격 fetch는 하지 않았다.

## 결과

실제 Isaac 시험 1회에서 **마커41 도킹 → 가상 덮개 열기 → 시뮬 인계 완료 → 가상 덮개 닫기 → 실제 후진 이격·정지**가 성공했다.

| 항목 | 측정/결과 |
|---|---|
| 인계 완료 시 겹침 | 72.4506% |
| 인계 완료 시 연속 정렬·정지 | 시뮬 1.10초 (기준 0.8초) |
| 도킹 | 공통 PrecisionMotion status=4, success=true, stopped=true |
| 인계·이격 | 공통 ReceiveLidState / WaitTransferState / ClearingState 결과 SUCCESS |
| 후진 목표 / 허용오차 | 원본 25.2cm / 1cm |
| 실측 odom 후진 변위 | 24.4198cm, 최종 정지 확인 |
| 인계 단계 시작부터 이격 완료 | 실제 시간 9.806초 |
| 센서 신선도 검사 | 3,218회, 거부 0회, 미래 시각 거부 0회 |
| 실수령 수량 | 미측정: count_valid=false, loaded_count=null |
| 환경 | Domain 13, SUBNET, headless, CPU PhysX / MBP, 60Hz |

물리 정답의 바구니 위치는 평가에만 사용했다. 마커/라이다 도킹과 후진은 공통 PrecisionMotion이 실제 바퀴를 제어했다. 기존 도킹 거리20cm·이격 수치·성공/실패 판정은 보존했다. 공통 farm_docking Python27파일은 원본9686aca와 byte 일치, 직전 낙하 시험의 자산4개 SHA256 불변을 확인했다.

## 이번 성공의 범위

- 전체 TransportPickup 서버의 미션 접수부터 실행한 시험은 아니다. 도킹 이후 시험 조립기가 **기존 공통 State와 DeviceBridge, TransferSession, PrecisionClient를 직접 재사용**했다. 공통 FSM 복사본/monkey patch는 없다.
- MechanicalOperation과 PrecisionMotion은 실제 DDS Action이다. TRANSFER_COMPLETE는 시험 조립기가 공통 TransferSession에 정확한 task/transfer/source ID로 전달했다. 관제 중계 및 TransferEvent DDS 서비스 경유는 아직 미검증이다.
- 덮개는 사용자 승인된 가상 기구 상태다. 실제 USD 덮개/바구니를 이동시키거나 과실을 생성·이동·수량 집계하지 않는다.
- 선별장 이동, 전체 예찰→수확→운송요청 통합, 실제 배출은 이번 시험 범위에 포함하지 않았다. 다음 단계는 운송 미션 환경·선별장 목적지 정합을 확인한 뒤 실제 경로 이동 연결이다.
- 이전 독립 낙하 시험의 수용60/75·외부낙하10·가장자리잔류5 기록은 그대로 유효하다. 이번 업무 진행 승인으로 해당 물리 결과를 성공으로 변경하지 않는다.

## 변경

- `basket_alignment_evaluation.json`: 최소 겹침0.72, 높이 양수 및 기존 정지 임계값/0.8초 유지. 완전포함 여부는 진단으로 유지.
- `farm_sim_devices/basket_alignment.py`: 기존 오프라인 기하 평가 재사용. 이동/회전·관측 공백 시 유지시간 초기화.
- `farm_sim_runtime/basket_monitor.py`, `fleet_config.py`, `run_fleet.py`: 설정에 지정한 두 로봇의 동일 시각 USD 프레임·wheel odom으로 평가하고 시뮬 장치에 증거 전달. 주행 제어 입력으로 전달하지 않는다.
- `farm_sim_devices/mechanical_ros.py`, `ros_adapter.py`: 기존 MechanicalOperation / TransportDeviceState 계약의 가상 장치. LID_OPEN/LID_CLOSE만 지원. 정렬 증거 만료·세션 변경·다른 task의 닫기·동시 요청 거부, 취소 처리, 수량 미측정 유지.
- `transport.json`, `transport_fleet.json`: 가상 장치와 평가 로봇 구성 연결. 평가 증거 없는 단독 운송 실행에서는 기구 준비 상태를 내지 않는다.
- `prepare_docking_alignment_trial.py`, `docking_alignment_probe.py`, `run_docking_alignment_trial.py`, `probe_sim_handoff.py`: 원본 harvest_clear를 수치 변경 없이 선택, `--handoff` 시험 경로 추가. 기존 도킹 단독 실행 유지.
- `analyze_docking_alignment.py`: 동일 평가기 사용. 과거 로그 재평가는 새 폴더에 저장하고 원래 완전포함 실패 자료는 보존.

## 검증 및 실패 기록

- 새 경계/장치 시험11개, 기존 기하·clock 순서·운송 하드웨어·통합 회귀25개: 총36 PASS. ROS 관련 시험은 `/opt/ros/jazzy/setup.bash`와 `scripts/env.sh sim` 적용 후 실행.
- sim_devices / sim_runtime / sim_config colcon 빌드3패키지 PASS, 문법·diff 공백 검사 PASS.
- 과거 성공 도킹 aa4c1a37… 새 기준 재평가: 정렬·정지5.183초, PASS. 이는 새 주행이 아니라 기록 재평가다.
- 실제 새 주행 session `6c02fdab5d674d7a9ffccb6521280cca`: 도킹/인계/이격 모두 성공. 이번1회 성공으로 이전 센서 지연·LEASE_EXPIRED 문제가 완전히 해결됐다고 판단하지 않는다.
- 시험 종료 SIGINT 정리 중 motion_gate는 context 종료 후 zero 발행으로 exit1, precision은 KeyboardInterrupt로 exit-2를 기록했다. 업무 중 실패와 구분한다. Isaac·두 장치 adapter·probe exit0, 실행 프로세스 종료 완료. 공통 종료 코드는 이번에 수정하지 않았다.
- 이번 최초 실행의 인계 구간은 외부 probe가 기다리며 일부 이벤트의 `sim_ns`가 고정됐다. 소요시간은 wall, 정렬 판정은 별도 실행 노드/증거의 sim_time_s를 사용했다. 후속 코드에서 `handoff_sim_ns`를 별도 실행 노드에서 기록하도록 수정했고 문법 검증했다. 원시 로그를 사후 수정하지 않았다.

## 자료와 재실행

- 공유: [summary.json](../test_results/20261027_basket_handoff/summary.json), [인계 이벤트](../test_results/20261027_basket_handoff/handoff_events.jsonl), 같은 폴더의 종료/정밀주행 로그.
- 원시 실행: `sim/runs/basket_handoff_20261027/live/41/`.
- 실제 위치: `sim/runs/drive_diagnostics/6c02fdab5d674d7a9ffccb6521280cca/`.
- 과거 데이터 재평가: `sim/runs/basket_handoff_20261027/replay72/`.

새 결과 디렉터리를 선택한다. 기존 결과를 덮어쓰지 않는다.

```bash
cd ~/main/farm_project
source /opt/ros/jazzy/setup.bash
source scripts/env.sh sim
export ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
python3 sim/tools/prepare_docking_alignment_trial.py sim/runs/basket_handoff_next
python3 sim/tools/run_docking_alignment_trial.py 41 sim/runs/basket_handoff_next --handoff
```

원복은 transport runtime.mechanical_device 비활성 및 fleet.basket_alignment 제거로 가상 기구 연결을 끄고, 평가 minimum_coverage를1.0으로 복귀한다. 기존 도킹 수치/USD는 이번에 변경하지 않았다. 미커밋·미푸시.

변경 파일 전달본: `sim/runs/basket_handoff_20261027_patch.zip`. 현재 미커밋 파일 전체 내용이므로 기존 미커밋 작업과 비교 후 적용한다.

```bash
cd ~/main/farm_project
unzip -o ~/Downloads/basket_handoff_20261027_patch.zip -d "$PWD"
```
