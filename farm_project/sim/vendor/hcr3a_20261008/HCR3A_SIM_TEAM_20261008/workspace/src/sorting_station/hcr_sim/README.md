# HCR-3A 실물 선별장 기능 시뮬레이션

2026-10-07 실물 사진과 Samsung Notes 치수를 기준으로 만든 Isaac Sim / Isaac Lab 환경이다. 수확용 SO-ARM101 및 기존 OMX 선별 환경과 별도로 실행한다.

## 실행과 구역 지정

저장소 루트에서 다음을 실행한다. 이 데스크탑의 Isaac Lab Python을 기본으로 사용한다.

```bash
bash src/sorting_station/run_hcr_sim.sh
```

다른 설치에서는 `ISAAC_PYTHON=/해당/환경/bin/python`을 지정한다. Isaac 환경에는 `numpy`, `scipy`, `torch`, OpenCV 및 Isaac Lab이 필요하다. Isaac의 `opencv-python-headless`로도 실행된다. 기존 운반로봇의 PhysX 운동학 목표를 사용하기 위해 기본 물리는 CPU(`--device cpu`), 영상 렌더링은 GPU를 사용한다. 이 설치의 GPU 물리에서는 kinematic target API가 지원되지 않아 운반 모드의 `--device cuda:0`은 시작 시 안내하고 차단한다.

카메라 창은 별도 GUI Python 프로세스에서 표시한다. 기본은 이 PC의 `/usr/bin/python3`와 GUI 지원 OpenCV이며, 다른 환경에서는 `HCR_GUI_PYTHON=/해당/GUI환경/bin/python`을 지정한다. 분류·구역 저장·로봇 제어는 Isaac 프로세스에서 처리하고, 표시 영상과 마우스/키 이벤트만 GUI 프로세스와 교환한다. GUI 로그와 마지막 표시 영상은 `outputs/sorting_station/hcr_sim/gui/<실행ID>/`에 기록한다. `--headless` 또는 `--no-camera-window`에서는 GUI 프로세스를 실행하지 않는다.

1. Isaac 창에서 보관부·로봇·미끄럼틀 전체를 관찰한다. 카메라 창은 미끄럼틀 하단을 위에서 본 영상이다.
2. 카메라 창의 회색 가이드 4개는 하단 집기 위치다. 소문자 `a`를 누른 뒤 원하는 첫 번째 레인의 가이드 안을 사각형으로 드래그한다. A–D 이름은 원하는 순서로 붙일 수 있으며, 사각형의 영상 위치로 실제 레인을 연결한다. 왼쪽부터 A–D로 지정해도 된다. `b`, `c`, `d`도 같은 방식으로 지정한다. 맨 앞 과실 몸통의 좁은 부분을 잡고 줄기와 뒤에 대기하는 과실은 제외한다. 줄기 색이 노랑 범위에 들어가면 YELLOW 또는 MIXED로 오판할 수 있다.
3. `s`로 구역을 저장한다. 구역을 편집하는 동안 새 작업 선택은 중지된다. 카메라 위치·해상도를 바꾸면 구역을 다시 지정한다.
4. 소문자 `g`로 더미 배치를 시작한다. 운반로봇이 접근하고 배출문을 연 뒤 박스를 기울여 과실을 붓는다. 투입·안정화가 끝난 뒤에 색 판정으로 선별한다. 먼저 과실을 보고 구역을 지정하려면 `t`로 투입만 실행하고 구역 지정·저장 후 `g`를 누른다. A→B→C→D 순서로 선택한다. 같은 레인에 다음 과실이 내려오면 다시 선택할 수 있다.
5. `x` 또는 대문자 `C`(Shift+C)는 새 작업을 중단하고 진행 중 1회를 완료한 뒤 취소한다. 소문자 `c`는 C 구역 편집이다. `q` 또는 ESC는 종료한다. Qt/PyQt5 환경에서는 실제 문자와 Shift를 보존하며, 다른 GUI 백엔드에서도 `x`로 취소할 수 있다.
6. 모든 구역이 3초 동안 `NO_COLOR`이면 `SUCCESS`가 된다. `WAIT`, `MIXED`, 미지정 구역은 빈 선별장으로 판단하지 않는다. `r`은 이동 시작 전 ROI 관련 오류를 해제한다. 구역을 수정하고 `g`를 누르면 재시작한다. 완료·취소 후 `r`은 남은 과실로 새 배치를 시작한다. 관절 추종·파지·놓기 오류는 장면 재실행이 필요하다. 과실을 다시 채우려면 프로그램을 재실행한다.

기본은 원래 30×30×19 cm 운반박스에 빨강/노랑 각각 2개씩 총 4개를 무작위로 적재한다. 열린 박스 위에 서로 겹치지 않는 위치·방향으로 과실을 생성하고, 중력과 접촉으로 떨어뜨려 자연스럽게 쌓는다. 규칙적인 격자·고정 층 배치는 기본에서 제거했다. 시작 후 최소 4초간 적재하고, 모든 과실의 충돌 형상이 박스 안에 들어와 0.5초간 안정된 뒤 출발한다. 적재가 끝나기 전에 누른 `g`/`t`는 대기했다가 실행한다. 적재가 12초 안에 안정되지 않으면 `TRANSPORT_LOADING_FAILED`로 멈춘다. 처음에는 운반박스를 가까이 보여주고 출발하면 전체 선별장 화면으로 돌아온다. 판정용 카메라 위치는 유지한다.

`--pepper-per-lane 1`은 운반 모드에서 총 4개, `2`는 총 8개다. 특정 레인에 한 개씩 배분하는 옵션은 아니다. 무작위 배치 기본 seed는 43이며 `--payload-seed 7`처럼 바꾸면 다른 위치·자세를 만든다. 같은 seed는 재현용이고 모든 배치의 배출 성공을 보장하지 않는다. 기존 박스·문·틸트 형상은 유지한다. 과실 전체 충돌 형상이 박스 전면을 벗어나고 모든 중심이 미끄럼틀 판정 범위에 들어와야 선별을 시작한다. 덜 배출되면 `TRANSPORT_DUMP_INCOMPLETE`로 멈춘다. 이전 격자 배치는 `--payload-layout ordered`로 과거 시험을 재현할 때만 사용한다.

기존 미끄럼틀에 미리 넣은 모드는 `--preloaded`다. 이 모드의 대기열 배치는 이번 운반박스 적재 변경과 별개다. `--auto-roi`는 자동 투영 구역을 쓰는 검증 옵션이며 일반 운용에서는 직접 지정한다. 저장된 아주 작은 ROI는 과실 자세가 바뀌면 몸통 대신 꼭지를 볼 수 있다. 투입 후 몸통을 포함하도록 직접 확인·재지정한다. 원래 사용자가 저장한 ROI는 자동으로 바꾸지 않는다.

단축 검증에는 `--stop-after-sorted N`을 사용한다. 선별·운반, HOME 복귀, 올바른 보관부 확인까지 N회 완료하면 종료한다. `--modbus` 모드에는 적용하지 않는다. 종료 보고서의 `validation_limit_reached=true`, `batch_complete=false`는 검증을 일찍 끝냈다는 뜻이며 전체 배치 완료가 아니다.

```bash
# 화면에서 무질서한 적재와 8개 배출을 보고, 1개 선별 후 종료
# 45도/X=0.695 m/5~45도 재기울임2회 시험 설정을 사용한다.
bash src/sorting_station/run_hcr_sim.sh \
  --config src/smartfarm_description/config/hcr3a_random8_validation.json \
  --pepper-per-lane 2 --payload-layout random --payload-seed 43 \
  --auto-start --stop-after-sorted 1

# 로봇팔 작업 없이 적재·배출만 확인. 이후 카메라 구역을 지정할 수도 있다.
bash src/sorting_station/run_hcr_sim.sh \
  --config src/smartfarm_description/config/hcr3a_random8_validation.json \
  --pepper-per-lane 2 --payload-seed 43 --unload-only
```

선택적인 틸트 재시도는 transport 설정에 `rock_cycles`, `rock_min_deg`, `rock_seconds`를 지정한 시험에서만 사용한다. 기본은 0회, 38도/X=0.715 m다. 위 8개 시험 설정은 2회를 사용하며 기본 4개 설정의 재검증이나 실물 제어 시퀀스로 표현하지 않는다. 무작위 8개 seed43은 전체 배출이 확인됐지만 seed42에서는 일부가 박스에 남았다. 검증 내용과 RGB/ROI 한계는 `VALIDATION.md`에 기록한다.

## 구성과 치수

좌표 원점은 로봇 설치판 중앙 바닥이다. +X에 투입 미끄럼틀, -X에 보관부가 있다. 사진의 왼쪽→오른쪽 순서와 대응한다. 내부 기하 레인 이름 A→D는 +Y→-Y다. 사용자 카메라 구역 이름 A→D는 별도로 실제 레인에 매핑된다. 레지스터 11/12 등은 사용자 구역 이름 기준이다. 보관부의 +Y 통로는 빨강, -Y 통로는 노랑이다. 좌우 표기는 보는 방향에 따라 달라지므로 색과 좌표로 구분한다.

| 부분 | 반영한 값 | 근거·가정 |
|---|---|---|
| 로봇 설치판 | 50 × 60 cm, 두께 4 cm | 사용자 노트 |
| 컨트롤러 외형 | 폭 22.3 × 깊이 47 × 높이 47 cm | 평면 노트 약 22 × 47 cm; 높이 47 cm는 명목값. 측정 확인 필요 |
| 설치판–컨트롤러 간격 | 7 cm | 사용자 노트 |
| 투입 미끄럼틀 | 폭 50.5 cm, 경사면 길이 50 cm, 상승 22.5 cm | 사용자 노트. 수평 길이 44.65 cm, 경사 약 26.74° |
| 4개 레인 | 유효 폭 각 12 cm, 폼보드 두께 5 mm | 4×12 + 5×0.5 = 50.5 cm |
| 투입 벽 | 바깥 10 cm, 내부 구분벽 5.5 cm | 사용자 노트 |
| 투입 하단 턱 | 높이 10 cm | 90 mm 과실의 이탈 방지를 위한 기능 근사값; 실물 턱 높이 아님 |
| 보관부 | 2개 경사 통로와 2개 보관함, 컨트롤러 위 | 사진 형태. 경사면 길이 26 cm, 낙차 13 cm, 보관함 길이 22 cm는 근사값 |
| 로봇 | 6 회전 관절, 주황/검정 링크, 고정 베이스 | HCR-3A 기능 근사 모델 |
| 그리퍼 | 2개 슬라이딩 손가락, 분홍 고마찰 패드 | JRT JEGH-3520P-A-Y003 사진을 참고한 근사 모델 |

원본 설정은 `src/smartfarm_description/config/hcr3a_station.json`이며 SI 단위다. 다른 설정 파일은 `--config /절대/경로.json`으로 적용한다. 과실 높이는 사용자 정정에 따라 **75 mm (0.075 m)**로 설정한다. 이전 105 mm는 실측 근거 없는 임시 가정이었다. 현재 높이는 원본 과실 메시의 전체 Z 범위를 75 mm로 축척한 값이며, 몸통/줄기 구분 측정은 아직 없다. 카메라 위치·시야각, 컨트롤러 높이, 보관부 치수, 마찰계수, 과실 지름 90 mm와 질량 9 g은 명목값이다.

폼보드에는 정적/동적 마찰 0.12/0.08, 패드에는 1.2/1.0을 지정했다. 과실은 중력으로 경사를 내려오며 벽·하단 턱·다른 과실과 충돌한다. 과실 형상은 `src/smartfarm_description/meshes/pepper`의 공통 Pepper USD를 사용하며 수확 제어·학습 모듈이나 캐시는 사용하지 않는다.

## 운반로봇과 투입 동작

기존 공통 자산 `src/smartfarm_description/urdf/transport_robot.portable.urdf`를 직접 Isaac USD로 변환해 사용한다. TurtleBot3 Waffle 차체·바퀴·센서와 기존 30×30×19 cm 박스, 지지대, 모터/기구 STL, 측면 배출문, 슬라이딩 윗뚜껑을 함께 불러온다. URDF·메시·`config/transport.json` 원본은 수정하거나 재생성하지 않는다. 변환 결과는 `outputs/sorting_station/hcr_sim/assets/transport/`에 둔다. 새로 만든 차량·넓힌 박스·4통로 배분 insert는 제거했다.

기본 실행은 미끄럼틀이 비어 있고 과실은 운반박스에 있다. `LOADING(최소4초+안정0.5초) → WAIT_START → APPROACH(6초) → OPEN_GATE(2.5초) → DOCK(2초) → TIP(5초,38도) → DUMP(6초) → SETTLE(3초 이상) → READY`를 거쳐 선별한다. 배출문이 벽에 닿지 않도록 입구에서 먼저 문을 열고 가까이 이동한다. 기존 박스의 전방 축 높이 25.5 cm와 미끄럼틀 상단 26.5 cm를 사용하고, 전방 축 X=71.5 cm로 맞춘다. 틸트는 원본 0–45도 범위, 배출문은 0–90도 범위다. 피니언과 두 슬라이딩 뚜껑은 원본 mimic 관계(이동량=0.06×회전각)를 명시적으로 반영한다.

원본 FK로 기존 8개 물리 링크의 PhysX kinematic target을 갱신한다. 차량 이동과 기존 관절 움직임은 지정한 경로/속도를 재현한다. 차량 바퀴 주행 제어·모터 토크/기어 동특성 검증은 아니다. 과실은 고정되지 않은 자유 rigid body로 실제 박스 접촉과 중력으로 배출한다. 과실 순간이동·부착·색 라벨에 따른 레인 재배치는 하지 않는다. 운반박스의 접촉 마찰 0.5/0.4는 별도 명목값이며 실측값이 아니다. 폼보드 미끄럼틀은 기존 0.12/0.08을 유지한다. 원래 박스 폭이 미끄럼틀보다 좁아 주로 가운데 두 레인으로 투입되며, A–D 네 구역의 지정·판정·우선순위 기능은 유지한다. 모든 과실의 충돌 형상이 박스 전면을 완전히 벗어나고 미끄럼틀 범위에 들어왔는지 확인한 뒤 선별을 허용하고, 덜 배출되면 TRANSPORT_DUMP_INCOMPLETE 오류를 낸다.

시작 전 `t`로 투입만 실행할 수도 있다. ROS 모드에서는 첫 배치의 BATCH_ACTIVE가 올라오면 같은 투입을 시작한다. 투입 중 카메라 상태는 WAIT로 전달해 빈 선별장으로 조기 완료하지 않게 한다. 실행 연결은 `hcr_sim/transport_asset.py`와 `transport.py`, 경로/시간 설정은 공통 HCR 설정의 transport 항목에 있다.

## 로봇 동작과 성공 기준

설치판·집기 위치·보관부 위치로부터 IK로 HOME, TRANSFER, A–D의 PICK/UP, RED/YELLOW와 각 CLEAR 경유 자세 14개를 생성한다. `teaching.json`의 관절각은 이 근사 모델의 라디안 값이다. 실제 Rodi 티칭값이나 HCR 관절 영점과 호환되는 데이터가 아니다.

한 번의 순서는 `APPROACH → DESCEND → CLOSE → LIFT → HOME → TRANSFER → STORAGE_CLEAR → PLACE_RED/YELLOW → OPEN → RETURN_CLEAR → TRANSFER → RETURN_HOME → VERIFY_BIN → DONE`이다. 하강·상승과 보관부 진입·이탈은 고정 방향의 직선 TCP 경로를 여러 IK 자세로 나누고, 나머지는 관절 경로로 연결한다. 덤핑 후 누운 과실은 근사 집게와 하단 턱의 간섭을 피하기 위해 root 높이에 2.5 cm 여유를 둔다. 보조 고정 전에 실제 TCP–과실 거리 4.5 cm 이내인지 계속 검사한다. 실제 관절 추종을 확인하고, 놓은 과실이 올바른 색 보관부 안에 들어갔을 때만 횟수를 증가시킨다. 한 번 처리 중에는 다른 명령을 선택하지 않는다. 보관부 판정은 평평한 보관함과 그 앞의 같은 색 경사 통로를 포함한다. 앞 과실 때문에 뒤 과실이 경사 통로에 머물 수도 있다. 다른 색 구획·바닥 낙하·보관부 밖은 실패다.

**파지는 보조 고정 조인트 방식이다.** 집게가 과실 가까이 도착하고 닫기 단계가 끝났을 때 과실을 손목에 고정하고, 열기 단계에서 고정을 제거한다. 선택된 과실과 근사 로봇 사이의 충돌은 접근부터 놓은 뒤 경유점으로 물러날 때까지 제외한다. 레인·보관함·다른 과실과의 충돌과 중력은 계속 적용한다. 이 방식은 색 판정·대기열·운반·놓기·완료 통신의 기능을 검증하기 위한 것이며, 마찰만으로 실제 그리퍼가 보유할 수 있는지 또는 집는 힘이 충분한지 입증하지 않는다. 링크 질량·관성·구동 한계도 실물 식별값이 아니다.

## 기존 ROS 2 관제 코드 연결

기본 `g` 시작은 ROS 없는 더미 관제 역할이다. ROS 2 연동에서는 기존 `SortBatch` action과 레지스터 맵을 그대로 사용한다. 실물 프로그램과 별도 카메라 상태·저널을 사용하고, 시뮬레이션 Modbus는 **127.0.0.1:1502**에만 접속한다.

터미널마다 ROS 환경과 이 작업공간의 `install/setup.bash`를 source한다. 패키지를 아직 빌드하지 않았다면:

```bash
colcon build --base-paths src/smartfarm_interfaces src/sorting_station/hcr_sorting \
  --packages-select smartfarm_interfaces hcr_sorting --symlink-install \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
```

터미널 1: 시뮬레이션용 PC 서버. 저장소 루트에서 실행한다.

```bash
ros2 run hcr_sorting sorter_node --ros-args \
  -p robot_id:=sorter_sim \
  -p modbus_host:=127.0.0.1 -p modbus_peer:=127.0.0.1 -p modbus_port:=1502 \
  -p camera_state:="$PWD/outputs/sorting_station/hcr_sim/state.json" \
  -p journal:="$PWD/outputs/sorting_station/hcr_sim/ros/journal.sqlite3" \
  -p runtime_state:="$PWD/outputs/sorting_station/hcr_sim/ros/runtime.json"
```

터미널 2: 모의 HCR 클라이언트를 포함한 환경. 카메라 창에서 A–D를 지정·저장한다.

```bash
bash src/sorting_station/run_hcr_sim.sh --modbus
```

터미널 3: 기존 더미 관제. READY 확인 후 안내에 따라 시작 goal을 전송한다.

```bash
ros2 run hcr_sorting dummy_control --robot-id sorter_sim
```

이 데스크탑의 검증 빌드는 `source outputs/sorting_station/hcr_sim/ros_install/setup.bash`로 바로 사용할 수 있다. 검증에는 별도 `ROS_DOMAIN_ID=67`을 사용했다. ROS_DOMAIN_ID와 RMW 설정은 세 터미널에서 일치시킨다. `--modbus`에서는 카메라 창의 `g` 시작 대신 관제 goal을 사용한다. GPU 렌더와 독립된 통신 스레드가 상태를 반복 전송한다. 작업 ACK→BUSY→DONE→READY는 기존 계약을 따른다. 배치 완료·취소·결과 횟수는 PC의 기존 supervisor가 관리한다.

| 명령 | A | B | C | D |
|---|---:|---:|---:|---:|
| 빨강 | 11 | 21 | 31 | 41 |
| 노랑 | 12 | 22 | 32 | 42 |

PC 레지스터 0–4: COMMAND, JOB_ID, REQUEST, BATCH_ACTIVE, HEARTBEAT. 모의 로봇 레지스터 100–103: STATE, ACK_JOB_ID, DONE_JOB_ID, ERROR_CODE. STATE는 0 미준비, 1 READY, 2 BUSY, 3 DONE, 4 ERROR다. 1회 완료는 복귀와 올바른 보관부 도착을 확인한 뒤 알린다.

## 생성 파일과 원본 자산

생성물은 모두 `outputs/sorting_station/hcr_sim`에 둔다.

- `hcr_station.usda`: 초기화된 장면. 전체 실행은 Python 런처를 사용한다. USD만 열면 색 판정·순차 제어가 실행되지는 않는다.
- `overview.png`, `camera_preview.png`, `camera_rgb.png`: 전체 환경과 판정 영상.
- `zones.json`: 사용자가 저장한 카메라 구역.
- `teaching.json`: 근사 모델에서 생성한 자세.
- `runtime.json`, `report.json`: 상태, 색별 완료 횟수, 오류, 개별 과실의 최종 위치와 이벤트.
- `state.json`: 기존 PC supervisor가 읽는 시뮬레이션 카메라 상태.
- `assets/`: URDF 변환 USD와 캐시. `source_cad/`: 확보한 제조사 CAD 참고 원본.
- `configuration.json`, `metadata.json`: 실행 설정과 소스 SHA256, 물리 간격, 장치 기록.

공통 자산 설정·생성기는 `src/smartfarm_description/config/hcr3a_station.json`, `scripts/generate_hcr3a.py`, `scripts/hcr3a_environment.py`, `urdf/hcr3a_functional.urdf`다. 실행·비전·순차 제어는 `src/sorting_station/hcr_sim`에 있다. 기존 OMX와 SO-ARM101 자산은 교체하지 않는다.

## 제조사 자료와 모델의 범위

[한화로보틱스 공식 CAD 다운로드](https://hanwharobotics.com/en/newsroom/download_view?menuSeq=85&bbsSeq=133)에서 HCR-3A와 A-series 컨트롤러 STEP ZIP을 확보했다. 이 CAD는 참고 원본으로 보관한다. 이번 움직이는 모델은 검증된 실물 관절 축·영점·관성 자료가 갖춰진 URDF가 아니므로 별도 기능 근사 모델을 사용한다.

다른 PC에서 참고 원본을 다시 받을 때는 `python3 src/smartfarm_description/scripts/fetch_hcr3a_cad.py`를 실행한다. 기능 시뮬레이션 자체는 STEP 파일 없이도 생성된다.

[제조사 HCR 카탈로그](https://hanwharobotics.com/hanwharobotics/file/240827/54fb583a240f4805996e25d868738599.pdf)의 HCR-3A는 6축, 도달거리 630 mm, 가반하중 3 kg이다. 시뮬레이션 링크의 길이·질량·동특성이 이 사양과 일치한다고 주장하지 않는다.

[JRT 제조사 전동 그리퍼 카탈로그](https://www.hannovermesse.de/apollo/hannover_messe_2026/obs/Binary/A1516375/JRT_ELECTRIC%20GRIPPER_ENG.pdf)의 기본 JEGH-3520P 몸체 치수 100 × 40 × 114 mm를 참고했다. 사진의 Y003 맞춤 손가락과 패드 외형은 근사값이다.

## 검증

```bash
PYTHONPATH=src/sorting_station /usr/bin/python3 -m unittest discover -s src/sorting_station/hcr_sim/tests -v
```

치수 정합성, 전체 티칭 위치의 IK 도달성, URDF 관절과 FK의 일치, 수확 런타임 의존성 분리를 검사한다. 실제 GPU 기능 검증 결과는 이 디렉터리의 `VALIDATION.md`에 기록한다.

RGB/물리와 실제 ROS goal을 함께 검사하려면 별도 ROS 도메인에서 `tests/ros_goal_probe.py`를 실행하고, 다른 터미널에서 `--headless --modbus --auto-roi --pepper-per-lane 1 --steps 30000`으로 환경을 실행한다. Probe의 카메라 타임아웃 3초는 렌더 부하를 고려한 시뮬레이션 검증 프로파일이다. 기존 실물 기본값 1초는 바꾸지 않는다.

```bash
# 터미널 1: /opt/ros/jazzy/setup.bash 및 ros_install/setup.bash source 후
export ROS_DOMAIN_ID=67 ROS_LOCALHOST_ONLY=1
/usr/bin/python3 src/sorting_station/hcr_sim/tests/ros_goal_probe.py

# 터미널 2: 서버의 WAITING 안내 이후
bash src/sorting_station/run_hcr_sim.sh --headless --modbus --auto-roi \
  --pepper-per-lane 1 --steps 30000
```

ROS 배치 결과는 관제 action Result가 기준이다. 로봇 루프의 `SCANNING`은 다음 명령을 기다리는 상태이며, 관제가 보내는 배치 SUCCESS와 구분한다. ROS 운용 중에는 배치를 시작하기 전에 ROI를 완성한다.
