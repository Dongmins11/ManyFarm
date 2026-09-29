#!/usr/bin/env python3
"""Install GeoJSON survey sections while preserving existing device/vision tuning."""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/scout_robot'))
from scout_robot.route import load_route

CONFIG = 'sim/ros_ws/src/farm_sim_config/config/scout_survey.json'
GRAPH = 'sim/ros_ws/src/farm_sim_config/maps/graph.geojson'


def configure(data, graph, route_file=GRAPH):
    """Return a new config; existing per-section segmentation and tuning win."""
    sections = graph['survey_sections']
    expected = [f'BED_{n:02d}' for n in range(1, 17)]
    if list(sections) != expected:
        raise ValueError('graph.geojson must define BED_01 through BED_16 in order')
    result = copy.deepcopy(data)
    current = result['sections']
    template = current['BED_01']
    for sid, geometry in sections.items():
        new = sid not in current
        section = copy.deepcopy(template if new else current[sid])
        section.update(copy.deepcopy(geometry))
        section['route_file'] = route_file
        if new:
            # A manual BED_01 capture list must not carry BED_01 IDs into another side.
            section['segmentation'] = {'mode': 'auto', 'id_prefix': sid + '_S',
                'overlap_fraction': template.get('segmentation', {}).get(
                    'overlap_fraction', result.get('overlap_fraction', .15))}
        else:
            section.setdefault('segmentation', {'mode': 'auto', 'id_prefix': sid + '_S',
                'overlap_fraction': result.get('overlap_fraction', .15)})
        section.setdefault('finish_at', 'last_segment')
        current[sid] = section
    # Keep unrelated user-defined sections, after the standard 16.
    result['sections'] = {sid: current[sid] for sid in expected + [s for s in current if s not in expected]}
    notes = [n for n in result.get('notes', []) if not n.startswith('BED_01 is a temporary')]
    note = 'BED_01..BED_16 are survey sides of eight physical beds; evaluation_bed_prim identifies the physical bed. Each side completes and publishes its own batch.'
    if note not in notes: notes.append(note)
    result['notes'] = notes
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / CONFIG)
    args = parser.parse_args()
    path = args.config.expanduser().resolve()
    try:
        graph = json.loads((ROOT / GRAPH).read_text(encoding='utf-8'))
        for section in graph['survey_sections'].values():
            load_route(ROOT / GRAPH, section['node_ids'])
        data = json.loads(path.read_text(encoding='utf-8'))
        updated = configure(data, graph)
        if updated != data:
            backups = ROOT / 'runs/config_backups'
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / ('scout_survey_before_16beds_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f') + '.json')
            shutil.copy2(path, backup)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                        prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(json.dumps(updated, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
                temporary.chmod(path.stat().st_mode)
                temporary.replace(path)
            finally:
                if temporary is not None: temporary.unlink(missing_ok=True)
            print(f'설정 백업: {backup}')
        for sid, s in graph['survey_sections'].items():
            direction = '-Y / 카메라 +X' if s['survey_side'] == 'west' else '+Y / 카메라 -X'
            print(f"{sid}: {s['evaluation_bed_prim'].split('/')[-1]} {s['survey_side']} / {direction}")
        print('16개 예찰 구역 적용 완료. 빌드 후 bringup과 예찰 서버를 다시 실행하세요.')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'적용 실패: {exc}\n')


if __name__ == '__main__': main()
