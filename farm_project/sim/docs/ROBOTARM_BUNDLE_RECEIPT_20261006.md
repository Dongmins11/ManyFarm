# 로봇팔 Teacher 전체 묶음 수령 검토

- 일자: 2026-10-06 KST. 상태: **필수 묶음 수령·무결성 확인 완료, 이식 보완 및 새 물리 재현 미실행**.
- 사용자 요청: 추가 자료를 `main/robotarm`에 넣었으므로 내용 파악. 앞선 “파일 다 받고 한 번에 작업”에 따라 설정만 먼저 적용하는 이전 A안은 진행하지 않았다.
- 농장 기준: main / `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`. 이번 fetch 후 `HEAD...origin/main=0/0`. 기존 미커밋 문서·백업 보존.
- 원본 압축: `main/robotarm/harvest_teacher_9g.tar.gz`. 원본 파일과 전달 소스는 수정하지 않았다.
- 검토용 추출 위치: `sim/runs/robotarm/received_20261006_143434/manyfarm_robotarm/`. 아래 **전달 루트**는 이 위치를 뜻한다. 운영 코드 경로에 설치·병합한 것이 아니다.

## 1. 수령 확인

이전의 “문서 4개만 수신” 상태는 해소됐다. 주요 추가 요청 자료는 모두 들어왔다.

| 자료 | 직접 확인한 내용 |
|---|---|
| 소스 | 실행용 현재 스냅샷, `handoff/base_source.tar`, 기반 커밋, 추적 수정 패치, 미추적 목록 |
| 정책 | Teacher 4개, 각각의 `run.json`, `teacher_ramp_20260930.json` 경로·SHA256 |
| 실행기 | `harvest_rl`, `harvest_runtime`, `eval_current_pair.py`, 9g 평가/수집 wrapper |
| 자산 | 로봇·박스·과실·나무·재질·텍스처, 생성 USD, 기존 학습/현재 로봇 캐시, `workspace.npz` |
| 비전 | `external/models/model_yolo11_seg_ver1.2.pt`, 비전 소스·환경 목록 |
| 검증 근거 | 10/1 빨강·노랑 각 3 episode 결과, 프레임 JSON, run/expert contract, 로그 |
| 문서 | 설치/재현 README, 환경 버전/freeze, ROS 인터페이스 및 기존 인계 문서 |
| 실물 참고 | `scripts/so101_bench/`의 보정·replay·bridge·추종 도구, Jetson/STS3215 관련 도구. 실물 운용 검증과는 별도 |

실행 필수 작업공간 NPZ는 포함되어 있다. 제외된 **평가 RGB-D 프레임 NPZ**, 가상환경 바이너리, 모든 과거 학습 기록은 새 Teacher 평가를 시작하기 위한 필수 추가 수신 자료로 판단하지 않는다. 과거 영상 재생/동일 영상 입력 비교/Student 재학습을 하려면 프레임 자료가 추가로 필요하다.

## 2. 수신 PC에서 직접 확인한 무결성

| 검사 | 결과 |
|---|---|
| 외부 `sha256sum -c SHA256SUMS` | 통과 |
| 압축파일 | 432,574,594 bytes, 약 412.54MiB |
| SHA256 | `7b33e66a3cad8003204fc69819eaf95be6362d246c574bb6cf827f953e161139` |
| archive 경로/형식 검사 | 단일 `manyfarm_robotarm` 루트, 경로 이탈/링크/특수파일 없음 |
| `python3 scripts/sim_team/verify_bundle.py` | **2,148개 파일 해시 일치** |
| 실제 압축 내 일반 파일 | 2,149개. 차이 1개는 자기 자신을 해시 목록에서 제외한 `handoff/MANIFEST.json` |
| `python3 scripts/collect_student_ramp.py --check` | 정책 4개 및 각 `run.json` 해시 일치 |
| Git LFS 미수신 포인터 | 파일 목록 전체 검사에서 0개 |
| 먼저 받은 문서/JSON 4개 | 묶음 내부 `docs/manipulation/` 파일과 byte 단위 일치 |
| 소스 이력 | 기반 `abe9e13357e1be549500712b62c5582649d444ab`, 기반 소스 1,478개, tracked patch 18개 파일, untracked 목록 27줄 |
| 원본 URDF mesh | 149개 참조 / 고유 53개 파일 모두 존재 |
| USD 정적 경로 | USD 계열 44개 파일에서 외부 참조 47개 연결 / 고유 22개 로컬 경로 존재 확인 |

USD 수치는 전체 묶음 파일을 조사한 결과다. 전달자의 “43개 USD 참조”와 검사 집합·집계 단위가 같다고 가정하지 않는다. 깊은 의존성 해석에서는 Isaac 내장 `OmniPBR.mdl`만 standalone pxr에서 미해결로 남았으며, 이를 전달 로컬 mesh 누락으로 분류하지 않는다. 최종 렌더 검증은 하지 않았다.

검사 스크립트는 내용을 먼저 확인한 후 파일 해시 검사 모드만 실행했다. 정책 역직렬화·학습·시뮬레이션·실물 동작은 시작하지 않았다.

증거 파일:

- `sim/runs/robotarm/received_20261006_143434/receipt_integrity.json`
- `sim/runs/robotarm/received_20261006_143434/historical_evaluation_summary.json`

## 3. 소스와 과거 평가 원본의 관계

전달 README는 **10/6 현재 수정본과 10/1 과거 평가 원본을 함께 제공**한다고 명시한다. 과거 평가 당시 미커밋 전체 소스 및 완전한 환경 lock은 없다. 따라서 수령 해시 통과를 과거 물리 궤적 재현 성공으로 기록하지 않는다.

과거 원본 JSON에서 직접 확인:

| 색상 | seed | episode 0 | episode 1 | episode 2 |
|---|---:|---|---|---|
| 빨강 | 182 | FAILED, 부적격 분리 | FAILED, 부적격 분리 | SUCCEEDED |
| 노랑 | 183 | SUCCEEDED | SUCCEEDED | FAILED, 분리 후 보유 확인 전 낙하 |

- 합계 적재 성공 3 / 실패 3 / timeout 0. 실패 진단은 `failure_bad_detach` 2건, `failure_dropped` 1건이다.
- 빨강 `expert_contract.runtime`은 전달 환경 snapshot과 완전 일치. 노랑은 seed만 183으로 다르다. 양쪽 질량 0.009kg, `transport_linear_pose_stop=true` 확인.
- 성공 3건 모두 최종 `valid_release=1`, `placement_hold_s≈0.60000008` 기록. 기존 설명의 “접근·분리 실패 3”보다 위 세부 플래그가 정확하다.
- 이는 이번 수신 PC의 실행 결과가 아니다. 비전 관측이 일부 소실된 성공 episode도 있으며, Teacher가 시뮬 내부 상태를 사용하므로 비전 정책의 수확 성능 근거가 아니다.
- 정책 4개의 원본 `run.json` 학습 질량은 모두 0.035kg이며, 9g은 평가 runtime의 명시적 override다. “9g 전달 묶음”을 9g으로 다시 학습한 정책으로 해석하지 않는다.

## 4. 실제 코드로 해결된 명세의 미확정 사항

| 쟁점 | 소스에서 확인한 결론 |
|---|---|
| 240Hz와 480Hz | `harvest_rl/env.py:59`에서 decimation에 contact_substeps를 곱하고 물리 dt를 나눈다. 명목 1/240×12와 substeps2는 실제 **1/480s·24step·정책20Hz** |
| break_distance 0.03 / hook 0.025m | `harvest_rl/logic.py`의 초기 일반 분리 조건은 attachment v4 분기에서 덮어쓴다. response5의 25mm 인장/40mm 전체 변위 조건이 추가됨. 단순 값 충돌이 아님 |
| 40ms 유지 | `env._apply_action()`에서 physics dt로 결합 판정. 매 물리 step 누적, 끊기면 0. 480Hz에서는 임계 도달이 20tick≈41.67ms이며 원본 로그도 일치 |
| 힘 제한 | short-hook 분리 조건을 계산한 뒤 대기 중 탄성력 크기를 과실별 임계력으로 제한. 제한 순서를 임의 변경하면 안 됨 |
| 관측 | `current_pair_geometry.selected_teacher_observation`은 다른 과실 슬롯을 지우고 선택 과실만 남김. **주변 과실 인지·회피가 학습된 정책으로 해석하면 안 됨** |
| 좌표 | `current_to_policy_frame`이 팔/박스 FK·관절 제한을 맞추고 기존 정책 프레임으로 변환. legacy 관측에 정책 좌표 기준 상수도 있어 농장 world 값을 그대로 넣으면 안 됨 |
| ROS 운용 | 인터페이스 초안과 Python target/executor 계약은 있지만 수확 `HarvestTarget` ActionServer는 없다. 수령 소스를 농장 `HarvestTask`에 바로 연결할 수는 없음 |

## 5. 적용 전에 보완할 두 가지 소스 문제

### 5.1 경로 보정 후 받은 USD 캐시가 재생성되는 경로

- `scripts/sim_team/prepare_receiver.py`는 생성 캐시 URDF/JSON/YAML의 원래 저장소 경로를 치환한다. 파일을 쓰지 않고 메모리에서 계산했을 때 변경 예정은 9개, 치환 후 URDF mesh 누락은 0개다.
- 하지만 `harvest_rl/current_robot.py:47`은 실행 시 `UrdfConverter`를 호출한다.
- 수신 Isaac Lab `asset_converter_base.py:88`은 config와 URDF 내용으로 MD5를 계산하고, 저장된 `.asset_hash`와 다르면 `force_usd_conversion=False`이어도 변환한다.
- 전달된 current cache 두 개의 hash는 원본 URDF와 일치하지만 **경로 치환 후에는 모두 달라진다**. prepare 스크립트는 해당 hash를 처리하지 않는다.
- 따라서 README 순서대로 prepare 후 평가하면 받은 current USD가 재생성되는 코드 경로가 있다. “캐시를 지우지 않는다”만으로 캐시 보존이 보장되지 않는다.
- 적용안: 원본 수령본은 보존하고 실행용 사본에서 경로 이식·캐시 재사용 검증을 먼저 보완한다. hash만 임의로 바꿔 차이를 숨기지 않고, geometry/관절/물리 계약이 동일한지 확인한다. **이번에는 prepare/변환을 실행하지 않았다.**

### 5.2 연속 수확의 HOME 복귀 시간 계산

- `harvest_runtime/isaac_return.py:59`는 한 번의 복귀 `_physical_step`에서 `settings.decimation=12`회 물리를 진행한다.
- 같은 환경의 실제 `cfg.decimation=24`, physics dt=1/480s이므로 복귀 한 호출의 물리 진행은 25ms다.
- 그런데 `tick_return`의 차분 속도·안정 dwell·목표 slew는 `env.step_dt=50ms`를 사용한다.
- contact_substeps=2에서 **실제 진행 시간과 제어 계산 시간의 2배 차이**가 정적으로 확인된다. 복귀·정지 확인 동작에 영향을 줄 수 있으므로 통합 전 수정 범위와 시험을 정해야 한다.
- 전달된 9g 평가는 단일 지정 과실 평가이며 물리 복귀를 검증한 결과가 아니다. 이 문제로 기존 3/6 결과를 무효라고 판단하지 않는다. 연속 수확/취소·정지 경로는 별도 검증한다.

## 6. 현재 PC 환경과 자산 통합 경계

| 항목 | 전달 | 현재 수신 PC |
|---|---|---|
| Isaac Python | 3.11.15 | 동일 |
| Isaac Sim / Lab package | 5.1.0.0 / 0.54.2 | 동일 |
| Isaac Lab commit | `37ddf626871758333d6ed89cf64ad702aef127d0` | 동일, tracked 변경 없음 |
| torch / torchvision / rsl-rl | 2.7.0+cu128 / 0.22.0+cu128 / 3.1.2 | 동일 |
| 비전 Python / Ultralytics / NumPy | 3.11.15 / 8.4.156 / 2.4.6 | `robot_venv`: 3.12.3 / 8.4.164 / 2.5.2 |

수신 Isaac Python은 `/home/ysy/isaac/env_isaaclab/bin/python3.11`이다. 패키지 metadata만 확인했으며 GPU 실행·드라이버/렌더 호환성을 인증한 것은 아니다. 전체 freeze에는 다른 작업용 패키지 차이도 있다. 현재 환경에 freeze를 일괄 덮어쓰지 않고 별도 비전 환경 또는 검증한 호환 조합을 사용한다. `.venv-yolo`는 Ultralytics가 같지만 Python/NumPy와 CPU torch 구성이 다르므로 완전 일치 환경으로 취급하지 않는다.

기존 생산자 절대경로 기본값이 일부 남아 있어 실행 시 `HARVEST_PY`, `STUDENT_DETECTOR`, `STUDENT_VISION_PY`, `EVAL_OUT`을 명시해야 한다. 새 평가 출력은 `sim/runs/robotarm/`에 둔다. 수신 정책과 run.json은 변경하지 않는다.

새 로봇 자산의 중요 차이:

- `current_robot`의 생성 USD는 **고정 차체·고정 바퀴·비활성 팔·고정 뚜껑**, 오른팔 6관절만 동작하는 독립 평가용이다. articulation 경로도 현재 농장과 다르다. 농장 주행 USD를 이 파일로 통째 교체하지 않는다.
- 전달 current USD는 fixed-joint 병합으로 박스 바닥 collision mesh가 base 아래에 들어 있다. 농장 기존 활성 USD의 바닥 누락을 보완할 근거 자산을 확보했다.
- 실제 9g 과실 캐시의 질량은 float 표현상 약0.0089999996kg, collision mesh 크기는 약66.284×70×75mm이며 convex decomposition 설정이다. 농장 과실의 기존 크기/충돌과 동일하다고 가정하지 않는다.
- 전달 소스/캐시에는 농장 10/6의 **캐스터 마찰 0 보정이 자동 반영되어 있지 않다**. 농장 자산 보완 시 기존 주행 보정을 보존하고 회귀 확인한다.
- 팔·바퀴의 URDF 링크/관절 내용은 기존 농장과 일치하지만 중앙 카메라 지지·장착 및 박스 바닥/기어 구조가 다르다. 전달 자산 변경을 필요한 부분부터 반영한다.
- 과실 물리/줄기/정책 주기, 오른팔 TF와 기존 왼팔 Window/audit 정합, 두 D435 구성은 여전히 농장 통합 작업이다.

## 7. 적용 작업의 확정 전 순서와 현재 상태

추가 대용량 필수 자료 요청보다 **수신 코드의 이식 보완과 독립 실행 검증**이 우선이다. 한 번의 통합 작업 범위에 다음을 포함하도록 기존 제안을 갱신한다.

1. 원본과 구분한 실행용 사본·버전/해시 기록, 경로 및 캐시 보존 보완, 비전 환경 준비.
2. 원본 단일 목표 9g 평가를 수신 PC에서 수행하고 환경·접촉·분리·적재·실행 해시를 새 기록으로 남김.
3. 복귀 시간 정합 보완 후 복귀/연속/취소·정지 검증. 후보별 및 주변 과실 접촉을 별도 기록.
4. 농장용 가동 차체를 유지하면서 오른팔·박스·과실 물리/TF/주기를 연결. 예찰 Window와 평가 영역을 같은 기준으로 조정하고 주행·센서 회귀 확인.
5. 기존 공통 `harvest_robot`의 요청/상태/결과와 받은 `harvest_runtime`의 내부 계약을 연결하는 최소 변경안 확정. 두 저장소의 동명 패키지를 같은 경로에 덮어쓰지 않음. 공통 동작/정답 입력 정책은 기존 승인 규칙 유지.

이번 직접 수행: 압축 수령/체크섬/경로 검사·별도 위치 추출, manifest/정책 해시 검사, 기존 파일 비교, 환경 metadata 비교, 원본 로그 집계, 코드 정적 분석 및 pxr 자산 검사. 보고서·상태 문서·이력만 갱신했다.

미실행: prepare_receiver, cache 변환, 의존성 설치, 정책 로딩/추론, 새로운 Isaac/PhysX/ROS 시험, 실물 구동, sim 운영 코드·설정·자산 반영, commit/push. 기존 사용자 변경을 보존했고 원격에는 문서를 반영하지 않았다.

복원은 이번 보고서와 관련 문서의 이번 항목만 이전 내용과 비교해 되돌린다. 원본 archive와 기존 인계 자료는 삭제하지 않는다. 검토용 추출본은 운영 경로에서 참조하지 않으며 이후 보관/정리는 별도 결정한다.
