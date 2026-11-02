"""벽 관측 이후 오돔 이동을 반영하는 평면 변환·제한시간 연결·속도 변화 제한."""
import math
import numpy as np
from .station_wall_control import wrap


def predict_wall(wall: dict, observed_pose: np.ndarray, current_pose: np.ndarray,
                 name: str) -> dict:
    """관측 시점 base 평면을 odom에 고정한 뒤 현재 base로 변환한다."""
    normal_odom=observed_pose[:2,:2]@np.asarray(wall['normal_xy'])
    distance_odom=wall['distance_m']+float(normal_odom@observed_pose[:2,3])
    normal=current_pose[:2,:2].T@normal_odom
    distance=distance_odom-float(normal_odom@current_pose[:2,3])
    center={'left':math.pi/2,'right':-math.pi/2,'rear':math.pi,'front':0.}[name]
    return dict(wall,normal_xy=normal.tolist(),distance_m=distance,
                angle=wrap(math.atan2(normal[1],normal[0])-center))


def continuation_scale(age_s: float, fresh_s: float, limit_s: float) -> float:
    """관측을 계속 못 받으면 이전 속도를 유지하지 않고 제한시간 내 0으로 줄인다."""
    if age_s<=fresh_s:return 1.
    return max(0.,min(1.,(limit_s-age_s)/(limit_s-fresh_s)))


def ramp_command(previous: tuple, target: tuple, dt: float, linear_accel: float,
                 linear_decel: float, angular_accel: float) -> tuple:
    """m/s²·rad/s² 단위. 실행 지연분을 큰 속도 점프로 보상하지 않는다."""
    dt=max(0.,min(dt,.1));out=[]
    for index,(old,new) in enumerate(zip(previous,target)):
        rate=angular_accel if index else (linear_decel if abs(new)<abs(old) else linear_accel)
        out.append(old+max(-rate*dt,min(rate*dt,new-old)))
    return tuple(out)
