"""Observation-only open-jaw approach diagnostic; never declares harvest success."""
import numpy as np


class OpenApproach:
    def __init__(self, dt=.05):
        self.dt = dt
        self.target_id = None
        self.reset()

    def reset(self):
        self.count = 0
        self.elapsed = self.lost = self.worsening = 0.
        self.best_distance = float('inf')

    def apply(self, action, sample, local_target, target_id, gap_m=.07, diameter_m=.07):
        if target_id != self.target_id:
            self.reset()
            self.target_id = target_id
        self.elapsed += self.dt
        result = np.asarray(action, dtype=np.float32).copy()
        state = sample['state']
        local = np.asarray(local_target, dtype=float)
        valid = bool(state[21] and 0 <= state[22] <= self.dt and sample['camera_valid'].any()
                     and np.isfinite(local).all())
        opened = bool(state[5] >= .95)
        # TCP is referenced to the nominal fruit diameter, not the open gap midpoint.
        error = local - np.array([(gap_m-diameter_m)/2, 0., 0.])
        distance = float(np.linalg.norm(error)) if valid else None
        centered = bool(valid and np.max(np.abs(error)) <= .012)
        self.lost = 0. if valid else self.lost + self.dt
        if valid and opened:
            self.best_distance = min(self.best_distance, distance)
            diverging = self.best_distance < .10 and distance > self.best_distance + .020
            self.worsening = self.worsening + self.dt if diverging else 0.
        else:
            self.worsening = 0.
        self.count = self.count + 1 if valid and opened and centered else 0
        ready = self.count >= 3
        abort = ('TARGET_LOST' if self.lost >= .5 else
                 'APPROACH_MISSED' if self.worsening >= .15 else
                 'APPROACH_TIMEOUT' if self.elapsed >= 8. else None)
        result[-1] = 1.
        if valid and opened and distance < .10:
            result[:5] *= .25
        if not valid or not opened or centered or abort:
            result[:5] = 0.
        return result, dict(mode='open_approach_diagnostic_v2', observable=valid,
                            opened=opened, estimated_centered=centered, ready=ready and not abort,
                            abort=abort, local_target_m=local.tolist(),
                            gap_center_error_m=error.tolist() if valid else None,
                            gap_m=float(gap_m), distance_m=distance,
                            best_distance_m=self.best_distance if np.isfinite(self.best_distance) else None)
