"""Offline measured calibration. No ROS, simulator truth or actuator writes.

T_A_B maps coordinates in B into A. 'base' is arm_2/base_link;
'gripper' is arm_2/gripper_link, NOT tool0 or the moving jaw.
All acceptance limits are engineering starting limits, not hardware guarantees.
"""
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rigid(value):
    t = np.asarray(value, dtype=float)
    if (t.shape != (4, 4) or not np.isfinite(t).all()
            or not np.allclose(t[3], [0, 0, 0, 1], atol=1e-8)
            or not np.allclose(t[:3, :3].T @ t[:3, :3], np.eye(3), atol=1e-5)
            or not np.isclose(np.linalg.det(t[:3, :3]), 1, atol=1e-5)):
        raise ValueError('Expected finite rigid T_A_B (metres)')
    return t


def mean_pose(poses):
    ts = [rigid(t) for t in poses]
    if not ts:
        raise ValueError('No poses')
    u, _, vt = np.linalg.svd(sum(t[:3, :3] for t in ts))
    r = u @ np.diag([1, 1, np.linalg.det(u @ vt)]) @ vt
    t = np.eye(4); t[:3, :3] = r
    t[:3, 3] = np.mean([x[:3, 3] for x in ts], axis=0)
    return t


def pose_error(reference, measured):
    d = np.linalg.inv(rigid(reference)) @ rigid(measured)
    angle = np.arccos(np.clip((np.trace(d[:3, :3])-1)/2, -1, 1))
    return float(np.linalg.norm(d[:3, 3])), float(np.degrees(angle))


def split_rows(rows, min_train=10):
    # Pose-level held-out split. Never split frames from the same stationary capture.
    train = [r for r in rows if r.get('split') == 'train']
    val = [r for r in rows if r.get('split') == 'validation']
    if len(train) < min_train or len(val) < 3:
        raise ValueError(f'Require >= {min_train} train poses and >= 3 held-out validation poses')
    ids = [r['capture_id'] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate capture identity')
    return train, val


def hand_eye(rows):
    import cv2
    train, val = split_rows(rows)
    gs = [rigid(r['base_from_gripper']) for r in train]
    cs = [rigid(r['optical_from_board']) for r in train]
    # Require independent rotational excitation. One-axis wrist rotation is insufficient.
    rv = np.array([cv2.Rodrigues(g[:3, :3] @ gs[0][:3, :3].T)[0].ravel() for g in gs[1:]])
    s = np.linalg.svd(rv, compute_uv=False)
    if s[1] < .12 or s[1] / max(s[0], 1e-12) < .08:
        raise ValueError('Insufficient rotation about two independent axes; collect varied poses')
    rot, xyz = cv2.calibrateHandEye([g[:3, :3] for g in gs], [g[:3, 3] for g in gs],
        [c[:3, :3] for c in cs], [c[:3, 3] for c in cs], method=cv2.CALIB_HAND_EYE_PARK)
    x = np.eye(4); x[:3, :3] = rot; x[:3, 3] = np.asarray(xyz).ravel(); rigid(x)
    # Same stationary board, solve reference using TRAIN ONLY.
    board = mean_pose([g @ x @ c for g, c in zip(gs, cs)])
    return report_pose(x, board, train, val, 'wrist')


def fixed_eye(rows, base_from_board):
    train, val = split_rows(rows, min_train=3)
    board = rigid(base_from_board)
    x = mean_pose([board @ np.linalg.inv(rigid(r['optical_from_board'])) for r in train])
    return report_pose(x, board, train, val, 'rear')


def report_pose(x, board, train, val, role):
    def errors(group):
        result = []
        for row in group:
            g = rigid(row['base_from_gripper']) if role == 'wrist' else np.eye(4)
            pos, angle = pose_error(board, g @ x @ rigid(row['optical_from_board']))
            result.append(dict(capture_id=row['capture_id'], position_error_m=pos, rotation_error_deg=angle))
        return result
    te, ve = errors(train), errors(val)
    passed = all(r['position_error_m'] <= .005 and r['rotation_error_deg'] <= 2 for r in te + ve)
    return dict(schema='harvest_camera_calibration_v1', role=role,
        parent_frame='arm_2/gripper_link' if role == 'wrist' else 'arm_2/base_link',
        child_frame='color_optical', parent_from_color_optical=x.tolist(),
        base_from_board=board.tolist(), train_errors=te, validation_errors=ve,
        consistency_passed=passed, calibration_verified=False,
        status='CONSISTENT_NEEDS_INDEPENDENT_BASE_METROLOGY' if passed else 'REJECTED_RESIDUAL',
        note='Board/FK consistency cannot certify robot joint zero or base-frame accuracy; no auto deployment.')


def fit_tcp(rows):
    train, val = split_rows(rows, min_train=6)
    def local(row):
        t = rigid(row['base_from_gripper']); p = np.asarray(row['centre_arm_m'], dtype=float)
        if p.shape != (3,) or not np.isfinite(p).all():
            raise ValueError('Surveyed centre_arm_m must be finite xyz; never use nominal FK centre as measurement')
        return t[:3, :3].T @ (p-t[:3, 3])
    offset = np.mean([local(r) for r in train], axis=0)
    def errors(group):
        return [dict(capture_id=r['capture_id'], error_m=float(np.linalg.norm(local(r)-offset))) for r in group]
    te, ve = errors(train), errors(val)
    return dict(schema='harvest_tcp_calibration_v1', frame='arm_2/gripper_link',
        centre_local_m=offset.tolist(), train_errors=te, validation_errors=ve,
        consistency_passed=all(r['error_m'] <= .003 for r in te + ve), calibration_verified=False,
        note='Fixed contact centre for the measured reference object/aperture only; independent metrology required.')


def depth_statistics(depth_m, roi, reference_z_m, low=.28, high=3):
    depth = np.asarray(depth_m)
    x, y, w, h = roi
    if (depth.ndim != 2 or not all(isinstance(v, int) for v in roi) or x < 0 or y < 0
            or w < 1 or h < 1 or x+w > depth.shape[1] or y+h > depth.shape[0]
            or not np.isfinite(reference_z_m) or reference_z_m <= 0):
        raise ValueError('Valid in-image ROI and positive optical-Z surface reference required')
    area = depth[y:y+h, x:x+w]
    good = np.isfinite(area) & (area > 0)
    z = area[good]
    return dict(roi_xywh=roi, reference_optical_z_m=reference_z_m,
        raw_valid_fraction=float(good.mean()), configured_valid_fraction=float((good & (area >= low) & (area <= high)).mean()),
        median_m=float(np.median(z)) if z.size else None,
        median_error_m=float(np.median(z)-reference_z_m) if z.size else None,
        p95_absolute_error_m=float(np.quantile(np.abs(z-reference_z_m), .95)) if z.size else None,
        depth_mad_m=float(np.median(np.abs(z-np.median(z)))) if z.size else None,
        note='No filtering, hole filling or ground-truth replacement; plane perpendicular to optical axis required.')


def detect_board(rgb, intr, columns, rows, square_m):
    import cv2
    if columns < 3 or rows < 3 or not np.isfinite(square_m) or square_m <= 0:
        raise ValueError('Inner corner dimensions >=3; measured positive square size in metres')
    model = intr['distortion_model']
    if model not in ('distortion.none', 'distortion.brown_conrady'):
        raise ValueError('Unsupported distortion model for OpenCV PnP: ' + model)
    k = np.array([[intr['fx'], 0, intr['ppx']], [0, intr['fy'], intr['ppy']], [0, 0, 1]], dtype=float)
    dist = np.zeros(5) if model == 'distortion.none' else np.array(intr['coeffs'])
    ok, corners = cv2.findChessboardCornersSB(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (columns, rows))
    if not ok:
        raise ValueError('Board not fully detected; recapture at stationary, focused pose')
    obj = np.zeros((rows*columns, 3), dtype=np.float64)
    obj[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)*square_m
    ok, r, t = cv2.solvePnP(obj, corners, k, dist, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok or t[2, 0] <= 0:
        raise ValueError('Invalid board pose')
    project, _ = cv2.projectPoints(obj, r, t, k, dist)
    rms = float(np.sqrt(np.mean(np.sum((project-corners)**2, axis=2))))
    if rms > 1:
        raise ValueError(f'Board reprojection RMS {rms:.3f}px >1px')
    pose = np.eye(4); pose[:3, :3] = cv2.Rodrigues(r)[0]; pose[:3, 3] = t.ravel()
    return dict(optical_from_board=pose.tolist(), reprojection_rms_px=rms, corners_px=corners.reshape(-1, 2).tolist())


def response_report(events):
    profiles = [e for e in events if e['event'] == 'profile']
    if len(profiles) != 1:
        raise ValueError('One force_workbench session profile required')
    hardware = profiles[0]['hardware']; rows = [e for e in events if e['event'] == 'telemetry']
    if not rows:
        raise ValueError('No actual feedback records')
    close_sign = profiles[0]['profile']['close_sign']
    opening = [e for e in events if e['event'] == 'open_step']
    markers = [e for e in events if e['event'] == 'operator_marker']
    release = next((e for e in markers if e['kind'] == 'released' and opening
                    and e['elapsed_s'] >= opening[0]['elapsed_s']), None)
    held = next((e for e in markers if e['kind'] == 'held'), None)
    return dict(schema='harvest_gripper_response_v1', hardware=hardware,
        status='OPERATOR_TIMED_MEASUREMENT' if hardware else 'DRY_RUN_NOT_PHYSICAL',
        opening_commands=len(opening), operator_markers=markers,
        release_keypress_delay_s=release['elapsed_s']-opening[0]['elapsed_s'] if release else None,
        measured_opening_to_release_rad=(release['feedback']['position']-held['feedback']['position'])*(-close_sign)*2*np.pi/4096
            if release and held and held['elapsed_s'] <= opening[0]['elapsed_s'] else None,
        max_tracking_error_ticks=max(abs(e['position']-e['target_ticks']) for e in rows),
        max_abs_load_raw=max(abs(e['load_raw']) for e in rows),
        max_abs_current_raw=max(abs(e['current_raw']) for e in rows),
        fault_events=[e for e in events if e['event'] in ('fault','travel_limit','release_failed')],
        note='Human event timing includes reaction delay. Encoder opening is not jaw gap or torque/newtons. '
             'Compare video and measured pad gap; no inferred friction/gain/effort or automatic simulation update.')
