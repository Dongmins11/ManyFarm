# 확정 예찰 Burger 장착 모델 — 2026-10-08

사용자가 확정한 판 중심/기둥/카메라/DUX 고정부/동일 Burger 추가 상판/6개 지지대 형상이다.
`base_footprint`와 `base_link`, IMU는 유지한다. 판 XY 중심의 지면 투영점은 `base_footprint` 대비 (-0.032,0,0)m다.

- `scout_burger.urdf`: PC 단독 미리보기용 전체 모델. 기존 본체·바퀴·라이다·IMU 포함.
- `scout_mount.urdf`: 실물 bringup용 추가 고정 링크만 포함. 기존 기본 TF를 재발행하지 않는다.
- `meshes/`: 기존 Burger 메시와 확정된 상판/고정부/지지대. 상대 파일시스템 대신 `package://farm_real_devices/description/meshes/...` 사용.
- 실행 시 카메라 외부 파라미터의 원본은 `robot/config/robots/burger/devices.json`이다. `farm_real_devices.description.load_description`이 두 URDF에 동일하게 적용한다.
- 기존 `bmany_camera_link` 및 `camera_color_optical_frame` 이름을 유지한다. `camera_color_frame`은 호환 고정 별칭이다. 파이캠은 `picam_frame → picam_optical_frame`이다.

## PC에서 모델만 보기

하드웨어·카메라 드라이버·주행은 실행하지 않는다. 다음은 별도 ROS 도메인이다.

```bash
cd /home/rungmin/Desktop/workspace/main/farm_project
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/setup.bash
ROS_DOMAIN_ID=97 ros2 launch farm_real_devices scout_description.launch.py
```

별도 터미널에서도 같은 ROS 환경과 `ROS_DOMAIN_ID=97`을 사용해 RViz를 열고 Fixed Frame=`base_footprint`, RobotModel의 Description Topic=`/robot_description`으로 선택한다. 운영 도메인에서 전체 preview와 실제 Burger bringup을 동시에 실행하지 않는다.

실물 모드에서는 기존 본체 `/scout_01/robot_description`과 장착 모델 `/scout_01/scout_mount_description`을 별도 RobotModel로 표시한다. TF는 같은 `/scout_01/tf_static`에 서로 다른 child 프레임을 발행한다. 기존 카메라 static publisher는 장착 모델 활성 시 실행되지 않는다. 외부에서 예전 `run_camera_mount.sh`를 따로 실행하지 않는다.

## 확인 범위

사용자 승인 형상이며 동역학용 질량/관성 검증 모델은 아니다. 카메라 하우징은 개략 형상, D435 상단 마운트 메시의 정확한 배치는 미포함이다. 추가 지지대는 원본 최상단 6개 체결축을 사용하고 길이 39.5mm는 판 간격에서 계산한 값이다. DUX 원본의 구멍 배치는 참고용이다.
확정 IMU는 base_link에서 (-0.032,0,0.068)m, RPY=0으로 유지한다. 파이캠 스트리밍/AprilTag 기능을 새로 실행하지 않는다.

## 메시 출처

Burger 본체/바퀴/LDS 메시 및 복제한 상판 원형은 ROBOTIS TurtleBot3 모델이다(https://github.com/ROBOTIS-GIT/turtlebot3, Apache-2.0). PC 저장소의 기존 sim 자산에서 가져왔다. 기존 sim 자산은 수정하지 않았다.
`dux_cross_tee_50x50.stl`은 사용자가 제공한 `dux_cross_tee_50x50_A1mini.3mf`의 형상에서 프린트 베드 이동만 제외한 것이다. 원본을 제조사 인증 CAD로 간주하지 않는다.
