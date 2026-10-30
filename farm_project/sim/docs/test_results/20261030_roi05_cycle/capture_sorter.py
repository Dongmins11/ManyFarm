"""별도 관측기: 원본 카메라/상태를 보존하며 로봇 명령은 보내지 않는다."""
import json, time
from pathlib import Path
import cv2
import numpy as np
base=Path(__file__).resolve().parent
out=base/'camera_history';out.mkdir(exist_ok=True)
last_key=None;last_image=-1;count=0;end=time.monotonic()+3600
with (out/'index.jsonl').open('a',buffering=1) as log:
 while time.monotonic()<end:
  try:
   runtime=json.loads((base/'sorting/runtime.json').read_text())
   state=json.loads((base/'sorting/state.json').read_text())
   report=json.loads((base/'sorting/physical_report.json').read_text())
   image=base/'sorting/camera_rgb.png';mtime=image.stat().st_mtime_ns
   key=(runtime['phase'],tuple(runtime['counts']),runtime['deposited'],tuple(state['zone_states'].values()))
   if key!=last_key and mtime!=last_image:
    data=image.read_bytes()
    if cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR) is not None:
     count+=1;name=f'{count:04d}'
     (out/(name+'.png')).write_bytes(data)
     info=dict(image=name+'.png',captured_wall=time.time(),image_mtime_ns=mtime,state=state,runtime=runtime,physical=report,note='RGB saved by runtime every 1 simulation second; state/image not hardware-synchronized')
     (out/(name+'.json')).write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
     log.write(json.dumps(dict(image=name+'.png',wall=info['captured_wall'],sim=runtime['sim_time'],phase=runtime['phase'],counts=runtime['counts'],states=state['zone_states']))+'\n')
     last_key=key;last_image=mtime
  except (OSError,ValueError,KeyError):pass
  if (base/'process_exit.json').exists():break
  time.sleep(.25)
print('camera snapshots:',count,flush=True)
