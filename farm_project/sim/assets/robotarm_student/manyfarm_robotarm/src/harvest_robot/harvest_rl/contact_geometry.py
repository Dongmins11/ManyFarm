"""Body-only collider experiment for the shipped Pepper mesh, in SI units."""
import numpy as np
from scipy.spatial import ConvexHull


def pepper_body_hull(points, length):
    """Keep the measured outer body envelope; cap the narrow top stem region.

    The shipped 75mm asset has broad body up to about z=31.9mm and a
    narrow stem above it. This is an asset-specific cut, not a universal
    pepper segmentation algorithm. Visuals and the attachment point stay intact.
    """
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all() or length <= 0:
        raise ValueError('Invalid pepper mesh')
    body = points[points[:, 2] <= .425 * length]
    if len(body) < 4:
        raise ValueError('No usable body below stem cut')
    # Guard against silently fitting a different asset or a too-small proxy.
    if np.any(np.ptp(body[:, :2], axis=0) < .95 * np.ptp(points[:, :2], axis=0)):
        raise ValueError('Stem cut removed the body width; review asset')
    hull = ConvexHull(body)
    vertices = body[hull.vertices]
    index = {old: new for new, old in enumerate(hull.vertices)}
    faces = []
    for face, equation in zip(hull.simplices, hull.equations):
        a, b, c = body[face]
        if np.dot(np.cross(b-a, c-a), equation[:3]) < 0:
            face = face[[0, 2, 1]]
        faces.append([index[int(i)] for i in face])
    return vertices, np.asarray(faces, dtype=np.int32)
