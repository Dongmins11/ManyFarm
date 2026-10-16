"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from .teacher_native_floor_unified_env import TeacherNativeFloorUnifiedEnv

from .jaw_surface_compare_v2 import SurfaceSpec


class TeacherJawSurfaceCompareEnv(TeacherNativeFloorUnifiedEnv):

    def __init__(self,*args,surface_spec=None,**kwargs):
        self.surface_spec=(surface_spec or SurfaceSpec()).validate()
        super().__init__(*args,**kwargs)
