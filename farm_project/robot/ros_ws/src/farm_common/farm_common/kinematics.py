"""실측 바퀴 회전량으로 적분하는 차동구동 odom. 위치 정답이나 cmd_vel 적분 아님."""
import math


def wheel_targets(linear, angular, radius, separation, max_linear, max_angular):
    if not all(math.isfinite(v) for v in (linear, angular)):
        return (0.0, 0.0)
    linear = max(-max_linear, min(max_linear, linear))
    angular = max(-max_angular, min(max_angular, angular))
    return ((linear-angular*separation/2)/radius, (linear+angular*separation/2)/radius)


class WheelOdometry:
    def __init__(self, radius, separation):
        if radius <= 0 or separation <= 0:
            raise ValueError('바퀴 치수는 양수여야 합니다.')
        self.radius, self.separation = radius, separation
        self.x = self.y = self.yaw = 0.0
        self.previous = None

    def update(self, positions, dt):
        left, right = map(float, positions)
        if dt <= 0 or not all(math.isfinite(v) for v in (left, right, dt)):
            raise ValueError('유효하지 않은 encoder/dt')
        if self.previous is None:
            self.previous = (left, right)
            return [self.x,self.y,self.yaw,0.0,0.0]
        dl, dr = [math.atan2(math.sin(a-b), math.cos(a-b))*self.radius
                  for a,b in zip((left,right),self.previous)]
        self.previous = (left,right)
        ds, da = (dl+dr)/2, (dr-dl)/self.separation
        scale = 1.0 if abs(da)<1e-9 else math.sin(da/2)/(da/2)
        self.x += ds*scale*math.cos(self.yaw+da/2)
        self.y += ds*scale*math.sin(self.yaw+da/2)
        self.yaw = math.atan2(math.sin(self.yaw+da), math.cos(self.yaw+da))
        return [self.x,self.y,self.yaw,ds/dt,da/dt]
