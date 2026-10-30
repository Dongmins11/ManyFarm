#!/usr/bin/env bash
# 사용자 직접 실행: 기존 환경 위에 검증한 복귀 overlay만 추가한다.
set -eo pipefail
if [[ $# -lt 1 ]]; then echo '사용법: launch_corner.bash /절대/복귀_release [--check]' >&2; exit 2; fi
corner_release="$1"
shift
source /home/vic/vmany/main/farm_project/robot/tools/terminal/environment.bash
source /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/install/local_setup.bash
source "$corner_release/install/local_setup.bash"
exec python3 /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.py "$corner_release" "$@"
