"""Record original command timing, not rendered or lagging measured poses."""
import hashlib
import json
import math
from pathlib import Path

NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']


def six(row):
    row = list(row)
    if len(row) != 6 or not all(math.isfinite(v) for v in row):
        raise ValueError('Six finite joint angles required')
    return row


class MotionRecord:
    def __init__(self, dt, initial, checkpoint, joint_names):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError('Invalid original control period')
        if list(joint_names) != ['arm_2_' + n for n in NAMES]:
            raise ValueError('Teacher joint order/model requires review')
        self.dt = dt
        self.initial = six(initial)
        self.checkpoint = str(Path(checkpoint).resolve())
        self.checkpoint_hash = hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
        self.samples = []

    def append(self, target, measured_after):
        self.samples.append(dict(t_s=len(self.samples)*self.dt,
                                 target_rad=six(target), measured_after_rad=six(measured_after)))

    def save(self, path, status, metadata):
        if not self.samples:
            raise ValueError('No commands recorded')
        data = dict(schema='so101_teacher_motion_v1', names=NAMES,
                    status=status, dt_s=self.dt, duration_s=len(self.samples)*self.dt,
                    initial_rad=self.initial, samples=self.samples,
                    checkpoint=self.checkpoint, checkpoint_sha256=self.checkpoint_hash,
                    metadata=metadata, hardware_authorized=False,
                    note='Original position targets at original simulation times; not hardware approval')
        with Path(path).open('x') as f:
            json.dump(data, f, indent=2, allow_nan=False)
