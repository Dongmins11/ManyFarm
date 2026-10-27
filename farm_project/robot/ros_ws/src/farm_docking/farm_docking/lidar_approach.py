"""Final docking: raw front lidar distance, odometry heading hold. No reverse."""
import math
import statistics

class ScanFreshnessError(RuntimeError):
    pass

def require_scan_fresh(scan, now_ns, max_age_s, context):
    stamp=scan.header.stamp.sec*10**9+scan.header.stamp.nanosec
    age=(now_ns-stamp)/1e9
    if not 0<=age<=max_age_s:
        raise ScanFreshnessError(f'{context}: age={age:.3f}s limit={max_age_s:.3f}s stamp_ns={stamp} now_ns={now_ns}')

def select_front_points(scan,c):
    values=[]
    for i,r in enumerate(scan.ranges):
        a=math.atan2(math.sin(scan.angle_min+i*scan.angle_increment),math.cos(scan.angle_min+i*scan.angle_increment))
        if abs(a)<=c['sector_half_angle_rad'] and math.isfinite(r) and scan.range_min<=r<=scan.range_max:
            values.append((a,r*math.cos(a)))
    if len(values)<c['min_points']:raise RuntimeError('Raw front scan insufficient')
    if c.get('selection_mode','all')=='center_cluster':
        # Excluded side returns still participate in the minimum clearance guard.
        if min(d for a,d in values)<c['hard_min_distance_m']:
            raise RuntimeError('Front lidar minimum clearance reached')
        values.sort()
        seed=min(range(len(values)),key=lambda i:abs(values[i][0]))
        if abs(values[seed][0])>c['center_max_angle_rad']:
            raise RuntimeError('Raw front center missing')
        selected=[values[seed][1]]
        for direction in (-1,1):
            prev=seed;i=seed+direction
            while 0<=i<len(values):
                a,d=values[i]
                if abs(a-values[prev][0])>abs(scan.angle_increment)*1.5+1e-6:break
                if max(max(selected),d)-min(min(selected),d)>c['max_spread_m']:break
                selected.append(d);prev=i;i+=direction
        if len(selected)<c['min_points']:
            raise RuntimeError(f'Raw front center cluster insufficient: selected={len(selected)} total={len(values)}')
    else:selected=[d for a,d in values]
    spread=max(selected)-min(selected)
    if spread>c['max_spread_m']:
        raise RuntimeError(f'Raw front surface inconsistent: spread={spread:.3f}m limit={c["max_spread_m"]:.3f}m')
    return selected

class LidarApproach:
    def __init__(self,c,marker_target=None):
        self.c=dict(c);self.good_since=None;self.last_stamp=None
        if c.get('surface_tracking'):
            for key in ('surface_match_m','surface_anchor_tolerance_m','surface_occlusion_s','surface_occlusion_travel_m','surface_prediction_speed_scale'):
                if key not in c:raise ValueError('Missing surface tracking '+key)
            if c['surface_prediction_speed_scale']>1:raise ValueError('Surface prediction must not accelerate')
        self.surface=FrontSurfaceTracker(c,marker_target) if c.get('surface_tracking',False) else None
        if c.get('selection_mode','all') not in ('all','center_cluster'):raise ValueError('Invalid scan selection mode')
        if c.get('selection_mode')=='center_cluster' and not 0<c.get('center_max_angle_rad',0)<=c['sector_half_angle_rad']:raise ValueError('Invalid center angle')
        for k,v in c.items():
            if k in ('raw_scan_topic','scan_frame','selection_mode','surface_tracking','marker_surface_selection'):continue
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:raise ValueError('Invalid lidar approach '+k)
        if not c['hard_min_distance_m']<c['target_distance_m']<c['max_start_distance_m']:raise ValueError('Invalid lidar distances')
        if c['min_linear_mps']>c['max_linear_mps']:raise ValueError('Invalid lidar speed')
    def step(self,scan,now_ns,heading_error,scan_pose=None,current_pose=None):
        c=self.c;stamp=scan.header.stamp.sec*10**9+scan.header.stamp.nanosec
        if scan.header.frame_id!=c['scan_frame']:raise RuntimeError('Raw lidar frame mismatch')
        require_scan_fresh(scan,now_ns,c['max_age_s'],'DISTANCE_RAW_SCAN_STALE')
        if not math.isfinite(heading_error) or abs(heading_error)>c['max_heading_error_rad']:raise RuntimeError('Final approach heading drift')
        if scan.range_min>=c['target_distance_m']-c['distance_tolerance_m']:raise RuntimeError('Target below reliable lidar range')
        if self.surface:
            d=self.surface.distance(scan,now_ns,scan_pose,current_pose)
        else:
            points=select_front_points(scan,c)
            d=statistics.median(points)
            if min(points)<c['hard_min_distance_m']:raise RuntimeError('Front lidar minimum clearance reached')
        if d>c['max_start_distance_m']:raise RuntimeError('Front target outside approach range')
        if d<c['target_distance_m']-c['distance_tolerance_m']:raise RuntimeError('Front target overshot')
        reached=abs(d-c['target_distance_m'])<=c['distance_tolerance_m']
        if reached and (self.surface is None or self.surface.observed):
            if self.good_since is None:self.good_since=stamp
        else:self.good_since=None
        done=reached and self.good_since is not None and (stamp-self.good_since)/1e9>=c['stable_s']
        v=0. if reached else min(c['max_linear_mps'],max(c['min_linear_mps'],c['linear_kp']*(d-c['target_distance_m'])))
        w=0. if reached else max(-c['max_angular_rps'],min(c['max_angular_rps'],c['heading_kp']*heading_error))
        if self.surface and not self.surface.observed:
            v*=c['surface_prediction_speed_scale'];w*=c['surface_prediction_speed_scale']
        return v,w,done,d

def front_distance(scan,now_ns,c,context='BACKOUT_RAW_SCAN_STALE'):
    """Raw front observation for reverse reacquisition, independent of dock completion."""
    stamp=scan.header.stamp.sec*10**9+scan.header.stamp.nanosec
    if scan.header.frame_id!=c['scan_frame']:raise RuntimeError('Raw lidar frame mismatch')
    require_scan_fresh(scan,now_ns,c['max_age_s'],context)
    points=[]
    for i,r in enumerate(scan.ranges):
        a=math.atan2(math.sin(scan.angle_min+i*scan.angle_increment),math.cos(scan.angle_min+i*scan.angle_increment))
        if abs(a)<=c['sector_half_angle_rad'] and math.isfinite(r) and scan.range_min<=r<=scan.range_max:points.append(r*math.cos(a))
    if len(points)<c['min_points']:raise RuntimeError('Raw front scan insufficient')
    if max(points)-min(points)>c['max_spread_m']:raise RuntimeError('Raw front surface inconsistent')
    return statistics.median(points)

class FrontSurfaceTracker:
    """Associate front returns to a fixed odom plane; never relock to background.

    Assumes the approached surface is stationary and approximately transverse
    to the initial laser axis. Scan-time TF prevents motion latency appearing
    as a changing surface. Nearer returns remain blocking observations.
    """
    def __init__(self,c,marker_target=None):
        self.marker_target=marker_target
        self.c=c;self.anchor=None;self.plane=None;self.normal=None
        self.last_seen=None;self.last_pose=None;self.last_scan=None
        self.observed=False;self.mode='ACQUIRE';self.count=0

    def distance(self,scan,now_ns,capture,current):
        c=self.c
        if capture is None or current is None or not all(math.isfinite(v) for v in (*capture,*current)):
            raise RuntimeError('Surface tracking requires scan-time and current laser odometry')
        stamp=scan.header.stamp.sec*10**9+scan.header.stamp.nanosec
        values=[]
        for i,r in enumerate(scan.ranges):
            a=math.atan2(math.sin(scan.angle_min+i*scan.angle_increment),math.cos(scan.angle_min+i*scan.angle_increment))
            if abs(a)<=c['sector_half_angle_rad'] and math.isfinite(r) and scan.range_min<=r<=scan.range_max:
                values.append((a,r))
        if self.anchor is None:
            # Existing center-cluster acquisition is retained, then its world
            # plane is committed. Failure here never starts blind movement.
            selected=select_marker_surface(scan,c,self.marker_target,capture) if c.get('marker_surface_selection') else select_front_points(scan,c)
            self.normal=(math.cos(capture[2]),math.sin(capture[2]))
            self.anchor=self.plane=sum(n*x for n,x in zip(self.normal,capture[:2]))+statistics.median(selected)
        nx,ny=self.normal
        projection=nx*math.cos(current[2])+ny*math.sin(current[2])
        if projection<.95:raise RuntimeError('Tracked surface heading outside approach corridor')
        origin=nx*current[0]+ny*current[1]
        expected=(self.plane-origin)/projection
        planes=[]
        for a,r in values:
            wx=capture[0]+r*math.cos(capture[2]+a)
            wy=capture[1]+r*math.sin(capture[2]+a)
            # Current laser-forward clearance, including scan acquisition lag.
            clearance=math.cos(current[2])*(wx-current[0])+math.sin(current[2])*(wy-current[1])
            if clearance<c['hard_min_distance_m']:
                raise RuntimeError('Front lidar minimum clearance reached')
            q=nx*wx+ny*wy
            if q<self.plane-c['surface_match_m']:
                raise RuntimeError('Tracked surface blocked by nearer front return')
            if abs(q-self.anchor)<=c['surface_anchor_tolerance_m'] and abs(q-self.plane)<=c['surface_match_m']:
                planes.append(q)
        matched=len(planes)>=c['min_points'] and max(planes,default=0)-min(planes,default=0)<=c['max_spread_m']
        self.count=len(planes);self.observed=matched
        if matched:
            if self.last_scan!=stamp:
                self.plane=.7*self.plane+.3*statistics.median(planes)
                self.last_seen=stamp;self.last_pose=capture
            self.mode='TRACKED_SURFACE'
        else:
            self.mode='ODOM_SURFACE_PREDICTION'
            if self.last_seen is None:raise RuntimeError('No initial tracked surface')
            age=(now_ns-self.last_seen)/1e9
            travel=math.hypot(current[0]-self.last_pose[0],current[1]-self.last_pose[1])
            if age>c['surface_occlusion_s'] or travel>c['surface_occlusion_travel_m']:
                raise RuntimeError(f'Tracked surface lost: age={age:.3f}s travel={travel:.3f}m matched={len(planes)}')
        self.last_scan=stamp
        return (self.plane-origin)/projection


def select_tf_ready_scan(scans, now_ns, max_age_s, transform_ready, minimum_stamp=None):
    """Newest fresh scan with capture-time TF, without blocking the control loop."""
    for scan in reversed(scans):
        stamp=scan.header.stamp.sec*10**9+scan.header.stamp.nanosec
        if minimum_stamp is not None and stamp<minimum_stamp:continue
        if not 0<=(now_ns-stamp)/1e9<=max_age_s:continue
        if transform_ready(scan):return scan
    raise ScanFreshnessError('SURFACE_SCAN_TF_PENDING: no fresh capture-time pair')


def initial_creep_command(scan,now_ns,c,origin,pose):
    """Bounded straight acquisition creep, with raw front clearance checks."""
    if scan is None:return 0.,0.
    if scan.header.frame_id!=c['scan_frame']:return 0.,0.
    try:require_scan_fresh(scan,now_ns,c['max_age_s'],'INITIAL_CREEP_SCAN_STALE')
    except ScanFreshnessError:return 0.,0.
    points=[]
    for i,r in enumerate(scan.ranges):
        a=math.atan2(math.sin(scan.angle_min+i*scan.angle_increment),math.cos(scan.angle_min+i*scan.angle_increment))
        if abs(a)<=c['sector_half_angle_rad'] and math.isfinite(r) and scan.range_min<=r<=scan.range_max:
            points.append(r*math.cos(a))
    if len(points)<c['min_points']:return 0.,0.
    if min(points)<=max(c['hard_min_distance_m'],c['target_distance_m']+.03):return 0.,0.
    if math.hypot(pose[0]-origin[0],pose[1]-origin[1])>=c['initial_creep_max_travel_m']:return 0.,0.
    error=math.atan2(math.sin(origin[2]-pose[2]),math.cos(origin[2]-pose[2]))
    if abs(error)>c['max_heading_error_rad']:return 0.,0.
    return min(c['initial_creep_mps'],c['max_linear_mps']),max(-c['max_angular_rps'],min(c['max_angular_rps'],c['heading_kp']*error))


def select_marker_surface(scan,c,marker_target,capture):
    """Select a contiguous scan cluster near the marker's odom XY position.

    Camera extrinsics are already applied in marker_position_in_base_m.
    This chooses a surface only; it never changes the robot heading.
    """
    if marker_target is None:raise RuntimeError('Marker surface target missing')
    dx,dy=marker_target[0]-capture[0],marker_target[1]-capture[1]
    x=math.cos(capture[2])*dx+math.sin(capture[2])*dy
    y=-math.sin(capture[2])*dx+math.cos(capture[2])*dy
    if x<=0:raise RuntimeError('Marker surface target behind lidar')
    angle=math.atan2(y,x)
    values=[]
    for i,r in enumerate(scan.ranges):
        a=math.atan2(math.sin(scan.angle_min+i*scan.angle_increment),math.cos(scan.angle_min+i*scan.angle_increment))
        if abs(a)<=c['sector_half_angle_rad'] and math.isfinite(r) and scan.range_min<=r<=scan.range_max:
            values.append((a,r*math.cos(a)))
    values.sort();groups=[]
    for a,d in values:
        if not groups or a-groups[-1][-1][0]>abs(scan.angle_increment)*1.5+1e-6 or abs(d-groups[-1][-1][1])>c['max_spread_m']:
            groups.append([])
        groups[-1].append((a,d))
    candidates=[]
    for g in groups:
        depths=[v[1] for v in g]
        if len(g)<c['min_points'] or max(depths)-min(depths)>c['max_spread_m']:continue
        angular_gap=max(g[0][0]-angle,angle-g[-1][0],0.)
        depth_gap=abs(statistics.median(depths)-x)
        if angular_gap<=c['marker_surface_angle_gate_rad'] and depth_gap<=c['marker_surface_depth_gate_m']:
            score=depth_gap/c['marker_surface_depth_gate_m']+angular_gap/c['marker_surface_angle_gate_rad']
            candidates.append((score,depths))
    candidates.sort(key=lambda item:item[0])
    if not candidates:raise RuntimeError('Marker surface not matched to front scan')
    if len(candidates)>1 and candidates[1][0]-candidates[0][0]<.2:
        raise RuntimeError('Marker surface ambiguous')
    return candidates[0][1]
