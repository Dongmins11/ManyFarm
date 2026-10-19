"""Native chain with explicit closed-floor collision representation comparison."""
from .teacher_native_settle_v2_env import TeacherNativeSettleV2Env
from .floor_collision_v3 import configure_floor


class TeacherNativeFloorV3Env(TeacherNativeSettleV2Env):
    def __init__(self, *args, floor_mode='original', **kwargs):
        self.floor_mode = floor_mode
        super().__init__(*args, **kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        self.floor_override = configure_floor(self.sim.stage, self.floor_mode)
