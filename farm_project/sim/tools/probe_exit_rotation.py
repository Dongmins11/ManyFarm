"""독립 fleet의 운송 장치에만 회전 명령을 보내는 물리 재현 시험. ROS 판정 시험 아님."""
import json
from pathlib import Path
import socket
import sys
import time

base=Path(sys.argv[1]).resolve()
config=json.loads((base/'transport.json').read_text())
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
sock.bind(('127.0.0.1',config['runtime']['telemetry_port']))
sock.settimeout(.2)
peer=('127.0.0.1',config['runtime']['command_port'])
fixture=json.loads((base/'fixture.json').read_text())
replay=fixture.get('replay_commands',[])
end_sim=fixture.get('end_sim',28.)
sequence=0;state=None;session=None;sim=0.
started=time.monotonic()
with (base/'commands.jsonl').open('w',buffering=1) as stream:
    try:
        while time.monotonic()-started<fixture.get('wall_timeout_s',180):
            try:
                raw,source=sock.recvfrom(65535)
                if source!=peer:continue
                state=json.loads(raw)
                if state.get('kind')!='state':continue
                session=state['session'];sim=state['stamp_ns']/1e9
            except socket.timeout:
                if state is None:continue
                if time.monotonic()-state['sent']>2.:break
            linear=0.;command=-.3 if 3.<=sim<23. else 0.
            if replay:
                eligible=[r for r in replay if r['time']<=sim-3.]
                linear,command=eligible[-1]['command'] if eligible and sim<end_sim-2. else (0.,0.)
            sequence+=1
            msg=dict(version=1,kind='cmd',session=session,seq=sequence,sent=time.monotonic(),linear=linear,angular=command)
            sock.sendto(json.dumps(msg).encode(),peer)
            stream.write(json.dumps(dict(sim=sim,session=session,mono=time.monotonic(),linear=linear,angular=command,odom=state['odom']))+'\n')
            if sim>=end_sim:break
    finally:
        if session:
            sequence+=1
            sock.sendto(json.dumps(dict(version=1,kind='cmd',session=session,seq=sequence,sent=time.monotonic(),linear=0.,angular=0.)).encode(),peer)
        sock.close()
(base/'probe_result.json').write_text(json.dumps(dict(session=session,last_sim=sim,completed=sim>=end_sim))+'\n')
