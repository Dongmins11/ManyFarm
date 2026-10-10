# 수확 AMCL 라이다 시각 동기 연결

목표는 좌표 기반 FollowPath 주행 중 AprilTag로 위치 추정을 바로잡아 기존 벽 간격을 유지하는 것이다. 이번 변경은 보정 시각 운반만 다루며, 종점 회전·주행 폭·costmap 설정을 추가 변경하지 않는다.

## 수확 태그 보정 라이다 시각 연결 — 2026-10-09

- 승인: 사용자 “그 방법대로 연결해보도록 하자”. 기준 원격 feat/apriltag-localization 7689f3648007c643f01a2dcaee160ae6fcbefcdd와 이후 전달·적용한 HarvestWork 수정본. 사용자 PC의 추가 변경은 해시 검사로 보존한다.
- farm_tag_amcl 패키지가 설치된 nav2_amcl::AmclNode를 상속하고 원본 라이다·필터 처리를 재사용한다. 태그 보정만 별도 토픽으로 받고 첫 유효 라이다 시각까지 odom 이동량을 운반한 뒤 같은 라이다로 필터를 갱신한다. 시스템 AMCL 라이브러리는 수정하지 않는다.
- 기존 task token/sequence/begin_ns/2초 heartbeat lease를 수신부에서도 검사한다. 대기 상한 250ms, 이미지 1초/보정 기준 시각 0.5초 유효시간을 적용하며 만료 시 기존 추정을 유지한다. 취소·작업 종료·수동 초기화·map 수신·비활성화·종료·시각 역행은 대기 요청을 폐기한다. 수동 초기화 후에는 새 작업 토큰이 필요하다.
- 송신부의 보정 계산·공분산·제한값은 유지한다. 발행과 실제 적용을 events.jsonl의 tag_correction_requested / tag_correction_applied로 구분한다. /initialpose는 RViz 등 기존 수동 초기화에 남긴다.
- 공통 scout_navigation.launch.py에는 기본 false인 선택 인자만 추가했다. 수확 real+tag_correction=true+scan_sync 설정에서만 farm_tag_amcl을 선택한다. 예찰/scout_new·공통 주행 알고리즘·지도·20cm 측면 간격·제어기·costmap·도착 허용오차·드라이버는 수정하지 않았다. navigation=false이면 외부 AMCL도 이 수신부여야 한다. 일반 AMCL로 조용히 대체하지 않는다.
- 직접 검사: 태그/launch 단위검사 50개, 수확 검사 60개 PASS. 실제 CMake/ament 빌드·설치 PASS. 실제 ROS/AMCL 검사 22개 PASS(지연 TF, 이동량 1회 반영, 토큰/신원/순서/시각/공분산 거절, 대기·heartbeat 만료, 수동 초기화/맵/비활성화/종료, 동적 토픽 변경 거절).
- 사용자 a2173029 녹화 센서 재생: 요청 12/적용 12, 태그 보정 관련 TF 경고 기존 12→새 코드 0, 오류 0. 수동 초기 위치 지정 경고 1회는 별도로 남아 있다. 별도 SE(2) 계산과 최대 차이 약 2.66e-8m/8.09e-9rad. 이는 수학적 시각 운반의 일치이며 실제 차체 오차 수치가 아니다.
- 검증 환경: Ubuntu24.04 x86_64, Jazzy nav2_amcl1.3.13/rclcpp28.1.22/tf2_ros0.36.23. 정식 패키지 라이브러리를 별도 경로에 풀어 사용했고, bondcpp CMake의 절대 include 경로만 임시 설치 경로로 재배치했다. 실행 라이브러리 코드는 수정하지 않았다. 로봇 arm64의 현재 라이브러리로 빌드·독립 Domain219 검사 후 운영 검증한다.
- 미검증: 새 수신부로 로봇 폐루프 주행, 실제 벽 간격 정확도, 카메라 종료 -11 해결. 녹화 재생을 실물 주행 성공으로 기록하지 않는다. USB latency_timer 영구 변경 없음. commit/push·로봇 동기화·실물 실행은 수행하지 않았다.
- 복원: 실행 종료 후 correction_transport를 initialpose로 되돌리면 수확 launch가 기존 nav2_amcl을 선택한다. 전체 파일 복원은 적용 도구가 기록한 저장소 밖 백업으로 이번 변경만 복원한다. 기존 미커밋 변경을 reset하지 않는다.
- 상세: docs/changes/HARVEST_TAG_SCAN_SYNC_20261009.md. 검증 기록·로봇/PC 적용 및 RViz 명령은 전달 압축의 evidence/와 RUN.md.

## 수신 계약

`tag_localization/control`은 기존 Harvest TagControl JSON을 그대로 사용한다. `tag_localization/correction`은 std_msgs/String JSON이며 protocol=1, robot_id, map_id, token, producer_session, sequence, source_stamp_ns(영상), pose_stamp_ns(운반된 pose의 odom 시각), sent_stamp_ns, frame_id, pose=[x,y,yaw], covariance[36]을 필수로 한다. 수신부 파라미터 tag_correction_protocol=scan_sync_v1, tag_robot_id, tag_map_id는 read-only다. 송신부가 이 값과 tf_broadcast를 확인한 뒤 전송한다.

콜백은 AMCL mutex로 직렬화된다. 대기 요청을 받는 것만으로 필터를 바꾸지 않는다. 스캔 시각이 pose_stamp_ns 이상이고 양쪽 odom TF와 라이다 장착 TF가 존재할 때 `T_map_base(pose) * inverse(T_odom_base(pose)) * T_odom_base(scan)`으로 운반한다. 입력의 3×3 평면 공분산은 보존하며 pf_init 후 원본 laserReceived를 같은 스캔으로 호출한다. 이후 이동은 원본 AMCL motion model로 한 번 반영된다. wall timer의 대기/lease는 steady clock으로 만료되어 ROS 시각 정지 중에도 오래된 요청을 적용하지 않는다.

같은 토큰의 producer 교체, 과거/중복 요청은 거절한다. 수동 초기화·지도 변경·재활성화 후 이전 토큰은 재개되지 않는다. 초기 위치를 다시 지정했다면 진행 중 작업을 끝내고 새 Goal을 보내야 한다. 4096개 작업 토큰 이력 상한에 도달하면 새 토큰을 거절하고 재시작이 필요하다. 파라미터로 scan/map/프레임/초기위치/transform_tolerance를 동적으로 바꿔 콜백을 재연결하는 것은 거절한다. 설정 변경은 재시작 후 적용한다.

## 검증 범위와 한계

실제 ROS 검사는 별도 Domain219/220, LOCALHOST, 가상 시각·지도·TF·라이다로 실행했다. 모터 또는 주행 Goal을 발행하지 않았다. 이전 프로토타입의 bool enable을 운영 코드에 남기지 않았고 실제 task JSON 계약을 시험했다. 녹화 재생에는 사용자의 TF/scan/보정 pose 및 영상 시각을 넣고 heartbeat를 합성했다. 원래 카메라 검출 계산이나 실제 로봇 반응을 다시 실행한 시험은 아니다.

부팅 수동 initialpose는 기존 AMCL 동작을 사용하므로 그 시점의 경고는 이 수정 대상이 아니다. 태그 경고 0회는 한 번의 주행 녹화 재생에서 확인한 결과다. 사용자 로봇 설치본의 버전 차이는 그 장비에서 빌드·검사해야 한다. 실행 로그에서 SENT와 APPLIED를 반드시 구분한다.

공식 참조: https://api.nav2.org/nav2-jazzy/html/amcl__node_8cpp_source.html 의 laserReceived/handleInitialPose. 새 패키지는 설치 헤더/공유 라이브러리와 함께 빌드한다.
