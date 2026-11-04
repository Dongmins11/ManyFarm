"""V5의 실제 파일 해시를 기록한다. 생성만으로 검수 통과를 선언하지 않는다."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parent
V3 = '../presentation_video_revision_v3_20261104/'
RAW = {'05_handoff_continuity.mp4': 150, '06_07_transport_sorting.mp4': 360}
REUSED = {V3 + name: 150 for name in ('01_overview.mp4', '02_scout.mp4', '04_deposit.mp4')}
REUSED['../presentation_video_20261104/03_grasp.mp4'] = 150
EDITS = {'ManyFarm_25s_clean.mp4': 750, 'ManyFarm_25s_captioned.mp4': 750}
SETTING_FILES = (
    'fleet.json', 'harvest.json', 'transport.json', 'scout.json', 'sorter.json', 'stations.json', 'cycle_layout.json',
    '00_apriltag_closeup.json', '05_handoff_continuity.json', '05_handoff_continuity_evidence.json',
    '05_physics_geometry.json', '05_physics_bake.json', 'handoff_continuity_state.json',
    '06_07_transport_sorting.json', '06_07_motion_evidence.json', '06_07_source_joint_geometry.json',
    '06_07_convex_fruit_audit.json', 'build_handoff_v5.py', 'audit_handoff_v5.py', 'build_continuous_v5.py',
    '06_07_scene.json', 'workspace_bounds.json', '06_07_grasp_plan.json', 'plan_grasp_v5.py',
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(name: str, frames: int) -> dict:
    return dict(file=name, sha256=digest(ROOT / name), frames=frames, fps=30,
                width=1920, height=1080, duration_s=frames / 30,
                codec='h264', pixel_format='yuv420p', audio=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace', action='store_true', help='명시적으로 기존 manifest만 갱신')
    args = parser.parse_args()
    target = ROOT / 'manifest.json'
    if target.exists() and not args.replace:
        raise FileExistsError('manifest exists; use --replace after checking current evidence')
    tools = sorted((ROOT / 'capture_tools').glob('*.py'))
    if not tools:
        raise FileNotFoundError('Capture-time tool snapshots required in capture_tools/')
    tools += [ROOT / 'settings' / name for name in SETTING_FILES]
    tools += sorted(ROOT.glob('*.py'))
    data = dict(schema_version=5,
        specification='INPUT_V5.md', specification_sha256=digest(ROOT / 'INPUT_V5.md'),
        baseline_commit='a4ca4c0add75bb6dfc84d16b2714734521ac4a9b',
        requirements_commit='4a5da37ca024b62a5dfdbc8276193028887f1f4b',
        scope='Isaac Sim GUI keyframed presentation animation; no autonomous mission or hardware-performance claim',
        source_scene='sim/assets/envs/output/farm_with_plants_v5.usd',
        scene_layer='session only; source USD not saved', gui=True, all_beds=True,
        clips=[record(n, f) for n, f in RAW.items()],
        reused_clips=[record(n, f) for n, f in REUSED.items()],
        edits=[record(n, f) for n, f in EDITS.items()],
        capture_tools={str(p.relative_to(ROOT)): digest(p) for p in tools},
        scout_inset_enabled=False,
        evidence={'preservation': 'original_hashes.json', 'capture_session': 'capture_session.json',
                  'motion': 'settings/06_07_motion_evidence.json',
                  'handoff': 'settings/05_handoff_continuity_evidence.json',
                  'handoff_physics_geometry': 'settings/05_physics_geometry.json',
                  'handoff_physics_bake': 'settings/05_physics_bake.json',
                  'handoff_independent_audit': 'qa/05_independent_bake_geometry_audit.json',
                  'handoff_render_diagnostic': 'qa/05_render_history_diagnostic_review.json',
                  'cargo_continuity': 'settings/handoff_continuity_state.json',
                  'captured_continuity_review': 'qa/continuity_precision_review.json',
                  'captured_continuity_review_code': 'qa/review_continuity_precision.py',
                  'initial_validation_failure': 'qa/validation_initial.txt',
                  'fruit_convex_audit': 'settings/06_07_convex_fruit_audit.json',
                  'independent_equipment_audit': 'qa/06_07_independent_geometry_audit.json',
                  'independent_audit_code': 'qa/audit_continuous_geometry.py',
                  'independent_measured_robot_cubes': 'qa/06_07_actual_robot_cubes.json',
                  'independent_station_boxes': 'qa/06_07_actual_station_boxes.json',
                  'support_triangle_audit': 'qa/06_07_support_triangle_audit.json',
                  'support_triangle_audit_code': 'qa/audit_support_triangles.py',
                  'original_fruit_triangles': 'qa/06_07_actual_fruit_triangles.json',
                  'camera_selection': 'qa/camera_selection.json',
                  'bed_nonexposure_review': 'qa/bed_nonexposure_review.json',
                  'assets': 'handoff_assets.json', 'tags': 'apriltag_installation.json',
                  'house': 'house_visibility_baseline.json',
                  'vegetation': 'vegetation_visibility_baseline.json', 'edit': 'edit_decisions.json',
                  'handoff_timed_decode': 'qa/05_handoff_continuity-timed-decode.json',
                  'continuous_timed_decode': 'qa/06_07_transport_sorting-timed-decode.json',
                  'clean_timed_decode': 'qa/ManyFarm_25s_clean-timed-decode.json',
                  'captioned_timed_decode': 'qa/ManyFarm_25s_captioned-timed-decode.json',
                  'handoff_frame_review': 'qa/05_handoff_continuity-mp4-review.json',
                  'continuous_frame_review': 'qa/06_07_transport_sorting-mp4-review.json',
                  'clean_frame_review': 'qa/ManyFarm_25s_clean-mp4-review.json',
                  'captioned_frame_review': 'qa/ManyFarm_25s_captioned-mp4-review.json',
                  'reused_deposit_cut_review': 'qa/04_cut_stability_review.json',
                  'root_keyframe_review': 'qa/root_keyframe_review.json',
                  'visual_review': 'qa/visual_review.json'},
        validation_note='Manifest records file hashes and intended specifications. Run verify_delivery.py and inspect actual MP4 QA separately.')
    data['evidence_sha256'] = {name: digest(ROOT / path) for name, path in data['evidence'].items()}
    # 전부 읽힌 다음 기록한다. 필수 영상 누락 시 부분 manifest를 쓰지 않는다.
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print('V5 manifest written. This is not a validation PASS.')


if __name__ == '__main__':
    main()
