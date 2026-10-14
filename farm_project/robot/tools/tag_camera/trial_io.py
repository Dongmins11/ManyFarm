"""Local camera control verification and bounded PNG storage with explicit overflow accounting.
No ROS, navigation, TF, or network operations. V4L2 values are readbacks, not
per-frame sensor exposure metadata. Acquisition timestamps remain read completion.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time

COMMON = dict(brightness=128,contrast=128,saturation=128,white_balance_automatic=1,
              gain=5,power_line_frequency=1,sharpness=128)
MAX_BYTES=2*1024**3
MIN_FREE=3*1024**3

def atomic(path, data):
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    os.replace(tmp,path)

def parse_controls(text):
    result={}
    for line in text.splitlines():
        match=re.search(r'^\s*(\w+)\s+0x[0-9a-fA-F]+.*?\bvalue=(-?\d+)',line)
        if match:
            result[match[1]]=dict(value=int(match[2]),inactive='inactive' in line,
                                  volatile='volatile' in line)
    return result

def read_controls(device):
    r=subprocess.run(['v4l2-ctl','-d',device,'--list-ctrls'],capture_output=True,text=True,check=True,timeout=3)
    return dict(wall_time_ns=time.time_ns(),monotonic=time.monotonic(),raw=r.stdout,controls=parse_controls(r.stdout),
                actual_sensor_exposure_metadata=False)

def set_control(device,name,value):
    subprocess.run(['v4l2-ctl','-d',device,f'--set-ctrl={name}={int(value)}'],capture_output=True,text=True,check=True,timeout=3)

def expected_mode(label):
    if label not in ('auto','manual_2ms'):raise ValueError('invalid_trial_label')
    return 0 if label=='auto' else 1

def verify_controls(snapshot,label):
    c=snapshot['controls'];expected=expected_mode(label)
    for name,value in COMMON.items():
        if name not in c or c[name]['value']!=value:raise RuntimeError('common_camera_setting_mismatch:'+name)
    if c.get('auto_exposure',{}).get('value')!=expected:raise RuntimeError('exposure_mode_not_applied')
    if label=='manual_2ms' and (c.get('exposure_time_absolute',{}).get('value')!=20 or c['exposure_time_absolute']['inactive']):
        raise RuntimeError('manual_2ms_not_applied')
    return True

def request_state(path,now):
    if not path.exists():return False,None
    data=json.loads(path.read_text())
    token=data.get('token')
    if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{32}',token):raise ValueError('bad_record_token')
    active=data.get('enabled') is True and float(data.get('expires_mono',0))>now
    return active,token

class TrialIO:
    def __init__(self,output,device,label,*,encode=None):
        self.output=Path(output);self.device=device;self.label=label;expected_mode(label)
        self.before=read_controls(device);atomic(self.output/'camera_controls_before.json',self.before)
        for name in ('auto_exposure','exposure_time_absolute'):
            if name not in self.before['controls']:raise RuntimeError('missing_camera_control:'+name)
        self.q=queue.Queue(maxsize=8);self.stop=threading.Event();self.fault='';self.lock=threading.Lock()
        self.dropped=0;self.last_dropped_stamp_ns=None
        self.snapshot=None;self.recording=False;self.token=None;self.started=None;self.written=0;self.enqueued=0;self.bytes=0;self.last_write=None
        self.encode=encode;self.writer=None;self.poller=None;self.applied=False;self.last_status=0.;self.restored=False
        if shutil.disk_usage(self.output).free<MIN_FREE:raise RuntimeError('at_least_3GiB_free_required')
        self.frames=self.output/'raw_frames';self.frames.mkdir(exist_ok=False)
        self.index=(self.output/'frames.jsonl').open('x',buffering=1)
        self.control_log=(self.output/'camera_controls.jsonl').open('x',buffering=1)
    def apply_after_camera_open(self):
        # Set after OpenCV opens/configures the camera, then read back while streaming.
        self.applied=True
        set_control(self.device,'auto_exposure',expected_mode(self.label))
        if self.label=='manual_2ms':set_control(self.device,'exposure_time_absolute',20)
        self.snapshot=read_controls(self.device);verify_controls(self.snapshot,self.label)
        atomic(self.output/'camera_controls_applied.json',self.snapshot)
        self.control_log.write(json.dumps(self.snapshot)+'\n')
        self.writer=threading.Thread(target=self._writer,name='frame_writer',daemon=True);self.writer.start()
        self.poller=threading.Thread(target=self._poll,name='control_readback',daemon=True);self.poller.start()
        self.status(force=True)
        print('EXPOSURE_READY:',self.label,'| manual request = 2ms' if self.label=='manual_2ms' else '| actual per-frame exposure unknown',flush=True)
    def _poll(self):
        while not self.stop.wait(1.):
            try:
                snap=read_controls(self.device);verify_controls(snap,self.label)
                with self.lock:self.snapshot=snap
                self.control_log.write(json.dumps(snap)+'\n')
            except Exception as exc:self.fault='control_readback_failed:'+str(exc);return
    def _writer(self):
        try:
            if self.encode is None:
                import cv2
            while not self.stop.is_set() or not self.q.empty():
                try:frame,meta=self.q.get(timeout=.1)
                except queue.Empty:continue
                try:
                    if self.encode is None:
                        ok,encoded=cv2.imencode('.png',frame,[cv2.IMWRITE_PNG_COMPRESSION,1])
                        if not ok:raise RuntimeError('PNG_encode_failed')
                        payload=encoded.tobytes()
                    else:payload=self.encode(frame)
                    if self.bytes+len(payload)>MAX_BYTES:raise RuntimeError('recording_2GiB_limit')
                    if shutil.disk_usage(self.output).free<512*1024**2:raise RuntimeError('recording_disk_space_low')
                    filename=str(meta['source_stamp_ns'])+'.png'
                    with (self.frames/filename).open('xb') as f:f.write(payload)
                    meta.update(file='raw_frames/'+filename,bytes=len(payload),saved_wall_time_ns=time.time_ns())
                    self.index.write(json.dumps(meta,allow_nan=False)+'\n')
                    with self.lock:self.written+=1;self.bytes+=len(payload);self.last_write=time.monotonic()
                finally:self.q.task_done()
        except Exception as exc:self.fault='frame_writer_failed:'+str(exc)
    def before_publish(self):
        if self.fault:raise RuntimeError(self.fault)
        if self.snapshot is None or time.monotonic()-self.snapshot['monotonic']>3.5:raise RuntimeError('control_readback_stale')
        now=time.monotonic();active,token=request_state(self.output/'record_request.json',now)
        if self.token is not None and active and token!=self.token:raise RuntimeError('different_recording_session')
        if active:
            if self.started is None:self.started=now;self.token=token
            if now-self.started>180:raise RuntimeError('recording_180s_limit')
        if self.recording and not active:
            # An expired/disconnected recording request cannot silently resume in the same capture.
            self.recording=False
            atomic(self.output/'recording_ended.json',dict(token=self.token,wall_time_ns=time.time_ns()))
        elif active:
            if (self.output/'recording_ended.json').exists():raise RuntimeError('recording_already_ended_restart_capture')
            self.recording=True
        self.status()
    def record_published(self,frame,stamp_ns,frame_id):
        if self.recording:
            snap=self.snapshot
            meta=dict(source_stamp_ns=stamp_ns,frame_id=frame_id,encoding='bgr8',shape=list(frame.shape),
                      timestamp_basis='camera read completion, not sensor exposure timestamp',trial_label=self.label,
                      record_token=self.token,controls_read_wall_time_ns=snap['wall_time_ns'],
                      requested_exposure_s=.002 if self.label=='manual_2ms' else None,
                      actual_sensor_exposure_metadata=False)
            try:self.q.put_nowait((frame.copy(),meta));self.enqueued+=1
            except queue.Full:
                # ROS publication has already happened. Only optional disk storage is skipped.
                self.dropped+=1;self.last_dropped_stamp_ns=stamp_ns
                if self.dropped==1:
                    print('RECORDING_WARNING: PNG queue full; camera and detection continue. Missing saved frames are counted.',flush=True)
        self.status()
    def status(self,force=False):
        now=time.monotonic()
        if not force and now-self.last_status<.3:return
        self.last_status=now
        with self.lock:
            snap=self.snapshot
            atomic(self.output/'camera_io_status.json',dict(trial_label=self.label,control_ready=bool(snap) and not self.fault,
                control_age_s=None if not snap else now-snap['monotonic'],fault=self.fault,
                recording_active=self.recording,record_token=self.token,frames_enqueued=self.enqueued,frames_written=self.written,
                frames_dropped=self.dropped,last_dropped_stamp_ns=self.last_dropped_stamp_ns,
                recording_warning='frame_writer_queue_full' if self.dropped else '',queue_depth=self.q.qsize(),bytes_written=self.bytes,last_write_age_s=None if self.last_write is None else now-self.last_write,
                closed=False))
    def close(self):
        self.recording=False;self.stop.set()
        for thread in (self.poller,self.writer):
            if thread:thread.join(timeout=6)
        if any(t and t.is_alive() for t in (self.poller,self.writer)):self.fault=self.fault or 'writer_or_control_thread_not_drained'
        if self.enqueued!=self.written:self.fault=self.fault or 'incomplete_frame_write'
        restore_error=None
        try:
            if self.applied:
                before=self.before['controls']
                # Restore the saved manual-register value first, then the original mode.
                set_control(self.device,'auto_exposure',1)
                set_control(self.device,'exposure_time_absolute',before['exposure_time_absolute']['value'])
                set_control(self.device,'auto_exposure',before['auto_exposure']['value'])
                restored=read_controls(self.device)
                if any(restored['controls'][k]['value']!=before[k]['value'] for k in ('auto_exposure','exposure_time_absolute')):
                    raise RuntimeError('restoration_readback_mismatch')
                self.restored=True;atomic(self.output/'camera_controls_restored.json',restored)
        except Exception as exc:restore_error=str(exc)
        if not any(t and t.is_alive() for t in (self.poller,self.writer)):
            self.index.close();self.control_log.close()
        atomic(self.output/'recording_summary.json',dict(trial_label=self.label,record_token=self.token,frames_enqueued=self.enqueued,
            frames_written=self.written,frames_dropped=self.dropped,last_dropped_stamp_ns=self.last_dropped_stamp_ns,
            recording_warning='frame_writer_queue_full' if self.dropped else '',
            bytes_written=self.bytes,complete=self.enqueued>0 and self.enqueued==self.written and not self.fault and self.dropped==0,
            fault=self.fault,controls_restored=self.restored,restore_error=restore_error,
            no_motion_commands=True,localization_correction=False))
        atomic(self.output/'camera_io_status.json',dict(closed=True,control_ready=False,recording_active=False,fault=self.fault))
        print('RECORDING_SAVED:',self.written,'frames | controls_restored=',self.restored,flush=True)
        if self.fault or restore_error:raise RuntimeError(self.fault or ('camera_control_restore_failed:'+restore_error))
