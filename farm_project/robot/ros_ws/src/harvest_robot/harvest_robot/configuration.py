"""수확 설정의 공통 기본값과 환경별 데이터를 같은 로더에서 읽는다."""
from pathlib import Path
from dataclasses import replace
import math
import json
from farm_navigation.navigation_types import NavigationSettings
from .transfer_rotation import rotation_parameters
from .discharge_client import discharge_parameters
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
    if policy_path is not None:
        policy = read_mapping(resolve_file(root, policy_path))
        if policy.get('schema_version') != 1:
            raise ValueError('공통 수확 설정은 schema_version=1이 필요합니다.')
        config = merge_mappings(policy, config)
    transfer_parameters(config)
    return config


def transfer_parameters(config: dict[str, Any]) -> dict[str, Any]:
    """환경별 인계 연결을 공통 ROS 파라미터로 변환한다. 미설정 환경은 OFF다."""
    values = config.get('transfer', {})
    if not isinstance(values, dict) or type(values.get('enabled', False)) is not bool:
        raise ValueError('transfer는 객체, enabled는 bool이어야 합니다.')
    rotation = rotation_parameters(values)
    discharge = discharge_parameters(values)
    services = values.get('device_services', {})
    source = values.get('load_source', 'external_topic')
    threshold = values.get('request_count', 0)
    if source not in ('external_topic', 'arm_feedback'):
        raise ValueError('transfer.load_source는 external_topic 또는 arm_feedback이어야 합니다.')
    if type(threshold) is not int or not 0 <= threshold <= 2147483647:
        raise ValueError('transfer.request_count는 0 이상의 int32여야 합니다.')
    if source == 'arm_feedback' and values.get('loaded_count_topic', ''):
        raise ValueError('팔 누적과 외부 적재 Topic은 동시에 선택할 수 없습니다.')
    if not isinstance(services, dict):
        raise ValueError('transfer.device_services는 객체여야 합니다.')
    result = {'transfer_discharge_mode': discharge['discharge_mode'],
              'transfer_discharge_action': json.dumps(discharge['discharge_action']),
              'transfer_rotation_mode': rotation['rotation_mode'],
              'transfer_rotation': json.dumps(rotation['rotation']),
              'transfer_enabled': values.get('enabled', False),
              'transfer_load_source': source,
              'transfer_request_count': threshold,
              'transfer_device_services': json.dumps(services),
              'transfer_capacity_count': values.get('capacity_count', 0),
              'transfer_loaded_count_topic': values.get('loaded_count_topic', '')}
    for name, default in (('stage_timeout_s', 120.0), ('stop_timeout_s', 10.0)):
        value = values.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('transfer.' + name + '는 유한한 양수여야 합니다.')
        result['transfer_' + name] = float(value)
    if 'journal_path' in values:
        result['transfer_journal_path'] = values['journal_path']
    return result


def approach_navigation_settings(settings: NavigationSettings, config: dict[str, Any],
                                 controller_id: str, goal_checker_id: str) -> NavigationSettings:
    """진입 전용 선택값만 적용한다. 미지정 환경의 작업·이탈 설정은 보존한다."""
    distance = config.get('approach_max_start_distance_m', settings.max_start_distance_m)
    if (isinstance(distance, bool) or not isinstance(distance, (int, float))
            or not math.isfinite(distance) or distance <= 0):
        raise ValueError('approach_max_start_distance_m는 유한한 양수여야 합니다.')
    return replace(settings, controller_id=controller_id, goal_checker_id=goal_checker_id,
                   max_start_distance_m=float(distance))
