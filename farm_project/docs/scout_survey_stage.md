# v0.5 — 한 베드 B 예찰 / ID / 수확 윈도우 / 관제 전달

## 동작

관제 테스트 클라이언트가 `/scout_01/scout_area` 요청 → 시작 경로점 접근 → 카메라 기하로 관측점 계산 → 각 관측점 이동·정지 → 새 RGB-D로 YOLO 검출 → 촬영 시각의 map 좌표 변환 → ID 비교 → 기존 윈도우 유지·새 윈도우 추가 → 경로 끝 도착 → 베드의 작업 목록을 한 번 전송.

B 원칙대로 **주행 중 프레임을 계속 작업에 등록하지 않습니다.** 정지 후 새 촬영 시각의 영상으로 확정합니다. 현재 7m 경로, 카메라와 15% 관측 겹침에서 5곳이 계산됩니다. 현재 화면은 관측을 마칠 때 갱신되고 이동 중에는 직전 관측 화면이 유지됩니다.

- 열매의 사각형 + 세션 내 ID: 노란색 테두리.
- 수확 윈도우: 보라색 3D 박스 투영.
- 하나의 윈도우 = 하나의 HarvestTask. 과실 수와 task 수는 다릅니다.
- 원본/크롭/ID·윈도우 이미지, 깊이, 촬영 시각, 지도 좌표, 보류 사유를 저장합니다.
- 실제 수확로봇이나 로봇팔에는 이동 명령을 보내지 않습니다.

## 1. 패치 적용·빌드 (robot_venv)

기존 단독 비전 프로그램과 `scout_route.launch.py`는 종료합니다. **Isaac + Nav2 bringup은 유지**합니다. 이 서버와 기존 경로 실행기를 동시에 주행시키지 마세요.

```bash
unzip -o ~/Downloads/farm_scout_survey_v0.5.zip -d ~/robotarm/
cd ~/robotarm/farm_project
source scripts/env.sh sim
cd robot/ros_ws
colcon build --packages-select scout_robot farm_bringup
cd ../..
source scripts/env.sh sim
```

이 패치는 기존 지도, USD, Nav2 파라미터, 비전 설정 JSON을 덮어쓰지 않습니다. v0.4.2 크롭 보정까지 적용된 프로젝트를 전제로 합니다. `farm_interfaces`는 기존에 빌드한 형식을 그대로 사용합니다.

## 2. 비전 Python 경로 기록

**방금 YOLO가 정상 동작했던 가상환경의 터미널에서** 실행합니다. 특정 환경 이름을 가정하지 않습니다.

```bash
cd ~/robotarm/farm_project
mkdir -p runs
python -c 'import sys; print(sys.executable)' > runs/vision_python.txt
```

서버가 이 Python으로 YOLO 작업 프로세스를 별도로 실행합니다. ROS Python에 torch를 새로 설치할 필요가 없습니다.

## 3. 예찰 서버 실행 (robot_venv)

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout_survey.launch.py mode:=sim \
  project_root:="$PWD" \
  vision_python:="$(cat runs/vision_python.txt)" \
  device:=0
```

서버를 켜는 것만으로는 이동하지 않습니다. 창을 끄려면 `headless:=true`를 추가할 수 있습니다. 기존 Isaac + Nav2 bringup이 종료된 상태라면 먼저 기존에 정상 동작한 bringup 명령으로 실행합니다.

## 4. 임시 관제에서 시작 (다른 robot_venv 터미널)

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
python control/scripts/send_scout_area.py --section BED_01
```

`BED_01`은 지금 시험하는 경로의 **임시 관제 이름**입니다. 정식 `SEC_A01`로 확정했다는 뜻이 아닙니다. 현재 USD 내부 과실 폴더 이름은 `/World/Vegetation/Bed_02`입니다.

현재 시험 범위는 **경로 노드 1~8의 7m 구간과 카메라를 향하는 베드 한쪽 면**입니다. USD 베드 양쪽 전체를 관측했다는 뜻이 아닙니다. 섹션 경계·반대편 경로를 확장하려면 설정과 GeoJSON을 함께 확정해야 합니다.

시작 후 모델 준비가 끝나면 이동합니다. 첫 실행은 모델 준비 시간이 걸립니다. 다음을 확인합니다.

1. 관측점에 도착하면 멈추고 ID·윈도우 화면이 갱신되는가.
2. 다음 관측에서 겹쳐 보이는 열매가 기존 ID를 유지하는가.
3. 경로 끝까지 이동한 뒤 관제 터미널에 `SEGMENT_COMPLETE`와 전체 task 목록이 한 번 나오는가.
4. 마지막 `SUCCESS`의 `harvest_task_count`가 윈도우 수와 같은가.

테스트 클라이언트에서 Ctrl+C를 누르면 자신이 요청한 예찰을 취소합니다. 서버도 자신이 보낸 Nav2 목표만 취소하고 종료 여부를 확인합니다. 실패/취소된 베드의 중간 작업 목록은 완료 배치로 전송하지 않습니다. 수신 내역은 `runs/control/*.jsonl`에 저장합니다.

PDF 규격의 `HarvestTask[]`는 **feedback**에 있으므로, 베드 완료 시 이 필드로 전달합니다. `result`에는 완료 섹션과 합계를 담습니다. `segment_id=BED_01_BATCH`는 한 베드를 한 배치로 보는 임시 대응입니다. 정식 segment 정의는 추후 교체해야 합니다. 네트워크 재전송까지 포함한 exactly-once/관제 ACK 보장은 별도 구현 대상입니다.

## 5. 저장 결과·RViz

```text
runs/scout_survey/<session>/
  survey.json                     전체 ID/XYZ/윈도우/수확 목표/보류/처리 시간
  vision_worker.log               추론 프로세스 로그
  BED_01/observation_001/
    rgb.png                       원본
    input.png                     크롭·패딩 YOLO 입력
    annotated.png                 원본 위 ID·윈도우 표시
    depth.npy                     같은 촬영 시각의 깊이
    observation.json              카메라/시간/검출/투영 정보
    map_detections.json            지도 변환 결과와 해당 관측의 ID
```

과실 좌표는 **깊이 영상에서 얻은 보이는 표면점**이며, 열매 중심/절단점/파지점이 아닙니다. 좌표와 ID는 JSON에 있고, 현재 PDF 메시지는 목표 위치와 예상 수량만 지원하므로 해당 필드만 관제에 보냅니다. 과실별 XYZ까지 관제 메시지로 전달하려면 인터페이스 합의가 추가로 필요합니다.

RViz에서 Add → MarkerArray → `/scout_01/survey_markers`를 선택하면 지도상 과실 ID와 보라색 윈도우를 볼 수 있습니다. 늦게 구독해도 볼 수 있도록 마지막 결과를 주기적으로 다시 발행합니다.

## 6. 임시 성능 비교: Isaac 배치값 vs 검출 결과

정답은 아래 **별도 도구에서만** 읽습니다. 관측점 생성/ID/윈도우 코드에서는 USD 정답을 사용하지 않습니다.

### 정답 파일 생성

현재 디스크에 저장된 농장 씬에서 실제 과실 메시의 월드 bounding box를 읽습니다. 메시 참조가 없으면 실패하며, prim 원점을 임의로 정답 중심처럼 대신 쓰지 않습니다.

```bash
cd ~/robotarm/farm_project
/home/ysy/isaac/env_isaaclab/bin/python sim/tools/export_scout_truth.py \
  --scene "$PWD/sim/assets/envs/output/farm_with_plants_v5.usd" \
  --output "$PWD/runs/scout_truth.json"
```

Isaac에서 실행 중에 과실을 옮겼고 저장하지 않았다면 위 파일과 장면이 다릅니다. 이 경우 Isaac Script Editor에서 아래처럼 **현재 stage**를 내보낼 수 있습니다. 원본 USD를 변경하지 않습니다.

```python
import runpy
import omni.usd
module = runpy.run_path('/home/ysy/robotarm/farm_project/sim/tools/export_scout_truth.py')
module['export'](omni.usd.get_context().get_stage(), '/home/ysy/robotarm/farm_project/runs/scout_truth.json')
```

### 가장 최근 예찰 결과와 비교 (NumPy가 있는 Python)

```bash
cd ~/robotarm/farm_project
python sim/tools/compare_scout_truth.py \
  --survey latest --truth runs/scout_truth.json
```

결과는 해당 세션의 `truth_comparison.json`에 저장됩니다. `--survey runs/scout_survey/<session>/survey.json`으로 세션을 지정할 수도 있습니다.

확인 항목:

- 이번 경로·한쪽 면·작업 높이에 배치된 Red/Yellow 수, 검출 ID 수, 정답과 대응된 수.
- 미검출 과실의 USD 경로, 대응되지 않은 검출 ID, 중복 ID 의심 목록.
- 윈도우별 예상 과실 수와 실제 대응한 과실 수, 같은 정답의 작업 중복 여부.
- 색상 일치 여부와 표면점→정답 AABB 거리, 표면점→박스 중심 거리.
- 예찰 전체 소요 시간 및 관측별 전처리·추론·깊이 연산 시간은 `survey.json`에 기록합니다.

평가 해석:

- 모델에 Green 클래스가 없으므로 Green은 누락률 분모에서 제외합니다.
- 반대편 면/경로 밖/작업 높이 밖 정답은 제외 사유를 기록합니다. 크롭 여유 영역에서 검출됐지만 작업 높이 밖인 ID도 별도 표시합니다.
- 가려진 과실도 배치 개수에 포함되므로 이 지표는 **예찰의 배치 과실 발견율**입니다. 화면에 실제 보이는 과실만의 YOLO 재현율이 아닙니다.
- 표면점과 메시 중심은 다르므로 중심 거리를 위치추정 RMSE라고 부르지 않습니다. 기본 매칭은 AABB까지 거리 3cm 이내, 일대일 최대 대응 수 기준입니다. 인접 과실/겹친 AABB는 오매칭될 수 있습니다.
- `T_map_world`는 현재 농장/지도 좌표가 일치하는 조건의 단위행렬입니다. 지도 원점/회전이 바뀌면 별도로 보정해야 합니다. 예측 좌표에 맞춰 정답을 움직이지 않습니다.
- 중간에 실패한 예찰도 비교할 수 있지만 `mission_status`를 확인해야 합니다.

## 설정과 아직 확정되지 않은 값

시뮬레이션 설정: `sim/ros_ws/src/farm_sim_config/config/scout_survey.json`

| 설정 | 현재 값 / 의미 |
|---|---|
| 정지 안정화 | odom 속도가 기준 이하로 시뮬레이션 시간 0.8초 유지 |
| ID 비교 | B 기본 로직: 3차원 거리 6.5cm, 프레임 내 일대일, 최초 좌표 유지 |
| 관측 겹침 | 최소 15% |
| 윈도우 폭/안전 여유 | 35cm / 좌우 각 3cm |
| 윈도우 높이 | 60.3~105.3cm |
| 윈도우 깊이 폭 | 10cm |
| 팔 XY 장착 | 제공 모델 `arm_1_mount`의 전방 19cm·오른쪽 18.5cm를 시험값으로 사용 |
| 팔 작업 오프셋 | 오른쪽 25cm, 시험 가정 |
| 수확 방향 | 예찰과 반대 방향: 오른쪽 팔이 베드를 보도록 하는 시험 가정 |

**수확 주행선과 팔 작업 오프셋은 확정 전입니다.** 여기서 계산한 목표는 기하 시험값이며 충돌 없는 경로/IK 가능 영역을 보장하지 않습니다. 기존 B의 상자 포함 조건을 이식한 것으로, 실제 수확로봇 담당자와 값 확인 후 사용해야 합니다.

B 기본 거리 매칭은 가까운 과실의 ID 교환, 표면점 변화, AMCL 보정으로 인한 중복을 완전히 해결하지 않습니다. 테스트 비교 결과로 오차를 확인하고 개선합니다. 기존 카메라 연결부의 자세 메타데이터는 바퀴 odom + 고정 장착 변환이며, 실제 차체 roll/pitch 흔들림 반영은 별도 보완 대상입니다.

## 코드 위치

- `scout_robot/survey_server.py`: 액션·Nav2·정지 확인·촬영 시각 TF·베드 배치 전송.
- `scout_robot/survey_core.py`: 관측점 기하, ID 비교, 좌표 변환, 지도 윈도우.
- `scout_robot/b_planner.py`: 제공 B planner의 기존 윈도우 보존/앵커 로직. 경로 방향을 로컬 축으로 변환해 재사용.
- `farm_vision/survey_worker.py`: 별도 YOLO 환경의 공유메모리·깊이 역투영·이미지 저장.
- `control/scripts/send_scout_area.py`: 임시 관제 요청·수신 코드.
- `sim/tools/export_scout_truth.py`, `compare_scout_truth.py`: 임시 정답 평가만 담당.

공통 코드에는 USD 정답 참조가 없습니다. 실물 모드는 명시적인 `survey_config`와 동일한 RGB-D 공유메모리/ROS 입력이 필요합니다. 실물 장치 연결은 이번에 작성하지 않았습니다.

## 검증 범위

오프라인 회귀 테스트 9개 통과: 관측점 끝단/겹침, ID 일대일 대응과 재사용, 기존 윈도우 고정, 높이/깊이 보류, 팔 오프셋 역산, 깊이 누락, 크롭 여유/역변환, 회전 좌표 변환, 정답 대응/윈도우 수.
추가로 실제 프로세스 간 공유메모리→요청/응답→이미지 저장→종료를 모의 검출기로 확인했고, USD 메시 정답 내보내기를 작은 시험 장면으로 확인했습니다.

**현재 실행 환경에 ROS 2/Nav2/Isaac/PyTorch가 없어 실제 로봇 주행·액션 연동·모델 추론은 통합 실행 검증하지 못했습니다.** 사용자 환경에서 첫 한 베드 시험으로 확인해야 합니다.
