"""Preserve the exact response6 stem, change only the tested solver settings."""
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def solver_ablation_runtime():
    from . import env as environment
    from .attachment_60hz_runtime import response6_runtime
    original_config=environment.HarvestEnvCfg
    def configuration():
        cfg=original_config();cfg.sim.physx.max_velocity_iteration_count=0
        cfg.sim.physx.min_position_iteration_count=16
        cfg.sim.physx.enable_external_forces_every_iteration=True
        return cfg
    with response6_runtime() as base,patch.object(environment,'HarvestEnvCfg',configuration):
        yield dict(base,solver_ablation=True,stem='Original exact response6; no D6 joints',
            max_velocity_iterations=0,min_position_iterations=16,distributed_external_forces=True)
