"""Preserve acquisition age across ROS/monotonic clocks and measured joint poses."""
from collections import deque
import math
import numpy as np


class RosClockMap:
    def __init__(self,jump_tolerance_s=.05):self.offset=None;self.tolerance=jump_tolerance_s

    def capture_to_monotonic(self,stamp_ros_s,now_ros_s,now_monotonic_s):
        if not all(math.isfinite(v) for v in [stamp_ros_s,now_ros_s,now_monotonic_s]):raise ValueError('Invalid capture clock')
        offset=now_ros_s-now_monotonic_s
        if self.offset is not None and abs(offset-self.offset)>self.tolerance:raise ValueError('ROS clock jumped; reset all timing buffers')
        if stamp_ros_s>now_ros_s+1e-6:raise ValueError('Future acquisition stamp')
        self.offset=offset
        # The original camera age remains now_ros-stamp_ros. This does not
        # certify that the driver header itself is an accurate exposure stamp.
        return stamp_ros_s-offset


class JointHistory:
    def __init__(self,duration_s=2.,maximum_gap_s=.05):
        self.rows=deque();self.duration=duration_s;self.maximum_gap=maximum_gap_s

    def append(self,stamp_s,q_rad):
        q=np.asarray(q_rad,float)
        if not math.isfinite(stamp_s) or q.shape!=(6,) or not np.isfinite(q).all():raise ValueError('Invalid joint sample')
        if self.rows and stamp_s<=self.rows[-1][0]:raise ValueError('Joint clock did not increase')
        self.rows.append((stamp_s,q.copy()))
        while self.rows and self.rows[0][0]<stamp_s-self.duration:self.rows.popleft()

    def at(self,stamp_s):
        if not math.isfinite(stamp_s):raise ValueError('Invalid pose timestamp')
        for i,(stamp,q) in enumerate(self.rows):
            if abs(stamp-stamp_s)<1e-9:return q.copy()
            if stamp>stamp_s:
                if i==0:return None
                previous,old=self.rows[i-1]
                if stamp-previous>self.maximum_gap:return None
                alpha=(stamp_s-previous)/(stamp-previous)
                return old*(1-alpha)+q*alpha
        # No extrapolation from the latest pose to an unseen camera exposure.
        return None
