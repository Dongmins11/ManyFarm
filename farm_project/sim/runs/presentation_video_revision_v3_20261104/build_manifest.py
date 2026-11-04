"""검수한 V3 전달 파일의 규격·출처·재현 설정 해시를 기록한다."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record(name: str, frames: int) -> dict:
    return dict(file=name, sha256=digest(ROOT/name), frames=frames, fps=30,
                width=1920, height=1080, duration_s=frames/30, codec='h264', pixel_format='yuv420p', audio=False)

def main() -> None:
    snapshots = ROOT/'capture_tools'; snapshots.mkdir(exist_ok=True)
    for name in ('stage_portfolio_photos.py','presentation_video_frames.py','presentation_scene_v3.py','request_presentation_capture.py'):
        shutil.copy2(PROJECT/'sim/tools'/name,snapshots/name)
    tools = sorted(snapshots.glob('*.py')) + sorted((ROOT/'settings').glob('*.json')) + sorted((ROOT/'settings').glob('*.py'))
    data = dict(schema_version=3, specification_commit='1ee8fbe663f414bf1d7bd1afcab25ce6a7071867',
        scope='Isaac Sim GUI keyframed presentation animation; no autonomous mission/performance claim',
        source_scene='sim/assets/envs/output/farm_with_plants_v5.usd', scene_layer='session only; source USD not saved',
        renderer='RayTracedLighting', gui=True, all_beds=True,
        clips=[record(n,f) for n,f in [('01_overview.mp4',150),('02_scout.mp4',150),('04_deposit.mp4',150),('05_handoff.mp4',150),('06_transport.mp4',120),('07_sorting.mp4',210)]],
        reused_clips=[record('../presentation_video_20261104/03_grasp.mp4',150)],
        edits=[record('ManyFarm_22s_clean.mp4',660),record('ManyFarm_22s_captioned.mp4',660)],
        capture_tools={str(p.relative_to(ROOT)):digest(p) for p in tools},
        evidence={'source_preservation':'original_hashes.json','apriltags':'apriltag_installation.json',
                  'house_baseline':'house_visibility_baseline.json','camera_review':'qa/camera_review.json',
                  'visual_review':'qa/visual_review.json','station_transform':'settings/station_transform.json',
                  'handoff_assets':'handoff_assets.json','scout_insert':'overlays/02_scout_insert.json',
                  'sorting_motion':'settings/07_motion_evidence.json','edit':'edit_decisions.json'},
        reproduction_command='python sim/tools/stage_portfolio_photos.py --gui --all-beds --runtime sim/runs/presentation_video_revision_v3_20261104/settings --output sim/runs/<new-output-directory>')
    (ROOT/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

if __name__ == '__main__': main()
