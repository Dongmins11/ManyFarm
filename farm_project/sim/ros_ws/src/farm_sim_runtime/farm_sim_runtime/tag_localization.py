"""공통 ROS 태그 입력에 시뮬 시계와 결과 디렉터리만 지정한다."""
from pathlib import Path
from farm_tag_localization.launch_support import ros_capture_actions


def tag_capture_actions(root: Path, profile: dict) -> tuple[list, str]:
    """가상 카메라도 실물 ROS 카메라와 같은 검출·Journal 코드를 실행한다."""
    return ros_capture_actions(root, profile, use_sim_time=True, output_root='sim/runs/apriltag')
