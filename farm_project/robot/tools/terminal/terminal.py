"""Vic 터미널 실행 도우미. 기존 프로세스는 종료하지 않는다."""
from pathlib import Path
import sys,os,json,shlex,fcntl,time
ROOT=Path(__file__).resolve().parents[3]
BASE=Path(__file__).resolve().parent
CAND=Path('/home/vic/Downloads/pc_dummy_fsm_candidate_20261023')

def processes() -> list:
    result=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid(): continue
        try:
            args=(p/'cmdline').read_bytes().decode().strip('\0').split('\0')
            if args and args[0]:result.append((int(p.name),args))
        except (OSError,UnicodeError):pass
    return result

def conflicts(mode: str, rows: list) -> list:
    out=[]
    for pid,args in rows:
        joined=' '.join(args)
        bridge=any(Path(a).name in ('zenoh-bridge-ros2dds','binary') for a in args[:1])
        if mode=='launch' and (any(Path(a).name in ('harvest_node','controller_server','vic_pinky_bringup') for a in args[:2]) or 'harvest.launch.py' in args or 'vicpinky_bringup' in joined):out.append((pid,args))
        if mode=='zenoh' and bridge and str(CAND/'robot-bridge.json') not in args:out.append((pid,args))
        if mode=='dummy-zenoh' and bridge and str(CAND/'robot-bridge.json') in args:out.append((pid,args))
    return out

def main() -> None:
    if len(sys.argv)<2:raise SystemExit('launch / init / zenoh / dummy-zenoh / status [--check]')
    mode=sys.argv[1];check=sys.argv[2:]==['--check']
    if sys.argv[2:] and not check:raise SystemExit('허용 인자: --check')
    rows=processes()
    if mode=='status':
        for pid,args in rows:
            if any(x in ' '.join(args) for x in ('harvest_node','harvest.launch.py','zenoh-bridge','backup/binary')) and args[0] not in ('bash','ssh'):print(pid,shlex.join(args))
        return
    commands={
        'launch':['ros2','launch','farm_bringup','harvest.launch.py',f'project_root:={ROOT}','mode:=real',f'environment_config:={ROOT}/robot/config/environments/harvest_handoff_real.yaml','devices:=true','navigation:=true','tag_correction:=true','tag_camera:=true',f'handoff_config:={ROOT}/robot/config/robots/vicpinky/transfer/handoff_fsm.json'],
        'init':['python3','/home/vic/Downloads/init_station_newmap.py'],
        'zenoh':['/usr/bin/zenoh-bridge-ros2dds','--config','/home/vic/Downloads/handoff_completion_fix/zenoh_harvest_handoff_v2.json5','--domain','77','--ros-automatic-discovery-range','LOCALHOST','--no-multicast-scouting','-e','tcp/192.168.0.20:7447'],
        'dummy-zenoh':['/home/vic/Downloads/zenoh_callback_candidate_20261023/candidate/zenoh-bridge-ros2dds','--config',str(CAND/'robot-bridge.json')]}
    if mode not in commands:raise SystemExit('알 수 없는 명령')
    paths={'launch':[ROOT/'robot/config/environments/harvest_handoff_real.yaml',ROOT/'robot/config/harvest/harvest_handoff_real.json',ROOT/'robot/config/robots/vicpinky/transfer/handoff_fsm.json'], 'init':[Path(commands['init'][1])], 'zenoh':[Path(commands['zenoh'][0]),Path(commands['zenoh'][2])], 'dummy-zenoh':[Path(commands['dummy-zenoh'][0]),CAND/'robot-bridge.json']}
    assert all(p.is_file() for p in paths[mode]),'필수 파일 없음'
    if mode=='launch':
        assert json.loads((ROOT/'robot/config/harvest/harvest_handoff_real.json').read_text())['completion_policy']=='ARRIVAL_THEN_ARM'
        os.environ['HANDOFF_TF_EXECUTOR']='dedicated';os.environ['HANDOFF_TIMING']='1'
    if mode=='dummy-zenoh':
        os.environ['CYCLONEDDS_URI']='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="lo"/></Interfaces><AllowMulticast>false</AllowMulticast></General><Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>64</MaxAutoParticipantIndex><Peers><Peer Address="127.0.0.1"/></Peers></Discovery></Domain></CycloneDDS>'
    cmd=commands[mode]
    if check:
        print('CHECK_ONLY:',shlex.join(cmd));print('기존 실행 충돌 PID:',[p for p,a in conflicts(mode,rows)]);return
    lockdir=Path.home()/'.cache/manyfarm';lockdir.mkdir(parents=True,exist_ok=True)
    lock=open(lockdir/('terminal-'+mode+'.lock'),'a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('같은 터미널 명령이 이미 실행 중')
    os.set_inheritable(lock.fileno(),True)
    clash=conflicts(mode,processes())
    if clash:
        print('중복 기동 차단. 기존 프로세스를 임의 종료하지 않습니다:',[(p,a[0]) for p,a in clash]);raise SystemExit(3)
    if mode=='init':
        print('기존 스테이션의 정확한 위치·방향에 놓은 경우만 실행합니다. window에서는 실행 금지.',flush=True)
        import rclpy
        from nav_msgs.msg import Odometry
        from farm_interfaces.msg import RobotStatus
        from rclpy.qos import qos_profile_sensor_data
        rclpy.init();n=rclpy.create_node('terminal_initialpose_guard');od=[];st=[]
        n.create_subscription(Odometry,'/harvest_01/odom',lambda m:od.append((time.monotonic(),m)),qos_profile_sensor_data)
        n.create_subscription(RobotStatus,'/harvest_01/status',lambda m:st.append((time.monotonic(),m)),10)
        end=time.monotonic()+2
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.1)
        now=time.monotonic();recent=[m for t,m in od if now-t<1]
        safe=len(recent)>=10 and st and now-st[-1][0]<2 and st[-1][1].state=='IDLE' and not st[-1][1].current_task_id and all(abs(m.twist.twist.linear.x)+abs(m.twist.twist.angular.z)<1e-6 for m in recent)
        n.destroy_node();rclpy.shutdown()
        if not safe:raise SystemExit('정지/IDLE 미확인: 초기위치 발행 안 함')
    logs=Path.home()/'vmany-terminal-logs';logs.mkdir(exist_ok=True)
    stamp=time.strftime('%Y%m%d_%H%M%S');folder=logs/(stamp+'_'+mode+'_'+str(os.getpid()));folder.mkdir()
    if mode=='launch':os.environ['HANDOFF_INPUT_TRACE']=str(folder/'trace')
    print('로그:',folder/'console.log',flush=True);os.chdir(ROOT)
    os.execvp('bash',['bash','-c','set -o pipefail; '+shlex.join(cmd)+' 2>&1 | tee '+shlex.quote(str(folder/'console.log'))])

if __name__=='__main__':main()
