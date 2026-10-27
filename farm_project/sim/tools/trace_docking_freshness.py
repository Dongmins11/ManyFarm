"""Python3.12 모니터링으로 공통 fresh()의 실패 당시 age를 기록한다. 반환값은 바꾸지 않는다."""
import json
import os
from pathlib import Path
import sys
import time

from farm_docking.precision_server import PrecisionServer, main


if __name__=='__main__':
    output=Path(os.environ['DOCKING_FRESHNESS_TRACE'])
    output.parent.mkdir(parents=True,exist_ok=True)
    counts=dict(calls=0,rejected=0,future=0)
    def returned(code, offset, value):
        counts['calls']+=1
        if value:return
        frame=sys._getframe(1)
        if frame.f_code is not code:return
        counts['rejected']+=1
        if frame.f_locals.get('age',0)<0:counts['future']+=1
        message=frame.f_locals.get('message')
        header=getattr(message,'header',None)
        with output.open('a') as stream:
            stream.write(json.dumps(dict(wall=time.time(),age_s=frame.f_locals.get('age'),
                limit_s=frame.f_locals.get('limit'),result=value,
                caller=frame.f_back.f_code.co_name,message_type=type(message).__name__,
                frame_id=getattr(header,'frame_id',None)))+'\n')
    tool=sys.monitoring.PROFILER_ID
    sys.monitoring.use_tool_id(tool,'docking freshness diagnostic')
    sys.monitoring.register_callback(tool,sys.monitoring.events.PY_RETURN,returned)
    sys.monitoring.set_local_events(tool,PrecisionServer.fresh.__code__,sys.monitoring.events.PY_RETURN)
    try:main()
    finally:
        sys.monitoring.free_tool_id(tool)
        output.with_suffix('.summary.json').write_text(json.dumps(counts,indent=2)+'\n')
