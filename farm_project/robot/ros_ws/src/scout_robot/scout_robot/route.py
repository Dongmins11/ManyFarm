"""Read our local-metre GeoJSON graph; this is not a longitude/latitude converter."""
import json
import math
from pathlib import Path


def load_route(path, node_ids, frame='map'):
    data = json.loads(Path(path).read_text())
    if data.get('type') != 'FeatureCollection':
        raise ValueError('GeoJSON FeatureCollection이 필요합니다.')
    if len(node_ids) < 2 or len(set(node_ids)) != len(node_ids):
        raise ValueError('경로 노드는 중복 없이 2개 이상 지정하세요.')
    points, edges = {}, set()
    for f in data['features']:
        g, p = f['geometry'], f['properties']
        if g['type'] == 'Point':
            if p.get('frame') != frame:
                raise ValueError('경로 좌표계가 map과 다릅니다. 위경도는 변환 없이 사용할 수 없습니다.')
            key = p['id']
            if key in points:
                raise ValueError(f'중복 경로 노드: {key}')
            x, y = map(float, g['coordinates'][:2])
            if not all(map(math.isfinite, (x, y))):
                raise ValueError('경로에 유효하지 않은 좌표가 있습니다.')
            points[key] = (x, y)
        elif g['type'] in ('LineString', 'MultiLineString'):
            edges.add((p['startid'], p['endid']))
    for a, b in zip(node_ids, node_ids[1:]):
        if (a, b) not in edges:
            raise ValueError(f'경로 연결이 없습니다: {a} → {b}')
    coords = [points[i] for i in node_ids]
    result = []
    for index, (x, y) in enumerate(coords):
        a, b = (coords[index], coords[index+1]) if index+1 < len(coords) else (coords[index-1], coords[index])
        dx, dy = b[0]-a[0], b[1]-a[1]
        if math.hypot(dx, dy) < 1e-6:
            raise ValueError('서로 다른 노드가 같은 위치를 가리킵니다.')
        result.append((node_ids[index], x, y, math.atan2(dy, dx)))
    return result
