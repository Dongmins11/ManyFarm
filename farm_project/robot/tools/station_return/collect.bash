#!/usr/bin/env bash
# 로봇의 별도 터미널에서 실행한다. 운영 launch·초기위치·주행 명령은 보내지 않는다.
set -eo pipefail
source /home/vic/vmany/main/farm_project/robot/tools/terminal/environment.bash
source /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/install/local_setup.bash
exec python3 /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.py "$@"
