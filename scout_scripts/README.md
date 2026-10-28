# 예찰 실행 스크립트

저장소 루트에서 `bash scripts/build.sh`로 PC 빌드 검증 가능. 로봇에서는 ROS Jazzy 및 TurtleBot3 underlay를 준비하고 저장소의 robot_build/install에 빌드한 뒤 사용한다. env.bash는 해당 설치를 읽는다. 별칭과 로봇 배포는 자동 변경하지 않는다.

- `bash scout_scripts/bringup.sh`
- `bash scout_scripts/init19.sh`: 실물이 19번에서 1번 방향일 때 초기 위치 발행
- `bash scout_scripts/zenoh.sh`: 관제 192.168.0.20:7447 연결

D435 Python 환경은 ~/pi_d435_setup/.venv/bin/python, legacy worker 경로는 ~/bmany_fleet_ws/perception_worker이다. 외부 환경은 이 저장소에 포함하지 않는다. 모델과 관측 설정은 farm_project/robot/config/vision/scout_real.json 참조.
