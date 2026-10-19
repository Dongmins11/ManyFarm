"""Explicit response6 adapter without editing an active frozen source snapshot.

Installs only inside a new simulator process. Reuses original event/qualification
bookkeeping, contacts, timers and control; restores originals on context exit.
"""
import copy
from contextlib import contextmanager
import hashlib
import inspect
from pathlib import Path

from .attachment_60hz import MODEL, RESPONSE, coupled_wrench


@contextmanager
def response6_runtime():
    from .settings import TaskSettings
    from . import env as environment
    import torch
    from isaaclab.utils.math import quat_mul, quat_conjugate
    original_validate = TaskSettings.validate
    original_apply = environment.HarvestEnv._apply_action
    original_wrench = environment.attachment_wrench
    provenance = dict(model=MODEL, stem_response_version=RESPONSE,
        solver='coupled 6x6 backward Euler with free gravity', hidden_substeps=0,
        original_apply_sha256=hashlib.sha256(inspect.getsource(original_apply).encode()).hexdigest(),
        adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        model_sha256=hashlib.sha256(Path(inspect.getfile(coupled_wrench)).read_bytes()).hexdigest())

    def validate(settings):
        if settings.stem_response_version != RESPONSE:
            return original_validate(settings)
        if (settings.attachment_version != 4 or settings.contact_substeps != 1
                or abs(settings.physics_dt-1/60)>1e-12 or settings.decimation != 3):
            raise ValueError('Response6 is an explicit 60Hz physics / 20Hz policy profile')
        legacy = copy.copy(settings)
        legacy.stem_response_version = 5
        original_validate(legacy)
        return settings

    def apply(env):
        if env.settings.stem_response_version != RESPONSE:
            return original_apply(env)
        slot = 0
        def wrench(displacement, velocity, lever, cfg, attached, timer, dt, threshold, inverse_inertia=None):
            nonlocal slot
            fruit = env.fruits[slot]
            quat = quat_mul(fruit.data.root_link_quat_w, quat_conjugate(env.rest_quat[:,slot]))
            error = 2*quat[:,1:]*torch.sign(quat[:,:1])
            omega = fruit.data.root_com_ang_vel_w
            # Only already-commanded physical loads, never a synthetic support.
            extra = torch.zeros_like(lever)
            if cfg.task=='hold':
                extra[:,0]=cfg.hold_force*env.has_grasped*(env.target_index==slot)
            if hasattr(env,'connector_commanded_force'):
                extra=extra+env.connector_commanded_force[:,slot]
            flags=getattr(env,'response6_gyroscopic_forces',{})
            if slot not in flags:
                from pxr import PhysxSchema
                body=env.sim.stage.GetPrimAtPath(fruit.root_physx_view.prim_paths[0])
                flags[slot]=bool(PhysxSchema.PhysxRigidBodyAPI(body).GetEnableGyroscopicForcesAttr().Get())
                env.response6_gyroscopic_forces=flags
            result = coupled_wrench(displacement, velocity, lever, omega, error,
                inverse_inertia, cfg, attached, timer, dt, threshold,
                external_force=extra,gyroscopic_forces=flags[slot])
            force, torque, still_attached, timer, load = result
            # Original _apply_action adds its independent angular restore after
            # this callback. Remove that exact term here to apply response6 once.
            eye = torch.eye(3,device=lever.device,dtype=lever.dtype)
            damping = torch.linalg.solve(eye+dt*cfg.angular_d*inverse_inertia,
                (cfg.angular_d*omega)[...,None]).squeeze(-1)
            legacy_restore = -cfg.angular_k*error-damping
            slot += 1
            return force, torque-legacy_restore*still_attached[...,None], still_attached, timer, load
        environment.attachment_wrench = wrench
        try:
            original_apply(env)
            if slot != len(env.fruits):
                raise RuntimeError('Response6 adapter did not consume every fruit')
        finally:
            environment.attachment_wrench = original_wrench

    TaskSettings.validate = validate
    environment.HarvestEnv._apply_action = apply
    try:
        yield provenance
    finally:
        environment.attachment_wrench = original_wrench
        environment.HarvestEnv._apply_action = original_apply
        TaskSettings.validate = original_validate
