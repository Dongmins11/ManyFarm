# 예찰로봇 소프트웨어 인수인계서

기준일: 2026-10-02. 대상: ROS 2 예찰로봇의 운영·관제 연동·기능 확장·장애 분석 담당자. 이 문서는 현행 구성과 운영 절차, 검증 범위, 남은 작업을 설명한다.

> 현재 상태: 관제 명령을 받아 실물 매니팜 그래프의 4번·6번·8번에 순서대로 도착하는 것까지 확인했다. 카메라 사전 준비와 촬영·검출도 실행됐다. 다만 최신 실행은 마지막 관측의 유효 깊이·신뢰도 표본 부족으로 `FAILED`였다. **세 지점 주행 성공과 전체 예찰 미션 성공은 구분해야 한다.**

## 1. 시스템 범위와 인수 상태

관제로부터 Section 예찰 명령을 받아 지정된 관측 지점으로 이동하고, RGB-D 영상에서 과실을 검출·등록한 뒤 수확 작업 목록을 만든다. 미션·상태 로직은 공유하고 sim/real 환경 데이터와 장치 어댑터를 교체한다.

실물 구성은 TurtleBot3 Burger, D435, 매니팜 지도·그래프다. `SEC_01`은 4번·6번·8번을 관측하고 명령 대기한다. 자동 복귀·도킹·언도킹은 구현되지 않았다.

기존 단일 survey_server에서 Node·Mission·Communication·StateController·State로 역할을 분리했고, 주행 기능은 farm_navigation으로 이관했다. 기존 서버·계산 코드는 참조·호환을 위해 보존했다. 같은 액션 이름의 기존 서버와 새 서버를 동시에 실행하지 않는다.

## 2. 설정 변경과 코드 변경의 구분

지도·장착값·카메라 프로파일·순찰 지점·허용오차는 config에서 변경한다. 새로운 업무 단계와 상태 전환은 State 코드에서 변경한다. 관제 메시지 형식을 변경할 때는 farm_interfaces와 실제 관제를 함께 맞춘다. 설정과 소스 모두 실행 중 프로세스에 자동 반영되지 않으므로 재시작이 필요하다.

## 3. 현재 폴더 구조와 각 패키지 책임

아래 경로는 `farm_project/` 기준이다. 설명에 필요한 주요 파일만 표시했다.

```text
farm_project/
├── control/
│   └── scripts/send_scout_area.py       # 테스트용 관제 ActionClient
├── scripts/
│   ├── run_scout_survey_worker.py       # 기존 시뮬 영상 워커 진입점
│   ├── run_scout_real_worker.py         # 실물 D435/YOLO RPC 진입점
│   └── scout_realsense_camera.py        # 실물 카메라 프로파일 적용
├── robot/
│   ├── config/
│   │   ├── environments/scout_real.yaml
│   │   ├── robots/burger/{devices.json,nav2.yaml}
│   │   ├── robots/vicpinky/nav2.yaml
│   │   ├── maps/many_farm/
│   │   ├── patrol/{scout_real_sections.json,scout_real_return.json}
│   │   ├── survey/{scout_real.json,scout_real.example.json}
│   │   └── vision/{scout.json,scout_real.json}
│   └── ros_ws/src/
│       ├── farm_common/                 # 범용 계산·경로·영상 공유 유틸
│       ├── farm_interfaces/             # ROS 메시지·액션 형식
│       ├── farm_vision/                 # 기존 영상·전처리·검출 기능
│       ├── farm_navigation/             # 공통 경로·Nav2·위치·정지 검사
│       ├── farm_real_devices/           # 기존 실물 드라이버 bringup
│       ├── farm_bringup/                # 환경 선택과 전체 실행 연결
│       └── scout_robot/
│           ├── scout_robot/            # 기존 서버와 예찰 계산 코드 보존
│           └── scout_new/              # 현재 새 예찰 실행 구조
├── sim/ros_ws/src/farm_sim_config/
│   ├── config/                         # 시뮬 환경·주행·예찰 설정
│   └── maps/                           # 시뮬 지도·그래프
├── tests/
└── docs/
```

### 공통 패키지라고 모든 기능을 넣지는 않는다

| 패키지 | 넣는 기능 | 현재 예 |
|---|---|---|
| `farm_common` | 로봇 업무와 무관한 유틸 | `paths.py`, `rgbd_shm.py`, `kinematics.py` |
| `farm_interfaces` | 서로 주고받을 ROS 자료형 | `ScoutArea.action`, `HarvestTask.msg`, `RobotPose.msg` |
| `farm_vision` | 영상·전처리·검출 관련 공통 구현 | `preprocess.py`, `detector.py`, `survey_worker.py` |
| `farm_navigation` | 동일한 계약으로 재사용 가능한 이동 기능 | 그래프 계획, Path 변환, Nav2Client, TF·odom 검사 |
| `farm_real_devices` | 실제 장치 드라이버 실행·namespace·장착 TF | Burger 기존 bringup, 기존 Vicpinky bringup 선택 |
| `scout_new` | 예찰 업무의 의미와 순서 | 어떤 Section을 촬영하고 언제 피드백을 보낼지 |

`kinematics.py`가 있다고 실물 모터 드라이버의 odom을 다시 계산하는 구조는 아니다. 실물에서는 기존 드라이버가 제공하는 바퀴 제어·odom을 사용한다. 마커 위치추정은 후속 범위이며, 아직 공통 위치추정 모듈을 완성한 것은 아니다.

### 소스 원본과 호환 링크

실제 소스 위치:

```text
robot/ros_ws/src/scout_robot/scout_new/
```

기존 설명 폴더 안의 다음 경로는 실제로 별도 사본이 아니라 상대 심볼릭 링크다.

```text
robot/ros_ws/src/scout_robot/scout_robot/Scout New/scout_new
    → ../../scout_new
```

`Scout New`의 README·GUIDE 등 설명 파일은 남아 있다. `build/`, `install/`은 소스와 별도의 빌드·설치 경로이며 직접 수정할 대상이 아니다. `scout_new`를 최종 `scout` 등으로 교체하는 이름·폴더 정리는 아직 수행하지 않았다.

## 4. 실행 모듈과 config 상세

### 모듈별 책임

| 구성 | 책임 |
|---|---|
| ScoutNode | 설정·ROS 자원·객체 생성과 종료 |
| ScoutCommunication | Goal 검증·취소·Feedback·Result |
| ScoutMission / MissionContext | 미션·Section·관측·누적 결과·보고서 |
| ScoutStateController | 상태 수명·이벤트 처리·공통 중단 |
| 각 State | 해당 단계의 행동 요청·결과 처리·전환 요청 |
| VisionRuntime | 영상 워커 사전 준비·대여·반환·종료 |
| Navigator | 경로 계획·Nav2 실행·정지·도착 검사 |

State의 enter는 I/O 요청 후 반환한다. 별도 작업 스레드가 주행·영상 응답을 기다리고, 완료 이벤트는 Controller.update에서 처리한다. exit는 상태 수명 종료이며 매번 모터·카메라를 끄는 함수가 아니다. 늦은 응답은 상태 generation 검사로 차단한다.

### config의 의미와 연결 관계

config는 같은 실행 코드가 **어떤 지도·장치·관측 지점·수치 조건을 사용할지 정하는 데이터**다. 파일 확장자가 같더라도 환경 YAML, 지도 YAML, Nav2 YAML은 역할이 다르다.

```text
launch: mode + project_root
 → 환경 YAML
    ├─ map_yaml → 지도 YAML → PGM 이미지
    ├─ route_graph → 포인트·엣지 GeoJSON
    ├─ nav_params → Nav2 파라미터 YAML
    ├─ device_config → 모델·USB·라이다·장착 TF JSON
    ├─ patrol_config → Section별 촬영 순서 JSON
    └─ survey_config → 베드·과실·윈도우 JSON
                         └─ vision_config → 카메라·모델·워커 JSON
```

일반 상대 설정 경로는 project_root 기준이다. 지도 YAML의 이미지 참조나 영상 Python·legacy 디렉터리는 해당 로더의 경로 규칙을 따른다. config를 다른 위치로 옮길 때 참조 경로도 함께 확인한다.

### 4.1 환경 YAML — 설정 선택의 진입점

실물: `robot/config/environments/scout_real.yaml`  
시뮬: `sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml`

| 항목 | 역할 |
|---|---|
| schema_version | 설정 형식. 환경 로더는 현재 1 요구 |
| configured | 설정 사용 가능 표시. 실기 성공 보증 아님 |
| survey_configured | 예찰 설정 준비 여부. 주행만 실행하는 경우와 분리 |
| mode | sim/real. launch 선택과 일치 필요 |
| robot_id / map_id | 관제·장치·예찰 설정 사이의 식별자 |
| map_yaml / route_graph | 위치추정 지도와 주행 그래프 경로 |
| nav_params / device_config | Nav2와 장치 설정 경로 |
| survey_config / patrol_config | 예찰 기준과 촬영 순서 경로 |
| navigation | 공통 Navigator의 모드·프레임·오차·플러그인 설정 |

실물 navigation은 follow_path, controller_id=RPP, base_frame=base_footprint, map_frame=map이다. goal_checker_id와 progress_checker_id는 Nav2에 등록된 이름과 일치해야 한다.

arrival_tolerance_m(0.08m), heading_tolerance_rad(0.12rad)는 Nav2 종료 후 애플리케이션의 최종 검사다. settle_s(0.8초)는 정지 확인 구간, goal_timeout_s(300초)는 이동 응답 제한이다. max_start_distance_m(0.10m), max_goal_distance_m(0.02m)는 그래프와 시작·목표 연결의 허용 거리다. path_spacing_m(0.04m)는 Path 보간 간격이다.

### 4.2 지도 — 위치추정 공간과 이동 그래프

폴더: `robot/config/maps/many_farm/`

- many_farm.yaml: 이미지 경로·해상도·원점·점유 판단 등의 지도 메타데이터. map_server가 읽는다.
- many_farm.pgm: 장애물과 자유 공간을 표현하는 점유 지도 이미지.
- graph.geojson: 이동 포인트와 엣지. 자체 경로 탐색 입력.
- reference/graph.json: 이전 시스템 참조 자료. 현재 경로 계산 입력 아님.

점유 지도는 AMCL·costmap에, 그래프는 지정 통로 주행에 사용한다. 둘은 같은 map 좌표계를 공유해야 한다. 이미지만 교체하고 그래프를 그대로 두면 경로가 실제 공간과 어긋날 수 있다.

### 4.3 Nav2 YAML — 위치추정·제어·장애물·속도 설정

파일: `robot/config/robots/burger/nav2.yaml`

| 블록 | 기능 |
|---|---|
| amcl | 라이다·지도 기반 위치추정, 초기 위치 정책 |
| controller_server | RPP/DWB, Path 추종, 도착·진척 검사 |
| local_costmap / global_costmap | 주변 장애물·지도 비용 정보 |
| planner_server | Nav2 경로 계획 |
| bt_navigator | NavigateToPose 등의 실행 흐름 |
| velocity_smoother | 속도·가속도 제한과 명령 평활화 |
| behavior_server | 회전·후진 등 Nav2 동작 |

모터 USB 포트나 카메라 해상도는 이 파일의 역할이 아니다. AMCL set_initial_pose=false이므로 현재 시험에서는 수동 초기 위치 입력이 필요하다. Nav2 goal_checker와 공통 Navigator의 최종 허용오차는 별개의 검사이므로 함께 검토한다.

### 4.4 devices.json — 실제 장치와 장착 TF

원본: `robot/config/robots/burger/devices.json`

| 항목 | 의미 |
|---|---|
| model | burger 등 기존 하드웨어 bringup 선택 |
| usb_port | 모터 보드 장치. 현재 /dev/ttyACM0 |
| lds_model | 기존 라이다 드라이버 선택. 현재 LDS-02 |
| robot_id / map_id | 환경과 일치 검사 |
| camera_mount | base→camera link→optical frame 관계 |
| xyz_m / rpy_rad | 장착 위치(m), 회전(rad) |

실제 장착이 바뀌면 TF 수치도 갱신한다. 카메라 해상도·자동 노출은 vision JSON에서 설정한다. URDF는 기존 로봇 패키지를 재사용하고 카메라 장착은 별도 고정 TF로 제공한다.

`farm_real_devices/config/scout_devices_real.json`은 설치용 링크다. robots/burger/devices.json을 원본으로 편집한다.

### 4.5 survey JSON — 베드·과실·수확 윈도우 기준

파일: `robot/config/survey/scout_real.json`

| 항목 | 의미 |
|---|---|
| vision_config | 연결할 영상 설정 경로 |
| output_dir | 미션 보고서·영상 로그 출력 루트 |
| base_frame | 로봇 기준 프레임 |
| association_distance_m | 과실 ID 거리 매칭 제한, 현재 0.065m |
| association_band_half_depth_m | 베드 평면 주변 수용 띠의 반폭, 현재 0.2m |
| overlap_fraction | 자동 관측점 설계의 영상 겹침 비율 |
| sections | Section별 베드·관측·수확 기준 |
| route_file / node_ids | 베드의 직선 진행 기준을 만드는 그래프·노드 |
| bed_plane_from_route_m | 경로에서 베드 평면까지 법선 거리, 현재 1.14m |
| segmentation | 기본 수동/자동 관측 계획 |
| finish_at | 마지막 촬영점 대기 또는 베드 끝 추가 이동 |
| harvest | 수확 목표 자세와 윈도우 포함 범위 계산 |

베드 기준 노드 2~9는 각 노드에서 촬영한다는 뜻이 아니다. 실제 촬영 노드는 patrol 설정의 4·6·8이다.

harvest의 mount_xy_base_m, work_offset_xy_base_m, heading_offset_rad는 수확 목표 계산에 사용한다. height_reference_m, height_offsets_m, width_m, depth_m, margin 항목은 윈도우 범위·포함 판정에 사용한다. 예찰 카메라 장착 TF와 수확 장착 수치를 혼동하지 않는다.

scout_real.example.json은 참조 예제이며 운영 입력은 scout_real.json이다.

### 4.6 patrol JSON — 실제 촬영 위치와 순서

파일: `robot/config/patrol/scout_real_sections.json`

```text
sections.SEC_01.segments
  SEG_01 → observation_node_id: 4
  SEG_02 → observation_node_id: 6
  SEG_03 → observation_node_id: 8
on_complete: WAIT_FOR_COMMAND
```

apply_patrol은 베드 기준을 유지하면서 촬영 순서를 적용한다. patrol_design은 노드가 베드 직선 위에 있고 진행 순서대로 있는지 검사한다. patrol 적용 시 finish_at은 last_segment이며 기본 segmentation 대신 그래프 노드 계획을 사용한다. 고정 세 지점이 전체 베드 영상 커버리지를 보장하지는 않는다.

scout_real_return.json은 별도 복귀 명령으로 노드 1에 돌아갈 설정 초안이다. 현재 FSM·런치·복귀 액션에 연결되지 않아 값을 바꿔도 자동 복귀하지 않는다.

### 4.7 vision JSON — 영상 환경·모델·카메라

파일: `robot/config/vision/scout_real.json`

| 항목 | 현재 값·역할 |
|---|---|
| backend | realsense_legacy. 실물 어댑터 선택 |
| worker_python | 영상 패키지가 설치된 ~/pi_d435_setup/.venv/bin/python |
| legacy_directory | 재사용 코드 ~/bmany_fleet_ws/perception_worker |
| model | legacy 디렉터리 기준 model_yolo11_seg_ver1.2.pt |
| camera_frame | camera_color_optical_frame. 장착 TF와 일치 필요 |
| confidence | 검출 수용 신뢰도 0.6 |
| preprocess | 선택 backend에서 사용하는 전처리 설정 |
| startup_timeout_s | 전체 워커 ready 대기 제한 300초 |
| rpc_timeout_s | 실물 관측 요청 응답 제한 180초 |
| camera.width / height / fps | RGB·Depth 1280×720, 6FPS |
| auto_white_balance / auto_exposure | true |
| warmup_frames | 시작 시 수신할 프레임 수 120 |
| warmup_timeout_s | 워밍업 프레임 대기 제한 90초 |

전체 워커 시작 제한과 카메라 워밍업 제한은 범위가 다르다. 모델·라이브러리 로딩은 전체 워커 시작에 포함된다.

### 설정 우선순위와 변경 시 주의

- 환경 mode와 launch mode, 환경·장치·예찰 ID 및 그래프 일치를 검사한다.
- 환경 파일과 다른 survey_config를 동시에 지정하면 거절한다.
- 주행 설정은 survey 기본값을 읽고 환경 navigation으로 덮어쓴다. base_frame 불일치는 오류다.
- 별도 vision_python 실행 인자는 vision JSON의 worker_python보다 우선한다.
- patrol 설정이 적용되면 실제 관측 계획은 patrol 노드 기준이다.
- 일반 설정 변경 후 관련 노드·launch를 재시작한다. 새 모듈·인터페이스 변경은 빌드도 필요하다.

## 5. 노드 시작부터 예찰 종료까지

### 5.1 시작과 사전 준비

```text
scout.launch.py
  ├─ 실물: 기존 드라이버 + 장착 TF
  ├─ Nav2: map_server / AMCL / controller / planner 등
  └─ scout_node
      ├─ 설정·그래프·베드 로드
      ├─ Mission / Controller / Communication 생성
      └─ VisionRuntime 비동기 준비
          → 모델 로딩
          → 카메라 연결·워밍업
          → ready 수신
          → Goal 수락 가능
```

영상 준비 완료는 영상 장치의 준비를 뜻한다. AMCL 초기 위치까지 자동으로 보장하지 않는다. 각 미션의 첫 이동 전에는 별도 Nav2 사전 검사를 수행한다.

실제 확인 로그:

```text
영상 사전 준비 시작: 모델 로딩·카메라 워밍업
영상 사전 준비 완료: Goal 수락 가능 (70.7초)
```

초기화 비용을 없앤 것이 아니라 노드 시작 단계로 옮겼다. 운영 Node는 `VisionRuntime`을 사용하고, `ScoutMission.open_observer()`에는 기존 직접 워커 생성 경로도 호환 목적으로 남아 있다.

### 5.2 Goal 처리

현재 액션 이름: `/scout_01/scout_area`

현재 실물 입력 예:

```yaml
robot_id: scout_01
task_id: SCOUT_102
section_ids: [SEC_01]
map_id: many_farm_v1
frame_id: map
crop_type: PAPRIKA
target_ripeness: RIPE
timestamp: "실제 요청 생성 시각"
```

`accept()`에서 다음을 검사한다.

- robot_id, map_id, frame_id, crop_type, target_ripeness 일치
- task_id와 section_ids가 비어 있지 않은지
- 구역 중복과 미등록 구역 여부
- 설정·영상 준비 오류
- 실행 중, 종료 중, 주행 정지 상태 미확인 여부

`ACCEPT`는 미션 수락이다. 주행 시작·도착·예찰 성공을 의미하지 않는다. 영상 준비 중 거절한 요청을 로봇이 자동 대기열에 넣지는 않는다. 준비 완료 후 관제가 다시 요청해야 한다.

### 5.3 State별 책임·동작·전환

```text
IDLE → NAVIGATION_MOVE → SEGMENT_PROGRESS → SEGMENT_COMPLETE
              ↑                                   │ 다음 촬영점
              └───────────────────────────────────┘
                                                  │ 마지막 지점
                                                  ↓
                                           SECTION_COMPLETE
                                             ├─ 다음 구역 → 이동
                                             └─ 전체 완료 → 정리 → IDLE
```

#### IDLE — 명령 대기

idle_state.py. 주행·관측을 시작하지 않는다. Communication이 Goal을 수락하면 Controller가 MissionContext를 생성하고 첫 Section을 선택해 NAVIGATION_MOVE로 전환한다. IDLE 자체가 장치 준비 완료를 보장하지 않는다.

#### NAVIGATION_MOVE — 준비·이동·도착

navigation_move_state.py. 최초 진입에서 미션 폴더 생성, Nav2 사전 검사, 준비된 워커 대여를 수행한다.

- section_start: patrol이면 첫 촬영 노드, 일반 계획이면 베드 origin을 목표로 한다.
- observation: Segment offset에 해당하는 베드 위치로 이동한다.
- section_exit: finish_at=route_end이면 베드 끝으로 추가 이동한다.

목표를 XY와 yaw로 전달한다. bed.world()는 XYZ를 반환하므로 호출 경계에서 XY로 변환한다. Nav2 종료 후 odom 정지와 실제 도착 오차를 확인한다.

첫 도착에서 영상 info·장착 정보를 읽어 관측 계획을 구성한다. 그래프 patrol은 이미 첫 촬영점에 있으므로 중복 이동 없이 SEGMENT_PROGRESS로 전환한다. 일반 촬영점 도착도 SEGMENT_PROGRESS, 출구 도착은 SECTION_COMPLETE로 전환한다. 이동 실패는 공통 중단 경로로 전달한다.

#### SEGMENT_PROGRESS — 촬영·검출·좌표 변환·등록

segment_progress_state.py.

1. 현재 Segment를 CAPTURING으로 기록한다.
2. 정지 확인 시각과 camera session을 포함해 capture를 요청한다.
3. 관측 중 움직임을 검사한다. 실물 어댑터는 TF 안정성도 검사한다.
4. 검출 좌표를 map 기준으로 변환한다.
5. 베드 길이·법선 허용 띠 밖 검출은 제외 사유와 함께 구분한다.
6. Survey.ingest로 과실 ID와 윈도우 상태를 갱신한다.
7. Observation을 저장하고 SEGMENT_COMPLETE로 전환한다.

이 상태는 완료 Feedback을 보내지 않는다. TF·검출 오류는 중단 경로로 전달한다.

#### SEGMENT_COMPLETE — 저장·완료 확정·다음 위치 판단

segment_complete_state.py. annotate를 요청해 이미지·ID 표시·윈도우 자료를 저장한다. map_detections.json과 관측 요약, Segment 완료 기록, survey.json을 저장한다.

- segment_expected_count는 해당 관측에서 등록된 고유 ID 수다.
- 중간 Segment면 SEGMENT_COMPLETE 피드백 후 다음 인덱스로 이동한다.
- 마지막 Segment면 구역 전체 윈도우에서 HarvestTask를 만들고 SECTION_COMPLETE로 전환한다.

현재 마지막 Segment의 피드백은 별도 발행하지 않는다. 파일 저장에 실패하면 완료로 보고하지 않는다.

#### SECTION_COMPLETE — 구역 확정·추가 이동·종료

section_complete_state.py. 계획된 모든 Segment가 COMPLETE인지 검사하고 Section 결과·수확 작업 수를 누적·저장한다. 저장 후 SECTION_COMPLETE 피드백을 보낸다.

finish_at=route_end이며 아직 경로 끝이 아니면 추가 이동 후 돌아온다. 이미 보고된 구역은 피드백을 중복 전송하지 않는다. 다음 Section이 있으면 NAVIGATION_MOVE로 전환하고 없으면 Controller.complete를 요청한다.

실물 patrol은 last_segment이므로 마지막 관측 위치에서 완료한다. 이 동작은 스테이션 복귀가 아니다.

#### DOCKING — 현재 미구현

docking_state.py는 존재하지만 실제 복귀·정밀 도킹 계약과 제어가 연결되지 않았다. 진입하면 DOCKING_UNAVAILABLE 오류가 발생한다. 현재 정상 예찰 흐름에서는 사용하지 않는다.

#### 실패·취소의 공통 처리

Controller가 정상 진행을 차단하고 진행 I/O 반환 후 주행 종료·정지 확인, 영상 자원 정리, 최종 보고서·Result 생성을 수행한다. 마지막에 IDLE로 복귀한다. 정지나 자원 종료가 불확실하면 motion_uncertain으로 후속 수락을 차단할 수 있다. 별도의 AnyState 클래스로 모든 오류를 몰아넣는 구조가 아니다.

### 5.4 Feedback과 Result

실제 전송은 `ScoutCommunication.feedback()`의 `goal.publish_feedback(feedback)`에서 한다.

| 시점 | 현재 전송 |
|---|---|
| 준비·이동 중 | 완료 피드백 없음 |
| 마지막을 제외한 Segment 처리 완료 | `SEGMENT_COMPLETE`, 완료 개수, 빈 harvest_tasks |
| 마지막 Segment 후 구역 완료 | `SECTION_COMPLETE`, 구역 전체 harvest_tasks |
| 미션 종료 | SUCCESS / FAILED / CANCELED Result |

마지막 Segment의 `SEGMENT_COMPLETE`는 별도로 보내지 않는다. 첫 촬영 전에 실패하면 Feedback 없이 FAILED Result만 받을 수 있다.

테스트 클라이언트가 요청한 작업의 결과가 실제 관제 UI에 자동 저장되는 것은 아니다. 실제 관제가 직접 요청·결과 처리를 하거나 별도 관찰 기능을 구현해야 한다.

### 5.5 워커 수명과 미션 수명의 차이

| 상황 | 처리 |
|---|---|
| 노드 시작 | 워커 생성·사전 준비 |
| 미션 시작 | 준비된 워커를 acquire |
| 정상 완료 | 워커 반환·유지, 다음 미션 재사용 |
| 사용 중 실패·취소 | 워커 종료 후 재준비하여 남은 RPC 응답 격리 |
| 노드 종료 | 준비 스레드와 워커 종료 |
| 초기 준비 실패 | 오류 사유 유지, 요청 수락 불가 |
| 대기 중 워커 프로세스 종료 | 생존 검사에서 거절, 현재 안내는 노드 재시작 |

모든 장애가 자동 복구되는 것은 아니다. 현재 구현은 실패·취소한 미션이 사용하던 워커 교체와 초기 준비 실패 처리를 구분한다.

로그도 미션별 파일에서 노드 수명 로그로 분리됐다.

```text
runs/scout_survey/vision_<ID>/vision_worker.log
runs/scout_survey/<미션 세션 ID>/survey.json
```

`survey.json`의 `vision_worker_log`가 공유 워커 로그를 가리킨다. 현재 재준비 시 같은 로그 파일을 다시 열기 때문에 이전 워커 로그가 덮어써질 수 있다. 미션별 survey.json은 별도로 남는다. 장기 운영의 로그 회전·임시 촬영 파일 정리는 추가 검토 대상이다.

## 6. 시뮬과 실물: 같은 부분과 다른 부분

| 항목 | 시뮬 | 실물 |
|---|---|---|
| 상위 미션·State 코드 | 공통 | 공통 |
| 환경 설정 | `sim/.../config/scout_runtime.yaml` | `robot/config/environments/scout_real.yaml` |
| 지도 ID | `farm_map_v1` | `many_farm_v1` |
| 구역 | 기존 BED 계열 | 현재 `SEC_01` |
| 지도·그래프 | 시뮬용 | 매니팜 실측 지도·그래프 |
| 주행 기본 방식 | `NavigateToPose` | 자체 그래프 계획 + `FollowPath` |
| 이유 | 그래프가 베드별 16개 비연결 성분 | 연결된 실물 통로 그래프 사용 |
| base frame | `scout_01/base_footprint` | `base_footprint` |
| ROS 시간 | 시뮬 시간 | 실시간 |
| 센서 입력 | 시뮬 영상·장치 연결 | 기존 Burger 드라이버 + D435 SDK |
| 영상 워커 | `run_scout_survey_worker.py` | `run_scout_real_worker.py` |
| 좌표 처리 | 시뮬 워커 메타데이터 기반 | 정지 관측 기준 TF와 안정성 검사 |
| 카메라 사전 준비 | 동일 수명 관리 적용 | 동일 수명 관리 적용 |
| 최신 실기 확인 | 사전 준비 변경 후 Isaac Sim E2E 미검증 | 세 촬영 지점 도착 확인 |

동일 코드란 서로 다른 지도의 포인트 ID·좌표를 데이터로 읽고 같은 계약으로 처리한다는 뜻이다. 시뮬 지도를 실물 그래프로 바꾸거나, 실물 `SEC_01`의 노드 번호를 시뮬에 그대로 적용한 것은 아니다.

시뮬 `FollowPath`를 쓰려면 베드 간 연결과 시작·목표의 그래프 적합성을 먼저 확보해야 한다. 연결을 임의로 추가하거나 실패하면 조용히 NavigateToPose로 바꾸는 처리는 넣지 않았다.

## 7. 주행 로직과 실물 순찰 데이터

```text
관제: SEC_01 요청
 → patrol JSON: 관측 노드 4, 6, 8 선택
 → State: 다음 목표 XY와 방향 결정
 → Navigator.plan()
 → 현재 TF 위치를 그래프에 연결
 → 자체 그래프 탐색(Dijkstra)
 → Path 보간
 → FollowPath(RPP)
 → Nav2 종료 + odom 정지 확인 + TF 도착 오차 검사
 → 촬영 단계
```

현재 새 공통 경로 계산은 `ComputeRoute` 액션 호출이 아니다. 기존 미니관제에는 자체 RouteToPose 경로와 ComputeRoute 사용 경로가 따로 있었으며 혼동하지 않는다.

현재 실물 주요 값:

| 값 | 설정 |
|---|---|
| 출발 참고점 | 1번 `(0.519, -0.759)` |
| 초기 방향 | 1번에서 2번을 바라봄: yaw `-π/2` |
| 관측 노드 | 4 / 6 / 8 |
| 베드 기준 경로 | 노드 2~9 |
| 베드 평면과 경로 간격 | 1.14m |
| 경로 보간 간격 | 0.04m |
| 그래프 시작점 허용 거리 | 0.10m |
| 그래프 목표점 허용 거리 | 0.02m |
| 최종 도착 검사 | 위치 0.08m, 방향 0.12rad |
| 정지 확인 시간 | 0.8초 |

초기 위치 명령은 실제 로봇 위치·방향을 추정기에 알려주는 것이다. 목표로 이동시키는 명령이 아니다. 현재 시험 배치의 방향은 1→2, yaw -90°다. 실제 배치가 다르면 이 값을 그대로 사용하지 않는다.

## 8. 카메라·과실·윈도우 처리

### 카메라

- RGB와 Depth: 1280×720, 6FPS.
- 자동 노출·자동 화이트밸런스 ON.
- 워밍업 120프레임. 프레임 시간 외 모델·모듈 로딩도 필요하다.
- 4600K는 관측된 값이며 수동 고정 설정이 아니다.
- 기존 로봇의 `~/bmany_fleet_ws/perception_worker` 구현과 `~/pi_d435_setup/.venv`를 재사용한다.
- 장착 TF는 `devices.json`에 저장한다. 기존 카메라 TF 런치와 중복 실행하지 않는다.
- 파이카메라·ArUco/AprilTag 위치추정은 아직 연결하지 않았다.

실물은 실제 노출 시각을 정확한 ROS 시각으로 제공한다고 가정하지 않는다. 관측 시작의 map→camera 변환을 기준으로 하고 관측 구간의 TF·odom 안정성을 확인한다. 움직임이나 오래된 TF가 감지되면 결과를 폐기한다.

### 워밍업을 하는 이유와 실제 구현

카메라 시작 직후 자동 노출·화이트밸런스가 주변 조명에 적응하는 구간의 영상을 바로 업무에 사용하지 않기 위해 일정 프레임을 먼저 받는다. 과실 색상·밝기 입력의 변동을 줄이려는 목적이며, RGB·Depth 스트림 시작도 이 준비 단계에 포함된다.

현재 ConfiguredCamera.start는 수신 sequence가 warmup_frames=120에 도달할 때까지 기다린다. 6FPS에서는 프레임 수 기준 약 20초가 필요하고 장치 시작·수신 지연은 추가된다. **노출이나 화이트밸런스가 실제 수렴했는지를 수치로 판정하는 구현은 아니다.** 설정한 프레임 수만으로 모든 조명 조건의 영상 품질을 보장하지 않는다.

자동 노출·화이트밸런스는 워밍업 이후에도 켜져 있다. 4600K는 측정 예이며 고정값이 아니다. 조명 변경 시 입력 품질을 별도로 확인한다.

영상 사전 준비의 약 70초는 Python·라이브러리 import, 모델 로딩, 카메라 연결, 프레임 워밍업을 모두 포함한 시간이다. 전체가 카메라 워밍업은 아니고, GPU 모델 예열을 별도로 구현했다는 뜻도 아니다.

노드 시작 때 이 비용을 먼저 지불하고 정상 미션 사이에는 워커를 유지한다. 실패·취소 후 재준비에는 다시 비용이 들며, 준비 중 Goal은 자동 대기열에 저장되지 않고 거절된다.

### 과실 등록 정책

선택 파일: `scout_robot/scout_robot/survey_policy.py`

```python
ACTIVE_SURVEY_POLICY = SurveyPolicy.MEDIAN_REVALIDATE
```

| 정책 | 좌표 갱신 | 윈도우 소속 |
|---|---|---|
| MEDIAN_REVALIDATE | 누적 관측의 축별 중앙값 | 갱신 좌표로 재검사 |
| FIRST_POSITION_KEEP_MEMBERSHIP | 최초 좌표 유지 | 기존 소속 유지, 새 과실 등록·추가 |

두 정책 모두 거리 제한 기반 일대일 대응을 사용한다. 보수적 별도 매칭 알고리즘은 도입되지 않았다. 정책은 코드에서 선택하며 한 Survey가 진행되는 동안 바뀌지 않는다.

## 9. 주요 소스 파일과 변경 범위

아래 링크는 이 문서 위치에서 접근할 수 있는 상대 경로다. 각 파일의 책임과 주요 이관 범위를 기록한다.

### 예찰 실행 구조

기준 폴더: `robot/ros_ws/src/scout_robot/scout_new/`

| 파일 | 작업 및 현재 역할 |
|---|---|
| [scout_node.py](../robot/ros_ws/src/scout_robot/scout_new/scout_node.py) | 추가·변경. ROS·설정·공통 주행·상태·영상 수명 연결 |
| [scout_mission.py](../robot/ros_ws/src/scout_robot/scout_new/scout_mission.py) | 추가·변경. 미션 데이터·보고서, 워커 대여·반환 |
| [scout_communication.py](../robot/ros_ws/src/scout_robot/scout_new/scout_communication.py) | 추가·변경. ActionServer, Goal 진단 로그, 영상 준비 검사 |
| [scout_state_controller.py](../robot/ros_ws/src/scout_robot/scout_new/scout_state_controller.py) | 추가·변경. 이벤트 기반 전환, 중단·정리, 성공 시 워커 재사용 |
| [mission_types.py](../robot/ros_ws/src/scout_robot/scout_new/mission_types.py) | 공유 작업 데이터와 관측 데이터 타입 |
| [vision_runtime.py](../robot/ros_ws/src/scout_robot/scout_new/vision_runtime.py) | 최근 추가. 노드 수명의 사전 준비·재사용·교체 |
| [observer.py](../robot/ros_ws/src/scout_robot/scout_new/observer.py) | 워커 RPC, 응답 큐, 종료, 생존 검사 |
| [real_observer.py](../robot/ros_ws/src/scout_robot/scout_new/real_observer.py) | 실물 정지 관측 기준 변환·안정성 검사 |
| [patrol_config.py](../robot/ros_ws/src/scout_robot/scout_new/patrol_config.py) | 순찰 JSON 검증, 그래프 노드를 관측 계획으로 연결 |
| [navigator.py](../robot/ros_ws/src/scout_robot/scout_new/navigator.py) | 공통 Navigator를 가리키는 호환 import |
| [navigation_move_state.py](../robot/ros_ws/src/scout_robot/scout_new/states/navigation_move_state.py) | 준비·이동·도착, 최근 XY 변환 수정 |
| [segment_progress_state.py](../robot/ros_ws/src/scout_robot/scout_new/states/segment_progress_state.py) | 촬영·검출·좌표 변환·과실 등록 |
| [segment_complete_state.py](../robot/ros_ws/src/scout_robot/scout_new/states/segment_complete_state.py) | 관측 저장, 완료 피드백, 수확 작업 생성 |
| [section_complete_state.py](../robot/ros_ws/src/scout_robot/scout_new/states/section_complete_state.py) | 구역 완료·다음 구역·미션 완료 판단 |

`idle_state.py`, `mission_state.py`는 상태 기본 구조다. `docking_state.py`의 존재가 복귀·정밀 도킹 기능 완성을 뜻하지 않는다.

### 공통 주행·런치·인터페이스

| 위치 | 변경 또는 역할 |
|---|---|
| `farm_navigation/farm_navigation/route.py` | 공통 그래프 로드·투영·경로 탐색 |
| `farm_navigation/farm_navigation/path_builder.py` | 그래프 계획 → ROS Path |
| `farm_navigation/farm_navigation/nav2_client.py` | 액션·파라미터 조회·취소 |
| `farm_navigation/farm_navigation/navigator.py` | 계획·실행·정지·도착 검사의 공통 창구 |
| `farm_navigation/farm_navigation/pose_provider.py` | TF 조회·시각 유효성 검사 |
| `farm_navigation/farm_navigation/motion_monitor.py` | odom 수신·정지 검사 |
| `farm_navigation/farm_navigation/configuration.py` | 환경 설정 로드·검증 |
| `farm_navigation/farm_navigation/navigation_types.py`, `arrival.py` | 설정·결과 타입과 도착 조건 |
| `farm_navigation/setup.py`, `package.xml` 등 | 새 공통 패키지 등록 |
| `farm_bringup/launch/scout.launch.py` | sim/real 전체 실행 선택 |
| `farm_bringup/launch/scout_navigation.launch.py` | 지도·Nav2 YAML 선택, namespace·리맵 |
| `farm_bringup/launch/scout_survey.launch.py` | 새 예찰 노드와 환경·Python 경로 연결 |
| `farm_real_devices/launch/scout_devices.launch.py` | 기존 드라이버 실행, Twist 형식, 장착 TF |
| `farm_real_devices/setup.py` 등 | 장치 설정 설치 연결 |
| `scout_robot/setup.py` 등 | 새 예찰 실행 진입점 패키징 |
| `farm_interfaces/action/ScoutArea.action` | 현재 관제 계약. 최신 문서 단일 section_id로 아직 변경하지 않음 |

위 경로에서 패키지 이름 앞에는 `robot/ros_ws/src/`가 붙는다.

### 환경 데이터·영상·정책

| 파일 | 작업 및 역할 |
|---|---|
| `robot/config/environments/scout_real.yaml` | 실물 설정의 연결점 |
| `robot/config/robots/burger/devices.json` | 모델·USB·라이다·카메라 장착값 |
| `robot/config/robots/burger/nav2.yaml` | 기존 Burger 설정 기반 실물 Nav2 설정 |
| `robot/config/robots/vicpinky/nav2.yaml` | 로봇별 별도 Nav2 설정, 실기 미검증 |
| `robot/config/maps/many_farm/many_farm.yaml`, `.pgm` | 기존 매니팜 점유 지도 자산 배치 |
| `robot/config/maps/many_farm/graph.geojson` | 실물 경로 계산 입력 |
| `robot/config/maps/many_farm/reference/graph.json` | 이전 그래프 참조 자료 |
| `robot/config/patrol/scout_real_sections.json` | SEC_01 → 4·6·8 매핑 |
| `robot/config/patrol/scout_real_return.json` | 미연결 복귀 설정 초안 |
| `robot/config/survey/scout_real.json` | 베드 기준·과실·수확 윈도우 값 |
| `robot/config/vision/scout_real.json` | 실물 모델·워커·카메라 프로파일 |
| `robot/config/vision/scout.json` | 기존 시뮬 영상 설정의 정리된 위치 |
| `sim/.../config/scout_runtime.yaml`, `scout_survey.json` | 시뮬 환경 연결·영상 설정 경로 등 |
| `scripts/run_scout_real_worker.py` | 기존 D435·YOLO를 FARM_RPC로 연결 |
| `scripts/scout_realsense_camera.py` | 해상도·FPS·자동 옵션·워밍업 적용 |
| `scout_robot/scout_robot/survey_policy.py`, `survey_core.py` | 과실 등록 정책 선택과 적용 |
| `control/scripts/send_scout_area.py` | 설정에서 robot/map ID를 읽는 테스트 클라이언트 |

`farm_real_devices/config/scout_devices_real.json`은 장치 설정 설치를 위한 심볼릭 링크다. 편집 원본은 `robot/config/robots/burger/devices.json`이다. 같은 설정을 두 곳에서 따로 수정하지 않는다.

### 검증 코드

- `tests/test_scout_state_flow.py`: 상태 전환·취소·예찰 흐름. 최근 실제 주행부와 같은 XY 입력 검사를 추가했다.
- `tests/test_real_observer.py`: 관측 변환·움직임 검사.
- `tests/test_scout_survey.py`: 과실 등록·윈도우 정책.
- `tests/test_vision_runtime.py`: 시뮬/실물 생성 분기, 정상 재사용, 실패 시 교체, 준비 실패·워커 종료 검사.
- `robot/ros_ws/src/farm_navigation/test/`: 경로·설정·공통 주행 계약.

## 10. 장애 분석과 수정 상태

| 현상 | 확인된 원인·상태 | 처리 |
|---|---|---|
| PC에서 farm_interfaces import 실패 | ROS workspace 환경 미적용 | install/setup.bash source 후 import 확인 |
| 다른 PC에서 토픽이 안 보임 | 해당 PC UFW가 수신 UDP 차단 | 로봇 IP의 UDP 허용 후 토픽 발견 확인 |
| map TF가 없다는 경고 | 해당 실행에서 AMCL 초기 위치 미설정 | 실제 위치·방향으로 initialpose 설정 |
| 관제 REJECT | farm_map_v1 / BED_01을 실물에 전송 | many_farm_v1 / SEC_01로 일치시킴 |
| Goal 후 긴 정지 | 모델·카메라를 미션 시작 때 준비 | 노드 시작 시 준비하도록 이관 |
| 전날 첫 주행 실패 | Nav2 Failed to make progress | 당시 명령·odom 기록이 없어 근본 원인 미확정 |
| 4번 촬영 후 6번 이동 실패 | XYZ를 XY 전용 Navigator에 전달 | State에서 XY로 변환, 회귀 검증 보강 |
| 최신 실행의 TF 오류 | 관측 기준 map←camera TF가 시각 검사에서 거절됨 | 원인 분석·수정 미완료 |
| 최신 실행의 마지막 관측 실패 | 검출은 있었으나 유효 깊이·신뢰도 표본 없음 | 정책·깊이 품질 분석 미완료 |

### 좌표 오류를 고친 위치와 이유

```python
# bed.world()는 과실·카메라 계산에도 쓰는 XYZ 함수이므로 유지합니다.
# 주행 호출 경계에서만 XY로 변환합니다.
target_xy = (float(xy[0]), float(xy[1]))
return self._mission.node._navigator.navigate(target_xy, context.bed.yaw)
```

그래프의 첫 목표는 XY여서 통과했고, 두 번째 목표는 `bed.world()`의 XYZ여서 거절됐다. 시뮬 촬영점·구역 출구 이동도 같은 경계를 지나므로 공통 수정했다. `bed.world()`에서 Z를 제거하거나 Navigator의 검증을 없애지 않았다.

## 11. 실제 검증 범위와 남은 문제

### 2026-10-02 확인한 보고서

로봇 경로 기준:

```text
~/manyfarm/main/farm_project/runs/scout_survey/
```

| 세션 | 주행 확인 | 관측 완료 | 최종 결과 |
|---|---|---|---|
| `2935001f1d62` | 4번 도착 | 1개 Segment | XY/XYZ 오류로 FAILED, 이후 수정 |
| `d2acf67aa213` | 4·6번 도착 | 1개 Segment | TF 시각 오류로 FAILED |
| `1a1eea5762e7` | 4·6·8번 도착 | 2개 Segment | 유효 깊이·신뢰도 표본 부족으로 FAILED |

마지막 실행에서 harvest_task_count가 0인 것을 과실이 전혀 없었다고 해석하면 안 된다. 현재 수확 작업 목록은 구역 전체 관측 후 확정하는데, 그 전에 실패했다.

### 자동 검증

최근 관련 테스트 59개 통과. 로봇 `scout_robot` 빌드와 `VisionRuntime` import 확인 완료. 테스트는 가짜 장치를 사용하는 부분이 있으며 실제 카메라·주행 품질까지 보장하지 않는다.

### 남은 작업

1. 관측 TF 시각 오류의 원인 확인: TF 수신 지연·시계·조회 시각·부하를 구분해야 한다. 검사를 무조건 해제하지 않는다.
2. 유효 깊이 표본이 없는 검출의 처리 정책: 재촬영, 제외, 실패 중 무엇이 맞는지 업무 기준을 정하고 영상 품질과 함께 검증한다. 현재는 검출이 존재하지만 유효 표본이 0이면 실패한다.
3. 전체 3개 Segment 완료 → SECTION_COMPLETE → SUCCESS Result → 관제 UI 저장까지 확인한다.
4. 정상 완료한 뒤 두 번째 Goal이 같은 워커를 재사용하는 실기 확인. 현재 단위 테스트는 통과했지만 최신 보고서는 실패 종료다.
5. 사전 준비 변경 후 Isaac Sim 전체 미션 검증.
6. 관제 최신 규격 반영. 아래 별도 표 참고.
7. 진척 검사와 회전 설정 검토: 현재 SimpleProgressChecker는 10초 안에 0.1m 위치 변화를 요구하고 RPP는 제자리 방향 정렬을 사용한다. 회전만 하면 진척을 인정하지 않는다. 이는 설정상 검토 대상이지 전날 실패 원인 확정은 아니다.
8. Nav2 실패 로그에 error_code 추가. 현재는 status와 error_msg 위주라 메시지가 비면 원인 파악이 어렵다.
9. 실물 RViz의 TF 리맵 보완. 현재 RViz launch에는 initialpose 리맵만 있고 실물 TF 토픽 리맵이 빠져 있다. headless 주행과는 별개다.
10. 워커 로그 회전·임시 데이터 정리와 준비 장애 복구 정책 보강.
11. 최종 패키지 이름·이전 소스·문서 정리. 현재 과거 문서에는 당시 상태가 남아 있어 본 문서의 기준일과 구분해야 한다.

### 통신 문서와의 차이

대조 기준은 확인된 [Confluence 예찰로봇 통신 프로토콜](https://robot3final.atlassian.net/wiki/spaces/3/pages/3375205) 46버전이다. 이후 문서 변경은 이 문서에 자동 반영되지 않는다.

| 항목 | 현재 코드 | 당시 확인한 문서 |
|---|---|---|
| Goal 구역 | section_ids 배열 | section_id 문자열 |
| ID 예 | SEC_01 / SEG_01 | SEC01 / SEC01_G01 |
| Result 구역 | completed_section_ids 배열 | section_id 문자열 |
| Segment 피드백 | 진행 정보, 빈 작업 목록 | 해당 Segment 작업 목록 |
| Section 피드백 | 전체 작업 목록 | 작업 목록 빈 배열 |
| 상태 보고 | 별도 status 미구현 | /scout_01/status 1Hz |
| 작업 조회 | 서비스 미구현 | /scout_01/get_harvest_tasks |
| 복귀 | 설정 초안만 존재 | /scout_01/return_to_station |

로봇과 실제 관제의 `.action`, `.msg`, `.srv`를 함께 맞추고 양쪽을 빌드해야 한다. 문서의 ID 문자열만 바꾼다고 메시지 타입 차이까지 해결되지 않는다.

## 12. 실행 방법과 관찰 지점

### 로봇 실행

PC에서 접속:

```bash
ssh bmany@192.168.0.11
```

로봇에서 실행:

```bash
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source ~/manyfarm/main/farm_project/robot/ros_ws/install/setup.bash
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
unset ROS_LOCALHOST_ONLY

ros2 launch farm_bringup scout.launch.py \
  mode:=real navigation:=true survey:=true \
  rviz:=false headless:=true \
  project_root:=$HOME/manyfarm/main/farm_project
```

`project_root`는 해당 명령을 실행하는 컴퓨터의 프로젝트 경로다. PC와 로봇의 사용자 홈이 달라도 각각 올바른 경로로 해석된다. 런치는 자동으로 Goal을 만들지 않는다.

### 초기 위치 — 도킹·언도킹 미구현 상태의 시험 절차

현재 자동 도킹·언도킹과 스테이션 출발 초기화 절차가 구현되지 않았다. 실물 시험에서는 **언도킹을 마치고 1번 포인트에 나온 상황을 작업자가 수동으로 구성**했다. 로봇을 1번에 배치하고 앞쪽을 2번으로 향하게 한 다음, 별도 명령으로 AMCL 초기 위치를 설정하고 예찰을 진행했다.

initialpose는 위치추정 초기화이며 도킹해제 명령이 아니다. 향후 도킹을 구현하더라도 AMCL 초기화 정책은 별도로 정해야 한다. 현재 launch 재시작 후에는 초기 위치를 다시 확인한다.

운영 순서: 로봇 배치 → bringup → 초기 위치 명령·TF 확인 → 영상 준비 완료 확인 → 기록 시작 → 관제 Goal 전송.


ROS 환경을 불러온 별도 터미널에서 실행한다. 실제 로봇이 **1번에 있고 앞쪽이 2번을 바라볼 때만** 아래 값을 사용한다.

```bash
ros2 topic pub --once /scout_01/initialpose \
  geometry_msgs/msg/PoseWithCovarianceStamped \
  "{header: {frame_id: map}, pose: {pose: {position: {x: 0.519, y: -0.759, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: -0.70710678, w: 0.70710678}}, covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06854]}}"
```

### 관제 대신 테스트 PC에서 명령 보내기

실제 관제와 테스트 스크립트에서 동시에 요청하지 않는다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/manyfarm/main/farm_project/robot/ros_ws/install/setup.bash
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
unset ROS_LOCALHOST_ONLY

python3 ~/manyfarm/main/farm_project/control/scripts/send_scout_area.py \
  --survey-config ~/manyfarm/main/farm_project/robot/config/survey/scout_real.json \
  --section SEC_01
```

영상 준비 완료 로그 이후 전송한다. 테스트 클라이언트의 Ctrl+C는 작업 취소 요청이다.

### 기록

로봇에서 Goal 전송 전에 기록한다.

```bash
mkdir -p ~/scout_debug
cd ~/scout_debug
ros2 bag record \
  /scout_01/cmd_vel_nav /scout_01/cmd_vel \
  /scout_01/odom /scout_01/joint_states /scout_01/sensor_state \
  /scout_01/is_rotating_to_heading \
  /scout_01/tf /scout_01/tf_static /rosout
```

`All requested topics are subscribed. Stopping discovery...`는 토픽 발견 절차를 끝냈다는 뜻이며 기록 중단이 아니다. recorder의 Ctrl+C는 기록 종료이며 로봇 정지 명령이 아니다.

## 13. 기능 확장 시 수정 위치

| 추가할 기능 | 주 수정 위치 |
|---|---|
| 새로운 구역·촬영 노드 | patrol / survey JSON, 그래프 데이터 |
| 실물 로봇 모델·장착값 | robots/<모델> 설정, 기존 드라이버 연결 |
| 새 관제 요청·피드백 규격 | farm_interfaces + ScoutCommunication + 해당 State |
| 상태별 업무 행동 | 해당 State |
| 미션 누적 결과·저장 | ScoutMission / MissionContext |
| 공통 취소·중단 전환 | ScoutStateController |
| 모든 로봇 공통 이동 방식 | farm_navigation |
| 카메라 모델·입력 연결 | VisionRuntime의 어댑터 선택과 영상 워커 |
| 영상 장치 생명주기 | VisionRuntime |
| 과실 ID·윈도우 정책 | survey_core / survey_policy |
| 교통제어 | 공통 경로 실행 경계 + 관제 계약, 아직 미구현 |
| 복귀·도킹 | 별도 통신 계약·State·장치 연결, 아직 미구현 |

## 14. 배포·변경 관리

- PC 소스: `/home/rungmin/manyfarm/main/farm_project`
- 로봇 소스: `/home/bmany/manyfarm/main/farm_project`
- 로봇 접속: `bmany@192.168.0.11`
- ROS Jazzy / Domain 77.
- 최근 XY 수정과 VisionRuntime 변경은 양쪽 소스에 배포했고 로봇 빌드도 완료했다.
- 실행 중 프로세스는 파일 복사만으로 바뀌지 않는다. 변경 코드 적용에는 해당 노드 재시작이 필요하다.
- 기존 `bmany_fleet_ws`, `turtlebot3_ws`, 카메라 venv는 재사용 의존성이다. 새 프로젝트만 복사한다고 다른 PC·로봇에서 자동 설치되는 것은 아니다.
- 이 문서는 코드·기록의 현재 상태를 설명한다. 모든 과거 파일을 삭제해도 된다는 최종 정리 승인이 아니다.

기존 이력: [공통 주행 이관 기록](NAVIGATION_REFACTOR_HISTORY.md), [공통 구조 안내](navigation_common_structure.md), [State 구조 안내](../robot/ros_ws/src/scout_robot/scout_new/STATE_ARCHITECTURE.md). 과거 이력의 '미검증' 또는 이전 카메라 해상도는 해당 작성 시점의 기록이며, 최신 상태는 본 문서의 실기 결과와 현재 설정을 함께 확인한다.
