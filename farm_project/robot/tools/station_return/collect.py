"""실물 복귀 구독 전용 기록. 기존 forward_transition_capture 도구를 재사용한다.
운영 명령 없이 경로·TF·odom·레이저·속도·태그를 기록하고 자신의 recorder만 종료한다.
"""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,os,shutil,signal,subprocess,time,sys
ROOT=Path('/home/vic/vmany/main/farm_project')
TOPICS=['map','initialpose','odom','amcl_pose','tf','tf_static','scan','scan_filtered','cmd_vel_normal','cmd_vel_nav','cmd_vel','lookahead_point','curvature_lookahead_point','is_rotating_to_heading','received_global_plan','lookahead_collision_arc','local_costmap/costmap_raw','local_costmap/costmap_raw_updates','local_costmap/costmap','local_costmap/costmap_updates','local_costmap/published_footprint','status','task_events','tag_localization/control','tag_localization/correction','tag_localization/events']
# 복귀 전용 서버의 원호 입력·충돌 예측·실제 costmap도 함께 보존한다.
TOPICS += ['station_corner/'+name for name in ('raw_nav', 'received_global_plan', 'lookahead_collision_arc', 'local_costmap/costmap_raw', 'local_costmap/costmap_raw_updates', 'local_costmap/published_footprint')]
# 후진 제어기는 일부 RPP 진단 토픽을 발행하지 않을 수 있다. 주행을 차단하지 않는다.
REQUIRED=['odom','tf','amcl_pose','scan_filtered','cmd_vel_normal']
EXTRA=['/apriltag_camera/detections','/harvest_01/follow_path/_action/feedback','/harvest_01/follow_path/_action/status','/harvest_01/return_to_station/_action/feedback','/harvest_01/return_to_station/_action/status']

EXTRA += ['/harvest_01/station_corner/follow_path/_action/'+name for name in ('feedback', 'status')]

def main() -> int:
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seconds',type=int,default=300);args=parser.parse_args()
 if not 30<=args.seconds<=600:parser.error('seconds는30~600')
 if os.environ.get('ROS_DOMAIN_ID')!='77':raise SystemExit('Domain77 환경 필요')
 lock=open('/tmp/manyfarm_station_return_capture.lock','w')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('같은 수집기가 이미 실행 중')
 if shutil.disk_usage(ROOT).free<3.25*1024**3:raise SystemExit('수집 공간 부족: 운영 카메라용 여유 보존, 자동 삭제 없음')
 stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');out=ROOT/'runs/station_return_capture'/stamp;out.mkdir(parents=True)
 print('CAPTURE_DIRECTORY='+str(out),flush=True)
 launch_logs=list(Path('/home/vic/vmany-terminal-logs').glob('*_launch_*/console.log'))
 launch_log=max(launch_logs,key=lambda p:p.stat().st_mtime) if launch_logs else None
 if launch_log:(out/'launch_before.log').write_bytes(launch_log.read_bytes())
 # 운영 파일의 읽기 사본과 해시. 서비스·Action 호출 없음.
 for index,p in enumerate([ROOT/'robot/config/robots/vicpinky/nav2.yaml',ROOT/'robot/config/navigation/harvest_nav2.yaml',ROOT/'robot/config/navigation/harvest_task.yaml',ROOT/'robot/config/maps/many_farm/graph.geojson',ROOT/'robot/config/localization/harvest_handoff_real.yaml',Path('/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/config/harvest_station_return_jetson_real.yaml')]):
  if p.is_file():(out/(str(index)+'_'+p.name)).write_bytes(p.read_bytes())
 processes=[]
 for p in Path('/proc').glob('[0-9]*/cmdline'):
  try:argv=[a.decode() for a in p.read_bytes().split(b'\0') if a]
  except (OSError,UnicodeError):continue
  if not any(Path(a).name in ['controller_server','harvest_node','velocity_smoother','amcl'] for a in argv[:2]):continue
  processes.append({'pid':p.parent.name,'argv':argv})
  for i,a in enumerate(argv[:-1]):
   if a=='--params-file' and Path(argv[i+1]).is_file():(out/(p.parent.name+'_'+str(i)+'_params.yaml')).write_bytes(Path(argv[i+1]).read_bytes())
 (out/'processes.json').write_text(json.dumps(processes,indent=2))
 import rclpy
 rclpy.init(args=[]);node=rclpy.create_node('station_return_capture_inventory')
 deadline=time.monotonic()+12
 while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.1)
 graph={t:node.count_publishers('/harvest_01/'+t) for t in TOPICS}
 (out/'publishers.json').write_text(json.dumps(graph,indent=2));node.destroy_node();rclpy.shutdown()
 missing=[t for t in REQUIRED if not graph[t]]
 if missing:print('NOT_READY: publisher 누락 '+str(missing),flush=True);return 2
 log=open(out/'recorder.log','w');stop=[False]
 def request_stop(signum: int, frame: object) -> None:stop[0]=True
 signal.signal(signal.SIGINT,request_stop);signal.signal(signal.SIGTERM,request_stop)
 command=['ros2','bag','record','--include-hidden-topics','-s','mcap','-o',str(out/'bag')]+['/harvest_01/'+t for t in TOPICS]+EXTRA+['/rosout','/parameter_events']
 child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 timing=subprocess.Popen([sys.executable,str(Path(__file__).with_name('timing_capture.py')),str(out/'timing.jsonl')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 started=time.monotonic();announced=False;reason='duration'
 try:
  while child.poll() is None and not stop[0]:
   if timing.poll() is not None:reason='timing_capture_failed';break
   elapsed=time.monotonic()-started
   if elapsed>args.seconds:break
   size=sum(p.stat().st_size for p in (out/'bag').glob('*') if p.is_file())
   if size>=256*1024**2 or shutil.disk_usage(ROOT).free<3.1*1024**3:reason='space_limit';break
   data=(out/'recorder.log').read_text(errors='replace')
   if not announced and all("Subscribed to topic '/harvest_01/"+t+"'" in data for t in REQUIRED):
    announced=True;print('CAPTURE_READY: 수집 연결 완료. 실제 자세·초기위치 확인 후 복귀 명령을 한 번만 전송하세요.',flush=True)
   if not announced and elapsed>25:reason='subscriptions_missing';break
   time.sleep(.25)
 finally:
  if child.poll() is None:
   os.killpg(child.pid,signal.SIGINT)
   try:child.wait(timeout=20)
   except subprocess.TimeoutExpired:
    print('recorder 종료 지연: PID '+str(child.pid)+'; 강제 종료하지 않았습니다.',flush=True);child.wait()
  if timing.poll() is None:
   os.killpg(timing.pid,signal.SIGINT)
   timing.wait(timeout=10)
  log.close()
 if launch_log:(out/'launch_after.log').write_bytes(launch_log.read_bytes())
 # 기존 태그 보정 JSONL에 보정 전/후 위치와 관측 편향이 있으므로 bag과 함께 보존한다.
 sessions=list((ROOT/'runs/harvest_tag').glob('*'))
 if sessions:
  session=max(sessions,key=lambda p:p.stat().st_mtime)
  (out/'tag_snapshot_source.json').write_text(json.dumps({'path':str(session),'mtime_ns':session.stat().st_mtime_ns,'note':'과거 세션일 수 있음. 이번 보정 여부는 bag/events와 시간 범위로 판정.'},ensure_ascii=False,indent=2))
  for p in session.rglob('*'):
   if p.is_file() and (p.name in ('events.jsonl','detections.jsonl','correction.log','settings.json','camera_info.json')):
    dest=out/'tag_snapshot'/p.relative_to(session);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 (out/'recording_scope.json').write_text(json.dumps({'topics':TOPICS,'extra':EXTRA,'note':'received_global_plan은 수신된 경우만 실제 경로 증거로 사용. publisher 존재만으로 경로 기록을 보장하지 않음.'},ensure_ascii=False,indent=2))
 files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
 (out/'manifest.json').write_text(json.dumps(files,indent=2));(out/'result.json').write_text(json.dumps({'ready':announced,'reason':'user_stop' if stop[0] else reason,'exit_code':child.returncode,'timing_exit_code':timing.returncode,'metadata_saved':(out/'bag/metadata.yaml').exists()},indent=2))
 print('CAPTURE_FINISHED='+str(out),flush=True)
 return 0 if announced and timing.returncode==0 and child.returncode in (0,130,-2) and (out/'bag/metadata.yaml').exists() else 3
if __name__=='__main__':raise SystemExit(main())
