"""Keep the finite grasp preload until an observed tray release is requested.

Only measured TCP/jaw, public tray geometry and the neural opening proposal are
used. No detached/contact/grasp/phase flags are read. Physical evaluation alone
judges whether the object was retained, separated and deposited.
"""
import numpy as np
from .student60_entry_hold import EntryHoldGripController
from .student60 import encode_command,decode_command


class RetainedGripController(EntryHoldGripController):
    def start(self,*args):
        super().start(*args)
        self.tray_open_s=0.;self.tray_release=False;self.last_tcp=None

    def step(self,frames,q_rad,qd_rad_s,tcp_arm,target,now,capture):
        command,note=super().step(frames,q_rad,qd_rad_s,tcp_arm,target,now,capture)
        tcp=np.asarray(tcp_arm,float)
        speed=float(np.linalg.norm(tcp-self.last_tcp)/.05) if self.last_tcp is not None else float('inf')
        self.last_tcp=tcp.copy()
        goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
        if self.hold_start is not None and self.guard_finished and not self.tray_release:
            point=(np.asarray(self.contract['box_from_arm'])@np.r_[tcp,1])[:3]
            lo=np.asarray(self.contract['box_min']);hi=np.asarray(self.contract['box_max'])
            radius=self.contract['task']['diameter']/2
            zone=bool(np.all(point[:2]>=lo[:2]+radius+.005) and np.all(point[:2]<=hi[:2]-radius-.005)
                      and hi[2]+radius+.005<=point[2]<=hi[2]+radius+.075)
            requested=bool(goal[-1]>q_rad[-1]+.01)
            self.tray_open_s=self.tray_open_s+.05 if zone and speed<.03 and requested else 0.
            self.tray_release=self.tray_open_s>=.15-1e-6
            if not self.tray_release:
                goal[-1]=max(self.contract['lower_rad'][-1],self.hold_jaw-np.deg2rad(4.))
                servo=np.array([8.,.15])
                command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
                note['visual_servo'].update(bounded_retention_hold=True,observed_tray_zone=zone,
                    observed_tcp_speed_m_s=speed,neural_opening_requested=requested)
        note['visual_servo']['observed_tray_release_latched']=self.tray_release
        return command,note
