"""Explicit behavior requirements; configuring these does not train policy weights."""
import math


def apply_behavior_mode(settings,mode):
    if mode=='checkpoint':return
    if mode not in ('strict','horizontal'):raise ValueError('Unknown behavior mode')
    settings.grasp_orientation='horizontal'
    settings.grasp_version=max(2,settings.grasp_version)
    settings.grasp_angle_tolerance=min(settings.grasp_angle_tolerance,math.radians(25))
    if mode=='horizontal':return
    settings.reward_version=max(7,settings.reward_version)
    settings.release_stop_s=max(.3,settings.release_stop_s)
    settings.release_speed=min(.05,settings.release_speed)
    settings.box_bottom_contact_tolerance=.010


def apply_gentle_hook(settings):
    """Provisional dissipative hook, not measured demonstration hardware."""
    settings.attachment_version=4
    settings.stem_response_version=4
    settings.break_force=2.5
    settings.spring_k=120.
    settings.spring_d=4.2
    settings.tension_hold_s=.12
    settings.valid_pull_distance=.012
    settings.stem_vertical_stiffness=80.
    settings.lateral_stiffness_ratio=.25
    settings.stem_max_extension=.08


def apply_short_hook(settings):
    """Opt-in finite-travel hook approximation, NOT measured twist-tie mechanics."""
    apply_gentle_hook(settings)
    settings.stem_response_version=5
    settings.spring_k=60.
    settings.stem_vertical_stiffness=40.
    settings.tension_hold_s=.04
    settings.stem_max_extension=.04


def prepare_harvest_transfer(settings):
    """Preserve checkpoint physics and grasp controller; switch task explicitly."""
    if settings.task not in ('pull','harvest','transport','place') or settings.attachment_version!=4 or settings.stem_response_version not in (4,5):
        raise ValueError('Harvest transfer requires attachment4/response4 or5 pull/harvest checkpoint')
    settings.task='harvest'
    settings.reward_version=8
    settings.stage_transfer=True
    settings.pull_progress_reward=False
    settings.pull_recovery_shaping=False
    apply_behavior_mode(settings,'strict')
