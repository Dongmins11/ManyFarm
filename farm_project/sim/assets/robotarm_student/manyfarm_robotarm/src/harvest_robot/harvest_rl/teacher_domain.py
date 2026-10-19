"""Reset-only Teacher domain math. No simulator import or global RNG mutation."""
import json
import math
from pathlib import Path
import torch


def load_domain(path):
    domain = json.loads(Path(path).read_text())
    if (domain['schema'] != 1 or domain['task'] != 'grasp' or domain['mass_kg'] != .009
            or domain['geometry'] != 'v1' or domain['visual_scene'] != 'greenhouse_v1'
            or domain['colors'] != ['Red', 'Yellow']
            or domain['yaw_deg'] != [-180, 180]
            or domain['observation_contract'] != 'teacher82_single_target_canonical_quaternion_v1'):
        raise ValueError('Unsupported Teacher domain contract')
    if not 0 <= domain['nominal_pose_fraction'] <= domain['upright_fraction'] < 1:
        raise ValueError('Nominal pose fraction must be part of the upright replay')
    if not 0 <= domain['edge_tilt_fraction'] <= 1:
        raise ValueError('Invalid edge tilt fraction')
    if not 0 <= domain['home_arm_jitter_rad'] <= .02 or domain['position_jitter_m'] != 0:
        raise ValueError('Only small HOME jitter and unmodified reachable bank positions are supported')
    if not 0 < domain['promotion_success_rate'] <= 1:
        raise ValueError('Invalid promotion rate')
    if not 1 <= domain['promotion_min_episodes'] <= domain['recent_window']:
        raise ValueError('Invalid promotion window')
    previous = (-1, -1., -1.)
    for stage in domain['stages']:
        values = (stage['earliest_iteration'], stage['max_tilt_deg'], stage['max_home_distance_m'])
        if (values[0] <= previous[0] or not 0 <= values[1] <= 30
                or values[1] < previous[1] or values[2] < previous[2]
                or not domain['minimum_home_distance_m'] < values[2] <= .34):
            raise ValueError('Invalid monotone curriculum')
        previous = values
    if not domain['stages'] or domain['stages'][0]['earliest_iteration'] != 0:
        raise ValueError('Curriculum must start at iteration zero')
    return domain


def canonical_quaternion(q):
    norm = torch.linalg.vector_norm(q, dim=-1, keepdim=True)
    if bool((norm < 1e-8).any()):
        raise ValueError('Zero quaternion')
    q = q / norm
    # q and -q represent the same rotation, including exact 180-degree cases.
    largest = q.gather(-1, q.abs().argmax(-1, keepdim=True))
    pivot = torch.where(q[..., :1] != 0, q[..., :1], largest)
    return q * torch.where(pivot < 0, -1., 1.)


def multiply_quaternion(a, b):
    aw, av = a[..., :1], a[..., 1:]
    bw, bv = b[..., :1], b[..., 1:]
    return torch.cat((aw*bw-(av*bv).sum(-1, keepdim=True),
                      aw*bv+bw*av+torch.linalg.cross(av, bv)), -1)


def rotate(q, vector):
    uv = torch.linalg.cross(q[..., 1:], vector)
    return vector + 2*(q[..., :1]*uv + torch.linalg.cross(q[..., 1:], uv))


def sample_pose(count, domain, stage, generator, device):
    u = torch.rand((count, 5), generator=generator, device=device)
    cap = math.radians(domain['stages'][stage]['max_tilt_deg'])
    tilt = torch.acos(1-u[:, 0]*(1-math.cos(cap)))
    tilt = torch.where(u[:, 1] < domain['edge_tilt_fraction'], cap*(.9+.1*u[:, 0]), tilt)
    tilt = torch.where(u[:, 2] < domain['upright_fraction'], 0., tilt)
    yaw = (2*u[:, 3]-1)*math.pi
    yaw = torch.where(u[:, 2] < domain['nominal_pose_fraction'], 0., yaw)
    azimuth = u[:, 4]*2*math.pi
    zero = torch.zeros_like(tilt)
    tilt_q = torch.stack((torch.cos(tilt/2), torch.sin(tilt/2)*torch.cos(azimuth),
                          torch.sin(tilt/2)*torch.sin(azimuth), zero), -1)
    yaw_q = torch.stack((torch.cos(yaw/2), zero, zero, torch.sin(yaw/2)), -1)
    return canonical_quaternion(multiply_quaternion(tilt_q, yaw_q)), tilt, yaw


def reset_geometry(nominal_root, quaternion, body_center_offset, local_tip):
    """Rotate about the grasp/body center, then attach at the rotated actual tip."""
    center = nominal_root + body_center_offset
    root = center - rotate(quaternion, body_center_offset.expand_as(nominal_root))
    anchor = root + rotate(quaternion, local_tip.expand_as(nominal_root))
    return root, anchor


def promote_stage(domain, stage, iteration, count, success_rate):
    if (stage+1 < len(domain['stages'])
            and iteration >= domain['stages'][stage+1]['earliest_iteration']
            and count >= domain['promotion_min_episodes']
            and success_rate >= domain['promotion_success_rate']):
        return stage+1
    return stage
