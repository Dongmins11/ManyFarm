#!/usr/bin/env python3
"""AprilTag·수확 연결 사전 검사. 장치 실행·Goal 전송·파라미터 변경 없음."""
from __future__ import annotations
import argparse
import ast
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable
import yaml

MARKER = re.compile(r'^(?:<{7}|={7}|>{7})(?: |$)', re.M)


def check_source(path: Path) -> None:
    """충돌 표시와 Python 구문 오류를 실제 실행 전에 거절한다."""
    source = path.read_text()
    if MARKER.search(source):
        raise ValueError(f'병합 충돌 표시: {path}')
    ast.parse(source, filename=str(path))


def check_parameters(data: object, prefix: str = '') -> None:
    """ROS YAML의 타입 없는 값과 빈 배열을 보수적으로 거절한다."""
    if isinstance(data, dict):
        for key, value in data.items():
            check_parameters(value, prefix + '.' + str(key))
    elif data is None or data == []:
        raise ValueError(f'타입 없는 ROS 파라미터: {prefix}')


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--ros', action='store_true', help='로봇의 설치 모듈·메시지·장치 경로도 읽기 검사')
    options = parser.parse_args(args)
    root = options.project_root.expanduser().resolve()
    src = root / 'robot/ros_ws/src'
    failures = []
    def run(name: str, operation: Callable[[], None]) -> None:
        try:
            operation()
            print('PASS:', name, flush=True)
        except Exception as exc:
            failures.append(name)
            print('FAIL:', name, type(exc).__name__, str(exc), flush=True)
    def sources() -> None:
        paths = [src / 'farm_bringup/launch/harvest.launch.py', src / 'farm_bringup/launch/scout_navigation.launch.py']
        for folder in (src / 'farm_tag_localization/farm_tag_localization',
                       src / 'harvest_robot/harvest_robot', src / 'farm_navigation/farm_navigation',
                       root / 'robot/tools/tag_camera'):
            paths.extend(folder.rglob('*.py'))
        for path in paths:
            check_source(path)
        print('  Python 파일:', len(paths))
    run('실행 소스 문법·충돌 표시', sources)
    # 설치 검사는 source한 모듈을 사용하고 오프라인만 저장소 모듈 경로를 사용한다.
    if not options.ros:
        for package in ('farm_tag_localization', 'farm_navigation', 'harvest_robot'):
            sys.path.insert(0, str(src / package))
    def binding() -> None:
        from farm_navigation.configuration import load_environment, read_mapping
        from farm_navigation.navigation_types import NavigationSettings
        from farm_navigation.route import RouteGraph
        from farm_navigation.arrival import validate_goal_checkers
        from farm_tag_localization.runtime import validate_binding, load_observer
        from harvest_robot.staged_navigation import load_sections
        env = load_environment(root / 'robot/config/environments/harvest_real.yaml', root, 'real', require_survey=False)
        cfg = read_mapping(root / env['tag_localization_config'])
        validate_binding(cfg, env, root)
        if cfg.get('correction_transport') != 'scan_sync':
            raise ValueError('실물 수확 보정 수신부 scan_sync 설정 불일치')
        print('  보정 수신부: farm_tag_amcl / scan_sync_v1')
        load_observer(str(root / env['tag_localization_config']), str(root), 'preflight')
        harvest = read_mapping(root / env['harvest_config'])
        if harvest['completion_policy'] != 'ARRIVAL_ONLY_NO_HARVEST':
            raise ValueError('이 검사는 실물 이동 전용 프로파일용입니다.')
        graph = RouteGraph(env['route_graph'])
        load_sections(harvest, graph)
        settings = NavigationSettings.from_mapping(env['navigation'])
        params = read_mapping(env['nav_params'])['controller_server']['ros__parameters']
        for key, selected in (('controller_plugins', settings.controller_id),
                              ('progress_checker_plugins', settings.progress_checker_id),
                              ('goal_checker_plugins', settings.goal_checker_id)):
            if selected not in params[key]:
                raise ValueError(f'{key}: {selected} 없음')
        if harvest.get('movement_mode') in ('route_then_pose', 'route_then_follow'):
            entry = harvest.get('approach_controller_id', settings.controller_id)
            if not isinstance(entry, str) or entry not in params['controller_plugins']:
                raise ValueError('진입 제어기 미등록: ' + str(entry))
            if entry == 'HarvestApproach':
                expected = dict(params[settings.controller_id], use_fixed_curvature_lookahead=True,
                                curvature_lookahead_dist=0.4, interpolate_curvature_after_goal=True)
                if params[entry] != expected:
                    raise ValueError('진입 전용 RPP 설정이 검증된 작업 프로파일/세 변경값과 다릅니다.')
            work = harvest.get('work_controller_id', settings.controller_id) if harvest.get('movement_mode') == 'route_then_follow' else settings.controller_id
            if not isinstance(work, str) or work not in params['controller_plugins']:
                raise ValueError('작업 제어기 미등록: ' + str(work))
            if work == 'HarvestWork':
                expected = dict(params[settings.controller_id], use_fixed_curvature_lookahead=True,
                                curvature_lookahead_dist=0.4, interpolate_curvature_after_goal=True)
                if params[work] != expected:
                    raise ValueError('작업 전용 RPP 설정이 검증된 기본값/세 변경값과 다릅니다.')
            print('  수확 제어기: 진입=' + entry + ', 작업=' + work + ', 이탈=' + settings.controller_id)
        flat = dict(params)
        for checker in params['goal_checker_plugins']:
            flat.update({checker + '.' + k: v for k, v in params[checker].items()})
        validate_goal_checkers(flat, settings.arrival_tolerance_m, settings.heading_tolerance_rad)
    run('지도 해시·보정 자산·화단 연결·도착 기준', binding)
    def shared_map() -> None:
        from farm_navigation.configuration import read_mapping
        from farm_navigation.route import RouteGraph
        scout = read_mapping(root / 'robot/config/environments/scout_real.yaml')
        harvest = read_mapping(root / 'robot/config/environments/harvest_real.yaml')
        for key in ('map_yaml', 'route_graph'):
            if (root / scout[key]).resolve() != (root / harvest[key]).resolve():
                raise ValueError('예찰/수확 공용 참조 불일치: ' + key)
        if scout['map_id'] != harvest['map_id']:
            raise ValueError('예찰/수확 지도 ID 불일치')
        config = read_mapping(root / harvest['harvest_config'])
        if (config['map_id'] != harvest['map_id'] or config.get('approach_planner') != 'graph'
                or config.get('movement_mode') != 'route_then_follow'):
            raise ValueError('수확 그래프 진입/FollowPath 설정 불일치')
        graph = RouteGraph(root / harvest['route_graph'])
        middle = tuple((a+b)/2 for a,b in zip(graph.nodes[0], graph.nodes[10]))
        graph.plan(middle, graph.nodes[config['sections']['SEC_01']['entry_node']])
        graph.plan(graph.nodes[11], graph.nodes[14])
        print('  수확 목표 14번:', graph.nodes[14], '| map_id:', harvest['map_id'])
    run('예찰/수확 공용 지도·0–10 중간 출발·14번 연결', shared_map)
    route_yaml = root / 'robot/config/harvest/route_server.yaml'
    run('Route Server 파라미터', lambda: check_parameters(yaml.safe_load(route_yaml.read_text())))
    def camera_plan() -> None:
        result = subprocess.run([sys.executable, str(root / 'robot/tools/tag_camera/pinky_tag_capture_compare.py'),
                                 '--trial-label', 'manual_2ms', '--plan'],
                                capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise ValueError(result.stderr.strip())
        plan = json.loads(result.stdout)
        if plan['motion_commands'] or plan['ros_domain_id'] != 178:
            raise ValueError('캡처 전용 실행 계약 불일치')
    run('카메라 plan·캘리브레이션', camera_plan)
    if options.ros:
        def installed() -> None:
            for name in ('harvest_robot.node', 'farm_tag_localization.node', 'farm_tag_localization.capture_session'):
                module = importlib.import_module(name)
                actual = Path(module.__file__).resolve()
                package, leaf = name.split('.')
                expected = src / package / package / (leaf + '.py')
                if actual.read_bytes() != expected.read_bytes():
                    raise ValueError(f'설치본/소스 불일치: {name}: {actual}')
                print('  설치본:', name, actual)
            from farm_interfaces.action import HarvestTask
            from nav2_msgs.action import ComputeRoute
            for cls, fields in ((HarvestTask.Goal, ('robot_id', 'map_id', 'harvest_task', 'section_id', 'timestamp')),
                                (ComputeRoute.Goal, ('start', 'goal', 'use_start', 'use_poses')),
                                (ComputeRoute.Result, ('path', 'error_code'))):
                if not set(fields).issubset(cls.get_fields_and_field_types()):
                    raise ValueError(f'설치된 메시지 계약 불일치: {cls}')
        run('설치 진입점 import·인터페이스', installed)
        def ros_parameters() -> None:
            from rclpy.parameter import parameter_dict_from_yaml_file
            values = parameter_dict_from_yaml_file(str(route_yaml))
            if not values or any(value.value.type == 0 for value in values.values()):
                raise ValueError('ROS 파라미터가 비었거나 타입이 없습니다.')
        run('설치 ROS의 YAML 파싱', ros_parameters)
        def dependencies() -> None:
            from ament_index_python.packages import get_package_prefix
            for package, executable in (('nav2_route', 'route_server'), ('apriltag_ros', 'apriltag_node'),
                                        ('image_proc', 'rectify_node'), ('farm_tag_amcl', 'amcl')):
                path = Path(get_package_prefix(package)) / 'lib' / package / executable
                if not path.is_file():
                    raise FileNotFoundError(path)
            get_package_prefix('rmw_cyclonedds_cpp')
            if not shutil.which('v4l2-ctl'):
                raise FileNotFoundError('v4l2-ctl')
            config = yaml.safe_load((root / 'robot/config/cameras/harvest_tag_capture.yaml').read_text())
            if not os.access(config['device'], os.R_OK | os.W_OK):
                raise PermissionError(config['device'])
            if int(Path('/proc/sys/net/core/rmem_max').read_text()) < 10 * 1024 * 1024:
                raise ValueError('rmem_max가 캡처 요구 최소 10MiB보다 작습니다.')
        run('설치 실행파일·장치 권한·수신 버퍼', dependencies)
    print('검사 결과:', 'FAIL' if failures else 'PASS')
    print('범위: 정적/설치 검사만. ROS 활성화·카메라 종료·실제 보정/이동 검증을 대체하지 않습니다.')
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
