# Vic Pinky 통합 실행 — 이동 시험 + 선택적 태그 보정

## 범위

예찰 `scout.launch.py`와 같이 `harvest.launch.py` 하나에서 실물 장치·Nav2·수확 이동 서버를 실행한다. `tag_correction:=true`이면 성공한 로봇 내부 카메라/검출 실행본과 태그→AMCL 어댑터도 자동 실행한다. 시작만으로 이동하지 않는다. 목표는 기존 HarvestTask Action으로 받는다.

미션은 `ARRIVAL_ONLY_NO_HARVEST`: 도착 성공을 반환하며 팔 작업은 수행하지 않는다. 전체 수확 FSM 구현 완료가 아니다. [FSM 차이 검토](HARVEST_FSM_GAP_20261007.md)를 참고한다.

## 기존 로봇에서 한 번 준비

- 작업 브랜치: `feat/apriltag-localization`. `project_root`는 저장소 아래 **farm_project**다.
- ROS Jazzy와 `~/vicpinky_ws`의 원래 Vic Pinky 드라이버가 필요하다.
- 카메라 어댑터는 기존 성공 실행본을 그대로 사용한다. `robot/config/cameras/harvest_tag_capture.yaml`의 `script`와 `workspace`를 현재 로봇 경로로 맞춘다. 기본값은 `~/manyfarm_experiments/pinky_tag_amcl_map_20261007/pinky_tag_capture_compare.py`와 기존 캘리브레이션 작업공간이다. Git clone만 한 새 로봇에는 이 파일들이 자동 설치되지 않는다. 카메라 코드를 다시 이식한 것으로 주장하지 않는다.
- 기존 캡처의 CycloneDDS/image_proc/apriltag_ros/OpenCV/v4l2-ctl 의존성이 필요하다. 기존 전용 Domain 178·loopback 설정을 그대로 사용하며 주행 Domain 156 환경은 변경하지 않는다.
- 기존 캡처가 요구하는 수신 버퍼: `sudo sysctl -w net.core.rmem_max=16777216` (재부팅 후 설정이 유지되는지 운영체제 설정에 따라 다름).
- 기존 mini_fleet·별도 Nav2·별도 장치·카메라·보정 실행본을 동시에 켜지 않는다. 이미 같은 장치나 Nav2를 운영 중인 경우에만 devices/navigation 옵션으로 해당 중복 실행을 제외한다.

프로젝트 루트에서 빌드:

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/vicpinky_ws/install/setup.bash"
cd robot/ros_ws
colcon build --symlink-install --packages-up-to farm_bringup harvest_robot
source install/setup.bash
```

## 로봇 메인 실행

아래 명령은 `farm_project` 디렉터리에서 실행한다. 초기 설치 후에는 환경 source와 이 launch로 실행한다. SSH 비밀번호·IP는 패키지에 넣지 않는다.

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/vicpinky_ws/install/setup.bash"
source robot/ros_ws/install/setup.bash
export ROS_DOMAIN_ID=156
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ROS_LOCALHOST_ONLY
ros2 launch farm_bringup harvest.launch.py \
  project_root:="$PWD" mode:=real tag_correction:=true
```

- OFF: 마지막 옵션을 `tag_correction:=false`로 변경.
- OFF에서도 태그 검출 비교 기록: `tag_correction:=false tag_camera:=true`.
- 외부 캡처를 이미 실행한 경우: `tag_camera:=false capture_directory:=/실제/현재/캡처폴더`.
- RViz는 예찰과 동일하게 별도 모니터링 실행이다. 초기 위치는 실제 로봇 위치에 맞게 설정한다. 임의 초기 위치를 자동 주입하지 않는다.
- launch 후 `/harvest_01/harvest_task`에 목표를 전달한다. 임의 좌표를 시작 시 자동 전송하지 않는다.

## 자동 연결과 종료

실물 환경 기본 파일은 `robot/config/environments/harvest_real.yaml`이다. 10/07 실험 지도 원본과 A 시험 경로를 `maps/harvest_field_20261007`에 별도로 보존했다. 예찰용 `maps/many_farm`은 수정하지 않았다. 태그 등록 파일의 지도 SHA-256과 동일함을 검사했다. 실제 로봇에서 새 Git 실행기로 주행 검증했다는 의미는 아니다.

카메라 세션마다 `runs/harvest_tag/<고유세션>`을 만든다. 성공 실행본이 그 아래 만든 현재 `settings.json`/`detections.jsonl`을 찾아 어댑터에 전달한다. 사용자가 매번 폴더를 복사하지 않는다. 이전 실행 폴더를 선택하지 않는다.

- `capture.log`: 카메라/검출 로그.
- `correction.log`: 태그 보정 노드 시작·요청 로그.
- `session.json`: 실제 캡처 경로와 자식 종료 코드.
- 캡처 하위 `amcl_tag_*/events.jsonl`: 보정 요청과 후속 AMCL 관측.

캡처/어댑터 오류는 `TAG_SESSION_ERROR`로 표시하고 해당 자식만 정리한다. Nav2/미션에 취소를 보내지 않는다. 보정 ON 옵션과 실제 보정 요청 발생은 구분한다. 오류가 발생한 주행을 ON 효과 실험으로 집계하지 않는다.

카메라의 전체 PNG 기록 요청은 자동으로 켜지 않는다. 검출 로그와 기존 캡처 자체의 진단 이미지는 저장되지만, 주행마다 전체 영상 저장을 보장하지 않는다. 이전 PNG 저장 큐가 주행/검출을 방해하는 경로를 추가하지 않았다.

Ctrl+C 시 태그 어댑터를 종료하고 기존 캡처 관리자가 카메라→검출→rectify 순서로 정리한다. 본 실행이 만든 프로세스 그룹만 종료한다. Nav2/미션 종료는 기존 launch 및 미션 취소 처리를 따른다.

## 검증과 제한

- 태그 패키지 계약 시험 30개 통과: 자동/외부 캡처, ON/OFF, 실물 장치 선택, 이중 캡처 거절, 현재 세션 폴더 선택, DDS 환경 분리, 자기 자식만 종료, 지도/모델/경로/goal checker 일치 등.
- Python 컴파일 검사. 10→13 경로 계산 및 14번 제외 확인. 실험 지도 YAML/PGM 원본 SHA-256 일치.
- ROS가 없는 환경에서 수행했다. colcon 빌드, 실제 ROS launch/DDS, 카메라 하드웨어, 실물 주행은 아직 미검증이다.
- 새 실물 환경은 기존 FollowPath 모드를 유지한다. 자유 좌표 NavigateToPose로 전환하지 않는다.
