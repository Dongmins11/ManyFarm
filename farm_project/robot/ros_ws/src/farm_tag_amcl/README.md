# 수확 전용 시각 동기 AMCL

수확 real+tag_correction=true에서만 선택한다. 예찰의 AMCL은 기존 nav2_amcl이다. 기본 주행·태그 기하·공분산·지도·컨트롤러 설정을 바꾸지 않는다.

필수 개발 의존성: ROS Jazzy nav2_amcl/nav2_util/rclcpp, Eigen3, nlohmann-json3-dev. 설치 라이브러리를 수정하지 않고 상속한다. CMake/ament_cmake로 빌드한다.

## 하드웨어 없는 실제 ROS 검사

프로젝트 robot/ros_ws에서 빌드·source한 뒤 다음을 실행한다. 검사 결과는 /tmp에 기록하며 모터·카메라·주행 Goal을 시작하지 않는다.

```bash
(
export ROS_DOMAIN_ID=219
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ROS_LOCALHOST_ONLY ROS_DISCOVERY_SERVER ROS_STATIC_PEERS
python3 src/farm_tag_amcl/test/verify_ros.py \
  "$(ros2 pkg prefix farm_tag_amcl)/lib/farm_tag_amcl/amcl"
)
```

상세 계약, 적용·복원, 실제 검사 범위: `docs/changes/HARVEST_TAG_SCAN_SYNC_20261009.md`.
