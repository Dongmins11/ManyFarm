"""기존 교통 구역 정책을 유지하며 변경된 그래프 좌표·엣지 연결을 재생성한다."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'sim/ros_ws/src/farm_sim_config'


def synchronize(directory: Path, maps: Path, *, write: bool = False) -> dict:
    path = directory/'traffic_zones.yaml'
    text = path.read_text()
    data = yaml.safe_load(text)
    original = copy.deepcopy(data)
    graph_data = {}
    changed_features = {}
    changes = {}
    for gid, cfg in data['graphs'].items():
        filename = Path(cfg['source_file']).name
        raw = (maps/filename).read_bytes()
        graph_data[gid] = {str(f['properties']['id']): f for f in json.loads(raw)['features']}
        before = {str(f['properties']['id']): f for f in json.loads((directory/cfg['source_file']).read_text())['features']}
        if set(before) != set(graph_data[gid]):
            raise ValueError('노드/엣지 추가·삭제는 구역 전체 재설계가 필요합니다.')
        changed_features[gid] = {k for k, v in graph_data[gid].items() if before[k] != v}
        if (directory/cfg['source_file']).read_bytes() != raw:
            changes[gid] = (cfg['source_file'], raw)
    if not changes:
        return {'changed_graphs': [], 'changed_zones': []}
    renamed = {}
    changed_zones = []
    for zid, zone in list(data['zones'].items()):
        if zone['kind'] not in ('node', 'edge'):
            continue
        if not any(ref.get('node_id', ref.get('edge_id')) in changed_features[ref['graph_id']]
                   for ref in zone['graph_refs']):
            continue
        coordinates = []
        for ref in zone['graph_refs']:
            feature = graph_data[ref['graph_id']][ref.get('node_id', ref.get('edge_id'))]
            geom, props = feature['geometry'], feature['properties']
            if zone['kind'] == 'node':
                ref['xy_m'] = geom['coordinates'];coordinates.append(ref['xy_m'])
            else:
                ref.update(from_node=str(props['startid']), to_node=str(props['endid']),
                           coordinates_m=geom['coordinates'])
                coordinates.extend(ref['coordinates_m'])
        pad = data['geometry_policy']['padding_radius_m']
        zone['bounds_m'] = [round(min(v[0] for v in coordinates)-pad, 6),
                            round(min(v[1] for v in coordinates)-pad, 6),
                            round(max(v[0] for v in coordinates)+pad, 6),
                            round(max(v[1] for v in coordinates)+pad, 6)]
        new_id = zid
        if zone['kind'] == 'edge' and any(
                (a['from_node'], a['to_node']) != (b['from_node'], b['to_node'])
                for a, b in zip(zone['graph_refs'], original['zones'][zid]['graph_refs'])):
            pairs = {tuple(sorted((int(v['from_node']), int(v['to_node'])))) for v in zone['graph_refs']}
            if len(pairs) != 1:raise ValueError('공유 엣지 끝점 불일치: '+zid)
            new_id = 'sim:E:' + ':'.join(map(str, next(iter(pairs))))
        if zone != original['zones'][zid] or new_id != zid:
            block = yaml.safe_dump({new_id: zone}, sort_keys=False, allow_unicode=True)
            block = ''.join('  '+line if line.strip() else line for line in block.splitlines(True))
            pattern = r'^  '+re.escape(zid)+r':\n.*?(?=^  [^ \n]|^\S|\Z)'
            text, count = re.subn(pattern, lambda _: block, text, flags=re.M|re.S)
            if count != 1:raise ValueError('구역 블록 식별 실패: '+zid)
            renamed[zid] = new_id;changed_zones.append(new_id)
    for old, new in renamed.items():text = text.replace(': '+old+'\n', ': '+new+'\n')
    def next_revision(value: str) -> str:
        prefix, number = value.rsplit('_', 1)
        return prefix+'_'+str(int(number)+1).zfill(len(number))
    for gid in changes:
        old = original['graphs'][gid]['graph_revision'];new = next_revision(old)
        # 현재 양 그래프가 같이 변경되며 미변경 그래프 버전은 보존한다.
        pattern = r'(  '+re.escape(gid)+r':\n.*?    graph_revision: )'+re.escape(old)+r'\n'
        text, count = re.subn(pattern, lambda m: m[1]+new+'\n', text, count=1, flags=re.S)
        if count != 1:raise ValueError('그래프 버전 블록 없음: '+gid)
    text = text.replace('zone_revision: '+original['zone_revision'],
                        'zone_revision: '+next_revision(original['zone_revision']))
    revised = yaml.safe_load(text)
    manifest = json.loads((directory/'source_manifest.json').read_text())
    manifest['zone_revision'] = revised['zone_revision']
    manifest['current_sources'] = []
    for gid, cfg in revised['graphs'].items():
        raw = (maps/Path(cfg['source_file']).name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        manifest['graph_revisions'][gid] = cfg['graph_revision']
        manifest['revision_catalog']['graphs'][gid] = dict(revision=cfg['graph_revision'], source_sha256=digest)
        manifest['current_sources'].append(dict(graph_id=gid, snapshot=cfg['source_file'], sha256=digest,
            path=str((maps/Path(cfg['source_file']).name).relative_to(ROOT))))
    manifest['revision_catalog']['zones'].update(revision=revised['zone_revision'],
        file_sha256=hashlib.sha256(text.encode()).hexdigest())
    if write:
        for snapshot, raw in changes.values():(directory/snapshot).write_bytes(raw)
        path.write_text(text)
        (directory/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return dict(changed_graphs=list(changes), changed_zones=changed_zones,
                zone_revision=revised['zone_revision'], written=write)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(json.dumps(synchronize(CONFIG/'config/traffic', CONFIG/'maps', write=args.write),indent=2))
