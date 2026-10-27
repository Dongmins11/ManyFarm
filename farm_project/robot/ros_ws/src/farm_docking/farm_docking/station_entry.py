"""Feedback tracking from the measured entry start to B in a fixed odom frame."""
import math


def wrap(x):return math.atan2(math.sin(x),math.cos(x))


def bounded(error,kp,limit,minimum):
    value=max(-limit,min(limit,kp*error))
    return math.copysign(max(abs(value),minimum),value) if value else 0.


class StationEntry:
    def __init__(self, config):
        self.c=dict(config);self.phase='ALIGN_ENTRY';self.aligned=False;self.start=None
        self.replans=0;self.needs_replan=False
        self.c.setdefault('mode','graph_transfer')
        if self.c['mode'] not in ('graph_transfer','align_then_marker'):raise ValueError('entry mode')
        self.c.setdefault('max_replans',3)
        self.c.setdefault('lookahead_m',.08)
        self.c.setdefault('rotate_in_place_rad',.2)
        if self.c['direction'] not in ('forward','reverse'):raise ValueError('entry direction')
        for name in ('position_tolerance_m','yaw_tolerance_rad','max_distance_m','max_lateral_m','max_linear_mps','max_angular_rps','min_linear_mps','min_angular_rps','linear_kp','angular_kp','timeout_s','lookahead_m','rotate_in_place_rad'):
            v=self.c[name]
            if type(v) not in (float,int) or not math.isfinite(v) or v<=0:raise ValueError('invalid entry '+name)
        if self.c['min_linear_mps']>self.c['max_linear_mps'] or self.c['min_angular_rps']>self.c['max_angular_rps']:raise ValueError('entry minimum exceeds maximum')

    def replan(self):
        if self.replans>=self.c['max_replans']:raise RuntimeError('Entry realignment attempts exhausted')
        self.replans+=1;self.start=None;self.aligned=False;self.needs_replan=False;self.phase='ALIGN_ENTRY'

    def step(self,pose,goal):
        if not all(math.isfinite(x) for x in (*pose,*goal)):raise ValueError('entry pose invalid')
        x,y,yaw=pose;gx,gy,heading=goal;c=self.c
        if c['mode']=='align_then_marker':
            # At A: align only. Translation belongs to the taught marker pose controller.
            error=wrap(heading-yaw)
            if abs(error)>c['yaw_tolerance_rad']:
                self.phase='ALIGN_ENTRY'
                return 0.,bounded(error,c['angular_kp'],c['max_angular_rps'],c['min_angular_rps']),False
            self.phase='VERIFY_ENTRY_STOP'
            return 0.,0.,True
        dx,dy=gx-x,gy-y;rho=math.hypot(dx,dy)
        sign=1 if c['direction']=='forward' else -1
        if self.start is None:
            if rho>c['max_distance_m']:
                raise RuntimeError(f'entry start distance {rho:.3f}m exceeds {c["max_distance_m"]:.3f}m')
            self.start=(x,y);self.goal=tuple(goal);self.length=rho
            self.ux,self.uy=(dx/rho,dy/rho) if rho>1e-9 else (math.cos(heading)*sign,math.sin(heading)*sign)
        if tuple(goal)!=self.goal:raise RuntimeError('entry odom goal changed during tracking')
        travelled=(x-self.start[0])*self.ux+(y-self.start[1])*self.uy
        lateral=-(x-self.start[0])*self.uy+(y-self.start[1])*self.ux
        if abs(lateral)>c['max_lateral_m'] or (travelled>self.length+c['position_tolerance_m'] and rho>c['position_tolerance_m']):
            self.needs_replan=True;self.aligned=False;self.phase='STOP_REPLAN_ENTRY'
            return 0.,0.,False
        if rho<=c['position_tolerance_m']:
            self.aligned=True
            error=wrap(heading-yaw)
            if abs(error)>c['yaw_tolerance_rad']:
                self.phase='ALIGN_OBSERVATION'
                return 0.,bounded(error,c['angular_kp'],c['max_angular_rps'],c['min_angular_rps']),False
            self.phase='VERIFY_OBSERVATION_STOP';return 0.,0.,True
        # Pursue a point ahead on the fixed start→B line. Recompute from odom each tick.
        advance=min(self.length,max(0.,travelled)+c['lookahead_m'])
        tx=self.start[0]+advance*self.ux;ty=self.start[1]+advance*self.uy
        bearing=math.atan2(ty-y,tx-x)+(math.pi if sign<0 else 0.)
        error=wrap(bearing-yaw)
        if not self.aligned:
            if abs(error)>c['yaw_tolerance_rad']:
                return 0.,bounded(error,c['angular_kp'],c['max_angular_rps'],c['min_angular_rps']),False
            self.aligned=True;self.phase='MOVE_TO_OBSERVATION'
        w=bounded(error,c['angular_kp'],c['max_angular_rps'],c['min_angular_rps']) if abs(error)>.01 else 0.
        if abs(error)>c['rotate_in_place_rad']:
            self.phase='REALIGN_ENTRY';return 0.,w,False
        self.phase='MOVE_TO_OBSERVATION'
        v=sign*bounded(rho,c['linear_kp'],c['max_linear_mps'],c['min_linear_mps'])*max(0.,1.-(abs(error)/c['rotate_in_place_rad'])**2)
        return v,w,False
