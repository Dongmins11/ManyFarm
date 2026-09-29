# v0.5.2 — 수확 범위 2cm 허용 + 관측 좌표 보정

## 바뀐 동작

- 기본 큐브의 각 면에서 바깥으로 **20mm까지 포함**합니다. 20mm 초과는 보류합니다.
- 축별 허용 오차입니다. 큐브에서의 유클리드 거리 20mm를 사용하는 규칙은 아닙니다.
- 좌우 3cm는 새 박스를 배치할 때 사용하는 기준으로 유지합니다. 포함 여부는 기본 큐브 전체와 바깥 2cm로 판단합니다.
- 기본 큐브/수확 목표 위치는 유지합니다. 주행 경로 끝 제한과 Nav2 도착 허용 오차는 변경하지 않습니다.
- 동일 ID를 다시 관측하면 모든 관측의 map 좌표를 축별 중앙값으로 보정합니다.
  한 번이면 그 측정값, 두 번이면 두 값의 중간, 세 번 이상이면 축별 중앙값입니다.
- 보정된 좌표로 기존 윈도우 포함 여부를 다시 검사합니다. 범위를 벗어난 열매는 다른 윈도우에 배정하거나 보류합니다.
  보류했던 열매가 범위 안으로 보정되면 작업에 포함합니다.
- 기존 윈도우의 ID·위치·크기는 유지합니다. 포함 열매가 없어지면 전송 목록에서 제외하고 ID는 재사용하지 않습니다.
  이후 열매가 다시 들어오면 같은 윈도우를 사용할 수 있습니다.

현재 설정 기준:

| 항목 | 기본 큐브 | 허용 오차 포함 |
|---|---:|---:|
| 좌우 폭 | 35cm | 39cm |
| 높이 | 45cm | 49cm |
| 앞뒤 깊이 | 10cm | 14cm |
| 지면 기준 높이 | 60.3–105.3cm | 58.3–107.3cm |

이것은 예찰에서 수확 후보를 선정하는 기준입니다. 실제 로봇팔 가동 범위가 늘어난다는 뜻은 아니며,
기존과 같이 로봇팔 이동·IK 검증은 수행하지 않습니다.

## 화면 표시

- 보라색: 기본 수확 큐브.
- 하늘색: 2cm 허용 범위를 포함한 큐브.
- 영상 하단 `Purple: nominal | Cyan: allowance 20mm` 표시.
- RViz에서도 같은 두 범위를 표시합니다.

## 왜 다섯 번 촬영하는가

GeoJSON 점마다 촬영하는 방식이 아닙니다.
GeoJSON에서 노드 1–8로 정한 **7m 구간**을 카메라의 유효 관측 폭 **약 1.91m**로 덮습니다.
관측 영역이 최소 15% 겹치도록 필요한 개수를 계산하고 양 끝을 맞춰 균등 배치하면 5곳입니다.

```text
촬영 수 = 1 + ceil((주행 구간 - 관측 폭) / (관측 폭 × (1 - 최소 겹침 비율)))
       = 1 + ceil((7 - 1.91) / (1.91 × 0.85)) = 5
```

현재 시작점부터 촬영 거리: 약 0.955, 2.228, 3.500, 4.772, 6.045m.
인접 촬영점 간격은 약 1.272m이므로 실제 겹침은 약 33.4%입니다.
15%는 최소 요구값이고, 정수 개수와 양 끝 정렬 때문에 실제 겹침이 더 큽니다.
시작 경로점과 마지막 경로점에도 이동하지만 추가 촬영점으로 세지는 않습니다.
이번 패치는 촬영 지점 계산, 기존 크롭·패딩, YOLO 모델을 변경하지 않습니다.

## 적용 순서

v0.5.1 도착 판정 패치가 적용된 프로젝트를 전제로 합니다.
예찰이 완료된 상태에서 **예찰 서버만 Ctrl+C로 종료**합니다. Isaac + Nav2는 유지해도 됩니다.

robot_venv 터미널:

```bash
unzip -o ~/Downloads/farm_scout_range_fusion_v0.5.2.zip -d ~/robotarm/
cd ~/robotarm/farm_project
source scripts/env.sh sim
python scripts/apply_scout_range_fix.py &&
(cd robot/ros_ws && colcon build --packages-select scout_robot farm_vision)
```

적용 스크립트가 각 section의 harvest에 다음 두 값만 추가/변경합니다.
다른 설정은 보존하며 원본은 `runs/config_backups/`에 백업합니다.

```json
{
  "range_tolerance_m": 0.02,
  "membership_margin_m": 0.0
}
```

기존 `side_margin_m: 0.03`은 박스 배치 기준으로 유지합니다.
기본 예찰 launch는 프로젝트 소스의 `scout_survey.json`을 직접 읽으므로 이 변경에 sim workspace 재빌드는 필요 없습니다.
별도 survey_config를 사용한다면 `python scripts/apply_scout_range_fix.py --config /사용중인/scout_survey.json`으로 해당 파일에 적용합니다.

예찰 서버 재실행:

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout_survey.launch.py mode:=sim \
  project_root:="$PWD" vision_python:="$(cat runs/vision_python.txt)" device:=0
```

별도 robot_venv 터미널에서 새 예찰 요청:

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
python control/scripts/send_scout_area.py --section BED_01
```

## 기록과 평가

`survey.json`의 열매별 필드:

- `position_map_m`: 보정된 현재 대표 좌표. ID 연결·수확 판정·평가에 사용합니다.
- `position_first_map_m`: 최초 측정 좌표.
- `position_latest_map_m`: 가장 최근 측정 좌표.
- `position_samples`: 각 관측의 좌표·시각·신뢰도.
- `position_span_m`: 관측값의 축별 최댓값–최솟값. 통계적 신뢰구간은 아닙니다.

윈도우의 `corners_map_m`은 기본 큐브, `acceptance_corners_map_m`은 판정 범위입니다.
관제 인터페이스는 기존처럼 완료 시 윈도우별 작업과 예상 수량을 전달합니다.

임시 GT 비교 도구도 설정에 따른 높이 허용 범위를 반영합니다.
GT 매칭 거리 기본값 3cm와 이번 수확 범위 허용값 2cm는 서로 다른 값이며, GT 매칭 거리는 변경하지 않았습니다.
범위 변경으로 평가 대상 개수가 달라질 수 있으므로 이전 점수와 비교할 때 기준을 함께 확인해야 합니다.
GT 중심 좌표와 검출 표면점의 차이 등 기존 평가 한계는 남아 있습니다.

좌표 중앙값은 같은 ID로 연결된 측정값을 모으는 처리입니다.
카메라 보정·AMCL의 공통 편향을 제거하거나, 가림에 의한 ID 분리·두 열매 오연결을 해결하는 기능은 아닙니다.
정답 USD 좌표는 보정이나 수확 판정에 사용하지 않습니다.

## 검증 결과

- 경계/좌표/재배정 회귀 검사 12개, 기존 예찰 검사 9개, 도착 검사 10개 통과.
- 별도 작업 프로세스·실제 공유메모리를 통한 캡처/저장/종료 검사 통과. YOLO 추론만 가짜 모델로 대체했습니다.
- 합성 영상에서 기본 큐브·허용 큐브 표시를 확인했습니다.
- 사용자가 제공한 세션 `56571de5ad6f`의 **저장된 첫 좌표만** 관측 순서대로 재계산한 결과:
  13개 ID 포함, 보류 0개, 윈도우 9개. F0001/F0003/F0005 포함 확인.
  이는 원본 영상 재추론이나 다회 좌표 보정 전체 재현이 아닙니다. 실제 재실행의 작업 수를 보장하지 않습니다.
- ROS Jazzy/Isaac Sim 환경이 없어 실제 colcon 빌드·주행·실제 모델 추론은 여기서 실행하지 못했습니다.
