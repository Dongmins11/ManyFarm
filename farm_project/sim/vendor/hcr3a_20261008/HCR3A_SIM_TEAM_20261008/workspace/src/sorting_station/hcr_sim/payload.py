"""Random, non-intersecting loading poses; gravity forms the actual cargo pile."""
import json
import numpy as np
from scipy.spatial.transform import Rotation
from .model import ROOT


def pepper_bounds(cfg):
    metadata = json.loads((ROOT / 'src/smartfarm_description/meshes/pepper/manifest.json').read_text())
    bounds = np.asarray(metadata['Pepper_Red']['bounds'])
    size = bounds[1] - bounds[0]
    scale = np.array([cfg['physics']['pepper_diameter'] / max(size[:2])] * 2
                     + [cfg['physics']['pepper_length'] / size[2]])
    return (bounds[0] + bounds[1]) * scale / 2, size * scale / 2


def boxes_separated(p, rotation, q, other_rotation, half, gap=.004):
    """Separating-axis test for oriented bounding boxes, including edge axes."""
    axes = np.concatenate((rotation.T, other_rotation.T,
        np.cross(rotation.T[:, None, :], other_rotation.T[None, :, :]).reshape(-1, 3)))
    axes = axes[np.linalg.norm(axes, axis=1) > 1e-8]
    axes /= np.linalg.norm(axes, axis=1)[:, None]
    radii = np.abs(axes @ rotation) @ half + np.abs(axes @ other_rotation) @ half
    return bool(np.any(np.abs(axes @ (p - q)) > radii + gap))


def random_payload_poses(cfg, count, geometry):
    """Scatter above the open cargo box without overlaps, then let PhysX settle."""
    if not 0 <= count <= 8:
        raise ValueError('Random cargo loading supports 0 to 8 peppers')
    center, half = pepper_bounds(cfg)
    g = geometry
    c = g['config']
    rng = np.random.default_rng(int(cfg['transport'].get('payload_seed', 43)))
    wall, margin = c['wall_thickness'], .008
    # All initial bodies are above the original top mechanism. No body begins
    # inside another fruit or cargo wall. XY projections stay over the opening.
    lower = np.array([-c['box_length'] + wall, -c['box_width']/2 + wall, c['box_height'] + .03])
    upper = np.array([-wall, c['box_width']/2 - wall, c['box_height'] + .61])
    for _ in range(10):
        placed = []
        for _ in range(1000):
            if len(placed) == count:
                break
            rotation = Rotation.random(random_state=rng).as_matrix()
            extent = np.abs(rotation) @ half
            lo, hi = lower + extent + margin, upper - extent - margin
            if np.any(lo >= hi):
                raise ValueError('Fruit is too large for the original box opening')
            point = rng.uniform(lo, hi)
            if all(boxes_separated(point, rotation, q, other, half) for q, other in placed):
                placed.append((point, rotation))
        if len(placed) == count:
            break
    else:
        raise ValueError('Could not generate non-intersecting random loading poses')
    yaw = np.diag([-1., -1., 1.])
    axis = np.array([cfg['transport']['start_front_x'], 0., g['cargo_zero'][2]])
    poses = []
    for point, rotation in placed:
        world_rotation = yaw @ rotation
        quat = Rotation.from_matrix(world_rotation).as_quat()
        poses.append(dict(position=(axis + yaw @ (point - rotation @ center)).tolist(),
                          rotation_wxyz=quat[[3, 0, 1, 2]].tolist()))
    return poses
