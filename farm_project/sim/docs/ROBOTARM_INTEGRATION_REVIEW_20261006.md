# 로봇팔 인수 자료와 농장 sim 반영안

> 이 문서는 설명 파일 4개만 받았던 시점의 검토다. 이후 사용자가 “파일 다 받고 한 번에 작업”을 요청하여 A 단독 적용을 보류했다. 전체 묶음 수령과 새 검사 결과는 [전체 묶음 수령 검토](ROBOTARM_BUNDLE_RECEIPT_20261006.md)를 따른다. 아래 “미수신”과 “A 승인 요청”은 이전 상태이며 현재 누락 현황이 아니다.

- 일자: 2026-10-06 KST. 상태: **검토 완료, 실행 코드·설정·자산 반영 승인 대기**.
- 요청: `main/robotarm` 자료를 확인하고 sim 반영 내용을 정리하여 사용자 확인 후 적용.
- 기준: `main`, HEAD `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`. 이번 `git fetch origin` 후 `HEAD...origin/main`은 `0 0`.
- 기존 AGENTS/README/변경 이력 및 미추적 인계 문서·백업을 보존한다. 이번 산출물은 이 검토서와 변경 이력뿐이다. 정책 실행, Isaac 물리 시험, ROS 시험, commit/push는 수행하지 않았다.

## 1. 결론과 승인 요청 범위

전달된 파일은 MD 2개와 JSON 2개다. **환경 조건과 연결 계약을 검토할 수 있지만 Teacher 수확을 실행할 코드·정책·전용 자산은 아직 없다.** 현재 농장 sim은 수확 로봇 이동과 작업영역 내 과실 개수 평가까지만 연결되어 있다.

권장 순서는 다음과 같다.

1. **이번 승인 요청 A — sim의 인수 설정·검사 도구 준비.** 원본 출처를 보존한 환경/후보 프로파일, 누락 자료 검사, 좌표·간격·주기 검사 및 자산 정적 검사 도구를 추가한다. 기본 농장 실행, 실제 과실 물리, 수확 Action의 완료 의미는 바꾸지 않는다.
2. **자료 확보 후 B — 독립 오른팔 9g 재현.** 원본 코드·정책·자산을 확인한 뒤 별도 시험 프로파일에서 접촉/결합/정책을 재현한다. 원본의 코드 변경본과 실행환경 버전까지 고정한다.
3. **B 검증 후 C — 농장 장면 연결.** 과실 한 개부터 시작하고 간격을 확보한 다과실로 확장한다. 오른팔 기준으로 예찰 Window의 목표 자세·작업영역·농장 TF를 함께 정합한다.
4. **별도 구체안 승인 후 D — 공통 수확 업무 연결.** 공통 미션에 팔 작업 요청/완료/취소를 연결하고 실제 적재 수량을 반환한다. B의 단계 실행기를 sim 내부의 별도 업무 FSM으로 복제하지 않는다.

A만 승인하는 것은 B~D의 미확정 제어 계약과 공통 변경까지 승인하는 뜻이 아니다. B~C의 정확한 파일·동작은 원본 인수 후 확정한다.

## 2. 현재 코드와 인수 조건의 차이

| 항목 | 현재 farm_project | 반영할 내용 / 판단 |
|---|---|---|
| 팔 장치 | `farm_sim_devices/arm_sim.py`는 `NotImplementedError`. `run_fleet.py`는 차체·카메라·라이다만 생성 | 오른팔 5관절+그리퍼 제어와 접촉·과실 상태 어댑터 필요 |
| 명령 경로 | `wire.py`의 선속도/각속도 명령, `ros_adapter.py`의 바퀴 2개 관절 상태 | Teacher의 6차원 정규화 **목표 증가량**은 바퀴 명령 또는 절대 관절각 입력과 다름. 원본의 관절 순서·제한·증분 적분을 보존 |
| 작업 좌표 | `harvest.json`의 논리 차체 축은 자산 축 대비 yaw π. `task.yaml`/파생 `scout_survey.json`/`harvest_audit.json`은 왼팔 기준 | Teacher는 `arm_2/base_link` 오른팔 기준. audit 박스만 바꾸면 예찰 목표 자세와 불일치하므로 일괄 정합 필요 |
| 과실 평가 | `scene_truth.py`는 시각 mesh의 월드 AABB 중심을 수집. `evaluation.py`는 임시 직육면체에 포함되는지 계산 | 후보는 과실 root 위치. root/파지 중심/질량중심/탐지 중심/꼭지점을 구분. 기존 개수 평가를 수확 성공으로 사용하지 않음 |
| 물리·렌더 | 현재 fleet 60Hz. 모든 로봇의 scene/physics/render 주기가 같아야 함. `run_fleet.py`는 physics/render dt를 같은 값으로 생성하고 매 step 렌더 | 원본 실행은 물리 480Hz·정책 20Hz라고 명시. 물리·정책·렌더·센서 발행 주기를 분리해 성능/접촉/clock 검증 필요 |
| 카메라 | 수확 프로파일 `camera.enabled=false`, 카메라 경로 null | 원본 평가 스크립트는 D435 두 대의 RGB-D 및 탐지 기록 의존. 기존 예찰 카메라/모델로 자동 대체 불가 |
| 수확 완료 | `harvest_robot/mission.py`는 목표 이동만 수행. `contract.py` 수확/실패 수량 0. `harvest_task.json`: `ARRIVAL_ONLY_NO_HARVEST` | 적재·실패·취소 의미를 바꾸려면 공통 미션/상태/결과 계약 검토 필요 |
| 목표 전달 | 현재 `HarvestTask.msg`는 task_id/window_id/goal_pose/expected_count | Teacher의 개별 과실 ID·상태는 없음. Window 도착 후 대상 획득/선택과 팔 요청 인터페이스가 별도로 필요 |

`run_sim.py`는 disabled 검사 전에 카메라 prim 경로를 읽으므로 현재 수확 프로파일로 바로 단독 재현에 사용할 수 없다. 현재 수확 실행 경로는 fleet이다. 독립 재현기는 원본 실행 경로를 먼저 사용하고 농장용 adapter는 이후 검증한다.

### 활성 USD 직접 정적 검사

설치된 Isaac 환경의 `pxr 0.24.5`로 USD를 읽었다. SimulationApp/PhysX는 실행하지 않았다.

- 활성 농장 `sim/assets/envs/output/farm_with_plants_v5.usd`: 과실 **288개(색상별 96개)**. 과실 하위 프림에서 `RigidBodyAPI`/`MassAPI`/`CollisionAPI` 적용은 각각 0개다. 현재 과실은 Teacher가 요구하는 9g 동적 접촉·분리 모델이 아니다.
- 과실 root 기준 기하에 개별 scale을 반영한 외형 범위는 X 약 60.19~77.13mm, Y 63.57~81.45mm, Z 82.19~105.32mm다. 중앙값 약 68.73×72.58×93.84mm로 Teacher의 폭70mm/높이75mm와 다르다. 현재 root와 월드 AABB 중심은 수치적으로 일치하지만, 전달 자산과 root/파지점/꼭지 의미까지 같다는 뜻은 아니다.
- 활성 로봇은 `sim/assets/robots/harvest_count_test/harvest_robot.usd`다. USD 프림 `arm_2_base_link`와 문서의 `arm_2/base_link`를 이름으로 매핑해야 한다. 정적 장착 변환은 자산 base 기준 `(-0.19,-0.185,0.713)m`, yaw -π/2; 논리 주행 base 기준 `(0.19,0.185,0.713)m`, yaw +π/2다.
- 현 자산에 후보를 대입하면 논리 좌표는 `(0.19-y, 0.185+x, 0.713+z)`다. 18개 후보의 범위는 X 0.049860~0.324795m, Y 0.454591~0.540152m, Z 0.859753~1.057858m. 기존 왼팔 audit의 X 범위 -0.365~-0.015m 밖에 **18개 모두** 위치한다. 이 수치는 현재 정적 자산의 확인값이며 runtime에는 현재 stage/TF 변환을 읽는다.
- 현재 활성 USD의 `box_bottom_left`, `box_bottom_right`, `harvest_lid_fixed` 하위는 Xform만 있고 Mesh/CollisionAPI가 없다. 현 주행용 자산으로 적재함 바닥 접촉과 0.6초 유지가 재현된다고 가정할 수 없다. 원본 적재 자산과 바닥/충돌을 대조하는 작업을 B의 필수 조건으로 둔다.
- 일부 빈 visual reference 경고도 확인했다. 시각 참조와 실제 물리 동작의 영향은 이번 정적 검사만으로 확정하지 않는다.

## 3. 반영할 환경 값과 해석

| 묶음 | 기준 값 |
|---|---|
| 과실 | 질량 **0.009kg**, 가로 크기 0.070m, 전체 높이 0.075m. 크기는 자산 기준이며 실측 확정값이 아님 |
| 접촉 | 정지/운동 마찰 1.0, 반발 0.02, contact/rest offset 0.001/0m, 중력 활성, 선형/각 감쇠 0/0.02 |
| 결합 | attachment v4 / stem response v5. 인장 60N/m, 횡방향 15N/m, 수직 40N/m, 선형 감쇠 4.2N·s/m, 회전 계수 0.015/0.002 |
| 연결점 | 제공 과실 자산 root local `(0.017530, 0.012588, 0.037500)`m. 다른 mesh/root/scale에는 검증 없이 재사용 불가 |
| 분리 | 기본 2.5N, reset별 2~3N. 인장축 arm local `(-1,0,0)`. 조건 연속 40ms; 끊기면 누적 초기화 |
| 파지 | 가로 파지, 중심 허용 10mm, 방향 허용 약 25°, gripper effort 상한 0.50N·m |
| 실행 | 정책 20Hz. snapshot 명목 dt=1/240s, decimation=12, contact_substeps=2. 문서의 실제 실행 dt=1/480s, decimation=24 |
| 운반/놓기 | 운반 배율 0.25에서 3초에 걸쳐 증가. 박스 위 안정 정지 연속 0.3초 후 고정 열기. 적재 유지 0.6초 |
| 운반 정지 | 위치차분 선속도 ≤0.05m/s와 순간 선속도 ≤0.20m/s, 집게 이동속도/회전/보유/박스 위 위치 조건을 함께 검사 |

분리 판정은 다음 OR 조건의 연속 유지다. 단순 `force > 2.5N` breakable joint로 대체하지 않는다.

1. 임계 인장력 초과 및 인장 변위 12mm 초과.
2. 전체 변위 40mm 이상 및 복원 하중이 임계력의 2배 초과.
3. short-hook: 인장 변위 25mm 이상 또는 전체 변위 40mm 이상.

이는 native joint나 그리퍼 weld가 아닌 외력·토크 기반 모델이다. force clipping과 분리 판정의 순서, 실제 갱신 주기는 원본 코드가 기준이다.

**snapshot 단독 재현의 누락/확인 사항:** 연결점, 25mm hook 이탈, contact/rest offset, 강체 감쇠, 임계력 랜덤 범위, 순간속도 0.20m/s 등은 문서에만 있다. `break_distance=0.03`과 hook 0.025m의 관계, 회전 정지 기준과 실제 dt 세분화는 원본 코드로 확인한다. 이름이 다른 값을 임의로 덮어써 불일치를 해소하지 않는다.

## 4. 후보와 좌표 검증

- 후보 JSON의 점 18개는 이미 `arm_2/base_link` 기준 **과실 root**다. `p_world = T_world_from_arm2 × [p_arm, 1]`을 적용한다. JSON의 과거 `policy_world_from_current_robot`를 후보에 다시 적용하지 않는다.
- 위치는 강체 변환, 인장축은 회전만 적용한다. 앵커는 `fruit_root_world + R_fruit × local_attachment`로 구성한다. 과실/로봇/박스 pose와 정책 관측에 사용하는 프레임을 일관되게 맞춘다.
- 파지 중심은 root의 local Z 방향 -0.006m다. USD AABB 중심을 이 위치와 같다고 간주하지 않는다.
- 전체 외곽 범위: X 0.265~0.365m, Y ±0.175m, Z -0.100~0.350m. 직육면체 전체 도달·수확 가능 보장이 아니다.
- 후보 실제 범위: X 0.269591~0.355152m, Y -0.134795~0.140140m, Z 0.146753~0.344858m. 18개 모두 외곽 범위 안이다.
- 문서 HOME TCP `(0.216404,-0.000392,0.274099)`m에서 후보까지 거리는 약 0.096876~0.179158m로 9cm 초과·18cm 미만 조건을 만족한다.
- 후보 root 간 18cm 이상인 쌍은 **39/153**, 최대 동시 선택은 **3개**, 가능한 3점 조합은 **19개**다. 최근접 3·13번은 약 22.555mm다. 번호는 JSON 배열의 1부터 시작하는 순서다.
- 예: 3·8·15번 간 거리는 약 0.229936/0.216132/0.235654m. 배치 간격 검사만 통과하며 파지/당김/운반/복귀 충돌 시험은 별도다.
- `box_min/max`는 **정책 환경의 적재 용기 영역**이다. 문서 장착점에서 빼면 arm local `[0.070,0.095,-0.207]`~`[0.260,0.285,-0.012]`m. 현행 `harvest_audit.json`의 작업영역 박스와 의미가 다르다. 회전된 박스는 프레임과 전체 형상을 변환해야 하며 min/max 두 점만 옮기지 않는다.

## 5. 추가 인수 목록

정책 전달서의 원래 상대 경로와 해시를 유지한 지정 버전 저장소 + 필수 외부 자산 묶음이 필요하다. 비슷한 이름의 현행 `harvest_robot` ROS 패키지는 아래의 RL 코드와 다르다.

| 필요한 자료 | 용도 |
|---|---|
| 접근·파지 `model_200.pt`, 당기기/운반/놓기 `teacher_final.pt` 각 1개 및 각 디렉터리 `run.json` | 원본 네트워크·정규화·제어 계약으로 복원. 같은 파일명 덮어쓰기 방지 |
| `src/harvest_robot/config/teacher_ramp_20260930.json` | 정책 경로/SHA256/단계 보정 원본 |
| `src/harvest_robot/harvest_runtime/`, `harvest_rl/`, `eval_current_pair.py`, `run.py` 및 import 의존성 | 관측 순서, 단계 전이, 분리/보유/적재 판정, 관절 명령 생성 |
| `scripts/eval_teacher_mass.sh`, `collect_student_ramp.py/.sh`, `collect_student_demos.sh` 및 호출 파일 | 해시 검사와 고정 Teacher 재현 |
| `src/smartfarm_description/` URDF/설정/mesh/생성 코드, `src/Pepper_RL_Demo/assets/` 및 manifest | 관절·TF·충돌 형상·과실 root/연결점 일치 확인 |
| `HARVEST_RL_VALIDATION.md`, 원본 `run.json`, `expert_contract.json`, episode 결과 | 담당자 검증 실적과 실행 조건 확인 |
| 커밋/로컬 변경본, Isaac Sim/Lab·Python·PyTorch·드라이버 버전 | 환경 재현 및 호환성 확인 |
| 원본 평가에 쓰는 YOLO 모델과 비전 환경, 또는 담당자가 검증한 기록 제외 실행 경로 | 현재 평가 스크립트의 D435/탐지 의존성 충족 |

문서의 `/home/bhc/...` 경로와 `outputs/harvest_rl/...`를 농장에 그대로 박아 넣지 않는다. 수신 후 입력 경로는 설정으로 연결하고 농장 쪽 신규 출력은 `sim/runs/robotarm/`에 둔다. Student/실물/양팔 실행을 이번 Teacher 연결에 포함하지 않는다.

## 6. 단계별 대상 파일·영향·완료 조건

아래 경로는 `farm_project/` 기준이며 신규 파일은 아직 만들지 않았다.

| 단계 | 대상 / 구체안 | 영향 및 검증 |
|---|---|---|
| A 승인 요청 | 신규 `sim/ros_ws/src/farm_sim_config/config/robotarm/`에 두 JSON을 출처/해시와 함께 수록. 신규 `teacher_integration.json`에 SI 단위, arm2 frame, 문서 보충값의 출처, 원본 확인 대기값, 필수 의존성 목록을 구분 | 설정 준비만 수행. 기존 기본 launch/scene/Task 동작 변화 없음. JSON 범위·단위·주기와 원본 SHA256 대조 |
| A 승인 요청 | 신규 `sim/tools/validate_robotarm_handoff.py`: 입력 자료/해시·후보 범위·간격·프레임 검사 및 준비 여부 출력. 신규 `sim/tools/inspect_robotarm_assets.py`: 읽기 전용 USD/URDF 원점·크기·joint/physics 검사 | 미수신 정책은 누락으로 보고하고 실행 가능으로 표시하지 않음. 출력은 `sim/runs/robotarm/` 아래. 회전된 로봇의 점/방향 변환 확인 |
| B 자료 확보 후 | `sim/assets/`의 별도 시험 장면/override, `farm_sim_config/config/robotarm/` 시험 프로파일, `sim/tools/` 재현 진입점 및 필요한 원본 runtime 연결 | 기본 농장과 분리한 오른팔 단일 목표 평가. 물성/결합/그리퍼/박스/정책 20Hz 검증. 원본 코드 부재 상태에서 근사 정책이나 성공 더미를 만들지 않음 |
| C B 완료 후 | `farm_sim_devices`의 팔·과실 물리 adapter, `farm_sim_runtime`의 주기/장면 구성. `task.yaml` 수확 기하와 파생 `scout_survey.json`, 별도 오른팔 audit 설정의 정합 검토 | 전 농장 과실을 즉시 동적 객체로 바꾸지 않고 시험 장면부터 검증. 물리 substep/렌더 분리, 차체 구동·센서·clock 회귀 확인. 원본 route/베드 연결은 임의 변경하지 않음 |
| D 별도 공통 승인 | `robot/ros_ws/src/harvest_robot/harvest_robot/{mission,state_controller,node,contract,communication}.py` 등. 이동 뒤 팔 요청/콜백·취소·타임아웃·실제 누적 수량 처리안 확정 | 실물과 sim이 공유하는 동작 변경. 기존 이동 전용 모드 보존 여부와 실제 팔 장치 계약을 먼저 합의. `farm_interfaces` 변경 필요성은 원본 팔 인터페이스 확인 후 결정 |

완료/검증 순서:

1. 원본 정책+메타데이터 해시와 환경 버전 검사. 명세 누락을 감지하고 임의 기본값으로 성공 처리하지 않는다.
2. 독립 환경: `python3 scripts/collect_student_ramp.py --check` 후 원본 `FRUIT_MASS_KG=0.009 POSE_STOP=1 HEADLESS=1 EPISODES=5 bash scripts/eval_teacher_mass.sh`를 수신 환경에 맞춰 실행한다. 현재는 해당 스크립트가 없어 실행하지 않았다.
3. `expert_contract.json`에서 mass=0.009, transport_linear_pose_stop=true, 정책 해시/보정 설정 확인. 실제 substep과 정책 주기를 기록한다.
4. 힘·변위 OR 조건/연속40ms/조건 끊김 reset, 물리 파지·분리·보유·정지0.3초·적재0.6초를 서로 구분해 기록한다.
5. 단일 후보→18개 후보별 반복→간격 확보 다과실 순서로 성공/실패 단계, 주변 과실 접촉과 복귀 간섭을 남긴다. 원본의 빨강/노랑 각 5회 명령과 과거 6회 기록을 구분한다.
6. 농장 TF를 이동/회전한 경우에도 같은 상대 상태와 오른팔 배치가 유지되는지 확인한다. 기존 예찰/수확 이동·개수 audit 시험은 C 단계 변경 범위에 맞춰 다시 수행한다.

Teacher의 시뮬 내부 상태 입력은 B의 **독립 평가 전용**이다. 기존 `sim/AGENTS.md`의 “시뮬 정답 좌표는 평가·디버깅에만 사용하며 공통 비전/제어 입력에 주입하지 않는다”와 D-010을 유지한다. 공통 운용 경로에 연결할 입력 출처는 D에서 별도로 확정한다.

## 7. 검토 증거·승인 상태·복원

- 직접 확인: 문서 4개와 코드/설정 정적 대조, JSON 파싱 및 후보 기하 계산, Git 상태/브랜치/HEAD/fetch 후 차이, 인수 파일 존재 및 SHA256 확인, pxr로 활성 USD의 과실 형상/physics API·팔 장착 변환·박스 바닥 정적 검사.
- 담당자 기록: 9g 정지 보정 평가 **6회 중 적재 3회, 접근·분리 실패 3회, 운반 시간초과 0회**. 원본 episode 로그는 미수신. 이번 직접 평가 결과나 18개 전수 성공률이 아니다.
- 승인 대기 근거는 사용자 요청의 “나한테 확인받고 적용해”다. 공통 변경은 추가로 `AGENTS.md`의 “공통 코드 변경은 적용 전에 사용자에게 이유, 대상 파일, 구체적인 변경안, 실물·시뮬 영향, 검증 방법을 제시하고 명시적으로 확인받는다”가 적용된다.
- 이번 검토만 되돌릴 때는 이 파일과 이번 CHANGELOG 항목만 제거한다. 기존 미커밋 이력·다른 인계 문서·원본 robotarm 자료는 보존한다. A 이후 구현 복원은 실제 변경 파일 명세에 기록한다.
- 다음 작업: 사용자 A 범위 확인 후 설정·검사 도구 반영. B 착수 전 §5 자료 확보. 실행 코드 변경은 아직 없으며 원격 미반영.

인수 파일 SHA256:

| 파일 (`main/robotarm/`) | SHA256 |
|---|---|
| `SIM_TEAM_HARVEST_HANDOFF_KR.md` | `2b6d178d20851b0210a9214181d9433a1a9583bf299334132787140779276394` |
| `SIM_TEAM_POLICY_DELIVERY_KR.md` | `7fe213b3b502446945228f399e55f7d4eb8e74ce5770d28e878f16a731de3ac9` |
| `teacher_environment_snapshot_20261001.json` | `789add59fc120ca9768e518572f98d72153ce63a53a21eabe66795ca9e0c291f` |
| `teacher_fruit_candidates_20261001.json` | `5b0718600807af1eecb253413b03e90ddf3370123257ebd6dcb01fae7dcbbbad` |

원본: [정책 전달](../../../robotarm/SIM_TEAM_POLICY_DELIVERY_KR.md), [환경·좌표 전달](../../../robotarm/SIM_TEAM_HARVEST_HANDOFF_KR.md), [환경 snapshot](../../../robotarm/teacher_environment_snapshot_20261001.json), [후보](../../../robotarm/teacher_fruit_candidates_20261001.json).
