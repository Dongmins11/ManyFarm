#!/usr/bin/env bash
set -e
terminal_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$terminal_dir/environment.bash"
exec python3 "$terminal_dir/terminal.py" "$@"
