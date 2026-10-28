"""공통 gate 반환값을 유지하며 제어권 요청 수신/만료 시각만 기록한다."""
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time

from farm_docking.motion_gate import Lease, MotionGate, main


if __name__ == '__main__':
    output = Path(os.environ['MOTION_GATE_TRACE'])
    pending = queue.Queue(maxsize=8192)
    closed = threading.Event()
    counts = dict(records=0, dropped=0)
    active = {}

    def writer() -> None:
        with output.open('a') as stream:
            while not closed.is_set() or not pending.empty():
                try:
                    row = pending.get(timeout=.2)
                except queue.Empty:
                    stream.flush()
                    continue
                stream.write(json.dumps(row, ensure_ascii=False)+'\n')

    def started(code, offset) -> None:
        frame = sys._getframe(1)
        if frame.f_code is not code:
            return
        local = frame.f_locals
        instance = local['self']
        lease = instance if code is Lease.request.__code__ else instance.lease
        row = dict(function=code.co_qualname, start_ns=time.monotonic_ns(),
                   deadline_before=lease.deadline, owner_before=lease.owner)
        if code is Lease.request.__code__:
            row.update(owner=local['owner'], renew=bool(local['token']),
                       release=local['release'], decision_now=local['now'])
        else:
            request = local['request']
            row.update(owner=request.owner, renew=bool(request.token), release=request.release)
        active[(threading.get_ident(), code)] = row

    def returned(code, offset, value) -> None:
        row = active.pop((threading.get_ident(), code), None)
        if row is None:
            return
        frame = sys._getframe(1)
        instance = frame.f_locals['self']
        lease = instance if code is Lease.request.__code__ else instance.lease
        row.update(end_ns=time.monotonic_ns(), deadline_after=lease.deadline,
                   accepted=bool(value[0] if code is Lease.request.__code__ else value.accepted),
                   reason=lease.reason if code is Lease.request.__code__ else value.error_message)
        try:
            pending.put_nowait(row)
            counts['records'] += 1
        except queue.Full:
            counts['dropped'] += 1

    worker = threading.Thread(target=writer, name='gate_trace_writer', daemon=True)
    worker.start()
    tool = sys.monitoring.PROFILER_ID
    events = sys.monitoring.events
    sys.monitoring.use_tool_id(tool, 'gate diagnostic')
    sys.monitoring.register_callback(tool, events.PY_START, started)
    sys.monitoring.register_callback(tool, events.PY_RETURN, returned)
    for method in (MotionGate.request, Lease.request):
        sys.monitoring.set_local_events(tool, method.__code__, events.PY_START | events.PY_RETURN)
    try:
        main()
    finally:
        sys.monitoring.free_tool_id(tool)
        closed.set()
        worker.join(timeout=3.)
        output.with_suffix('.summary.json').write_text(json.dumps(counts, indent=2)+'\n')
