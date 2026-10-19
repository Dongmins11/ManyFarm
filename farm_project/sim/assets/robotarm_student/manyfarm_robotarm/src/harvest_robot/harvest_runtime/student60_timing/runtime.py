"""Independent capture, vision, decision and20Hz command dispatch.

All data accepted here is camera/public geometry or measured proprioception.
No simulator target/contact/phase/success is an input. No hardware I/O exists.
"""
from heapq import heappush,heappop
import math
import numpy as np
from harvest_vision.geometry import Frame
from harvest_vision.student60_tracking import AssignedFruitTracker
from harvest_vision.student60_camera_center import selected_record
from ..student60_latest_vision import owned_snapshot
from .pipeline import LatestServer,CameraDelivery,command_gate
from .controller import phase_from_note


class TimingRuntime:
    def __init__(self,controller,vision_processor,profile,arm_from_world,roi,assigned_id,label,initial_command,
                 *,mode='virtual',clock=None,measure_floor=True,center_corrector=None):
        import time
        self.controller=controller;self.profile=profile;self.arm_from_world=np.asarray(arm_from_world,float)
        self.mode=mode;self.clock=clock or time.monotonic;self.assigned_id=assigned_id;self.label=label
        self.center_corrector=center_corrector;self.last_applied=np.asarray(initial_command).copy()
        self.camera=CameraDelivery(profile);self.proprio_events=[];self.proprio=None;self.event_sequence=0
        self.tracker=AssignedFruitTracker(roi);self.detections=[];self.last_rear=-1;self.retired=None;self.fault=None
        self.pending_payload=None;self.last_tick=None;self.commands=0;self.accepted=0;self.rejected={};self.vision_updates=0
        self.execution_late_ticks=0;self.max_execution_interval_s=0.;self.last_vision_timing=None
        self.vision=LatestServer(vision_processor,lambda:profile.delay('vision') if mode=='virtual' else 0.,
            mode=mode,clock=self.clock,measure_floor=measure_floor)
        self.policy=LatestServer(self._decide,lambda:profile.delay('policy') if mode=='virtual' else 0.,
            mode=mode,clock=self.clock,measure_floor=measure_floor,hold_for_ack=True,
            tail_delay=lambda:profile.delay('dispatch') if mode=='virtual' else 0.)

    def ingest_camera(self,capture,received_s=None):
        if self.mode=='virtual':self.camera.append(capture)
        else:
            now=self.clock() if received_s is None else received_s
            for name,data in capture.items():
                if name not in ('right','rear'):raise ValueError('Unknown model camera')
                if not math.isfinite(data['stamp_s']) or data['stamp_s']>now:raise ValueError('Camera clock mismatch')
                self.camera.captured+=1
                previous=self.camera.current.get(name)
                if previous is None or data['stamp_s']>previous['stamp_s']:
                    self.camera.current[name]=dict(owned_snapshot(data),delivered_s=now)
        if received_s is not None:self.advance(received_s)

    def append(self,capture):
        """Native rig recorder protocol: enqueue all30Hz acquisitions."""
        self.ingest_camera(capture,max(d['stamp_s'] for d in capture.values()))

    def ingest_proprio(self,stamp_s,q,qd,tcp,received_s=None):
        if not math.isfinite(stamp_s):raise ValueError('Invalid encoder timestamp')
        value=dict(stamp_s=stamp_s,q=np.asarray(q,float).copy(),qd=np.asarray(qd,float).copy(),tcp=np.asarray(tcp,float).copy())
        if value['q'].shape!=(6,) or value['qd'].shape!=(6,) or value['tcp'].shape!=(3,) or not all(np.isfinite(value[k]).all() for k in ('q','qd','tcp')):
            raise ValueError('Invalid measured proprioception')
        self.event_sequence+=1
        ready=stamp_s+self.profile.delay('joint_feedback') if self.mode=='virtual' else (self.clock() if received_s is None else received_s)
        if ready<stamp_s:raise ValueError('Encoder clock mismatch')
        heappush(self.proprio_events,(ready,self.event_sequence,value))

    def advance(self,now):
        capture=self.camera.advance(now)
        while self.proprio_events and self.proprio_events[0][0]<=now+1e-9:
            _,_,value=heappop(self.proprio_events)
            if self.proprio is None or value['stamp_s']>self.proprio['stamp_s']:self.proprio=value
        rear=capture.get('rear')
        if rear is not None and rear['frame_number']>self.last_rear:
            self.last_rear=rear['frame_number']
            if not self.profile.drop('vision'):self.vision.submit(dict(rear=rear),now)
        result=self.vision.take(now)
        if result is not None:
            if result.error:self.fault=result.error
            else:
                self.last_vision_timing=dict(request_s=result.submitted_s,ready_s=result.ready_s,
                    compute_wall_s=result.compute_wall_s)
                self.detections=[dict(r,age_s=now-r['stamp_s']) for r in result.value]
                self.tracker.update(self.detections,now);self.vision_updates+=1
                if self.tracker.selected is None:
                    candidates=[key for key,t in self.tracker.snapshot(now).items() if t['valid'] and t['label']==self.label]
                    if len(candidates)==1:self.tracker.assign(now,candidates[0])
        self.policy.advance(now)
        return capture

    def _payload(self,now):
        capture=self.camera.current
        if set(capture)!={'right','rear'} or self.proprio is None:return None
        target=self.tracker.observation(now);target['target_id']=self.assigned_id
        track=self.tracker.tracks.get(self.tracker.selected);stamp=None if track is None else track['stamp_s']
        return dict(capture=capture,target=target,target_stamp_s=stamp,detections=self.detections,
            vision_timing=self.last_vision_timing,
            joint_stamp_s=self.proprio['stamp_s'],q=self.proprio['q'],qd=self.proprio['qd'],tcp=self.proprio['tcp'])

    def _decide(self,payload,now):
        capture=payload['capture'];frames={}
        for name,data in capture.items():
            frames[name]=Frame(data['rgb'],data['aligned_depth_m'],data['intrinsics']['rgb'],
                self.arm_from_world@data['world_from_optical']['rgb'],data['stamp_s'],data['pose_stamp_s'],name)
        target=dict(payload['target']);stamp=payload['target_stamp_s']
        target['age_s']=.3 if stamp is None else now-stamp
        observed=selected_record(target['position_m'],payload['detections']) if target['valid'] else None
        assigned=(observed if observed is not None and np.linalg.norm(np.asarray(observed['grasp_estimate_arm_m'])-target['position_m'])<1e-7
            and abs(stamp-observed['stamp_s'])<1e-7 else None)
        if target['valid'] and self.center_corrector is not None and observed is not None:
            position,_=self.center_corrector.predict(None,target['position_m'],observed);target['position_m']=position.tolist()
        packet=dict(capture,student_target_detections=payload['detections'],student_assigned_detection=assigned)
        command,note=self.controller.step(frames,payload['q'],payload['qd'],payload['tcp'],target,now,packet)
        evidence=stamp
        anchor=note.get('visual_servo',{}).get('approach_anchor',{})
        if anchor.get('active') and anchor.get('bbox_stamp_s') is not None:evidence=anchor['bbox_stamp_s']
        return dict(command=command,note=note,phase=phase_from_note(note),evidence_stamp_s=evidence)

    def tick(self,now):
        if self.last_tick is not None and now<=self.last_tick:raise ValueError('Execution clock did not advance')
        interval=None if self.last_tick is None else now-self.last_tick
        if interval is not None:
            self.max_execution_interval_s=max(self.max_execution_interval_s,interval)
            if interval>.055:self.execution_late_ticks+=1
        self.last_tick=now;self.advance(now);result=self.policy.take(now)
        if self.retired is not None:raise ValueError('Acknowledge actual dispatch before another tick')
        accepted,reason=command_gate(result,now,self.profile)
        if self.fault:accepted=False;reason='latched_processing_fault'
        if result is not None:self.retired=result
        command=result.value['command'].copy() if accepted else self.last_applied.copy()
        self.pending_payload=self._payload(now);self.commands+=1
        if accepted:self.accepted+=1
        else:self.rejected[reason]=self.rejected.get(reason,0)+1
        note=dict(dispatch_s=now,accepted=accepted,reason=reason,actual_command_source='new_result' if accepted else 'last_applied_goal',
            execution_interval_s=interval,
            policy_busy=self.policy.busy,vision_busy=self.vision.busy,
            policy_sequence=None if result is None else result.sequence,
            policy_request_s=None if result is None else result.submitted_s,
            policy_ready_s=None if result is None else result.ready_s,
            policy_compute_wall_s=None if result is None else result.compute_wall_s,
            vision_timing=None if result is None else result.payload.get('vision_timing'),
            camera_timing=None if result is None else {name:dict(capture_s=d['stamp_s'],
                pose_s=d['pose_stamp_s'],received_s=d['delivered_s']) for name,d in result.payload['capture'].items()},
            command_age_s=None if result is None else now-result.submitted_s,
            target_capture_s=None if result is None else result.payload.get('target_stamp_s'),
            evidence_capture_s=None if result is None or result.error else result.value.get('evidence_stamp_s'),
            joint_sample_s=None if result is None else result.payload['joint_stamp_s'],
            phase=None if result is None or result.error else result.value['phase'],
            decision_note=None if result is None or result.error else result.value['note'])
        return command,note

    def applied(self,command,now):
        """Call only after actual write/read-back of the command, not prediction."""
        self.last_applied=np.asarray(command).copy()
        if self.retired is not None:
            if self.retired.error:self.fault=self.retired.error
            else:self.controller.acknowledge_at(self.last_applied,now)
            self.policy.acknowledge();self.retired=None
        if self.pending_payload is not None and self.fault is None:
            self.policy.submit(self.pending_payload,now);self.pending_payload=None

    def summary(self):
        return dict(execution_ticks=self.commands,accepted_commands=self.accepted,rejections=self.rejected,
            execution_late_ticks=self.execution_late_ticks,max_execution_interval_s=self.max_execution_interval_s,
            camera_captured=self.camera.captured,camera_dropped=self.camera.dropped,vision_updates=self.vision_updates,
            vision=self.vision.summary(),policy=self.policy.summary(),fault=self.fault,
            hardware_io=False,real_end_to_end_measured=self.profile.real_end_to_end_measured)

    def close(self):self.vision.close();self.policy.close()
