#!/usr/bin/env bash
# 도킹 완료 자세에서 30초 정지 측정. 주행·초기화·카메라 제어 명령은 보내지 않는다.
set -eo pipefail
if [[ "${1:-}" == '--help' ]]; then
  echo '사용법: bash dock_reference.bash — 원하는 도킹 자세에 정지한 뒤 실행(30초 자동 종료)'
  exit 0
fi
source /home/vic/vmany/main/farm_project/robot/tools/terminal/environment.bash
source /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/install/local_setup.bash
out="/home/vic/vmany/main/farm_project/runs/station_docking_reference/$(date +%Y%m%d_%H%M%S_%N)"
mkdir -p "$out"
echo "DOCK_REFERENCE_DIRECTORY=$out"
echo '정지 측정입니다. 주행 명령을 보내지 말고 로봇·주변 물체를 움직이지 마세요.'
set +e
timeout --foreground --signal=INT 30s ros2 bag record --disable-keyboard-controls -s mcap -o "$out/bag" \
  /harvest_01/scan /harvest_01/scan_filtered \
  /harvest_01/tf /harvest_01/tf_static /harvest_01/odom \
  /harvest_01/amcl_pose /harvest_01/cmd_vel \
  /harvest_01/cmd_vel_normal /harvest_01/cmd_vel_nav \
  > "$out/recorder.log" 2>&1
record_exit=$?
set -e
python3 - "$out" "$record_exit" <<'PY'
"""저장된 메시지 수 확인. 정지·도킹 성공 판정은 후속 분석에서 수행한다."""
import json
import sys
from pathlib import Path
import yaml
out = Path(sys.argv[1])
meta = out / 'bag/metadata.yaml'
if not meta.exists():
    raise SystemExit(f'기록 저장 실패: {out / "recorder.log"} 확인')
data = yaml.safe_load(meta.read_text())['rosbag2_bagfile_information']
counts = {v['topic_metadata']['name']: v['message_count'] for v in data['topics_with_message_count']}
required = ['scan', 'scan_filtered', 'tf', 'tf_static', 'odom']
missing = [v for v in required if not counts.get('/harvest_01/' + v, 0)]
result = {'recorder_exit': int(sys.argv[2]), 'message_counts': counts, 'missing': missing,
          'note': '정지 기준 자세 측정. 목표 거리·허용치 미확정. 정지 여부는 odom/scan 후속 분석 필요.'}
(out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False, indent=2))
if missing or int(sys.argv[2]) not in (0, 124, 130):
    raise SystemExit('DOCK_REFERENCE_INCOMPLETE: 위 수신/종료 상태 확인 필요')
print(f'DOCK_REFERENCE_SAVED={out}')
PY
