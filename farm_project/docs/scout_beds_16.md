# 예찰 구역 16개 — v0.5.7

기존 물리 재배 베드 8개의 양쪽 면을 각각 예찰하도록 BED_01~BED_16을 구성했습니다. 씬의 베드 개수는 8개입니다. 관제가 요청하는 BED 번호는 이제 **베드 한쪽 면**을 뜻합니다.

![16개 예찰 경로](scout_beds_16.png)

## 번호와 방향

그림은 map 좌표 +Y가 위, +X가 오른쪽입니다. 위쪽 줄을 왼쪽부터, 이후 아래쪽 줄을 왼쪽부터 배정했습니다. 노드 ID와 중간 노드는 유지하고, 각 경로 양 끝을 50cm씩 확장했습니다.

| 물리 베드 위치 | USD 베드 | 왼쪽 면, 아래로 주행 (-Y) | 오른쪽 면, 위로 주행 (+Y) |
|---|---|---|---|
| 위쪽 1열, 중심 (-5, 6) | Bed_02 | BED_01 | BED_02 |
| 위쪽 2열, 중심 (-2, 6) | Bed_04 | BED_03 | BED_04 |
| 위쪽 3열, 중심 (2, 6) | Bed_06 | BED_05 | BED_06 |
| 위쪽 4열, 중심 (5, 6) | Bed_08 | BED_07 | BED_08 |
| 아래쪽 1열, 중심 (-5, -6) | Bed_01 | BED_09 | BED_10 |
| 아래쪽 2열, 중심 (-2, -6) | Bed_03 | BED_11 | BED_12 |
| 아래쪽 3열, 중심 (2, -6) | Bed_05 | BED_13 | BED_14 |
| 아래쪽 4열, 중심 (5, -6) | Bed_07 | BED_15 | BED_16 |

홀수 구역은 카메라가 +X를, 짝수 구역은 -X를 바라봅니다. 둘 다 **로봇 진행 방향의 왼쪽**입니다. 이 방향 조건은 예찰 구간에 적용됩니다. 구역 사이를 이동하거나 회전할 때는 Nav2가 주행 방향을 정하며 촬영하지 않습니다.

## 경로 길이 수정

- 제공된 `farm_framechanged.usdc`의 `Bed_Edge` 외곽 길이: **8.00m**. 내부 GrowBed 길이: 7.88m.
- 기존 예찰 경로는 7m여서 외곽 앞뒤가 각각 0.50m 짧았습니다.
- 16개 경로 모두 **8m**로 변경했습니다. 베드 외곽과 동일한 길이이며 별도 초과 여유는 없습니다.
- 위쪽 BED_01~08: Y=2.0~10.0m. 홀수는 10→2, 짝수는 2→10.
- 아래쪽 BED_09~16: Y=-10.0~-2.0m. 홀수는 -2→-10, 짝수는 -10→-2.
- 경로 X, 좌측 카메라 방향, 128개 노드 ID 및 112개 연결 ID는 유지했습니다.
- 각 경로 첫/끝 노드만 변경했습니다. 연결선 좌표와 cost도 실제 거리로 동기화했습니다. 첫/끝 연결 길이는 1.5m, 중간 연결은 1m입니다.
- 기존 auto 설정이면 촬영 지점이 새 8m 범위를 덮도록 자동 재계산됩니다. 현재 카메라 조건에서는 여전히 BED당 5회입니다. 수동 segment 설정은 자동 재배치되지 않습니다.
- `finish_at=last_segment`이면 로봇은 마지막 촬영 위치에서 예찰을 마칩니다. 경로 끝 좌표까지 반드시 주행하는 설정은 아니지만 설계된 카메라 관측 범위는 경로 끝까지 포함합니다.

## 적용

예찰 요청을 취소하고 기존 예찰 서버와 bringup을 종료한 뒤 적용합니다.

```bash
cd ~/main/farm_project
mkdir -p runs/config_backups
cp sim/ros_ws/src/farm_sim_config/maps/graph.geojson "runs/config_backups/graph_before_8m_$(date +%Y%m%d_%H%M%S).geojson"
unzip -o ~/Downloads/farm_scout_routes_8m_v0.5.7.zip -d ~/main/
source scripts/env.sh sim
(cd sim/ros_ws && colcon build --symlink-install --packages-select farm_sim_config)
```

별도의 config 변경이나 apply_scout_beds_16.py 재실행은 필요 없습니다. 기존 16개 구역 설정이 있는 환경용 패치입니다.

터미널 1 — bringup 재실행:

```bash
cd ~/main/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout.launch.py mode:=sim navigation:=true rviz:=true \
  isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python \
  assets_root:="$PWD/sim/assets"
```

터미널 2 — 예찰 서버 재실행:

```bash
cd ~/main/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout_survey.launch.py mode:=sim \
  project_root:="$PWD" vision_python:="$(cat runs/vision_python.txt)" device:=0
```

터미널 3 — 전체 요청:

```bash
cd ~/main/farm_project
source scripts/env.sh sim
python control/scripts/send_scout_area.py --all
```

## 확인 범위와 남은 확인

- 오프라인 경로/촬영/방향/설정 호환 검사 5개 통과.
- 16개 경로의 끝점, 연결선 좌표·cost, 베드 외곽 일치 확인.
- 제공된 점유 맵에서 16개 경로 모두 자유 공간이며, 로봇 반경 0.12m 기준 같은 연결된 통로에 있습니다. 픽셀 오차를 뺀 최소 장애물 간격은 약 0.779m입니다.
- 실제 ROS/Isaac Sim 주행은 이 환경에서 실행하지 않았습니다. 재시험으로 끝단 열매 검출·윈도우 배정을 확인해야 합니다.
- 이번 변경은 경로 길이 조정입니다. 작업 깊이·높이 범위 밖 판정, 좌표 오차, 잎 가림은 별도 문제입니다. 베드 길이와 일치시켜도 수확 정차점이 외곽보다 더 나가야 하는 열매는 추가 정차 계획 검토가 필요합니다.
