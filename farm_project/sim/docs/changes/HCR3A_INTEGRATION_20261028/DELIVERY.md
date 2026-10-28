# 전달 파일

`hcr3a_integration_20261028_changes.zip`은 이번 공통 추가 파일·시뮬 시험 도구·원본 vendor·관련 문서다. 원본 수치 및 기존 주행 코드는 변경하지 않는다. 현재 문서 파일은 기존 미커밋 기록을 포함한 최신본이다.

`hcr3a_integration_20261028_evidence.zip`에는 단독 시험 5회와 ROS/오프라인 시험 로그, 결과, 카메라 영상, 원본 대응표가 들어 있다. generated USD/빌드 산출물/매 시험 source 복사본은 용량 중복으로 제외했다.

두 압축파일의 내부 경로는 `farm_project/`로 시작한다. 같은 기준 버전에 적용할 때 사용한다. 다른 작업자의 변경이 있는 환경에서는 먼저 zip 목록과 diff를 비교한다. 현재 작업공간에는 이미 적용돼 있어 재해제할 필요 없다.

```bash
unzip -o /path/to/hcr3a_integration_20261028_changes.zip -d /home/ysy/main
unzip -o /path/to/hcr3a_integration_20261028_evidence.zip -d /home/ysy/main
```

별도 시험 빌드:

```bash
cd /home/ysy/main/farm_project
source /opt/ros/jazzy/setup.bash
colcon --log-base sim/runs/hcr3a_intake_20261028/ros/log build \
  --base-paths robot/ros_ws/src/farm_interfaces robot/ros_ws/src/hcr_sorting \
  --build-base sim/runs/hcr3a_intake_20261028/ros/build \
  --install-base sim/runs/hcr3a_intake_20261028/ros/install \
  --packages-select farm_interfaces hcr_sorting
```

물리 통신 시험은 해당 overlay를 source하고 ROS_DOMAIN_ID=13, ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET으로 `sim/tools/probe_hcr_sorting.py`와 원본 `--preloaded --modbus` 실행기를 함께 구동한다. 새 실행 폴더를 사용하고 vendor/이전 보고서를 덮어쓰지 않는다. 정상은28800step, 취소는9000step으로 실행했다. 원본 서버의 실물 기본 IP로 직접 실행하지 말고 probe의 localhost 설정을 사용한다.
