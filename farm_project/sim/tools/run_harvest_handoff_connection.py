"""생성된 인계 설정의 정차 연결 시험. 시작한 프로세스만 정리한다."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
base=Path(sys.argv[1]).resolve();runtime=base/'runtime'
aligned='--aligned' in sys.argv[2:]
if (base/'connection_result.json').exists():raise FileExistsError('기존 시험 결과 보존')
if os.environ.get('ROS_DOMAIN_ID')!='13' or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE')!='SUBNET':
    raise ValueError('ROS Domain13/SUBNET 필요')
fleet=json.loads((runtime/'fleet.json').read_text())
fleet['device_configs']=[p for p in fleet['device_configs'] if not p.endswith('/scout_fleet.json')]
(runtime/'connection_fleet.json').write_text(json.dumps(fleet,indent=2)+'\n')
processes=[];logs=[]
def start(name,cmd):
    log=(base/(name+'.log')).open('w');logs.append(log)
    process=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    processes.append((name,process));return process
try:
    start('harvest',['ros2','launch','farm_bringup','harvest.launch.py','mode:=sim','project_root:='+str(ROOT),
        'environment_config:='+str(runtime/'harvest_runtime.yaml'),'handoff_config:='+str(runtime/'handoff.json'),
        'tag_correction:=false'])
    start('transport_adapter',['ros2','run','farm_sim_devices','ros_adapter','--ros-args','-r','__ns:=/transport_01',
        '-p','use_sim_time:=true','-p','config_file:='+str(ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json')])
    start('isaac',['ros2','launch','farm_sim_runtime','isaac.launch.py','project_root:='+str(ROOT),
        'fleet_config:='+str(runtime/'connection_fleet.json'),'headless:=true','physics_device:=cpu','duration_s:=180',
        'isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python'])
    probe=start('connection_probe',['/usr/bin/python3','sim/tools/probe_harvest_handoff_connection.py',str(base/'connection_result.json')]+(['--aligned'] if aligned else []))
    deadline=time.monotonic()+270
    while probe.poll() is None:
        if any(p.poll() is not None for n,p in processes if n!='connection_probe'):
            raise RuntimeError('시험 프로세스 종료; 로그 확인')
        if time.monotonic()>deadline:raise TimeoutError('연결 시험 제한시간')
        time.sleep(1)
    if probe.returncode:raise RuntimeError('연결 시험 실패; result/log 확인')
finally:
    for name,p in reversed(processes):
        if p.poll() is None:os.killpg(p.pid,signal.SIGINT)
    deadline=time.monotonic()+45
    while any(p.poll() is None for _,p in processes) and time.monotonic()<deadline:time.sleep(.5)
    for name,p in processes:
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
    (base/'process_exit.json').write_text(json.dumps({n:p.poll() for n,p in processes},indent=2)+'\n')
    for log in logs:log.close()
