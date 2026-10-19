"""Finger-only contact materials over unmodified native full-chain controls."""
from .teacher_native_floor_unified_env import TeacherNativeFloorUnifiedEnv
from .jaw_surface_compare_v2 import SurfaceSpec,configure


class TeacherJawSurfaceCompareEnv(TeacherNativeFloorUnifiedEnv):
    def __init__(self,*args,surface_spec=None,**kwargs):
        self.surface_spec=(surface_spec or SurfaceSpec()).validate()
        super().__init__(*args,**kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        self.surface_override=configure(self,self.surface_spec)
