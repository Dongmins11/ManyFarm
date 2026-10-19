"""Validate explicit seed-disjoint demonstration splits. Does not train."""
import argparse,json
from pathlib import Path
from harvest_rl.student_bc import prepare,audit_root

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inspect',nargs='+',type=Path,help='Read-only inventory; does not create training split')
    p.add_argument('--train',nargs='+',type=Path)
    p.add_argument('--validation',nargs='+',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.inspect:
        if a.train or a.validation or a.output:p.error('--inspect cannot be combined with split creation')
        results=[]
        for root in a.inspect:
            print('AUDIT',root,flush=True)
            try:
                _,episodes,skipped,_=audit_root(root)
                results.append(dict(root=str(root),accepted=True,successful_episodes=len(episodes),
                    frames=sum(e['samples'] for e in episodes),skipped=skipped))
            except (ValueError,KeyError,OSError) as exc:results.append(dict(root=str(root),accepted=False,reason=str(exc)))
        print(json.dumps(results,indent=2));return
    if not a.train or not a.validation or a.output is None:p.error('Require --train --validation --output')
    print('AUDIT_AND_FREEZE: validating every sample; no learning',flush=True)
    plan=prepare(a.train,a.validation)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f: json.dump(plan,f,indent=2)
    print(json.dumps(dict(summary=plan['summary'],warnings=plan['warnings']),indent=2));print('PREPARED',a.output)
if __name__=='__main__':main()
