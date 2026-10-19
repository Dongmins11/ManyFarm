"""Separate, CPU-checkable pull experiments; no change to the certified V4 path."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FILES = [
    'src/harvest_robot/harvest_rl/pull_speed_comparison.py',
    'src/harvest_robot/harvest_rl/pull_speed_probe.py',
    'scripts/teacher60_pull_speed_case.py',
    'scripts/compare_teacher60_pull.py',
    'scripts/compare_teacher60_pull.sh',
]


@dataclass(frozen=True)
class PullExperiment:
    speed_m_s: float = .015
    travel_m: float = .07
    initial_hold_s: float = 1.
    endpoint_hold_s: float = 1.
    loss_response: str = 'continue'
    pause_limit_s: float = .3
    resume_stable_s: float = .1
    total_pause_limit_s: float = 1.
    policy_dt_s: float = .05

    def __post_init__(self):
        values = [v for k, v in asdict(self).items() if k != 'loss_response']
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError('Experiment distances, rates and durations must be finite and positive')
        if self.loss_response not in ('continue', 'pause'):
            raise ValueError('Unknown contact-loss response')
        if self.resume_stable_s > self.pause_limit_s or self.pause_limit_s > self.total_pause_limit_s:
            raise ValueError('Contact recovery must fit inside the pause budget')
        if abs(self.policy_dt_s - .05) > 1e-12:
            raise ValueError('The experiment preserves 20Hz policy control')

    @property
    def duration_s(self):
        # Equal retreat distance, including the last command tick and endpoint dwell.
        pause = self.total_pause_limit_s if self.loss_response == 'pause' else 0.
        return math.ceil((self.initial_hold_s + self.travel_m / self.speed_m_s
                          + self.endpoint_hold_s + pause) / self.policy_dt_s) * self.policy_dt_s + self.policy_dt_s

    def retreat(self, elapsed):
        return np.clip(np.asarray(elapsed) * self.speed_m_s, 0., self.travel_m)


class ContactPause:
    """A probe-local pause/stop, never an environment success or failure flag.

    A pause sends zero arm action, retaining the existing loaded targets. It does
    not rebase targets to measured joints, close beyond preload, reset or move fruit.
    """
    def __init__(self, count, experiment):
        self.cfg = experiment
        self.paused = np.zeros(count, dtype=bool)
        self.halted = self.paused.copy()
        self.age = np.zeros(count)
        self.recovered = np.zeros(count)
        self.total_pause = np.zeros(count)
        self.elapsed = np.zeros(count)
        self.pause_events = np.zeros(count, dtype=int)

    def after_step(self, stable, active, pulling, command_paused):
        active = np.asarray(active, dtype=bool)
        stable = np.asarray(stable, dtype=bool)
        command_paused = np.asarray(command_paused, dtype=bool)
        if not pulling:
            return
        running = active & ~command_paused & ~self.halted
        self.elapsed[running] += self.cfg.policy_dt_s
        if self.cfg.loss_response == 'continue':
            return
        waiting = active & command_paused & ~self.halted
        self.total_pause[waiting] += self.cfg.policy_dt_s
        self.age[waiting] += self.cfg.policy_dt_s
        start = active & ~self.paused & ~stable & ~self.halted
        self.paused[start] = True
        self.pause_events[start] += 1
        self.age[start] = self.recovered[start] = 0.
        self.recovered = np.where(active & self.paused & stable,
                                  self.recovered + self.cfg.policy_dt_s, 0.)
        resumed = active & self.paused & (self.recovered >= self.cfg.resume_stable_s - 1e-9)
        self.paused[resumed] = False
        self.age[resumed] = self.recovered[resumed] = 0.
        self.halted |= active & (
            (self.paused & (self.age >= self.cfg.pause_limit_s - 1e-9))
            | (self.total_pause >= self.cfg.total_pause_limit_s - 1e-9))


def experiment_contract(base, experiment):
    # Distinct hashes stop experimental results from unlocking the old PPO gate.
    return dict(base, pull_experiment=dict(
        schema='teacher60_pull_speed_diagnostics_v1', comparison_only=True,
        settings=asdict(experiment), duration_s=experiment.duration_s,
        files={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in FILES}))


def paired_indices(report, metadata, bank_sha, count):
    expected = dict(mode='pull-probe', learning=False, physics_hz=60, policy_hz=20,
                    split='validation', probe_bank_sha256=bank_sha,
                    source_grasp_sha256=metadata['source_checkpoint_sha256'],
                    source_grasp_contract_sha256=metadata['source_contract_sha256'],
                    domain_stage=metadata['domain_stage'], physical_signature=metadata['physical_signature'])
    if any(report.get(k) != v for k, v in expected.items()):
        raise ValueError('Reference pull report differs from the bank/source/physics')
    rows = sorted(report['episodes'], key=lambda e: e['env_id'])
    indices = [e['bank_state_index'] for e in rows]
    if (len(rows) < 32 or [e['env_id'] for e in rows] != list(range(len(rows)))
            or any(type(i) is not int or not 0 <= i < count for i in indices)):
        raise ValueError('Reference must contain all original trials, including failures')
    return indices


def same_initial_states(first, second):
    keys = ('bank_state_indices', 'joint_q_rad', 'joint_velocity_rad_s',
            'joint_targets_rad', 'fruit_states_local', 'tcp_m')
    if any(first[k] != second[k] for k in keys):
        raise ValueError('Paired initial state/velocity/target differs')


def read_trace(path):
    traces = {}
    with Path(path).open() as stream:
        for line in stream:
            data = json.loads(line)
            for env_id, row in zip(data['env_ids'], data['rows']):
                traces.setdefault(env_id, []).append(dict(zip(data['columns'], row), time_s=data['time_s']))
    return traces


def summarize_case(path, indices, expected_experiment, expected_digest):
    path = Path(path)
    report = json.loads((path / 'probe.json').read_text())
    run = json.loads((path / 'run.json').read_text())
    initial = json.loads((path / 'initial_state.json').read_text())
    rows = sorted(report['episodes'], key=lambda e: e['env_id'])
    if (report.get('experiment') != asdict(expected_experiment)
            or report.get('followup_contract_sha256') != expected_digest
            or report.get('training_gate_eligible') is not False
            or report.get('comparison_only') is not True
            or not run.get('source_and_assets_still_match')
            or run.get('learning') is not False
            or abs(run.get('actual_physics_dt_s', 0) - 1/60) > 1e-12
            or abs(run.get('actual_policy_dt_s', 0) - .05) > 1e-12
            or report['maintenance']['gripper'] != 'bounded-preload'
            or report['maintenance']['handoff_arm'] != 'stored'
            or [e['env_id'] for e in rows] != list(range(len(indices)))
            or [e['bank_state_index'] for e in rows] != indices
            or initial['bank_state_indices'] != indices):
        raise ValueError('Incomplete or mismatched pull experiment')
    traces = read_trace(path / 'trace.jsonl')
    if set(traces) != set(range(len(indices))):
        raise ValueError('Missing paired trial trace')
    budget = report['maintenance']['preload_budget_rad']
    metrics = []
    for e in rows:
        i = e['env_id']; trace = traces[i]
        close = max(initial['joint_targets_rad'][i][-1] - r['gripper_target_rad'] for r in trace)
        if close > budget + 1e-6:
            raise ValueError('Bounded preload exceeded its closing budget')
        if e['passed'] and (e['failure'] or e['attached'] or not e['valid_detach'] or not e['retained'] or e['guard_halted'] or e['timed_out']):
            raise ValueError('Experiment counted a false successful trial')
        first = next((r for r in trace if not r['qualified_grasp'] or r['slip_m'] >= report['physical_signature']['max_slip']), None)
        metrics.append(dict(env_id=i, bank_state_index=indices[i], passed=e['passed'],
            first_unstable_s=None if first is None else first['time_s'],
            first_unstable_retreat_m=None if first is None else first['command_retreat_m'],
            first_unstable_fruit_rotation_deg=None if first is None else first['fruit_rotation_deg'],
            first_unstable_tcp_error_m=None if first is None else first['command_tcp_error_m'],
            max_tcp_error_m=max(r['command_tcp_error_m'] for r in trace),
            max_fruit_rotation_deg=max(r['fruit_rotation_deg'] for r in trace),
            max_arm_contact_N=max(r['arm_contact_peak_N'] for r in trace),
            max_additional_close_deg=math.degrees(close),
            max_command_retreat_m=max(r['command_retreat_m'] for r in trace),
            guard_halted=e['guard_halted'], pause_events=e['pause_events'],
            first_arm_collision=e['first_arm_collision'], reasons=e['reasons']))
    passed = sum(e['passed'] for e in rows)
    return dict(passed=passed, count=len(rows), fraction=passed / len(rows),
                provisional_pull_gate_met=passed / len(rows) >= .8,
                environment_failures=sum(e['failure'] for e in rows),
                environment_timeouts=sum(e['timed_out'] for e in rows),
                guard_stops=sum(e['guard_halted'] for e in rows),
                experiment=asdict(expected_experiment), duration_s=report['duration_s'],
                metrics=metrics, probe_report=str(path / 'probe.json')), initial
