# AprilTag 주행 인수본의 시뮬 적용

2026-10-13 사용자 요청으로 `apriltag_handoff_20261013_150524_808020`를 현재 작업공간에 병합했다.
아래 내용은 시뮬 전용 추가 조치이며, 실물 담당자의 주행 성공 기록과 이번 검증을 구분한다.

## 동작과 설정

- 수확은 기존 그래프에서 구역 진입 → 작업 직선 이동 → 구역 이탈을 구분한다.
  `harvest_task.json`은 `route_then_follow`와 `approach_planner=graph`를 사용한다.
  실물 노드 번호 대신 `task.yaml`의 16개 구역 진입/이탈 노드를 연결했다.
  실물처럼 진입 목표를 작업 허용 구간 내부에 둔다. 허용 시작은 기존 그래프의 연결된 직선 직전 노드이며,
  SEC01은 허용 시작9002 → 진입20102(0.8m 안쪽) → 이탈20100 순서다.
  태그 검출을 기다리지 않고 작업 이동 중 유효한 관측으로 보정한다.
  이 구간 설정 변경은 수확 ROS launch 재시작 후 적용되며 기존 Goal 명령은 그대로 사용한다.
- Section 필드가 없는 현행 HarvestTask는 목표 XY/yaw와 등록된 작업 직선을 대조해 구역을 고른다.
  하나의 구역으로 결정되지 않는 목표는 거절한다. `window_id`에서 구역을 추측하지 않는다.
- 기존 오른팔 정차선, 속도/RPP 설정, `ARRIVAL_THEN_ARM`, Teacher와 팔 결과 대기는 유지한다.
  직선 작업 구간의 전방 이동 검사는 인수본과 동일하다. 이미 지난 목표나 역방향 목표는 실패한다.
- 태그 보정은 `tag_correction:=true`로 켠다. `all.launch.py`에서 선택한 예찰·수확 모두에 적용하며 기본값은 꺼짐이다.
  켜면 Isaac RGB → `image_proc` 왜곡 보정 → `apriltag_ros` 검출 → 시뮬 Journal → 공통 관측기 →
  `farm_tag_amcl` 라이다 시각 동기 보정으로 연결된다. AMCL이 계속 map→odom TF를 소유한다.
- 태그 100~114는 구역마다 반복된다. 자산 키는 `(section_id, family, tag_id)`이며,
  주행 서버가 작업 이동 단계에서 허용한 구역만 사용한다. 구역 없는 검출·만료된 작업은 보정하지 않는다.
- 시뮬 지도 해시, 240개 실제 배치 좌표, 카메라 K/D/외부변환, namespaced TF를 별도 등록했다.
  실물 좌표와 실물 픽셀 편향 모델은 시뮬에 복사하지 않는다. scene truth는 보정 입력이 아니다.
- 실제 영상 연결 시험에서 detector의 기본 RELIABLE QoS와 시뮬 카메라 BEST_EFFORT가 달라
  영상이 연결되지 않는 문제를 확인하고 `qos_profile=sensor_data`로 맞췄다.
  실제 렌더의 검출 코너를 대조해 태그 검출 좌표축과 종이 표면의 x/z 방향 차이도 자산 생성에 반영했다.

주요 파일:

- `sim/tools/build_tag_localization.py`: `apriltag_map.json`·`harvest.json`·시뮬 지도에서 태그 등록 자산 생성.
- `sim/ros_ws/src/farm_sim_config/config/tag_localization/`: 시뮬 자산·지도 바인딩·관측 한계.
- `sim/tools/rebuild_route_data.py`: 기존 원본에서 수확 진입/이탈·작업 구간 설정도 생성.
- `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/tag_capture.py`: 실제 detector 품질/코너·영상 시각을 Journal로 기록.
- `sim/ros_ws/src/farm_sim_runtime/launch/{harvest,all}.launch.py`: 시뮬 영상 처리와 보정 조합.

## 준비와 실행

ROS Jazzy 환경에서 영상 처리 패키지가 필요하다. 시스템에 없으면 다음 명령으로 설치한다.
공통 `farm_tag_amcl`, `farm_tag_localization` 및 수정한 sim 패키지도 다시 빌드해야 한다.

```bash
sudo apt install ros-jazzy-apriltag-ros ros-jazzy-image-proc
cd ~/main/farm_project
source /opt/ros/jazzy/setup.bash
bash scripts/build.sh sim
source scripts/env.sh sim
```

기존 Isaac 프로세스와 연결해 수확 서버를 실행하는 명령:

```bash
ros2 launch farm_sim_runtime harvest.launch.py \
  project_root:="$PWD" mode:=sim tag_correction:=true
```

기존 전체 실행 명령에도 `harvest:=true tag_correction:=true`를 추가할 수 있다.
`isaac_python`, `vision_python`, Domain ID 등은 기존 [실행 가이드](RUN_GUIDE_20261006.md)를 따른다.
실물 USB 카메라는 시작하지 않는다. 실행 중 영상 기록과 보정 이벤트는 `sim/runs/apriltag/<세션>/`,
중복 보정 잠금은 `sim/runs/locks/`에 남는다.

준비 후 확인할 토픽은 `/harvest_01/apriltag_camera/image_raw`, `camera_info`, `image_rect`, `detections`,
`/harvest_01/tag_localization/events`다. 마지막 토픽의 `tag_correction_applied`가 실제 적용 근거다.
검출 또는 `tag_correction_requested`만으로 AMCL 적용/주행 성공을 판단하지 않는다.

지도·태그 배치·카메라 설정을 변경하면 다음을 실행하고 다시 빌드한다.

```bash
python3 sim/tools/build_tag_localization.py
python3 sim/tools/validate_route_data.py
```

구역/그래프 원본 변경 시에는 기존 `rebuild_route_data.py`로 파생 경로도 재생성한다.
등록 지도 해시가 달라지면 launch가 보정을 거절한다.

## 검증 범위

이번 오프라인 실행:

- 태그 배치·텍스처/카메라 ROS 메시지 4개, Journal 계약 3개, 영상 launch 조립/QoS 2개, 시뮬 태그 자산/기하 3개,
  단계별 구역 설정 3개, 기존 parallel approach 7개, 수확 Action 계약 1개 시험 통과.
- 모든 240개 태그의 이상적인 투영 코너를 실제 공통 관측기에 입력해 시뮬 base pose 복원 확인.
  이는 렌더·검출·센서 잡음·실제 이동 성공 시험이 아니다.
- 16개 구역 목표 3지점씩 고유 선택, 반대 yaw·범위 밖·중복 구역 거절 및 생성 설정 일치 확인.
- `validate_route_data.py`: 연결 그래프·16개 구역·80개 관측점·371개 계획 경로 검사 통과.

이번 실제 영상 시험에서는 Isaac에서 240개 태그를 배치하고 SEC01/ID104 정차 영상을 새로 렌더했다.
그 영상을 실제 ROS rectifier/detector와 Journal에 연결해 10개 검출 기록의 영상/CameraInfo 시각 일치를 확인했다.
수정된 자산으로 계산한 위치 오차는 약 1.44mm, yaw 오차는 약 0.171°였다.
이는 한 위치의 정차 영상 재생 결과이며 이동 중 위치 추정 정확도나 수확 성공률을 의미하지 않는다.
영상 노드를 SIGINT로 종료할 때 upstream rectifier/detector가 `-11`로 끝나는 현상은 남아 있다.
Journal 노드는 정상 종료했고 시험 프로세스는 모두 정리했다. 수신·보정 성공과 종료 안정성은 구분한다.

실제 ROS/Isaac 실행 결과는 같은 날짜의 `sim/docs/CHANGELOG.md`와
`sim/runs/apriltag_integration_20261013/`에 기록한다. 이동 중 보정, 구역 전환 및 팔 수확을 포함한
전체 E2E 완료 여부는 해당 기록을 확인한다. 정차 렌더 또는 합성 ROS 입력 시험만으로 전체 E2E를 통과했다고 보지 않는다.

되돌릴 때에는 이번 변경의 sim 파일·공통 패키지 병합을 함께 되돌린다.
보정만 끌 때는 `tag_correction:=false`를 사용하며, 이는 새 단계별 주행을 이전 방식으로 되돌리는 옵션이 아니다.
Git commit/push는 이 작업에서 수행하지 않았다.

검증 수치 요약은 [검증 JSON](changes/APRILTAG_VALIDATION_20261013.json), 공통 변경 범위는
[통합 기록](../../docs/changes/APRILTAG_HANDOFF_INTEGRATION_20261013.md)에 보존했다.
현재 워크스페이스에는 이미 적용되어 있다. 다른 복사본으로 전달할 변경 파일 묶음은
[패치](../runs/apriltag_integration_20261013/apriltag_integration_20261013.tar.gz)다.
압축 루트는 `farm_project/` 내부이며 기존 예찰 URDF 변경과 실행 로그/임시 의존성은 포함하지 않는다.
다운로드한 파일을 적용하는 명령:

```bash
cd ~/main/farm_project
tar --backup=numbered -xzf "$HOME/Downloads/apriltag_integration_20261013.tar.gz" -C "$PWD"
```

설정·소스 적용 후 위 준비 절차대로 두 workspace를 빌드한다. 공용 문서에는 현재 워크스페이스의
기존 문서 수정도 보존되어 있으므로 다른 복사본의 문서 편집이 있으면 패치의 해당 문서와 병합한다.


## 예찰·수확 공통 주행 보정 연결 — 2026-10-13 후속

사용자가 “예찰도 apriltag 기준으로 주행보정 … 동일 개념의 주행 시스템을 공유”하도록 승인했다.
경로 실행은 기존 `farm_navigation.Navigator`/Nav2를 유지하고, 보정 사용 신호 `TagControl`도
`farm_navigation`으로 공통화했다. 수확의 기존 import 경로는 호환용으로 남긴다.
두 로봇은 동일한 `farm_tag_localization` 관측기와 `farm_tag_amcl` 시각 동기 보정을 사용한다.
태그는 AMCL 위치 보정 입력이며 로봇별 별도 태그 주행 알고리즘을 만들지 않는다.

예찰의 추가 PiCam은 USD `picam_optical_frame/Camera`의 실제 렌더 센서다.
기존 D435 과실 촬영은 유지하며 PiCam RGB·CameraInfo를
`/scout_01/apriltag_camera/{image_raw,camera_info}`로 발행한다.
수확은 기존 `/harvest_01/apriltag_camera/…`를 유지한다.
시뮬 검출 노드 조립도 `farm_sim_runtime/tag_localization.py`를 공유한다.

반복 태그 ID는 로봇별 namespace·캡처 기록·구역 권한으로 구분한다.
예찰은 구역 진입 완료 후 관측 지점 사이 이동에만 해당 section 권한을 열고,
접근/이탈·정지 관측·완료·실패·취소 때 닫는다. 수확의 기존 단계/권한 정책은 유지한다.
로봇별 업무 FSM과 관제 메시지는 그대로다.

PiCam 장착은 URDF를 사용하고 광학값은 명시적인 **시뮬 pinhole 모델**이다.
실물 PiCam 교정값으로 사용하면 안 된다. 예찰은 태그 거리 약1.1m·검은 영역 약48px이므로
관측 거리/영상 면적 조건을 예찰 프로파일에 별도로 둔다. 지도와 계산 코드는 공유한다.
이 연결은 앞서 보류한 수확 진입 허용오차 수정이나 정밀 주행 허용치 확정과 별개다.

빌드 후 기존 시뮬 런치를 종료하고 새 터미널에서 overlay를 source한다.
이전 안내의 `all.launch.py ... scout:=true harvest:=true tag_correction:=true`를 그대로 사용하면
두 로봇에 연결된다. 예찰 단독은 `harvest:=false`로 실행한다.
새 센서 추가는 실행 중인 Isaac에 자동 반영되지 않으므로 Isaac도 재시작해야 한다.
검증 결과와 남은 제한은 PROJECT_STATE의 공통 주행 보정 후속 항목을 따른다.

실제 예찰 정차 영상 검증에서는 검출/관측 연결은 5/5 성공했으나 위치 오차가 약8.1cm,
방향 오차3.4°로 측정돼 축별5cm 시험을 통과하지 못했다. 이 연결만으로 정밀 주행이
확보됐다고 판단하면 안 된다. 이동 시험 전 관측 정확도 보완이 필요하며, 이 수치는
예찰 카메라 한 장면의 관측값으로 수확 근거리 카메라 결과와 구분한다.


## 주행 성능 옵션 — 2026-10-14

기존 `all.launch.py` 주행 명령에 `physics_device:=cpu rviz:=false`를 추가해 CPU 물리를 시험할 수 있다. Isaac 화면이 필요 없으면 `headless:=true`도 추가한다. headless에서도 D435와 두 AprilTag 카메라는 유지된다. 기본 `physics_device:=profile`은 이전 물리 설정이다. CPU 팔 수확/접촉 동등성은 미확인이므로 수확 정책 검증에 무조건 적용하지 않는다.

일반 fleet 세부 계측은 `performance_log:=sim/runs/drive_test/frames.jsonl`을 추가한다(동일 파일은 실행 시 덮어씀). 변경 후 Isaac/ROS를 재시작하고 새 overlay를 source해야 한다. 정량 결과·철회 실험·제한은 PROJECT_STATE §42를 참고한다.

CPU 실제 Nav2 재시험에서는 진입 도착 방향 오차0.1069rad(허용0.05)로 중단됐다. CPU 성능 개선 확인과 주행 성공 검증을 구분하며, 현재 CPU는 비교 시험용 선택이다. 도착 조건을 완화하지 않았다.

같은 목표를 기존 GPU 물리로 실행했을 때는 스테이션→진입 정렬→SEC01 작업 목표까지 `SUCCEEDED`, AprilTag 보정4회 적용을 확인했다(팔OFF/expected0). CPU 전환은 주행 결과 차이의 원인을 확인한 후 판단한다. 현재 운용은 기본 `physics_device:=profile`을 유지한다.

화면이 필요 없을 때의 우선 적용 옵션은 `physics_device:=profile rviz:=false headless:=true`다. 동일 짧은 주행 비교에서 GPU 화면ON17.66→headless18.64FPS로 효과는 작다. CPU29.05/CPU headless36.23FPS는 성능 측정값이며 도착 방향 실패가 남아 운영 권장값은 아니다.


후속 반복 확인(2026-10-14): CPU/GPU 각각2회 추가 실행에서 두 설정 모두1성공/1실패였다. 기존 포함 CPU1/3·GPU2/3이며 GPU에서도 같은 진입 방향 과회전 실패가 발생했다. 위 단회 성공/실패를 CPU 고유 문제나 GPU 주행 안정성 보장으로 해석하면 안 된다. FPS 차이는 반복 확인됐으며, 공통 정렬·정지 응답 분석이 다음 단계다. 운영 기본값/허용치는 이번 검사에서 변경하지 않았다(PROJECT_STATE §43).
