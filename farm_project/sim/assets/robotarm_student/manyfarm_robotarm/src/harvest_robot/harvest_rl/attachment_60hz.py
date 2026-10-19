"""Response6: coupled point/orientation implicit connector with free gravity.

SI world coordinates. One solve per physical step, no hidden integration steps,
pose correction, grasp weld, velocity clipping or post-detachment forces.
"""
import torch

MODEL = 'coupled_point_orientation_v6'
RESPONSE = 6


def skew(v):
    zero = torch.zeros_like(v[..., 0])
    x, y, z = v.unbind(-1)
    return torch.stack((zero, -z, y, z, zero, -x, -y, x, zero), -1).reshape(*v.shape[:-1], 3, 3)


def coupled_wrench(displacement, point_velocity, lever, angular_velocity,
                   orientation_error, inverse_inertia, cfg, attached, timer,
                   dt, threshold, gravity=(0., 0., -9.81),
                   external_force=None, external_torque=None, gyroscopic_forces=False):
    """Return COM force/torque and the unchanged response5 fracture criteria.

    Generalized velocity is [attachment point velocity, angular velocity].
    The symmetric 6x6 mobility includes both point torque and angular spring.
    Free gravity is included in predicted next-step velocity, not cancelled by
    an artificial COM support. The solver then applies ordinary gravity itself.
    """
    if inverse_inertia is None:
        raise ValueError('Response6 requires the authored world inverse inertia')
    if cfg.attachment_version != 4 or dt <= 0:
        raise ValueError('Response6 requires attachment4 and a positive physical timestep')
    eye3 = torch.eye(3, device=displacement.device, dtype=displacement.dtype)
    r = skew(lever)
    top = torch.cat((eye3/cfg.mass-r@inverse_inertia@r, -r@inverse_inertia), -1)
    bottom = torch.cat((inverse_inertia@r, inverse_inertia), -1)
    mobility = torch.cat((top, bottom), -2)
    axis = displacement.new_tensor(cfg.tension_axis)
    axis = axis/axis.norm()
    vertical = displacement.new_tensor([0., 0., 1.])
    vertical = vertical-(vertical*axis).sum()*axis
    vertical = vertical/vertical.norm().clamp_min(1e-8)
    k3 = cfg.spring_k*(cfg.lateral_stiffness_ratio*eye3
         +(1-cfg.lateral_stiffness_ratio)*axis[:,None]*axis[None,:])
    k3 = k3+(cfg.stem_vertical_stiffness-cfg.spring_k*cfg.lateral_stiffness_ratio)*vertical[:,None]*vertical[None,:]
    zeros3 = torch.zeros_like(k3)
    stiffness = torch.cat((torch.cat((k3, zeros3), -1),
                          torch.cat((zeros3, cfg.angular_k*eye3), -1)), -2)
    damping = torch.diag(displacement.new_tensor([cfg.spring_d]*3+[cfg.angular_d]*3))
    effective = damping+dt*stiffness
    position = torch.cat((displacement, orientation_error), -1)
    velocity = torch.cat((point_velocity, angular_velocity), -1)
    # Rigid-body free acceleration: gravity, centrifugal point acceleration,
    # and gyroscopic angular acceleration. No unmeasured contact prediction.
    gyro = torch.zeros_like(angular_velocity)
    if gyroscopic_forces:
        inertia = torch.linalg.inv(inverse_inertia)
        gyro = -(inverse_inertia @ torch.linalg.cross(
            angular_velocity, (inertia @ angular_velocity[...,None]).squeeze(-1), dim=-1)[...,None]).squeeze(-1)
    if external_torque is not None:
        gyro = gyro+(inverse_inertia@external_torque[...,None]).squeeze(-1)
    point_free = displacement.new_tensor(gravity) + torch.linalg.cross(
        angular_velocity, torch.linalg.cross(angular_velocity, lever, dim=-1), dim=-1)
    point_free -= (r @ gyro[...,None]).squeeze(-1)
    if external_force is not None:
        point_free = point_free+external_force/cfg.mass
    free = torch.cat((point_free, gyro), -1)
    rhs = -(stiffness @ position[...,None]+effective @ (velocity+dt*free)[...,None])
    identity = torch.eye(6, device=displacement.device, dtype=displacement.dtype)
    wrench = torch.linalg.solve(identity+dt*effective@mobility, rhs).squeeze(-1)
    point_force, angular_spring_torque = wrench[..., :3], wrench[..., 3:]
    # Preserve the prior bounded reaction while a geometric opening completes.
    unclamped_load = (-(point_force*axis).sum(-1)).clamp_min(0)
    magnitude = point_force.norm(dim=-1).clamp_min(1e-9)
    scale = torch.minimum(torch.ones_like(magnitude), threshold/magnitude)
    point_force = point_force*scale[...,None]
    load = (-(point_force*axis).sum(-1)).clamp_min(0)
    extension = (displacement*axis).sum(-1)
    exceeded = ((unclamped_load>threshold)&(extension>cfg.valid_pull_distance)
                | (extension>=.025) | (displacement.norm(dim=-1)>=cfg.stem_max_extension))
    timer = torch.where(attached & exceeded, timer+dt, torch.zeros_like(timer))
    attached = attached & (timer < cfg.tension_hold_s)
    force = point_force*attached[...,None]
    torque = (torch.linalg.cross(lever, point_force, dim=-1)+angular_spring_torque)*attached[...,None]
    return force, torque, attached, timer, load
