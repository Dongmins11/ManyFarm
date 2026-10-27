#!/usr/bin/env bash
set -e
release_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source /home/vic/vmany/main/farm_project/robot/tools/terminal/environment.bash
source "$release_dir/install/local_setup.bash"
exec python3 "$release_dir/terminal.py" "$@"
