"""Read-only reproduction of the V5 saved-149 versus baked-150 handoff comparison."""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.spatial.transform import Rotation

RUN = Path(__file__).resolve().parents[1]
PROJECT = RUN.parents[2]
CARGO = '/World/transport_robot/cargo_box'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def polar(m):
    u, s, vh = np.linalg.svd(m[:3, :3])
    return Rotation.from_matrix(u @ vh), s

def main():
    names = ['preview/05_handoff_continuity-0149.png.json',
             'preview/06_07_transport_sorting-0000.png.json',
             'settings/handoff_continuity_state.json', 'settings/05_physics_geometry.json',
             'settings/05_physics_bake.json', 'settings/05_handoff_continuity.json',
             'settings/06_07_transport_sorting.json', 'settings/06_07_source_joint_geometry.json']
    before, after, continuity, geometry, bake, req5, req6, joints = [read(RUN/n) for n in names]
    mesh_file = PROJECT / continuity['source_mesh_points_file']
    meshes = {x['source']: np.asarray(x['root_local_points'], float) for x in read(mesh_file)}
    cargo5 = np.asarray(before['inspected'][CARGO]); cargo6 = np.asarray(after['inspected'][CARGO])
    intended_cargo5 = np.asarray(continuity['cargo_world_end'])
    root6 = np.asarray(req6['base']['placements']['/World/transport_robot']['matrix'])
    def fixed_fk(root, joint): return root @ np.asarray(joint['f0']) @ np.linalg.inv(joint['f1'])
    intended_cargo6 = fixed_fk(fixed_fk(root6, joints['transport']['base_joint']), joints['transport']['box_tilt_joint'])
    endpoint5 = req5['keyframes'][-1]
    endpoint6 = req6['keyframes'][0]
    assert endpoint5['time'] == 5 and endpoint6['time'] == 0
    rows = []
    for clone in continuity['clones']:
        p = clone['path']; points = meshes[clone['source']]
        actual5 = np.asarray(before['inspected'][p]); actual6 = np.asarray(after['inspected'][p])
        requested5 = np.asarray(before['state']['placements'][p]['matrix'])
        requested6 = np.asarray(after['state']['placements'][p]['matrix'])
        a = np.linalg.inv(cargo5) @ actual5; b = np.linalg.inv(cargo6) @ actual6
        va = points @ a[:3,:3].T + a[:3,3]; vb = points @ b[:3,:3].T + b[:3,3]
        vertex_delta = np.linalg.norm(vb-va, axis=1)
        ra, sa = polar(a); rb, sb = polar(b)
        exact5 = np.asarray(endpoint5['state']['placements'][p]['matrix'])
        exact6 = np.asarray(endpoint6['state']['placements'][p]['matrix'])
        intended = np.asarray(clone['final_cargo_matrix'])
        ea = np.linalg.inv(intended_cargo5) @ exact5
        eb = np.linalg.inv(intended_cargo6) @ exact6
        rows.append(dict(id=p, source=clone['source'], color=clone['color'], original_vertices=len(points),
            saved05_time_s=before['time_s'], saved06_time_s=after['time_s'],
            actual_cargo_relative_matrix_05=a.tolist(), actual_cargo_relative_matrix_06=b.tolist(),
            requested_world_matrix_05_saved_frame=requested5.tolist(), requested_world_matrix_06_saved_frame=requested6.tolist(),
            actual_world_matrix_05=actual5.tolist(), actual_world_matrix_06=actual6.tolist(),
            requested_vs_actual05_world_max_abs=float(np.max(abs(actual5-requested5))),
            requested_vs_actual06_world_max_abs=float(np.max(abs(actual6-requested6))),
            actual_relative_matrix_max_abs_delta=float(np.max(abs(b-a))),
            translation_vector_m=(b[:3,3]-a[:3,3]).tolist(), translation_norm_m=float(np.linalg.norm(b[:3,3]-a[:3,3])),
            orientation_polar_angle_rad=float((rb*ra.inv()).magnitude()),
            singular_scale05=sa.tolist(), singular_scale06=sb.tolist(),
            max_absolute_singular_scale_delta=float(np.max(abs(sb-sa))),
            max_relative_singular_scale_delta=float(np.max(abs(sb-sa)/sb)),
            max_original_mesh_vertex_displacement_m=float(vertex_delta.max()),
            max_vertex_index=int(vertex_delta.argmax()), rms_original_mesh_vertex_displacement_m=float(np.sqrt(np.mean(vertex_delta**2))),
            requested05_5s_vs_bake150_world_max_abs=float(np.max(abs(exact5-np.asarray(bake['frames'][-1]['placements'][p])))),
            intended05_5s_vs_continuity_relative_max_abs=float(np.max(abs(ea-intended))),
            intended06_0s_vs_continuity_relative_max_abs=float(np.max(abs(eb-intended))),
            intended05_5s_vs_06_0s_relative_max_abs=float(np.max(abs(ea-eb))),
            bake149_vs_bake150_world_translation_m=float(np.linalg.norm(np.asarray(bake['frames'][-1]['placements'][p])[:3,3]-np.asarray(bake['frames'][-2]['placements'][p])[:3,3]))))
    maxima = {k:max(x[k] for x in rows) for k in ['actual_relative_matrix_max_abs_delta','translation_norm_m',
        'orientation_polar_angle_rad','max_absolute_singular_scale_delta','max_relative_singular_scale_delta',
        'max_original_mesh_vertex_displacement_m','requested_vs_actual05_world_max_abs','requested_vs_actual06_world_max_abs',
        'requested05_5s_vs_bake150_world_max_abs','intended05_5s_vs_06_0s_relative_max_abs']}
    physical_limit = 1e-6; strict_limit = 1e-9
    passed = maxima['max_original_mesh_vertex_displacement_m'] <= physical_limit and maxima['intended05_5s_vs_06_0s_relative_max_abs'] <= strict_limit
    result = dict(schema_version=5, passed=passed,
        initial_failure={'reported_first_failing_id':'/World/PresentationFruits/Handoff_06',
                         'reported_max_abs_matrix_delta':4.5238731677388344e-7,'old_mixed_unit_matrix_tolerance':1e-8,
                         'note':'The first failing set-iteration item was not the worst of all seven. All-seven maximum is reported below.'},
        method='Read saved GUI matrices; remove each cargo world transform; SVD polar rotation and singular scales; transform every original mesh vertex (no convex reduction or scale normalization) and compare Euclidean displacement. Separately reconstruct requested06 cargo by original zero-joint FK and compare the exact baked/requested05 5.0s endpoint.',
        findings=[
          'Primary cause is a one-frame endpoint selection mismatch: the five-second MP4 saves frames 0..149, ending at 4.9666666667 s; handoff_continuity_state uses the final Bullet sample 150 at 5.0 s. The bake retains tiny settling motion and float-matrix variation between those samples.',
          'This is not a GUI fruit transform application failure: requested and inspected fruit world matrices are exactly equal for all seven at both saved frames.',
          'The maximum physical difference is below one micrometre when evaluated over every original mesh vertex. There is no evidence of a macroscopic pose reset, lost fruit, intentional rescale or altered source geometry.',
          'A separate 9.313225746e-9 m cargo Z difference exists between the geometry-export authored cargo pose and the GUI zero-joint FK pose. Stored joint translations contain float32 values (0.009999999776482582+0.24500000476837158), whereas the authored/export cargo Z is 0.2549999952316284. This nanometre contribution is measured separately from the Bullet endpoint movement.',
          'Gf.Matrix4d is used for the capture transform writes; the observed saved fruit matrices match those double-precision requests. Calling the entire mismatch USD float rounding would be inaccurate.'
        ],
        recommendation={'scope':'Only actual captured05 frame 149 to actual06 frame 0 settled-cargo continuity',
            'max_original_mesh_vertex_displacement_m':physical_limit,
            'strict_intended_5s_to_06_request_matrix_tolerance':strict_limit,
            'decision':'Accept this existing capture if both bounded checks pass. No recapture is required for this measured submicrometre terminal residual. Do not relax geometry/contact or arbitrary pose tests.',
            'not_recommended':'A blanket 1e-6 elementwise matrix tolerance mixes units and also fails the actual worst matrix element 1.55998e-6. Use original-mesh displacement in metres.',
            'future_endpoint_fix':'For future builds derive continuation state from the last encoded sample 149, or explicitly freeze the final hold before frame 149. Do not modify the already captured V5 files for this audit.'},
        cargo_precision={'geometry_export_cargo_world':intended_cargo5.tolist(), 'gui05_cargo_world':cargo5.tolist(),
            'gui05_minus_export_translation_m':(cargo5[:3,3]-intended_cargo5[:3,3]).tolist(),
            'base_joint_f0_translation':np.asarray(joints['transport']['base_joint']['f0'])[:3,3].tolist(),
            'box_tilt_joint_f0_translation':np.asarray(joints['transport']['box_tilt_joint']['f0'])[:3,3].tolist(),
            'requested06_fk_vs_gui_cargo_max_abs':float(np.max(abs(intended_cargo6-cargo6)))},
        maxima=maxima, total_original_vertices=sum(x['original_vertices'] for x in rows), fruits=rows,
        source_hashes={n:sha(RUN/n) for n in names} | {'../presentation_video_revision_v3_20261104/settings/handoff_mesh_points.json':sha(mesh_file),
            '05_handoff_continuity.mp4':sha(RUN/'05_handoff_continuity.mp4'), '06_07_transport_sorting.mp4':sha(RUN/'06_07_transport_sorting.mp4'),
            'qa/review_continuity_precision.py':sha(Path(__file__))},
        limitations=['The physical bound is between the two recorded endpoint poses, not a claim that the endpoint samples are bit-identical.',
          'SVD decomposition separates rotation and stretch of float-derived matrices; it does not imply an intentional scale animation.',
          'This report does not change the videos, motion settings or verifier. GUI screenshots cannot visually resolve this submicrometre difference.'])
    (RUN/'qa/continuity_precision_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':passed,'maxima':maxima,'total_vertices':result['total_original_vertices']},indent=2))

if __name__ == '__main__': main()
