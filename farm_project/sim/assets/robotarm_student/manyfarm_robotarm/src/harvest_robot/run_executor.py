"""Portable executor contract demo. Does not run Isaac Sim or move hardware."""
import argparse
import json
from pathlib import Path
from harvest_runtime.demo import build_demo
from harvest_runtime import Request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--targets',nargs='+',default=['red-1','yellow-1'])
    p.add_argument('--fail-target')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    executor,world=build_demo(args.fail_target)
    executor.start([Request(f'demo-{i}',t) for i,t in enumerate(args.targets)],0.)
    for step in range(1,10001):
        executor.tick(step*.05)
        if executor.done:break
    report=executor.report()
    report.update(mode='contract_demo_no_physics',deposited_in_demo=sorted(world.deposited))
    body=json.dumps(report,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(body)
    print(body)
    return 0 if executor.state=='SUCCEEDED' else 1


if __name__=='__main__':
    raise SystemExit(main())
