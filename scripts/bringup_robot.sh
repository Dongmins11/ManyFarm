#!/usr/bin/env bash
# 이전 이름 호환: 기본값은 현재 운송 설정.
set -eo pipefail
exec bash "$(dirname -- "$0")/bringup.sh" transport current "$@"
