# 운송 접수 전 장치 서비스 준비 순서 수정 — 2026-10-29

사용자 “수정해” 승인. 기준18d0e00+기존미커밋변경. 이번 변경은 시뮬 시험기4파일에 한정한다. 공통 TriggerDevice/운송 FSM/판정·시간제한·물리/실물 설정은 변경하지 않는다.

## 원인과 수정

이전 한사이클은 수확까지52분 수행한 뒤 TransportPickup 접수에서 `수령 장치 미연결: LID_OPEN`으로 거절됐다. 덮개 준비 검사도 UNLOAD/STOP endpoint를 요구하지만, 선별장 하역용 두 서비스를 제공하는 probe_sorter_cycle은 인계 후에야 시작하는 순환 의존이 있었다.

- run_single_cycle: post_sorter 시험기를 시작부터 실행한다. post_sorter 성공 종료는 정상 단계 완료로 인정하고 비정상 종료는 기존 supervisor에서 실패로 처리한다.
- probe_sorter_cycle: `--wait-for-handoff`에서 장치 서비스와 최신 odom/상태 수신은 즉시 시작한다. fixture의 handoff_complete가 true가 될 때까지 BucketUnload/SortBatch/ReturnToStation 명령을 보내지 않는다. 대기 중 고용량 위치/scan 로그 저장은 하지 않으며 STOP 판정용 최신 odom은 계속 갱신한다. 기존 단독 시험은 옵션 없이 동일 순서로 실행한다.
- single_cycle_steps: 실제 양쪽 인계 성공 뒤 기존 과실 manifest로 fixture를 원자적으로 갱신하고 handoff_complete를 설정한다. 이미 떠 있는 동일 서비스/프로세스가 선별장 작업을 이어간다. 새 프로세스 중복 생성/서비스 교체는 하지 않는다.
- probe_handoff_window: 긴 예찰·수확 전에 실행 프로파일의 덮개열기/닫기/하역/정지 서비스4개 연결을 실제 확인한다. 연결 실패 시 예찰 시작 전에 중단한다.
- 결과 파일은 임시 파일→rename으로 게시해 읽는 쪽이 반쪽 JSON을 읽지 않도록 한다.

## 직접 검증

2026-10-29 18:12~18:13 KST, Domain13/SUBNET, 기존 CPU60/render30 농장과 실제 ROS 운송 서버를 실행했다. 이전 거절된 staging_pose를 그대로 사용한 **접수→즉시 취소 시험**이며 예찰·수확을 다시 수행하거나 성공을 가정하지 않았다.

1. 예찰/인계 전 실제 네 서비스 연결 PASS.
2. 도킹 전 UNLOAD 실제 호출은 success=false: 기존 도킹/정지/허가 조건 유지 PASS.
3. TransportPickup 실제 Goal ACCEPT: 이전 LID_OPEN 준비 거절 미발생.
4. 즉시 취소 결과 status5/CANCELED/error_code NONE: 정지 확인 PASS.
5. 인계 허가 없는 동안 post_sorter의 unload_goal/sort_goal/return_goal 기록 없음. 서비스만 제공하고 작업은 대기함을 확인.
6. 기존 가상 과실 인계/투입 거절 관련8검사 PASS. 문법/diff 검사 PASS.

runner/probe exit0, 시험 소유 프로세스 종료 기록 확인. gate exit1/precision−2/post_sorter−2는 SIGINT 정리 과정 기록이다. post_sorter는 인계 대기 중 취소됐으며 하역 실패로 집계하지 않는다. 최종 메타데이터에서 접수시험을 pickup_preflight.json으로 구분해 전체사이클 모니터 자동선택 대상에서 제외했다. 이 분류/설명 변경은 정적 검사만 했고 ROS 시험을 반복하지 않았다.

**전체 인계→선별→복귀는 이번에 재시험하지 않았다.** 실제 인계 허가 이후 장기 연속 수행까지 통과한 것으로 보고하지 않는다. 다음 단계는 수정된 연결로 인계 이후 연속 시험이다.

## 실행 및 자료

접수/취소만 검증하는 명령(새 출력 폴더 사용):

```bash
cd /home/ysy/main/farm_project
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/setup.bash
source sim/ros_ws/install/setup.bash
source sim/runs/hcr3a_intake_20261028/ros/install/local_setup.bash
export ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
python3 sim/tools/run_single_cycle.py sim/runs/pickup_service_order_NEW \
  --pickup-preflight sim/runs/sec01_cycle_scout_sec02_20261028_attempt02/runtime/pickup_goal.json
```

원문: sim/runs/pickup_service_order_20261029_attempt01/. 공유근거: sim/docs/test_results/20261029_pickup_service_order/. 이전52분 수확 자료는 변경하지 않았다. 커밋/푸시 미실시.

복원은 이번4파일의 조기시작/허가대기/사전검사를 이전 실행순서로 되돌리는 것이며, 기존 LID_OPEN 거절이 재발하므로 권하지 않는다.

[변경 파일 ZIP](../../runs/pickup_service_order_20261029_changes.zip)은 이번4개 시험기 파일의 현재 내용과 보고자료를 포함한다. 기존 미커밋 사이클 연결 변경도 파일 안에 포함되어 있다.

```bash
cd /home/ysy/main/farm_project
unzip -o sim/runs/pickup_service_order_20261029_changes.zip -d .
```
