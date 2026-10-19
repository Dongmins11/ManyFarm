"""Guarded Teacher chain with one primitive closed-box support surface."""
from .teacher_native_settle_v4_env import TeacherNativeSettleV4Env
from .floor_unified import configure_floor


class TeacherNativeFloorUnifiedEnv(TeacherNativeSettleV4Env):
    def __init__(self,*args,floor_mode='unified',**kwargs):
        self.floor_mode=floor_mode
        super().__init__(*args,**kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        self.floor_override=configure_floor(self.sim.stage,self.floor_mode)
