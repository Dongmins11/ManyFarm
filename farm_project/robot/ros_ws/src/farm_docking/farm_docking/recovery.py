"""Recoverable waits and bounded odometry-based marker search."""
import math

class Recoverable(RuntimeError):
    def __init__(self,reason,detail=''):
        self.reason=reason
        super().__init__(detail or reason)

class RecoveryWait:
    def __init__(self,reason,now,timeout,stable):
        self.reason=reason;self.started=now;self.timeout=timeout;self.stable=stable;self.good_since=None
    def check_deadline(self,now):
        if now-self.started>self.timeout:raise TimeoutError('Recovery timeout: '+self.reason)
    def update(self,healthy,stopped,now):
        self.check_deadline(now)
        if not healthy or not stopped:self.good_since=None;return False
        if self.good_since is None:self.good_since=now
        return now-self.good_since>=self.stable

class MarkerSearch:
    def __init__(self,yaw,now,angle,speed,dwell):
        self.origin=yaw;self.targets=[angle,-angle,0.];self.index=0
        self.speed=speed;self.dwell=dwell;self.wait_until=now+dwell;self.at_target=False
    def step(self,yaw,stopped,now):
        if self.index>=len(self.targets):return 0.,True
        error=math.atan2(math.sin(self.origin+self.targets[self.index]-yaw),math.cos(self.origin+self.targets[self.index]-yaw))
        if abs(error)<.025:
            self.index+=1
            if self.index>=len(self.targets):return 0.,True
            error=math.atan2(math.sin(self.origin+self.targets[self.index]-yaw),math.cos(self.origin+self.targets[self.index]-yaw))
        return math.copysign(min(self.speed,max(.011,.8*abs(error))),error),False


def recovery_observation_ready(preview, now_ns, observation_start_ns,
                               recovery_after_ns, image_max_age_s,
                               odom_max_age_s, tracking, visual_recovery,
                               visual_transit):
    """Use the tracker estimate's clock and bounds, not the image input gate.

    Input age was checked at acceptance. Between images the tracker already
    checks prediction age, travel and yaw; WAIT_OBSERVATION invalidates it.
    Require an accepted post-recovery image before allowing resumption.
    """
    stamp=preview.get('stamp_ns',0)
    age=(now_ns-stamp)/1e9
    limit=odom_max_age_s if visual_transit else image_max_age_s
    ready=bool(preview) and stamp>=observation_start_ns and 0<=age<=limit and preview.get('phase')!='WAIT_OBSERVATION'
    if visual_recovery:
        source=preview.get('source_observation_stamp_ns',0)
        source_age=(now_ns-source)/1e9
        source_limit=tracking['max_prediction_s'] if visual_transit else min(image_max_age_s,tracking['max_input_age_s'])
        ready=ready and source>recovery_after_ns and 0<=source_age<=source_limit
    return ready
