"""원본 과실 삼각면으로 support hull-only 경고를 좁히는 독립 QA."""
from pathlib import Path
import hashlib
import json
import os
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
ROOT = RUN.parents[2]


def export():
    from pxr import Usd, UsdGeom
    asset = ROOT / 'sim/assets/envs/output/farm_with_plants_v5.usd'
    stage = Usd.Stage.Open(str(asset))
    evidence = json.loads((RUN / 'settings/06_07_motion_evidence.json').read_text())
    out = {}
    for fruit in evidence['fruits']:
        prim = stage.GetPrimAtPath(fruit['source'])
        inv = np.linalg.inv(np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T)
        points = []; triangles = []
        for child in Usd.PrimRange(prim, Usd.TraverseInstanceProxies()):
            if not child.IsA(UsdGeom.Mesh):
                continue
            mesh = UsdGeom.Mesh(child)
            m = inv @ np.asarray(UsdGeom.Xformable(child).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
            p = np.asarray(mesh.GetPointsAttr().Get(), float)
            offset = len(points)
            points.extend((p @ m[:3, :3].T + m[:3, 3]).tolist())
            indices = list(mesh.GetFaceVertexIndicesAttr().Get()); cursor = 0
            for count in mesh.GetFaceVertexCountsAttr().Get():
                face = indices[cursor:cursor+count]; cursor += count
                triangles.extend([[offset+face[0], offset+face[j], offset+face[j+1]] for j in range(1, count-1)])
        out[fruit['source']] = {'points': points, 'triangles': triangles}
    output = {'source': str(asset.relative_to(ROOT)), 'source_sha256': hashlib.sha256(asset.read_bytes()).hexdigest(), 'meshes': out}
    (HERE / '06_07_actual_fruit_triangles.json').write_text(json.dumps(output) + '\n')


def clipped_triangle(triangle, margin):
    polygon = list(triangle)
    for axis in range(3):
        for sign in (-1, 1):
            result = []
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                da = sign*a[axis] - (.5-margin[axis]); db = sign*b[axis] - (.5-margin[axis])
                if da <= 0:
                    result.append(a)
                if (da <= 0) != (db <= 0):
                    result.append(a+(b-a)*da/(da-db))
            polygon = result
            if not polygon:
                return False
    return True


def check():
    from scipy.spatial.transform import Rotation
    audit_path = HERE / '06_07_independent_geometry_audit.json'
    audit = json.loads(audit_path.read_text())
    evidence_path = RUN / 'settings/06_07_motion_evidence.json'
    request_path = RUN / 'settings/06_07_transport_sorting.json'
    evidence = json.loads(evidence_path.read_text())
    request = json.loads(request_path.read_text())
    topology_path = HERE / '06_07_actual_fruit_triangles.json'
    topology = json.loads(topology_path.read_text()); meshes = topology['meshes']
    box_path = HERE/'06_07_actual_station_boxes.json'
    mesh_point_path = ROOT/'sim/runs/presentation_video_revision_v3_20261104/settings/handoff_mesh_points.json'
    mesh_points = {x['source']: x['root_local_points'] for x in json.loads(mesh_point_path.read_text())}
    robot_path=HERE/'06_07_actual_robot_cubes.json'
    joint_path=RUN/'settings/06_07_source_joint_geometry.json'
    robot=json.loads(robot_path.read_text()); joints=json.loads(joint_path.read_text())
    source_paths = [request_path, evidence_path, audit_path, topology_path, box_path, mesh_point_path, ROOT/topology['source'],robot_path,joint_path]
    source_hashes = {os.path.relpath(p, RUN): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    point_delta = max(float(np.max(np.abs(np.asarray(m['points'])-np.asarray(mesh_points[s])))) for s,m in meshes.items())
    boxes = {b['path']: b for b in json.loads(box_path.read_text())['boxes']}
    sources = {f['id']: f['source'] for f in evidence['fruits']}
    T=np.asarray(evidence['station_transform']);invT=np.linalg.inv(T)
    base_arm=invT@np.asarray(request['base']['placements']['/World/HCRRobot']['matrix'])
    def moving_box(event):
        role='arm' if event['obstacle'].startswith('/hcr3a_functional/') else 'transport'
        cube=next(c for c in robot[role]['visual_cubes'] if c['path']==event['obstacle'])
        frame=request['keyframes'][event['frame']];q=frame['state']['joints']
        by_child={j['b']:(n,j) for n,j in joints[role].items()}
        def rec(path):
            if path not in by_child:return np.asarray(robot[role]['initial_links'][path])
            name,j=by_child[path];d=np.eye(4);value=q.get(name,0.)
            if j['kind']=='PhysicsRevoluteJoint':d[:3,:3]=Rotation.from_rotvec(np.eye(3)[j['axis']]*value).as_matrix()
            elif j['kind']=='PhysicsPrismaticJoint':d[j['axis'],3]=value
            return rec(j['a'])@np.asarray(j['f0'])@d@np.linalg.inv(np.asarray(j['f1']))
        base=base_arm if role=='arm' else invT@np.asarray(frame['state']['placements']['/World/transport_robot']['matrix'])
        m=base@rec(cube['body'])@np.asarray(cube['body_relative_matrix']);m[:3,:3]*=cube['size']
        return m
    events = audit['conservative_hull_only_events']
    blocking = []; worst = 0.
    for event in events:
        frame = evidence['frames'][event['frame']]
        pose = np.asarray(frame['fruit_states'][event['fruit']]['station_local_matrix'])
        mesh = meshes[sources[event['fruit']]]
        m=np.asarray(boxes[event['obstacle']]['matrix']) if event['obstacle'] in boxes else moving_box(event)
        inv = np.linalg.inv(m)
        p = np.asarray(mesh['points']) @ pose[:3, :3].T + pose[:3, 3]
        p = p @ inv[:3, :3].T + inv[:3, 3]
        triangles = p[np.asarray(mesh['triangles'])]
        near = np.all(triangles.max(1) > -.5, axis=1) & np.all(triangles.min(1) < .5, axis=1)
        dimensions = np.linalg.norm(m[:3, :3], axis=0)
        depth = 0.
        for tri in triangles[near]:
            lo, hi = 0., float(min(dimensions)/2)
            if not clipped_triangle(tri, np.zeros(3)):
                continue
            for _ in range(20):
                mid = (lo+hi)/2
                if clipped_triangle(tri, mid/dimensions): lo = mid
                else: hi = mid
            depth = max(depth, lo)
        worst = max(worst, depth)
        if depth > .00005:
            blocking.append({**event, 'actual_triangle_max_penetration_m': depth})
    result = {'request_sha256': audit['request_sha256'], 'evidence_sha256': source_hashes['settings/06_07_motion_evidence.json'],
        'audit_sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest(), 'topology_sha256': hashlib.sha256(topology_path.read_bytes()).hexdigest(),
        'request_matches_independent_audit': source_hashes['settings/06_07_transport_sorting.json'] == audit['request_sha256'],
        'evidence_matches_independent_audit': source_hashes['settings/06_07_motion_evidence.json'] == audit['evidence_sha256'],
        'source_hashes': source_hashes, 'all_sources_unchanged_at_check_end': all(hashlib.sha256((RUN/p).read_bytes()).hexdigest()==h for p,h in source_hashes.items()),
        'original_mesh_points_max_delta_m': point_delta,
        'topology_source_unchanged': hashlib.sha256((ROOT/topology['source']).read_bytes()).hexdigest()==topology['source_sha256'],
        'hull_only_station_events_checked': sum(e['obstacle'].startswith('/World/HCRStation/') for e in events),
        'hull_only_all_equipment_events_checked': len(events), 'actual_triangle_max_penetration_m': worst, 'blocking_events': blocking,
        'threshold_m': .00005, 'method': 'original mesh faces fan-triangulated; triangle clipped against each original Cube shrunk by a physical margin',
        'limitations': 'All station and moving-equipment hull-only events from the independent audit; no dynamic or swept-volume validation.'}
    (HERE/'06_07_support_triangle_audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'events': len(events), 'max_triangle_depth': worst, 'blocking':len(blocking)}))


if __name__ == '__main__':
    export() if '--export-usd' in sys.argv else check()
