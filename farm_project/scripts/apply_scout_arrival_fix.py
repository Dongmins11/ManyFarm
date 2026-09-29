#!/usr/bin/env python3
"""Persist two Nav2 tolerances without overwriting the user's other tuning."""
import argparse
import copy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAV = ROOT / 'sim/ros_ws/src/farm_sim_config/config/nav2_scout.yaml'


def mapping_value(node, key):
    if not isinstance(node, yaml.MappingNode):
        raise ValueError(f'{key}: YAML mapping required')
    matches = [value for name, value in node.value if name.value == key]
    if len(matches) != 1:
        raise ValueError(f'{key}: expected exactly one YAML entry, found {len(matches)}')
    return matches[0]


def updated_text(text):
    """Use YAML scalar locations, then verify that only the two values changed."""
    before = yaml.safe_load(text)
    expected = copy.deepcopy(before)
    params = expected['controller_server']['ros__parameters']
    if params.get('goal_checker_plugins') != ['general_goal_checker']:
        raise ValueError('This patch expects the scout general_goal_checker configuration')
    checker = params['general_goal_checker']
    if checker.get('plugin') != 'nav2_controller::SimpleGoalChecker':
        raise ValueError('This patch expects nav2_controller::SimpleGoalChecker')
    new_values = {'xy_goal_tolerance': 0.05, 'yaw_goal_tolerance': 0.08}
    old_values = {key: checker[key] for key in new_values}
    checker.update(new_values)
    if expected == before:
        return text, old_values, False
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    for key in ['controller_server', 'ros__parameters', 'general_goal_checker']:
        node = mapping_value(node, key)
    changes = []
    for key, value in new_values.items():
        scalar = mapping_value(node, key)
        if not isinstance(scalar, yaml.ScalarNode):
            raise ValueError(f'{key}: YAML scalar required')
        changes.append((scalar.start_mark.index, scalar.end_mark.index, str(value)))
    after = text
    for start, end, replacement in sorted(changes, reverse=True):
        after = after[:start] + replacement + after[end:]
    if yaml.safe_load(after) != expected:
        raise ValueError('YAML alias/layout would affect other settings; no file was changed')
    return after, old_values, True


def apply(path, backup_dir):
    path = Path(path).expanduser().resolve()
    new_text, old, changed = updated_text(path.read_text(encoding='utf-8'))
    print(f'설정 파일: {path}')
    print(f"xy_goal_tolerance: {old['xy_goal_tolerance']} → 0.05")
    print(f"yaw_goal_tolerance: {old['yaw_goal_tolerance']} → 0.08")
    if not changed:
        print('이미 적용된 값입니다. 빌드와 Nav2 재시작 여부를 확인하세요.')
        return
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = backup_dir / f'nav2_scout_before_arrival_{stamp}.yaml'
    shutil.copy2(path, backup)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(new_text)
        temporary.chmod(path.stat().st_mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f'원본 백업: {backup}')
    print('두 도착 기준만 저장했습니다. farm_sim_config 빌드 후 Nav2를 재시작하세요.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nav-params', type=Path, default=DEFAULT_NAV)
    args = parser.parse_args()
    try:
        apply(args.nav_params, ROOT / 'runs/config_backups')
    except (KeyError, ValueError, OSError, yaml.YAMLError) as exc:
        parser.exit(1, f'설정 적용 실패: {exc}\n')


if __name__ == '__main__':
    main()
