"""제어와 독립적으로 USD 바구니 프레임의 개구부 투영/정지 유지 시간을 평가한다."""
import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


import sys
sys.path.insert(0,str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.basket_alignment import polygon,area,intersection,BasketAlignment


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--diagnostics',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    spec=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/docking/basket_alignment_evaluation.json').read_text())
    read=lambda name:[json.loads(line) for line in (args.diagnostics/(name+'_01.jsonl')).read_text().splitlines()]
    harvest,transport=read('harvest'),read('transport')
    ht=np.array([x['sim_time_s'] for x in harvest]);samples=[];longest=0.
    evaluator=BasketAlignment(spec)
    for t in transport:
        index=int(np.argmin(abs(ht-t['sim_time_s'])));h=harvest[index]
        if abs(h['sim_time_s']-t['sim_time_s'])>.1:continue
        sample=evaluator.sample(t['sim_time_s'],h,t)
        samples.append(sample);longest=max(longest,sample['held_s'])
    if not samples:raise RuntimeError('동시각 바구니 실제 프레임 기록 없음')
    report=dict(scope='evaluation only; aperture dimensions provisional from URDF',samples=len(samples),
                source=str(args.diagnostics),spec=spec,max_coverage=max(x['coverage'] for x in samples),
                minimum_center_distance_m=min(x['horizontal_distance_m'] for x in samples),
                longest_aligned_stationary_s=longest,alignment_hold_pass=longest>=spec['hold_s'],initial=samples[0],final=samples[-1])
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'basket_samples.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in samples))
    (args.output/'basket_alignment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['spec','initial','final']},ensure_ascii=False))


if __name__=='__main__':main()
