# 주행 담당자 요청: AprilTag 추가 보정 코드 및 실물 카메라 bringup

작성: 2026-10-08 KST. 기준 로컬 main `450bf5f100a81986469a22aba47847d9c2619acc` + 기존 미커밋 변경.
이 문서는 전달용 초안이며 외부로 발송하지 않았다. 원격 최신 소스를 조회한 결과가 아니다.

## 확인 결과

`main/AprilTag/AprilTag_Awall_8m`에는 배치 규격, PNG, 좌표표, 카메라 장착 추정/K/D 및 문서만 있다. 검출·주행 보정 소스, ROS 패키지, launch, 시험 bag은 없다.

로컬 `robot/ros_ws/src`와 `robot/config`의 Python/YAML/JSON/package.xml에서 `apriltag`, `april_tag`, `fiducial`, PCWEB400 관련 구현을 찾지 못했다. 특히 아래 파일에 태그 검출 구독이나 태그 관측 기반 주행 오차 보정 연결이 없다.

- `farm_navigation/farm_navigation/navigator.py`, `nav2_client.py`, `pose_provider.py`, `configuration.py`, `parallel_approach.py`
- `farm_bringup/launch/harvest.launch.py`, `scout_navigation.launch.py`
- `farm_real_devices` 및 현재 환경/로봇 설정

현재 주행은 RouteGraph → Path → Nav2 FollowPath/RPP이며 평행 접근 정렬 기능은 있으나 AprilTag 관측에 의한 보정이 아니다. `harvest.launch.py`의 real 장치 모드는 명시적으로 미구현 오류를 낸다. 따라서 **이번 로컬 인수본에서는 AprilTag 주행 보정이 전달·통합되지 않은 상태**로 판단한다. 다른 브랜치/별도 작업공간의 존재 여부까지 단정하지 않는다.

## 전달을 요청하는 항목

1. 실물 Route 10→13 시험에 사용한 **실행 소스 전체**, 패키지 의존성/버전, 브랜치·커밋, launch, 파라미터, 실행 명령, 사용한 bag/로그. 후보 설정/폐기 코드와 실제 시험 코드를 구별해 달라.
2. 검출기 tag36h11, **검은 경계 tag_size=0.050m**, 영상·CameraInfo 토픽/형식/QoS, 검출 결과 토픽/메시지, corner 및 tag pose 축 정의, 촬영 시각 TF 사용 여부, 중복 검출·pose ambiguity 처리, 관측 품질 필터.
3. 주행 보정 방식: 횡오차/yaw/종방향 중 무엇을 보정하는지, 기준 경로와 태그 벽의 관계, 적용 구간·최대 보정량·주기·게인, RPP·AMCL·odom과의 결합 위치. `cmd_vel` 다중 발행이나 `map→odom` 이중 발행이 발생하지 않도록 소유권과 활성/비활성 전환을 명시해 달라.
4. 구간 진입/이탈, 태그 미검출·오검출·오래된 관측·구간 밖 ID·TF 누락·취소/정지 시 동작 및 fallback. 상태·진단·실패 판단 기준도 필요하다.
5. 실물 태그 ID→면/구간/지도 pose 등록 형식과 원점·회전 정의. sim은 사용자 확정으로 각 면에 100~114를 반복하고 `(section_id, tag_id)`로 식별한다. 현재 활성 구간이 없거나 경계에서 불명확하면 ID만으로 map pose를 선택/보정하면 안 된다. **sim ID를 실물 설치 완료 ID로 해석하지 말아 달라.** 기존 코드는 100~106에 고정돼 있는지, 설정으로 확장 가능한지 확인 요청.
6. PCWEB400 USB 장치 식별(고정 by-id), 사용 드라이버/launch, MJPG 1280×720 요청30fps, ROS 상한10Hz, 수동 노출2ms의 실제 V4L2 설정값·단위, calibration URL 및 실물 TF 발행 주체. 실물 수확 bringup에 넣을 재사용 가능한 장치 실행부가 필요하다.
7. 장착값은 추정값이다. base_footprint가 구동축 중간 바닥점이고 +X 전방/+Y 왼쪽인지 확인해 달라. 예찰로봇 카메라의 부모 프레임, xyz/quaternion, 내부 보정 정보는 별도 전달 요청.

## 시뮬 측 준비된 입력

- `sim/ros_ws/src/farm_sim_config/config/apriltag_map.json`: `map=farm_map_v1`, 240개 태그의 black/paper 중심, 면의 오른쪽/정면 벡터, section/bed, 0.050m 검은 경계. map→world 등록도 포함. 검출 정답을 주행 입력으로 직접 주입하지 않는다.
- 8개 bed의 동·서 16면, 면당15개. SEC01~SEC16 각각 ID100~114를 반복한다. 태그 중심 피치0.564m, 시작0.032m, 끝7.928m, 높이0.264m. 식별키는 `(section_id, tag_id)`이며 사용자 확정 방식이다. 검출기 ID만으로는 전체 지도에서 위치가 유일하지 않다.
- `/harvest_01/apriltag_camera/image_raw` (`sensor_msgs/Image`, rgb8)와 `/harvest_01/apriltag_camera/camera_info` (`sensor_msgs/CameraInfo`), sensor-data QoS, 동일 촬영 시각, 1280×720, 10Hz 목표.
- frame `harvest_01/apriltag_camera_optical_frame`; 논리 base_footprint 기준 translation `[-0.00433822, 0.25046456, 0.26142254]`m. optical quaternion xyzw `[-0.69205081,0.00823666,0.00411433,0.72179007]`. optical 회전 중복 적용 금지.
- K/D: `sim/assets/apriltag/camera_mount_reference.json`. 실제 렌더도 OpenCV pinhole 왜곡 모델에 이 K/D를 적용한다. USB 압축/노출/센서 노이즈를 물리적으로 재현한 것은 아니다.
- 현행 수확 정차선에서 렌즈→태그 면 횡거리 약 **0.2635m**. 자료의 실물 정지 실측0.1815m, 기존 route 목표0.2045m와 다르다. 팔 작업선에 맞춘 현재 수확 경로를 이번 작업에서 변경하지 않았다. 실물 보정 목표 거리를 하드코딩하지 말고 환경 설정으로 선택할 수 있어야 한다.

## 인수 후 검증 조건

우선 정차 영상에서 검출 ID·corner 순서·왜곡 보정·축/단위·TF 시각을 확인한다. 그 다음 양쪽 면과 다수 bed에서 태그가 보일 때/없을 때, 구간 전환·오래된 관측·중복 ID의 안전한 거절을 검증한다. 마지막으로 동일한 초기 오차에서 보정 전후 횡오차/yaw 분포, 경로 완주·정지 오차를 비교한다. 영상에서 태그가 검출됐다는 사실만으로 주행 보정 완료로 판정하지 않는다.

공통 주행 소스 적용은 인수 코드 분석 후 대상 파일·실물 영향·검증 계획을 구체화하여 기존 공통 변경 절차로 진행한다.
