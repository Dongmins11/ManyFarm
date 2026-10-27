"""Reverse clearance helpers; marker teaching remains the return-position authority."""
import math

def reverse_point(pose,goal,c):
    x,y,yaw=pose;gx,gy=goal
    if not all(math.isfinite(v) for v in (*pose,*goal)):raise ValueError('Invalid reverse point')
    dx,dy=gx-x,gy-y;distance=math.hypot(dx,dy)
    if distance>c['max_distance_m']:raise RuntimeError('Graph return distance exceeds configured corridor')
    if distance<=c['position_tolerance_m']:return 0.,0.,True
    bx=math.cos(yaw)*dx+math.sin(yaw)*dy;by=-math.sin(yaw)*dx+math.cos(yaw)*dy
    angle=math.atan2(-by,-bx)
    if bx>=0 or abs(angle)>c['max_heading_error_rad']:raise RuntimeError('Graph return node is outside reverse corridor')
    w=max(-c['max_angular_rps'],min(c['max_angular_rps'],c['steering_kp']*math.atan2(-by,max(-bx,c['lookahead_m']))))
    v=-min(c['max_linear_mps'],max(c['min_linear_mps'],distance*c['linear_kp']))*max(.5,math.cos(angle))
    return v,w,False

def backout_command(distance,heading_error,c):
    if not all(math.isfinite(v) for v in (distance,heading_error)):raise RuntimeError('Invalid backout observation')
    if abs(heading_error)>c['max_heading_error_rad']:raise RuntimeError('Backout heading drift')
    if distance<c['min_front_distance_m']:raise RuntimeError('Backout front range below minimum')
    remaining=c['reference_front_distance_m']-distance
    if remaining<=c['distance_tolerance_m']:return 0.,0.
    v=-min(c['max_linear_mps'],max(c['min_linear_mps'],remaining*c['linear_kp']))
    w=max(-c['max_angular_rps'],min(c['max_angular_rps'],c['heading_kp']*heading_error))
    return v,w
