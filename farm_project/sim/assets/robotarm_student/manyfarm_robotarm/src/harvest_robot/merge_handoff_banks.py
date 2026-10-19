"""Merge compatible measured handoff states; never synthesize physical states."""
import argparse
import hashlib
import json
from pathlib import Path
import torch


def merge(paths, output):
    payloads = [torch.load(p, map_location='cpu', weights_only=True) for p in paths]
    first = payloads[0]
    for p, payload in zip(paths, payloads):
        if payload['metadata'] != first['metadata']:
            raise ValueError(f'Incompatible handoff metadata: {p}')
        if set(payload['states']) != set(first['states']):
            raise ValueError(f'Incompatible state fields: {p}')
        n = len(payload['states']['target_index'])
        if n == 0 or any(len(v) != n for v in payload['states'].values()):
            raise ValueError(f'Invalid state count: {p}')
        if any(v.is_floating_point() and not torch.isfinite(v).all() for v in payload['states'].values()):
            raise ValueError(f'Nonfinite state: {p}')
    result = {'metadata': first['metadata'], 'states': {
        key: torch.cat([p['states'][key] for p in payloads]) for key in first['states']}}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f:
        torch.save(result, f)
    manifest = {'bank': str(output.resolve()), 'count': len(result['states']['target_index']),
                'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'sources': [{'path': str(Path(p).resolve()),
                    'count': len(d['states']['target_index']),
                    'sha256': hashlib.sha256(Path(p).read_bytes()).hexdigest()}
                    for p,d in zip(paths,payloads)]}
    output.with_suffix('.json').write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge(args.inputs, args.output), indent=2))
