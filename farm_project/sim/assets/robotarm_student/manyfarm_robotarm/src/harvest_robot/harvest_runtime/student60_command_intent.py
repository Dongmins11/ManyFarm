"""Physical jaw intent for an absolute position goal, from measured joint state."""
import numpy as np


def jaw_drive_intent(goal,measured,speed,dt):
    if speed<=0 or abs(dt-.05)>1e-8:raise ValueError('Expected positive jaw speed and20Hz')
    value=(goal-measured)/(speed*dt)
    if hasattr(value,'clamp'):return value.clamp(-1,1)
    if not np.isfinite(value).all():raise ValueError('Nonfinite jaw drive error')
    return np.clip(value,-1,1)
