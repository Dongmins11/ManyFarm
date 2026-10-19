"""Disable old stem forces; relay actual PhysX break into original harvest logic."""
from contextlib import contextmanager
from unittest.mock import patch
import torch
from .attachment_60hz_runtime import response6_runtime


@contextmanager
def hook_connector_runtime():
    from . import attachment_60hz_runtime as previous
    from . import env as environment
    with response6_runtime() as base:
        original_config = environment.HarvestEnvCfg
        original_apply = environment.HarvestEnv._apply_action
        original_wrench = previous.coupled_wrench
        current = None
        slot = 0

        def configuration():
            cfg = original_config()
            cfg.sim.physx.max_velocity_iteration_count = 0
            cfg.sim.physx.min_position_iteration_count = 16
            cfg.sim.physx.enable_external_forces_every_iteration = True
            return cfg

        def event_only(displacement, velocity, lever, omega, error, inverse, cfg,
                       attached, timer, dt, threshold, **kwargs):
            nonlocal slot
            if abs(dt - 1/60) > 1e-9:raise ValueError('Hook runs at physical60Hz')
            broke = current.hook_pending_breaks[:, slot]
            remaining = attached & ~broke
            # Observation estimate only; the constraint owns the actual force.
            # Keep it explicitly distinct from solver reaction measurements.
            if hasattr(current, 'hook_connectors'):
                specs = current.hook_connectors.specs
                direction = displacement.new_tensor([s.pivot_offset_direction for s in specs])
                direction = direction / direction.norm(dim=-1,keepdim=True)
                lengths = displacement.new_tensor([s.length_m for s in specs])
                radii = displacement - lengths[:,None]*direction
                distance = radii.norm(dim=-1)
                extension = (distance-lengths).clamp_min(0)
                radial = radii/distance.clamp_min(1e-9)[:,None]
                stiffness = displacement.new_tensor([s.stiffness_N_m for s in specs])
                load_estimate = (stiffness*extension*(-radial[:,0])).clamp_min(0)
            else:
                load_estimate = torch.zeros_like(timer)
            slot += 1
            # Original _apply_action sees true->false and checks actual contact,
            # valid pull and subsequent retention. Do not pre-mark success here.
            return (torch.zeros_like(displacement), torch.zeros_like(displacement),
                    remaining, torch.zeros_like(timer), load_estimate)

        def apply(env):
            nonlocal current, slot
            current = env
            slot = 0
            env.hook_pending_breaks = (env.hook_connectors.pending_mask() if hasattr(env,'hook_connectors')
                                      else torch.zeros_like(env.attached))
            original_apply(env)
            if slot != len(env.fruits):raise RuntimeError('Hook callback missed a fruit')

        previous.coupled_wrench = event_only
        environment.HarvestEnv._apply_action = apply
        try:
            with patch.object(environment,'HarvestEnvCfg',configuration):
                yield dict(model='finite_length_hook_v2', base_adapter=base,
                    actual_force_owner='PhysX D6 spherical distance soft limit',legacy_stem_wrench_disabled=True,
                    angular_restoration_disabled=True,fracture='actual constraint2.5N; no70mm displacement fracture',
                    physics_hz=60, policy_hz=20, explicit_candidate=True)
        finally:
            environment.HarvestEnv._apply_action = original_apply
            previous.coupled_wrench = original_wrench

