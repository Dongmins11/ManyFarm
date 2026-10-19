"""Bound the time spent closing before encoder-observed contact acquisition.

An experimental assisted-control candidate. It preserves the camera entry gate,
arm hold, encoder contact observer, finite preload and all transfer/release logic.
No contact, fruit truth or simulator phase is available to this controller.
"""
import numpy as np
from .student60 import decode_command,encode_command
from .student60_flexible_transfer import FlexibleTransferCameraHarvestController


class FasterCaptureCameraHarvestController(FlexibleTransferCameraHarvestController):
    def step(self,frames,q,qd,tcp,target,now,capture):
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        v=note['visual_servo']
        if (self.entry_ready and self.hold_start is None
                and v.get('geometry_gentle_closing',False)
                and not v.get('observed_tray_release_latched',False)):
            goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
            previous=float(self.inner.previous_q[-1]);speed=.30
            goal[-1]=np.clip(float(q[-1])-.020,previous-speed*.05,previous+speed*.05)
            goal[-1]=np.clip(goal[-1],self.contract['lower_rad'][-1],self.contract['upper_rad'][-1])
            servo[1]=speed
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
            v.update(commanded_closing_speed_rad_s=speed,experimental_faster_contact_acquisition=True,
                precontact_goal_lead_rad=.020)
        return command,note
