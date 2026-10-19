"""ROS-free selected-target boundary. SI units; positions share calibrated arm frame.

No tracking, TF lookup, simulator truth or completion inference lives here.
Future ROS/vision adapters supply these validated values to the student.
"""
from dataclasses import dataclass
import math
import torch

CONTRACT_VERSION = 1
STUDENT_STATE_DIM = 23


@dataclass(frozen=True)
class TargetObservation:
    target_id: str
    frame_id: str
    stamp_s: float
    position_m: tuple[float, float, float]
    valid: bool


class TargetSession:
    """One immutable assignment at a time; terminal results require explicit reset."""
    def __init__(self, frame_id: str, ttl_s: float = .3):
        if not frame_id or not math.isfinite(ttl_s) or ttl_s <= 0:
            raise ValueError("Require frame and positive TTL")
        self.frame_id, self.ttl_s = frame_id, ttl_s
        self.reset()

    def reset(self):
        self.status = "WAIT_TARGET"
        self.task_id = self.target_id = None
        self.observation = None
        self.reason = ""

    def assign(self, task_id: str, target_id: str):
        if self.status != "WAIT_TARGET":
            raise RuntimeError("Assignment requires explicit recovery/reset after terminal")
        if not task_id or not target_id:
            raise ValueError("Require persistent task and target IDs")
        self.task_id, self.target_id = task_id, target_id
        self.status = "RUNNING"

    def update(self, observation: TargetObservation, now_s: float):
        if self.status != "RUNNING":
            raise RuntimeError("No active assignment")
        if observation.target_id != self.target_id or observation.frame_id != self.frame_id:
            raise ValueError("Observation identity/frame mismatch")
        if (not math.isfinite(now_s) or not math.isfinite(observation.stamp_s)
                or observation.stamp_s > now_s):
            raise ValueError("Require finite timestamps in the same clock domain")
        if self.observation and observation.stamp_s < self.observation.stamp_s:
            raise ValueError("Out-of-order observation")
        if len(observation.position_m) != 3 or not all(math.isfinite(x) for x in observation.position_m):
            raise ValueError("Require finite XYZ, including invalid observations")
        if type(observation.valid) is not bool:
            raise ValueError("valid must be boolean")
        self.observation = observation

    def sample(self, now_s: float):
        """Return XYZ, valid and age; lost observations never imply completion."""
        if not math.isfinite(now_s):
            raise ValueError("Invalid clock")
        obs = self.observation
        if obs and now_s < obs.stamp_s:
            raise ValueError("Clock moved backwards; reset session")
        age = min(self.ttl_s, now_s-obs.stamp_s) if obs else self.ttl_s
        valid = (self.status == "RUNNING" and obs is not None and obs.valid
                 and now_s-obs.stamp_s <= self.ttl_s)
        return (obs.position_m if valid else (0., 0., 0.)), bool(valid), age

    def finish(self, status: str, reason: str):
        if self.status != "RUNNING":
            raise RuntimeError("Terminal result is latched")
        if status not in ("SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED") or not reason:
            raise ValueError("Require terminal status and evidence/reason")
        self.status, self.reason = status, reason

    def result(self):
        return dict(task_id=self.task_id, target_id=self.target_id,
                    status=self.status, reason=self.reason)


def student_state(proprio, target_position, tcp_position, valid, age_s, ttl_s=.3):
    """Tensor path shared by simulator and future runtime; no privileged fallback.

    XYZ and TCP must be in the SAME arm-base frame (not TCP rotating axes).
    Invalid target deltas are zero. RGB and recurrent/history state are separate.
    """
    if not math.isfinite(ttl_s) or ttl_s <= 0:
        raise ValueError("Invalid TTL")
    n = proprio.shape[0]
    if (proprio.shape != (n, 18) or target_position.shape != (n, 3)
            or tcp_position.shape != (n, 3) or valid.shape != (n,)
            or age_s.shape != (n,) or valid.dtype != torch.bool):
        raise ValueError("Invalid student observation shapes/types")
    tensors = (proprio, target_position, tcp_position, age_s)
    if not all(torch.isfinite(t).all() for t in tensors) or bool((age_s < 0).any()):
        raise ValueError("Non-finite state or negative observation age")
    fresh = valid & (age_s <= ttl_s)
    relative = torch.where(fresh[:, None], target_position-tcp_position, 0.)
    return torch.cat((proprio, relative, fresh[:, None].to(proprio.dtype),
                      age_s.clamp(max=ttl_s)[:, None]), dim=-1)
