"""바퀴 속도 측정 기반 PI 보정. 위치 정답/차체 pose를 사용하지 않는다."""
import numpy as np


class WheelVelocityServo:
    def __init__(self, config: dict) -> None:
        self.kp=float(config['kp']); self.ki=float(config['ki'])
        self.dt=float(config.get('dt_s',1/60))
        self.limit=float(config['max_correction_rad_s'])
        if not all(np.isfinite(v) and v>0 for v in [self.kp,self.ki,self.dt,self.limit]):
            raise ValueError('wheel_velocity_servo 설정은 양의 유한한 수여야 합니다.')
        self.integral=np.zeros(2);self.filtered=np.zeros(2);self.previous=np.zeros(2)

    def command(self, desired: np.ndarray, measured: np.ndarray) -> np.ndarray:
        desired=np.asarray(desired,dtype=float);measured=np.asarray(measured,dtype=float)
        if desired.shape!=(2,) or measured.shape!=(2,) or not np.isfinite([desired,measured]).all():
            raise ValueError('바퀴 명령과 측정은 유한한 2개 속도여야 합니다.')
        if np.all(np.abs(desired)<1e-8):
            # USD 관절의 velocity drive가 정지 제동을 담당한다. 외부 PI의
            # 지연 측정/잔여 적분으로 반대 방향 target을 만들어 재회전시키지 않는다.
            self.integral[:]=0.
            self.filtered=measured.copy()
            self.previous=desired.copy()
            return np.zeros(2)
        self.filtered += .25*(measured-self.filtered)
        # 정지 전환에서 기존 주행 적분만 지운다. 정지 유지 중에는 외란을 보상한다.
        reset=((np.abs(desired)<1e-8)&(np.abs(self.previous)>=1e-8))|(desired*self.previous<0)
        self.integral[reset]=0.
        error=desired-self.filtered
        self.integral[~reset]=np.clip(self.integral[~reset]+self.ki*error[~reset]*self.dt,-self.limit,self.limit)
        self.previous=desired.copy()
        return desired+np.clip(self.kp*error+self.integral,-self.limit,self.limit)
