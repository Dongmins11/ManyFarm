"""Comparison-only arm command feedback; never change grasp/physics/outcome flags."""
from dataclasses import asdict, dataclass
import math
import torch

from .pull_refine_60hz import PullRefinement, prepare_actions


@dataclass(frozen=True)
class PullFeedbackSpec:
    require_ready: bool = False
    ready_dwell_s: float = .25
    attached_action_limit: float = 1.
    contact_feedback: bool = False
    weak_scale: float = .5
    recovery_dwell_s: float = .1
    pause_limit_s: float = .3
    total_pause_limit_s: float = .6
    resume_ramp_s: float = .25

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not isinstance(value, bool) and (not math.isfinite(value) or value <= 0):
                raise ValueError(f'Positive finite setting required: {key}')
        if self.attached_action_limit > 1 or self.weak_scale > 1:
            raise ValueError('Feedback may reduce commands only')
        if self.recovery_dwell_s > self.pause_limit_s or self.pause_limit_s > self.total_pause_limit_s:
            raise ValueError('Recovery must fit in bounded pause budget')


class PullFeedback:
    def __init__(self, count, device, spec):
        self.spec = spec
        self.base = PullRefinement(ramp_s=.5, initial_scale=.2)
        self.ready_time = torch.zeros(count, device=device)
        self.started = torch.zeros(count, device=device, dtype=torch.bool)
        self.start_time = self.ready_time.clone()
        self.paused = self.started.clone()
        self.halted = self.started.clone()
        self.pause_age = self.ready_time.clone()
        self.total_pause = self.ready_time.clone()
        self.recovery_time = self.ready_time.clone()
        self.resume_time = torch.full_like(self.ready_time, -100.)
        self.pause_events = self.ready_time.clone()
        self.diagnostics = {}

    def reset(self, ids):
        for name in ('ready_time', 'started', 'start_time', 'paused', 'halted', 'pause_age',
                     'total_pause', 'recovery_time', 'pause_events'):
            getattr(self, name)[ids] = 0
        self.resume_time[ids] = -100.

    def step(self, actions, elapsed, confirmed, release, attached, valid_detach,
             *, qualified, slip, distance, minimum_contact_force, max_slip,
             center_tolerance, contact_threshold, dt=.05):
        if abs(dt-.05) > 1e-9:
            raise ValueError('This comparison preserves 20Hz control')
        scope = confirmed & ~release
        attached_scope = scope & attached
        stable = qualified & (slip < max_slip)
        self.ready_time = torch.where(attached_scope & stable, self.ready_time+dt, 0.)
        ready = self.ready_time >= self.spec.ready_dwell_s-1e-7
        start = attached_scope & ~self.started & (elapsed >= 2.-1e-7)
        if self.spec.require_ready:
            start &= ready
        self.start_time = torch.where(start, elapsed, self.start_time)
        self.started |= start
        # Rebase only the ramp's clock; loaded joint targets and observations stay unchanged.
        delayed = self.started & (self.start_time > 2.+1e-7)
        effective = torch.where(delayed, 2.+elapsed-self.start_time, elapsed)
        if not self.spec.require_ready:
            effective = elapsed
        result, ramp, holding = prepare_actions(actions, effective, confirmed, release,
                                                attached, valid_detach, self.base)
        waiting = attached_scope & ~self.started & (elapsed >= 2.-1e-7)
        result[waiting, :5] = 0.
        pulling = attached_scope & self.started
        weak = pulling & ((distance > .85*center_tolerance) | (slip > .75*max_slip)
                          | (minimum_contact_force < 1.25*contact_threshold))
        pause_command = pulling & False
        resumed = pulling & False
        if self.spec.contact_feedback:
            begin = pulling & ~stable & ~self.paused & ~self.halted
            self.paused |= begin
            self.pause_age = torch.where(begin, 0., self.pause_age)
            self.recovery_time = torch.where(begin, 0., self.recovery_time)
            self.pause_events += begin.float()
            active = pulling & self.paused & ~self.halted
            self.pause_age += active.float()*dt
            self.total_pause += active.float()*dt
            self.recovery_time = torch.where(active & stable, self.recovery_time+dt, 0.)
            # Recovery on the budget boundary wins; otherwise retain targets, never invent failure.
            resumed = active & (self.recovery_time >= self.spec.recovery_dwell_s-1e-7)
            self.paused &= ~resumed
            self.resume_time = torch.where(resumed, elapsed, self.resume_time)
            expired = active & ~resumed & ((self.pause_age >= self.spec.pause_limit_s-1e-7)
                         | (self.total_pause >= self.spec.total_pause_limit_s-1e-7))
            self.halted |= expired
            pause_command = pulling & (self.paused | self.halted)
        limit = torch.full_like(elapsed, self.spec.attached_action_limit)
        if self.spec.contact_feedback:
            limit = torch.where(weak, limit*self.spec.weak_scale, limit)
        if self.spec.attached_action_limit < 1 or self.spec.contact_feedback:
            result[pulling, :5] = result[pulling, :5].clamp(-limit[pulling, None], limit[pulling, None])
        if self.spec.contact_feedback:
            recovering = pulling & ((elapsed-self.resume_time) < self.spec.resume_ramp_s)
            scale = (.2+.8*((elapsed-self.resume_time)/self.spec.resume_ramp_s).clamp(0, 1))
            result[recovering, :5] *= scale[recovering, None]
            result[pause_command, :5] = 0.
        self.diagnostics = dict(feedback_ready=ready, feedback_stable=stable,
            feedback_ready_s=self.ready_time, feedback_started=self.started,
            feedback_start_s=self.start_time, feedback_waiting=waiting,
            feedback_paused=pause_command, feedback_halted=self.halted,
            feedback_weak_margin=weak, feedback_action_limit=limit,
            feedback_total_pause_s=self.total_pause, feedback_pause_events=self.pause_events,
            feedback_resume_event=resumed)
        return result, ramp, holding
