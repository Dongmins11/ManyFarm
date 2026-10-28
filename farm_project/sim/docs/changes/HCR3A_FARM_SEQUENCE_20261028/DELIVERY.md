# 전달 및 실행

이 자료는 main ea25693 위의 기존 미커밋 HCR/운송 통합 작업을 전제로 한다. 공통 `farm_interfaces`/`hcr_sorting` 인수와 `sim/vendor/hcr3a_20261008` 원본 전달본이 먼저 있어야 한다.

변경 파일 ZIP에는 이번에 건드린 파일의 **현재 전체 내용**을 담는다. 같은 파일에 있던 이전 미커밋 변경을 보존한 스냅샷이며 그 변경까지 삭제/원복하지 않는다. 별도 환경에 덮어쓰기 전 로컬 차이를 확인한다.

```bash
cd ~/main/farm_project
unzip -o ~/Downloads/hcr3a_farm_sequence_20261028_changes.zip -d .
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/local_setup.bash
source sim/runs/hcr3a_intake_20261028/ros/install/local_setup.bash
cd sim/ros_ws
colcon build --packages-select farm_sim_runtime farm_sim_devices
cd ../..
source sim/ros_ws/install/local_setup.bash
source sim/runs/hcr3a_intake_20261028/ros/install/local_setup.bash
ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET \
  python3 sim/tools/run_sorter_cycle_trial.py sim/runs/hcr_farm_new_run --sorting
```

선별 overlay 경로는 이번에 실제 빌드/검증한 경로다. 다른 PC는 앞선 HCR 전달 문서대로 `farm_interfaces`, `hcr_sorting`을 먼저 빌드하고 그 install을 source해야 한다. `--prepare-only`는 실행 설정만 생성한다. `--dock-entry-fixture`는 전체 접근 시험과 구분되는 도킹 직전 초기 배치다.

ROS 연결: `/transport_01/bucket_unload`, `/transport_01/unload_event`, `/sorter_01/sort_batch`, `/sorter_01/status`, `/transport_01/return_to_station`. 시험기의 가상 하역 Trigger가 같은 세션의 `sorting/deposit_request.json`을 쓰고 농장 루프가 실제 과실 투입 결과를 회신한다. Frontend의 선별 자동 워커를 새로 구현한 것은 아니다.

기존 농장 실행을 유지하려면 fleet의 `sorter_config`를 지정하지 않으면 된다. 원본 농장 USD를 수정하지 않으므로 씬 파일 복구는 필요 없다. TF 발행 수정 원복은 이 작업 변경분만 되돌리고 앞선 TF 선전달/기계장치 통합 변경을 제거하지 않아야 한다. 원복하면 이번 미래 TF 현상이 재발할 수 있다.

성공/실패·제한은 REVIEW.md와 원시 로그를 기준으로 한다. 커밋·푸시하지 않았다.
