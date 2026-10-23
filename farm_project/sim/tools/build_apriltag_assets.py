"""전달 규격과 task.yaml에서 원본 15개 패턴을 반복하는 태그 배치표를 생성합니다."""
import json
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'sim/assets/apriltag'
CONFIG = ROOT / 'sim/ros_ws/src/farm_sim_config/config'


def build() -> dict:
    """단위 m, map 기준, (section_id, tag_id)로 식별하는 배치표를 저장합니다."""
    task = yaml.safe_load((CONFIG / 'task.yaml').read_text())
    spec = json.loads((ASSETS / 'placement.json').read_text())
    records = []
    pattern_cells = {}
    # Bed_Edge 외측면은 중심에서 0.5m. 1mm는 z-fighting 방지용 오프셋입니다.
    profile = json.loads((CONFIG / 'apriltag_layout.json').read_text())
    for section_id, assignment in profile['sections'].items():
        section = task['sections'][section_id]
        a = np.array(section['survey_geometry']['start_xy_m'], float)
        b = np.array(section['survey_geometry']['end_xy_m'], float)
        tangent = (b - a) / np.linalg.norm(b - a)
        normal = np.array([tangent[1], -tangent[0]])
        center = np.array(section['physical_bed_center_map_m'], float)
        start = center - tangent * np.linalg.norm(b - a) / 2
        start += normal * (profile['bed_half_width_m'] + profile['surface_offset_m'])
        for index, source in enumerate(spec['placements']):
            tag_id = assignment['first_id'] + index
            if source['paper_end_s_mm'] / 1000 > np.linalg.norm(b - a):
                raise ValueError(f'{section_id}: 태그 종이가 bed 끝을 초과합니다.')
            texture = ASSETS / 'textures' / f'tag36h11_ID{tag_id}_64x69mm.png'
            if not texture.is_file():
                raise FileNotFoundError(texture)
            if str(tag_id) not in pattern_cells:
                # 제공 PNG의 실제 36h11 셀을 보존한다. 런타임에는 영상 라이브러리가 필요 없다.
                import cv2
                picture = cv2.imread(str(texture), cv2.IMREAD_GRAYSCALE)
                pixels_per_m = picture.shape[1] / (spec['paper_size'][0]/1000)
                edge_px = spec['black_edge']/1000 * pixels_per_m
                center_x = picture.shape[1]/2
                center_y = picture.shape[0]/2 - (
                    spec['black_center_height']-spec['paper_plane_center_height'])/1000*pixels_per_m
                pattern_cells[str(tag_id)] = [[int(picture[
                    int(center_y-edge_px/2+(row+.5)*edge_px/8),
                    int(center_x-edge_px/2+(column+.5)*edge_px/8)] > 127)
                    for column in range(8)] for row in range(8)]
            xy = start + tangent * source['tag_center_s_mm'] / 1000
            records.append(dict(id=tag_id, family=spec['family'], section_id=section_id,
                bed_prim=section['evaluation_bed_prim'], wall_prim=assignment['wall_prim'],
                black_edge_m=spec['black_edge']/1000,
                paper_size_m=[v/1000 for v in spec['paper_size']],
                tag_center_map_m=[*xy, spec['black_center_height']/1000],
                paper_center_map_m=[*xy, spec['paper_plane_center_height']/1000],
                right_map=[*tangent, 0.], normal_map=[*normal, 0.],
                texture=str(texture.relative_to(ROOT)),
                source_status='provided_pattern'))
    if len({(r['section_id'],r['id']) for r in records}) != len(records):
        raise ValueError('동일 구간 내 태그 ID 중복')
    result = dict(schema_version=1, map_id=task['map_id'], frame_id='map',
        identity_fields=['section_id','id'], requires_active_section=True,
        T_map_world=task['evaluation']['T_map_world'],
        note='시뮬 배치. 실물 설치 완료/독립 측량 좌표가 아님.', tags=records)
    result['pattern_cells'] = pattern_cells
    (CONFIG / 'apriltag_map.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(f"태그 {len(build()['tags'])}개 생성")
