"""Policy-free floor diagnostic factory with explicit contact-buffer variant."""
from .teacher_native_settle_v2_env import TeacherNativeSettleV2Env
from .floor_collision_buffered import configure_floor


class TeacherNativeFloorBufferedEnv(TeacherNativeSettleV2Env):
    def __init__(self,*args,floor_mode='buffered',**kwargs):
        self.floor_mode=floor_mode
        super().__init__(*args,**kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        self.floor_override=configure_floor(self.sim.stage,self.floor_mode)
