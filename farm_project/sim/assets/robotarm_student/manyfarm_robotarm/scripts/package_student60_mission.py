"""Add a separately versioned mission to the sealed D435 baseline; never overwrite it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'outputs/sim_team_delivery/student60_d435_v20_20261016'
BASE_SHA = '6251bdad2e0e7a9c7dad549056910b42b868cce2084a2e665610e27fa8100e81'
EVIDENCE = ROOT/'outputs/harvest_rl/student60_mission_v1_20261016'


def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.resolve().is_relative_to(EVIDENCE.resolve()):
        p.error('Package output must be outside the evidence tree')
    a.output.mkdir(parents=True,exist_ok=False)
    original=BASE/'harvest_student60_d435_v20_20261016.tar.gz'
    if sha(original)!=BASE_SHA: raise ValueError('Original sealed baseline changed')
    with tarfile.open(original) as f: f.extractall(a.output,filter='data')
    workspace=a.output/'manyfarm_robotarm'
    paths=['src/harvest_robot/config/student60_mission_v1.json',
        'src/harvest_robot/harvest_runtime/student60_mission.py',
        'src/harvest_robot/harvest_runtime/student60_mission_session.py',
        'src/harvest_robot/harvest_rl/student60_mission_env.py',
        'src/harvest_robot/harvest_sensors/mission_video.py',
        'scripts/run_student60_mission.py','scripts/package_student60_mission.py',
        'scripts/configure_student60_stow.py','scripts/check_student60_stow_geometry.py',
        'scripts/sim_team/check_student60_mission_release.py',
        'tests/test_student60_mission.py',
        'docs/manipulation/STUDENT60_MISSION_V1_KR.md']
    for name in paths:
        dst=workspace/name;dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():raise FileExistsError('Refuse to overwrite baseline: '+name)
        shutil.copy2(ROOT/name,dst)
    u20=ROOT/'outputs/harvest_rl/student60_u20_set_20261015_172817_e60f49a8/u20_bc_after_collection_r3_quality_20261016/train/student_best.pt'
    shutil.copy2(u20,workspace/'handoff/models/u20_student.pt')
    shutil.copy2(u20.parent.parent/'data.json',workspace/'handoff/models/u20_training_plan.json')
    old=json.loads((workspace/'handoff/DEPLOYMENT.json').read_text())
    release=dict(schema='student60_mission_v1',base_archive_sha256=BASE_SHA,
        models=dict(d435=old['models']['student'],u20=dict(path='handoff/models/u20_student.pt',sha256=sha(u20)),
                    center=old['models']['center'],detector=old['models']['detector']),
        frozen_physics_usd=old['frozen_physics_usd'],config='src/harvest_robot/config/student60_mission_v1.json',
        original_d435_single_target_result='4/4; not multi-fruit or folded-return evidence',
        new_mission_status='candidate; D435 two-fruit native mission completed; see FINAL_CHECKS.json for scope',
        u20_status='RGB-only checkpoint with new mission/v20 assistance; movement/inference checks are not a multi-fruit harvest success claim',
        hardware_executed=False,stow_pose_user_approved=False,
        camera_robot=dict(d435_usd=old['robot_with_cameras'],
            u20_urdf='src/smartfarm_description/urdf/harvest_robot_u20_wrist_v1.urdf',
            u20_native_creation='run_student60_mission.py --camera u20 uses included frozen USD and U20 visuals/rig'))
    demo=EVIDENCE/'d435_recorded_r2/Student_D435_multifruit_success_20261016.mp4'
    if demo.exists():
        checked=json.loads((demo.parent/'video_validation.json').read_text())
        if not checked['passed'] or not checked['mission_complete'] or sha(demo)!=checked['sha256']:
            raise ValueError('Demonstration video has not passed verification')
        shutil.copy2(demo,workspace/'handoff/mission_demo.mp4')
        release['demonstration_video']=dict(path='handoff/mission_demo.mp4',sha256=sha(demo),
            playback='1x simulation time',seconds=float(checked['probe']['format']['duration']))
    (workspace/'handoff/MISSION_RELEASE.json').write_text(json.dumps(release,indent=2)+'\n')
    evidence=workspace/'handoff/mission_verification';evidence.mkdir()
    for src in EVIDENCE.rglob('*'):
        if ('before' in src.parts or not src.is_file() or
                (src.suffix not in ('.json','.png','.jpg') and src.name not in ('executed_runner.py','tests_final.log'))
                or 'fruit_assets' in src.parts): continue
        dst=evidence/src.relative_to(EVIDENCE);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    shutil.copy2(ROOT/'docs/manipulation/STUDENT60_MISSION_V1_KR.md',workspace/'handoff/MISSION_README_KR.md')
    files=[dict(path=str(f.relative_to(workspace)),sha256=sha(f),bytes=f.stat().st_size)
           for f in sorted(workspace.rglob('*')) if f.is_file() and '__pycache__' not in f.parts]
    (workspace/'handoff/MISSION_MANIFEST.json').write_text(json.dumps(dict(files=files),indent=2)+'\n')
    archive=a.output/'harvest_student60_d435_u20_mission_v1_20261016.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=4) as f:
        for name in [r['path'] for r in files]+['handoff/MISSION_MANIFEST.json']:
            f.add(workspace/name,arcname='manyfarm_robotarm/'+name,recursive=False)
    (a.output/'SHA256SUMS').write_text(sha(archive)+'  '+archive.name+'\n')
    shutil.copy2(workspace/'handoff/MISSION_README_KR.md',a.output/'README_KR.md')
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),files=len(files)),indent=2))


if __name__=='__main__':main()
