"""Inject scene CCD into the instantiated config, not removed dataclass fields."""
from contextlib import contextmanager
from .component_scene_audit import inspect_scene


@contextmanager
def scene_ccd_runtime(enabled):
    from .env import HarvestEnvCfg
    original=HarvestEnvCfg.__init__
    previous=bool(HarvestEnvCfg().sim.physx.enable_ccd)
    def initialize(config,*args,**kwargs):
        original(config,*args,**kwargs)
        config.sim.physx.enable_ccd=bool(enabled)
    HarvestEnvCfg.__init__=initialize
    try: yield dict(previous_enable_ccd=previous,requested_enable_ccd=bool(enabled),version=2)
    finally: HarvestEnvCfg.__init__=original
