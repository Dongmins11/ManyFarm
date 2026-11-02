# 영상 전용 종료 실행 파일

기존 image_proc/AprilTag 컴포넌트와 SingleThreadedExecutor를 사용한다. 영상·태그 알고리즘과 파라미터는 바꾸지 않는다. 노드/executor 종료 후 OpenCV 전역 arena를 해제하고 TBB finalize 성공을 확인한 뒤 컴포넌트 라이브러리를 해제한다. 실패는 exit3이며 성공으로 숨기지 않는다.

`robot/tools/tag_camera/pinky_tag_capture_compare.py`의 실제 실행 경로에서 이 패키지의 `rectify_safe`, `apriltag_safe`를 조회한다. 설치 누락 시 카메라 시작 전에 실패하며 원본으로 자동 우회하지 않는다. 공유 컴포넌트 컨테이너에서는 다른 OpenCV 작업이 진행될 수 있으므로 이 종료 방식을 재사용하지 않는다. 시뮬 ROS 영상 launch는 변경하지 않았다.

빌드: 해당 장비의 Jazzy/기존 workspace 환경을 source한 후 `robot/ros_ws`에서 `colcon build --packages-select farm_tag_camera_runtime --executor sequential` 실행, 새 셸에서 workspace `install/setup.bash`를 source한다. 기존 패키지만 선택 빌드하는 배포에서도 이 패키지를 명시적으로 포함해야 한다. x86/ARM 바이너리를 서로 복사하지 않는다.

2026-10-24 v2 후보 실제 영상 120초/939프레임 후 두 실행 파일 종료0을 확인했다. 운영 경로 설치 후에는 카메라를 재기동하지 않았으며 다음 재기동 검증은 별도다. 상세 결과/승인/원복은 docs/changes/HANDOFF_DELAY_AUDIT_20261023.md 참조.
