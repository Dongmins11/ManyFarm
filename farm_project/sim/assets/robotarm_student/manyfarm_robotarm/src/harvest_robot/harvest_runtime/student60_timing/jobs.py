"""Read-only host GPU/native-work guard; never terminates another user's job."""
import os
from pathlib import Path
import subprocess


def owned(pid,exclude_group):
    try:return exclude_group is not None and os.getpgid(pid)==exclude_group
    except ProcessLookupError:return False


def occupied(exclude_group=None):
    if Path('/proc/1/comm').read_text().strip() not in ('systemd','init'):raise RuntimeError('Host process visibility required')
    jobs=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        pid=int(entry.name)
        if pid==os.getpid() or owned(pid,exclude_group):continue
        try:
            args=[v.decode() for v in (entry/'cmdline').read_bytes().split(b'\0') if v]
            if not args or 'python' not in Path(args[0]).name:continue
            script=next((x for x in args[1:] if x not in ('-u','-B','-I','-s','-E','-O','-OO')),None)
            if script is None:continue
            name=Path(script).name
            if name.startswith(('collect_student60','eval_student60','train_student60')) or name in (
                'view_student60_camera.py','preview_u20_wrist.py','benchmark_student60_latency.py','run_student60_u20_after_collection.py'):
                jobs.append(dict(pid=pid,script=name))
        except (OSError,UnicodeError):continue
    result=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],
        capture_output=True,text=True,timeout=10)
    if result.returncode:raise RuntimeError('Cannot verify GPU ownership: '+result.stderr)
    for line in result.stdout.splitlines():
        parts=[x.strip() for x in line.split(',')]
        if len(parts)<3 or not parts[0].isdigit():continue
        pid=int(parts[0]);name=Path(parts[1]).name
        if pid!=os.getpid() and name!='sunshine' and not owned(pid,exclude_group):
            jobs.append(dict(pid=pid,gpu_process=name,memory_mib=parts[2]))
    return jobs
