"""Guarded preload relaxation and explicit closed-floor collision comparison."""
from .teacher_native_settle_v4_env import TeacherNativeSettleV4Env
from .floor_collision_buffered import configure_floor


class TeacherNativeFloorGuardedEnv(TeacherNativeSettleV4Env):
    def __init__(self, *args, floor_mode='buffered', **kwargs):
        self.floor_mode = floor_mode
        super().__init__(*args, **kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        self.floor_override = configure_floor(self.sim.stage, self.floor_mode)
