#!/usr/bin/env bash
# 사용자 직접 실행: 영상 없이 복귀·도킹의 관측/제어/결과를 180초 기록한다.
# 운영 프로세스·초기위치·주행 명령은 보내지 않는다.
set -eo pipefail
source /home/vic/vmany/main/farm_project/robot/tools/terminal/environment.bash
out="/home/vic/vmany/main/farm_project/runs/station_docking_trial/$(date +%Y%m%d_%H%M%S_%N)"
mkdir -p "$out"
echo "DOCK_RECORD_DIRECTORY=$out"
echo '필요 토픽의 Subscribed 표시를 확인한 뒤 미니관제에서 요청하세요. 180초 자동 종료, Ctrl+C로 조기 종료 가능합니다.'
set +e
timeout --foreground --signal=INT 180s ros2 bag record --disable-keyboard-controls --include-hidden-topics -s mcap -o "$out/bag" \
  /harvest_01/scan /harvest_01/scan_filtered /harvest_01/tf /harvest_01/tf_static \
  /harvest_01/odom /harvest_01/amcl_pose /harvest_01/cmd_vel /harvest_01/cmd_vel_normal \
  /harvest_01/received_global_plan /harvest_01/status \
  /harvest_01/station_corner/raw_nav /harvest_01/station_corner/received_global_plan \
  /harvest_01/station_docking/dock_target /harvest_01/station_docking/raw_nav \
  /harvest_01/station_docking/controller_wait /harvest_01/station_docking/handoff_wait_clock \
  /harvest_01/station_docking/local_costmap/costmap_raw \
  /harvest_01/station_docking/local_costmap/costmap_raw_updates \
  /harvest_01/station_docking/local_costmap/published_footprint \
  /harvest_01/station_docking/follow_path/_action/feedback \
  /harvest_01/station_docking/follow_path/_action/status \
  /harvest_01/return_to_station/_action/feedback /harvest_01/return_to_station/_action/status \
  /rosout /parameter_events 2>&1 | tee "$out/recorder.log"
record_exit=${PIPESTATUS[0]}
set -e
echo "기록 종료 코드=$record_exit, 경로=$out"
if [[ -f "$out/bag/metadata.yaml" ]]; then
  ros2 bag info "$out/bag" | tee "$out/bag_info.txt"
else
  echo 'metadata.yaml이 없습니다. recorder.log를 확인하세요.' >&2
  exit 1
fi
[[ "$record_exit" == 0 || "$record_exit" == 124 || "$record_exit" == 130 ]]
