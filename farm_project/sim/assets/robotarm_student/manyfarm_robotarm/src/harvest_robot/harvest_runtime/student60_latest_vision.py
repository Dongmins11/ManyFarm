"""Wall-clock latest-frame worker and dispatch checks, without robot I/O.

This is a deployment building block, not a hardware runner or a replacement for
the frozen Student's 20Hz observation/history contract. Capture and pose stamps
must already be mapped into the same monotonic host clock.
"""
from dataclasses import dataclass
import copy
import math
import threading
import time
import numpy as np


def owned_snapshot(value):
    """Own camera data before a capture thread reuses its buffers."""
    if isinstance(value,np.ndarray):
        result=value.copy();result.setflags(write=False);return result
    if isinstance(value,dict):return {k:owned_snapshot(v) for k,v in value.items()}
    if isinstance(value,list):return [owned_snapshot(v) for v in value]
    if isinstance(value,tuple):return tuple(owned_snapshot(v) for v in value)
    return copy.deepcopy(value)


@dataclass(frozen=True)
class VisionInput:
    sequence: int
    captured_s: float
    target_id: str
    generation: int
    payload: object


@dataclass(frozen=True)
class VisionResult:
    source: VisionInput
    started_s: float
    finished_s: float
    value: object
    error: str | None = None


def dispatch_check(*,captured_s,proprio_s,computed_s,now_s,max_age_s=.05):
    """Check again AFTER inference, just before dispatch; never refresh stamps."""
    stamps=[captured_s,proprio_s,computed_s,now_s,max_age_s]
    if not all(math.isfinite(x) for x in stamps) or max_age_s<=0:return False,'invalid_clock'
    if captured_s>computed_s or proprio_s>computed_s or computed_s>now_s:return False,'future_stamp'
    if now_s-captured_s>max_age_s+1e-9:return False,'image_deadline'
    if now_s-proprio_s>max_age_s+1e-9:return False,'joint_deadline'
    if now_s-computed_s>max_age_s+1e-9:return False,'command_deadline'
    return True,'fresh'


class LatestVision:
    """One running job + one replaceable pending frame; control never joins it."""
    def __init__(self,processor,target_id,*,clock=time.monotonic):
        if not target_id:raise ValueError('Explicit target ID required')
        self.processor=processor;self.clock=clock;self.target_id=target_id;self.generation=0
        self.pending=None;self.result=None;self.last_sequence=-1;self.inflight=None
        self.submitted=0;self.replaced=0;self.finished=0;self.discarded=0;self.last_error=None
        self.condition=threading.Condition();self.stopped=False
        self.thread=threading.Thread(target=self._run,name='student60-latest-vision',daemon=True);self.thread.start()

    def reset(self,target_id):
        if not target_id:raise ValueError('Explicit target ID required')
        with self.condition:
            if self.stopped:raise RuntimeError('Vision worker is closed')
            self.target_id=target_id;self.generation+=1;self.pending=None;self.result=None
            self.last_sequence=-1;self.last_error=None

    def submit(self,sequence,captured_s,payload):
        now=self.clock()
        if type(sequence) is not int or sequence<0 or not math.isfinite(captured_s) or captured_s>now:
            raise ValueError('Require increasing frame sequence and monotonic capture stamp')
        # Copy outside the mailbox lock. Capture owns this producer-side cost;
        # it is measured separately from inference/dispatch latency.
        with self.condition:generation=self.generation;target_id=self.target_id
        snapshot=owned_snapshot(payload)
        with self.condition:
            if self.stopped:raise RuntimeError('Vision worker is closed')
            if generation!=self.generation:return False
            if sequence<=self.last_sequence:raise ValueError('Frame sequence did not increase')
            self.last_sequence=sequence;self.submitted+=1
            if self.pending is not None:self.replaced+=1
            self.pending=VisionInput(sequence,float(captured_s),target_id,generation,snapshot)
            self.condition.notify()
        return True

    def latest(self,now_s=None,max_age_s=.05):
        now=self.clock() if now_s is None else now_s
        if not math.isfinite(now) or not math.isfinite(max_age_s) or max_age_s<=0:raise ValueError('Invalid observation clock/TTL')
        with self.condition:
            if self.stopped:return None
            result=self.result
            if result is None or result.error or result.source.generation!=self.generation:return None
            if not result.source.captured_s<=result.finished_s<=now:return None
            return result if now-result.source.captured_s<=max_age_s+1e-9 else None

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.stopped or self.pending is not None)
                if self.stopped:return
                source=self.pending;self.pending=None;self.inflight=source.sequence
            started=self.clock();value=None;error=None
            try:value=self.processor(source)
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            result=VisionResult(source,started,self.clock(),value,error)
            with self.condition:
                self.inflight=None;self.finished+=1
                if source.generation==self.generation:
                    self.result=result;self.last_error=error
                else:self.discarded+=1
                self.condition.notify_all()

    def summary(self):
        with self.condition:
            return dict(submitted=self.submitted,replaced=self.replaced,finished=self.finished,
                discarded=self.discarded,pending_sequence=None if self.pending is None else self.pending.sequence,
                inflight_sequence=self.inflight,last_error=self.last_error,target_id=self.target_id,generation=self.generation)

    def close(self,timeout=5.):
        with self.condition:self.stopped=True;self.pending=None;self.condition.notify_all()
        self.thread.join(timeout)
        if self.thread.is_alive():raise TimeoutError('Vision processor did not stop; close its detector transport')
