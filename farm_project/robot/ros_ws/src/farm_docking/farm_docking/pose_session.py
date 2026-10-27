"""Fail-closed decision between pose preview and an owned velocity output."""
import math


def pose_command(preview, now_ns, *, session_start_ns, marker_id, expected_marker_id,
                 output_enabled, odom_fresh, scan_fresh, lease_ok, cancelled,
                 clearance_verified, max_age=.3):
    if cancelled:raise RuntimeError('Pose docking cancelled')
    if not output_enabled:raise RuntimeError('Pose motor output disabled')
    if not lease_ok:raise RuntimeError('Pose motion lease unavailable')
    if not odom_fresh or not scan_fresh:raise RuntimeError('Pose odom/scan stale')
    if not clearance_verified:raise RuntimeError('Pose approach clearance not verified')
    if marker_id!=expected_marker_id:raise RuntimeError('Pose target marker mismatch')
    if not preview or preview['stamp_ns']<session_start_ns:raise RuntimeError('No observation for this session')
    age=(now_ns-preview['stamp_ns'])/1e9
    if not 0<=age<=max_age:raise RuntimeError('Pose observation stale')
    if preview['phase']=='WAIT_OBSERVATION':raise RuntimeError(preview.get('reason','Pose unavailable'))
    v,w=preview['linear_x'],preview['angular_z']
    if not all(math.isfinite(x) for x in (v,w)):raise RuntimeError('Invalid pose velocity')
    return v,w,bool(preview['at_target'])
