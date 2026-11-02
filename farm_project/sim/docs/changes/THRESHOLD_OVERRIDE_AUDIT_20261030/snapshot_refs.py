"""고정 커밋의 감사용 입력을 /tmp에 추출한다. checkout/merge/pull을 하지 않는다."""
import io
from pathlib import Path
import subprocess
import tarfile

root = Path(__file__).resolve().parents[4]
dest = Path('/tmp/farm_threshold_audit_20261030')
for name, commit in (
    ('drive', '366e0c37164c22afdd2f640624b61eef8f0fa6f7'),
    ('harvest', 'e135cdef9462276cc25d9fa336f084e2dcac72e4'),
):
    raw = subprocess.check_output(['git', 'archive', commit,
        'farm_project/robot/config', 'farm_project/robot/ros_ws/src'], cwd=root.parent)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            relative = Path(member.name)
            if (not member.isfile() or relative.is_absolute() or '..' in relative.parts
                or relative.suffix not in ('.py','.yaml','.yml','.json','.xml','.cpp','.hpp','.h')):
                continue
            target = dest/name/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
    print(dest/name/'farm_project')
