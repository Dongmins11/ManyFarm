# SEC01 한 사이클 통합 시험

2026-10-28. 사용자 “사이클 돌려보자 이제 한사이클만 딱”. 기준 `18d0e00` + 직전 미커밋 운송 회전105수정. 업무를 수락한 시도는 한 번만 실행하고 실패한 구간을 자동 반복하지 않는다.

## 범위와 연결

새 ScoutArea(SEC01) → 예찰결과 모든 윈도우 HarvestTask/동시 예찰 ReturnToStation → 실제 TransportPickup/DockTransfer → 기존 과실 가상 인계 → BucketUnload/레인 투입 → SortBatch → 운송 ReturnToStation → 수확 ReturnToStation. 하나의 Isaac 세션·원래 스테이션 초기배치, Domain13/SUBNET, CPU60Hz/render30Hz. 예찰/수확 태그 보정 ON. 실제 메시지의 성공 여부를 단계마다 검사한다.

- 관제는 제공된 Frontend handoff_worker 원본을 실제 DDS에 연결한다. 새 자동 순서 제어는 sim/tools의 시험기다. HTTP/운영 Frontend 전체 자동화 및 교통 예약 검증은 아니다. 교통 미연결 상태에서 인계 후 운송을 먼저 선별장/스테이션으로 내보낸 뒤 수확로봇을 복귀시키는 순서로 통로 충돌을 피한다.
- 기존 수확 완료 윈도우 fixture, 선별용 미리 적재된2개 과실 fixture는 사용하지 않는다. 초기288과실 모두 원래 씬에 남긴다. 현재 시뮬 세션의 최초 정답 snapshot을 `initial_scene.json`으로 보존한다.
- 승인된 정렬 유지 인계가 완료되면 실제 수확 바구니 내부의 분리된 빨강/노랑 과실만 운송 바구니로 가상 이동한다. 원래 prim/ID를 유지하며 과실을 생성하거나 부착 과실을 강제 분리하지 않는다. 팔 레이저 수량과 실제 바구니 과실 수는 동일하다고 가정하지 않는다. 기구 배출/낙하 물리 시험은 제외한다.
- 임시 마커42장착은 이전 SEC01 인계시험의 [0.34,-0.06,0.081]m를 유지한다. 실측 자료가 아니다. 인계 접근 목표는 기존 시험과 동일하게 윈도우의 Y·yaw를 유지하고 그래프 X로 투영한다. 운영 관제의 윈도우/그래프 목표 계약 해결로 보고하지 않는다.
- 선별장 모델과 갱신 지도를 세 로봇에 연결한다. 지도 원점/해상도/좌표계가 같고 태그 배치·카메라 보정·외부변환이 동일함을 확인한 뒤, 실행 복사본의 지도 해시 및 태그 자산 map_version만 갱신했다. 오래된 바인딩 검사 자체를 끄지 않는다.

## 수정 범위

공통/실물 제어·미션·판정은 수정하지 않는다. 새 `run_single_cycle.py`와 `single_cycle_steps.py`, 기존 `probe_handoff_window.py`의 선택형 전체시험 분기, `probe_sorter_cycle.py` 빈 배치 처리, `sorter_runtime.py` 가상 바구니 인계 및 run_fleet 연결. 모든 새 실행 설정은 sim/runs 아래 생성한다. 기존 분리시험의 입력 경로는 유지한다.

진행은 실제시간·액션 Goal/feedback/result를 events.jsonl에 남기며 `progress.json`에 최신 업무 이벤트, `partial_result.json`에 완료 윈도우까지 기록한다. 인계 후에는 post_sorter/events.jsonl 및 result.json에도 개별 결과가 남는다.

## 준비 실패도 보존

1. attempt01: 새 선별장 지도와 이전 태그 등록 지도 해시 불일치로 예찰/수확 launch 거절. 업무 Goal 전 실패. 전체 종료 중 선별 연결 거절 등 후속 로그를 함께 보존했다.
2. attempt02: 새 시험기에 예찰용 vision_python 지정이 누락되어 시스템 Python의 torch import 실패. 예찰 Goal은 준비 오류로 REJECT되어 미션 시작 전 종료. 기존 `/home/ysy/venv/robot_venv/bin/python`으로 수정했다.
3. attempt03: 교통 미연결 예찰은 RobotStatus를 발행하지 않는데 시험기가 그 토픽의 ready를 대기했다. 영상·Nav2는 정상 준비됐으나 Goal 전 대기 중 수동 정리. 실제 영상 준비 로그와 Nav2 lifecycle GetState 확인으로 수정했다.
4. attempt04: 21:25:26 KST ScoutArea Goal ACCEPT. **실제 업무를 수락한 첫 번째 사이클 시도**다. 이후 업무 실패 시 재실행하지 않는다.

준비 실패를 정상 주행/수확 실패나 성공한 사이클로 합산하지 않는다. 해당 raw 경로 `sim/runs/sec01_single_cycle_20261028_attempt01`~`04`, runner 로그는 각 경로명 뒤 `_runner.log`다.

## 검증과 결과

실행 전 기존 지도/씬/과실투입/인계 관련24검사, 가상 인계의 이전세션·정렬만료·차체이동·팔미복귀 거절4검사 통과. 문법 검사 및 farm_sim_runtime 빌드 통과. 세 로봇 초기배치/fixture과실없음/마커42·41·40/태그좌표 보존을 확인했다.

**실제 업무 시도1회 실패, 자동 재시험 없음. 전체 사이클 미완료.**

| 단계 | 결과 |
|---|---|
| SEC01 새 예찰 | SUCCESS, 관측5구간, 윈도우9개, expected13개 |
| 예찰 복귀 | 수확과 동시에 시작했으나 시험 종료 때 취소 요청; 완료 확인 없음 |
| 수확 W001 접근 | FAILED, expected1/harvested0/failed_count0. 팔 실행 전 주행 중단 |
| 인계·선별·운송 복귀·수확 복귀 | 미도달, 성공으로 집계하지 않음 |

실제 시작21:25:26, 예찰 완료21:28:49, 수확 실패21:32:09 KST. 준비 시간 제외 업무 실행 약6분43초. `result.json`의 최종 수확 오류는 `CANCEL_UNCONFIRMED: 정지 확인 실패: 속도·odom 최신성·시각 진행을 확인하세요.`다. 같은 시점 Nav2 로그에 `Failed to make progress`(진행 실패105)가 있다.

### 실패 지점과 확인된 사실

- 수확로봇은 북쪽 공통 통로 Y≈11.55에서 서쪽으로, 예찰로봇은 같은 통로에서 스테이션 쪽으로 후진 복귀했다. 교통 예약을 연결하지 않은 채 두 경로를 동시에 실행한 시험 구성이다.
- 두 로봇 중심이 약40cm까지 가까워졌고, 시간 근접 샘플의 Nav2 footprint 기준으로 겹침이 나온다. 실제 접촉력은 수집하지 않았으므로 정확한 충돌 접촉점·힘은 확정하지 않는다. 이전 진행 설명의 약35cm는 시각 차이가 있는 근접 샘플 비교였다. 저장된 최근접 대응 표본은38.6cm/시각차 약0.2초이며 수 mm 정확도의 동시 거리 측정으로 해석하지 않는다.
- 시뮬215.07→230.07초 수확 실제 위치 변화2.10mm, 방향 변화0.76°에 그쳤다. 이동·회전 명령은 계속 있었다. 예찰과 수확이 가까운 상태에서 비슷한 방향으로 함께 밀리는 움직임도 있어 **동시 통로 진입에 따른 로봇 간 물리 간섭이 유력**하다.
- 수확은 이미 `PoseProgressChecker`, 이동0.1m/회전0.1rad/20초를 사용했다. 방금 고친 운송 마지막회전의 “회전을 진행으로 인정하지 않음”과 다르다. 이번에는 실제 운동 자체가 거의 멈췄다.
- 수확 정지명령 뒤에도 wheel odom에 수 cm/s 속도가 남아 최종 정지 확인이 실패했다. 종료 예외가 최초 예외를 감싸는 구조이며, 최초 예외가 들어있는 `/harvest_01/task_events`는 이번 probe가 구독하지 않아 영속 원문이 없다. 따라서105가 최초 중단 원인인지, 이미 중단하는 과정에서 추가 발생한 것인지까지 단정하지 않는다. 다음 시험의 진단 누락을 막기 위해 해당 transient-local 진단 토픽과 종료 시 액션 결과 구독/기록을 추가했다. **이 계측 추가 뒤 재시험하지 않았다.**

### 책임 범위와 다음 작업

현재 증거는 팔 성능이나 마지막 운송 복귀보다 **교통 미연결 상태에서의 시험 순서 구성**을 먼저 수정해야 함을 가리킨다. 공유 통로를 예찰로봇이 비운 다음 수확로봇을 진입시키는 대기를 권한다. 공통 진행 제한/정지 기준을 완화해 밀고 지나가게 하지 않는다. 실제 충돌력 미측정/최초 예외 원문 누락은 조사 한계로 남긴다.

수확 이후 가상 과실 인계와 선별 연결은 코드·거절 검사만 통과했고 이번에는 실제 실행하지 못했다. 정상 인계/양 로봇 복귀가 검증됐다고 보고하지 않는다.

모든 시험 소유 프로세스 종료 확인. runner/probe exit1(시험 실패), scout/harvest/transport/Isaac exit0. gate exit1 및 precision−2는 기존 SIGINT 정리 과정의 context/KeyboardInterrupt 로그로 별도 보존했다. 과거 준비 오류도 삭제하지 않았다. 공유 결과는 `sim/docs/test_results/20261028_sec01_single_cycle/`, 원시 로그는 위 runs 경로다. 변경은 미커밋·미푸시다.

## 변경 파일 전달

[현재 변경 파일 ZIP](../../runs/sec01_single_cycle_20261028_changes.zip)은 기준18d0e00 이후 직전 스테이션105 수정과 이번 시험 연결/보고 자료를 포함한다. 현재 상태 저장용이며 통합 완주 검증을 의미하지 않는다.

```bash
cd /home/ysy/main/farm_project
unzip -o sim/runs/sec01_single_cycle_20261028_changes.zip -d .
```

## 후속 — SEC01 완료 후 SEC02 연속 예찰

사용자 “예찰은 복귀하지 말고 그대로 SEC02 예찰 시작” 지시에 따라 시뮬 시험기의 다음 명령을 ReturnToStation에서 ScoutArea(SEC02)로 변경했다. SEC01의 수확 목록은 유지하고 SEC02 결과는 scout_sec02_result.json에 별도 저장한다. SEC02 완료 후 추가 작업/복귀 없이 기존 WAIT_FOR_COMMAND로 대기하며, SEC01 인계 전에 SEC02의 실제 성공 결과도 확인한다. 공통 코드/주행/실물 판정은 변경하지 않는다.

현재 로컬 Frontend는 교통 설계 자료만 포함하고 실행 backend에서 AcquirePassage 서버는 확인되지 않았다. 이번 시험 프로파일의 traffic.enabled는 기본 false다. 이전 정체 위치는 서로 다른 평행 주행선이 아니라 두 그래프에 공통인 북쪽 Y=11.5 통로다. SEC01→SEC02 정적 경로는 아래쪽 Y=0 통로를 통과한다. 공통 RouteGraph로 SEC01 끝(-6.655,2)→SEC02 시작(-3.345,2) 경로 7.31m를 확인했다. 실제 임무는 마지막 관측점에서 기존 구간 이탈/진입 정책을 사용하므로 이 정적 길이를 실제 주행 거리로 집계하지 않는다. 이것이 교통관제 통합 검증을 대신하지는 않는다.

실행 경로: sim/runs/sec01_cycle_scout_sec02_20261028_attempt01~02. attempt01은 hcr_sorting overlay 누락으로 Goal 전 준비 종료; 이전 업무 실패와 구분한다. 패키지 탐색을 실행 전 검사하도록 추가하고 기존 선별 overlay를 포함해 attempt02 시작. CPU60/render30, Domain13/SUBNET, 태그 보정 유지. 현재 결과는 진행 중이며 종료 결과를 별도 기록한다. 수정 파일 문법/공통 경로 계산 확인; 실제 연속 예찰·SEC01 완주는 아직 검증 중이다.

- attempt02 실제 확인: 21:49:16 KST SEC01 예찰 SUCCESS(5구간,9윈도우,expected13) 후 SEC02 ScoutArea 수락 및 SEC01 W001 HarvestTask 수락. SEC02 survey session=3eb7cc0fcbf3 RUNNING, 예찰 실제 위치가 남쪽(-6.55,-0.10)까지 진행한 것을 확인했다. 같은 시점 수확은 북쪽(-2.00,11.62)에서 접근 중이다. 예찰 ReturnToStation 명령 없음. 전체 수확·인계·선별·복귀 결과는 아직 미확정이며 시험 runner가 계속 실행한다. 자동 업무 재시도는 없다.

후속 변경 묶음: [SEC02 연속 예찰 변경 ZIP](../../runs/sec01_cycle_scout_sec02_20261028_changes.zip). 이번 시뮬 시험기3파일 및 관련 상태/이력/보고서3파일의 현재 내용이다. 앞선 전체 변경 묶음을 대체하는 전체 저장소 백업은 아니다.

```bash
cd /home/ysy/main/farm_project
unzip -o sim/runs/sec01_cycle_scout_sec02_20261028_changes.zip -d .
```

후속 시험 최종 결과(10/29 확인): [SEC01_CYCLE_RESULT_20261029.md](SEC01_CYCLE_RESULT_20261029.md). SEC01 모든수확액션완료/8개수확후 운송접수 장치준비오류로종료,전체미완주. 위 진행중표현은 당시상태다.
