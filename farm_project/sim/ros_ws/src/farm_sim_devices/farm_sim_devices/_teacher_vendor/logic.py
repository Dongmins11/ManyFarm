"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

import torch

def limited_joint_targets(targets, measured, actions, speed, dt, lower, upper, max_error):
    result = (targets + actions * speed * dt).clamp(lower, upper)
    # Prevent an unreachable closing target from accumulating through the fruit.
    result[:, -1] = torch.maximum(result[:, -1], measured[:, -1] - max_error)
    return result.clamp(lower, upper)

def dwell(timer, condition, dt):
    return torch.where(condition, timer + dt, torch.zeros_like(timer))

def compliant_gripper_hold(target, measured, opening_action, active, error, lower, upper):
    # Opening releases the latch; zero action afterwards must not close again.
    active = active & (opening_action <= 0)
    target = torch.where(active, measured-error, target).clamp(lower, upper)
    return target, active

def stage_success(task, confirmed, attached, loaded_time, detached_time, place_time, cfg):
    if task == "grasp":
        return confirmed & attached
    if task == "hold":
        return attached & (loaded_time >= cfg.hold_s)
    if task == "pull":
        return ~attached & (detached_time >= cfg.detached_hold_s)
    return ~attached & (place_time >= cfg.place_hold_s)

def valid_pull(displacement, cfg):
    """Extension gate: radial for v2, configured outward axis for v4, -X otherwise."""
    if cfg.attachment_version == 4:
        axis = torch.as_tensor(cfg.tension_axis, device=displacement.device, dtype=displacement.dtype)
        axis = axis / torch.linalg.vector_norm(axis)
        return (displacement * axis).sum(-1) > cfg.valid_pull_distance
    if cfg.attachment_version == 2:
        return torch.linalg.vector_norm(displacement, dim=-1) > cfg.valid_pull_distance
    return -displacement[...,0] > cfg.valid_pull_distance

def bilateral_contact(fixed_force, moving_force, distance, cfg):
    f = torch.linalg.vector_norm(fixed_force, dim=-1)
    m = torch.linalg.vector_norm(moving_force, dim=-1)
    opposed = (fixed_force * moving_force).sum(-1) < -0.15 * f * m
    return ((f > cfg.contact_threshold) & (m > cfg.contact_threshold) & opposed
            & (distance < cfg.diameter * 0.9))

def contained_in_box(position, velocity, cfg):
    lo = torch.tensor(cfg.box_min, device=position.device)
    hi = torch.tensor(cfg.box_max, device=position.device)
    # Conservative spherical bound valid for any fruit orientation.
    radius = max(cfg.diameter / 2, cfg.length * .48)
    # Bottom contact permits centre at collider resting height (whole visual stem differs).
    xy = ((position[..., :2] > lo[:2] + radius) & (position[..., :2] < hi[:2] - radius)).all(-1)
    # Opt-in current-asset correction; never accept a centre below the box floor.
    lower = lo[2] + max(0., cfg.length*.42 - cfg.legacy_box_bottom_margin)
    z = (position[..., 2] > lower) & (position[..., 2] < hi[2] - radius)
    return xy & z & (torch.linalg.vector_norm(velocity, dim=-1) < 0.12)

def grasp_diagnostics(distance, action, velocity, fixed_force, moving_force, grip, cfg):
    """Step-level evidence, not episode failure causes. Closing commands may stall."""
    near = distance < .025
    closing = action < -.05
    moving = velocity < -.02
    fixed = torch.linalg.vector_norm(fixed_force, dim=-1) > cfg.contact_threshold
    mobile = torch.linalg.vector_norm(moving_force, dim=-1) > cfg.contact_threshold
    return {
        "near": near,
        "near_no_close_command": near & ~closing & ~grip,
        "near_close_no_motion": near & closing & ~moving & ~grip,
        "near_close_no_contact": near & closing & ~fixed & ~mobile,
        "near_one_contact": near & (fixed ^ mobile),
        "near_two_contacts_not_opposed": near & fixed & mobile & ~grip,
        "bilateral_contact": grip,
    }

def qualified_grasp(contact, center_error, cfg):
    """Same gate for dwell, retained grasp and substep detachment credit."""
    if cfg.grasp_version == 1:
        return contact
    return contact & (center_error <= cfg.grasp_center_tolerance)

def placement_target(cfg, device):
    # Inside the box, with clearance for the conservative fruit extent.
    radius = max(cfg.diameter/2, cfg.length*.48)
    height = cfg.box_max[2]+radius+.025 if cfg.reward_version >= 7 else cfg.box_max[2]-radius-.015
    return torch.tensor([(cfg.box_min[0]+cfg.box_max[0])/2,
                         (cfg.box_min[1]+cfg.box_max[1])/2,
                         height], device=device)

def fruit_bounds(position, quaternion, cfg):
    """World AABB of the actual oriented ellipsoidal body (decorative stem excluded)."""
    w,x,y,z = quaternion.unbind(-1)
    r = torch.stack((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),
                     2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),
                     2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)), -1).reshape(-1,3,3)
    radii = torch.tensor([cfg.diameter/2,cfg.diameter/2,cfg.length*.4],device=position.device)
    extent = ((r*r)*radii.square()).sum(-1).sqrt()
    center = position-r[:,:,2]*(cfg.length*.08)
    return center, extent

def settled_in_box(position, quaternion, velocity, cfg):
    center, extent = fruit_bounds(position, quaternion, cfg)
    lo = torch.tensor(cfg.box_min,device=position.device)
    hi = torch.tensor(cfg.box_max,device=position.device)
    lower_tolerance = torch.full_like(lo,cfg.box_contact_tolerance)
    if cfg.sequence:
        lower_tolerance[2] = .005  # native multi-fruit fixture: settled hull bottom differs by ~3.9mm
    lower_tolerance[2] = max(cfg.box_contact_tolerance,.005 if cfg.sequence else 0.,cfg.box_bottom_contact_tolerance)
    inside = ((center-extent >= lo-lower_tolerance) &
              (center+extent <= hi+cfg.box_contact_tolerance)).all(-1)
    return inside & (velocity.norm(dim=-1) < .12)

def above_box(position, quaternion, cfg):
    center, extent = fruit_bounds(position, quaternion, cfg)
    lo = torch.tensor(cfg.box_min,device=position.device)
    hi = torch.tensor(cfg.box_max,device=position.device)
    xy = ((center[:,:2]-extent[:,:2] >= lo[:2]+.005) &
          (center[:,:2]+extent[:,:2] <= hi[:2]-.005)).all(-1)
    bottom = center[:,2]-extent[:,2]
    return xy & (bottom >= hi[2]+.005) & (bottom <= hi[2]+.07)

def controlled_release(lost_contact, armed, in_zone, previous_speed, tcp_speed, horizontal_speed, cfg):
    return (lost_contact & armed & in_zone & (previous_speed <= cfg.release_speed)
            & (tcp_speed <= cfg.release_speed) & (horizontal_speed <= cfg.release_speed))

def update_pending_detach(pending, grip, slip, elapsed, dt, hold_s, max_slip):
    """No grace for contact loss: a dropped fruit cannot be caught for credit."""
    maintained = grip & (slip < max_slip)
    rejected = pending & ~maintained
    elapsed = torch.where(pending & maintained, elapsed + dt, torch.zeros_like(elapsed))
    accepted = pending & maintained & (elapsed >= hold_s)
    return pending & ~rejected & ~accepted, elapsed, accepted, rejected

def recover_pending_detach(pending, grip, contact, distance, slip, elapsed, age, lost, dt, hold_s, max_slip, tolerance):
    """Bounded recovery; only strict continuous grasp earns detachment credit."""
    age = torch.where(pending, age + dt, torch.zeros_like(age))
    lost = torch.where(pending & ~contact, lost + dt, torch.zeros_like(lost))
    rejected = pending & ((slip >= max_slip) | (distance > tolerance) | (lost > .100001) | (age > .750001))
    elapsed = torch.where(pending & grip & ~rejected, elapsed + dt, torch.zeros_like(elapsed))
    accepted = pending & ~rejected & (elapsed >= hold_s)
    return pending & ~rejected & ~accepted, elapsed, accepted, rejected, age, lost

def horizontal_grasp_alignment(gripper_quat, fruit_quat, tolerance):
    """SO101 fixed-finger normal is local X; fruit long axis is local Z.

    Require both world-horizontal closure and closure across the fruit's long
    axis, so tilting the fruit alone cannot satisfy the preference. Quats: wxyz.
    Finger order and yaw are unconstrained.
    """
    import math
    w,x,y,z = gripper_quat.unbind(-1)
    closing = torch.stack((1-2*(y*y+z*z), 2*(x*y+w*z), 2*(x*z-w*y)), -1)
    w,x,y,z = fruit_quat.unbind(-1)
    upright = torch.stack((2*(x*z+w*y), 2*(y*z-w*x), 1-2*(x*x+y*y)), -1)
    error = torch.maximum(closing[...,2].abs(), (closing*upright).sum(-1).abs()).clamp(0,1)
    return error, error <= math.sin(tolerance)

def placement_contained(position, quaternion, velocity, cfg):
    """Shared deposit geometry, independent of release qualification."""
    if cfg.reward_version >= 7 or getattr(cfg, 'shape_placement', False):
        return settled_in_box(position, quaternion, velocity, cfg)
    return contained_in_box(position, velocity, cfg)

def pull_squeeze_error(base, hold_time, grip, has_grasped):
    """Gradual preload after 0.75s continuous qualified grip; no opening override."""
    extra=((hold_time-.75)*.01).clamp(0.,.02)
    return base+torch.where(grip & has_grasped,extra,torch.zeros_like(extra))

def rearm_confirmed_squeeze(active, confirmed, closing_action):
    """Restore compliant hold only with confirmed contact and an explicit close.

    An opening command must always release the latch; mere proximity cannot arm it.
    """
    return (active | (confirmed & (closing_action < -0.05))) & (closing_action <= 0)

def retain_detached_grip_target(previous, proposed, detached, confirmed, active, action):
    """Preserve established closing target, but never suppress explicit opening."""
    hold=detached & confirmed & active & (action<=0)
    return torch.where(hold,previous,proposed)

def retain_confirming_grip_target(previous, proposed, scope, confirmed, active, action, *, preload_start=None, preload_step=0.):
    """Opt-in post-break confirmation: keep established preload, not measured-angle chasing.

    Scope must come from current physical capture evidence. No contact/confirmation
    is invented, and explicit opening or inactive squeeze releases the target.
    """
    held=scope & confirmed & active & (action<=0)
    target=previous
    if preload_start is not None and preload_step:
        # One bounded adjustment at the handoff, never repeated angle chasing.
        target=previous-preload_step*preload_start.to(previous.dtype)
    return torch.where(held,target,proposed),held

def qualified_transport_hold_scope(transport, attached, valid_detach, retained, grip, contact):
    """Current physical carrying only; never retain a target through loss or release."""
    return transport & ~attached & valid_detach & retained & grip & contact

def bounded_transport_preload(previous, proposed, measured, origin, latched,
                              start, context, physical_grip, active, action, *,
                              initial_step, error, max_close, rate, dt):
    """Evaluation-only, position-error preload with an absolute closing budget.

    Start requires qualified physical carrying. Afterwards weak/lost contact
    freezes the last target, preventing a jump to measured-error fallback.
    This does not latch contact/success or constrain fruit motion. Release and
    inactive squeeze immediately resume the ordinary proposed command.
    """
    start = start & context & physical_grip & active & (action <= 0)
    origin = torch.where(start, previous, origin)
    latched = (latched | start) & context & active & (action <= 0)
    base = torch.where(start, previous-initial_step, previous)
    floor = origin-max_close
    desired = torch.minimum(base, measured-error).clamp_min(floor)
    delta = (desired-base).clamp(min=-rate*dt, max=0.)
    adjusting = latched & physical_grip & ~start
    target = torch.maximum(torch.where(adjusting, base+delta, base), floor)
    return torch.where(latched, target, proposed), origin, latched, adjusting & (delta < 0)

def release_intent_step(intent, age, lost, gripper_action, hand_still, dt):
    """A stopped opening has 1.5 s to lose contact; hand motion/closing cancels it.

    Falling fruit velocity is not a hand throwing measurement. Actual contained
    settling remains a separate mandatory success condition.
    """
    age = torch.where(intent, age+dt, torch.zeros_like(age))
    intent = intent & (age<=1.5) & (gripper_action>=0) & hand_still
    approved = lost & intent
    return intent & ~approved, age, approved

def placement_outcome(in_box, raw_grip, attached, retained, valid_detach):
    """Actual settled containment; release-motion approval is deliberately independent.

    The caller accumulates dwell and gives physical failure conditions priority.
    """
    return in_box & ~raw_grip & ~attached & retained & valid_detach

def mesh_settled_in_box(position, quaternion, velocity, vertices, cfg):
    """Contain the actual collider vertices, including stem, at existing tolerances."""
    w,x,y,z=quaternion.unbind(-1)
    r=torch.stack((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),
                   2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),
                   2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)),-1).reshape(-1,3,3)
    rotated=torch.matmul(vertices[None],r.transpose(1,2))
    lower=rotated.amin(1)+position;upper=rotated.amax(1)+position
    lo=torch.as_tensor(cfg.box_min,device=position.device,dtype=position.dtype)
    hi=torch.as_tensor(cfg.box_max,device=position.device,dtype=position.dtype)
    tolerance=torch.full_like(lo,cfg.box_contact_tolerance)
    tolerance[2]=max(cfg.box_contact_tolerance,cfg.box_bottom_contact_tolerance,.005 if cfg.sequence else 0.)
    return ((lower>=lo-tolerance)&(upper<=hi+cfg.box_contact_tolerance)).all(-1)&(velocity.norm(dim=-1)<.12)

def orientation_speed(previous,current,dt):
    """Shortest quaternion angle per control interval; quaternion sign invariant."""
    previous=previous/previous.norm(dim=-1,keepdim=True).clamp_min(1e-8)
    current=current/current.norm(dim=-1,keepdim=True).clamp_min(1e-8)
    return 2*torch.acos((previous*current).sum(-1).abs().clamp(0,1))/dt

def transport_stage_mask(task, stage, reference):
    """Same transport scope for independent training and staged inference."""
    if stage is not None:
        return stage == 1
    return torch.full_like(reference, task == 'transport', dtype=torch.bool)

def early_detach_check(pending, contact, strict_grip, distance, slip, elapsed, age, dt, hold_s, tolerance, max_slip):
    """Continuous physical capture is mandatory; never grant credit for a later catch."""
    age=torch.where(pending,age+dt,age)
    rejected=pending & (~contact | (distance>tolerance) | (slip>=max_slip) | (age>hold_s+.35))
    elapsed=torch.where(pending & strict_grip & ~rejected,elapsed+dt,torch.zeros_like(elapsed))
    accepted=pending & ~rejected & (elapsed>=hold_s)
    return pending & ~rejected & ~accepted,elapsed,age,accepted,rejected

def pending_capture_grip(centered_contact, orientation_ok, separate_orientation=False):
    """Only for an existing early-detach candidate; dwell/slip are checked separately."""
    return centered_contact if separate_orientation else centered_contact & orientation_ok

def captured_break_candidate(selected_break, valid, centered_contact, confirmed, include_confirmed=False):
    return selected_break & ~valid & centered_contact & (~confirmed | include_confirmed)

def transport_stop_speed(pose_speed, instantaneous_speed, limit):
    """Control-interval motion plus a bounded instantaneous contact-spike guard.

    Caller still requires uninterrupted release_stop_s dwell, zone and stable grip.
    This is not permission to ignore arbitrarily large within-step velocities.
    """
    return ((pose_speed <= limit) & (instantaneous_speed <= 4 * limit)
            & torch.isfinite(pose_speed) & torch.isfinite(instantaneous_speed))
