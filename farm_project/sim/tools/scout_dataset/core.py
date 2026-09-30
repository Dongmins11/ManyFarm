"""Geometry, instance filtering, polygon export and RGB-only degradation.

No Isaac imports: these functions can be verified on a CPU. All geometry is
in world metres. Images are RGB uint8; cv2 BGR is used only at codec boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import numpy as np


@dataclass(frozen=True)
class Fruit:
    path: str
    bed_path: str
    physical_bed: int
    color: str

    @property
    def class_id(self):
        return {"red": 0, "yellow": 1}[self.color]


@dataclass
class BedGeometry:
    physical_bed: int
    bed_path: str
    center_xy: np.ndarray
    tangent_xy: np.ndarray
    normal_xy: np.ndarray
    half_length_m: float
    half_width_m: float
    edge_paths: list[str]

    def sample_pose(self, side, rng, distance, height, pitch_deg=0.0,
                    yaw_jitter_deg=0.0, margin=0.0):
        """Camera optical centre at exact perpendicular edge distance.

        The entire bed length is a continuous sampling interval. There are no
        route nodes, segments or snapping operations in this calculation.
        """
        if side not in ("west", "east"):
            raise ValueError(f"Unknown survey_side: {side}")
        if distance <= 0 or not 0 <= margin < self.half_length_m:
            raise ValueError("Invalid edge distance or bed-end margin")
        sign = -1.0 if side == "west" else 1.0
        along = float(rng.uniform(-self.half_length_m + margin,
                                  self.half_length_m - margin))
        outward = sign * self.normal_xy
        xy = self.center_xy + along*self.tangent_xy + outward*(self.half_width_m + distance)
        yaw = math.radians(float(rng.uniform(-yaw_jitter_deg, yaw_jitter_deg)))
        inward = -outward
        rotation = np.array([[math.cos(yaw), -math.sin(yaw)],
                             [math.sin(yaw), math.cos(yaw)]])
        horizontal = rotation @ inward
        pitch = math.radians(pitch_deg)
        forward = np.array([*(horizontal * math.cos(pitch)), math.sin(pitch)])
        position = np.array([*xy, height])
        actual = float(np.dot(xy-self.center_xy, outward)-self.half_width_m)
        if not math.isclose(actual, distance, abs_tol=1e-8):
            raise AssertionError("Camera-to-edge distance mismatch")
        return {"position_world_m": position.tolist(),
                "forward_world": forward.tolist(), "along_m": along,
                "edge_distance_m": actual, "side": side,
                "pitch_deg": pitch_deg, "yaw_jitter_deg": math.degrees(yaw)}


def bed_geometry_from_points(number, path, points_xy, edge_paths):
    points = np.asarray(points_xy, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError("Invalid Bed_Edge vertices")
    # Oriented basis from long frame edges, not from foliage/fruit extents.
    values, vectors = np.linalg.eigh(np.cov(points.T))
    tangent = vectors[:, int(np.argmax(values))]
    major = int(np.argmax(np.abs(tangent)))
    if tangent[major] < 0:
        tangent = -tangent
    normal = np.array([tangent[1], -tangent[0]])
    if normal[0] < 0:
        normal = -normal
    ts, ns = points @ tangent, points @ normal
    length, width = float(np.ptp(ts)), float(np.ptp(ns))
    if length <= 1 or not 0.1 < width < length/2:
        raise ValueError(f"Unexpected Bed_Edge bounds: {length=}, {width=}")
    center = ((ts.min()+ts.max())/2)*tangent + ((ns.min()+ns.max())/2)*normal
    return BedGeometry(number, path, center, tangent, normal,
                       length/2, width/2, edge_paths)


def usd_camera_matrix(position, forward):
    """Column-vector transform: USD camera +X right, +Y up, -Z forward."""
    f = np.asarray(forward, float)
    f /= np.linalg.norm(f)
    right = np.cross(f, [0., 0., 1.])
    if np.linalg.norm(right) < 1e-8:
        raise ValueError("Camera forward is vertical")
    right /= np.linalg.norm(right)
    up = np.cross(right, f)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((right, up, -f))
    matrix[:3, 3] = position
    return matrix


def fruit_ancestor(path, fruits):
    # Exact path components avoid Bed_02/Bed_020 or Pepper_1/Pepper_10 collisions.
    if not isinstance(path, str) or not path.startswith("/"):
        return None
    while path and path != "/":
        if path in fruits:
            return fruits[path]
        path = path.rsplit("/", 1)[0]
    return None


def classify_fruit_side(position_world, bed, tolerance_m=1e-4):
    """Assign the whole fruit by its world placement relative to bed centreline."""
    offset = float(np.dot(np.asarray(position_world, float)[:2]-bed.center_xy, bed.normal_xy))
    if not np.isfinite(offset) or abs(offset) <= tolerance_m:
        raise ValueError("Fruit lies on the bed centreline; side assignment is ambiguous")
    return "west" if offset < 0 else "east"


def select_target_instances(payload, fruits, target_bed_path, target_side, fruit_membership):
    """Union submeshes by fruit; accept only the requested physical bed AND side.

    Semantically-labelled instance masks already contain only visible pixels;
    geometry hidden behind leaves is never projected as a filled silhouette.
    """
    if target_side not in ("west", "east"):
        raise ValueError("A target survey side is required")
    data = np.asarray(payload["data"])
    if data.ndim == 3 and data.shape[2] == 1:
        data = data[..., 0]
    if data.ndim != 2 or data.dtype.kind not in "ui":
        raise ValueError("Expected non-colorized integer instance segmentation")
    labels = payload.get("info", {}).get("idToLabels")
    if labels is None:
        raise RuntimeError("Annotator did not return instance-ID to prim-path mapping")
    visible_ids, counts = np.unique(data, return_counts=True)
    groups, excluded, opposite, unmatched = {}, {}, {}, []
    for instance_id, count in zip(visible_ids.tolist(), counts.tolist()):
        path = labels.get(str(instance_id), labels.get(instance_id))
        if instance_id in (0, 1) and path in (None, "BACKGROUND", "UNLABELLED"):
            continue
        if isinstance(path, dict):
            path = path.get("primPath", path.get("path"))
        fruit = fruit_ancestor(path, fruits)
        if fruit is None:
            # An unresolved Pepper path means we cannot safely trust the output.
            if isinstance(path, str) and re.search(r"/Pepper_\d+_(red|yellow)(/|$)", path):
                raise RuntimeError(f"Visible fruit absent from scene inventory: {path}")
            unmatched.append(str(path))
            continue
        if fruit.bed_path != target_bed_path:
            excluded[fruit.path] = excluded.get(fruit.path, 0)+count
            continue
        member = fruit_membership.get(fruit.path)
        if not member or member.get("side") not in ("west", "east"):
            raise RuntimeError(f"Missing survey-side membership: {fruit.path}")
        if member["side"] != target_side:
            opposite[fruit.path] = opposite.get(fruit.path, 0)+count
            continue
        groups.setdefault(fruit.path, []).append(instance_id)
    selected = [(fruits[path], np.isin(data, ids), ids)
                for path, ids in sorted(groups.items())]
    return selected, {"excluded_other_bed_fruits": len(excluded),
                      "excluded_other_bed_pixels": sum(excluded.values()),
                      "excluded_prim_paths": sorted(excluded),
                      "excluded_opposite_side_fruits": len(opposite),
                      "excluded_opposite_side_pixels": sum(opposite.values()),
                      "excluded_opposite_side_prim_paths": sorted(opposite),
                      "other_instance_count": len(unmatched)}


def mask_to_polygon(mask, epsilon=0.25):
    """One YOLO row per fruit, including disconnected visible fragments.

    Closed contour tours (including holes) are joined by a zero-width outbound
    and return bridge. A convex hull would label occluding leaves incorrectly.
    Exact raster GT is saved separately because TXT polygons are approximate.
    """
    import cv2
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_TREE,
                                   cv2.CHAIN_APPROX_SIMPLE)
    rings = []
    for contour in contours:
        if len(contour) < 3 or abs(cv2.contourArea(contour)) < .5:
            continue
        approx = cv2.approxPolyDP(contour, epsilon, True) if epsilon else contour
        if len(approx) < 3:
            approx = contour
        rings.append(approx[:, 0].astype(np.float64))
    if not rings:
        return None
    rings.sort(key=lambda x: abs(cv2.contourArea(x.astype(np.float32))), reverse=True)
    polygon = rings.pop(0)
    while rings:
        best = None
        for k, ring in enumerate(rings):
            distances = ((polygon[:, None, :]-ring[None, :, :])**2).sum(axis=2)
            i, j = np.unravel_index(np.argmin(distances), distances.shape)
            candidate = (distances[i, j], k, i, j)
            if best is None or candidate[0] < best[0]:
                best = candidate
        _, k, i, j = best
        ring = rings.pop(k)
        tour = np.concatenate((ring[j:], ring[:j+1]))
        polygon = np.concatenate((polygon[:i+1], tour, polygon[i:i+1], polygon[i+1:]))
    return polygon


def make_labels(selected, min_pixels=8, epsilon=.25):
    lines, objects, masks = [], [], []
    dropped = []
    for fruit, mask, instance_ids in selected:
        pixels = int(np.count_nonzero(mask))
        polygon = mask_to_polygon(mask, epsilon) if pixels >= min_pixels else None
        if polygon is None:
            dropped.append({"prim_path": fruit.path, "visible_pixels": pixels,
                            "reason": "tiny_or_degenerate_visible_region"})
            continue
        h, w = mask.shape
        normalized = np.clip(polygon / np.array([w, h]), 0., 1.)
        lines.append(str(fruit.class_id)+" "+" ".join(f"{v:.8f}" for v in normalized.ravel()))
        ys, xs = np.nonzero(mask)
        objects.append({"class_id": fruit.class_id, "class_name": fruit.color.capitalize(),
                        "prim_path": fruit.path, "bed_prim": fruit.bed_path,
                        "physical_bed": fruit.physical_bed, "visible_pixels": pixels,
                        "instance_ids_this_frame": instance_ids,
                        "gt_mask_value": len(objects)+1,
                        "bbox_xyxy_px": [int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)],
                        "polygon_xy_px": polygon.tolist()})
        masks.append(mask)
    return lines, objects, masks, dropped


def postprocess_rgb(rgb, config, rng):
    """Approximate sensor/ISP variation; no geometric warps or label transforms."""
    import cv2
    rgb = np.asarray(rgb)
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Postprocess expects HxWx3 RGB uint8")
    if not config.get("enabled", True):
        return rgb.copy(), {"enabled": False}
    sample = lambda key: float(rng.uniform(*config[key]))
    strong = bool(rng.random() < config["strong_blur_probability"])
    sigma = sample("strong_gaussian_sigma_px" if strong else "gaussian_sigma_px")
    # Parameters are defined at 1280px width; scale PSF if a different resolution is used.
    sigma *= rgb.shape[1]/1280
    a = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), max(sigma, .05))
    motion = bool(rng.random() < config["motion_blur_probability"])
    angle = None
    if motion:
        size = max(3, int(round(config["motion_kernel_px"]*rgb.shape[1]/1280)) | 1)
        angle = float(rng.uniform(0, 180))
        kernel = np.zeros((size, size), np.float32)
        kernel[size//2, :] = 1
        transform = cv2.getRotationMatrix2D(((size-1)/2, (size-1)/2), angle, 1.)
        kernel = cv2.warpAffine(kernel, transform, (size, size))
        kernel /= kernel.sum()
        a = cv2.filter2D(a, -1, kernel)
    gain, gamma = sample("gain"), sample("gamma")
    a = 255*np.power(np.clip(a*gain/255, 0, 1), gamma)
    read_sigma, signal_sigma, chroma_sigma = (sample(k) for k in (
        "read_noise_sigma_8bit", "signal_noise_sigma_8bit", "chroma_noise_sigma_8bit"))
    luminance = np.mean(a, axis=2, keepdims=True)/255
    noise_sigma = np.sqrt(read_sigma**2 + signal_sigma**2*luminance)
    a += rng.normal(0, 1, (*a.shape[:2], 1)).astype(np.float32)*noise_sigma
    a += rng.normal(0, chroma_sigma, a.shape).astype(np.float32)
    out = np.clip(np.rint(a), 0, 255).astype(np.uint8)
    quality = None
    if rng.random() < config["jpeg_probability"]:
        quality = int(rng.integers(config["jpeg_quality"][0], config["jpeg_quality"][1]+1))
        ok, encoded = cv2.imencode(".jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR),
                                  [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("JPEG augmentation failed")
        out = cv2.cvtColor(cv2.imdecode(encoded, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return out, {"enabled": True, "gaussian_sigma_px": sigma,
                 "strong_blur": strong, "motion_angle_deg": angle,
                 "read_noise_sigma_8bit": read_sigma,
                 "signal_noise_sigma_8bit": signal_sigma,
                 "chroma_noise_sigma_8bit": chroma_sigma, "gain": gain,
                 "gamma": gamma, "jpeg_quality": quality,
                 "calibration": "visual_reference_preset_not_measured_camera_model"}


def label_overlay(rgb, objects, masks):
    import cv2
    out = rgb.copy()
    for obj, mask in zip(objects, masks):
        color = np.array([255, 65, 65] if obj["class_id"] == 0 else [255, 220, 30])
        out[mask] = (.68*out[mask]+.32*color).astype(np.uint8)
        polygon = np.rint(obj["polygon_xy_px"]).astype(np.int32)
        cv2.polylines(out, [polygon], True, tuple(int(x) for x in color), 1)
        x, y = obj["bbox_xyxy_px"][:2]
        cv2.putText(out, f'{obj["class_name"]} {obj["gt_mask_value"]}',
                    (x, max(14, y-4)), cv2.FONT_HERSHEY_SIMPLEX, .45,
                    tuple(int(x) for x in color), 1, cv2.LINE_AA)
    return out
