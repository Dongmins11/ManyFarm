"""Reach above the tray before requiring its final low release pitch."""
from .student60_finite_load import FiniteLoadCameraHarvestController


class FlexibleTransferCameraHarvestController(FiniteLoadCameraHarvestController):
    def start(self,*args):
        super().start(*args);self.above_box_dwell=0.

    def step(self,frames,q,qd,tcp,target,now,capture):
        command,note=super().step(frames,q,qd,tcp,target,now,capture)
        v=note['visual_servo']
        if self.transfer_phase=='across':
            _,vertical=self.pose(q)
            ready=(v.get('observed_transfer_error_m',float('inf'))<.006
                and v.get('observed_transfer_speed_m_s',float('inf'))<.02 and abs(vertical)<.10)
            self.above_box_dwell=self.above_box_dwell+.05 if ready else 0.
            if self.above_box_dwell>=.15-1e-6:
                self.transfer_phase='lower';self.transfer_dwell=0.
                v.update(above_box_position_confirmed=True,next_transfer_phase='lower',
                    release_pitch_alignment_during_descent=True)
        else:self.above_box_dwell=0.
        return command,note
