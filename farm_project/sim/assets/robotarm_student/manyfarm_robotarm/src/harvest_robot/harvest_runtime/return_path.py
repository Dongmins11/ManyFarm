"""Pure numerical recorded-path return helpers. Not a collision-free path proof."""
import numpy as np


def reverse_path(history, home, open_gripper, spacing=.025):
    history=np.asarray(history,dtype=float)
    home=np.asarray(home,dtype=float)
    if history.ndim!=2 or history.shape[1]!=6 or home.shape!=(6,) or not np.isfinite(history).all() or not np.isfinite(home).all():
        raise ValueError('Require finite measured joint history Nx6 and HOME6')
    if len(history)==0 or not np.isfinite(open_gripper) or spacing<=0:
        raise ValueError('Empty path or invalid return parameters')
    # Remove only effectively identical samples. Do not shortcut curved paths.
    path=[]
    for q in history[::-1]:
        q=q.copy();q[-1]=open_gripper
        if not path or np.max(abs(q[:5]-path[-1][:5]))>=spacing:
            path.append(q)
    end=home.copy();end[-1]=open_gripper
    path.append(end)
    return np.array(path)


def bounded_target(measured, desired, velocity, dt):
    measured,desired=np.asarray(measured),np.asarray(desired)
    if not np.isfinite(measured).all() or not np.isfinite(desired).all() or velocity<=0 or dt<=0:
        raise ValueError('Invalid return command')
    return measured+np.clip(desired-measured,-velocity*dt,velocity*dt)
