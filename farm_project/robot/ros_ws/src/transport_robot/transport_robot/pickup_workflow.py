"""Harvest transfer profile selection and preflight, independent of map coordinates."""
from dataclasses import replace
import math

def stage_request(request, workflow, stage):
    marker = workflow['initial_marker_id'] if stage == 'approach' else workflow['final_marker_id']
    return replace(request, profile_id=workflow[stage + '_profile'],
                   target_marker_id=marker, docking_marker_id=marker)

def validate_pickup_workflow(profile, device):
    c = profile.get('pickup_workflow', {})
    if not c.get('enabled'):
        raise ValueError('수확 인계 비활성: 티칭 및 거리 설정 필요')
    if c.get('receipt_confirmation') != 'transfer_complete_event':
        raise ValueError('Receipt confirmation must explicitly use TRANSFER_COMPLETE; count remains unknown')
    for key in ('ready_timeout_s', 'transfer_timeout_s'):
        v = c.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('Invalid pickup timeout: ' + key)
    for operation in ('LID_OPEN', 'LID_CLOSE'):
        if not device.supports(operation) or not getattr(device, 'operation_ready', lambda op:device.available())(operation):
            raise ValueError('수령 장치 미연결: ' + operation)
    registry = profile.get('precision_registry', {}).get('profiles', {})
    for stage in ('approach', 'dock', 'clearance'):
        p = registry.get(c.get(stage + '_profile'), {})
        marker = c['initial_marker_id'] if stage == 'approach' else c['final_marker_id']
        if not p.get('configured') or p.get('target_marker_id') != marker or p.get('docking_marker_id') != marker:
            raise ValueError('수확 프로파일 미확정/마커 불일치: ' + stage)
        operation = 'CLEAR' if stage == 'clearance' else 'DOCK'
        if operation not in p.get('allowed_operations', ['DOCK']):
            raise ValueError('수확 프로파일 operation 불일치: ' + stage)
    approach = registry[c['approach_profile']]
    target = profile.get('pickup_targets', {}).get('targets', {}).get(approach.get('pose_target'), {})
    if target.get('status') != 'taught' or target.get('marker_id') != c['initial_marker_id']:
        raise ValueError(f"{c['initial_marker_id']}번 대기 자세 티칭 필요")
    dock = registry[c['dock_profile']]
    for key in ('target_distance_m', 'hard_min_distance_m', 'max_start_distance_m'):
        v = dock.get('lidar_approach', {}).get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('수확 라이다 실측값 필요: ' + key)
    if not dock['lidar_approach']['hard_min_distance_m'] < dock['lidar_approach']['target_distance_m'] < dock['lidar_approach']['max_start_distance_m']:
        raise ValueError('Invalid pickup lidar distance order')
    retreat = registry[c['clearance_profile']].get('relative_backout', {})
    if not isinstance(retreat.get('distance_m'), (int, float)) or isinstance(retreat.get('distance_m'), bool) or not math.isfinite(retreat['distance_m']) or retreat['distance_m'] <= 0:
        raise ValueError('수확 이격 거리 티칭 필요')
    return c
