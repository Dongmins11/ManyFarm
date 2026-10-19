"""Isolated extension of the frozen speed probe, with separate provenance."""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .contact_maintenance_60hz import ContactMaintenance, feedback_from_env
from .contact_points_60hz import RECORDING, recording_views, capture_contact_points, point_summary
from .pull_speed_comparison import experiment_contract

ROOT = Path(__file__).resolve().parents[3]
FILES = ['src/harvest_robot/harvest_rl/contact_maintenance_60hz.py',
         'src/harvest_robot/harvest_rl/contact_points_60hz.py',
         'src/harvest_robot/harvest_rl/contact_maintenance_experiment.py',
         'scripts/teacher60_contact_case.py', 'scripts/compare_teacher60_contact.py',
         'scripts/compare_teacher60_contact.sh']


def contract(base, experiment, cfg):
    return dict(experiment_contract(base, experiment), contact_maintenance_experiment=dict(
        schema='teacher60_contact_maintenance_v2', comparison_only=True,
        training_gate_eligible=False, settings=asdict(cfg),
        contact_sampling='Separate read-only PhysX view; last substep of each 20Hz observation; pre-reset.',
        contact_recording=RECORDING.copy(),
        files={f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}))


@contextmanager
def installed(experiment, cfg):
    """Child-process-only hooks; every original object is restored on exit."""
    from . import bounded_grip_60hz, followup_60hz, followup_60hz_probe, pull_speed_probe
    original = (bounded_grip_60hz.BoundedGripPreload, followup_60hz.make_contract,
                followup_60hz_probe.probe, pull_speed_probe.capture_diagnostics)
    bound = {}

    class Controller(ContactMaintenance):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, cfg=cfg, feedback=lambda: feedback_from_env(bound['env']))

    def probe(env, wrapped, mode, duration, out, metadata, seed):
        bound['env'] = env
        views, point_metadata = recording_views(env)
        (out/'contact_points_metadata.json').write_text(json.dumps(point_metadata, indent=2)+'\n')
        print('CONTACT_POINTS_READY', {name: data['recording_buffer_capacity']
            for name, data in point_metadata['jaws'].items()}, 'control sensors unchanged', flush=True)
        finished = set()
        warned = set()
        ticks = 0
        with (out/'contact_points.jsonl').open('x') as stream:
            def capture(current, fruit_reference, tcp_reference):
                nonlocal ticks
                result = original[3](current, fruit_reference, tcp_reference)
                # Raw buffer reads precede Isaac's auto-reset. Never change ContactSensorCfg.
                contacts = capture_contact_points(current, views)
                for name, rows in contacts.items():
                    if name not in warned and any(not r['data_complete'] for r in rows):
                        print('CONTACT_POINTS_INCOMPLETE', name,
                            'diagnostic frame unavailable; aggregate control continues', flush=True)
                        warned.add(name)
                result.update(point_summary(current, contacts))
                controller = current.followup_preload
                result.update(maintenance_extra_budget_rad=controller.extra.clone(),
                              maintenance_adjusting=controller.adjusting.clone(),
                              maintenance_weak_age_s=controller.weak_age.clone())
                ticks += 1
                snap = current.followup_snapshot
                active = [i for i in range(current.num_envs) if i not in finished]
                stream.write(json.dumps(dict(time_s=ticks*current.step_dt, env_ids=active,
                    bank_state_indices=[int(snap['bank_indices'][i]) for i in active],
                    rows=[{name: data[i] for name, data in contacts.items()} for i in active]), allow_nan=False)+'\n')
                if ticks % 5 == 0: stream.flush()
                finished.update(i for i in active if bool(snap['success'][i] or snap['failure'][i]))
                return result
            pull_speed_probe.capture_diagnostics = capture
            try:
                report = pull_speed_probe.probe(env, wrapped, mode, duration, out, metadata, seed, experiment=experiment)
                report['contact_maintenance'] = asdict(cfg)
                report['contact_points_report'] = str(out/'contact_points.jsonl')
                report['contact_recording'] = point_metadata
                (out/'probe.json').write_text(json.dumps(report, indent=2)+'\n')
                return report
            finally:
                pull_speed_probe.capture_diagnostics = original[3]

    bounded_grip_60hz.BoundedGripPreload = Controller
    followup_60hz.make_contract = lambda *args, **kwargs: contract(original[1](*args, **kwargs), experiment, cfg)
    followup_60hz_probe.probe = probe
    try:
        yield
    finally:
        (bounded_grip_60hz.BoundedGripPreload, followup_60hz.make_contract,
         followup_60hz_probe.probe, pull_speed_probe.capture_diagnostics) = original
