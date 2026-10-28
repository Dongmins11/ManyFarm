# HCR 선별장 기능 검증 — 2026-10-07

이 결과는 사진·노트에서 구성한 기능 근사 모델의 검증이다. 실물 HCR-3A의 관절 영점·동특성·파지력 검증은 아니다. 파지는 명시적인 보조 고정 조인트와 선택 과실–로봇 접촉 제외를 사용한다.

처음 RGB/ROS 시험은 운반박스 추가 전의 기록이다. 현재 기본 실행은 차량 반입부터 시작하므로 아래쪽 최신 반입 시험을 참고한다. 이전 배치를 재현하려면 `--preloaded --config outputs/sorting_station/hcr_sim/validation/standalone/configuration.json`을 추가한다.

## RGB + 물리 기반 전체 배치

```bash
bash src/sorting_station/run_hcr_sim.sh \
  --headless --auto-roi --auto-start --pepper-per-lane 2 --steps 60000
```

- 결과: `SUCCESS`, 빨강 4 / 노랑 4, 오류 없음, 38,947 physics steps / 약 162.28 simulation seconds.
- 실제 렌더 RGB를 기존 HCR HSV 분류기로 판정했다. 자동 ROI는 카메라 투영에서 몸통 패치를 잡으며 색 라벨이나 렌더 segmentation을 판정 입력으로 사용하지 않는다.
- BUSY 레인 순서 `A A B B C C D D`, 각각 ASSISTED_GRASP와 DONE 1회. 다음 과실이 내려온 같은 레인도 다시 선택했다.
- 8개 과실 모두 최종 위치가 해당 색 보관 구획 안에 있고 `sorted=true`임을 별도로 검사했다. 보관 구획은 경사 통로와 평평한 보관함을 포함한다. 뒤 과실은 앞 과실에 막혀 경사 통로에 머물 수 있다.
- 마지막 로봇 복귀 이후 A–D가 3초 동안 NO_COLOR여서 배치를 완료했다.
- 근거: `outputs/sorting_station/hcr_sim/validation/standalone/`의 `report.json`, `metadata.json`, `configuration.json`, `full_batch5.log`, `overview.png`, 카메라 PNG, `teaching.json`. 설정·실행 소스 SHA256을 기록했다.

## 회귀 검사

- 새 환경 단위 검사 9개 통과: 치수·14개 IK 자세·URDF 축/TCP·파트 의존성·선택 우선순위·완료 1회 집계·빈 장면 판정·보관 구획·통신 heartbeat.
- 기존 HCR core / Modbus 검사 17개 통과.
- Python 16개 파일 구문 검사와 런처 bash 구문 검사 통과.
- 실제 ROS 프로토콜 회귀 시험 통과: Goal/Feedback/Result/Status, TCP BUSY/DONE/READY, 같은 A 빨강 2회 + B 노랑 1회, 중복 goal 거부, 취소 시 진행 중 1회 완료. 이 시험은 모의 카메라/동작을 사용했으며 RGB/물리 전체 배치와 구분한다. 로그: `outputs/sorting_station/hcr_sim/ros_protocol.log`.

## 실제 ROS goal + RGB/물리 통합

`tests/ros_goal_probe.py`와 `run_hcr_sim.py --headless --modbus --auto-roi --pepper-per-lane 1 --steps 24000`을 동시에 실행했다. ROS Jazzy / Domain 67, 별도 journal, 루프백 1502, 카메라 timeout 3초의 검증 프로파일이다. 실물 기본 timeout 1초는 변경하지 않았다.

- 실제 관제 action Goal 수락, WAIT_ACK/BUSY/WAIT_READY feedback, 최종 `SUCCESS`, 빨강 2 / 노랑 2, `error_code=NONE` 반환.
- 물리 제어 이벤트는 A→B→C→D, DONE 4회. 최종 과실 4개 모두 올바른 색 보관 구획 안에 남아 있음을 별도로 확인했다.
- 시뮬레이터는 24,000 steps / 100 simulation seconds에 정상 종료했다. 로봇 로컬 상태 SCANNING은 다음 레지스터를 기다리는 상태이며 배치 Result SUCCESS와 구분한다.
- 근거: `outputs/sorting_station/hcr_sim/validation/ros/goal_result.json`, `report.json`, `runtime.json`, 소스·설정 metadata, ROS/시뮬레이터 로그와 PNG.
- 실물 로봇 IP 또는 실제 제어 포트에는 연결하지 않았다.

## 마지막 자산 정리

위 운반 시험 이후 파프리카 원본을 공통 `smartfarm_description/meshes/pepper` 위치로 바이트 변경 없이 복사하고, HCR 파생 USD 캐시를 `outputs/sorting_station/hcr_sim/assets/peppers`로 분리했다. 기존 OMX의 기본 원본/캐시 경로는 유지했다. 이동 전후 빨강·노랑 각각 156개 composed USD 속성(visual·collider·질량·물리)이 동일함을 검사했고, 새 원본/캐시로 240-step 초기화·RGB 시험도 정상 종료했다. 근거는 `validation/common_assets.json`, `common_assets_compare.log`, `common_asset_smoke.log`다. 운반 시험의 당시 소스 SHA는 각 시험 metadata에 보존한다.

## 재현 범위

데스크탑 RTX 4070 SUPER, Isaac Lab Python `/home/bhc/isaac/env_isaaclab/bin/python`, 물리 240 Hz, RGB 카메라 640×480, 렌더 요청 15 Hz로 실행했다. 과실 크기 90×105 mm / 질량 9 g, 폼보드 마찰 0.12/0.08, 패드 마찰 1.2/1.0은 명목값이다. 투입 하단 턱 55 mm, 보관부 치수·높이·로봇 링크도 일부 근사값이다.

한 가지 기본 배치를 검증했다. 크기·마찰·카메라 위치를 넓게 바꾼 성공률이나 실물 재현 정확도를 측정한 결과는 아니다. 직접 ROI를 지정하는 GUI는 구현했고, 이번 자동 시험에서는 투영 ROI를 사용했다. 줄기나 다음 과실을 함께 잡아 MIXED가 되면 해당 작업을 선택하지 않는다.


## GUI 오류 수정 검증

- 원인: 실제 Isaac Python의 opencv-python-headless 4.11.0.86 / GUI NONE. 기존 namedWindow 호출에서 오류 발생.
- 카메라 GUI를 PC 기본 Python의 OpenCV(Qt5) 자식 프로세스로 분리했다. Isaac 쪽 headless cv2에서 실제 창 표시/정상 종료를 검증했다.
- 실제 비-headless Isaac+카메라 GUI를 2,400 physics steps / 10 simulation seconds 실행해 정상 종료했다. 자동 ROI RGB 판정은 A=RED, B=YELLOW, C=RED, D=YELLOW. 결과/영상: outputs/sorting_station/hcr_sim/validation/gui/.
- 실제 시험 창에 포커스를 주고 a/Shift+C/g와 마우스 드래그를 보내, 부모 이벤트 큐에 순서대로 전달됨을 확인했다. Qt의 Shift 보존과 x 취소 별칭을 반영했다. 시험 후 원래 포커스/마우스 위치를 복구했다. 로그: gui_key_probe.log.
- 구역 지정·저장·시작 이벤트 순서, c/C/x 구분, 창 닫기 종료를 포함한 회귀 11개. 원본 파프리카 USD에 필요한 fruit_* 상대 텍스처도 복구해 GUI에서 회색 과실로 보이는 문제를 수정했다. 물리 형상·질량·마찰·ROS/레지스터 계약 변경 없음.

- 최종 코드(텍스처·Qt Shift 처리·x 취소 포함)로 480-step GUI 재검증도 정상 종료하고 A/C 빨강·B/D 노랑 판정을 확인했다. 오류가 난 Isaac Python/headless OpenCV 환경에서 회귀 11개 통과. 최종 근거: validation/gui/final/.


## 운반박스 반입 및 g 오류 수정 — 2026-10-07 추가

- 사용자 오류 원본: `validation/before_transport/report.json`의 VISION_PICK_COLOR_MISMATCH. 같은 디렉터리의 zones.json은 영상 왼쪽부터 A–D인데 당시 물리 레인은 오른쪽부터 A–D였다. 단순히 키가 누락된 것이 아니라 첫 선택에서 잘못된 레인으로 해석됐다.
- 현재 ROI 중심→실제 집기 레인 일대일 매핑, 중복/가이드 밖 시작 차단, 이동 전 ROI 오류 복구를 추가했다. 기존 사용자 zones.json은 바꾸지 않았다. 단위/회귀 15개 통과: `validation/transport_unit.log`.
- 실제 GUI 창의 g 입력으로 IDLE→SCANNING→차량 접근/배출/READY→첫 APPROACH를 확인했다. 6,500 steps에 HOME 단계로 정상 종료, SIM 오류 없음. GUI 중 겹치는 ROI 드래그는 거부하고 기존 구역을 유지했다. 시험 중 ROI가 재편집되어 이 GUI 시험의 최종 매핑은 A→A,B→B,C→C,D→D다. 원래 저장된 왼쪽부터 구역의 검증은 아래 별도 ROS 시험과 단위 검사에서 수행한다. 근거: `validation/transport_gui/run.log`, report/PNG/audit.json. 초기 고정 역순 매핑만 기대한 GUI probe assertion은 이 재편집 때문에 실패했고, 실제 g 이벤트 및 최종 유효 매핑/무오류 결과를 별도로 확인했다.

차량 반입부터 8개 전체 선별:

```bash
bash src/sorting_station/run_hcr_sim.sh --headless --auto-start --auto-roi --steps 50000
```

- 43,027 steps / 약179.28초에 SUCCESS, 빨강4/노랑4, 오류 없음. 차량은6초 접근/1초 배출문/3초 기울임/5초 배출 대기 뒤18초에 전체 미끄럼틀 진입을 확인했다.
- BUSY/DONE8회, 같은 레인 재선택 포함. 놓기·복귀 이후만 집계하며 마지막에도 8개 전부 올바른 색 보관부 안에 남아 있음을 별도 감사했다.
- 과실은 운반 중 고정하지 않은 자유 rigid body. 베이스·박스·문만 kinematic으로 움직였다. 보조 고정 파지는 선별 로봇이 집은 뒤에만 적용된다.
- 초기55 mm 턱 시험은 첫 과실4개가 설치판으로 넘어가 TRANSPORT_DUMP_INCOMPLETE로 종료됐다. 실패를 성공 처리하지 않았다. 하단 턱을 명목100 mm로 보강한 후 위 시험이 통과했다. 100 mm는 실물 측정값이 아니다.
- 근거: `validation/transport_8/`의 report/metadata/configuration/PNG/audit.json, `validation/transport_trial2.log`. 실패 원본은 `validation/failed_dump_55mm_report.json` 및 transport_trial.log. 이전 standalone/ROS 기록은 보존한다.


실제 ROS Goal + 저장된 수동 구역 + 차량 투입:

```bash
# 분리 ROS domain67의 probe를 실행한 뒤
bash src/sorting_station/run_hcr_sim.sh --headless --modbus --pepper-per-lane 1 --steps 30000
```

- Goal 수락 → BATCH_ACTIVE 상승 → 차량 반입 → A–D 순차 선택 → Result SUCCESS. 빨강2/노랑2, error_code=NONE. WAIT_ACK/BUSY/WAIT_READY feedback 포함, BUSY/DONE4회.
- 자동 ROI를 사용하지 않았다. 사용자가 저장한 원래 왼쪽부터 구역을 그대로 읽었고 A→물리D, B→C, C→B, D→A 매핑을 확인했다. 선택 순서는 사용자 A 노랑/B 빨강/C 노랑/D 빨강이었다. 초기 색상 불일치 오류는 재발하지 않았다.
- 30,000 steps /125 simulation seconds에 정상 종료. 시뮬레이터 SCANNING은 다음 명령 대기이며 관제의 SUCCESS와 구분한다. 최종 과실4개가 모두 올바른 색 보관부에 남아 있음을 별도 확인했다. 사용자 zones.json은 작업 전 백업과 바이트까지 동일하다.
- 근거: `validation/ros_transport/` goal_result/report/audit/metadata/configuration/zones/PNG, `validation/ros_transport_probe.log`, `validation/ros_transport_sim.log`. 서버와 시뮬레이터 exit0. 단위/회귀 최종15개, Python 및 bash 구문 검사 통과.
- 실제 차량 주행·배출 구동기 동특성·무작위 대량 투입·실물 파지력 검증은 포함하지 않는다. 4통로 배분 insert와 차량 외형은 기능 근사다.


## 기존 Waffle 운반로봇 URDF 재사용 — 2026-10-07 추가

사용자 요청에 따라 별도 생성한 차량/넓힌 박스/4통로 insert를 제거하고 공통 `transport_robot.portable.urdf`와 기존 Waffle·박스·모터 기구·문·슬라이딩 뚜껑 STL을 직접 변환해 사용한다. 공통 FK도 기존 `model_geometry.py`를 사용한다. 원본 URDF 두 종류, transport.json, 참조 메시, FK 총 98개 파일이 Git HEAD와 바이트 단위로 동일하다. 소스 hash는 `validation/existing_transport_sources.json`에 기록했다.

- 원래 박스 30×30×19 cm, 축 높이25.5 cm, 기존 관절/문/뚜껑 형상과 제한을 유지했다. 원본 FK의 8개 rigid body를 PhysX kinematic target으로 움직인다. 과실은 운반/배출 중 자유 rigid body다. 표시 메시만 물리 목표와 동기화하며 충돌 형상은 교체하지 않는다.
- 설치된 PhysX GPU backend는 kinematic target을 지원하지 않아 CPU 물리/GPU 렌더로 실행한다. CPU에서는 Fabric을 끄고 /physics/updateToUsd를 켜 실제 HCR/과실의 자세로 RGB를 갱신한다. 배출문은 입구에서 먼저 열고 정렬한다. 베이스 자율주행/모터 토크 동특성 검증은 아니다. 박스 마찰0.5/0.4와 집기 높이 여유25 mm는 명목값이며 실제 TCP 거리45 mm 검사는 유지한다.
- 두 층8개는 기존 문/상단 기구 앞에 끼어 TRANSPORT_DUMP_INCOMPLETE였다. 실패 원본 `validation/existing_transport_failed_two_layers/`와 existing_transport_8.log를 보존했다. 원래 박스를 넓히지 않고 검증된 단층4개를 기본으로 한다. 운반 모드의 더 큰 적재 프리셋은 시작 시 차단하며 --preloaded에는 긴 레인 대기열을 남긴다. 실물 최대 적재 용량을 확정한 결과는 아니다.

최종 실제 ROS Goal + 저장된 수동 ROI + 기존 차량 물리 투입:

```bash
# Domain67 ROS probe를 실행한 뒤 (127.0.0.1:1502 전용)
bash src/sorting_station/run_hcr_sim.sh --headless --modbus --steps 30000
```

- Goal 수락→BATCH_ACTIVE→차량 반입/배출→24.5 simulation seconds에 READY→RGB 선별→Result SUCCESS. 빨강2/노랑2, error_code=NONE. BUSY/보조 파지/DONE 각각4회. 사용자 구역 기준 B B C C 순서로 같은 레인의 다음 과실을 반복 처리했다. 원래 박스 폭을 유지하므로 가운데 두 레인으로 투입됐다.
- 30,000 physics steps /125 simulation seconds에 정상 종료. 관제 Result는 SUCCESS, 모의 팔 로컬 SCANNING은 다음 명령 대기다. 최종 과실4개가 모두 해당 색 보관부에 남아 있고 sorted=true임을 별도 감사했다. 소스/설정 hash가 최종 실행 코드와 일치한다.
- 기존 사용자 zones.json은 작업 전 백업과 바이트까지 같다. 수동 구역 A→물리D,B→C,C→B,D→A 매핑을 사용했으며 자동 ROI는 이 최종 시험에서 사용하지 않았다.
- 최종 자산/제어/구역/통신 회귀17개와 Python/bash 구문 검사가 통과했다. 초기 solver/속도/CPU 표시 동기화 실패 기록은 existing_transport_failed_* 디렉터리 및 trial 로그에 남겨 성공으로 취급하지 않는다.
- 근거: `validation/existing_transport_ros/`의 goal_result/report/audit/metadata/configuration/zones/PNG, existing_transport_ros_probe.log, existing_transport_ros_sim.log, existing_transport_unit.log.


## 과실 높이 75 mm 정정 검증 — 2026-10-07

이전 기록의 105 mm는 실측 근거 없는 임시 가정이었다. 사용자 정정에 따라 HCR 설정의 pepper_length를 0.075 m로 변경했다. 지름 90 mm/질량 9 g은 여전히 명목값이다. 원본 과실 USD와 기존 운반로봇 자산은 수정하지 않았다.

- 재생성된 빨강/노랑 파생 USD의 시각 메시 전체 높이와 충돌 메시 높이 모두 75 mm 확인. 적재 중심과 집기 가이드는 같은 설정 높이를 사용한다.
- headless, auto-start, 저장된 수동 ROI, 30,000-step 상한으로 실행: 운반로봇 투입 READY 24.5초 → 실제 RGB 선별 → 25,596 steps /106.65 simulation seconds에 SUCCESS, 빨강2/노랑2, 오류 없음, exit0.
- 완료 후 4개 모두 해당 색 보관부 안에 잔류하고 sorted=true. 기존 zones 파일 불변, 운반 원본98개 hash 불변, 회귀18개 통과. 근거: validation/height75_manual/ 및 height75_manual.log.
- 이전 105 mm 모델의 두 층8개 배출 실패를 75 mm 모델의 적재 한계로 일반화하지 않는다. 이번에는 단층4개만 검증했다. 75 mm에서의 8개 배출은 미검증이며 기존 단층 프리셋을 유지한다.


## 75 mm 과실 8개 배출 및 1회 선별 조기 종료 — 2026-10-07

사용자 요청에 따라 8개 전체 배출을 시험하고, 성공했다면 선별2회에서 종료하도록 설정했다. **8개 배출은 실패했다.** 전체 배출 조건을 충족하지 못한 상태에서는 선별을 시작하지 않았으며 실패 기준을 완화하지 않았다.

| 시험 | 미끄럼틀 판정에 들어온 중심 수 | 결과 |
|---|---:|---|
| 두 층, 38도, 도킹 X=0.715 m | 5/8 | 배출 불완전, 선별0회 |
| 한 층3열, 38도 | 4/8 | 배출 불완전, 선별0회 |
| 두 층, 45도 | 6/8 | 배출 불완전, 선별0회 |
| 두 층, 45도, 도킹 X=0.695 m | 7/8 | 배출 불완전, 선별0회 |
| 위 조건 + 5~45도 재기울임2회 | 7/8 | 배출 불완전, 선별0회 |

마지막 시험의 남은 과실 중심은 X=0.72271 m, Y=-0.10593 m, Z=0.34517 m로 박스 출구/미끄럼틀 입구에 남았다. 미끄럼틀 상단 X=0.70651 m + 기존 판정 여유15 mm 범위를 넘었다. 각 수치는 기존 중심 위치 판정에 의한 수이며 과실 몸체 전체가 박스와 비접촉이라는 증명은 아니다. 마지막 실패는17,161 steps /71.504 simulation seconds에 기록했다. 박스와 과실은 기존 형상을 그대로 사용했고 운반 과실의 고정/순간이동은 없다. 실물 배출 가능 수를 확정하는 시험은 아니다.

- 실패 근거: validation/height75_8_attempts.json, height75_8_two_layers/, height75_8_three_columns/, height75_8_two_layers45/, height75_8_two_layers45_dock695/, height75_8_rock_failed/의 report/configuration/audit/PNG와 height75_8_trial1~5.log. 한 층3열 레시피는 폐기했다. 현재8개 옵션은 두 층 실험 프리셋이며 기본은 검증된4개다. 재기울임은 별도 설정에서만 활성화하고 기본0회다.
- 조기 종료 대조 시험: 기본4개/38도/도킹 X=0.715 m, 저장된 수동 ROI, --stop-after-sorted 1. 노랑1개 선별·운반, HOME 복귀, 올바른 보관부 확인 후 DONE에서 종료. 남은3개는 미선별이며 전체배치 SUCCESS가 아니다. report validation_limit_reached=true / batch_complete=false, DONE1회. 10,416 steps /43.4 simulation seconds, 오류 없음.
- 대조 근거: validation/height75_stop1_control/ 및 height75_stop1_control.log. 기존 운반 원본98개 SHA/저장 ROI 불변, 회귀21개 및 Python/bash 구문 검사 통과. 이는8개 배출 성공으로 집계하지 않는다.


## 무작위 중력 적재와 8개 배출 — 2026-10-07

사용자가 실제처럼 무질서하게 쌓인 운반 과실을 요청했다. 기본 운반 적재를 격자/고정 두 층에서 무작위 위치·회전으로 변경했다. 기존 30×30×19 cm 박스 위에 초기 충돌 없는 8개를 생성하고, 자유 rigid body 접촉·중력으로 쌓은 뒤 출발한다. 박스 안 전체 충돌 형상/선속도/각속도를 검사하며 최소4초+0.5초 안정화를 기다린다. 물리 적재 실패 시 출발하지 않는다. 원본 박스/뚜껑/문/기구와 과실 높이75 mm, 명목 지름90 mm/질량9 g은 유지했다. 최초 화면은 쌓인 운반박스를 가까이 보여주며 출발 후 전체 장면으로 복귀한다. 판정용 카메라와 기존 수동 ROI는 움직이거나 덮어쓰지 않는다.

초기 seed42 시험은 기존 중심 위치 기준으로8개 배출/빨강2회 선별이 통과했으나, 사후 검사에서2개의 몸체가 박스 바닥에 남았음을 발견했다. 이를8개 배출 성공으로 집계하지 않는다. 근접 중심 판정에 더해 **모든 과실의 실제 충돌 hull이 원래 박스 전면을 완전히 벗어나야** READY가 되도록 강화했다. 실패 원본: validation/random8_seed42_spatial_only/ 및 random8_seed42.log. 남은 과실을 순간이동하거나 오류 기준을 완화하지 않았다.

최종 검증은 seed43, 45도, 도킹 X=0.695 m, 5~45도 재기울임2회 프로파일로 수행했다. 이는 기본4개/38도/X=0.715 m 프로파일의 검증 결과가 아니다.

- 투입만 실행: 무작위8개가4.5초에 박스 안에서 안정됨 → 자유 접촉 반입/재기울임 →59초에 전체8개 READY. 저장된 최종 자세와 파생 USD 충돌점을 독립 계산했으며8개 hull 모두 cargo-local 전면X=0을 벗어났다(최소 여유0.1067 m). 중심8개 모두 미끄럼틀 범위. 선별0회, 오류 없음. 근거: validation/random8_seed43_unload/의 report/configuration/audit/PNG 및 random8_seed43.log.
- 선별2회 시도: 위8개 배출 뒤 노랑1회 완료. 다음 앞 과실의 초록 꼭지를 원래 B ROI(15×11px)가 YELLOW로 판정하여 VISION_PICK_COLOR_MISMATCH로 두 번째 이동 전에 차단했다. 실제 빨강 몸통과 꼭지의 영상 위치로 확인했으며 자동 색 라벨 교체나 사용자 ROI 수정은 하지 않았다. 실패 근거: validation/random8_seed43_sort2_error/ 및 random8_seed43_sort2.log. 2회 성공으로 표현하지 않는다.
- 사용자 허용 범위인 선별1회로 최종 재실행: 8개 전체 배출59초 → 실제 RGB 노랑1회 선별·운반·HOME 복귀·올바른 노랑 보관부 도착 →18,697 steps/77.90417 simulation seconds에 DONE에서 정상 종료. error="", validation_limit_reached=true, batch_complete=false, 나머지7개 미선별. 근거: validation/random8_seed43_sort1/의 report/configuration/metadata/audit/PNG 및 random8_seed43_sort1.log. 전체8개 선별 완료 또는 전체 배치 SUCCESS가 아니다.
- 회귀26개 통과. 무작위 seed42/43/7의 초기 충돌/박스 개구 범위, 독립 LP 교차 검사, 재현성, 안정화 전 출발 차단, 적재 타임아웃, 박스에 남은 과실의 READY 거부를 포함한다. 구문 검사 통과. 기존 운반 원본98개 SHA256와 사용자 zones.json 바이트 불변을 각 최종 audit에서 확인했다.

다른 seed의 배출 성공률·원래 실물 모터 토크·실물 파지력은 검증하지 않았다. 선별 파지는 기존 보조 고정 방식이다. 무작위 자세에서는 기존 아주 작은 ROI가 꼭지 색에 민감하므로 이후 여러 회 선별을 하려면 사용자가 과실 몸통을 포함하도록 영역을 확인·재지정해야 한다. RGB 판정/불일치 차단은 유지했다.
