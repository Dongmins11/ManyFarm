"""수확 설정의 공통 기본값과 환경별 데이터를 같은 로더에서 읽는다."""
from pathlib import Path
from typing import Any

from farm_navigation.configuration import merge_mappings, read_mapping, resolve_file


NAVIGATION_KEYS = frozenset({
    'movement_mode', 'approach_planner', 'approach_controller_id',
    'approach_goal_checker_id', 'work_controller_id', 'resolve_section_from_goal_pose',
})


def load_harvest_config(path: str | Path, root: Path) -> dict[str, Any]:
    """공통 기본값 위에 해당 파일의 명시적 설정을 적용한다. 구형 입력도 호환한다."""
    config = read_mapping(path)
    policy_path = config.get('task_navigation_policy')
    if policy_path is None:
        return config
    policy = read_mapping(resolve_file(root, policy_path))
    if policy.get('schema_version') != 1:
        raise ValueError('공통 수확 설정은 schema_version=1이 필요합니다.')
    return merge_mappings(policy, config)
