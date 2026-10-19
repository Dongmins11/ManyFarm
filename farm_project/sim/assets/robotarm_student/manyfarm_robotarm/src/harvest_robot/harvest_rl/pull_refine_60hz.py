"""Separate pull-policy transfer and bounded arm ramp. Original ready v1 stays frozen."""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from .pull_ready_60hz import make_contract as parent_contract, prepare_actions as parent_actions
from .grasp_handoff_60hz import contract_digest
from .teacher_asset_reference import sha

ROOT = Path(__file__).resolve().parents[3]
FILES = ['scripts/teacher_60hz_pull_refine.py',
         'src/harvest_robot/harvest_rl/pull_refine_60hz.py',
         'scripts/compare_teacher60_pull_policy.py']


@dataclass(frozen=True)
class PullRefinement:
    ramp_s: float = 0.
    initial_scale: float = .2
    hold_after_detach: bool = False

    def __post_init__(self):
        if not math.isfinite(self.ramp_s) or self.ramp_s < 0:
            raise ValueError('Ramp duration must be finite and nonnegative')
        if not math.isfinite(self.initial_scale) or not 0 < self.initial_scale <= 1:
            raise ValueError('Initial arm scale must be in (0, 1]')


def prepare_actions(actions, elapsed, confirmed, release_intent, attached, valid_detach, spec):
    """Modify commands only; keep loaded targets, real contact and failure criteria.

    Ramp is applied to bounded actions so a saturated proposal cannot defeat it.
    Ramp=0, hold=False is byte-for-byte the original ready action computation.
    Zero arm command maintains the existing target, never measured joint rebasing.
    """
    result = parent_actions(actions, elapsed, confirmed, release_intent)
    scope = confirmed & ~release_intent
    scale = elapsed.new_ones(elapsed.shape)
    if spec.ramp_s:
        fraction = ((elapsed - 2.) / spec.ramp_s).clamp(0., 1.)
        scale = spec.initial_scale + (1. - spec.initial_scale) * fraction
        ramping = scope & (elapsed >= 2. - 1e-7) & (elapsed < 2. + spec.ramp_s)
        result[ramping, :5] = result[ramping, :5].clamp(-1., 1.) * scale[ramping, None]
    holding = scope & valid_detach & ~attached if spec.hold_after_detach else scope & False
    result[holding, :5] = 0.
    return result, scale, holding


def make_contract(metadata, spec):
    parent = parent_contract(metadata)
    return dict(schema='teacher60_pull_refine_v1', parent=parent,
                parent_contract_sha256=contract_digest(parent), refinement=asdict(spec),
                action_semantics='arm5 bounded ramp after2s; neutral jaw; release intent priority; optional loaded-target hold after valid physical detachment',
                files={p: sha(ROOT / p) for p in FILES})


def validate_assignments(selection, payload, bank_sha, episodes):
    values = selection.get('indices', [])
    if (selection.get('bank_sha256') != bank_sha or len(values) != episodes
            or any(type(i) is not int or not 0 <= i < len(payload['states']['q']) for i in values)):
        raise ValueError('Assignment must contain every paired trial and match the bank SHA256')
    return values


def evaluation_assignments(episodes, payload):
    """Recover the old evaluation's exact bank states from recorded domain samples."""
    samples = payload['states']['domain_samples'].cpu().tolist()
    result = []
    for row in episodes:
        expected = [row['bank_point_id'], row['tilt_deg'], row['yaw_deg'],
                    row['home_distance_m'], 0 if row['color'] == 'Red' else 1, row['stage']]
        candidates = [i for i, s in enumerate(samples)
                      if len(s) == len(expected) and all(abs(a - b) <= 1e-5 for a, b in zip(s, expected))]
        if len(candidates) != 1:
            raise ValueError(f'Old trial cannot be uniquely matched to the bank: {expected}')
        result.append(candidates[0])
    return result


def verify_selection(path, metadata):
    """A comparison certificate supplements, never replaces, the physical parent gate."""
    report = json.loads(Path(path).read_text())
    if (report.get('schema') != 'teacher60_pull_policy_comparison_v1'
            or report.get('completed') is not True or report.get('same_initial_states') is not True
            or report.get('count', 0) < 64):
        raise ValueError('Incomplete paired comparison; supplemental training is not ready')
    selected = report['selected']
    spec = PullRefinement(**selected['refinement'])
    expected = contract_digest(make_contract(metadata, spec))
    run_path = Path(selected['directory']) / 'run.json'
    run = json.loads(run_path.read_text())
    if (run.get('source_and_assets_still_match') is not True or run.get('learning') is not False
            or selected['contract_sha256'] != expected
            or run['followup_contract_sha256'] != expected
            or sha(selected['checkpoint']) != selected['checkpoint_sha256']
            or selected['count'] != report['count'] or selected['success'] < report['baseline_success']):
        raise ValueError('Selected checkpoint/source/controller changed or regresses the paired baseline')
    for case in report['cases']:
        if sha(Path(case['directory']) / 'evaluation.json') != case['evaluation_sha256']:
            raise ValueError('Comparison evidence changed')
    return report, spec
