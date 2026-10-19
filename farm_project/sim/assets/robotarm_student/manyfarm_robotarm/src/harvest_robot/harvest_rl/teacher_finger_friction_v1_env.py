"""Adopted material version for full-chain evaluation and native training.

Both classes use the same actual finger-only material installer. No historical
source, cached USD, model or normalizer is changed. Import after AppLauncher.
"""
from .teacher_native_floor_unified_env import TeacherNativeFloorUnifiedEnv
from .teacher_native_contact_control_env import TeacherNativeContactControlEnv
from .environment_version import load_profile,validate_settings
from .jaw_surface_compare_v2 import SurfaceSpec,configure


class VersionedSurface:
    def __init__(self,*args,environment_profile=None,**kwargs):
        self.environment_profile,self.environment_profile_path=load_profile(environment_profile)
        settings=args[0] if args else kwargs.get('settings')
        if settings is None:raise ValueError('Explicit TaskSettings required')
        validate_settings(settings,self.environment_profile)
        self.surface_spec=SurfaceSpec(effective_friction=1.6,pad_mode='none')
        super().__init__(*args,**kwargs)

    def _setup_scene(self):
        super()._setup_scene()
        self.surface_override=configure(self,self.surface_spec)


class TeacherFingerFrictionV1EvalEnv(VersionedSurface,TeacherNativeFloorUnifiedEnv):
    """Original full harvest controls with adopted contact materials."""


class TeacherFingerFrictionV1TrainEnv(VersionedSurface,TeacherNativeContactControlEnv):
    """Native arm5 training environment; requires a NEW training contract."""
