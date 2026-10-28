"""공통 반환값을 바꾸지 않고 센서 최신성·계산·대기 시간을 비동기 기록한다."""
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time

from farm_docking.precision_server import PrecisionServer, main
from farm_docking.clients import LeaseClient
from farm_docking.marker_geometry import solve_marker, compose_marker


if __name__=='__main__':
    output=Path(os.environ['DOCKING_FRESHNESS_TRACE'])
    output.parent.mkdir(parents=True,exist_ok=True)
    timing=output.with_name('docking_timing.jsonl')
    counts=dict(calls=0,rejected=0,future=0,dropped=0)
    pending=queue.Queue(maxsize=8192);closed=threading.Event()
    def emit(destination: str, row: dict) -> None:
        try:pending.put_nowait((destination,row))
        except queue.Full:counts['dropped']+=1
    def writer() -> None:
        with output.open('a') as fresh_stream,timing.open('a') as timing_stream:
            while not closed.is_set() or not pending.empty():
                try:destination,row=pending.get(timeout=.2)
                except queue.Empty:
                    fresh_stream.flush();timing_stream.flush();continue
                stream=fresh_stream if destination=='fresh' else timing_stream
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    worker=threading.Thread(target=writer,name='docking_trace_writer',daemon=True);worker.start()
    frames={};native={}
    def begin(code,offset):
        key=(threading.get_ident(),code)
        frames.setdefault(key,[]).append((time.monotonic_ns(),time.thread_time_ns()))
    def elapsed(code,start,cpu,kind,**extra):
        ns=time.monotonic_ns()-start;cpu_ns=time.thread_time_ns()-cpu
        if ns>=3_000_000 or code.co_name=='renew':
            emit('timing',dict(kind=kind,function=code.co_qualname,wall=time.time(),
                mono_ns=time.monotonic_ns(),elapsed_ms=ns/1e6,thread_cpu_ms=cpu_ns/1e6,
                thread=threading.get_native_id(),**extra))
    def returned(code,offset,value):
        key=(threading.get_ident(),code)
        if frames.get(key):
            start,cpu=frames[key].pop();elapsed(code,start,cpu,'python')
        if code is not PrecisionServer.fresh.__code__:return
        counts['calls']+=1
        if value:return
        frame=sys._getframe(1)
        if frame.f_code is not code:return
        counts['rejected']+=1
        if frame.f_locals.get('age',0)<0:counts['future']+=1
        message=frame.f_locals.get('message');header=getattr(message,'header',None)
        emit('fresh',dict(wall=time.time(),mono_ns=time.monotonic_ns(),
            age_s=frame.f_locals.get('age'),limit_s=frame.f_locals.get('limit'),result=value,
            caller=frame.f_back.f_code.co_name,message_type=type(message).__name__,
            frame_id=getattr(header,'frame_id',None)))
    def unwound(code,offset,error):
        key=(threading.get_ident(),code)
        if frames.get(key):
            start,cpu=frames[key].pop();elapsed(code,start,cpu,'python_exception',error=str(error))
    def c_begin(code,offset,callable,arg):
        if hasattr(callable,'__code__'):return
        native[(threading.get_ident(),code,offset)]=(time.monotonic_ns(),time.thread_time_ns(),
            getattr(callable,'__qualname__',type(callable).__name__))
    def c_end(code,offset,callable,arg):
        item=native.pop((threading.get_ident(),code,offset),None)
        if item:elapsed(code,item[0],item[1],'native',callee=item[2])
    selected=[getattr(PrecisionServer,name).__code__ for name in (
        'fresh','consume_image','_consume_image_locked','process_pose_image','solve',
        'control_tick','activate_profile','update_target_control')]
    selected += [LeaseClient.renew.__code__,LeaseClient.call.__code__,
                 solve_marker.__code__,compose_marker.__code__]
    tool=sys.monitoring.PROFILER_ID;ev=sys.monitoring.events
    sys.monitoring.use_tool_id(tool,'docking diagnostic')
    for event,callback in ((ev.PY_START,begin),(ev.PY_RETURN,returned),(ev.PY_UNWIND,unwound),
                           (ev.CALL,c_begin),(ev.C_RETURN,c_end),(ev.C_RAISE,c_end)):
        sys.monitoring.register_callback(tool,event,callback)
    for code in selected:
        sys.monitoring.set_local_events(tool,code,ev.PY_START|ev.PY_RETURN|ev.CALL|ev.C_RETURN|ev.C_RAISE)
    # Python3.12의 PY_UNWIND는 전역 이벤트만 지원한다. 선택 함수의 스택만 처리한다.
    sys.monitoring.set_events(tool,ev.PY_UNWIND)
    try:main()
    finally:
        sys.monitoring.free_tool_id(tool)
        closed.set();worker.join(timeout=3.)
        output.with_suffix('.summary.json').write_text(json.dumps(counts,indent=2)+'\n')
