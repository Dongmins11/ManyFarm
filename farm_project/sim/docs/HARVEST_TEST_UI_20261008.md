# 가변 Hz 로봇팔 수확 시험 UI

2026-10-08 KST. 기준 `main/450bf5f100a81986469a22aba47847d9c2619acc` 및 기존 작업을 보존한 미커밋 상태.
사용자 요청의 배치/수확 버튼을 기존 Isaac 농장·Teacher·근거리 과실 물리에 연결한 시뮬 전용 시험이다.

## 실행

```bash
cd ~/main/farm_project
python3 sim/tools/harvest_test_ui.py
```

Isaac GUI 창이 열리면 **Harvest physics Hz 입력·Apply → 1. Place robot(배치) → 정지 확인 → 2. Harvest(수확)** 순서로 누른다.
현재 Kit 기본 글꼴의 한글 표시 문제로 패널은 영문으로 표시한다.
ROS launch/source/colcon 빌드는 필요 없다. 기본 Isaac Python은 `~/isaac/env_isaaclab/bin/python`이며,
다른 설치는 `--isaac-python /경로/bin/python` 또는 `FARM_ISAAC_PYTHON`으로 지정한다.
실행 중인 운영 시뮬과는 포트·snapshot이 분리되지만 같은 GPU 자원은 사용한다.

- `--harvest-hz 240`: 초기 수확 주기 지정. 기본480Hz, 60Hz의 양의 정수배를 지원한다. GUI에서도 정지 상태에서 변경할 수 있다.
- `--seed 713`: 동일 초기 장면에서 무작위 배치 순서를 재현한다.
- `--prepare-only`: 독립 설정과 실제 실행 명령만 출력한다.
- `--duration-s 60`: 60 시뮬 초 후 시험 프로세스를 종료한다. 일반 관찰은 생략한다.
- 종료는 Isaac 창을 닫거나 실행 터미널에서 Ctrl+C다. Isaac의 Stop/reset 뒤에는 도구를 재실행한다.

## 버튼과 표시

| 항목 | 동작 |
|---|---|
| 1. Place robot | 기존 Section 수확 정차선에서 아직 시도하지 않은 부착 빨강/노랑 과실이 오른팔 Teacher 범위에 드는 위치를 무작위 선택한다. 다음 시험을 위해 오른팔 HOME을 초기화하고 차체를 즉시 배치한다. 이미 적재한 과실은 차체와 같은 변환으로 옮겨 바구니 상대 위치·자세·속도를 보존한다. 작업 위치로 카메라를 맞춘다. Nav2 주행 시험은 아니다. |
| 2. Harvest (선택 Hz) | 배치 후 실제 정지/HOME와 현재 후보를 확인한 경우 활성화된다. 기존 ArmSession을 통해 현재 위치의 후보를 과실당 한 번씩 시도한다. |
| Stop harvest | 기존 취소 계약으로 실제 정지를 확인한다. 정지 후 Place가 다시 활성화된다. HOME이 아니면 Place로 다음 시험을 준비한 뒤 Harvest를 누른다. |
| Harvest physics Hz / Apply | 정지 상태에서 다음 수확·physics-only 주기를 설정한다. 60/120/180/240/…Hz를 지원하며 렌더 목표60Hz와 정책20Hz는 유지한다. 수확 중 변경은 거절한다. |
| FPS | 최근 약1초의 실제 GUI 갱신 빈도. 물리 Hz 및 렌더 목표60Hz와 구분한다. |
| 물리 Hz / 활성 과실 | 실제 스케줄러 주기와 실제 active 배열 개수를 표시한다. 팔 주변 녹색 과실도 이웃 충돌 물리를 위해 활성화된다. 녹색은 수확 대상이 아니다. |
| 결과 | 작업 상태, 팔 단계, 실제 적재/실패 수를 표시한다. 처리 `SUCCESS`와 적재 성공은 별개다. 적재 0을 성공 수확으로 표시하지 않는다. |

배치는 현재 `scout_survey.json`의 정차선 X/방향/Y 범위, 측정된 차체→오른팔 변환,
`teacher_policy.json`의 작업 상자·HOME 거리 조건, 현재 과실 pose/부착 상태를 사용한다.
바닥 지도에서 `nav2_harvest.yaml`의 차체 footprint와 padding 전체가 자유 셀인지 검사한다.
지도 밖·미확인/장애물 셀·녹색·분리 과실·이미 시도한 과실은 배치 대상으로 선택하지 않는다.
배치 후 0.5 시뮬 초 연속 정지/HOME와 실제 후보를 다시 확인한다.

수확 중에는 재배치·중복 시작을 차단한다. 성공·취소 후에도 결과와 시도/적재 이력은 보존하며 다음 배치를 허용한다.
실제 정지 미확인(`CANCEL_UNCONFIRMED`, `safe_stopped=false`) 또는 기존 적재 과실이 이미 바구니를 벗어난 경우에는 재시작해야 한다.
이 오류를 정상 정지로 덮어쓰거나 과실을 재부착/재생성하지 않는다.

## 물리와 시험 범위

- 대기: 60Hz. 수확: UI 선택 주기, 기본480Hz. 물리 tick은 `1/Hz`초이며 480Hz는2.083ms다.
- 낮은 Hz는 학습 당시480Hz와 다른 물리 적분 조건이다. FPS 개선과 수확 안정성을 별도로 평가한다.
- 렌더: 60Hz 기준. Teacher 정책: 기존 20Hz. 실제 화면 FPS나 wall time 480회/초 보장은 아니다.
- 물리 활성 범위는 기존 오른팔 장착점 중심 0.8m, 유지 반경 1.0m다.
- 수확 종료 뒤 움직이는/분리된 과실은 기존 물리를 유지한다. 안정 조건이 충족되면 60Hz로 돌아온다.
- 기존 정책·물성·성공 조건·농장 과실 위치/회전/ID를 유지한다. 원본 USD를 저장하지 않는다.
- 정차선·바닥 여유·Teacher 입력 범위 검사는 팔 전체의 IK/동적 충돌 회피 또는 실제 적재 성공 보장이 아니다.
- 공통 미션·Nav2·실물 코드 변경 없음. 런타임의 `--harvest-test-ui` 모드는 단독 수확 장치와
  별도 출력 설정만 허용하며 외부 UDP 제어 명령을 무시한다.

## 기록과 검증

실행 설정·배치/버튼/주기/결과 이벤트: `sim/runs/harvest_test_ui/<UTC시각_실행ID>/`.
`ui_events.jsonl`의 첫 `OPEN` 레코드에 해당 물리 로그와 Teacher 로그 경로가 있다.
`frame_performance.jsonl`은 프레임별 제어·정책·영역준비·줄기외력·PhysX step·접촉관측·렌더·상태반영·전체과실 snapshot 시간을 초 단위로 기록한다.
`frame_s`는 로그 쓰기와 realtime sleep을 제외한 처리시간이고, `wall_s`의 프레임 간 차이는 두 비용까지 포함한다.
과실 분리만으로 수확 성공을 계산하지 않으며 기존 `trace.jsonl`/`result.json`에 실제 결과를 남긴다.

현재 검증 로그는 `sim/runs/harvest_hz_benchmark_20261008/`에 있다. 이전 최초 UI 시험은
`sim/runs/harvest_test_ui/validation_20261008/`에 보존했다.

### 현재 수확·성능 비교

Isaac Sim5.1 / RTX4070 SUPER, 각 주기마다 새 프로세스·새 장면, seed713 첫 배치
SEC10/Bed01/Pepper0017 yellow로 1회씩 실행했다. 진단 추론 trace 추가 옵션은 끄고,
같은 카메라·충돌 표시·렌더 목표60Hz·정책20Hz 조건을 사용했다. 카메라 센서와 lidar는 꺼져 있다.
FPS는 실제 렌더 프레임 시작 시각 간격으로 계산했다.

| 물리 Hz | 작업 중 평균 FPS | POLICY 구간 FPS | 실제 적재 | 최종 결과 |
|---|---:|---:|---:|---|
| 480 | 4.28 | 4.31 | 0/1 | 복귀 접촉2.804N, RETURN_FAILED; 실제 정지 확인 |
| 240 | 7.33 | 7.68 | 0/1 | 복귀 접촉3.294N 후 정지 미확인 |
| 120 | 13.95 | 12.42 | 0/1 | 복귀 접촉4.072N 후 정지 미확인 |
| 60 | 22.45 | 19.67 | 0/1 | 이웃 과실 분리 후 정지 미확인 |

작업 중 평균은 POLICY·복귀·정지 대기를 포함한다. 60Hz의 POLICY 구간은15프레임으로 짧으므로
장시간 정상 수확의 FPS로 일반화하면 안 된다. 이는 동일한 위치의 각1회 비교이며 농장 전체 성공률이 아니다.
네 프로세스는 모두 종료0이지만 수확은 모두 실패했다. 낮은 Hz에서 실제 정지 확인이 실패하면 버튼 차단을 유지한다.

초기 비교에서는 PhysX `foundLostPairsCapacity` 오류(필요최대4,048,988 / 설정2,097,152)가 발생했다.
농장 장면 버퍼를4,194,304로 늘린 뒤 위 네 조건을 다시 실행했고 동일 오류0건을 확인했다.
학습 물성·충돌 형상·solver를 바꾼 것이 아니라 장면 규모에 필요한 메모리 용량만 조정한 것이다.
초기 오류 포함 결과는 `baseline_buffer_overflow/`에 별도 보존했다.

병목 계측에서480Hz는 프레임당 약232ms 중 약196ms를 물리 step에 쓴다. 물리 tick당 약24ms를
프레임당8회 실행하는 비용이 크다. 렌더·Kit UI 약20ms, 줄기외력 약4ms, 접촉 관측 약5ms,
전체 과실 snapshot 평균 약4ms였다. 정책 추론이나 센서가 주된 병목이라는 근거는 없었다.
별도 PhysX 계측은 simulate0.34ms / fetch_results24.0ms를 측정했다. fetch_results는 계산 완료 대기와
결과 반영을 포함하므로 이 수치 전체를 GPU 계산 시간이나 USD 쓰기 시간으로 단정하지 않는다.

실제 설정은 GPU dynamics/GPU broadphase + CPU/numpy tensor 경로, 매 tick USD 위치·속도 쓰기,
Fabric 확장 비활성이다. 장면에는 convex 형상4,829개, articulation3개가 남아 있다.
과실 활성 수5개가 전체 충돌 장면도5개라는 뜻은 아니다.

팔 정책 없이 같은480Hz 물리에서 USD 쓰기 ON→OFF→ON을 각240tick 비교했다.
fetch_results 평균은23.99→18.00→24.64ms였다. 따라서 매 tick USD 쓰기는 약6ms의 비용이며,
끄더라도 약18ms의 native 계산 완료 대기·readback 비용이 남았다. 한 가지 설정만 끄면480Hz가
실시간이 된다는 근거는 없다. 이 진단은 별도 프로세스에서 수행하고 원래 설정을 복원했다.
운영 UI의 화면 갱신을 희생하는 쓰기 비활성화는 적용하지 않았다.
[공식 성능 안내](https://docs.isaacsim.omniverse.nvidia.com/latest/reference_material/sim_performance_optimization_handbook.html)도
물리 주기·CPU/GPU 데이터 경로·USD/Fabric 갱신 비용을 구분해 점검하도록 설명한다.
이 진단을 기준으로 아래의 480Hz 최적화를 추가 적용했다.

관련 컨트롤러·실행기·주기·영역 검사52개와 실제USD 물성 정렬 검사7개 PASS.
실제 GUI 취소→Place 재활성→240Hz 입력 적용→재배치/HOME→Harvest 재활성→새240Hz 작업도 통과했다.
`retry_events.jsonl`과 `retry.log`에서 상태·결과/ID 보존 및 프로세스 종료0을 확인할 수 있다.

성공 상태 후 추가 시험에서는 SEC15 작업이 SUCCESS/정지확인으로 끝나고 Place 재활성을 확인했다.
하지만 실제 적재는0/실패1(`pending_detach,bad_detach`)이어서, 적재 과실을 가진 재배치 검사는
선행조건 불충족으로 명시적 실패(exit1) 처리했다. `success_retry_events.jsonl`의 HARVEST_RESULT와
`success_retry.log`에 보존했다. 실제 적재가 있는 재배치의 상대 pose·속도 보존은 컨트롤러 검사로
확인했으며 해당 물리 E2E는 미검증이다. 성공률 개선을 위해 정책/줄기 물성을 바꾸지는 않았다.

### 480Hz PhysX 최적화와 정적 전환 철회 — 2026-10-08 후속

최종 요구는 **예찰 로봇·수확 로봇·운송 로봇·선별 로봇팔 네 대의 동시 동작**이다.
성능을 높이기 위해 다른 로봇을 정적으로 만드는 것은 이 요구에 맞지 않는다.
이전 시험 UI에 넣었던 선별기·예찰 로봇43강체/42관절의 정적 전환 함수와 호출, 전용 검사를 제거했다.
원본 USD에는 저장하지 않았으므로 이전 시험 프로세스를 종료하고 새 stage를 열면 원래 동적 물리가 복원된다.
현재 시험 맵의3개 관절계 복원은 네 로봇 동시 운용 구현·성능 검증과 구분한다.

현재 유지한 변경은 **USD 위치·속도 쓰기를 렌더 프레임의 마지막 물리 tick에 수행**하는 것뿐이다.
480Hz에서 중간7회 쓰기를 생략하지만 줄기 힘·물리 step·접촉 관측은8회 모두 실행한다.
60Hz에서는 기존 경로를 사용하며, 예외 발생 시 원래 쓰기 설정을 복원한다.
이 옵션은 독립 수확 UI에만 적용하고 일반 fleet은 기존 경로를 유지한다.
학습 팔 물성·충돌 형상·GPU dynamics/GPU broadphase/TGS·solver12/4·정책20Hz·수확480Hz는 유지한다.

이전 동일 seed713·480Hz GUI 비교의 기록은 다음과 같다. 각 조건은1회이며 네 로봇 동시 운용 시험이 아니다.

| 조건 | 평균 FPS | 프레임당 물리 step | 실제 적재 |
|---|---:|---:|---:|
| 변경 전 | 4.28 | 195.84ms | 0/1 |
| 로봇 물리 유지 + USD 쓰기만 변경 — 현재 유지한 방식 | 4.67 | 171.66ms | 0/1 |
| 두 로봇 정적화 + USD 쓰기 변경 — 철회한 방식 | 7.01 | 102.43ms | 0/1 |

7.01FPS와 물리 step48% 감소를 목표 환경의 성능 개선 수치로 사용하지 않는다.
유지한 방식의 기존 비교 결과는 약9% FPS 개선이며 쾌적한 수준이 아니다. 수확 성공 문제도 남아 있다.
로봇 물리를 유지한 USD 쓰기 시험에서 과실 PhysX/USD/Fabric root 위치 오차는0m,
표시 하위 메시 최대 오차는1.3e-15m였다. 독립 상자 시험은480→60→480Hz, 중간 tick의 자연 sleep,
tensor 위치·속도 변경 후 재활성화를 통과했다(8초·480render·3420tick, 최대 위치 오차1.92e-8m, 종료0).
정적화를 제거한 코드의 스케줄러15개·UI17개·fleet 진입점2개 검사는 통과했다.
이전 정적화 전용3개 검사는 해당 기능과 함께 제거했다.

현재 World는 numpy/CPU 상태 조회 경로를 사용하고 Teacher 정책도 CPU에서 실행한다.
GPU 물리가 계산한 위치·속도·접촉력을 CPU의 줄기 힘 계산·접촉 판정 코드가 읽고 다음 힘을 입력한다.
하지만 `fetch_results` 계측에는 **물리 계산 완료 대기와 결과 반영 비용이 함께 포함**된다.
당시에는 GPU 계산 자체·CPU로의 데이터 전달·USD 쓰기의 비중을 분리하지 못했다.
아래 후속 Nsight 실측에서 주병목은 GPU 관절계 솔버 실행이고, GPU→CPU 복사는 작다는 것을 확인했다.
현재 장면의 모든 로봇 물리를 유지한 결과이며 최종 네 로봇 동시 운용 시험은 아니다.

다른 비교 실험의 scene query 비활성화4.10FPS·CPU thread0 4.52FPS는 적용하지 않았다.
CPU dynamics/MBP10.51FPS도 학습 GPU backend와 달라 적용하지 않았다.

로그: `sim/runs/physx_optimization_20261008/`. `batch_launch.json`/`batch.log`는 로봇 물리를 유지한
쓰기 최적화 시험이고, `production_launch.json`/`production.log`는 **철회한 정적화 방식의 과거 기록**이다.
`sleep_check/result.json`에 sleep 검증이 있다. 정적화 제거 후 실제 UI 복원 확인은
`restored_ui_launch.json`, `restored_ui.log`, `restored_scene.json`에 별도로 기록한다.
원래 physics tick/주기 UI/팔 정렬/과실 표시 동기화 수정은 보존한다.

## 다른 PC에 변경 파일 적용

정적화 철회를 반영한 최신6개 파일 묶음은 `sim/runs/physx_optimization_20261008/changed_files.tar.gz`다.
기존 버튼/Hz 수정이 적용된 PC에서 대상 파일의 별도 변경을 보관하고 다음과 같이 적용한다.
이전7개 파일 묶음을 적용했다면 폐기한 `sim/tests/test_harvest_test_background.py`도 제거한다.

```bash
tar -xzf "$HOME/Downloads/changed_files.tar.gz" -C "$HOME/main/farm_project"
```

아래는 그 이전 버튼/Hz 변경 파일 묶음 안내다.

이번 파일 묶음은 `sim/runs/harvest_hz_benchmark_20261008/changed_files.tar.gz`다. 기존 시험 UI에 적용하는14개 현재 파일이며 이전 미커밋 변경도 포함하므로 대상 파일과 비교한다.
현재 작업 PC에는 이미 반영되어 있으므로 다시 풀 필요 없다. 대상 PC의 별도 수정 파일은 먼저 보관한다.

```bash
tar -xzf "$HOME/Downloads/changed_files.tar.gz" -C "$HOME/main/farm_project"
```

복원은 버튼 조건/HOME 준비·주기 입력·프레임 계측 및 농장 GPU 버퍼 변경만 비교해서 되돌린다.
기존 과실 표시 동기화와 팔 물성 정렬 등 이전 작업은 보존한다. 원본 USD·운영 JSON·정책 파일은 수정하지 않았다. 커밋·푸시는 수행하지 않았다.

## 충돌·중력 진단 추가 — 2026-10-08 후속

`Physics only`로 팔 없이 주변 과실을 선택한 Hz로 관찰하고, `Selected/All`로 충돌 와이어를 표시할 수 있다.
`Fruit physics inspector`에 고정/동적·중력·변위·회전·줄기 힘·선택 과실별 손가락 접촉력이 표시된다.
[확인 순서와 실제 수치, 랜덤 회전이 남는 이유](HARVEST_PHYSICS_INSPECTION_20261008.md)를 참고한다.
관찰 중에는 배치/수확을 막고, 관찰 OFF 후 정지 확인을 거쳐 실행한다. 수확 정책·줄기 물성은 그대로다.

## GPU/CPU 병목 분리와 이전 Nav2 환경의 차이 — 2026-10-08 후속 실측

사용자 요청은 CPU/GPU 병목을 실제로 분리하고, 현재 대기22FPS와 이전 Nav2 약70FPS의 차이를
설명한 뒤 물리 조건 타협 여부를 판단하는 것이다. 기준은 main/450bf5f와 기존 미커밋 변경이다.
이번에는 운영 소스·정책·물성·원본 USD를 바꾸지 않고 격리 실행의 계측과 대조만 수행했다.
모든 결과와 재현 wrapper는 `sim/runs/physx_bottleneck_20261008/`에 있다.

### 실제 시간을 소비하는 곳

Nsight Systems2025.3.2의 CUDA/NVTX/OSRT 추적과 PhysX 내부 profile zone을 함께 기록했다.
대기60Hz76tick + 수확480Hz352tick, 총428tick이다. CPU IP sampling은 시스템 권한 제한으로
수행하지 않았고 전역 보안 설정도 변경하지 않았다. Nsight 계측 부하는 별도 비계측 FPS와 구분한다.

| 비용 | 직접 측정 |
|---|---:|
| USD 쓰기를 생략한 수확 tick의 `fetch_results` 벽시계 | 17.843ms/tick |
| 같은 구간에서 실제 CUDA 커널이 실행 중인 시간의 합집합 | 15.924ms/tick |
| 복사까지 포함한 GPU 작업 시간 비중 | 위 `fetch_results`의89.7% |
| GPU→CPU 복사 | 전체428tick 평균0.0619ms/tick |
| `simulate` 호출 | 평균0.394ms/tick |

CUDA 커널515,266개는 모두 동일 Isaac 프로세스·GPU·context에 속하고 `fetch_results` 구간 안에서
실행됐다. 렌더/Teacher 추론 CUDA 커널을 물리 비용으로 합산한 결과가 아니다. CPU에서 호출한
`fetch_results`의 경과 시간이 길다는 것은 CPU가 그 시간만큼 직접 계산한다는 뜻이 아니다.
이번에는 GPU 솔버가 실행되는 동안 CPU 호출이 완료를 기다리는 비중이 컸다.
GPU→CPU 복사를 개선하는 것만으로 이17.8ms를 없앨 수 있다는 설명은 맞지 않는다.

가장 비싼 두 커널은 `artiSolveInternalConstraintsTGS1T`,
`artiPropagateRigidImpulsesAndSolveSelfConstraintsTGS1T`다. 각각15,408회(428×36),
모든 launch가1block×32thread였다. 공식107.3/PhysX5.6.1 구현에서도 이 경로는 thread 하나가
관절계 하나를 처리한다. 현재3개 관절계는 대량 병렬 학습 환경과 달리 이 커널의 병렬 처리 폭이 작다.
이것은 GPU 전체가 포화됐다는 주장이나 커널 시간 전체가 순수 산술 연산이라는 주장이 아니다.

GPU 경로는 활성 강체·관절계의 solver position/velocity 반복 횟수를 각각 최대값으로 합친다.
현재 농장은 수확 관절계12/4, 기존 관절계32/1 설정이 함께 있어 실제 커널 반복은32+4였다.
따라서 수확팔 속성12/4가 일치한 기존115항목 검사만으로 장면 전체 solver 동작까지 같다고
판정할 수 없다. 임의로 다른 로봇의 반복 횟수를 낮추거나 전역 상한을 씌우지 않았다.
32/1 설정은 원본 맵의 `/World/sorting_station_portable/root_joint`,
`/World/scout_robot_camera_fixed/base_footprint`에 있다. 전달 학습 코드의 과실도 기본16/1이고
해당 학습 설정은 이를 덮어쓰지 않으므로 학습 장면의 실효 반복을 단순히12/4라고 부를 수 없다.
학습 전체 장면의 실제 kernel 반복 횟수는 이번에 추적하지 않았다. 이 구분은
`offline_iteration_audit.json`의 자산·설정 대조 결과에 기록했다.

근거: `gpu_480_nsys.nsys-rep`, `gpu_480_analysis.json`, 독립 검산 `gpu_kernel_audit.json`.
원본 profile의 일별 run 경로는 `gpu_480_nsys_launch.json`에 기록했다.
공식 소스: [최대 반복 횟수 취합](https://github.com/NVIDIA-Omniverse/PhysX/blob/107.3-physx-5.6.1/physx/source/gpusolver/src/PxgContext.cpp#L974),
[TGS 반복](https://github.com/NVIDIA-Omniverse/PhysX/blob/107.3-physx-5.6.1/physx/source/gpusolver/src/PxgTGSCudaSolverCore.cpp#L1327),
[관절계별 thread 처리](https://github.com/NVIDIA-Omniverse/PhysX/blob/107.3-physx-5.6.1/physx/source/gpuarticulation/src/CUDA/internalConstraints2.cu#L1554).

### 아무 작업을 하지 않아도 느린 이유

같은 ReviewCamera,1280×720,센서OFF,각각 새 프로세스에서 준비 구간을 제외하고 측정했다.
아래 수확 UI 조건은 모두97개 동적 강체·288개 고정 과실 강체·3개 관절계·4,829개 convex shape를
유지했다. 고정 과실도 충돌 형상은 엔진에 남는다. 다른 로봇을 정적으로 만든 비교가 아니다.
대기 물리는480Hz가 아니라60Hz였다.

| 조건 | 실제 프레임 갱신 FPS | 물리/프레임 | 렌더/프레임 | 전체 과실 좌표 기록/프레임 |
|---|---:|---:|---:|---:|
| 현재 수확 UI, GPU | 29.80 | 23.82ms | 5.90ms | 2.86ms |
| 같은 장면, CPU/MBP | 50.23 | 5.64ms | 6.59ms | 3.30ms |
| GPU, 좌표 기록만 생략한 진단 | 31.95 | 24.10ms | 6.07ms | 0ms |
| CPU/MBP, 좌표 기록만 생략한 진단 | 59.53 | 5.32ms | 6.43ms | 0ms |
| 이전 Nav2 구성에 가까운 원본 맵 대조 | 59.56 | 1.81ms | 4.90ms | 없음 |

현재 루프는60FPS 제한이 있다. 원본 맵 대조의 sleep을 제외한 처리 용량은138.49frame/s지만
실제 표시 FPS는59.56이다. 이를 실제138FPS 또는 사용자가 기억한70FPS의 정확한 재현이라고
표현하지 않는다. 이번 대조는 `run_sim.main()`을 실행한 시뮬레이터 시험이며 ROS2/Nav2 경로 주행은
수행하지 않았다. 과거 카메라·창 크기·센서·주행 로그가 없어 사용자가 본70FPS 자체는 미검증이다.

그럼에도 실행 환경의 간극은 확인됐다. 원본 맵의 과실은 표시 메시였고 물리 충돌체가 없었다.
원본 맵 대조는43개 동적 강체·2개 관절계·29개 convex shape, CPU/MBP였다. 현재 UI는 수확로봇을
추가하고 과실288개의 물리 형상을 구성하며 GPU/TGS 설정과5Hz 전체 과실 좌표 기록을 사용한다.
같은 배경 맵 파일을 열었다고 같은 물리 장면인 것은 아니다. 과실 shape 증가가 성능 저하의 전부라는
뜻도 아니다. 현재 장면 그대로 CPU로 바꾼 비교에서 물리 비용23.82→5.64ms가 별도로 확인됐다.

기존 열린 UI의 대기 로그는27.48FPS, 물리20.04ms·렌더8.94ms·좌표기록6.07ms/프레임이었다.
카메라/표시 상태에 따라22~30FPS 수준이 달라질 수 있지만, 이번 측정만으로 사용자22FPS의
정확한 당시 조건까지 재현했다고 말하지 않는다. 좌표 기록은 과실288개의 메시 탐색과 world bound를
매번 재계산한다. 기존 UI에서는 약71ms의 작업이0.2시뮬초마다 한 번씩 발생했다.
`cProfile`에서도 메시 탐색/bound 계산이 중심이고 파일 저장은 작았다.

대조 기록: `idle_comparisons.json`, `live_idle_before.json`, `scene_truth_profile.pstats`,
`nav_reference/nav_reference_result.json`. 원본 맵 대조 전후 원본USD SHA256은 동일했다.

### 개선 판단과 검증 한계

우선순위는 **480Hz와 로봇 물리를 유지한 CPU backend 비교 검증**이다. 이번 CPU/MBP480Hz
수확은 작업 중13.01FPS, POLICY12.81FPS, 물리38.98ms/프레임이었다. seed713의 실제 적재는0/1,
복귀 접촉2.839N으로 RETURN_FAILED, 실제 정지 확인, 프로세스 종료0이었다.
성능 이득이 수확 성공이나 학습 GPU backend와의 동등성을 보장하지 않는다.

동일 조건의 GPU480Hz도 새 프로세스로 재측정했다. Nsight 추적은 두 FPS 비교 실행에서 끈 상태다.

| 480Hz, 모든 로봇 물리 유지 | 작업 중 FPS | POLICY FPS | 물리/프레임 | 실제 적재/결과 |
|---|---:|---:|---:|---|
| 현재GPU, USD쓰기 프레임당1회 | 4.69 | 4.71 | 170.72ms | 0/1, RETURN_FAILED/2.804N |
| CPU/MBP, 같은 USD쓰기 방식 | 13.01 | 12.81 | 38.98ms | 0/1, RETURN_FAILED/2.839N |

두 실행은 같은seed/대상/주기/형상·질량·정책을 사용했다. 물리 backend 차이로 복귀 정지 소요시간이
달라 작업 프레임은156/204개였고, POLICY는 둘 다138프레임이다. 모두 정상종료0, PhysX오류0건,
실제 정지 확인이다. 수확 성공률은 각각1회 실패이며 농장 전체 성공률 결론을 내리지 않는다.
`harvest_comparisons.json`에 구간별 계산값과 원본 로그 경로를 보존했다.

CPU480Hz도 물리 처리만 약39ms/프레임이므로 이 조건에서 렌더만 줄여60FPS를 달성할 수 없다.
당장 Hz를 낮추거나 다른 로봇을 비활성화하기보다 CPU backend의 관측·접촉·성공률 회귀를 먼저
비교하는 편이 근거가 있다. 이후에도 목표 속도가 부족하면 물리 주기/자산 관절 구성/표시 주기의
타협을 각각 평가해야 한다. 전체 과실 좌표 기록 캐시는 별도 후보이며 GPU solver 주병목의 해결책은 아니다.

좌표 캐시 prototype은 오프라인19개 변경 사례와 실제 Isaac 대기의 첫8개 출력에서 기존 구현과
동일했다(벽시계 기록 제외). 실제 대기에서 snapshot 비용은2.86→0.22ms/프레임으로 줄었지만,
USD 변경 감지 callback에도 총0.385초/394회가 추가됐다. 전체 FPS는29.80→30.22로 차이가 작았고
실행 간 변동과 분리되지 않았다. 따라서 이를 큰 최적화로 포장하거나 운영 코드에 적용하지 않았다.
실제 수확 중 캐시 동등성은 미검증이다. `truth_cache_runtime_comparison.json`,
`scene_truth_cache_equivalence.json`과 prototype wrapper를 후속 비교용으로 보존했다.

재현(프로젝트 루트, Isaac GUI 접근 가능한 환경에서 순차 실행):

```bash
python3 sim/runs/physx_bottleneck_20261008/launch_profile.py
python3 sim/runs/physx_bottleneck_20261008/launch_cases.py gpu_idle cpu_idle gpu_no_truth cpu_no_truth
python3 sim/runs/physx_bottleneck_20261008/launch_nav_reference.py
python3 sim/runs/physx_bottleneck_20261008/launch_cases.py gpu_harvest cpu_harvest gpu_cached_truth_verify
```

wrapper는 해당 파일명의 결과를 덮어쓰므로 기존 증거를 보존하려면 먼저 결과 폴더를 복사한다.
운영 GUI와 동시에 실행하면 자원을 공유해 FPS 비교가 무효가 될 수 있다.

이번 CPU 전환·좌표 기록 생략은 격리 시험에만 적용했다. 기본 UI는 기존GPU/수확480Hz/대기60Hz와
모든 로봇 물리를 유지한다. 최종 네 로봇 동시 미션·Nav2 동시 수확·여러 위치 성공률은 미검증이다.
새로운 운영 코드 최적화나 backend 기본값 변경은 이번 진단 결과와 구분한다. 커밋·푸시 없음.
진단 종료 뒤 일반 `python3 sim/tools/harvest_test_ui.py --seed 713`을 다시 실행했다.
새 session은`20261008T094925_dt_6va5f`, UI OPEN/IDLE60Hz와 정상 프레임 기록·오류0건을 확인했다.
`final_ui.log`, `final_ui_status.json`에 복원 상태를 남겼다.

이번 갱신 문서4개의 사본은 `sim/runs/physx_bottleneck_20261008/diagnostic_docs.tar.gz`다.
이 PC에는 이미 반영했다. 다른 PC에는 기존 파일의 별도 변경을 먼저 보관하고 적용한다.

```bash
tar -xzf /path/to/diagnostic_docs.tar.gz -C ~/main/farm_project
```
