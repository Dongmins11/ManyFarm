"""Finite encoder-load preload, capped around the original captured goal."""
import numpy as np
from .student60_side_scan import SideScanCameraHarvestController


class FiniteLoadCameraHarvestController(SideScanCameraHarvestController):
    def start(self,*args):
        super().start(*args)
        self.load_hold_origin=None;self.load_last_time=None;self.load_preload=0.

    def holding_jaw_target(self,q,now):
        if self.load_hold_origin!=self.hold_start:
            self.load_hold_origin=self.hold_start;self.load_last_time=None;self.load_preload=0.
        previous=float(self.inner.previous_q[-1])
        if self.load_last_time is None or now>self.load_last_time+1e-7:
            dt=.05 if self.load_last_time is None else min(.05,max(0.,now-self.load_last_time))
            if float(q[-1])-previous<.015:
                self.load_preload=min(.025,self.load_preload+.02*dt)
            self.load_last_time=now
        desired=max(self.hold_jaw-self.load_preload,float(q[-1])-.04)
        return float(np.clip(desired,previous-.015,previous+.015))

    def step(self,frames,q,qd,tcp,target,now,capture):
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        note['visual_servo'].update(finite_encoder_preload_rad=self.load_preload,
            finite_encoder_preload_limit_rad=.025,encoder_load_proxy_rad=float(q[-1]-self.inner.previous_q[-1]))
        return command,note
