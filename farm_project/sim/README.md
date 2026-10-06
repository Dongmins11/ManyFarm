# 시뮬레이션 설정과 실행

현재 실행 절차는 [실물·시뮬 실행 가이드](../docs/RUN_GUIDE_20261002.md)를 따른다. 과거 문서의 scout launch에서 Isaac/RViz를 함께 켜는 명령은 더 이상 사용하지 않는다.

## 실행 단위

| 단위 | 진입점 |
|---|---|
| Isaac 환경 | farm_sim_runtime isaac.launch.py |
| 예찰 장치·Nav2·서버 | farm_sim_runtime scout.launch.py |
| RViz 모니터링 | farm_bringup rviz.launch.py |
| 위 구성 한 번에 실행 | farm_sim_runtime all.launch.py |

현재 구현 범위는 예찰 한 대이며 수확·운송·정식 관제 프로세스는 포함하지 않는다. 로봇 launch에서 rviz=true/start_isaac=true를 사용하면 새 실행 명령 안내 오류를 낸다.

## 설정 원본

- 환경 선택: sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml
- 경로·관측점·station: 같은 config의 task.yaml 및 maps/scout_harvest.geojson
- 장치: config/scout.json
- 비전: config/scout_vision.json. 모델 파일은 기존 공통 robot/models/scout 자산 사용
- Nav2: config/nav2_scout.yaml. 실물과 같은 follow_path/RPP 및 제어 튜닝
- 화면: config/scout.rviz
- 합성 데이터: sim/config/scout_dataset.json

원본 경로·station 수정 후 `python sim/tools/rebuild_route_data.py`와 `python sim/tools/validate_route_data.py`를 실행한다. 생성된 station_spawn.json과 AMCL 초기 pose는 같은 station을 사용한다.

예찰·비전·합성 데이터 출력은 sim/runs 안에 둔다. 기존 공용 시험 클라이언트의 runs/control 로그는 이번 분리에서 변경하지 않았다. 단독 비전은 `python sim/tools/run_scout_vision.py`로 실행한다.

변경 이력은 docs/CHANGELOG.md, 경로·station·FollowPath 적용값은 각 날짜별 문서를 참고한다. 최신 실행 명령은 상단 공통 실행 가이드가 우선한다.


## robot_venv에 비전이 설치된 경우

robot_venv를 활성화한 상태에서 vision_python 인자를 생략하면 해당 venv의 Python을 사용한다. FARM_VISION_PYTHON이 설정돼 있으면 그 값이 우선하므로 자동 선택을 원하면 해당 환경변수를 해제한다. isaac_python은 별도로 지정한다.

```bash
ros2 launch farm_sim_runtime all.launch.py \
  project_root:="$PWD" \
  isaac_python:="$HOME/venv/env_isaaclab/bin/python" \
  device:=0
```

셸 줄 연결용 역슬래시 뒤에는 공백을 넣지 않는다. 기존 공통 실행 안내의 vision_python 지정은 시뮬 all/scout에서는 이제 선택 사항이다.
