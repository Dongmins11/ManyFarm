"""Forward docking along the taught pose's approach line (robot-relative errors)."""
import math


def command(preview, config):
    if preview.get('phase')=='WAIT_OBSERVATION':return None
    if any(not math.isfinite(v) or v<=0 for v in config.values()):raise ValueError('Invalid pose path settings')
    x,y,yaw=(preview[k] for k in ('error_x_m','error_y_m','error_yaw_rad'))
    if not all(math.isfinite(z) for z in (x,y,yaw)):raise ValueError('Invalid pose path error')
    along=math.cos(yaw)*x+math.sin(yaw)*y
    cross=-math.sin(yaw)*x+math.cos(yaw)*y
    if along < -config['overshoot_m']:raise RuntimeError('Taught approach line overshot; reposition required')
    # Polar pose feedback: the terminal orientation contributes during motion,
    # not only after reaching XY. A curved correction can initially turn away
    # from terminal yaw to remove lateral error on a differential-drive robot.
    alpha=math.atan2(y,x)
    beta=math.atan2(math.sin(yaw-alpha),math.cos(yaw-alpha))
    w=max(-config['max_angular_rps'],min(config['max_angular_rps'],
        config['heading_kp']*alpha-config['terminal_gain']*beta))
    blend=max(0.,1.-(abs(alpha)/config['rotate_first_rad'])**2)
    v=min(config['max_linear_mps'],max(config['min_linear_mps'],config['linear_kp']*math.hypot(x,y)))*blend
    return dict(linear_x=v,angular_z=w,phase='TRACK_TAUGHT_LINE' if v>0 else 'ALIGN_TAUGHT_LINE',
                path_along_m=along,path_cross_m=cross)
