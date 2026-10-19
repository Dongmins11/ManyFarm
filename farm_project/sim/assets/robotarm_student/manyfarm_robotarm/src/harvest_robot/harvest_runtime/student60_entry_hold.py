"""Stop chasing changing depth estimates while the jaws close around an entry.

Entry comes from persistent camera alignment plus measured jaw opening. Holding
uses the previous actual arm command, not contacts, simulator phase or fruit pose.
"""
from .student60_stable_grip import StableGripController
from .student60 import encode_command,decode_command


class EntryHoldGripController(StableGripController):
    def start(self,*args):
        super().start(*args)
        self.entry_arm_hold=None

    def step(self,*args):
        command,note=super().step(*args)
        if self.entry_jaw_gate and self.entry_ready and self.entry_arm_hold is None:
            self.entry_arm_hold=self.inner.previous_q[:5].copy()
        if self.entry_arm_hold is not None and not self.guard_finished:
            goal,servo=decode_command(command,self.contract['lower_rad'],self.contract['upper_rad'])
            goal[:5]=self.entry_arm_hold
            command=encode_command(goal,servo,self.contract['lower_rad'],self.contract['upper_rad'])
            note['visual_servo'].update(active=True,entry_arm_hold=True)
        return command,note
