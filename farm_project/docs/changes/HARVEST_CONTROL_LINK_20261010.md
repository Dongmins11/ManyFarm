# 관제 → Vic Pinky 좌표 이동 연결 준비

기준: 2026-10-10 KST. 수확 `25cdf88`, Control `337c2d5`, Frontend `5909f0d`를 직접 조회했다.
이번 패키지는 적용 준비본이며 사용자 PC·관제 PC·로봇 배포 또는 DDS/실주행 완료 기록이 아니다.

## 변경 범위

- Control: `HarvestTask.action`에 `section_id` 추가, `manual_harvest.py`·`ros_adapter.py`가 보관 중인 Section 전달. 생성 메시지 검사와 관련 테스트 갱신.
- Frontend: 별도 `HarvestTask.action` 동일 갱신, `control_core.py`에서 선택 작업의 Section 전달. 웹은 farm_control 모듈을 사용하지 않으므로 이 저장소도 대상이다.
- main/farm_project: 이번 인계 문서와 상태/결정/변경 이력만 추가. 수확 코드와 이미 설치한 인터페이스 정의는 그대로다.
- 예찰 scout_new, ScoutArea.action, HarvestTask.msg, 수확 주행/태그/지도/제어기/footprint/카메라/모터 설정은 변경하지 않는다. 팔·복귀 Action도 이번 대상이 아니다.

## 고정 계약

수확 Action: `/harvest_01/harvest_task`, `farm_interfaces/action/HarvestTask`.
Goal 선언 순서: `robot_id`, `map_id`, `harvest_task`, **`section_id`**, `timestamp`.
실물 값: `harvest_01`, `many_farm_v1`, `section_id=SEC_01`, `goal_pose.frame_id=map`.
위치 m, yaw rad. 위치는 과실 좌표가 아니라 예찰에서 생성한 로봇 Base 목표다.
원본 task_id/window_id/goal_pose/expected_count를 그대로 전달하며 Window ID를 분해하지 않는다.
현재 SUCCESS는 목표 도착·정지 완료다. 예상 개수는 유지하고 실제 수확량은 0이다.

통신 Domain은 **수확 156 유지**. SUBNET, fastrtps, ROS_LOCALHOST_ONLY 해제.
Control README는 실물77, FULL_PIPELINE은 실물156으로 문서가 상충한다.
Frontend Git 기본값은 real77이고 `MANIFARM_REAL_ROS_DOMAIN_ID`로 변경 가능하다.
현재 Git의 웹 worker와 키보드 관제는 각각 한 ROS Context에서 예찰·수확을 함께 연결한다.
따라서 예찰77·수확156을 동시에 연결하는 브리지가 이미 구현됐다고 해석하면 안 된다.
이번에 관제/예찰 Domain이나 웹 설정·기존 원장을 자동 변경하지 않는다.
관제 수확 프로세스가 이미156이면 그대로 사용한다. 실제 프로세스가77이면 로봇을77로 바꾸지 말고 관제 실행 구성을 맞춘다.
예찰이 별도 Domain을 유지해야 하는 현장 구성이라면 그 전달 경로는 추가 확인 대상이며 이번 패치만으로 다중 Domain 연결을 보장하지 않는다.

## 적용과 빌드

전달 패키지의 apply.py는 저장소별 변경 전/후 SHA256을 검사한다. 이후 수정된 파일이나 모호한 저장소는 덮어쓰지 않는다.
PC 백업 위치는 `/home/eunbi/vmany_backups`로 고정한다. 저장소 내부·로봇에 백업하지 않는다.
자동 commit/push/merge/pull/stash 또는 원장 삭제를 하지 않는다. 기본은 검토만, `--apply`가 있어야 반영한다.
`--auto`는 /home/eunbi 아래 기존 Git 체크아웃만 탐색하며 없는 관제 저장소를 임의 생성하지 않는다.
담당자가 관제 PC에만 소스를 가지고 있다면 `control.patch`/`frontend.patch`를 전달해 대상 커밋과 로컬 변경을 검토·병합한다.
현재 설치 경로와 다른 워크스페이스에 빌드해 놓고 기존 프로세스를 사용하는 실수를 피한다.

Control 터미널 관제를 사용하는 PC (CONTROL_ROOT는 실제 Control Git 저장소 루트):

```bash
source /opt/ros/jazzy/setup.bash
cd "$CONTROL_ROOT"
colcon build --packages-select farm_interfaces farm_control --symlink-install
source install/setup.bash
python3 src/farm_interfaces/examples/verify_interfaces.py
```

웹 관제를 사용하는 PC (FRONTEND_ROOT는 실제 Frontend Git 저장소 루트):

```bash
cd "$FRONTEND_ROOT"
bash ros_ws/build_interfaces.sh
source /opt/ros/jazzy/setup.bash
source ros_ws/install/local_setup.bash
python3 ros_ws/src/farm_interfaces/examples/verify_interfaces.py
```

두 경우 모두 진행 중 작업이 끝난 뒤 관제 프로세스를 종료하고 새 빌드로 재시작한다.
웹에 이전 형식의 QUEUED 수확 작업이 있으면 웹의 수확 중지로 미전송 작업을 PENDING으로 돌린 뒤 새 형식으로 다시 선택한다.
실행/결과 미확정 작업의 Goal·UUID·원장은 변경하거나 삭제하지 않는다.

수확 로봇은 이미 `25cdf88` 형식으로 실물 시험한 설치본을 사용한다. 이번 수확 소스 변경이 없으므로 무조건 재빌드/복사하지 않는다.
아래 설치 타입 검사가 다를 때만 동일 Action 소스와 실제 설치본을 비교한 뒤 인터페이스 및 의존 패키지를 재빌드한다.

## 공통 환경 (관제와 수확 ROS 터미널)

```bash
export ROS_DOMAIN_ID=156
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ROS_LOCALHOST_ONLY ROS_DISCOVERY_SERVER ROS_STATIC_PEERS
```

카메라 capture_session의 별도 환경은 기존 설정을 유지한다.
브리지 없이 두 로봇을 한 관제 Context에서 연동하려면 두 서버가 해당 Context에서 발견되어야 한다.

## 1. PC RViz

PC 프로젝트 ROS install이 없어도 실행 가능하다.

```bash
cd /home/eunbi/vmany/main/farm_project
bash robot/tools/tag_camera/bias_trial/trial.bash rviz
```

기존 도구가 Domain156과 `/tf`, `/tf_static`, `/initialpose`의 `/harvest_01` remap을 설정한다.

## 2. 로봇 실행

PC 새 터미널에서 SSH 접속한다.

```bash
ssh -t vic@192.168.0.12
```

로봇 터미널:

```bash
cd /home/vic/vmany/main/farm_project
python3 robot/tools/vicpinky_motor_latency.py check
bash robot/tools/tag_camera/bias_trial/trial.bash launch on
```

장치·Nav2·카메라·태그 어댑터는 harvest.launch.py 하나로 실행된다. bringup/navigation을 중복 실행하지 않는다.
`launch on`은 기존 검증 모델의 편향 보상을 명시적으로 ON으로 선택한다. 기존 기본 OFF 설정은 바꾸지 않는다.
**launch 후 60초 안에 PC RViz의 2D Pose Estimate로 실제 위치·방향을 지정한다.**
이번 문서는 14번 Goal을 자동 전송하지 않는다. 목표는 관제에서 받은 작업 좌표다.

## 3. 로봇 준비 확인 및 기록 시작

별도 로봇 SSH 터미널:

```bash
cd /home/vic/vmany/main/farm_project
bash robot/tools/tag_camera/bias_trial/trial.bash ready
source /opt/ros/jazzy/setup.bash
source /home/vic/vicpinky_ws/install/setup.bash
source robot/ros_ws/install/setup.bash
export ROS_DOMAIN_ID=156
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ROS_LOCALHOST_ONLY ROS_DISCOVERY_SERVER ROS_STATIC_PEERS
ros2 interface show farm_interfaces/action/HarvestTask
tag_link_run=$(cat /tmp/harvest_bias_trial_path)
test -d "$tag_link_run" && test ! -e "$tag_link_run/bag" || exit 1
ros2 bag record -s mcap -o "$tag_link_run/bag" \
  /harvest_01/tf /harvest_01/tf_static /harvest_01/odom \
  /harvest_01/scan_filtered /harvest_01/amcl_pose \
  /harvest_01/cmd_vel /harvest_01/cmd_vel_nav \
  /harvest_01/received_global_plan /harvest_01/task_events \
  /harvest_01/tag_localization/control \
  /harvest_01/tag_localization/correction \
  /harvest_01/tag_localization/events /rosout
```

타입 검사 출력의 Goal 부분에 `string section_id`가 있는지 확인한다.
관제에서 받은 Goal/Feedback/Result 원문은 관제 events.jsonl/summary.json에 기록된다. 일반 rosbag 토픽 기록만으로 Action Goal/Result 서비스까지 수집됐다고 간주하지 않는다.
기존 trial.bash goal은 14번 시험 명령이므로 이번 관제 연동에서는 실행하지 않는다.

## 4. 관제에서 발견 확인 → Goal 전송

관제의 실제 ROS 설치 환경을 source한 터미널에서 위 공통 환경156을 설정한 뒤:

```bash
ros2 interface show farm_interfaces/action/HarvestTask
ros2 action list -t
ros2 action info /harvest_01/harvest_task
```

Goal의 section_id와 수확 서버 발견을 먼저 확인한다. 두 로봇을 연속 연동할 때는 `/scout_01/scout_area`도 발견되어야 한다.
서버가 발견되지 않으면 반복 Goal 전송 대신 실제 관제 worker Domain·설치 prefix·동일 LAN을 확인한다.

터미널 관제 실행 (실제 Control 워크스페이스에서 위 빌드/source 및 환경156 완료 후):

```bash
ros2 run farm_control harvest_control_node --ros-args \
  -p mode:=scout_only -p task_id:="SCOUT_LINK_$(date +%Y%m%d_%H%M%S)" \
  -p section_id:=SEC_01 -p map_id:=many_farm_v1 -p frame_id:=map \
  -p harvest_robot_id:=harvest_01 -p harvest_action:=/harvest_01/harvest_task \
  -p output_root:=/tmp/manifarm/harvest_link
```

Enter로 예찰 요청 → 성공 Result 수신 → `s`로 좌표·작업 목록 확인 → 실제 통로가 비었음을 확인 → `h`로 한 작업 전송.
목표 좌표/방향은 예찰 원문 그대로며 14번으로 덮어쓰지 않는다. 첫 Result 확인 후 다음 작업도 명시적으로 `h`를 누른다.
실패/취소 부분 목록은 기존 정책대로 전송 보류. `q`/Ctrl+C는 원격 작업 취소가 아니므로 실행 중 정지 명령으로 사용하지 않는다.

웹 관제는 기존 실행 경로를 유지하고 `/api/control?environment=real` 응답의 `identity.domain_id=156`, `map_id=many_farm_v1`, `sections`에 `SEC_01` 포함을 확인한다.
예찰 성공 목록에서 작업 한 건을 선택해 수확 전송한다. 도킹/복귀는 이번 서버 범위 밖이다.
현재 웹 설정이77이라면 환경 전체를 무조건156으로 바꾸지 않는다. 예찰 Domain/원장과 함께 확인한다.
단일 환경을156으로 운용하기로 정해져 있고 기존 원장과도 일치할 때만 `MANIFARM_REAL_ROS_DOMAIN_ID=156`을 사용한다.
Domain/지도 불일치로 원장이 거절되면 원장을 삭제하거나 별도 빈 원장으로 우회하지 않는다.

## 5. 종료·수집·로봇→PC 복사

관제의 최종 Result와 로봇 정지 확인 → bag 터미널 Ctrl+C → launch 터미널 Ctrl+C 순서.
카메라 종료 오류는 별도 기록이며 주행 중 태그 보정 실패와 혼동하지 않는다.
로봇 터미널:

```bash
cd /home/vic/vmany/main/farm_project
bash robot/tools/tag_camera/bias_trial/trial.bash collect
```

PC 터미널:

```bash
mkdir -p /home/eunbi/vmany_backups
tag_link_logs=$(mktemp -d /home/eunbi/vmany_backups/harvest_control_logs_XXXXXX)
scp vic@192.168.0.12:/tmp/harvest_tag_bias_latest.tar.gz "$tag_link_logs/robot.tar.gz"
printf 'PC 로그 보관: %s\n' "$tag_link_logs"
```

관제 터미널 모드는 시작 로그에 출력된 EVIDENCE의 정확한 실행 폴더를 함께 보관한다. 웹은 현재 실행의 web_* 폴더 events.jsonl/summary.json 및 원장 경로를 기록한다.
관제 PC가 별도 장비라면 **그 장비의 실제 SSH 주소와 출력된 정확한 실행 폴더**로 PC 백업 폴더에 scp한다. 주소·실행 폴더를 추측하거나 최신 폴더 전체를 섞지 않는다.

## 검증 결과와 남은 확인

- 직접 오프라인: Control 기존64+추가4 = 68 PASS. Section·원본 좌표·ID·FIFO·실행 중 중복 전송 방지·부분 목록 보류·이동 성공 수량0 처리.
- 직접 오프라인: 웹 실제 ControlQueue의 성공 예찰→선택 수확→Section/좌표/ID 전달→수량0 SUCCESS→동일 작업 재전송 거절 1 PASS.
- 웹 전체 pytest는 이 실행 환경에 pytest가 없어 실행하지 못했다. ROS2도 설치되어 있지 않아 생성 타입/CDR·DDS·Action 왕복 검증 미실행. 도구의 모의 객체 검사는 ROS 직렬화 검사를 대체하지 않는다.
- PC/로봇 설치·빌드·실제 관제 전송·실물 주행은 미실행. 적용 뒤 이를 오프라인 검사와 분리해 기록한다.
- 완료 증거: 동일 task_id/window_id의 원본 예찰 Task와 관제 Goal, 수확 수락/Result를 대조하고 현재 목표 주행 및 태그 적용 이벤트를 확인한다. 단순 SUCCESS 횟수로 벽20cm 유지나 실제 수확 성공을 판정하지 않는다.

## 원복

적용기가 기록한 PC 백업 및 patch를 현재 변경과 비교해 이번 파일만 되돌린다. 관제 인터페이스를 원복하면 의존 노드를 함께 재빌드·재실행한다.
수확 태그 기준 `25cdf88`과 로봇의 동작 코드는 이 패키지로 변경되지 않는다.
