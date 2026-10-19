"""검증된 Student 전달본을 상대 경로 그대로 sim 자산에 보존한다."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ARCHIVE_SHA256 = '409633afa28bc4c05e1558a4df7f9c1ff9da95e412f4a608b1b8bc7d0c56cbec'
ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    if hashlib.file_digest(args.archive.open('rb'), 'sha256').hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Student 전달 압축 SHA256 불일치')
    destination = ROOT/'sim/assets/robotarm_student'
    if destination.exists():
        raise FileExistsError(destination)
    with tarfile.open(args.archive) as archive:
        for item in archive.getmembers():
            path = Path(item.name)
            if path.is_absolute() or '..' in path.parts or item.issym() or item.islnk():
                raise ValueError('안전하지 않은 전달 경로: '+item.name)
        archive.extractall(destination, filter='data')
    release = destination/'manyfarm_robotarm'
    manifest = json.loads((release/'handoff/MISSION_MANIFEST.json').read_text())
    for row in manifest['files']:
        path = (release/row['path']).resolve()
        if not path.is_relative_to(release) or hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != row['sha256']:
            raise ValueError('Student 파일 SHA256 불일치: '+row['path'])
    (destination/'PROVENANCE.json').write_text(json.dumps(dict(
        archive_sha256=ARCHIVE_SHA256, files_verified=len(manifest['files']),
        entry='manyfarm_robotarm/handoff/MISSION_RELEASE.json', source_files_modified=False), indent=2)+'\n')
    print('Student release verified:', len(manifest['files']))


if __name__ == '__main__':
    main()
