"""벽 시험용 설정 투영과 속도 전달 정책. 기본 서버 파라미터를 수정하지 않는다."""
from copy import deepcopy
import math


def isolated_parameters(controller: dict, costmap: dict, prefix: str, scan: str, odom: str, config: dict) -> dict:
    if not all(v.startswith('/') for v in (prefix,scan,odom)):
        raise ValueError('절대 ROS 연결명 필요')
    if controller.get('enable_stamped_cmd_vel',False):raise ValueError('시험 연결은 Twist 전용')
    if costmap.get('global_frame')!='odom' or not costmap.get('footprint') or not costmap.get('plugins'):
        raise ValueError('실행 중 odom costmap·footprint 필요')
    cm=deepcopy(costmap)
    for layer in cm['plugins']:
        for source in cm.get(layer+'.observation_sources','').split():
            key=layer+'.'+source
            if cm.get(key+'.data_type')!='LaserScan':raise ValueError('지원하지 않는 센서 형식')
            cm[key+'.topic']=scan
    cm={k:v for k,v in cm.items() if v is not None and v!=[]}
    c=config['controller']
    server={'use_sim_time':controller.get('use_sim_time',False),'controller_frequency':20.,
            'enable_stamped_cmd_vel':False,'odom_topic':odom,'controller_plugins':['WallAlign'],
            'goal_checker_plugins':['wall_goal'],'progress_checker_plugins':['wall_progress'],
            'failure_tolerance':0.,'bond_heartbeat_period':0.,'publish_zero_velocity':True,
            'min_x_velocity_threshold':0.,'min_y_velocity_threshold':0.,'min_theta_velocity_threshold':0.,
            'WallAlign.plugin':'farm_wall_controller::WallController',
            'WallAlign.desired_linear_vel':c['max_linear'],'WallAlign.use_collision_detection':True,
            'WallAlign.max_allowed_time_to_collision_up_to_carrot':2.,
            'wall_goal.plugin':'farm_wall_controller::WallGoalChecker',
            'wall_progress.plugin':'nav2_controller::PoseProgressChecker',
            'wall_progress.required_movement_radius':.005,'wall_progress.required_movement_angle':.01745,
            'wall_progress.movement_time_allowance':10.}
    server.update({'wall_alignment.'+k:v for k,v in c.items()})
    return {prefix+'/controller_server':{'ros__parameters':server},
            prefix+'/local_costmap/local_costmap':{'ros__parameters':cm}}


class WallCommandGate:
    """벽 시험의 전진·양방향 회전만 허용. 관측/충돌은 upstream 검사와 별도로 확인한다."""
    def __init__(self, linear: float, angular: float) -> None:
        if not all(math.isfinite(v) and v>0 for v in (linear,angular)):raise ValueError('속도 한계 오류')
        self.linear=linear;self.angular=angular;self.enabled=False;self.error='';self.last=None;self.start=0.
    def arm(self, now: float) -> None:
        if self.error:raise RuntimeError(self.error)
        self.start=now;self.last=None;self.enabled=True
    def close(self) -> None:self.enabled=False
    def fail(self, message: str) -> None:self.error=message;self.enabled=False
    def accept(self, linear: float, angular: float, now: float) -> bool:
        if not self.enabled or self.expired(now):return False
        if not all(math.isfinite(x) for x in (linear,angular,now)) or not -1e-9<=linear<=self.linear+1e-9 or abs(angular)>self.angular+1e-9:
            self.fail('벽 접근 명령 범위 이탈');return False
        self.last=now;return True
    def expired(self, now: float) -> bool:
        if self.enabled and now-(self.last if self.last is not None else self.start)>(.3 if self.last is not None else 5.):
            self.fail('벽 접근 명령 만료');return True
        return False
