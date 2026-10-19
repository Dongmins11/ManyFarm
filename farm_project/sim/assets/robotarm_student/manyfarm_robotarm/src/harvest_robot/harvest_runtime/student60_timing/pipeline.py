"""Latest-only timed servers for reproducible simulation and wall-clock execution.

Virtual servers compute only from already available snapshots, then withhold
results until their recorded/injected completion time. Physics is advanced by
the caller throughout that delay. Wall servers run the same processor off-thread.
"""
from dataclasses import dataclass
from heapq import heappush,heappop
import math
import threading
import time
from ..student60_latest_vision import owned_snapshot


@dataclass(frozen=True)
class TimedResult:
    sequence: int
    submitted_s: float
    ready_s: float
    generation: int
    payload: object
    value: object
    compute_wall_s: float
    error: str | None = None


class LatestServer:
    """One active request, one replaceable pending request, ordered completions."""
    def __init__(self,processor,delay,*,mode='virtual',clock=time.monotonic,measure_floor=False,hold_for_ack=False,tail_delay=lambda:0.):
        if mode not in ('virtual','wall'):raise ValueError('Unknown server clock')
        self.processor=processor;self.delay=delay;self.mode=mode;self.clock=clock;self.measure_floor=measure_floor
        self.hold_for_ack=hold_for_ack;self.awaiting_ack=False;self.tail_delay=tail_delay
        self.lock=threading.RLock();self.pending=None;self.active=None;self.ready=None;self.sequence=0;self.generation=0
        self.submitted=0;self.replaced=0;self.completed=0;self.last_time=-math.inf;self.stopped=False
        self.thread=None

    def submit(self,payload,now):
        if not math.isfinite(now):raise ValueError('Invalid request timestamp')
        copied_at=time.monotonic();snapshot=owned_snapshot(payload);copy_s=time.monotonic()-copied_at
        with self.lock:
            if self.stopped:raise RuntimeError('Server closed')
            if now<self.last_time-1e-9:raise ValueError('Clock regressed')
            self.submitted+=1;self.sequence+=1
            if self.pending is not None:self.replaced+=1
            self.pending=(self.sequence,now,self.generation,snapshot,copy_s)
        self.advance(now)

    def _compute(self,request,start):
        sequence,submitted,generation,payload,copy_s=request;t=time.monotonic();value=None;error=None
        if self.mode=='wall':start=self.clock()
        try:value=self.processor(payload,start)
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        elapsed=time.monotonic()-t+copy_s
        duration=max(float(self.delay()),elapsed if self.measure_floor else 0.)+float(self.tail_delay())
        if not math.isfinite(duration) or duration<0:raise ValueError('Invalid server delay')
        ready=(self.clock() if self.mode=='wall' else start)+ (0. if self.mode=='wall' else duration)
        # Wall mode adds an explicit emulated margin only when requested by its
        # caller; actual processing time is already in clock()-submitted.
        if self.mode=='wall' and duration>elapsed:ready+=duration-elapsed
        result=TimedResult(sequence,submitted,ready,generation,payload,value,elapsed,error)
        with self.lock:
            if generation==self.generation and not self.stopped:self.active=result

    def advance(self,now):
        request=None
        with self.lock:
            if not math.isfinite(now) or now<self.last_time-1e-9:raise ValueError('Clock regressed')
            self.last_time=now
            if isinstance(self.active,TimedResult) and self.active.ready_s<=now+1e-9:
                self.ready=self.active;self.active=None;self.completed+=1
                if self.hold_for_ack:self.awaiting_ack=True
            if self.active is None and self.pending is not None and not self.stopped and not self.awaiting_ack:
                request=self.pending;self.pending=None;self.active='computing'
        if request is not None:
            if self.mode=='wall':
                self.thread=threading.Thread(target=self._compute,args=(request,now),daemon=True);self.thread.start()
            else:self._compute(request,now)

    def take(self,now):
        self.advance(now)
        with self.lock:
            result=self.ready;self.ready=None;return result

    @property
    def busy(self):
        with self.lock:return self.active is not None

    def acknowledge(self):
        with self.lock:
            if not self.awaiting_ack:raise ValueError('No retired result awaiting acknowledgement')
            self.awaiting_ack=False

    def reset(self):
        with self.lock:
            if self.active=='computing':raise RuntimeError('Finish current worker before resetting stateful processor')
            self.generation+=1;self.pending=None;self.active=None;self.ready=None;self.last_time=-math.inf;self.awaiting_ack=False

    def summary(self):
        with self.lock:return dict(submitted=self.submitted,replaced=self.replaced,completed=self.completed,
            busy=self.active is not None,pending=self.pending is not None,mode=self.mode)

    def close(self):
        with self.lock:self.stopped=True;self.pending=None
        if self.thread is not None:
            self.thread.join(5.)
            if self.thread.is_alive():raise TimeoutError('Worker still active; close its detector transport')


class CameraDelivery:
    def __init__(self,profile):
        self.profile=profile;self.events=[];self.current={};self.counter=0;self.captured=0;self.dropped=0

    def append(self,capture):
        # Called at native30Hz, not just at policy20Hz. Each view retains its
        # original exposure/pose/joint stamps and immutable image buffers.
        for name,value in capture.items():
            self.captured+=1
            if self.profile.drop('camera_'+name):self.dropped+=1;continue
            self.counter+=1;ready=value['stamp_s']+self.profile.delay('camera_'+name)
            heappush(self.events,(ready,self.counter,name,owned_snapshot(value)))

    def advance(self,now):
        while self.events and self.events[0][0]<=now+1e-9:
            ready,_,name,value=heappop(self.events)
            if name not in self.current or value['stamp_s']>self.current[name]['stamp_s']:
                self.current[name]=dict(value,delivered_s=ready)
        return dict(self.current)


def command_gate(result,now,profile):
    """Reject late work before applying it; preserve the last accepted goal."""
    if result is None:return False,'no_ready_command'
    if result.error:return False,'processor_error'
    if result.ready_s>now+1e-9:return False,'not_ready'
    if now-result.submitted_s>profile.value['command_max_age_s']+1e-9:return False,'command_deadline'
    payload=result.payload
    if not 0<=now-payload['joint_stamp_s']<=profile.value['joint_max_age_s']+1e-9:return False,'joint_deadline'
    phase=result.value['phase'];stamp=result.value.get('evidence_stamp_s',payload.get('target_stamp_s'))
    if phase in profile.phase_age:
        if stamp is None or not 0<=now-stamp<=profile.phase_age[phase]+1e-9:return False,'target_deadline'
    return True,'accepted'
