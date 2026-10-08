# 로봇암팀 Teacher 진단 요청 회신 — 2026-10-08

수신팀 직접 실행 결과다. 요청 원문은 `main/robotarm/SIM_TEAM_TEACHER_DIAGNOSTIC_REQUEST_KR.md`이며, 해당 폴더의 자료는 보존했다. 농장 기준은 `main/7d9ae40ec8e0d0bebf0e0552f8a6ee85ddfc9bc3` 및 기존 미커밋 변경이다. 이번에는 원인 비교용 기록만 추가했으며 정책·물성·농장 과실 초기 자세를 보정하지 않았다. 학습·실물 구동·원격 게시·담당자 메시지 발송은 하지 않았다.

## 회신 요약

```text
받은 TAR: /home/ysy/robotarm/harvest_teacher_9g.tar.gz
SHA256: 7b33e66a3cad8003204fc69819eaf95be6362d246c574bb6cf827f953e161139
전달 버전: harvest_teacher_9g_20261006_143434
base_commit: abe9e13357e1be549500712b62c5582649d444ab + 전달 당시 git_status
기존 해제본: sim/runs/robotarm/received_20261006_143434/manyfarm_robotarm
새 독립 해제본: sim/runs/robotarm/receiver_diagnostic_20261008/independent/manyfarm_robotarm
Teacher 4개 및 각 run.json: 전달 기준과 SHA256 모두 일치
독립 진단: 적재 성공7 / 실패3 / 시간초과0 / 목표미선정0 / 실행오류0
농장 완료 평가 2회: 적재 성공0 / 실패1 / 시간초과1 / 목표미선정0 / 실행오류0
별도 실행 오류: GUI 초기화 SIGSEGV 2회(정책 실행 전, 위 2회 평가에서 제외)
실제 주기: 독립 물리480Hz / 정책20Hz; 농장 수확480Hz / 정책20Hz / 렌더 설정60Hz
```

농장 두 job의 `status=SUCCESS`는 후보 처리 및 안전 정지 완료이고, 각각 `success_count=0, failed_count=1`이다. 이를 수확 성공으로 계산하지 않았다. 독립 성공은 정상 분리·보유 후 박스 적재까지 완료한 판정이다.

## 1. 전달본과 독립 재현

새 해제본에서 경로 보정 **전에** 전달 `verify_bundle.py`로 2,148개 파일을 검증하고 `collect_student_ramp.py --check`를 통과했다. 이후 전달 `prepare_receiver.py`가 캐시9개의 수신 경로를 보정했다. 실제 실행기는 추가 캐시를 갱신해 최종 manifest 차이는12개다. 상대/절대 자산 경로, converter 시각·cache ID 차이를 `provenance.json`의 diff로 보존했다. 과실 물성 수치를 바꾼 차이는 없으며 전달 평가·환경·정책 소스와 체크포인트/메타데이터 해시는 유지됐다.

실행은 받은 `robotarm/eval_delivered_teacher.py`를 그대로 사용했다. 이 어댑터는 전달 `eval_current_pair.py`, `CurrentPairEnv`, `StagedTeacher`, 저장 normalizer, 하위 제어·성공 판정을 사용하고 **카메라·YOLO 기록만 제외**한다. `eval_teacher_mass.sh`의 카메라/탐지 포함 전체 경로를 재현했다고 주장하지 않는다.

```bash
/home/ysy/isaac/env_isaaclab/bin/python /home/ysy/main/robotarm/eval_delivered_teacher.py \
  --bundle-root /home/ysy/main/farm_project/sim/runs/robotarm/receiver_diagnostic_20261008/independent/manyfarm_robotarm \
  --target red --seed 182 --episodes 5 \
  --output /home/ysy/main/farm_project/sim/runs/robotarm/receiver_diagnostic_20261008/independent/red
# yellow는 --target yellow --seed 183, 별도 yellow 출력 경로로 실행
```

| 장면 | 적재 성공 | 실패 | 시간초과 | 종료 코드 |
|---|---:|---:|---:|---:|
| 빨강 seed182, 5회 | 3 | 2 | 0 | 0 |
| 노랑 seed183, 5회 | 4 | 1 | 0 | 0 |

송신·수신의 **10개 trace, 총1,069tick는 파일 SHA256까지 일치**했다. 원본/전문가/정규화 관측, 실행 action, q/qd, 관절 목표, diagnostics의 최대 수치 차이는0이다. 별도 episode metadata에서 노랑4의 두 과실 중심거리만 `2.78e-17m` 차이가 있었고 좌표와 trace는 같았다. 이번 조건의 실제 비교 결과이며 다른 환경의 결정론을 보장하는 주장은 아니다.

수신 설치는 Python3.11.15, Isaac Sim5.1.0.0, Isaac Lab0.54.2, PyTorch2.7.0+cu128, RSL-RL3.1.2, CUDA runtime 패키지12.8.57, RTX4070 SUPER/driver580.173.02다. 송신 handoff의 driver580.178.04와 차이가 있다. 독립 진단은 같은 결과로 재현됐으므로 이 버전 차이만으로 농장 실패를 설명하지 않는다.

모델 4개의 절대/상대 경로·직접 계산 SHA256, 각 `run.json`, ramp/profile, handoff base_commit/git_status, 실제 argv·허용목록 환경변수는 묶음의 `provenance/`, `provenance.json`, `independent/*_process.json`, `*_invocation.json`에 있다. 학습 메타데이터35g와 실제 runtime override9g를 구분했다.

## 2. 이번 농장 연속 기록

기존 fixture 검증 도구에 `--teacher-diagnostic-trace`만 추가해 재실행했다. 원본 과실 위치·랜덤 회전은 유지하고 초기 차체를 fixture에 배치했다. 이후 관절·과실·차체 순간 이동으로 동작을 보정하지 않았다. Nav2 도착 성공 시험이 아니다.

```bash
cd /home/ysy/main/farm_project
# stdout/환경 전체 실행 argv는 각 result.json의 command 참고
python3 sim/tools/check_teacher_harvest.py \
  --fixture sim/tests/fixtures/teacher_dock.json \
  --output sim/runs/robotarm/receiver_diagnostic_20261008/farm/headless_yellow/result.json \
  --teacher-diagnostic-trace --wall-timeout-s 700
# 빨강은 teacher_dock_red.json 및 별도 headless_red 출력 경로
```

| 항목 | 노랑 | 빨강 |
|---|---|---|
| 실제 목표 | Bed_02/Pepper_0031_yellow | Bed_05/Pepper_0030_red |
| POLICY 행 수 | 400 | 42 |
| 결과 | `target_timeout`, 부착 유지 | `bad_detach`, 분리됨 |
| 실제 적재 | 0 | 0 |
| 복귀/정지 | 확인, 종료0 | 확인, 종료0 |
| 세션 | `050a3038edfb4db2849f6e431b63b974` | `e80d491ff7ec44ccb5070f616f3243d4` |

매 POLICY 행은 **현재 sample로 직전 명령 결과를 평가한 뒤 다음 명령을 기록**한다. 종료 tick은 새 추론이 아니므로 `policy_executed=false`다. 송신 어댑터는 한 행에 step 전 observation/action과 step 후 diagnostics를 같이 저장하므로, 양쪽 diagnostics를 같은 행 번호로 단순 비교하면 안 된다.

- `teacher/trace.jsonl`: 원본82·전문가 시간슬롯42 보정82·실제 normalizer 출력82, 실제 전문가 원출력6·StagedTeacher 후처리6·clip 후6·그리퍼 보정 후6·최종 관절 목표6, 단계/상태 플래그. 실제 forward hook 관찰이며 추가 추론이나 통계 학습은 없다.
- `diagnostics/continuous.jsonl`: 초기화부터 복귀·정지까지 시뮬/벽시계·물리 step·실제dt·q/qd·PhysX 관절 목표·차체/팔 pose·접촉·과실/앵커/적용 줄기 힘/토크. POLICY의 `time_s`로 연결한다.
- `diagnostics/runtime_contract.json`: 초기화된 PhysX 질량/COM/역관성, drive gains/effort, 접촉 body/filter 경로, 박스 경계, 합성된 USD joint/collider/material/scene 속성.
- `diagnostics/target_001.json`: 선택 순간의 실제 TF, 원래 과실 자세, 인장축·앵커·threshold와 collider/material 속성.
- `physics/`: setup, 활동·분리 사건, 최종 summary. `result.json`은 호출·종료·검증 결과이며 `passed=true`는 프로토콜·안전종료 검사 통과다.

위치/속도 단위는m·m/s, 관절rad, 힘N, 토크Nm, quaternion은wxyz다. `T_policy_world = inverse(T_world_arm_at_selection)`에 legacy `policy_arm_position_m`을 더한 고정 프레임을 사용한다. 센서 contact force는 실제 physics dt로 나눈 PhysX impulse이며 선택 과실 필터와 두 손가락 경로를 함께 기록했다. 초기 차체와 팔 TF, 실제 과실·박스 프레임은 로그 원값으로 제공한다.

## 3. 현재 확인된 차이와 담당자 검토 요청

전달 모델과 독립 실행 재현은 일치했다. 농장 통합은 기존 StagedTeacher와 추출된 원본 계산을 쓰지만 장면·물리 장착과 관측 어댑터가 별도다. 농장 성공0을 물리 미적용 하나로 확정하지 않는다.

1. **접근 실패와 분리 실패를 구분해서 봐 주십시오.** 새 노랑 장면은 파지 영역 진입 없이 시간초과다. 빨강은 정상 파지 확인 전에 분리돼 `bad_detach`다. 두 장면 모두 ENTRY(-1)에 머물렀다. 상세 거리·방향·접촉 및 분리 시점은 `farm_analysis.md/json`에 있다.
2. **초기 조건이 다릅니다.** 독립 환경은 과실 identity 회전, legacy-near18점/2과실/중심간0.18m 이상, 고정 베이스다. 농장은288과실의 기존 랜덤 회전·밀집 배치와 움직일 수 있는 주행 차체, 연속 근거리 후보를 사용한다. 서로 다른 초기 관측의 숫자 차이만으로 어댑터 오류를 단정할 수 없다.
3. **실제 물성·drive는 읽어 확인했습니다.** 과실9g, 중력활성/dynamic, convexDecomposition collider, 마찰1/1·반발0.02·contact offset1mm/rest0, combine average. 팔 gains25/1.5·집게8/0.3, effort2/0.5Nm가 적용돼 있다. USD의 COM 자동계산 기본값은 실제 COM으로 해석하지 말고 `fruit_physx`를 사용해야 한다.
4. **solver/자기충돌 구성이 다릅니다.** 농장 articulation의 합성 USD는 위치32/속도1회·self collision false, 전달 환경 소스는12/4회·self collision true다. 코드·readback 근거를 첨부하며 이번 회신에서는 바꾸지 않았다. 이 차이가 실패 원인인지 별도 통제 비교가 필요하다.
5. **중력과 줄기 모델을 구분해야 합니다.** 현재 줄기는 native connector 관절이 아닌 world 앵커 spring + 초기 quaternion 복원 토크다. 앞선 물리 단독 실측에서9g 과실은10.788mm 내려가고8.360° 회전했으며 줄기 수직 힘0.088290N이 중력과 균형을 이뤘다. 초기 자세 복원 때문에 수직으로 완전히 정렬되지 않는다. 이번 수확/독립 평가와 별개인 같은날 이전 관찰 자료를 첨부했다.

다음 비교는 운영 과실을 수정하지 않는 별도 장면에서 초기 q/qd·목표 pose/속도·TF·앵커·threshold를 맞춘 뒤 원본/정규화 관측→action→PhysX 목표→접촉의 최초 차이 tick을 찾는 순서가 적절하다. 이 동일 초기조건 농장 대조는 이번에는 실행하지 않았다. 첨부 실패 장면에서 우선 확인할 어댑터/접촉 항목과 통제 조건에 대한 검토를 부탁드린다.

## 4. 검증·제한·첨부

CPU Teacher/ArmSession 검사60개와 fleet entrypoint2개를 통과했다. 새 계측 검사는 실제 가중치 입력/출력, 일반 실행과 action/target 동일성, normalizer 불변, 이벤트 비소비, 종료 후 연속 기록을 확인한다. GPU에서는 독립10회와 농장2회가 정상 종료했다. 단위 검사와 수확 성공률을 혼합하지 않았다.

GUI 재시도2회는 `World` 초기화의 render에서 native OmniGraph SIGSEGV로 종료됐다. Teacher와 새 recorder 생성 전 오류이며, 원인 확정/수정은 하지 않았다. stdout·명령·종료코드를 보존했다. **이번 실패/성공 viewport 영상은 확보하지 못했다.** 첨부 PNG는 이전 물리 단독 관찰이며 이번 수확 영상의 대용으로 표시하지 않았다. 카메라/YOLO 포함 독립 재현, 같은 초기조건의 농장 대조, Nav2·실물 시험도 미실행이다.

노랑 수집 이후 관측 항목순서 메타데이터와 USD 무한대 기본값의 표준JSON 표현을 보강했다. 노랑 trace는 `observation_layout` 없이 source/order 문서로 해석하며, USD 원본 JSON은 그대로 보존하고 `.portable.json` 사본에서 Infinity를 문자열로 표시했다. red는 최종 기록 형식을 사용한다. 관측·명령·물리 계산은 변경하지 않았다.

회신 묶음: `sim/runs/robotarm/receiver_diagnostic_20261008/TEACHER_DIAGNOSTIC_REPLY_20261008.tar.gz`.
`REPLY_KR.md`, 요청 원본/송신 trace, 이번 stdout·결과·trace·설정, provenance, 비교/분석, 관련 통합 소스와 SHA256 manifest를 포함한다. 대형 checkpoint·전체 해제본·RGB-D NPZ는 포함하지 않는다. 참조용 소스가 포함된 로그 묶음이며 설치 패치가 아니다.

```bash
mkdir -p ~/Downloads/teacher_diagnostic_review
tar -xzf ~/Downloads/TEACHER_DIAGNOSTIC_REPLY_20261008.tar.gz \
  -C ~/Downloads/teacher_diagnostic_review
```

미커밋·원격 미반영이며 이번 원격 최신 상태는 조회하지 않았다. 실제 파일 전달/담당자 발송은 사용자가 이 묶음을 첨부하면 된다.


## 후속 정정 — 2026-10-08 팔 충돌/물성 정렬

앞선 회신은 팔 충돌 메시 근사화까지 일치시킨 검증이 아니었다. 농장 팔은 convexHull, 전달 current_robot은 convexDecomposition이었으며 카메라 고정 몸체 합성, 자기충돌/solver, 팔 접촉 센서 범위도 달랐다. 사용자 지적으로 재감사 후 전달 오른팔 메시·합성 질량/관성을 적용하고 solver12/4·자기충돌true·접촉 재질·GPU/TGS 설정을 맞췄다. [적용표/검증/남은 차이](HARVEST_PHYSICS_INSPECTION_20261008.md)의 추가 정정 절을 참고한다.

독립/농장 USD·PhysX115항목 일치,56개 검사PASS. 농장 수확1회는 arm_collision 후 복귀 접촉으로 적재0/1이며 안전정지·60Hz복귀·종료0. 로그 `sim/runs/arm_physics_alignment_20261008/`. 기존 회신 tar.gz는 당시 결과로 보존했으며 이번 변경을 담은 새 회신을 외부 발송하지 않았다.


## 후속 정정 — 내부 적재 로그와 표시 과실의 불일치 (2026-10-08)

사용자가 지적한 “로그에는 운반/적재, 화면의 과실은 초기 위치”를 재현했다. 과실 custom matrix xform으로 인해 동적 PhysX pose와 USD/Fabric 표시 pose가 분리됐다. 따라서 기존 내부 SUCCESS를 화면까지 일치한 수확 검증으로 해석하면 안 된다. 초기 배치와 kinematic 고정을 표준 translate/orient/scale로 수정했다.

통제된 이동·낙하 시험의 PhysX 대 표시 위치 최대오차는0.550647m→0.000590m(root0m), 최종 실제GUI5초 종료0, 관련43검사PASS. 전체 수확 재시험은 아직 미실행이다. [원인·증거·변경파일·적용명령](HARVEST_PHYSICS_INSPECTION_20261008.md)의 마지막 정정 절과 `sim/runs/fruit_render_sync_20261008/`를 참고한다. 새 일반 시험창에 수정 적용, 기존 자료 보존. 외부 발송 없음.
