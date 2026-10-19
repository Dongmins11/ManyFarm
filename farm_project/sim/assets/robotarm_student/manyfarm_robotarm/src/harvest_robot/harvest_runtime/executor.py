"""Caller-clocked, nonblocking sequential harvest coordinator (contract v1).

A backend owns policy observations/actions, independent completion evidence and
collision-checked return motion. The coordinator never resets a physical scene.
All hooks must return promptly; one owner calls tick/cancel (not thread-safe).
"""
from dataclasses import dataclass
from typing import Callable, Protocol
import math


def positive(value):
    return math.isfinite(value) and value > 0


@dataclass(frozen=True)
class Target:
    target_id: str
    frame_id: str
    position_m: tuple[float, float, float]
    stamp_s: float
    valid: bool = True

    def validate(self, target_id, frame_id, now, ttl):
        if self.target_id != target_id or self.frame_id != frame_id:
            raise ValueError('Target identity/frame mismatch; adapter must transform frames')
        if type(self.valid) is not bool or not self.valid:
            raise ValueError('Target observation invalid')
        if (not math.isfinite(self.stamp_s) or not 0 <= now-self.stamp_s <= ttl
                or len(self.position_m) != 3
                or not all(math.isfinite(v) for v in self.position_m)):
            raise ValueError('Target stale/future or nonfinite position')


@dataclass(frozen=True)
class Request:
    request_id: str
    target_id: str
    timeout_s: float = 20.


@dataclass(frozen=True)
class Feedback:
    request_id: str
    target_id: str
    status: str  # RUNNING, SUCCEEDED, FAILED, TIMED_OUT
    reason: str = ''


class Backend(Protocol):
    """Implementations must not infer success from target disappearance.

    start_target resets ONLY per-target policy/history/task state. tick_target
    feeds teacher truth OR student sensors to the policy, applies validated
    commands and polls independent completion. start_return/tick_return perform
    actual motion and report readiness only after hand empty, safe pose reached,
    and world state refreshed. stop requests a safe hold; tick_stop acknowledges
    it. stop must also work if start_target/start_return raised part way through.
    """
    def start_target(self, request: Request, target: Target, now_s: float) -> None: ...
    def tick_target(self, request: Request, now_s: float) -> Feedback: ...
    def start_return(self, request: Request, now_s: float) -> None: ...
    def tick_return(self, request: Request, now_s: float) -> Feedback: ...
    def stop(self, reason: str, now_s: float) -> None: ...
    def tick_stop(self, now_s: float) -> bool: ...


class Executor:
    """One immutable batch, fixed upstream order, no automatic retry or skip.

    observe is called AFTER return, immediately before assigning each target.
    During harvesting the backend must enforce sensor freshness/command limits.
    Construct a new executor for a new batch only after acknowledged stop/return;
    backend/world may persist. Completed IDs can be carried across batches.
    """
    TERMINAL = frozenset(('SUCCEEDED', 'FAILED', 'TIMED_OUT', 'CANCELLED'))

    def __init__(self, backend: Backend, observe: Callable[[str, float], Target],
                 frame_id: str, *, observation_ttl_s=.3, return_timeout_s=20.,
                 stop_timeout_s=2., completed_ids=()):
        if not frame_id or not all(positive(v) for v in
                (observation_ttl_s, return_timeout_s, stop_timeout_s)):
            raise ValueError('Require frame and finite positive timeouts')
        self.backend, self.observe, self.frame_id = backend, observe, frame_id
        self.ttl, self.return_timeout, self.stop_timeout = observation_ttl_s, return_timeout_s, stop_timeout_s
        self.completed = set(completed_ids)
        self.state = 'IDLE'
        self.reason = ''
        self.results = []
        self.events = []
        self.stop_confirmed = False
        self._last_time = None
        self._queue = ()
        self._index = 0
        self._pending = 'FAILED'

    @property
    def done(self):
        return self.state in self.TERMINAL

    @property
    def active(self):
        return self._queue[self._index] if self._queue else None

    def _clock(self, now):
        if not math.isfinite(now) or (self._last_time is not None and now < self._last_time):
            raise ValueError('Clock must be finite and monotonic; do not mix ROS/wall clocks')
        self._last_time = now

    def _transition(self, state, now, reason=''):
        self.state, self.reason = state, reason
        self._entered = now
        self.events.append(dict(stamp_s=now, state=state, reason=reason,
                                request_id=self.active.request_id if self.active else None))

    def start(self, requests, now_s):
        if self.state != 'IDLE':
            raise RuntimeError('Batch already started; terminal state is latched')
        self._clock(now_s)
        requests = tuple(requests)
        if not requests or any(not isinstance(r, Request) or not r.request_id or not r.target_id
                               or not positive(r.timeout_s) for r in requests):
            raise ValueError('Require nonempty requests with IDs and positive timeout')
        if len({r.request_id for r in requests}) != len(requests) or len({r.target_id for r in requests}) != len(requests):
            raise ValueError('Duplicate request/target IDs')
        if any(r.target_id in self.completed for r in requests):
            raise ValueError('Already completed target')
        self._queue = requests
        self._return(now_s)  # First target also requires a known safe start.

    def _return(self, now):
        self._transition('RETURNING', now)
        try:
            self.backend.start_return(self.active, now)
        except Exception as exc:
            self._stop('FAILED', f'return_start: {exc}', now)

    def _feedback(self, feedback):
        if not isinstance(feedback, Feedback) or (feedback.request_id, feedback.target_id) != (self.active.request_id, self.active.target_id):
            raise ValueError('Feedback request/target mismatch')
        if feedback.status not in ('RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT'):
            raise ValueError('Unsupported backend status')
        if feedback.status != 'RUNNING' and not feedback.reason:
            raise ValueError('Terminal feedback requires evidence/reason')
        return feedback

    def _stop(self, status, reason, now):
        self._pending = status
        self._transition('STOPPING', now, reason)
        try:
            self.backend.stop(reason, now)
        except Exception as exc:
            self.reason += f'; stop_request_error: {exc}'

    def cancel(self, now_s, reason='operator_cancel'):
        if self.done or self.state == 'IDLE':
            return
        self._clock(now_s)
        if self.state != 'STOPPING':
            self._stop('CANCELLED', reason, now_s)

    def tick(self, now_s):
        if self.done or self.state == 'IDLE':
            return self.state
        try:
            self._clock(now_s)
        except ValueError as exc:
            # Invalid clock must not issue another policy action.
            self._stop('FAILED', str(exc), self._last_time)
            return self.state
        try:
            if self.state == 'STOPPING':
                ack = self.backend.tick_stop(now_s)
                if type(ack) is not bool:
                    raise ValueError('Stop acknowledgement must be bool')
                if ack:
                    self.stop_confirmed = True
                    self._transition(self._pending, now_s, self.reason)
                elif now_s-self._entered >= self.stop_timeout:
                    self._transition('FAILED', now_s, self.reason+'; stop_unconfirmed')
            elif self.state == 'RETURNING':
                if now_s-self._entered >= self.return_timeout:
                    self._stop('TIMED_OUT', 'return_timeout', now_s)
                    return self.state
                f = self._feedback(self.backend.tick_return(self.active, now_s))
                if f.status in ('FAILED','TIMED_OUT'):
                    self._stop(f.status, 'return_failed: '+f.reason, now_s)
                elif f.status == 'SUCCEEDED':
                    if self.active.target_id in self.completed:
                        self._index += 1
                    if self._index == len(self._queue):
                        self._index -= 1
                        self._transition('SUCCEEDED', now_s, 'all_targets_confirmed_and_returned')
                        return self.state
                    target = self.observe(self.active.target_id, now_s)
                    target.validate(self.active.target_id, self.frame_id, now_s, self.ttl)
                    self.backend.start_target(self.active, target, now_s)
                    self._transition('HARVESTING', now_s)
            elif self.state == 'HARVESTING':
                if now_s-self._entered >= self.active.timeout_s:
                    self._stop('TIMED_OUT', 'target_timeout', now_s)
                    return self.state
                f = self._feedback(self.backend.tick_target(self.active, now_s))
                if f.status in ('FAILED','TIMED_OUT'):
                    self.results.append(dict(request_id=f.request_id,target_id=f.target_id,status=f.status,reason=f.reason))
                    self._stop(f.status, f.reason, now_s)
                elif f.status == 'SUCCEEDED':
                    self.completed.add(self.active.target_id)
                    self.results.append(dict(request_id=f.request_id,target_id=f.target_id,status=f.status,reason=f.reason))
                    self._return(now_s)
        except Exception as exc:
            if self.state == 'STOPPING':
                self._transition('FAILED', now_s, self.reason+f'; stop_unconfirmed: {exc}')
            else:
                self._stop('FAILED', f'backend_error: {exc}', now_s)
        return self.state

    def report(self):
        return dict(contract_version=1,state=self.state,reason=self.reason,
                    completed_ids=sorted(self.completed),results=list(self.results),
                    stop_confirmed=self.stop_confirmed,events=list(self.events))
