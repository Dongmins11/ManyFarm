# HCR-3A 선별장 인수·단독 검증 및 농장 연결 자료

작성: 2026-10-28. 로컬 기준 main/ea256936 및 기존 미커밋 작업.
이번 범위는 **레인에 들어온 과실 이후의 선별**이다. 전달본의 운송 접근·박스 개방·기울임·배출은 실행/통합하지 않았다.

## 현재 결론

- 전달본 원본을 보존하고 단독 Isaac 시험을 수행했다. 빨강 1개 집기·놓기·HOME·보관 확인은 통과했다.
- 8개 연속 시험은 원본 ROI에서 7개만 선별하고 SUCCESS가 됐다. 잔여 빨강 1개가 ROI에 충분히 잡히지 않는 문제가 재현됐다.
- ROI 높이를 늘리는 비교는 3개 선별 후 MIXED로 정체했다. 이 설정은 농장/원본에 채택하지 않았다.
- 승인받은 공통 연결: farm_interfaces 타입 2개/빌드 등록, hcr_sorting 원본 15개 파일 추가. namespace 외 제어/FSM/수치 변경 없음.
- 실제 ROS와 실제 RGB·팔 물리 정상 배치는 4개 전부 보관(빨강2/노랑2), 잔량0 및 SUCCESS를 확인했다.
- 실제 ROS와 실제 RGB·팔 물리를 연결한 취소 시험: CANCELED, 빨강 1개. 놓기·HOME 후 물리 수량과 ROS 수량 일치.
- 농장 과실 투입, 농장 실행 루프, reset/pause, Frontend 전체 사이클은 **아직 미통합**이다. 이번 시험 과실은 격리된 단독 fixture이며 실제 수확 과실을 대신 생성한 농장 시험이 아니다.

## 원본과 보존 범위

- ZIP: `/home/ysy/main/HCR3A_SIM_TEAM_20261008.zip`
- SHA256: `2d0e397a28cedb1391349f1ab9ae18fe04f471b2a2c21a3776cf47e7b7e6a1c3`.
- 보존 경로: `sim/vendor/hcr3a_20261008/HCR3A_SIM_TEAM_20261008/`
- 전달본 snapshot: `60cbd85eba2bcee4fcd7515e11cb5dd3dfa182a6` 및 ZIP에 포함된 별도 파일. 커밋만으로 ZIP 전체를 복원할 수 있다고 가정하지 않는다.
- `verify_delivery.py`: 275개 파일 해시·리소스 참조 PASS. 실행 결과와는 별개다.
- 원본 `run_hcr_sim.py --preloaded`를 사용해 운송 경로를 제외했다. source/config는 복사본에서 유지하고 로그·생성 자산은 매 시험별 workspace에 격리했다.
- 원본 CPU 240Hz를 단독 시험에 사용했다. 농장 CPU 60Hz 설정, 로봇 바퀴·바구니·주행 설정은 이번 작업으로 변경하지 않았다.

## 이번 공통 변경

사용자 답변: **“공통 연결 변경 적용”**. 아래 제안 범위를 승인받은 뒤 적용했다.

1. `robot/ros_ws/src/farm_interfaces/action/SortBatch.action` 추가.
2. `robot/ros_ws/src/farm_interfaces/msg/SorterStatus.msg` 추가.
3. 해당 `CMakeLists.txt`에 생성 목록 2개 추가.
4. `robot/ros_ws/src/hcr_sorting/` 15개 파일 추가. 원본에서 `smartfarm_interfaces`를 `farm_interfaces`로만 치환. core/Modbus/성공·실패/수량/취소/timeout 유지.

두 타입의 이름·타입·순서는 Frontend 전달본, ZIP, 최신 Confluence 원문과 일치한다. 기존 예찰·수확·운송 타입은 덮어쓰지 않았다.
파일별 원본·치환 횟수: [common_source_map.json](common_source_map.json).
적용 내용: [common_integration.proposed.patch](common_integration.proposed.patch) — 파일명은 제안 당시 이름을 보존했으며 현재 승인·적용 완료.
15개 파일 모두 namespace 치환 외 byte 일치 검증. 별도 `sim/runs/hcr3a_intake_20261028/ros/install`로 빌드했으며 기존 운용 overlay를 덮어쓰지 않았다.
원복은 이 패치만 역적용한다. 실행 중에는 하지 않는다. 이번 이후 수정이 없는 경우 저장소 루트에서 `git apply -R farm_project/sim/docs/changes/HCR3A_INTEGRATION_20261028/common_integration.proposed.patch`로 원복 가능하다.

## 실제 시험 결과

결과 원본: `sim/runs/hcr3a_intake_20261028/`.

| 시험 | 입력 | 결과 | 의미 |
|---|---:|---|---|
| preloaded_01 | 4개, 1회 완료에서 종료 | 빨강 1, DONE, 20.679초 sim | 한 동작 성공, 전체 배치 성공 아님 |
| preloaded_02 | 8개, 원본 ROI | 빨강 3/노랑 4, SUCCESS, 142.125초 sim | 87.5% 선별, 실제 1개 남음 |
| preloaded_03 | 8개, ROI 높이만 32px | 빨강 1/노랑 2, SCANNING, 220초 sim 상한 | 5개 남음, A/B/D MIXED. 개선안 미채택 |
| physics_success_01 | 4개, 실제 ROS/Modbus/RGB/물리 | SUCCESS 빨강2/노랑2, 잔량0 | 정상 완료 Result와 물리 보관 수량 일치 |
| physics_cancel_01 | 4개, 실제 ROS/Modbus/RGB/물리 | 첫 BUSY에 취소, CANCELED 빨강 1 | 정상 놓기·HOME 완료 이후 취소와 물리/ROS 수량 일치 |

- 기존 오프라인 시험: 제어 6 + 모델 4 + 카메라 4 + link 1 + core 14 + Modbus 3 = **32 PASS**. 소켓 시험의 최초 sandbox 오류는 보존하고 localhost 허용 재실행으로 통과 확인.
- 실제 ROS Action/Status + 모의 카메라/Modbus 시험: SUCCESS 2 red/1 yellow, A 반복 명령, 중복 거절, 취소 1개 보존 PASS. 이는 물리 시험과 구분한다. 원본 시험의 empty .25초/settle .1초는 이 가속 통신 시험에만 사용했다.
- 실제 RGB/물리 ROS 시험은 camera 1초, HCR 3초, ACK 10초, BUSY 120초, READY 10초, scene 60초, batch 1800초 등 원본 기본값 유지.
- `physics_success_01`은 원본 ROI/판정으로 실제 ROS SUCCESS 2 red/2 yellow, 물리 sorted 4/4, 잔량0 확인. 통신 후에도 원본 heartbeat를 유지해 시뮬120초(28800step) 최종 보고와 대조했다. 액션 완료 시각은 events.jsonl의 result이며,120초 전체를 선별 동작 시간으로 해석하지 않는다.

### 누락 및 정체 원인

`preloaded_02`의 잔여 과실은 물리 레인 B의 빨강이며, 현재 카메라 라벨은 C다. 위치는 HCR 로컬 `(0.30410, 0.07525, 0.10286)m`이고 `sorted=false`다.

원본 C ROI는 `[349,142,18,11]`이다. 저장된 실제 RGB를 원본 분류기에 다시 넣으면 빨강 비율 7.0707%, 노랑 0%로 최소 8%보다 낮아 NO_COLOR가 된다. 네 영역 모두 NO_COLOR 3초 조건으로 SUCCESS가 된 것이다. 과실이 물리적으로 없어진 것이 아니다.

ROI 높이만 32px로 늘리면 남은 빨강을 잡지만 다른 과실의 꼭지/노란색 계열 픽셀까지 함께 포함한다. 비교 시험 최종 실제 영상에서 A/B/D는 빨강 54.95/47.92/46.70%, 노랑 11.98/26.25/25.52%로 두 색이 모두 8%를 넘어 MIXED였다. 픽셀 비율은 재계산한 사실이며, 꼭지 영향은 영상과 위치에 근거한 해석이다. HSV 임계값이나 MIXED/완료 판정을 완화하지 않았다.

`SUCCESS`는 원본 계약상 **네 관측 영역의 색상 미검출 종료**이며 상류/레인 잔량 0의 보증이 아니다. 관제 결과 수량과 별도로 투입 수량·실제 보관 수량·잔량을 평가 로그에 보존해야 한다. 정답 잔량으로 제어 성공을 강제로 만들지 않는다.

원본 라벨 우선순위는 카메라 A→B→C→D이고 선택 가능한 색이 있는 첫 영역을 처리한다. 이번 투영에서 카메라→물리 레인은 A→D, B→C, C→B, D→A다. 물리 레인 문자열을 그대로 카메라 우선순위로 해석하면 안 된다. 실제 연속 BUSY 라벨은 B,A,A,C,B,D,D였고 같은 A/D 반복이 확인됐다.

## 담당자에게 공유할 연결 정보

### 좌표계·레인·과실 경로

농장 stage는 metre, Z-up, 현재 `T_map_world`는 identity다. 이 값은 `sim/ros_ws/src/farm_sim_config/config/scout_survey.json`의 실행 설정으로 읽어야 한다.

| 항목 | 확인한 경로/의미 |
|---|---|
| 농장 stage | `sim/assets/envs/output/farm_with_plants_v5.usd` |
| 기존 과실 예 | `/World/Vegetation/Bed_01/Fruits/Pepper_0001_yellow` |
| 기존 과실 식별 | `crop:color` 및 실제 prim_path. 경로 목록은 `farm_paths.json` |
| 전체 농장 과실 | 288개: 빨강/노랑/초록 각96개. 전체 수를 이번 투입 수량으로 사용하지 않음 |
| 기존 선별장 | `/World/sorting_station_portable`, map=(-7,14), yaw=+90° |
| 전달본 레인 바닥 | `/World/HCRStation/IntakeSlope`, 경계 `IntakeWall0`~`IntakeWall4` |
| 전달본 팔 | `/World/HCRRobot` |
| 전달본 카메라 | `/World/SortingCamera` |
| 전달본 보관부 | `/World/HCRStation/RedBinFloor`, `YellowBinFloor`; 같은 색 `RedStorageSlope`/`YellowStorageSlope`도 원본 보관 판정에 포함 |
| 단독 fixture 과실 | `/World/Peppers/{A..D}_{index}_{red|yellow}`. **농장 통합에서는 생성하지 않음** |

HCR 로컬 원점은 팔 설치판 중심의 바닥이다. +X는 투입부, -X는 보관부, 물리 A~D는 +Y→-Y, red bin은 +Y, yellow bin은 -Y다. 레인 중심 Y는 `0.1875, 0.0625, -0.0625, -0.1875m`, 집기 명목 X는 `0.308m`이다. 파일 설정에서 계산한다.

**새 HCR 모델은 기존 선별장과 원점·투입면 방향·크기가 다르다.** 기존 root 위치/회전을 그대로 적용하면 투입면이 맞는다고 보장할 수 없다. 기존 접근점8004=(-7,13.25), 북향은 기존 모델 기준이다. 새 HCR을 (-7,14), -90°로 놓는 단순 예도 +X 투입부 끝이 약 y=13.293까지 나와 기존 접근점과 약4.3cm밖에 떨어지지 않는다. 이는 제안 계산이며 배치 승인이 아니다. 새 자산은 투입면·로봇 충돌 여유를 먼저 맞춘 다음 로컬→world 변환을 확정해야 한다. 이번 작업은 기존 모델/도킹 마커/그래프를 교체하지 않았다.

### 기존 과실 재사용과 시작 조건

농장 `configure_farm_fruits()`/`FruitAttachments`의 prim_path를 그대로 유지해야 한다. 전달본 `spawn_peppers()`는 단독 시험 전용으로 남기고, 통합 어댑터는 투입된 실제 객체를 바인딩해야 한다. ID·색·prim·부모 좌표계·현재 물리 pose를 유지하고 실제 투입 수량 목록을 batch_id에 연결한다. 복제/삭제 후 새 과실 생성으로 인계 수량을 만들지 않는다.

현재 농장 `MechanicalRosServer.unsupported_unload()`는 실제 하역 미구현을 반환한다. 수확→운송도 정렬 기반 가상 인계이며, 이번 새 전달문만으로 레인 실제 투입 구현이 이미 완료됐다고 볼 수 없다. **투입 완료 이벤트의 발행 주체와 실제 prim 목록 전달이 아직 필요하다.** ZIP의 transport/payload로 대체하지 않는다.

현재 ROS 계약의 시작 순서는 다음과 같다.

1. 관제가 배치 반입 가능 상태(`receive_ready`)를 확인한다. 기본 receive_enabled=false를 유지하고 투입 허용을 별도로 결정한다.
2. 해당 배치의 레인 투입 및 운송 안전 이격을 완료한다. `BucketUnload SUCCESS`는 이 둘을 보장해야 한다.
3. 최신 `ready=true`를 확인하고 `/sorter_01/sort_batch`로 단 한 번 배정한다.
4. 팔 동작 중 새 명령을 받지 않고 완료된 동작마다 물리 보관 및 HOME 이후 누적 집계를 보고한다.
5. Feedback 수량을 더하지 말고 최신 누적값으로 교체한다. Result로 확정하고 취소/실패에서도 이미 완료된 수량을 보존한다.

선별 서버는 BucketUnload를 직접 구독하지 않는다. 이 연결은 관제/농장 연결부 책임이며 이번 단독 probe는 이 상류 완료를 검증한 것이 아니다.

### ROS 설정

- 시뮬 고정: `ROS_DOMAIN_ID=13`, `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`. ZIP의 Domain67/localhost, 최신 실물 운영 문서의 Domain24를 복사하지 않았다.
- robot_id `sorter_01`.
- `/sorter_01/sort_batch`: `farm_interfaces/action/SortBatch`.
- `/sorter_01/status`: `farm_interfaces/msg/SorterStatus`, 1Hz.
- `/sorter_01/reset_fault`: `std_srvs/srv/Trigger`.
- 시뮬 Modbus만 `127.0.0.1:1502`, peer127.0.0.1. 실물 `.2:502/.100`에 연결하지 않는다.
- camera_state/runtime/journal은 시험별 경로. 저널 삭제나 프로세스 재시작으로 실패를 성공 처리하지 않는다.

## 농장 통합 전에 남은 작업

1. **카메라 ROI 보정**: 실제 과실 자세·연속 대기열에서 미검출/MIXED 모두 검증. 이번 단순 확장 설정은 미채택. 원본 판정을 변경할 필요가 있으면 담당자 공통 코드 변경으로 별도 검토.
2. **배치와 좌표 변환**: 전달본은 원점 고정이며 제어/부착/보관 판정에 `/World` 경로와 world 좌표가 들어 있다. 설정 기반 station frame/prim 경계를 추가해야 한다. 원본 팔 수치·보관 범위를 임의 조정하지 않는다.
3. **농장 기존 과실 바인딩**: 레인 투입 결과의 원래 prim/ID/개수/배치 연결. 다른 과실 템플릿·크기로 갈아끼우지 않는다.
4. **공통 루프/reset/pause**: 전달본은 자체 AppLauncher/SimulationContext/step을 만든다. 농장은 기존 run_fleet World 루프 하나를 써야 한다. 시뮬 정지 때 팔·선택·동작 시간을 함께 멈추고, reset 시 기존 작업·부착·누적 수량·저널을 일관되게 종료해야 한다. 현재 run_fleet은 시간 역행 reset을 감지하면 프로세스 재시작을 요구하며, 새 선별 수명주기 연결은 없다.
5. **시계 정책**: 원본 ROS Supervisor는 monotonic wall time, 팔은 sim time이다. `/use_sim_time`만 넣어도 camera/scene/BUSY 제한이 자동 정지하지 않는다. pause 시 freshness와 동작 timeout 정책을 명시적으로 연결해야 하며 원본 watchdog을 끄거나 임의로 늘리지 않는다. 공통 시계 변경이 필요하면 기존 실물 기본 동작을 유지하는 별도 승인안으로 다룬다.
6. **관제 연쇄 검증**: 실제 투입 완료→SortBatch→Status/Feedback/Result→취소/오류/재시작. 이번 probe가 Frontend 전체 사이클 통과를 뜻하지 않는다.

전달본 `Sorter.choose()`는 색 선택은 RGB로 하지만 집는 위치는 실제 과실 좌표를 읽어 보조 파지를 만든다. 이 기능 근사 시험을 비전만 사용하는 실물 집기 성능으로 해석하지 않는다. 농장 정답을 공통 비전/주행 입력으로 주입하는 연결은 이번에 추가하지 않았다.

## 근거·재실행

- [최초 통신 문서](https://robot3final.atlassian.net/wiki/spaces/3/pages/12746755), [현재 운영 기준 v4](https://robot3final.atlassian.net/wiki/spaces/3/pages/30343169). 현재 운영 기준의 farm_interfaces 필드/순서 확인. 조회본은 runs의 `protocol_30343169_v4.md`에 보존.
- 원시 물리 보고: 각 시험 `workspace/outputs/sorting_station/hcr_sim/report.json`, `camera_rgb.png`, `camera_preview.png`, `runtime.json`, `metadata.json`.
- `physical_summary.json`, `roi_replay.json`, `common_import_audit.json`, `interface_audit.json`, `farm_paths.json`.
- ROS 연결 시험 도구: `sim/tools/probe_hcr_sorting.py`. 모의 DONE/카메라를 생성하지 않는다. 실제 시뮬과 함께 별도 시험 폴더에서만 실행한다.

단독 원본 8개 재현(먼저 ZIP workspace를 새 실행 폴더에 복사; 원본 vendor에서 실행하지 않음):

```bash
cd <새 실행 폴더>/workspace
ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET \
  /home/ysy/isaac/env_isaaclab/bin/python -u src/sorting_station/run_hcr_sim.py \
  --config src/smartfarm_description/config/hcr3a_random8_validation.json \
  --preloaded --pepper-per-lane 2 --auto-start --steps 52800 \
  --headless --no-camera-window --device cpu
```

공통 변경은 적용/별도 빌드했으며 커밋·푸시는 하지 않았다. 이전 시험과 기존 미커밋 변경은 보존했다.
