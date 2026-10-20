#!/usr/bin/env bash
# 현재 감독자가 끝나면 체크포인트를 이어받는다. 사용자 systemd 서비스에서 실행한다.
set -e
cd /home/ysy/main/farm_project
source /opt/ros/jazzy/setup.bash
source scripts/env.sh sim
campaign_output=${1:-/home/ysy/main/farm_project/sim/runs/section_campaign_20261019}
mkdir -p "$campaign_output"
exec >> "$campaign_output/supervisor.log" 2>&1
/usr/bin/python3 - "$campaign_output/campaign.lock" <<'PY'
import fcntl
import sys
with open(sys.argv[1], 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
PY
if [[ -e "$campaign_output/STOP" ]]; then
    exit 0
fi
exec /usr/bin/python3 -u sim/tools/run_section_campaign.py --output "$campaign_output" --domain 13 --resume
