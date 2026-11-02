"""후진 스테이션의 벽 관측·명령 계산. ROS I/O 없이 기록 재생 시험 가능."""
import math
import numpy as np
from farm_navigation.wall_reference import fit_wall


def wrap(value: float) -> float:
    return math.remainder(value, 2*math.pi)


def observe_walls(points: np.ndarray, config: dict) -> dict:
    """base 좌표의 제한 영역에서 벽 후보를 고른다. 후보는 시간 연속성 검사 전이다."""
    result = {}
    bearings = np.degrees(np.arctan2(points[:,1], points[:,0]))
    ranges = np.linalg.norm(points, axis=1)
    for name, center in [('left',90), ('right',-90),
                         ('front',0) if config.get('direction') == 'forward' else ('rear',180)]:
        section = config['walls'][name]
        delta = (bearings-center+180)%360-180
        selected = points[(abs(delta)<section['half_sector_deg']) &
                          (ranges<config['max_range_m'])]
        try:
            wall = fit_wall(selected, config['fit_threshold_m'], config['min_points'],
                            section['min_ratio'], config['min_span_m'])
            angle = wrap(wall['normal_angle_rad']-math.radians(center))
            if (abs(angle)>config['max_wall_angle_rad'] or
                    wall['residual_rms_m']>config['max_rms_m']):
                continue
            # 정상 통로와 거리 차이가 큰 옆 벽은 기준으로 채택하지 않는다.
            if name in ('left', 'right') and abs(wall['distance_m']-section['target_m'])>config['side_capture_m']:
                continue
            result[name] = dict(wall, angle=angle)
        except ValueError:
            continue
    return result


class StableWalls:
    """odom 좌표의 동일 평면만 누적한다. 다른 평면이면 기존 기준을 유지하고 재관측한다."""
    def __init__(self, config: dict) -> None:
        self.c=config; self.anchor={}; self.count={}; self.last_stamp={}

    def update(self, walls: dict, odom: np.ndarray, stamp: float) -> dict:
        ready={}
        for name in self.c['walls']:
            if name not in walls:
                self.count[name]=0
                continue
            wall=walls[name]; n=odom[:2,:2]@np.array(wall['normal_xy'])
            distance=wall['distance_m']+float(n@odom[:2,3])
            old=self.anchor.get(name)
            if old is not None and (abs(wrap(math.atan2(n[1],n[0])-old[0]))>self.c['plane_angle_jump_rad'] or
                                    abs(distance-old[1])>self.c['plane_jump_m']):
                self.count[name]=0
                continue
            if self.last_stamp.get(name)==stamp:
                continue  # 동일 스캔을 여러 번 안정 관측으로 세지 않는다.
            # 센서 최신성과 처리된 프레임 간격을 분리한다. 벽 연속성 검사는 위에서 유지한다.
            if stamp-self.last_stamp.get(name,stamp)>self.c.get('tracking_gap_s',self.c['max_age_s']):
                self.count[name]=0
            self.last_stamp[name]=stamp
            self.count[name]=self.count.get(name,0)+1
            if old is None:self.anchor[name]=(math.atan2(n[1],n[0]),distance)
            if self.count[name]>=self.c['stable_frames']:ready[name]=wall
        return ready


def reverse_command(config: dict, walls: dict, yaw_error: float, blend: float) -> tuple:
    """후진 조향 부호: 왼쪽 벽에 가까우면 양의 회전으로 뒤쪽을 오른쪽으로 보낸다."""
    sides=[name for name in ('left','right') if name in walls]
    angle=float(np.mean([walls[n]['angle']-config['walls'][n]['target_angle_rad'] for n in sides])) if sides else 0.
    offsets=[]
    if 'left' in walls:offsets.append(config['walls']['left']['target_m']-walls['left']['distance_m'])
    if 'right' in walls:offsets.append(walls['right']['distance_m']-config['walls']['right']['target_m'])
    lateral=float(np.mean(offsets)) if offsets else 0.
    desired=angle+max(-config['max_steer_angle_rad'],min(config['max_steer_angle_rad'],config['lateral_gain']*lateral))
    omega=(1-blend)*config['heading_gain']*yaw_error+blend*config['heading_gain']*desired
    omega=max(-config['max_angular_rps'],min(config['max_angular_rps'],omega))
    speed=config['speed_mps']
    rear=walls.get('rear')
    if rear:
        remaining=rear['distance_m']-config['walls']['rear']['target_m']
        if remaining<=config['distance_tolerance_m']:return 0.,0.,'VERIFY_WALL_STOP'
        speed=min(speed,max(config['min_speed_mps'],config['distance_gain']*remaining))
    return -speed,omega,'REVERSE_WALL_TRACK' if blend>0 else 'REVERSE_ODOM'


def arrival_matches(config: dict, walls: dict) -> bool:
    if 'rear' not in walls:return False
    if abs(walls['rear']['distance_m']-config['walls']['rear']['target_m'])>config['distance_tolerance_m']:return False
    sides=[name for name in ('left','right') if name in walls]
    if not sides:return False
    return all(abs(walls[n]['distance_m']-config['walls'][n]['target_m'])<=config['lateral_tolerance_m'] and
               abs(wrap(walls[n]['angle']-config['walls'][n]['target_angle_rad']))<=config['angle_tolerance_rad'] for n in sides)


class ArrivalSettler:
    """정상 관측 구간만 누적한다. 짧은 공백은 보존하되 공백 시간을 더하지 않는다."""
    def __init__(self, required_s: float, gap_s: float, min_samples: int = 1) -> None:
        self.required_s=required_s;self.gap_s=gap_s;self.min_samples=min_samples
        self.reset()

    def reset(self) -> None:
        self.elapsed=0.;self.last_good=None;self.previous_stamp=None;self.samples=0;self.last_stamp=None

    def pause(self, now: float) -> None:
        if self.last_good is not None and now-self.last_good>self.gap_s:
            self.reset()
        self.previous_stamp=None

    def observe(self, stamp: float, now: float, valid: bool) -> bool:
        if not valid or (self.last_stamp is not None and stamp<=self.last_stamp):
            self.reset();return False
        if self.last_good is not None and now-self.last_good>self.gap_s:
            self.reset()
        if self.previous_stamp is not None:
            delta=stamp-self.previous_stamp
            # 중복·역행 시각이나 콜백 정체 구간으로 완료 시간을 채우지 않는다.
            if delta<=0:
                self.reset();return False
            if delta>self.gap_s:
                self.reset()
            else:
                self.elapsed+=min(delta, max(0.,now-self.last_good))
        self.previous_stamp=stamp;self.last_stamp=stamp;self.last_good=now;self.samples+=1
        return self.elapsed>=self.required_s and self.samples>=self.min_samples


def forward_command(config: dict, walls: dict, yaw_error: float, blend: float) -> tuple:
    """전진은 후진과 횡오차 조향 부호가 반대다. 전방 벽을 정지 거리 기준으로 쓴다."""
    adapted = dict(config, lateral_gain=-config['lateral_gain'],
                   walls={**config['walls'], 'rear': config['walls']['front']})
    observed = dict(walls)
    if 'front' in walls:
        observed['rear'] = walls['front']
    v, w, state = reverse_command(adapted, observed, yaw_error, blend)
    return -v, w, state.replace('REVERSE', 'FORWARD')


def forward_arrival_matches(config: dict, walls: dict) -> bool:
    """실측 전방·측면 벽으로 완료 판정. 전방 벽 각도도 티칭 자세와 비교한다."""
    if 'front' not in walls:
        return False
    adapted = dict(config, walls={**config['walls'], 'rear': config['walls']['front']})
    observed = dict(walls, rear=walls['front'])
    return (arrival_matches(adapted, observed) and
            abs(wrap(walls['front']['angle']-config['walls']['front']['target_angle_rad']))
            <= config['angle_tolerance_rad'])
