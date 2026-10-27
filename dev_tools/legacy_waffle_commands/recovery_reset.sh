#!/usr/bin/env bash
set -eo pipefail
if [[ "${1:-}" != "--confirm-clear" ]]; then
  read -r -p '로봇을 도킹 구역 밖으로 옮겼고 기구 연결이 해제됐습니까? [yes 입력]: ' recovery_answer
  [[ "$recovery_answer" == "yes" ]] || { echo '복구 취소'; exit 1; }
fi
source "$HOME/.local/share/waffle_commands/env.bash"
timeout 15s ros2 service call /transport_01/recovery_reset std_srvs/srv/SetBool '{data: true}'
