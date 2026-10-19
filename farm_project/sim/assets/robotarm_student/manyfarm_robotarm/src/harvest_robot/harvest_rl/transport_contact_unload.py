"""Bounded opening to unload excess contact near a stationary box waypoint."""
import math
import torch


def unload_step(previous,spent,eligible,force_min,dt):
    budget=math.radians(1.);rate=math.radians(.5)
    active=eligible & (force_min>.5) & (spent<budget-1e-8)
    increment=torch.where(active,(budget-spent).clamp(min=0.,max=rate*dt),0.)
    return previous+increment,spent+increment,increment
