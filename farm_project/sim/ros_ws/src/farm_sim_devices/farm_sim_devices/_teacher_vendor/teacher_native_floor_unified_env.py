"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from .teacher_native_settle_v4_env import TeacherNativeSettleV4Env


class TeacherNativeFloorUnifiedEnv(TeacherNativeSettleV4Env):

    def __init__(self,*args,floor_mode='unified',**kwargs):
        self.floor_mode=floor_mode
        super().__init__(*args,**kwargs)
