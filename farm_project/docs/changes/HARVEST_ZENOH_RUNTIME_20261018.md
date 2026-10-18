# 수확 실물 Zenoh 실행 기준 반영 — 2026-10-18

- 승인: 사용자가 현장 성공 통신 설정 반영 및 새 작업 브랜치와 로컬 정합 요청.
- 기준: integration/shared-real-harvest-20261018 / fb5c61a644521518ecd967f4b7014f5a2aaff7cc. 조회 시 main은 2a397da이며 후속 변경 없음.
- 작업 브랜치: feat/harvest-handoff-real-20261018.
- 변경: robot/tools/tag_camera/bias_trial/trial.bash의 source 이후 통신 설정만 변경. Fast DDS/SUBNET 대신 CycloneDDS/Domain 77/LOCALHOST, 기존 DDS 관련 환경변수 6개 해제.
- 주행·지도·태그·인계 FSM·공통 launch·시뮬 설정은 변경하지 않는다. 기존 다른 인계 시험 도구를 Zenoh 시험에 그대로 사용하지 않는다.

## 현장 성공 절차

2026-10-16 사용자 확인 기록이며 이번 변경으로 재실행한 결과가 아니다.
주행 런치 → 초기 위치 설정 → 로봇 Zenoh 브리지 → 관제 표시 확인.
Zenoh 자체의 보편적인 필수 순서로 단정하지 않는다.

로봇 SSH 새 터미널에서 ROS 명령은 먼저 다음을 적용한다.
trial.bash는 자체적으로 이 source 및 통신 설정을 적용하므로 중복 입력할 필요 없다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/vic/vicpinky_ws/install/setup.bash
source /home/vic/vmany/main/farm_project/robot/ros_ws/install/setup.bash
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER
unset ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
```

로봇 재부팅 후에는 `sudo ip link set lo multicast on` 적용.
처음 시작할 때 `test -f /tmp/init_station_newmap.py`로 파일을 확인한다.
없으면 PC(eunbi) 터미널에서 복사:

```bash
scp /home/eunbi/Downloads/harvest_map_patch_20261014/init_station_newmap.py vic@192.168.0.12:/tmp/init_station_newmap.py
```

1. 로봇 SSH 터미널 A: `bash /home/vic/vmany/main/farm_project/robot/tools/tag_camera/bias_trial/trial.bash launch on`
2. 로봇 SSH 새 터미널 B: 위 source/통신 설정 후 `python3 /tmp/init_station_newmap.py`.
   초기 위치 x=0.104, y=-1.105, yaw=87.79도. 10/14 지도와 당시 실제 출발 위치·방향이 같을 때만 사용. 이동 Goal이 아니다.
3. 로봇 SSH 새 터미널 C: 위 source/통신 설정 후 아래 실행.

```bash
zenoh-bridge-ros2dds --domain 77 --ros-localhost-only --no-multicast-scouting -e tcp/192.168.0.20:7447
```

관제 측 수신 브리지도 실행 중이어야 한다. 주소 변경 시 실제 주소를 확인한다.
PC에서 ROS 노드를 직접 실행할 때는 PC 워크스페이스 source와 동일 통신 설정 및 PC 브리지가 필요하다. SSH만 사용하는 PC에는 불필요하다.
별도 bringup/navigation을 중복 실행하지 않는다. 이동 Goal·실제 장치 구동은 별도 요청이다.
설정은 새 프로세스부터 적용되며 이미 실행된 노드에는 반영되지 않는다.
사용자 확인 결과는 /harvest_01/status, IDLE, ready=true, map_id=farm_map_v1 및 관제 표시다.
BATTERY_UNAVAILABLE은 배터리 미측정이며 실제 0%를 뜻하지 않는다.

## 검증과 로컬 반영 상태

- bash -n 통과.
- 기존 Fast DDS/SUBNET/Domain156 및 잔존 DDS 환경변수를 주입한 격리 셸에서 설정 블록 실행: 6개 변수 해제와 CycloneDDS/77/LOCALHOST 확인 통과.
- trial.py에서 통신 환경변수 강제 설정은 발견하지 않았다.
- ROS 빌드·실물 구동·관제 재연결은 미실행. 기존 133개 오프라인 검증을 이번 실물 검증으로 해석하지 않는다.
- 이 작업 환경에는 /home/eunbi/vmany/main 및 /home/vic/vmany/main이 없다. 로봇 SSH는 Network is unreachable로 실패했다.
- 따라서 PC/로봇 브랜치와 미커밋 변경, 실제 현장 trial.bash는 아직 미확인이고 로컬 전환도 미완료다.
- 로컬에서는 git status/branch/HEAD를 먼저 확인하고 fetch 후 새 브랜치로 전환한다. 미커밋 변경이 있으면 중단해 diff를 비교하며 reset/clean/자동 stash로 덮어쓰지 않는다.
- 이번 변경만 되돌릴 때는 trial.bash 통신 블록의 diff만 역적용한다. 현장 CycloneDDS 설정이나 인계 저널을 임의 삭제하지 않는다.
