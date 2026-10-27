"""시뮬 정답 자세로 인계 정렬을 평가한다. 주행/마커 제어 입력으로 사용하지 않는다."""
import math
import numpy as np


def polygon(matrix: list, spec: dict) -> np.ndarray:
    center=np.asarray(spec['center_local_m']);half=np.asarray(spec['opening_size_m'])/2
    local=[center+[x*half[0],y*half[1],0] for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    return (np.asarray(matrix)@np.column_stack((local,np.ones(4))).T).T[:,:3]


def area(points: np.ndarray) -> float:
    if len(points)<3:return 0.
    return abs(float(np.sum(points[:,0]*np.roll(points[:,1],-1)-points[:,1]*np.roll(points[:,0],-1))))/2


def intersection(subject: np.ndarray, clip: np.ndarray) -> np.ndarray:
    def cross(a,b):return float(a[0]*b[1]-a[1]*b[0])
    output=list(subject)
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        inputs,output=output,[]
        if not inputs:break
        for start,end in zip([inputs[-1]]+inputs[:-1],inputs):
            ds,de=cross(b-a,start-a),cross(b-a,end-a)
            if (ds>=0)!=(de>=0):output.append(start+(end-start)*(ds/(ds-de)))
            if de>=0:output.append(end)
    return np.asarray(output)


class BasketAlignment:
    def __init__(self,spec: dict) -> None:
        self.spec=spec;self.previous=None;self.since=None
        self.minimum=float(spec.get('minimum_coverage',1.))
        if not 0<self.minimum<=1:raise ValueError('minimum_coverage는 0 초과1 이하')

    def sample(self,now: float,harvest: dict,transport: dict) -> dict:
        s=self.spec
        hp=polygon(harvest['T_world_evaluation_frames'][s['harvest']['frame']],s['harvest'])
        tp=polygon(transport['T_world_evaluation_frames'][s['transport']['frame']],s['transport'])
        if not np.isfinite(hp).all() or not np.isfinite(tp).all() or area(hp[:,:2])<=0:
            self.previous=None;self.since=None
            raise ValueError('바구니 평가 좌표 오류')
        coverage=area(intersection(hp[:,:2],tp[:,:2]))/area(hp[:,:2])
        delta=hp.mean(axis=0)-tp.mean(axis=0)
        stationary=all(abs(r['wheel_odom'][3])<s['stop_linear_mps'] and abs(r['wheel_odom'][4])<s['stop_angular_rps'] for r in [harvest,transport])
        world_stopped=False
        if self.previous is not None and 0<now-self.previous[0]<=.2:
            dt=now-self.previous[0]
            world_stopped=max(np.linalg.norm(hp.mean(axis=0)-self.previous[1]),np.linalg.norm(tp.mean(axis=0)-self.previous[2]))/dt<s['stop_linear_mps']
            for points,old_edge in [(hp,self.previous[3]),(tp,self.previous[4])]:
                edge=points[1,:2]-points[0,:2]
                yaw_delta=math.atan2(old_edge[0]*edge[1]-old_edge[1]*edge[0],float(old_edge@edge))
                world_stopped=world_stopped and abs(yaw_delta)/dt<s['stop_angular_rps']
        clearance=float(hp[:,2].min()-tp[:,2].max())
        aligned=coverage+1e-6>=self.minimum and clearance>0
        if aligned and stationary and world_stopped:
            self.since=now if self.since is None else self.since
        else:self.since=None
        held=0. if self.since is None else now-self.since
        self.previous=(now,hp.mean(axis=0),tp.mean(axis=0),hp[1,:2]-hp[0,:2],tp[1,:2]-tp[0,:2])
        return dict(sim_time_s=float(now),coverage=float(coverage),minimum_coverage=self.minimum,
            full_containment=bool(coverage>=1.-1e-6),center_delta_m=delta.tolist(),horizontal_distance_m=float(np.linalg.norm(delta[:2])),
            positive_height_clearance_m=clearance,aligned=bool(aligned),wheel_stopped=bool(stationary),world_stopped=bool(world_stopped),
            held_s=float(held),hold_pass=bool(held+1e-9>=s['hold_s']),
            harvest_corners_world=hp.tolist(),transport_corners_world=tp.tolist())
