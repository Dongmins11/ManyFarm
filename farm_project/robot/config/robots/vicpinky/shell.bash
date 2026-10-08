# Vic Pinky 실물용 별칭. ROS·드라이버 환경 로딩 후 source한다.
# 입력·반환 인자 없음. 별칭만 정의하며 로봇을 실행하지 않는다.
# 파일 위치에서 farm_project 경로를 계산해 PC·로봇의 사용자 경로 차이를 처리한다.
_vicpinky_project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)" || return 1

# 기존 로그 필터 함수를 재사용하지 않고 현재 별칭 동작을 유지한다.
unset -f bringup 2>/dev/null
alias bringup='ros2 launch vicpinky_bringup bringup.launch.xml'
alias navigation="ros2 launch vicpinky_navigation bringup_launch.xml map:=$(printf '%q' "$_vicpinky_project_root/robot/config/maps/harvest_field_20261007/many_farm.yaml")"

unset _vicpinky_project_root
