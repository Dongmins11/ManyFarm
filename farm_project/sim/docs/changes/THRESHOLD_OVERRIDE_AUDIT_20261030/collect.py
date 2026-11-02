"""정적 설정 감사. 실행 프로세스/설정을 바꾸지 않고 실제 로더로 기본값을 병합한다."""
import dataclasses
import hashlib
import json
from pathlib import Path
import sys
import yaml

root = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
runtime = Path(sys.argv[3]).resolve() if mode == 'sim' else None
for package in ('farm_navigation', 'harvest_robot'):
    sys.path.insert(0, str(root/'robot/ros_ws/src'/package))
from farm_navigation.configuration import read_mapping, merge_mappings, load_nav2_parameters
from farm_navigation.navigation_types import NavigationSettings
from harvest_robot.configuration import load_harvest_config
from harvest_robot.handoff_server_config import build_server_config

groups = {}
sources = {}

def read(path):
    path = Path(path)
    path = path if path.is_absolute() else root/path
    raw = path.read_bytes()
    sources[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
    return yaml.safe_load(raw)

def profile(role, path):
    env = read(path)
    policy = read(env['navigation_policy']) if env.get('navigation_policy') else {}
    nav = merge_mappings(policy, env['navigation'])
    if role == 'scout':
        survey = read(env['survey_config'])
        survey_nav = {k: survey[k] for k in ('base_frame', 'goal_timeout_s', 'arrival_tolerance_m',
            'heading_tolerance_rad', 'settle_s', 'controller_node') if k in survey}
        nav = merge_mappings(survey_nav, nav)
        groups['scout.survey'] = survey
        groups['scout.vision'] = read(survey['vision_config'])
    groups[role+'.navigation'] = merge_mappings(dataclasses.asdict(NavigationSettings()), nav)
    groups[role+'.environment'] = env
    groups[role+'.nav2'] = load_nav2_parameters(root/env['nav_params'], root)
    # scout_navigation.launch.py/transport_navigation.launch.py의 RewrittenYaml 투영.
    def apply_clock(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'use_sim_time':
                    value[key] = mode == 'sim'
                else:
                    apply_clock(item)
    apply_clock(groups[role+'.nav2'])
    read(env['nav_params'])
    nav_input = read(env['nav_params'])
    if 'shared_nav2' in nav_input:
        read(nav_input['shared_nav2'])
    if role in ('scout', 'harvest'):
        tag = read(env['tag_localization_config'])
        groups[role+'.tag'] = tag
        if tag.get('model_file'):
            model = read(tag['model_file'])
            if model.get('shared_model_file'):
                model = merge_mappings(read(model['shared_model_file']), model.get('overrides', {}))
            groups[role+'.tag_model'] = model
        if tag.get('pixel_bias_profile'):
            groups[role+'.pixel_bias'] = read(tag['pixel_bias_profile'])
        if env.get('tag_capture_config'):
            groups[role+'.tag_capture'] = read(env['tag_capture_config'])
        if role == 'scout':
            groups['scout.patrol'] = read(env['patrol_config'])
    if role == 'harvest':
        task = load_harvest_config(root/env['harvest_config'], root)
        groups['harvest.task'] = task
        from harvest_robot.arm_client import configured_arm_settings
        arm = configured_arm_settings(task)
        groups['harvest.arm_action_effective'] = dataclasses.asdict(arm) if arm else {}
        groups['harvest.work_policy_effective'] = {
            'navigation_collision_retry_count': task.get('navigation_collision_retry_count', nav.get('collision_retry_count', 0)),
            'work_path_heading_limit_rad': task.get('work_path_heading_limit_rad'),
        }
        read(env['harvest_config'])
        handoff = read(runtime/'handoff.json' if runtime else 'robot/config/robots/vicpinky/transfer/handoff_fsm.json')
        groups['harvest.handoff'] = handoff
        wall = read(handoff['wall_config'])
        groups['harvest.wall'] = wall
        groups['harvest.monitor'] = read(handoff['monitor_policy'])
        bundle = build_server_config(groups['harvest.nav2'], env['robot_id'], wall,
            NavigationSettings.from_mapping(nav), mode == 'sim', footprint_padding=handoff.get('footprint_padding'))
        groups['harvest.generated_handoff_server'] = bundle
    if role == 'transport':
        groups['transport.precision_profiles'] = read(env['precision_profiles'])
        groups['transport.pickup_targets'] = read(env['pickup_targets_file'])
        groups['transport.destinations'] = read(env['destinations'])
        if env.get('legacy_sites'):
            groups['transport.legacy_sites'] = read(env['legacy_sites'])
    return env

if mode == 'sim':
    profile('scout', runtime/'scout_runtime.yaml')
    profile('harvest', runtime/'harvest_runtime.yaml')
    profile('transport', runtime/'transport_runtime.json')
    for name in ('precision.yaml','sorter.json','fleet.json','source_adaptations.json','pickup_adaptations.json'):
        groups['sim.'+name] = read(runtime/name)
else:
    profile('scout','robot/config/environments/scout_real.yaml')
    profile('harvest','robot/config/environments/harvest_handoff_real.yaml')
    if (root/'robot/config/environments/transport_docking_trial.yaml').exists():
        profile('transport','robot/config/environments/transport_docking_trial.yaml')
    jetson = root/'robot/config/environments/harvest_handoff_jetson_real.yaml'
    if jetson.exists():
        env = read(jetson)
        groups['harvest.jetson_environment'] = env
        groups['harvest.jetson_task'] = load_harvest_config(root/env['harvest_config'], root)

print(json.dumps(dict(groups=groups, sources=sources), ensure_ascii=False, indent=2))
