"""격리 fleet에서 수확 차체 회전→정지 응답을 측정한다. Nav2 E2E 시험은 아니다."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim/ros_ws/src/farm_sim_devices'))
from farm_sim_devices.wire import LocalDatagrams


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--servo',action='store_true')
    parser.add_argument('--heading',action='store_true')
    args=parser.parse_args()
    directory=ROOT/f'sim/runs/harvest_braking_20261007_servo{int(args.servo)}_heading{int(args.heading)}'
    directory.mkdir(parents=True,exist_ok=True)
    config=ROOT/'sim/ros_ws/src/farm_sim_config/config'
    fleet=json.loads((config/'harvest_fleet.json').read_text())
    devices=[]
    for i,file in enumerate(fleet['device_configs']):
        device=json.loads((ROOT/file).read_text())
        device['runtime'].update(command_port=22600+i*10,telemetry_port=22601+i*10)
        if device['robot_id']=='harvest_01':
            device['base'].pop('wheel_velocity_servo',None)
            if args.servo:device['base']['wheel_velocity_servo']=dict(kp=1.,ki=4.,max_correction_rad_s=2.,dt_s=1/60)
        device['camera']['shm_name']='braking_test_'+device['robot_id']
        path=directory/(device['robot_id']+'.json');path.write_text(json.dumps(device));devices.append(str(path.relative_to(ROOT)))
    audit=json.loads((ROOT/fleet['evaluation_config']).read_text())
    audit['evaluation']['snapshot_file']=str((directory/'scene.json').relative_to(ROOT))
    audit['output_dir']=str(directory.relative_to(ROOT))
    audit_path=directory/'audit.json';audit_path.write_text(json.dumps(audit))
    fleet['evaluation_config']=str(audit_path.relative_to(ROOT))
    fleet['device_configs']=devices;fleet['clock']=dict(command_port=22690,telemetry_port=22691)
    path=directory/'fleet.json';path.write_text(json.dumps(fleet))
    command=[str(Path.home()/'isaac/env_isaaclab/bin/python'),str(ROOT/'sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py'),
        '--project-root',str(ROOT),'--fleet-config',str(path),'--headless','--duration-s','32']
    for p in ['sim/ros_ws/src/farm_sim_devices','sim/ros_ws/src/farm_sim_runtime','robot/ros_ws/src/farm_common']:
        command+=['--module-path',str(ROOT/p)]
    transport=LocalDatagrams(22611,22610)
    heading_runs=[];heading_phase=0;heading_target=None;stop_time=None
    samples=[];latest=None;session=None;start=time.monotonic();last=0.
    with (directory/'isaac.log').open('w') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        try:
            while process.poll() is None and time.monotonic()-start<240:
                for packet in transport.receive():
                    if packet.get('kind')=='state':
                        latest=packet;session=packet['session'];samples.append(packet)
                if latest and time.monotonic()-last>.02:
                    t=latest['stamp_ns']/1e9
                    # 기존 고속과 저속 조건을 같은 차체에서 비교하고 반대 방향도 확인한다.
                    w=.5 if 3<=t<6 else .06 if 13<=t<18 else -.06 if 23<=t<28 else 0.
                    if args.heading:
                        w=0.
                        if t>=3 and heading_phase<2:
                            direction=1. if heading_phase==0 else -1.
                            if heading_target is None:
                                heading_target=latest['odom'][2]+direction*.3
                            error=math.remainder(heading_target-latest['odom'][2],2*math.pi)
                            if stop_time is None and direction*error>.01:
                                w=direction*.06
                            elif stop_time is None:
                                stop_time=t
                            elif t-stop_time>=3.:
                                heading_runs.append(dict(target=heading_target,actual=latest['odom'][2],error_rad=error))
                                heading_phase+=1;heading_target=None;stop_time=None
                    transport.send(dict(kind='cmd',session=session,seq=time.monotonic_ns(),sent=time.monotonic(),linear=0.,angular=w))
                    last=time.monotonic()
                time.sleep(.005)
            if process.poll() is None:
                process.terminate();process.wait(timeout=60)
        finally:
            transport.close()
    (directory/'states.json').write_text(json.dumps(samples))
    cases=[]
    if samples:
        nearest=lambda t:min(samples,key=lambda row:abs(row['stamp_ns']/1e9-t))
        for begin,end,speed in [(3,6,.5),(13,18,.06),(23,28,-.06)]:
            first,stop,settled=map(nearest,[begin,end,end+3])
            cases.append(dict(command_rad_s=speed,
                rotation_rad=math.remainder(stop['odom'][2]-first['odom'][2],2*math.pi),
                residual_rad=math.remainder(settled['odom'][2]-stop['odom'][2],2*math.pi)))
    checks=dict(clean_exit=process.returncode==0,complete=len(samples)>900,
        positive_low_speed=bool(len(cases)==3 and cases[1]['rotation_rad']>.15),
        negative_low_speed=bool(len(cases)==3 and cases[2]['rotation_rad']<-.15),
        low_speed_braking=bool(len(cases)==3 and max(abs(c['residual_rad']) for c in cases[1:])<.03))
    if args.heading:
        cases=[]
        checks=dict(clean_exit=process.returncode==0,complete=len(heading_runs)==2,
            heading_settled=bool(len(heading_runs)==2 and max(abs(r['error_rad']) for r in heading_runs)<.05))
    result=dict(heading_runs=heading_runs,returncode=process.returncode,session=session,sample_count=len(samples),cases=cases,
        checks=checks,passed=all(checks.values()),scope='isolated physical wheel odometry response; not Nav2 E2E')
    (directory/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
