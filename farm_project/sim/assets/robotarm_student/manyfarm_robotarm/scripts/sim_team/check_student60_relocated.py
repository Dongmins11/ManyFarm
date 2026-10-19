"""Check a release while rejecting reads of the author's workspace/data.

Installed Python environments remain allowed. C++ USD/RTX file access needs
the independent USD dependency inspection/native file trace as well.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from student60_bundle import ROOT, deployment


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--building', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--native-output', type=Path)
    p.add_argument('--vision-python', type=Path)
    args = p.parse_args()
    source = Path(deployment()['source_root'])
    if ROOT == source or ROOT.is_relative_to(source):
        p.error('Run this check after extracting outside the source workspace')
    blocked = []
    def guard(event, values):
        if event != 'open' or not values or not isinstance(values[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(values[0])).absolute()
        if path.is_relative_to(source) and not path.is_relative_to(source / '.venvs'):
            blocked.append(str(path))
            raise PermissionError('Release must not read original workspace: ' + str(path))
    sys.addaudithook(guard)
    if args.native_output:
        if args.vision_python is None:
            p.error('--vision-python is required for native relocation check')
        import run_student60_delivered as runner
        sys.argv = [runner.__file__, '--output', str(args.native_output),
                    '--vision-python', str(args.vision_python), '--headless',
                    '--colors', 'Red', '--per-color', '1', '--smoke-steps', '20']
        if args.building:
            sys.argv.append('--building')
        runner.main()
        return
    from student60_bundle import check_contract
    check, _, _ = check_contract(args.building)
    result = dict(passed=True, extraction_root=str(ROOT), original_source_read_attempts=blocked,
                  source_workspace_denied=True, model_contract=check,
                  scope='Python file audit + CPU model inference; native USD access checked separately')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('RELOCATED_STUDENT60_CHECK', args.output, flush=True)


if __name__ == '__main__':
    main()
