"""곡선 시험 서버의 분리 설정과 속도 전달 조건. 기존 주행 설정을 수정하지 않는다."""
from copy import deepcopy
import math
from .transfer_arc import trial_profile


def isolated_parameters(controller: dict, costmap: dict, prefix: str, scan_topic: str, odom_topic: str) -> dict:
    """실행 중 costmap 수치는 보존하고 독립 controller의 플러그인만 선택한다."""
    if not prefix.startswith('/') or not scan_topic.startswith('/') or not odom_topic.startswith('/'):
        raise ValueError('절대 ROS 이름 필요')
    if controller.get('enable_stamped_cmd_vel', False):
        raise ValueError('이번 연결은 기존 Twist 입력 환경에 한정한다')
    if not costmap.get('plugins') or costmap.get('global_frame') != 'odom':
        raise ValueError('실행 중 odom local costmap 필요')
    if not costmap.get('footprint') or costmap.get('resolution', 0) <= 0:
        raise ValueError('실행 중 footprint와 해상도 필요')
    cp = deepcopy(costmap)
    for plugin in cp['plugins']:
        for source in cp.get(plugin+'.observation_sources','').split():
            key=plugin+'.'+source
            if cp.get(key+'.data_type') != 'LaserScan':
                raise ValueError('확인하지 않은 센서 형식: '+key)
            cp[key+'.topic']=scan_topic
    server={
        'use_sim_time':controller.get('use_sim_time',False),
        'controller_frequency':controller.get('controller_frequency',20.0),
        'enable_stamped_cmd_vel':False, 'odom_topic':odom_topic,
        'controller_plugins':['TransferArc'],
        'goal_checker_plugins':['transfer_arc_goal'],
        'progress_checker_plugins':['transfer_arc_progress'],
        'failure_tolerance':0.0, 'bond_heartbeat_period':0.0,
        'min_x_velocity_threshold':controller.get('min_x_velocity_threshold',.001),
        'min_y_velocity_threshold':controller.get('min_y_velocity_threshold',.001),
        'min_theta_velocity_threshold':controller.get('min_theta_velocity_threshold',.001),
    }
    for plugin,values in trial_profile().items():
        server.update({plugin+'.'+key:value for key,value in values.items()})
    # 빈 배열은 ROS YAML 형식 판정이 불가능하므로 생략한다. 기본 빈 값으로 유지한다.
    cp={k:v for k,v in cp.items() if v is not None and v != []}
    return {prefix+'/controller_server':{'ros__parameters':server},
            prefix+'/local_costmap/local_costmap':{'ros__parameters':cp}}


class CommandGate:
    """명시 실행 중에만 새 명령을 전달한다. 이상은 유지해 후속 명령도 차단한다."""
    def __init__(self, *, direction: str = 'reverse_left') -> None:
        # 기존 호출은 후진 좌회전만 허용한다. 복귀는 명시 선택하며 부호만 대칭이다.
        if direction not in ('reverse_left', 'forward_right', 'retreat', 'align'):
            raise ValueError('곡선 gate 방향은 reverse_left 또는 forward_right여야 합니다.')
        self._direction = direction
        self._sign = 1 if direction == 'reverse_left' else -1
        self.enabled=False
        self.error=''
        self.last_received=None
        self.started=None

    def arm(self, now: float) -> None:
        if self.error: raise RuntimeError(self.error)
        self.enabled=True;self.started=now;self.last_received=None

    def close(self) -> None:
        self.enabled=False

    def accept(self, linear: float, angular: float, now: float, conflict: bool=False) -> bool:
        if not self.enabled or self.error:return False
        if self.expired(now):return False
        in_range = (-.025 <= self._sign*linear <= 0.000001 and -.001 <= self._sign*angular <= .18)
        if self._direction == 'retreat':
            in_range = -.010000001 <= linear <= .000001 and abs(angular) <= .05
        elif self._direction == 'align':
            in_range = abs(linear) <= .000001 and abs(angular) <= .030000001
        if conflict or not all(math.isfinite(x) for x in (linear,angular)) or not in_range:
            self.error='다른 동작 또는 곡선 속도 범위 위반';self.enabled=False;return False
        self.last_received=now
        return True

    def expired(self, now: float) -> bool:
        if not self.enabled:return False
        # 액션 수락 전에는 속도를 전달하지 않았으므로 5초의 응답 대기만 허용한다.
        age=now-(self.last_received if self.last_received is not None else self.started)
        if age > (.3 if self.last_received is not None else 5.0):
            self.error='곡선 속도 입력 시간 초과';self.enabled=False;return True
        return False
