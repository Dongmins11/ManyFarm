"""Explicit physics-clock transfer without changing policy time or old defaults."""
import copy
import json
import math
from pathlib import Path


def load_profile(path):
    profile = json.loads(Path(path).read_text())
    if profile.get('schema') != 1 or profile.get('policy_hz') != 20:
        raise ValueError('Physics profile requires schema1 and the existing 20Hz policy')
    values = clock_values(profile['physics_hz'], profile['policy_hz'])
    expected = dict(physics_dt_s=values['physics_dt'],
                    decimation=values['decimation'], contact_substeps=1)
    for name, value in expected.items():
        if name in profile and profile[name] != value:
            raise ValueError(f'Physics profile {name} conflicts with its requested clock')
    from .simulation_clock import render_interval
    render_hz = profile.get('render_hz', 0)
    if type(render_hz) is not int or render_hz < 0:
        raise ValueError('Rendering frequency must be a nonnegative integer')
    render_interval(values['physics_dt'], values['decimation'], render_hz)
    if 'stem_response_version' in profile:
        if (profile['stem_response_version'] != 6 or profile['physics_hz'] != 60
                or profile.get('attachment_model') != 'coupled_point_orientation_v6'):
            raise ValueError('Only the explicit response6/60Hz coupled connector profile is supported')
    return profile


def clock_values(physics_hz, policy_hz=20):
    if type(physics_hz) is not int or physics_hz not in (60, 120, 240, 480):
        raise ValueError('Supported physics frequencies: 60,120,240,480Hz')
    if policy_hz != 20 or physics_hz % policy_hz:
        raise ValueError('Keep the original 20Hz policy with integer decimation')
    return dict(physics_dt=1/physics_hz, decimation=physics_hz//policy_hz,
                contact_substeps=1)


def apply_clock(settings, physics_hz, render_hz=0):
    """Return a new settings object; no hidden 480Hz substeps at 60Hz."""
    result = copy.deepcopy(settings)
    for key, value in clock_values(physics_hz).items():
        setattr(result, key, value)
    result.render_hz = render_hz
    result.validate()
    if not math.isclose(result.physics_dt*result.decimation, .05, abs_tol=1e-12):
        raise ValueError('Clock transfer changed the policy timestep')
    return result
