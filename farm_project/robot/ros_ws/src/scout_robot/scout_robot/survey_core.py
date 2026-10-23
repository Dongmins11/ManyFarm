"""Sensor-only B survey geometry. No USD, ground truth or ROS imports."""
from . import survey_policy
from .survey_policy import SurveyPolicy
import math
import numpy as np
from .b_planner import Config, Fruit, PlanResult, extend_plan


def matrix_from_pose(position, quaternion):
    x,y,z,w = map(float,quaternion)
    n = math.sqrt(x*x+y*y+z*z+w*w)
    if n < 1e-10: raise ValueError('Invalid quaternion')
    x,y,z,w = x/n,y/n,z/n,w/n
    T=np.eye(4)
    T[:3,:3]=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
              [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
              [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
    T[:3,3]=position
    return T


def transform_points(T, points):
    a=np.asarray(points,dtype=float).reshape(-1,3)
    return a@np.asarray(T)[:3,:3].T+np.asarray(T)[:3,3]


class StraightBed:
    def __init__(self, route, cfg):
        self.origin=np.array(route[0][1:3],dtype=float)
        end=np.array(route[-1][1:3],dtype=float)
        self.length=float(np.linalg.norm(end-self.origin))
        if self.length < .1: raise ValueError('Bed route is too short')
        self.t=(end-self.origin)/self.length
        self.n=np.array([-self.t[1],self.t[0]])
        self.yaw=math.atan2(self.t[1],self.t[0])
        last=-1.
        for _,x,y,_ in route:
            d=np.array([x,y])-self.origin;s=float(d@self.t)
            if abs(d@self.n)>.01 or s<=last: raise ValueError('B stage requires an ordered straight route')
            last=s
        self.cfg=cfg
        self.bed_n=float(cfg['bed_plane_from_route_m'])
        h=cfg['harvest'];yaw=self.yaw+float(h['heading_offset_rad'])
        R=np.array([[math.cos(yaw),-math.sin(yaw)],[math.sin(yaw),math.cos(yaw)]])
        arm=R@np.array(h['mount_xy_base_m']);work=R@np.array(h['work_offset_xy_base_m'])
        if abs(work@self.t)>1e-5 or work@self.n<=0:
            raise ValueError('Harvest work offset must point toward bed, perpendicular to route')
        self.harvest_yaw=math.atan2(math.sin(yaw),math.cos(yaw))
        self.plan_cfg=Config(width=h['width_m'],margin=h['side_margin_m'],
            mount_x=float(arm@self.t),mount_y=float(arm@self.n),mount_z=h['height_reference_m'],
            work_distance=float(work@self.n),depth=h['depth_m'],z_min=h['height_offsets_m'][0],
            z_max=h['height_offsets_m'][1],bed_y=self.bed_n,route_start=0.,route_end=self.length,
            range_tolerance=h.get('range_tolerance_m',0.0),
            depth_tolerance=h.get('depth_tolerance_m',0.0),
            membership_margin=h.get('membership_margin_m',h['side_margin_m']))
        self.plan_cfg.validate()

    def local(self, xyz):
        p=np.array(xyz);d=p[:2]-self.origin
        return [float(d@self.t),float(d@self.n),float(p[2])]

    def world(self,s,n,z=0.):
        xy=self.origin+self.t*s+self.n*n
        return [float(xy[0]),float(xy[1]),float(z)]

    def viewpoints(self,K,T_base_camera,width,height,preprocess,overlap):
        # Use calibrated mount in the planned heading, not current localization error.
        if not 0 <= overlap < 1: raise ValueError('Overlap must be in [0,1)')
        R=np.array([[math.cos(self.yaw),-math.sin(self.yaw),0],[math.sin(self.yaw),math.cos(self.yaw),0],[0,0,1]])
        T=np.eye(4);T[:3,:3]=R;T[:2,3]=self.origin
        C=T@np.array(T_base_camera);eye=C[:3,3];rot=C[:3,:3];K=np.array(K)
        normal3=np.r_[self.n,0.];along3=np.r_[self.t,0.]
        if np.dot(rot[:,2],normal3)<.5: raise ValueError('Camera does not face configured bed side')
        intervals=[]
        for z in preprocess['height_band_m']:
            limits=[]
            for u in [width*preprocess['edge_fraction'],width*(1-preprocess['edge_fraction'])]:
                a=rot[:,0]-((u-K[0,2])/K[0,0])*rot[:,2]
                plane_point=np.array(self.world(0,self.bed_n,z))
                denom=a@along3
                if abs(denom)<1e-8: raise ValueError('Degenerate camera orientation')
                s=-float(a@(plane_point-eye))/denom
                p=rot.T@(plane_point+along3*s-eye)
                v=K[1,1]*p[1]/p[2]+K[1,2]
                if p[2]<=0 or not 0<=v<=height: raise ValueError('Work height outside camera FOV')
                limits.append(s)
            intervals.append(sorted(limits))
        lo=max(a[0] for a in intervals);hi=min(a[1] for a in intervals);U=hi-lo
        if U<=0: raise ValueError('Empty camera coverage')
        if self.length<=U: stops=[self.length/2-(lo+hi)/2]
        else:
            count=1+math.ceil((self.length-U)/(U*(1-overlap)))
            stops=np.linspace(-lo,self.length-hi,count).tolist()
        if any(s<0 or s>self.length for s in stops): raise ValueError('Observation stop outside route')
        return {'stops_s_m':stops,'relative_coverage_m':[lo,hi],'usable_width_m':U,
                'overlap_fraction':overlap,'route_length_m':self.length}


class Survey:
    def __init__(self, bed, prefix, association_distance, *, policy: SurveyPolicy | None = None):
        self._policy = survey_policy.ACTIVE_SURVEY_POLICY if policy is None else policy
        if not isinstance(self._policy, SurveyPolicy):
            raise ValueError("policy는 SurveyPolicy 타입이어야 합니다.")
        self.bed=bed;self.prefix=prefix;self.distance=float(association_distance)
        if not 0<self.distance<.5: raise ValueError('Invalid association distance')
        self.fruits=[];self.plan=PlanResult();self.observations=0
        self.window_segments={}

    def ingest(self,detections,segment_id=None):
        segment_id=segment_id or f'{self.prefix}_S{self.observations+1:03d}'
        # 선택한 방식의 대표 좌표와 일대일 매칭합니다. 거리 매칭 자체는 두 방식이 같습니다.
        pairs=[]
        for i,d in enumerate(detections):
            p=np.asarray(d['position_map_m'],float)
            if p.shape!=(3,) or not np.isfinite(p).all(): raise ValueError('Invalid detection XYZ')
            for j,f in enumerate(self.fruits):
                dist=float(np.linalg.norm(p-np.array(f['position_map_m'])))
                if dist<=self.distance:pairs.append((dist,i,j))
        assigned={};used=set()
        for _,i,j in sorted(pairs):
            if i not in assigned and j not in used:assigned[i]=j;used.add(j)
        for i,d in enumerate(detections):
            if i not in assigned:
                assigned[i]=len(self.fruits)
                self.fruits.append(dict(id=f'{self.prefix}_F{len(self.fruits)+1:04d}',
                    position_map_m=list(d['position_map_m']),class_name=d['class_name'],
                    position_first_map_m=list(d['position_map_m']),position_samples=[],
                    first_segment_id=segment_id,observed_segment_ids=[],
                    confidence=d['confidence'],seen_count=0,first_stamp_ns=d['stamp_ns']))
            f=self.fruits[assigned[i]];f['seen_count']+=1;f['last_stamp_ns']=d['stamp_ns']
            if segment_id not in f['observed_segment_ids']:f['observed_segment_ids'].append(segment_id)
            f['position_samples'].append({'stamp_ns':int(d['stamp_ns']),
                'position_map_m':list(d['position_map_m']),'confidence':float(d['confidence']),
                'segment_id':segment_id})
            samples=np.array([sample['position_map_m'] for sample in f['position_samples']])
            if self._policy is SurveyPolicy.MEDIAN_REVALIDATE:
                f['position_map_m']=np.median(samples,axis=0).tolist()
            else:
                # 최신 좌표·관측 이력은 아래에서 계속 갱신하되 대표 좌표는 고정합니다.
                f['position_map_m']=list(f['position_first_map_m'])
            f['position_latest_map_m']=list(d['position_map_m'])
            f['position_span_m']=np.ptp(samples,axis=0).tolist()
        # Recheck corrected coordinates against fixed windows before dispatch.
        observed=[Fruit(f['id'],*self.bed.local(f['position_map_m'])) for f in self.fruits]
        # Exclude out-of-section/context detections before calling ingest in server.
        self.plan=extend_plan(self.plan,observed,self.bed.plan_cfg,revalidate=self._policy is SurveyPolicy.MEDIAN_REVALIDATE);self.observations+=1
        for task in self.plan.tasks:self.window_segments.setdefault(task.task_id,segment_id)
        return [self.fruits[assigned[i]]['id'] for i in range(len(detections))]

    def windows(self):
        out=[]
        for task in self.plan.tasks:
            if not task.member_ids:continue
            d=task.to_dict();d['window_id']=f'{self.prefix}_W{task.task_id:03d}'
            d['segment_id']=self.window_segments[task.task_id]
            d['goal_pose']={'frame_id':'map','position':self.bed.world(task.base_x,task.base_y),'yaw':self.bed.harvest_yaw}
            d['corners_map_m']=[self.bed.world(s,n,z) for z in [task.window_z_min,task.window_z_max]
                for n in [task.window_y_min,task.window_y_max] for s in [task.window_x_min,task.window_x_max]]
            tol=self.bed.plan_cfg.range_tolerance
            d['range_tolerance_m']=tol
            depth_tol=self.bed.plan_cfg.depth_tolerance
            d['depth_tolerance_m']=depth_tol
            d['acceptance_corners_map_m']=[self.bed.world(s,n,z)
                for z in [task.window_z_min-tol,task.window_z_max+tol]
                for n in [task.window_y_min-tol-depth_tol,task.window_y_max+tol+depth_tol]
                for s in [task.safe_x_min-tol,task.safe_x_max+tol]]
            d['expected_count']=len(task.member_ids);out.append(d)
        # 추가 관측으로 뒤늦게 생성된 창도 ID는 유지하고 실제 수확 진행 방향으로 반환한다.
        forward = (math.cos(self.bed.harvest_yaw), math.sin(self.bed.harvest_yaw))
        return sorted(out, key=lambda window: sum(
            window['goal_pose']['position'][i]*forward[i] for i in (0, 1)))

    def record(self):
        return {'fruits':self.fruits,'windows':self.windows(),'holds':[vars(h) for h in self.plan.holds],
                'observation_count':self.observations,'harvest_task_count':len(self.windows()),
                'total_expected_count':sum(len(t.member_ids) for t in self.plan.tasks),
                'survey_policy':self._policy.value,
                'position_semantics':'map-frame RGB-D surface position, not fruit center/grasp point',
                'position_fusion':('componentwise_median_all_observations; two observations use their midpoint'
                    if self._policy is SurveyPolicy.MEDIAN_REVALIDATE else 'first_observation_position'),
                'range_tolerance_m':self.bed.plan_cfg.range_tolerance,
                'depth_tolerance_m':self.bed.plan_cfg.depth_tolerance,
                'membership_margin_m':self.bed.plan_cfg.membership_margin,
                'reserved_empty_window_count':sum(not t.member_ids for t in self.plan.tasks),
                'identity_method':'B baseline greedy 3D one-to-one; identity errors remain possible'}
