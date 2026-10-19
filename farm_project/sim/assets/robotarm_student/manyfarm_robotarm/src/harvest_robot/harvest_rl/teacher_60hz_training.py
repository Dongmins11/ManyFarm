"""Fresh grasp-stage settings; never imports Isaac or loads an old checkpoint."""
from .physics_profile import apply_clock
from .settings import TaskSettings


def fresh_grasp_settings(source, seed=42, render_hz=30):
    if source['robot_source'] != 'current' or source['task']['mass'] != .009:
        raise ValueError('Fresh 60Hz training requires the current robot and 9g source')
    cfg = apply_clock(TaskSettings(**source['task']), 60, render_hz)
    if cfg.attachment_version != 4:
        raise ValueError('Response6 requires an attachment4 source')
    cfg.task = 'grasp'
    cfg.reward_version = 3
    cfg.num_fruits = 1
    cfg.sequence = False
    cfg.target_mode = 'nearest'
    cfg.random_colors = False
    cfg.pregrasp_fraction = 0.
    cfg.curriculum = 0.
    cfg.workspace_split = 'train'
    cfg.seed = seed
    cfg.start_bank = ''
    cfg.transport_replay_fraction = 0.
    cfg.transport_start_min = cfg.transport_start_max = 0.
    cfg.grasp_orientation = 'horizontal'
    cfg.grasp_version = 2
    cfg.entry_first_grasp = True
    cfg.entry_capture_shaping = True
    cfg.stage_transfer = True
    # Validate all ordinary task constraints without loading simulator modules.
    # Response6 itself is validated by its explicit runtime adapter after launch.
    cfg.stem_response_version = 5
    cfg.validate()
    cfg.stem_response_version = 6
    return cfg


def domain_grasp_settings(source, seed=42, render_hz=30, split='train'):
    cfg = fresh_grasp_settings(source, seed, render_hz)
    # Two actual color assets; only one is placed in the working area at reset.
    # The spare stays outside the arm path. No visual recoloring of Red geometry.
    cfg.num_fruits = 2
    cfg.workspace_split = split
    return cfg
