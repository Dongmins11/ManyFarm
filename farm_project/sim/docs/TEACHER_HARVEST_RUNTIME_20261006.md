# 도착 후 sim Teacher 수확 실행

기준: 2026-10-06, `main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd` 이후 미커밋 구현.
이 문서는 최신 사용자 승인 범위와 실제 코드·설정을 설명한다. **순수 계산·정책 CPU 시험은 확인했으며, 이번 구현의 실제 Isaac 수확 결과는 아래 검증 표에 별도로 기록한다. 구현 존재를 수확 성공 검증으로 읽지 않는다.**

## 승인 범위와 현재 동작

사용자는 대부분의 실행을 sim에 두고, 공통 수확에는 **기존 이동·정지·도착 확인 뒤 팔 작업을 호출하는 연결**을 추가하도록 승인했다. 기존 외부 `HarvestTask` 형식을 그대로 사용한다. 내부 팔 작업도 같은 Action 형식을 `sim/harvest_arm` endpoint에서 재사용하며 새 `farm_interfaces` 메시지·서비스·Action을 추가하지 않는다.

현재 정차 위치에서 Teacher 근거리 조건에 들어오는 **빨강·노랑을 과실당 한 번** 시도한다. 녹색과 추가 차체 이동은 제외한다. 개별 과실이 실패해도 실제 팔 복귀가 끝나면 다음 과실을 시도한다. 확정 대상의 처리가 모두 끝나면 작업은 `SUCCESS`이며, 실제 적재·실패 수량은 따로 전달한다. 제어 상실·복귀 실패·취소 등으로 처리를 중단한 상태와 구분한다.

이번 Teacher 시험에는 현재 Isaac 과실 pose·접촉·줄기 상태를 사용한다. 이는 사용자가 승인한 **sim Teacher 검증에 한정된 정답 입력 예외**다. 예찰 비전, Nav2 위치 입력, Student, 실물 장치에 정답을 주입하지 않는다. 실물 설정과 공통 주행 알고리즘을 변경하지 않는다.

이전 [통합 검토](TEACHER_HARVEST_INTEGRATION_REVIEW_20261006.md)와 [공통 변경 제안](proposals/HARVEST_ARM_COMMON_CONTRACT_20261006.md)의 새 후보조회·`PickFruit` 타입·공통 Window 실행기 안은 채택하지 않았다. 해당 문서는 검토 이력이며 이 문서의 좁은 적용 범위가 우선한다.

## 실행 구조

```text
기존 외부 HarvestTask
  → 공통 HarvestMission: Nav2 이동 → 정지·실제 도착 확인
  → 공통 ArmActionClient: 기존 HarvestTask를 내부 endpoint로 전달
  → sim ArmRosServer: 로봇/세션/Goal 검증, UDP start·keepalive·cancel
  → 기존 run_fleet의 ArmSession: 대상 확정 → 한 과실 정책 → 실제 복귀 → 결과 집계
  → TeacherDevice: 현재 농장 상태 측정 / 오른팔 drive 목표 적용
  → TeacherController: 원본 4정책·상태 수식 / 20Hz 관절 증가 목표
  → 동일한 농장 World의 물리·렌더 루프
```

| 위치 | 책임 |
|---|---|
| `robot/ros_ws/src/harvest_robot/harvest_robot/mission.py`, `arm_client.py` | 도착 후 장치 Action 호출, 취소·종료 확인. sim 패키지를 import하지 않음 |
| 같은 패키지 `node.py`, `communication.py`, `contract.py` | 설정 선택, 기존 Feedback/Result의 검증된 수량 전달과 실패·취소 처리 |
| `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/arm_ros.py` | 기존 Action ↔ 로컬 UDP, 세션·작업 상관관계, wall 시간 timeout |
| 같은 sim 패키지 `arm_session.py` | 현재 정차 위치의 후보·1회 시도 기록, 실제 복귀, 정지 확인, 작업 결과 |
| 같은 sim 패키지 `teacher_device.py` | PhysX 실제 pose·힘·관절 측정, 좌표 변환, 6축 목표 명령 |
| 같은 sim 패키지 `teacher_policy.py`, `teacher_state.py`, `_teacher_vendor/` | 정책 로딩·관측·단계 전환·원본 수식·물리 결과 진단 |
| `sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py` | 기존 World에 연결하고 물리 tick 뒤 접촉/분리 증거를 수집 |
| `sim/ros_ws/src/farm_sim_config/config/teacher_policy.json` | 체크포인트/해시, 원본 평가 옵션, 좌표·동작·정지 설정 |

원본 `HarvestEnv`를 생성하지 않는다. Teacher 코드에는 자체 `World.step()`, 장면 reset, 과실 재부착·삭제, 관절 teleport가 없다. 목표 변경 시 정책 내부 상태만 초기화하고, 실제 과실과 이전 적재물은 계속 물리 장면에 남는다.

수확·복귀·안착 확인 중에는 기존 [동적 물리](ADAPTIVE_HARVEST_PHYSICS_20261006.md)를 통해 팔 주변 과실을 활성화하고 물리 480Hz를 요청한다. 정책은 시뮬 시간 기준 20Hz, 렌더는 60Hz다. 시뮬 시간과 wall 시간을 혼용해 정책 주기를 바꾸지 않는다. 분리 과실은 동적으로 유지하며 바구니에 월드 고정하지 않는다.

## 대상·좌표·관측 계약

대상은 현재 물리 상태에서 부착된 빨강·노랑이고, 원래 과실 prim 경로를 지속 ID로 쓴다. 최초 후보 snapshot을 HOME TCP 거리순·ID순으로 정렬해 각각 한 번 처리한다. 시작 직전에 후보가 여전히 유효한지도 다시 확인한다. 처리한 ID는 해당 Isaac 실행 세션에서 보존하여 새 요청으로 자동 재시도하지 않는다. `expected_count`를 후보 수나 실제 성공 수로 복사하지 않는다.

| 기준 | 현재 설정 |
|---|---|
| 좌표 | 실제 오른팔 장착점 `arm_2/base_link`, 단위 m |
| 과실 root 외곽 | X `[0.265,0.365]`, Y `[-0.175,+0.175]`, Z `[-0.10,+0.35]` |
| HOME TCP 기준 추가 조건 | 거리 `0.09 < d < 0.18` m |
| HOME TCP | 팔 기준 약 `[0.21640447,-0.00039200,0.27409939]` m |
| 원본 정책의 팔 원점 | 정책 좌표 `[0.235,-0.19,0.713]` m |
| 정책 변환 | `T_policy_from_world = T_policy_from_arm × inverse(T_world_from_arm_at_selection)` |

이 연속 범위는 후보 필터다. 전달된 **18개 이산 후보와 일치한다는 뜻이나 IK·접근/복귀 충돌 없음·수확 성공 인증이 아니다.** 물리 활성화 반경 0.8m도 정책 도달 범위와 다르다. Task의 `goal_pose`는 차체의 정차 목표이며 과실 pose가 아니다. Window ID를 분해해 과실 위치를 만들지 않는다.

각 시도 시작 때 실제 팔 장착 TF를 저장하고 pose·자세·속도·anchor·힘을 같은 정책 프레임으로 변환한다. 매 정책 주기 최신 상태를 공급하며, 차체가 움직이거나 장착 TF가 허용 범위를 벗어나면 중단한다. root, COM, 파지 중심, 꼭지점은 서로 다르다. 원본 파지 중심은 `root + R × [0,0,-0.006]` m다.

82차원 관측은 원본 순서를 유지한다. 정규화 관절 위치6, 속도6, 직전 명령6, TCP 위치3·자세4, 목표 상대 위치3·속도3·자세4, 박스 상대 위치3, 진행 스칼라6, 과실 위치8슬롯24·mask8, anchor3, 줄기 상태3이다. 원본 `selected_teacher_observation()`처럼 **과실8슬롯 중 선택 목표의 한 슬롯과 mask만 채우고 나머지는 0**이다. 실제 이웃 collider와 접촉은 존재하지만 정책이 주변 과실을 관측해 회피한다고 설명하지 않는다.

양손가락의 목표 과실 접촉은 PhysX impulse를 해당 실제 물리 dt로 나눈 N 값이다. 분리 판정에는 분리 직전 integration의 pose/contact snapshot을 사용한다. 이후 새 접촉을 소급해 유효 파지·분리 증거로 만들지 않는다.

## 원본 정책과의 일치 범위

런타임 파일은 `sim/assets/robotarm_teacher/{entry,pull,transport,place}/`에 복사한 정책4개와 각 `run.json`이다. [프로파일](../ros_ws/src/farm_sim_config/config/teacher_policy.json)에 원본 경로와 SHA-256을 기록하고 로딩 전에 파일·run 해시를 검증한다. 수신 폴더를 실행 시 참조하지 않는다. `sim/runs/robotarm/received_20261006_143434/manyfarm_robotarm` 원본은 수정하지 않았다.

- 공식 RSL-RL `ActorCritic` 구조와 정규화 상태를 strict load한다. actor/critic 은닉층 `[256,256,128]`, ELU, 관측82 → 명령6이며 현재 추론 장치는 CPU다.
- 원본 `StagedTeacher`의 entry/grasp → pull → transport → place routing을 재사용한다. transport 초기 배율0.25에서3초 동안1로 올리는 보정을 유지한다. 현재 `release_mode=fixed`에서는 place 가중치도 검증·로딩하지만 실제 놓기 명령을 원본 고정 출력으로 덮어쓴다.
- 명령은 `[-1,1]`로 clamp한 뒤 기존 목표에 증가분을 더한다. 20Hz에서 팔5축 최대 증분은 `0.8×0.05=0.04 rad`, 그리퍼는 `1.2×0.05=0.06 rad`다. 고정 놓기 `+0.15`는 주기당 그리퍼 `+0.009 rad`이며 팔 증가분은0이다. 그리퍼 목표 오차 제한·파지 유지·재압착 보정도 원본 수식을 따른다.
- 원본의 파지 유지0.25초, 분리 후 보유0.5초, 놓기 전 정지0.3초, 박스 안착0.6초와 유효 파지·분리·보유/놓기 승인 상태를 유지한다. 관절 한계는 실제 모바일 articulation에서 읽어 원본 기준과 대조한다.
- `_teacher_vendor/provenance.json`에 복제 근거가 있다. `logic.py`, `entry_grasp.py`, `sequence.py`, `settings.py`, `staged_teacher.py`는 원본과 바이트/해시가 일치한다. `kernel.py`의 7개 메서드 `_grasp_center`, `_grasp_orientation`, `_pre_physics_step`, `_update_task`, `_target_elapsed_steps`, `proprio`, `_get_observations`는 원본 AST 일치를 확인했다. World 생성·step 부분은 이식하지 않았다.

**위 일치는 계산·정책 이식 범위이지 전체 시뮬 동등성이나 실제 성공률 보장이 아니다.** 체크포인트는 원래 35g 학습물이고 전달 평가 설정이9g다. 이번에9g로 재학습하지 않았다. 농장 과실은 받은 자산을 Teacher 폭70mm·높이75mm로 맞췄지만, 원본 평가와 농장 전체 기하·배치·회전·이웃 간격이 다르다. 이전 다른 모양/크기 농장 과실에서 성공했다는 근거도 새 이식의 성능 보장이 아니다.

고정형 원본 팔과 바퀴가 있는 모바일의 접촉 환경도 다르다. 모바일 전체 articulation solver/self-collision과 주행 바닥을 원본 학습 장면으로 덮어쓰지 않았다. 원본의 카메라 고정 병합 body와 현재 별도 body 차이 때문에 고정 손가락 접촉은 실제 gripper body에서 읽고 카메라 접촉은 팔 접촉으로 기록한다. 물리 차이는 [물리 적용 보고서](ROBOTARM_PHYSICS_20261006.md)에 분리해 기록한다.

## 물리적 성과와 작업 종료 의미

| 기록/상태 | 의미 |
|---|---|
| `physical_status=SUCCEEDED` | 실제 줄기가 분리되고 각 손가락의 목표 접촉력 norm이0.08N 미만이며, 과실 collider 전체가 박스 범위 안에 있고 선속도0.12m/s 미만인 상태를 연속0.6초 충족 |
| `teacher_strict_success` | 원본의 유효 파지·분리·보유·놓기 승인까지 포함한 RL 성공 진단. 사용자 적재 수량과 별도로 보존 |
| 과실 실패 | 미분리·놓침·박스 밖 낙하·시간초과 등. 실제 팔 복귀가 확인되면 다음 대상 진행 |
| 작업 `SUCCESS` | 확정 후보 전체 처리와 종료 정지가 완료됨. 예: 성공2/실패1도 SUCCESS, 수확량2/실패량1 |
| 작업 `FAILED` | 제어/통신/관측 오류, 비목표 과실 분리, 베이스 이동, 복귀 실패, 종료 미확인 등으로 중단 |
| 작업 `CANCELED` | 취소 요청 뒤 실제 정지가 확인됨. 이미 확정한 수량은 보존 |

물리적 안착은 원본 박스 `[0.305,-0.095,0.506]`~`[0.495,0.095,0.701]` m를 같은 정책 프레임에서 검사한다. 일반 면 허용오차3mm, 바닥 하한 허용오차10mm다. root 점 하나만 안에 있다는 이유로 성공 처리하지 않는다. 한 손가락만0.08N 이상 접촉해도 성공을 막고 안착 연속 시간을 초기화한다. 이 무접촉 조건은 사용자 물리 성과 판정에 적용하며 원본 strict 수식은 변경하지 않는다.

정책이 종료되면 현재 실제 관절 위치에서 복귀를 시작한다. 측정한 이동 경로를 거꾸로 따라가며 실제 관절 목표만 내고, HOME 도달·속도·집게 열림·접촉 상한을 확인한다. 복귀 후 최대2초의 시뮬 시간 동안 추가 안착을 관찰한 뒤 물리 성과를 확정한다. 원본 실행기의 첫 실패 즉시 batch 중단과 달리, 이 부분은 사용자가 승인한 일반 실패 후 다음 대상 처리다. 원본 복귀 코드의 물리25ms/계산50ms 불일치를 재현하지 않고 기존 농장 루프의 실제20Hz 제어를 사용한다.

앞서 성공으로 집계한 적재물의 박스 이탈 감시는 `PREVIOUS_DEPOSIT_LOST` 오류로 작업을 중단하는 계약이다. 누적 Feedback을 역행시키지 않으므로 이미 발표한 성공 수량을 빼지 않고 최종 상실 오류를 함께 남긴다. **이 감시를 포함한 실제 장면 시험은 아래 검증 표에서 확인해야 한다.** 성공 수량만으로 이후 운송 중 보존까지 인증하지 않는다.

정상 빈 후보는 SUCCESS/수확0/실패0일 수 있다. 예상 수량과의 차이를 가짜 성공·실패로 채우지 않는다. 정지 ACK가 없으면 성공·취소로 추정하지 않고 `CANCEL_UNCONFIRMED`와 차단 상태를 유지한다. 취소 수락 응답 자체는 팔 정지 증거가 아니다.

## 실행 방법

### 1. 유한 시간 단독 물리 검사

프로젝트 루트에서 실행한다. 기본 Isaac Python은 `~/isaac/env_isaaclab/bin/python`이며 필요하면 `--isaac-python`으로 지정한다.

```bash
cd ~/main/farm_project
python3 sim/tools/check_teacher_harvest.py \
  --gui \
  --output sim/runs/robotarm/teacher_check/result.json
```

이 도구는 기존 `run_fleet.py`를 한 번 실행하고 로컬 UDP로 팔 작업을 요청한다. **실제 ROS/Nav2 도착 시험이 아니다.** 기본 `sim/tests/fixtures/teacher_dock.json`에 따라 검사 시작 전 차체 station만 배치한다. 농장288개 과실의 위치·회전·ID는 유지하고, 실행 도중 차체·관절·과실을 teleport/reset하지 않는다. fixture의 예상 ID와 실제 선택·실행한 ID를 대조하며, 예상 수량을 Teacher 성공 수량으로 주입하지 않는다.

`--gui`는 화면을 보여 주는 옵션이며 계속 열린 상태를 유지하는 옵션이 아니다. terminal 결과, 기본90초의 시뮬 실행 한도 또는600초의 wall 한도에 도달하면 **GUI와 자식 Isaac 프로세스가 자동 종료**된다. 한도는 `--duration-s`, `--wall-timeout-s`로 바꿀 수 있다. 별도 `--cancel-after-s`는 시뮬 시간 기준 취소 검사용이다. 같은 검사 도구를 동시에 여러 개 실행하지 않는다.

결과 디렉터리에 `result.json`, `isaac.log`, 검사에 사용한 fleet/station/device 설정 사본이 남는다. `result.json`의 `terminal.status`, `success_count`, `failed_count`, `safe_stopped`, `error_code`를 함께 확인한다. **기본 exit0은 예상 과실의 실제 정책 실행·로그/수량 정합·정지·프로세스 정상 종료를 통과했다는 뜻이며 과실 수확 성공을 뜻하지 않는다.** `passed`(검사), `protocol_completed`(결과·정지), `task_status`(작업), `harvested_count`/`failure_count`(성과)가 별도다. 실제 안착 성공을 요구하려면 `--require-harvest`를 추가한다. 과실 수확0이면 이 옵션의 검사는 실패한다. 종료는 프레임 경계에서 수행하며 Kit의 정상 종료를 최대60초 기다린다. 개별 작업 상세는 결과의 `teacher_log_dir`에 있는 `request.json`, `trace.jsonl`, `result.json`에서 확인한다.

USD를 Isaac GUI에서 직접 여는 것만으로 이 동작을 실행할 수는 없다. 드라이브/줄기/동적 물리·Teacher와 bridge가 `run_fleet`의 실행 세션에 연결되어야 한다.

### 2. 실제 수확 서버와 함께 실행

기존 [시뮬 실행 가이드](RUN_GUIDE_20261006.md)의 ROS Jazzy/비전 환경을 준비한다. 이번 소스 변경은 공통 수확 패키지와 sim 패키지를 모두 포함하므로 빌드 후 새 터미널 환경을 적용한다.

```bash
cd ~/main/farm_project
bash scripts/build.sh sim
source scripts/env.sh sim
export FARM_ISAAC_PYTHON="$HOME/isaac/env_isaaclab/bin/python"
ros2 launch farm_sim_runtime all.launch.py \
  project_root:="$PWD" \
  isaac_python:="$FARM_ISAAC_PYTHON" \
  harvest:=true \
  headless:=false
```

예찰을 함께 사용할 때는 비전 환경의 Python을 기존 가이드대로 `vision_python:=...`에 지정한다. 수확 서버만 시험하려면 `scout:=false`를 추가할 수 있다. `rviz:=false`는 RViz만 제외하고, `headless:=true`는 Isaac 화면을 제외한다.

`harvest`의 launch 기본값은 false이므로 **`harvest:=true`가 필요하다.** 이때 기본 fleet은 `harvest_fleet.json`, 수확 환경은 `harvest_runtime.yaml`이다. 현행 `harvest_task.json`은 `ARRIVAL_THEN_ARM`, `harvest.json`의 `runtime.harvest_arm.enabled`는 true이고 `teacher_policy.json`을 참조한다. 추가 `teacher:=true` 인자는 없다. 일반 전체 launch는 자동 종료되는 검사 도구와 다르다.

이 명령은 서버를 시작하며 수확 Goal까지 자동 전송하지 않는다. 기존 관제/수확 시험 클라이언트에서 실제 `HarvestTask`를 요청해야 한다. 기존 공통 Navigator의 이동·정지·도착 검사를 통과한 뒤 팔 Action을 호출한다. 도착 전 이동 실패를 팔 성공으로 바꾸지 않는다. `farm_bringup all.launch.py`는 이 전체 조합 명령의 대체가 아니다.

### 3. CPU 정책·계산 재검사

```bash
cd ~/main/farm_project
PYTHONDONTWRITEBYTECODE=1 "$HOME/isaac/env_isaaclab/bin/python" \
  -m unittest discover -s sim/tests -p 'test_teacher_*.py' -v
```

체크포인트 추론은 CPU에서 실행한다. 이 시험 명령은 Isaac World를 만들거나 GPU 물리 장면을 시작하지 않는다. Isaac용 환경에 설치된 Torch/RSL-RL을 사용한다.

## 검증 기록과 남은 항목

기준 환경은 Isaac Sim5.1.0, Torch2.7.0+cu128, RSL-RL3.1.2, Python3.11, RTX4070SUPER다. ROS Jazzy는 시스템 Python3.12다. 최종 검사 도구의 통과는 정상 수확 성공 인증과 구분한다.

| 검사 | 직접 확인 결과 | 근거/범위 |
|---|---|---|
| 단위·USD 전체 | 178개 중176 PASS, ROS2개는 이 환경에서 skip | `sim/runs/robotarm/teacher_integration_20261006/unit_usd_final.log` |
| 순수 Teacher | 36/36 PASS | state17 + policy9 + device10. 실제4정책·run SHA/정규화/82→6 추론 포함 |
| 원본 수식 보존 | PASS | vendor5파일 해시, kernel7메서드 AST 동등 |
| 공통·시뮬 빌드 | 4패키지 PASS | harvest_robot + farm_sim_devices/config/runtime |
| 실제 ROS/UDP | 2/2 PASS | 자기 UUID 취소 ACK와terminal, 누적2/1, start 유실 재전송, 센서/속도 명령 병행. 실제 물리는 없는 시험 장치 |
| 실제 Isaac 정책·복귀·결과 | **최종 smoke PASS** | `attempt04_final/result.json`: 45회 정책 명령, 정상 종료code0, 후보/실행ID/누적 수량/trace 정합 모두 통과. 성과는0성공/1실패 |
| 실제 바구니 안착 | **미달: 서로 다른 과실3개에서0개** | 아래 실제 시도 표. `--require-harvest` 재평가도 정확히 실패 |
| 실제 취소·정지 | **최종 PASS** | `cancel_verified/result.json`: 정책10회 실행 중 취소, 실제 정지 후CANCELED, 수량0/0 보존, 모든 검사 및프로세스code0 |
| 기존 적재물 이탈 감시 | 단위 검증 PASS, 실제 적재 장면 미검증 | 현재 TF의 전체 collider 경계·바닥 허용오차 및 세션 중단 시험 |
| Nav2 이동→도착→팔→최종 Result | 실제 전체 장면 미검증 | 초기 배치 fixture 및 ROS 시험 장치로 대체하지 않음 |
| 여러 과실의 실패 후 다음 시도 | 단위 검증 PASS, 실제 여러 과실 미검증 | 실제3개 정차 fixture는 각각 후보1개였다 |

실제 농장 시험은 원래288개 과실의 위치·회전·ID를 유지했다. 각 실행은 시험용 초기 차체 배치만 바꾸었다.

| 실행 | 기존 과실 | 관측 결과 | 최종 성과 |
|---|---|---|---|
| attempt02 | Bed02 / Pepper0031 yellow | ENTRY20초 시간 초과, 실제 HOME 복귀·정지 | SUCCESS,0/1 |
| attempt03 | Bed05 / Pepper0030 red | 양손가락 접촉·줄기 분리, `bad_detach`, 낙하 후 실제 복귀 | SUCCESS,0/1 |
| attempt04_final | Bed01 / Pepper0027 red | `bad_detach`, 낙하 후 실제 복귀·정지 | SUCCESS,0/1; 최종 smoke PASS |

위 `SUCCESS`는 정차 후보 처리를 마쳤다는 의미다. **농장 로봇팔이 정상적으로 주워 담는 성능은 아직 달성하지 못했다.** ENTRY 이후 유효 분리/운반/놓기 단계를 실제 농장에서 끝까지 통과했다고 볼 수 없다. 실패 기준을 완화하거나 과실 pose를 속여 성공으로 바꾸지 않았다.

중간 시행착오도 보존한다. attempt01은 SDK가 여러 팔 sensor path와 빈 filter 목록의 길이를 맞추지 못해 초기화 실패했다. 센서별 빈 filter를 명시해 수정하고 이후 실제 장면에서 확인했다. attempt02/03은 terminal 정지 후 시험기의 즉시SIGINT에서 프로세스가-11로 끝났다. 첫 취소 검사 `cancel_final`도20초의 짧은 종료 대기로 정상 종료를 방해했다. 최종 도구는 `--stop-after-arm-job`으로 프레임 경계에서 종료하고60초 기다리며, 비정상 종료를 검사 실패로 기록한다. 중간 로그를 최종 프로세스 PASS로 합산하지 않는다.

원본 운동학과 attempt02의401샘플을 대조한 TCP 위치 오차는 최대0.2921mm, 자세 차이는0.052412°였다. 최초 HOME 차이는0.000355mm였으며, 후기 차이는 실제 차체의 미세 yaw 변화와 부합한다. 400개 정책 입력을 CPU로 재생한 action 최대 차이는1.073e-6, 관절 목표 최대 차이는1.371e-6rad, stage/status 차이는0이었다. 큰 좌표계·관절 순서 오류 근거는 찾지 못했다. 재현 스크립트/해시는 `analysis_attempt02/`에 있다.

전달 원본 CurrentPairEnv는 과실 quaternion을 identity로 배치한다. 첫 실제 과실은 그 기준 대비127.62° 회전, 수직 기울기17.47°이고 가장 가까운18개 전달 점과8.781mm 차이가 났다. 자세만 바꾼 CPU 대조에서도 정책 출력이 크게 달랐다. 이는 입력 분포 차이의 증거이며 실패의 단독 원인이나 자세 변경 시 성공의 보장은 아니다. 농장 형상·근접 이웃·움직이는 차체와 원본 평가 조건의 차이도 남는다.

attempt03의 분리 순간 손가락 힘은 각각 약3.83N였지만 줄기 인장 성분은0N이었다. 인장축 반대 방향 변위와 총변위42.945mm로4cm 초과 분리가 작동했다. 손가락 접촉력과 줄기 인장력을 같은 값으로 해석하지 않는다. 수식·물성은 전달9g 평가 설정을 유지했다.

남은 필수 성능 작업은 **원본 재현과 현재 농장 조건을 비교해 Teacher의 파지 실패를 해결하고 실제 안착 성공을 확보하는 것**, 그 뒤 최신 예찰/Nav2 도착과 전체 연결을 검사하는 것이다. 필요 자료·담당자 전달안은 [농장 평가 후 요청](TEACHER_FARM_EVALUATION_REQUEST_20261006.md)에 정리한다. 카메라/Student·실물·자동 차체 재배치·다수 수확로봇 동시 정책·바구니 상대 고정은 이번 완료 범위가 아니다. 분리 과실은 물리적으로 남으며 기존 적재물 보존 감시가 운송 전체를 인증하지 않는다.

기초 물리·동적 주기의 별도 PASS는 [물리 보고서](ROBOTARM_PHYSICS_20261006.md)와 [동적 물리 보고서](ADAPTIVE_HARVEST_PHYSICS_20261006.md)에 있다. 담당자 과거9g 평가3/6과 이번 농장의 새 결과를 합산하지 않는다. 이번 소스·문서·자산은 로컬에 적용했으며 커밋·푸시하지 않았다. [버전 관리 검증 요약](changes/TEACHER_RUNTIME_VALIDATION_20261006.json)에 최종/중간 결과를 구분해 보존했다.
