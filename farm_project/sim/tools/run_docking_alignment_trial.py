"""분리 도킹 시험을 실행하고 자신이 시작한 프로세스만 종료한다. 준비 도구 선행 필요."""
from pathlib import Path
import os,subprocess,time,signal,sys,json
root=Path(__file__).resolve().parents[2];base=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/'sim/runs/docking_alignment_20261027';phase=sys.argv[1];out=base/phase
if (out/'result.json').exists():raise FileExistsError('기존 시험 결과 보존: '+str(out))
sorter='--sorter' in sys.argv[3:]
processes=[];files=[]
def start(name,args):
 f=(out/(name+'.log')).open('w');files.append(f);p=subprocess.Popen(args,cwd=root,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);processes.append((name,p));return p
try:
 for robot in ['harvest','transport']:
  start(robot+'_adapter',['ros2','run','farm_sim_devices','ros_adapter','--ros-args','-r','__ns:=/'+robot+'_01','-p','use_sim_time:=true','-p','config_file:='+str(out/(robot+'.json'))])
 start('gate',['ros2','run','farm_docking','motion_gate','--ros-args','-r','__ns:=/transport_01','-p','use_sim_time:=true'])
 os.environ['DOCKING_FRESHNESS_TRACE']=str(out/'freshness_trace.jsonl')
 start('precision',['/usr/bin/python3','sim/tools/trace_docking_freshness.py','--ros-args','--params-file',str(base/'params.yaml'),'-r','__ns:=/transport_01','-r','/cmd_vel:=motion/precision','-r','/odom:=odom','-r','/dock/cmd:=precision_legacy_disabled','-r','/dock/state:=precision_legacy_state'])
 if sorter:
  start('navigation',['ros2','launch','farm_sim_runtime','transport_navigation.launch.py','project_root:='+str(root),'environment_config:='+str(out/'transport_runtime.yaml'),'journal_dir:='+str(out/'journal')])
 start('isaac',['ros2','launch','farm_sim_runtime','isaac.launch.py','project_root:='+str(root),'fleet_config:='+str(out/'fleet.json'),'headless:=true','physics_device:=cpu','duration_s:='+('600' if sorter else '200'),'isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python'])
 probe=start('probe',['/usr/bin/python3','sim/tools/docking_alignment_probe.py','--marker',phase.split('_')[0],'--output',str(out)]+(['--handoff'] if '--handoff' in sys.argv[3:] else [])+(['--sorter-profile',str(out/'transport_runtime.yaml')] if sorter else []))
 deadline=time.monotonic()+(800 if sorter else 420)
 while probe.poll() is None:
  failed=[(name,p.returncode) for name,p in processes if name!='probe' and p.poll() is not None]
  if failed:raise RuntimeError('Child exited: '+str(failed))
  if time.monotonic()>deadline:raise TimeoutError('trial watchdog')
  time.sleep(1)
 print('PROBE_EXIT',probe.returncode,flush=True)
 if probe.returncode!=0:raise RuntimeError('시험 probe 실패: '+str(probe.returncode))
finally:
 for name,p in reversed(processes):
  if p.poll() is None:os.killpg(p.pid,signal.SIGINT)
 deadline=time.monotonic()+55
 while any(p.poll() is None for _,p in processes) and time.monotonic()<deadline:time.sleep(1)
 for name,p in processes:
  if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
 (out/'process_exit.json').write_text(json.dumps({n:p.poll() for n,p in processes},indent=2)+'\n')
 for f in files:f.close()
