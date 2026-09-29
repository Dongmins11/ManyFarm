# 사용: source scripts/env.sh sim  또는  source scripts/env.sh real
_farm_mode="${1:-sim}"
if [[ "$_farm_mode" != sim && "$_farm_mode" != real ]]; then
    echo 'mode는 sim 또는 real이어야 합니다.' >&2
    return 2
fi
_farm_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$_farm_root/robot/ros_ws/install/setup.bash" ]]; then
    echo '공통 workspace를 먼저 빌드하세요.' >&2
    return 2
fi
source "$_farm_root/robot/ros_ws/install/setup.bash" || return
if [[ "$_farm_mode" == sim ]]; then
    if [[ ! -f "$_farm_root/sim/ros_ws/install/local_setup.bash" ]]; then
        echo 'sim workspace를 먼저 빌드하세요.' >&2
        return 2
    fi
    source "$_farm_root/sim/ros_ws/install/local_setup.bash" || return
fi
unset _farm_mode _farm_root
