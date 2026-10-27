"""Stationary marker-bearing acquisition; no taught XY target or reacquisition."""
import math

def wrap(a):return math.atan2(math.sin(a),math.cos(a))

class HeadingCapture:
    def __init__(self,c):self.c=c;self.samples=[];self.last_stamp=0
    def add(self,report,odom_yaw,now_ns):
        stamp=report.get('stamp_ns',0)
        if stamp<=self.last_stamp:return None
        # 관측이 끊긴 전후의 표본을 합쳐 안정 관측으로 인정하지 않는다.
        if self.last_stamp and (stamp-self.last_stamp)/1e9>self.c['max_age_s']:self.samples=[]
        self.last_stamp=stamp
        if not 0<=(now_ns-stamp)/1e9<=self.c['max_age_s']:self.samples=[];return None
        marker=next((m for m in report.get('markers',[]) if m['marker_id']==self.c['marker_id']),None)
        if marker is None:self.samples=[];return None
        x,y,z=marker['marker_position_in_base_m']
        if not all(math.isfinite(v) for v in (x,y,z,odom_yaw)) or x<=0:self.samples=[];return None
        if self.c.get('heading_source') == 'odom_current':
            # Marker identity/freshness only; neither bearing nor normal steers.
            self.samples.append(wrap(odom_yaw))
        else:
            if abs(y)>self.c.get('max_lateral_m',float('inf')):self.samples=[];return None
            bearing=math.atan2(y,x)
            if abs(bearing)>self.c['max_bearing_rad']:self.samples=[];return None
            direction=bearing
            if self.c.get('heading_source') == 'marker_normal':
                rotation=marker.get('marker_rotation_in_base', [])
                try:nx,ny=-float(rotation[0][2]),-float(rotation[1][2])
                except (IndexError,TypeError,ValueError):self.samples=[];return None
                if not math.isfinite(nx+ny) or nx<=0 or math.hypot(nx,ny)<.5:self.samples=[];return None
                direction=math.atan2(ny,nx)
                if abs(direction)>self.c['max_bearing_rad']:self.samples=[];return None
            self.samples.append(wrap(odom_yaw+direction+self.c.get('heading_offset_rad',0.)))
        self.samples=self.samples[-self.c['samples']:]
        if len(self.samples)<self.c['samples']:return None
        mean=math.atan2(sum(math.sin(a) for a in self.samples),sum(math.cos(a) for a in self.samples))
        if max(abs(wrap(a-mean)) for a in self.samples)>self.c['spread_rad']:return None
        return mean
