"""Apply/undo the sim-only caster material patch; Python standard library only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rollback', type=Path, help='Printed backup file to restore')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    bundle = root / 'sim/patches/harvest_caster_fix_20261006'
    manifest = json.loads((bundle / 'manifest.json').read_text())
    target = root / manifest['target']
    current = target.read_bytes()
    current_hash = digest(current)
    if args.rollback:
        replacement = args.rollback.expanduser().read_bytes()
        if current_hash != manifest['after_sha256'] or digest(replacement) != manifest['before_sha256']:
            raise SystemExit('롤백 중단: 현재 파일 또는 백업이 이 패치 버전과 다릅니다.')
        operation = 'ROLLBACK'
    else:
        if current_hash == manifest['after_sha256']:
            print('이미 적용되어 있습니다. Isaac을 재시작하세요.')
            return
        if current_hash != manifest['before_sha256']:
            raise SystemExit('적용 중단: USD가 확인한 원본과 다릅니다. 기존 수정 보호를 위해 덮어쓰지 않았습니다.')
        replacement = (bundle / 'harvest_robot.usd').read_bytes()
        if digest(replacement) != manifest['after_sha256']:
            raise SystemExit('적용 중단: 패치 파일 체크섬 불일치')
        operation = 'APPLY'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backup_dir = root / 'sim/runs/patch_backups' / ('harvest_caster_' + stamp)
    backup_dir.mkdir(parents=True)
    backup = backup_dir / 'harvest_robot.usd'
    shutil.copy2(target, backup)
    temporary = target.with_name(target.name + '.caster-fix.tmp')
    temporary.write_bytes(replacement)
    temporary.replace(target)
    log = root / 'sim/docs/changes/CASTER-FIX-20261006-013-applied.jsonl'
    log.parent.mkdir(parents=True, exist_ok=True)
    record = dict(operation=operation, timestamp=stamp, target=manifest['target'],
                  before_sha256=current_hash, after_sha256=digest(replacement),
                  backup=str(backup.relative_to(root)))
    with log.open('a') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    print(operation + ': ' + manifest['target'])
    print('백업: ' + str(backup))
    print('변경 로그: ' + str(log))
    print('빌드 불필요. Isaac을 완전히 종료한 뒤 다시 실행하세요.')


if __name__ == '__main__':
    main()
