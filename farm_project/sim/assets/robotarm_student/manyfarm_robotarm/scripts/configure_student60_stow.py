"""Create a new editable stow configuration in degrees; preserve the old file."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/harvest_robot'))


def main():
    import numpy as np
    from harvest_rl.kinematics import ArmKinematics
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=ROOT/'src/harvest_robot/config/student60_mission_v1.json')
    p.add_argument('--joint-deg',nargs=6,type=float,required=True,
        metavar=('PAN','SHOULDER','ELBOW','WRIST_FLEX','WRIST_ROLL','GRIPPER'))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();config=json.loads(a.base.read_text());q=np.deg2rad(a.joint_deg);kin=ArmKinematics()
    if not np.isfinite(q).all() or np.any(q<kin.lower) or np.any(q>kin.upper):p.error('Outside original joint limits')
    config['stow_rad']=q.tolist();config['status']='new_simulation_pose_requires_preview_and_motion_check'
    config['hardware_authorized']=False
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:f.write(json.dumps(config,indent=2)+'\n')
    print('NEW_STOW_CONFIG',a.output)
    print('Preview with: scripts/run_student60_mission.py --camera d435|u20 --config <new file> --preview-only --execute --headless --output <new directory>')


if __name__=='__main__':main()
