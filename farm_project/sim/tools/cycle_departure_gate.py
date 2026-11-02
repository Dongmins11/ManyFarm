"""교통 미연결 시험의 출발 순서. 실제 상태와 공통 그래프를 사용하며 주행을 대체하지 않는다."""
import json
import math
from dataclasses import fields
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def path_distance(point,points):
    from farm_navigation.route import project
    return min((project(point,a,b)[0] for a,b in zip(points,points[1:]) if a!=b),
               default=math.dist(point,points[0]))

def choose_first(harvest,transport,routes,clearance):
    def blocks(point,route):
        distance=path_distance(point,route);initial=math.dist(point,route[0])
        # 인계 직후 여유 원이 겹쳐도 전 경로가 더 접근하지 않는 이탈은 허용한다.
        return distance<=clearance and (initial>clearance or distance<initial-1e-6)
    blocked=blocks(harvest,routes['transport'])
    if blocked and blocks(transport,routes['harvest']):
        raise RuntimeError('두 로봇이 서로의 출발 경로를 점유: 출발 금지, 교통 재계획 필요')
    return 'harvest' if blocked else 'transport'

class DepartureGate:
    def __init__(self,base,node,wait,record):
        from farm_interfaces.msg import RobotStatus
        from rclpy.qos import qos_profile_sensor_data
        from rosidl_runtime_py.convert import message_to_ordereddict
        self.node,self.wait,self.record=node,wait,record
        self.latest={};self.subscriptions=[]
        for role in ('harvest','transport'):
            def observe(msg,role=role):
                self.latest[role]=(dict(message_to_ordereddict(msg)),node.get_clock().now().nanoseconds)
            self.subscriptions.append(node.create_subscription(RobotStatus,'/'+role+'_01/status',observe,qos_profile_sensor_data))
        self.base=base

    def pose(self,role):
        data,stamp=self.latest.get(role,({},0))
        age=(self.node.get_clock().now().nanoseconds-stamp)/1e9
        pose=data.get('pose',{})
        if not 0<=age<=1 or pose.get('frame_id')!='map':return None
        if data.get('state')=='ERROR':raise RuntimeError(role+' 출발 감시 오류: '+data.get('error_message',''))
        p=pose['position'];value=(p['x'],p['y'],pose['yaw'])
        return value if all(math.isfinite(x) for x in value) else None

    def plan(self):
        from farm_navigation.configuration import read_mapping,load_nav2_parameters
        from farm_navigation.navigation_types import NavigationSettings
        from farm_navigation.route import RouteGraph
        from farm_common.station_return import Station,plan_station_return
        self.wait(lambda:all(self.pose(r) is not None for r in ('harvest','transport')),180,'출발 순서 현재 위치 확인')
        profiles={r:read_mapping(self.base/'runtime'/f'{r}_runtime.{"yaml" if r=="harvest" else "json"}') for r in ('harvest','transport')}
        settings={};graphs={};radii={}
        for role,p in profiles.items():
            config=read_mapping(ROOT/p['navigation_policy']) if p.get('navigation_policy') else {}
            config.update(p.get('navigation',{}))
            if role=='harvest':config.update(p.get('station_return_navigation',{}))
            settings[role]=NavigationSettings(**{k:v for k,v in config.items() if k in {f.name for f in fields(NavigationSettings)}})
            graphs[role]=RouteGraph(ROOT/p['route_graph'])
            nav=load_nav2_parameters(ROOT/p['nav_params'],ROOT)
            cost=nav['local_costmap']['local_costmap']['ros__parameters']
            polygon=cost['footprint'];polygon=json.loads(polygon) if isinstance(polygon,str) else polygon
            radii[role]=max(math.hypot(*v) for v in polygon)+float(cost.get('footprint_padding',0))
        h=self.pose('harvest');t=self.pose('transport')
        p=profiles['harvest'];station=read_mapping(ROOT/p['station_config'])['stations']['harvest_01']
        hp,reverse,audit=plan_station_return(graphs['harvest'],Station(station['station_id'],tuple(station['xy_m']),station['yaw_rad']),h[:2],h[2],settings['harvest'])
        p=profiles['transport'];dest=read_mapping(ROOT/p['destinations'])['destinations']['SORT_01']
        ts=settings['transport'];tp=graphs['transport'].plan(t[:2],graphs['transport'].nodes[dest['approach_node_id']],ts.max_start_distance_m,ts.max_goal_distance_m)
        self.routes={'harvest':hp.points,'transport':tp.points}
        self.clearance=sum(radii.values())+sum(s.arrival_tolerance_m for s in settings.values())
        first=choose_first(h[:2],t[:2],self.routes,self.clearance)
        self.record('departure_order',first=first,poses={'harvest':h,'transport':t},routes=self.routes,clearance_m=self.clearance,harvest_plan=audit)
        return first

    def cleared(self,leader):
        follower='transport' if leader=='harvest' else 'harvest'
        pose=self.pose(leader)
        if pose is None:return False
        distance=path_distance(pose[:2],self.routes[follower])
        if distance<=self.clearance:return False
        self.record('departure_clear',leader=leader,pose=pose,distance_m=distance,required_m=self.clearance)
        return True

    def close(self):
        for sub in self.subscriptions:self.node.destroy_subscription(sub)
