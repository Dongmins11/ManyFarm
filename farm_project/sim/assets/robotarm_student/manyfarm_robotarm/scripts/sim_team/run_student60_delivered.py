"""Run the delivered D435/v20 GUI or headless demo without raw training data."""
import argparse
import json
import os
from pathlib import Path
import sys
from student60_bundle import ROOT, deployment, check_contract, relocate_physics_input


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--building', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--vision-python', type=Path, default=Path(os.environ.get('VISION_PYTHON', sys.executable)))
    p.add_argument('--output', type=Path)
    p.add_argument('--export-robot', type=Path)
    args, extra = p.parse_known_args()
    check, c, physical = check_contract(args.building)
    print('DELIVERED_STUDENT60_CHECK', json.dumps(check), flush=True)
    if args.check_only:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(check, indent=2) + '\n')
        return
    if args.output is None:
        p.error('--output must name a new evaluation directory')
    if not args.vision_python.is_file():
        p.error('--vision-python must point to a Python with the recorded Ultralytics dependencies')
    relocate_physics_input()
    if args.export_robot:
        from export_student60_robot import install_export_hook
        install_export_hook(args.export_robot.resolve())
    sys.path.insert(0, str(ROOT / 'scripts'))
    import view_student60_camera as demo
    d = deployment()

    def release_preflight(checkpoint, data, seed, camera_path, detector):
        expected = [ROOT / d['models']['student']['path'], ROOT / d['data_path'],
                    ROOT / d['models']['detector']['path']]
        if [Path(v).resolve() for v in (checkpoint, data, detector)] != expected:
            raise ValueError('This release runner requires its pinned models/data plan')
        if json.loads(camera_path.read_text()) != c['camera_config'] or seed in d['input_seeds']:
            raise ValueError('Camera configuration changed or training seed reused')
        return dict(check, seed=seed, contract_matches=True), c, physical

    demo.preflight = release_preflight
    sys.argv = [str(ROOT / 'scripts/view_student60_camera.py'),
        '--checkpoint', str(ROOT / d['models']['student']['path']),
        '--data', str(ROOT / d['data_path']),
        '--center-correction', str(ROOT / d['models']['center']['path']),
        '--detector', str(ROOT / d['models']['detector']['path']),
        '--vision-python', str(args.vision_python), '--output', str(args.output),
        '--seed', '106146', '--per-color', '2', '--split', 'test',
        '--wall-seconds', '2400', '--episode-wall-seconds', '600',
        '--cache-camera-maps', '--fast-native-depth', '--detector-device', 'cuda:0',
        '--visual-servo', '--entry-jaw-gate', '--execute'] + extra
    demo.main()


if __name__ == '__main__':
    main()
