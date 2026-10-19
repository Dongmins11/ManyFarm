"""Audit recovered approach segments against a frozen BC plan; no training."""
import argparse,json
from pathlib import Path
from harvest_rl.student_dagger import prepare_dagger

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--roots',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    plan=prepare_dagger(json.loads(a.base.read_text()),a.roots)
    with a.output.open('x') as f:json.dump(plan,f,indent=2)
    print('DAGGER_PREPARED',plan['summary'],a.output,flush=True)
if __name__=='__main__':main()
