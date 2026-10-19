"""Replace legacy virtual stem only inside an explicitly versioned worker."""
from contextlib import contextmanager
from dataclasses import asdict
from unittest.mock import patch
import torch
from .native_connector import directional_open


@contextmanager
def native_connector_runtime(spec):
    from . import attachment_60hz_runtime as previous
    from . import env as environment
    with previous.response6_runtime() as base:
        original_config=environment.HarvestEnvCfg
        def configuration():
            cfg=original_config()
            if spec.solver=='pgs':cfg.sim.physx.solver_type=0
            elif spec.solver in ('tgs-zero','tgs-distributed'):
                # NVIDIA documents regular D6 drive issues with TGS velocity
                # iterations. Clamp scene-wide so robot contact islands cannot
                # restore a nonzero count inherited from body/articulation USD.
                cfg.sim.physx.max_velocity_iteration_count=0
                cfg.sim.physx.min_position_iteration_count=16
                cfg.sim.physx.enable_external_forces_every_iteration=spec.solver=='tgs-distributed'
            return cfg
        original=previous.coupled_wrench
        def native(displacement,velocity,lever,omega,error,inverse,cfg,attached,timer,dt,threshold,**kwargs):
            remaining,next_timer,axial,opening=directional_open(displacement,attached,timer,dt,spec)
            # Only bookkeeping. The compliant D6 is the sole physical stem load.
            estimate=(spec.axial_stiffness_N_m*axial-spec.damping_N_s_m*velocity[:,0]).clamp(0,spec.force_limit_N)
            return torch.zeros_like(displacement),torch.zeros_like(displacement),remaining,next_timer,estimate
        previous.coupled_wrench=native
        try:
            with patch.object(environment,'HarvestEnvCfg',configuration):
                yield dict(model='native_compliant_d6_v1',spec=asdict(spec),base_validation_adapter=base,
                    actual_force_owner='PhysX free-axis D6 force drives',legacy_virtual_force_disabled=True,
                    force_limit_is_per_linear_axis=True,explicit_physics_transfer=True)
        finally:previous.coupled_wrench=original
