"""Stationary acquisition -> bounded frozen odom transit -> fresh final vision."""
import math
import numpy as np
from .departure import DepartureTracker
from .target_tracker import FixedTargetTracker, yaw, wrap, planar

class StagedDockTracker(DepartureTracker):
    def __init__(self,target,marker_id,tracking,config):
        super().__init__(target,marker_id,tracking,config)
        self.phase='ACQUIRE';self.verify_after_ns=0;self.final_count=0
        self.final_samples=[]
        self._hybrid_scale=1.;self._hybrid_stamp=None
        self._approach_heading=None
        if self.d.get('hybrid_relative_control'):
            if not self.d.get('visual_correction_during_transit') or not self.d.get('odom_only_after_acquire'):
                raise ValueError('hybrid relative control requires visual transit and terminal lock')
            if not 0<self.d.get('occluded_speed_scale',0)<=1 or not math.isfinite(self.d.get('source_speed_transition_s',0)) or self.d.get('source_speed_transition_s',0)<=0:
                raise ValueError('invalid hybrid speed transition')
        if not 0 < self.d['reobserve_distance_m'] < self.d['max_odom_travel_m']:
            raise ValueError('reobserve_distance_m')
    def stable(self,samples):
        if len(samples)<self.d['acquire_samples']:return False
        xy=np.array([g[:2,3] for g in samples])
        return (np.max(np.linalg.norm(xy-np.median(xy,axis=0),axis=1))<=self.d['acquire_spread_m'] and
                max(abs(wrap(yaw(g)-yaw(samples[-1]))) for g in samples)<=self.d.get('acquire_yaw_spread_rad',.1))
    def update(self,report,odom_base,now_ns,max_distance,max_tilt):
        distance_cfg=self.d.get('distance_corridor')
        if distance_cfg:
            # Marker translation is enough: do not rotate the stand-off vector
            # with the noisy marker normal or the taught terminal orientation.
            marker=next((m for m in report['markers'] if m['marker_id']==self.marker_id),None)
            if marker is not None and 0<=(now_ns-report['stamp_ns'])/1e9<=self.c['max_input_age_s']:
                position=np.asarray(marker['marker_position_in_base_m'],dtype=float)
                if position.shape!=(3,) or not np.isfinite(position).all():return False
                anchor=yaw(odom_base) if self._approach_heading is None else self._approach_heading
                global_marker=odom_base@np.r_[position,1.]
                goal=planar(global_marker[0]-distance_cfg['target_range_m']*math.cos(anchor),
                            global_marker[1]-distance_cfg['target_range_m']*math.sin(anchor),anchor)
                relative=np.linalg.inv(odom_base)@goal
                if np.linalg.norm(relative[:2,3])>max_distance:
                    self.reason='distance target outside approach envelope';return False
                if self._approach_heading is None:self._approach_heading=anchor
                virtual_marker=relative@np.linalg.inv(self.target)
                report=dict(report,markers=[dict(marker_id=self.marker_id,
                    marker_position_in_base_m=virtual_marker[:3,3].tolist(),
                    marker_rotation_in_base=virtual_marker[:3,:3].tolist())])
        if self.phase in ('TRANSIT','ALIGN') and self.d.get('odom_only_after_acquire',False) and not (self.phase=='TRANSIT' and self.d.get('visual_correction_during_transit',False)):
            return False  # Committed goal is immutable, even with new/missing/noisy images.
        if self.phase in ('TRANSIT','ALIGN'):
            # Optional fresh visual correction never invalidates the locked estimate.
            saved=(self.goal.copy(),self.origin.copy(),self.stamp,self.accepted_count)
            ok=FixedTargetTracker.update(self,report,odom_base,now_ns,max_distance,max_tilt)
            self.origin=saved[1]  # Keep total travel bound anchored at initial acquisition.
            if ok:
                delta=np.linalg.norm(self.goal[:2,3]-saved[0][:2,3])
                angle=abs(wrap(yaw(self.goal)-yaw(saved[0])))
                if delta>self.d.get('update_step_m',.01) or angle>self.d.get('update_step_rad',.05):
                    if self.d.get('continuous_visual_handoff') or self.d.get('visual_correction_during_transit'):
                        step=self.goal[:2,3]-saved[0][:2,3]
                        step*=min(1.,self.d.get('update_step_m',.01)/max(delta,1e-9))
                        da=wrap(yaw(self.goal)-yaw(saved[0]))
                        da=max(-self.d.get('update_step_rad',.05),min(self.d.get('update_step_rad',.05),da))
                        self.goal=planar(*(saved[0][:2,3]+step),yaw(saved[0])+da)
                    else:
                        self.goal,self.origin,self.stamp,self.accepted_count=saved
                        self.reason='visual correction exceeds step bound';return False
            if ok:
                self._visual_origin=odom_base.copy()
                self._visual_relative=np.linalg.inv(odom_base)@self.goal
            return ok
        if self.phase=='ACQUIRE':
            ok=super().update(report,odom_base,now_ns,max_distance,max_tilt)
            if self.locked:
                if self.stable([g for g,_ in self.samples]):
                    self.phase='TRANSIT';self._visual_origin=odom_base.copy()
                    self._visual_relative=np.linalg.inv(odom_base)@self.goal
                else:self.locked=False
            return ok
        if report['stamp_ns']<=self.verify_after_ns:return False
        ok=FixedTargetTracker.update(self,report,odom_base,now_ns,max_distance,max_tilt)
        if ok:
            self.final_count+=1
            self.final_samples.append(self.goal.copy())
            self.final_samples=self.final_samples[-self.d['acquire_samples']:]
            if self.stable(self.final_samples):self.phase='FINAL'
        else:
            self.final_count=0;self.final_samples=[]
        return ok
    def observation(self,odom_base,odom_stamp,now_ns):
        if self.phase=='ACQUIRE':return None,'acquiring stopped marker target'
        if self.phase in ('TRANSIT','ALIGN'):
            if self.d.get('continuous_visual_handoff'):
                origin=getattr(self,'_visual_origin',self.origin)
                age=(now_ns-self.stamp)/1e9
                travel=float(np.linalg.norm(odom_base[:2,3]-origin[:2,3]))
                turn=abs(wrap(yaw(odom_base)-yaw(origin)))
                if (age>self.c['max_prediction_s'] or travel>self.c['max_prediction_distance_m'] or
                        turn>self.c['max_prediction_yaw_rad']):
                    return None,f'visual continuation limit: age={age:.3f}s travel={travel:.3f}m yaw={turn:.3f}rad'
                return super().observation(odom_base,odom_stamp,now_ns)
            if self.phase=='TRANSIT' and self.d.get('visual_correction_during_transit') and not self.d.get('distance_corridor'):
                origin=getattr(self,'_visual_origin',self.origin)
                age=(now_ns-self.stamp)/1e9
                travel=float(np.linalg.norm(odom_base[:2,3]-origin[:2,3]))
                turn=abs(wrap(yaw(odom_base)-yaw(origin)))
                if (not 0<=age<=self.c['max_prediction_s'] or travel>self.c['max_prediction_distance_m'] or
                        turn>self.c['max_prediction_yaw_rad']):
                    return None,f'approach visual continuation limit: age={age:.3f}s travel={travel:.3f}m yaw={turn:.3f}rad; {self.reason}'
            estimate,reason=super().observation(odom_base,odom_stamp,now_ns)
            if self.d.get('hybrid_relative_control'):
                # Latest accepted marker-relative target, compensated from its
                # capture pose to the current base. The exact same target is
                # retained during occlusion; switching sources cannot jump it.
                relative=np.linalg.inv(odom_base)@self._visual_origin@self._visual_relative
                marker=relative@np.linalg.inv(self.target)
                estimate['markers'][0].update(marker_rotation_in_base=marker[:3,:3].tolist(),
                    marker_position_in_base_m=marker[:3,3].tolist())
                age=(now_ns-self.stamp)/1e9
                missing=(self.last_attempt is not None and self.last_attempt>self.stamp and bool(self.reason))
                mode=('FINAL_ALIGNMENT' if self.phase=='ALIGN' else
                      'ODOM_CONTINUATION' if missing or age>self.c['max_input_age_s'] else 'VISUAL_RELATIVE')
                desired=self.d['occluded_speed_scale'] if mode=='ODOM_CONTINUATION' else 1.
                dt=0. if self._hybrid_stamp is None else max(0.,(odom_stamp-self._hybrid_stamp)/1e9)
                step=dt/self.d['source_speed_transition_s']
                self._hybrid_scale+=max(-step,min(step,desired-self._hybrid_scale))
                self._hybrid_stamp=odom_stamp
                estimate.update(tracking_source=mode,tracking_speed_scale=self._hybrid_scale)
            relative=np.linalg.inv(odom_base)@self.goal
            x,y=relative[:2,3]
            if self.d.get('distance_corridor'):
                return estimate,reason
            if self.phase=='TRANSIT' and math.hypot(x,y)<=self.d.get('terminal_position_m',.02):
                self.phase='ALIGN'
            if self.phase=='ALIGN':
                if math.hypot(x,y)>self.d.get('terminal_position_exit_m',.035):
                    raise RuntimeError('Frozen target alignment position drift')
                if self.d.get('odom_only_after_acquire',False):
                    return estimate,reason  # Stay locked through terminal alignment and settling.
                if abs(yaw(relative))<=self.d.get('terminal_yaw_rad',.05):
                    if 0<=(now_ns-self.stamp)/1e9<=self.c['max_input_age_s']:
                        self.phase='FINAL';self.locked=False
                    else:
                        self.phase='VERIFY';self.locked=False;self.verify_after_ns=now_ns
                        return None,'fresh final marker observation required'
            return estimate,reason
        if self.phase=='VERIFY':return None,'fresh final marker observation required'
        return FixedTargetTracker.observation(self,odom_base,odom_stamp,now_ns)


def transit_command(preview, config):
    """Reach frozen XY first; reserve terminal yaw for fresh final alignment."""
    x,y=preview['error_x_m'],preview['error_y_m']
    alpha=math.atan2(y,x)
    if config.get('track_final_heading',False):
        # Polar pose control: beta is the goal heading relative to the
        # line of sight. Negative beta feedback curves onto the goal heading;
        # simply adding positive yaw error can steer away from the target XY.
        rho=math.hypot(x,y)
        beta=wrap(preview['error_yaw_rad']-alpha)
        turn=config['heading_kp']*alpha-config['final_heading_kp']*beta
        limit=config['max_angular_rps']
        w=max(-limit,min(limit,turn))
        blend=max(0.,1.-(abs(alpha)/config['rotate_first_rad'])**2)
        # Keep steering attenuation and saturation scaling. A profile may
        # compensate low-speed deadband only while nearly facing the target.
        speed=config['linear_kp']*rho
        if abs(alpha)<=config.get('aligned_min_speed_bearing_rad',0.1) and abs(turn)<=limit:
            speed=max(speed,config.get('aligned_min_linear_mps',0.0))
        v=min(config['max_linear_mps'],speed)*blend
        v*=min(1.,limit/max(abs(turn),1e-9))
        return dict(linear_x=v,angular_z=w,phase='MOVE_TO_FIXED_TARGET',at_target=False)
    w=max(-config['max_angular_rps'],min(config['max_angular_rps'],config['heading_kp']*alpha))
    blend=max(0.,1.-(abs(alpha)/config['rotate_first_rad'])**2)
    v=min(config['max_linear_mps'],max(config['min_linear_mps'],config['linear_kp']*math.hypot(x,y)))*blend
    return dict(linear_x=v,angular_z=w,phase='MOVE_TO_FIXED_TARGET',at_target=False)


def frozen_alignment(preview, config):
    error=preview['error_yaw_rad']
    w=max(-config['max_angular_rps'],min(config['max_angular_rps'],config['angular_pid']['kp']*error))
    return dict(linear_x=0.,angular_z=w,phase='ALIGN_FIXED_TARGET',at_target=False)


def visual_line_command(preview, config, entry):
    """Track the taught approach line while moving; align yaw only inside entry XY.

    Approach steering follows the target point; taught yaw is aligned after arrival.
    No visual watchdog or search transition lives in this velocity controller.
    """
    x,y,a=(preview[k] for k in ('error_x_m','error_y_m','error_yaw_rad'))
    along=math.cos(a)*x+math.sin(a)*y
    cross=-math.sin(a)*x+math.cos(a)*y
    if along < -entry['behind_tolerance_m']:
        raise RuntimeError('Visual entry overshot: re-position required')
    xy=(-entry['behind_tolerance_m']<=along<=entry['forward_tolerance_m'] and
        abs(cross)<=entry['lateral_tolerance_m'])
    limit=config['max_angular_rps']
    if xy:
        aligned=abs(a)<=entry['yaw_tolerance_rad']
        w=0. if aligned else max(-limit,min(limit,config['heading_kp']*a))
        return dict(linear_x=0.,angular_z=w,phase='SETTLE_LIDAR_ENTRY' if aligned else 'ALIGN_LIDAR_ENTRY',at_target=False)
    cross=-math.sin(a)*x+math.cos(a)*y
    rho=math.hypot(x,y)
    # Translation approaches the taught point with bounded gentle steering.
    # Final taught yaw belongs only to the XY-arrival branch above.
    bearing=math.atan2(y,x)
    approach_limit=config.get('approach_max_angular_rps',.10)
    w=max(-approach_limit,min(approach_limit,
        config.get('approach_heading_kp',.8)*bearing))
    blend=max(0.,1.-(abs(bearing)/config['rotate_first_rad'])**2)
    floor=config.get('terminal_min_linear_mps',config['min_linear_mps'])
    # Slow translation when the limited turn rate cannot yet follow the bearing.
    turn_scale=min(1.,approach_limit/max(abs(config.get('approach_heading_kp',.8)*bearing),1e-6))
    v=min(config.get('approach_max_linear_mps',.04),
        max(floor,config['linear_kp']*rho))*blend*turn_scale
    return dict(linear_x=v,angular_z=w,phase='TRACK_VISUAL_LINE',at_target=False)


def distance_corridor_command(preview, config):
    """Approach a stand-off distance with a fixed heading corridor, not a pose."""
    x,y,a=(preview[k] for k in ('error_x_m','error_y_m','error_yaw_rad'))
    along=math.cos(a)*x+math.sin(a)*y
    cross=-math.sin(a)*x+math.cos(a)*y
    reached=along<=config['distance_tolerance_m']
    # a = anchor heading - current heading. Clamp the desired heading about
    # the acquisition anchor; do not reset the anchor with new detections.
    offset=math.atan2(cross,max(along,config['lookahead_m']))
    limit=config['max_heading_offset_rad']
    offset=max(-limit,min(limit,offset))
    w=max(-config['max_angular_rps'],min(config['max_angular_rps'],config['heading_kp']*wrap(a+offset)))
    v=min(config['max_linear_mps'],max(config['min_linear_mps'],config['linear_kp']*max(0.,along)))
    v*=max(0.,math.cos(a))
    return dict(linear_x=0. if reached else v,angular_z=0. if reached else w,
        phase='DISTANCE_SETTLING' if reached else 'APPROACH_DISTANCE',at_target=False,
        distance_reached=reached,remaining_along_m=along,lateral_offset_m=cross,
        heading_from_anchor_rad=-a,desired_heading_offset_rad=offset)
