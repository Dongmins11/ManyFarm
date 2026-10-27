"""Identify only the front lidar plane; never suppress physical collision tests."""
import math
import numpy as np
from .footprint_guard import FootprintGuard


def surface_points(points, distance, config):
    p=np.asarray(points,dtype=float)
    return ((p[:,0]>0) & (np.abs(p[:,0]-distance)<=config['plane_tolerance_m']) &
            (np.abs(p[:,1])<=config['half_width_m']))


def surface_guard(guard,config):
    for k in ('plane_tolerance_m','half_width_m','margin_m','sample_motion_m','max_scan_skew_s'):
        if not math.isfinite(config[k]) or config[k]<=0:raise ValueError('Invalid target surface '+k)
    c=dict(guard.c)
    c.update(margin_m=config['margin_m'],sample_motion_m=config['sample_motion_m'])
    if c['margin_m']>guard.c['margin_m']:raise ValueError('Target margin exceeds normal margin')
    return FootprintGuard(guard.poly,c)


def matching_raw(filtered, history):
    """Pair acquisition stamp and frame, irrespective of arrival order."""
    def key(m):return (m.header.frame_id,m.header.stamp.sec,m.header.stamp.nanosec)
    wanted=key(filtered)
    return next((m for m in reversed(history) if key(m)==wanted),None)


def raw_front_mask(ranges, angles, range_min, range_max, half_angle):
    """Restore only the configured distance-measurement cone, not body returns."""
    if not math.isfinite(half_angle) or not 0<half_angle<=math.pi/12:
        raise ValueError('Raw front cone must be positive and at most 15 degrees')
    rr=np.asarray(ranges,dtype=float);aa=np.asarray(angles,dtype=float)
    return (np.isfinite(rr)&(rr>=range_min)&(rr<=range_max)&
            (np.abs(np.arctan2(np.sin(aa),np.cos(aa)))<=half_angle))


def fresh_scan_pairs(filtered, raw, now_ns, max_age_s):
    """Newest acquisition first; exact raw/filtered stamp, one shared age limit."""
    stamp=lambda m:m.header.stamp.sec*10**9+m.header.stamp.nanosec
    for candidate in sorted(filtered,key=stamp,reverse=True):
        if not 0<=(now_ns-stamp(candidate))/1e9<=max_age_s:continue
        pair=matching_raw(candidate,raw)
        if pair is not None:yield candidate,pair
