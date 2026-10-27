"""Stop/reobserve barrier around the marker pose PID; no ROS dependencies."""
import math

class ApproachGate:
    def __init__(self, config):
        self.c = dict(max_distance_m=0.4, align_tolerance_rad=0.05,
                      realign_threshold_rad=0.17, position_tolerance_m=0.01)
        config=dict(config)
        self.heading_first=config.pop('heading_first',False)
        if type(self.heading_first) is not bool:raise ValueError('heading_first must be bool')
        self.heading_ready=not self.heading_first
        self.c.update(config)
        if any(not math.isfinite(v) or v <= 0 for v in self.c.values()):
            raise ValueError('Invalid approach limits')
        if self.c['align_tolerance_rad'] >= self.c['realign_threshold_rad']:
            raise ValueError('Approach hysteresis is inverted')
        self.phase = 'ALIGN'
        self.after_ns = None

    def step(self, preview, stopped, now_ns):
        x,y = preview['error_x_m'],preview['error_y_m']
        rho = math.hypot(x,y)
        if not math.isfinite(rho) or rho > self.c['max_distance_m']:
            raise RuntimeError(f'Approach target distance {rho:.3f}m exceeds {self.c["max_distance_m"]:.3f}m')
        if not self.heading_ready:
            yaw=preview.get('error_yaw_rad',float('nan'))
            if not math.isfinite(yaw):raise RuntimeError('Missing target yaw for initial alignment')
            if abs(yaw)>self.c['align_tolerance_rad']:
                self.phase='ALIGN_HEADING'
                return 'ALIGN_HEADING'
            self.heading_ready=True
        # PoseController blends forward motion and yaw correction continuously.
        # The station observation stop and final settling remain outside this gate.
        self.phase = 'APPROACH'
        return 'APPROACH'


def near_entry_command(preview, config, control):
    """Sorter-only terminal corridor: stop translation, finish taught yaw.

    The target is the visual-to-lidar handoff pose, not final physical docking.
    Missing/stale observations remain governed by the server freshness gates.
    """
    if not config:return None
    x,y,yaw=(preview.get(k,float('nan')) for k in ('error_x_m','error_y_m','error_yaw_rad'))
    if not all(math.isfinite(v) for v in (x,y,yaw)):return None
    if not (-config['behind_tolerance_m']<=x<=config['forward_tolerance_m'] and
            abs(y)<=config['lateral_tolerance_m']):return None
    aligned=abs(yaw)<=config['yaw_tolerance_rad']
    w=0. if aligned else max(-control['max_angular_rps'],min(control['max_angular_rps'],control['angular_pid']['kp']*yaw))
    if w:w=math.copysign(max(abs(w),control.get('min_angular_rps',0.)),w)
    return dict(linear_x=0.,angular_z=w,phase='SETTLE_LIDAR_ENTRY' if aligned else 'ALIGN_LIDAR_ENTRY',aligned=aligned)


def search_evidence(session, report, marker_id, now_ns, max_age):
    stamp=report.get('stamp_ns',0)
    age=(now_ns-stamp)/1e9
    missing=(bool(report) and 0<=age<=max_age and
             not any(m['marker_id']==marker_id for m in report.get('markers',[])))
    if not missing:
        session['missing_frame_count']=0
        session['missing_frame_stamp']=stamp
        return False
    if session.get('missing_frame_stamp')!=stamp:
        session['missing_frame_stamp']=stamp
        session['missing_frame_count']=session.get('missing_frame_count',0)+1
    return session.get('missing_frame_count',0)>=3
