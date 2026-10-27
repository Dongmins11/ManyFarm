"""검증된 이격 통로에서 목표 pose로 후진한다. 임의 거리 fallback은 없다."""
import math

def wrap(a): return math.atan2(math.sin(a),math.cos(a))

def reverse_to_pose(pose, target, max_distance=.8, xy_tol=.02, yaw_tol=.05):
    x,y,yaw=pose;gx,gy,gyaw=target
    if not all(math.isfinite(v) for v in (*pose,*target)):raise ValueError('유한 pose 필요')
    dx,dy=gx-x,gy-y;distance=math.hypot(dx,dy)
    if distance>max_distance:raise ValueError('검증된 이격 길이 초과')
    if distance<=xy_tol:
        error=wrap(gyaw-yaw)
        return (0.,max(-.15,min(.15,error)),abs(error)<=yaw_tol)
    error=wrap(math.atan2(dy,dx)-yaw-math.pi)
    # 옆/앞의 목표를 향해 무조건 돌지 않는다. 프로파일 방향부터 수정한다.
    if abs(error)>.5:raise ValueError('이격 목표가 후진 통로 밖에 있음')
    return (-min(.04,distance*.5),max(-.15,min(.15,error)),False)
