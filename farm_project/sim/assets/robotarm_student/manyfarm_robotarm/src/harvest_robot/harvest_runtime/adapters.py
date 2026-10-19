"""Composed backend: policy actions cannot declare harvest success.

Wire real sensors/simulation into read_observation, an independent detector into
completion, and a checked controller into apply_action. No automatic ground-truth
fallback, tensor conversion, joint-order guess, or unverified HOME trajectory.
"""
from dataclasses import dataclass
from typing import Any, Callable, Protocol
import math
from .executor import Feedback, Request, Target


@dataclass(frozen=True)
class Observation:
    request_id: str
    target_id: str
    frame_id: str
    stamp_s: float
    payload: Any  # teacher tensor OR student RGB-D/proprio; adapter owns schema
    valid: bool = True  # readiness of the whole policy input, not target visibility


class Policy(Protocol):
    def start_target(self, request: Request, target: Target) -> None: ...
    def act(self, observation: Observation) -> Any: ...
    def end_target(self) -> None: ...  # clear recurrent/history state; no world reset


class Motion(Protocol):
    def start_return(self, request: Request, now_s: float) -> None: ...
    def tick_return(self, request: Request, now_s: float) -> Feedback: ...
    def stop(self, reason: str, now_s: float) -> None: ...
    def tick_stop(self, now_s: float) -> bool: ...


class PolicyBackend:
    """Common teacher/student backend with required explicit integration hooks.

    completion polls BEFORE action; a successful completion must independently
    establish deposit/release, not merely policy termination or lost detection.
    validate_action must reject unsafe/nonfinite/wrong-unit/wrong-joint commands
    (raise), and apply_action sends exactly one checked command. Sensor adapter
    defines whether a lost target is still a valid history/depth observation.
    """
    def __init__(self, policy: Policy, motion: Motion, *,
                 read_observation: Callable[[Request, float], Observation],
                 completion: Callable[[Request, float], Feedback],
                 validate_action: Callable[[Any, Observation], None],
                 apply_action: Callable[[Any, float], None], observation_ttl_s=.3):
        if not math.isfinite(observation_ttl_s) or observation_ttl_s <= 0:
            raise ValueError('Require positive observation TTL')
        self.policy, self.motion = policy, motion
        self.read_observation, self.completion = read_observation, completion
        self.validate_action, self.apply_action = validate_action, apply_action
        self.ttl = observation_ttl_s
        self.target = None
        self.request = None

    def start_target(self, request, target, now_s):
        self.request, self.target = request, target
        self.last_stamp = None
        self.policy.start_target(request, target)

    def tick_target(self, request, now_s):
        if request != self.request:
            raise ValueError('Backend request mismatch')
        feedback = self.completion(request, now_s)
        if (not isinstance(feedback, Feedback)
                or (feedback.request_id, feedback.target_id) != (request.request_id, request.target_id)
                or feedback.status not in ('RUNNING','SUCCEEDED','FAILED','TIMED_OUT')):
            raise ValueError('Invalid completion feedback')
        if feedback.status != 'RUNNING':
            return feedback
        obs = self.read_observation(request, now_s)
        if (not isinstance(obs, Observation) or type(obs.valid) is not bool or not obs.valid
                or (obs.request_id,obs.target_id,obs.frame_id) != (request.request_id,request.target_id,self.target.frame_id)
                or not math.isfinite(obs.stamp_s) or not 0 <= now_s-obs.stamp_s <= self.ttl
                or (self.last_stamp is not None and obs.stamp_s < self.last_stamp)):
            raise ValueError('Invalid/stale/mismatched policy observation')
        self.last_stamp = obs.stamp_s
        action = self.policy.act(obs)
        self.validate_action(action, obs)
        self.apply_action(action, now_s)
        return feedback

    def start_return(self, request, now_s):
        self.policy.end_target()
        self.motion.start_return(request, now_s)

    def tick_return(self, request, now_s):
        return self.motion.tick_return(request, now_s)

    def stop(self, reason, now_s):
        # A broken policy cleanup must not prevent sending a stop request.
        try:
            self.motion.stop(reason, now_s)
        finally:
            self.policy.end_target()

    def tick_stop(self, now_s):
        return self.motion.tick_stop(now_s)
