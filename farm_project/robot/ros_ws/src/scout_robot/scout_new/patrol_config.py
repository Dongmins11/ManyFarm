"""관제 Section ID를 지도 노드 기반 관측 순서로 변환합니다. 복귀는 포함하지 않습니다."""
from copy import deepcopy
from typing import Any
from farm_navigation.route import RouteGraph


def apply_patrol(config: dict[str, Any], patrol: dict[str, Any], graph: RouteGraph) -> dict[str, Any]:
    """베드 좌표 기준은 유지하고 별도 JSON의 관측 순서만 적용합니다."""
    for key in ('robot_id', 'map_id'):
        if patrol.get(key) != config[key]:
            raise ValueError(f'순찰 설정 {key} 불일치')
    result = deepcopy(config)
    sections = {}
    for section_id, entry in patrol['sections'].items():
        source = entry.get('bed_section_id', section_id)
        if source not in config['sections']:
            raise ValueError(f'{section_id}: 베드 설정 {source}가 없습니다.')
        if entry.get('on_complete') != 'WAIT_FOR_COMMAND':
            raise ValueError('노드 순찰은 완료 후 명령 대기만 지원합니다.')
        segments = entry['segments']
        if not segments or len({item['segment_id'] for item in segments}) != len(segments):
            raise ValueError('관측 Segment는 비어 있거나 ID가 중복될 수 없습니다.')
        for item in segments:
            if not item['segment_id'] or item['observation_node_id'] not in graph.nodes:
                raise ValueError('유효한 Segment ID와 그래프 노드가 필요합니다.')
        bed = deepcopy(config['sections'][source])
        bed['patrol_segments'] = deepcopy(segments)
        bed['finish_at'] = 'last_segment'
        sections[section_id] = bed
    result['sections'] = sections
    return result


def patrol_design(bed: Any, graph: RouteGraph) -> dict[str, Any]:
    """고정 촬영 지점입니다. 연속 베드 전체의 영상 커버리지를 보장한다는 뜻은 아닙니다."""
    segments = []
    previous = -float('inf')
    for item in bed.cfg['patrol_segments']:
        xy = graph.nodes[item['observation_node_id']]
        offset, normal, _ = bed.local([*xy, 0.0])
        if abs(normal) > .01 or not -.000001 <= offset <= bed.length + .000001 or offset <= previous:
            raise ValueError('관측 노드는 베드 주행 직선 위에 진행 순서대로 있어야 합니다.')
        segments.append(dict(item, offset_m=max(0., min(bed.length, offset)), position_map_m=list(xy)))
        previous = offset
    return {'segments': segments, 'stops_s_m': [item['offset_m'] for item in segments],
            'segmentation_mode': 'graph_nodes', 'finish_at': 'last_segment',
            'completion_behavior': 'WAIT_FOR_COMMAND', 'coverage_policy': 'fixed_capture_points'}
