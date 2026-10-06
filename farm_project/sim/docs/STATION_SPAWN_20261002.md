# Isaac 시작 station 자동 배치

후속 launch 분리 반영: 현재 Isaac 시작은 `farm_sim_runtime isaac.launch.py`, 전체 시작은 `farm_sim_runtime all.launch.py`다. 아래의 과거 통합 실행 설명 대신 `docs/RUN_GUIDE_20261002.md`를 따른다.

현재 단일 로봇 실행부의 예찰로봇을 설정된 station에 자동 배치한다. 예찰 기본값은 map XY=(-5, 13.25)m, yaw=-π/2다. 수확·운송 로봇의 생성/센서/구동 실행부를 추가한 것은 아니다.

## 실행 흐름

1. `task.yaml`의 stations 및 `evaluation.T_map_world`에서 `station_spawn.json`을 생성한다. AMCL의 `initial_pose`도 같은 예찰 station에서 생성한다.
2. `scout.json`의 `station_spawn.enabled: true`에 따라 Isaac 실행부가 장치 설정 옆 `station_spawn.json`을 읽는다.
3. 씬을 연 뒤 물리 초기화 전에 로봇 root 전체를 옮긴다. 센서/바퀴의 상대 위치와 기존 body 높이는 유지한다. map/world 등록 변환과 root/body/parent 오프셋을 고려한다.
4. USD session layer에만 배치한다. 원본 USD를 저장하지 않는다. 물리 reset 후 XY 오차 5mm·yaw 오차 0.01rad 이내인지 검사하고 실패 시 실행을 중단한다.
5. AMCL은 같은 station pose를 초기 추정값으로 사용한다. 이후에는 기존 LiDAR/바퀴 odom으로 위치를 추정한다. 시뮬 정답 pose를 주행 중 계속 주입하지 않는다.

현재 설치된 로봇 root/body가 없는 경우, 방향이 미정이거나 설계안 상태인 station, 잘못된 map/world 변환, 별도 제어 좌표계가 필요한 장치는 오류로 처리한다. 임의의 위치나 방향으로 대체하지 않는다.

station 원본을 수정하면 프로젝트 루트에서 실행한다.

```bash
python sim/tools/rebuild_route_data.py
python sim/tools/validate_route_data.py
python sim/tests/test_station_spawn.py
bash scripts/build.sh sim
```

`farm_sim_runtime isaac.launch.py`가 수정된 실행부를 시작한다. 로봇 bringup은 Isaac을 시작하거나 이동시키지 않는다. 이미 실행 중인 Isaac은 새 실행부로 재시작해야 한다. 수동으로 USD만 연 경우에는 이 코드가 실행되지 않는다.

기존 씬 위치를 사용하려면 `scout.json`의 station_spawn.enabled를 false로 지정하고 AMCL 초기 pose도 해당 위치에 맞춰야 한다. station 값으로 재생성하면 AMCL도 다시 station으로 설정되므로 두 방식의 설정을 혼용하지 않는다.

## NavigateToPose와 FollowPath

| 구분 | NavigateToPose | FollowPath (현재 선택) |
|---|---|---|
| 예찰 코드가 Nav2에 보내는 값 | 목표 XY·yaw | 그래프에서 계산한 Path |
| 이동 경로 계산 | Nav2가 점유 지도로 계산 | 공통 RouteGraph가 허용 그래프 엣지에서 계산 |
| 연결 그래프 사용 | 이동 경로 계산에는 사용하지 않음. 목표 관측점 정의는 사용 | station/현재 위치에서 목표까지 연결 경로 계산에 사용 |
| 주행 제어 | Nav2 주행 구성 | Nav2 FollowPath controller |

둘 다 자율주행이다. 차이는 **이동 경로를 누가 결정하느냐**다. NavigateToPose에서는 고정 관측점에 가더라도 중간 이동이 복원된 그래프 경로와 일치한다고 보장하지 않는다.

현재 공통 Navigator는 `navigation.mode: follow_path`일 때 AMCL이 추정한 현재 위치를 그래프에 대응시키고, 목표까지 방향 그래프를 탐색해 Path를 만든 뒤 FollowPath 액션으로 보낸다. 공통 코드를 수정할 필요는 없다. 현재 설정상 시작점이 그래프에서 0.1m 이상 떨어지면 경로 계획을 거절한다. 이전 USD 시작 위치는 station과 달랐으므로 데이터 복원 때 바로 전환하지 않았다.

후속 사용자 요청으로 실물과 같은 `follow_path`를 적용했다. 현재 `sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml`은 다음 값이다.

```yaml
navigation:
  mode: follow_path
```

위 코드는 현재 설정의 발췌다. controller_id=RPP를 포함한 상세 정렬 내역은 `FOLLOWPATH_ALIGNMENT_20261002.md`를 참고한다. 이 선택은 공통 예찰 Navigator를 통한 미션 이동에 적용된다. RViz가 직접 NavigateToPose Goal을 보내는 동작을 FollowPath로 바꾸는 설정은 아니다.

FollowPath 선택만으로 다중 로봇 교통 제어, 자동 station 복귀, 도킹, 막힌 그래프 경로의 대체 경로 재계획까지 추가되는 것은 아니다. 현재 그래프의 역할별 통행 필터는 파생 데이터에서 적용하며 실시간 교통 허가는 별도다.

## 검증

- 좌표 변환/부모·body 오프셋/비영점 map-world 등록/높이 보존/중복 배치/오류 처리: 오프라인 시험 6개 통과.
- ROS launch 객체를 시험용 기록 객체로 대체한 설정 검사: 4개 조합 통과, AMCL/station 불일치 실행 거절 확인.
- 기존 16구역·80관측점·371개 경로 검사 통과.
- nav2_scout.yaml은 초기 pose 외의 파라미터 값을 유지한다. sim 밖 파일은 변경하지 않는다.
- ROS/Isaac/실제 USD 변환 API·물리 구동 및 colcon 빌드는 이 환경에서 실행하지 못했다. 실제 시작 시 station placement 로그와 RViz 초기 위치를 확인해야 한다.

이번 누적 패치는 직전 연결 경로 복원 패치의 sim 파일을 포함한다. 이전 시험 서버나 공통 코드를 덮어쓰지 않는다.
