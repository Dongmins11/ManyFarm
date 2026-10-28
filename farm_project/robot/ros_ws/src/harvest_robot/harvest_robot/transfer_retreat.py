"""벽 이탈의 경로 계산만 담당한다. 실행은 공통 Navigator/SpinClient에 맡긴다."""
import math
from dataclasses import dataclass
from farm_navigation.navigation_types import RoutePlan
from farm_navigation.transfer_arc import wrap


@dataclass(frozen=True)
class RetreatPlan:
    route: RoutePlan
    path: tuple
    target: tuple
    travel_heading: float
    distance: float


def retreat_plan(current: tuple, target: tuple, *, maximum: float = .2,
                 heading_limit: float = math.radians(15), spacing: float = .002) -> RetreatPlan:
    """현재 자세에서 저장 원호 끝점으로 후진한다. 전진/대각선 큰 이탈은 거절한다."""
    for pose in (current, target):
        if len(pose) != 3 or not all(type(v) in (int,float) and math.isfinite(v) for v in pose):
            raise ValueError('유한한 평면 자세 필요')
    if not all(math.isfinite(v) and v > 0 for v in (maximum,heading_limit,spacing)):
        raise ValueError('양의 경로 제한 필요')
    dx,dy=target[0]-current[0],target[1]-current[1]
    distance=math.hypot(dx,dy)
    if distance > maximum:
        raise ValueError('벽 이탈 최대 거리 초과')
    if distance <= .005:
        heading=current[2]
    else:
        heading=wrap(math.atan2(dy,dx)+math.pi)
        if (abs(wrap(heading-current[2])) > heading_limit
                or abs(wrap(heading-target[2])) > heading_limit):
            raise ValueError('저장 끝점이 후진 진행 방향 범위 밖입니다.')
    count=max(1,math.ceil(distance/spacing))
    path=tuple((current[0]+dx*i/count,current[1]+dy*i/count,heading) for i in range(count+1))
    # 명시적 yaw 없이 공통 build_path(reverse=True)가 차체 후진 방향을 만든다.
    route=RoutePlan('retreat','', 'odom',tuple(p[:2] for p in path),(),distance)
    return RetreatPlan(route,path,tuple(target),heading,distance)


def retreat_error(plan: RetreatPlan, pose: tuple) -> dict:
    """시작-끝 선분 이탈·후진 방향·한 번의 이동 범위를 감시한다."""
    if len(pose)!=3 or not all(math.isfinite(v) for v in pose):
        raise ValueError('현재 자세 오류')
    a=plan.path[0];b=plan.target
    length=max(plan.distance,1e-12)
    ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    dx,dy=pose[0]-a[0],pose[1]-a[1]
    progress=dx*ux+dy*uy
    cross=abs(dx*uy-dy*ux)
    if cross>.01 or progress<-.008 or progress>plan.distance+.008:
        raise RuntimeError('벽 이탈 경로 범위 초과')
    if abs(wrap(pose[2]-plan.travel_heading))>math.radians(15):
        raise RuntimeError('벽 이탈 방향 범위 초과')
    return {'position_error_m':math.dist(pose[:2],b[:2]),
            'heading_error_rad':abs(wrap(pose[2]-b[2])),
            'cross_track_m':cross,'progress_m':progress}


def retreat_profile(station: dict) -> dict:
    """기존 StationReverse RPP의 설정을 복사하고 시험 서버의 저속 값만 선택한다."""
    if station.get('plugin')!='farm_nav2_controller::ReverseRegulatedPurePursuitController':
        raise ValueError('기존 StationReverse RPP 필요')
    profile=dict(station)
    profile.update(desired_linear_vel=.01,min_approach_linear_velocity=.006,
        allow_reversing=True,use_rotate_to_heading=False,use_collision_detection=True,
        rotate_to_heading_angular_vel=.03,
        lookahead_dist=.04,min_lookahead_dist=.04,max_lookahead_dist=.04,
        use_velocity_scaled_lookahead_dist=False,use_fixed_curvature_lookahead=False,
        interpolate_curvature_after_goal=False,approach_velocity_scaling_dist=.04,
        regulated_linear_scaling_min_speed=.006,max_allowed_time_to_collision_up_to_carrot=2.0)
    return {'Retreat':profile,
        'retreat_goal':{'plugin':'nav2_controller::SimpleGoalChecker','stateful':False,
                        'xy_goal_tolerance':.005,'yaw_goal_tolerance':math.radians(14)},
        'retreat_progress':{'plugin':'nav2_controller::PoseProgressChecker',
            'required_movement_radius':.01,'required_movement_angle':.04,'movement_time_allowance':10.0}}


def alignment_path(pose: tuple, target_yaw: float) -> tuple:
    """재진입 위치에서 소각도 회전의 전체 footprint 검사에 사용할 자세열."""
    delta=wrap(target_yaw-pose[2])
    if not all(math.isfinite(v) for v in (*pose,target_yaw)) or abs(delta)>math.radians(15):
        raise ValueError('재진입 보정 각도 범위 초과')
    n=max(1,math.ceil(abs(delta)/.002))
    return tuple((pose[0],pose[1],wrap(pose[2]+delta*i/n)) for i in range(n+1))


def alignment_parameters(prefix: str, base_frame: str, *, use_sim_time: bool = False,
                         transform_tolerance: float = .5, odom_frame: str = 'odom') -> dict:
    """독립 Nav2 Spin 인스턴스. 같은 costmap/footprint를 구독한다."""
    return dict(use_sim_time=use_sim_time,behavior_plugins=['spin'],
        **{'spin.plugin':'nav2_behaviors::Spin'},local_frame=odom_frame,global_frame=odom_frame,
        robot_base_frame=base_frame,cycle_frequency=20.,transform_tolerance=transform_tolerance,
        local_costmap_topic=prefix+'/local_costmap/costmap_raw',global_costmap_topic=prefix+'/local_costmap/costmap_raw',
        local_footprint_topic=prefix+'/local_costmap/published_footprint',global_footprint_topic=prefix+'/local_costmap/published_footprint',
        min_rotational_vel=.03,max_rotational_vel=.03,rotational_acc_lim=1.,simulate_ahead_time=2.,
        enable_stamped_cmd_vel=False,bond_heartbeat_period=0.)


def alignment_footprint(parameters: dict) -> tuple:
    """costmap 차체 좌표 사각형과 padding을 읽는다. 발행 시각의 자세를 섞지 않는다."""
    import json
    points=json.loads(parameters['footprint'])
    padding=parameters['footprint_padding']
    if (not isinstance(points,list) or len(points)!=4 or
            type(padding) not in (int,float) or not math.isfinite(padding) or padding<0):
        raise ValueError('사각 footprint/padding 설정 오류')
    if any(not isinstance(v,list) or len(v)!=2 or
           any(type(x) not in (int,float) or not math.isfinite(x) for x in v) for v in points):
        raise ValueError('footprint 좌표 오류')
    hx=max(abs(v[0]) for v in points);hy=max(abs(v[1]) for v in points)
    if min(hx,hy)<=0 or any(abs(abs(x)-hx)>1e-9 or abs(abs(y)-hy)>1e-9 for x,y in points):
        raise ValueError('설정 footprint는 중심 대칭 사각형이어야 합니다.')
    if len(set((x>0,y>0) for x,y in points))!=4:
        raise ValueError('footprint 모서리 중복')
    return tuple((math.copysign(hx+padding,x),math.copysign(hy+padding,y)) for x,y in points)


def alignment_clearance(pose: tuple, target_yaw: float, footprint: list, grid: dict,
                        *, body_footprint: tuple) -> float:
    """발행 footprint는 크기 검증에만 사용하고 현재 자세로 차체 형상을 배치한다.

    서로 다른 시각의 world 좌표와 현재 자세를 역변환하지 않는다. padding을
    포함한 설정 형상과 발행 형상의 모든 점간 거리가 다르면 출력 전에 차단한다.
    """
    from farm_navigation.arc_clearance import check_grid
    for vertices in (footprint,body_footprint):
        if len(vertices)!=4 or any(len(v)!=2 or not all(math.isfinite(x) for x in v) for v in vertices):
            raise ValueError('사각 footprint 입력 오류')
    def distances(vertices):
        return sorted(math.dist(vertices[i],vertices[j]) for i in range(4) for j in range(i))
    if any(abs(a-b)>2e-5 for a,b in zip(distances(footprint),distances(body_footprint))):
        raise RuntimeError('발행 footprint와 padding 포함 설정 크기 불일치')
    c,s=math.cos(pose[2]),math.sin(pose[2])
    world=[(pose[0]+c*x-s*y,pose[1]+s*x+c*y) for x,y in body_footprint]
    return check_grid(alignment_path(pose,target_yaw),world,pose,grid)
