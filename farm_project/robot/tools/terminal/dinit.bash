#!/usr/bin/env bash
# 로봇에서 사용자 직접 실행. 기존 vinit/launch를 변경하지 않는다.
set -e
terminal_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# PC 정적 확인은 ROS 환경을 설정하거나 로봇에 접속하지 않는다.
if [[ "$#" == 1 && "$1" == '--check' ]]; then
  exec python3 "$terminal_dir/dinit.py" --check
fi
source "$terminal_dir/environment.bash"
exec python3 "$terminal_dir/dinit.py" "$@"
