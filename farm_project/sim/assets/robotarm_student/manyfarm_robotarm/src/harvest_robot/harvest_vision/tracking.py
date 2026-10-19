"""Conservative arm-frame tracking. No simulator state or actuator dependency."""
import numpy as np


class TrackManager:
    def __init__(self, frame_id='arm_2/base_link', clock_id='simulation', *, ttl=.3,
                 gate=.06, retention=2., allow_provisional=False, deduplicate=False):
        if not 0 < ttl <= retention or gate <= 0: raise ValueError('Invalid tracking limits')
        self.frame_id,self.clock_id=frame_id,clock_id
        self.ttl,self.gate,self.retention=ttl,gate,retention
        self.allow_provisional=allow_provisional
        self.deduplicate=deduplicate
        self.tracks={};self.serial=0;self.now=-float('inf');self.selected=None

    def update(self, records, now):
        if not np.isfinite(now) or now < self.now: raise ValueError('Clock reset requires new manager')
        self.now=now
        # Process cameras independently; one detection per track per camera.
        cameras=sorted(set(d['camera_id'] for d in records))
        for camera in cameras:
            candidates=[]
            for d in records:
                if d['camera_id']!=camera: continue
                if d['frame_id']!=self.frame_id or d['clock_id']!=self.clock_id:
                    raise ValueError('Frame/clock mismatch')
                stamp=d['stamp_s'];point=d.get('grasp_estimate_arm_m')
                if not d.get('candidate_valid') or (not self.allow_provisional and not d.get('control_valid')): continue
                if not np.isfinite(stamp) or not 0 <= now-stamp <= self.ttl or point is None: continue
                point=np.asarray(point,dtype=float)
                if point.shape!=(3,) or not np.isfinite(point).all(): continue
                candidates.append((d,point))
            if self.deduplicate:
                kept=[]
                def coverage(item):
                    box=np.asarray(item[0].get('bbox',[]))
                    area=float(np.prod(np.maximum(0,box[2:]-box[:2]))) if box.shape==(4,) and np.isfinite(box).all() else 0.
                    return area,float(item[0].get('confidence',0))
                # Prefer full-object boxes to high-confidence partial masks.
                for d,point in sorted(candidates,key=coverage,reverse=True):
                    duplicate=False
                    for other,p in kept:
                        if d['label']!=other['label'] or np.linalg.norm(point-p)>.025:continue
                        a=np.asarray(d.get('bbox',[]));b=np.asarray(other.get('bbox',[]))
                        if a.shape!=(4,) or b.shape!=(4,) or not np.isfinite(np.r_[a,b]).all():continue
                        areas=[float(np.prod(np.maximum(0,x[2:]-x[:2]))) for x in (a,b)]
                        if min(areas)<=0:continue
                        intersection=float(np.prod(np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2]))))
                        iou=intersection/(sum(areas)-intersection)
                        if (intersection/min(areas)>=.85 or iou>=.65) and min(areas)/max(areas)>=.45:
                            duplicate=True;break
                    if not duplicate:kept.append((d,point))
                candidates=kept
            associations=[]
            for d,point in candidates:
                nearby=[key for key,t in self.tracks.items() if t['label']==d['label']
                        and (t['completed'] or now-t['stamp_s']<=self.retention)
                        and np.linalg.norm(point-t['position_m'])<=self.gate]
                associations.append(nearby)
            for index,(d,point) in enumerate(candidates):
                nearby=associations[index]
                # Refuse merges/splits/crossings instead of silently swapping ID.
                if len(nearby)>1: continue
                if nearby:
                    key=nearby[0]
                    if sum(key in x for x in associations)>1: continue
                    t=self.tracks[key]
                    if t['completed'] or d['stamp_s']<t['stamp_s']: continue
                    t.update(position_m=point,stamp_s=d['stamp_s'],control_valid=d.get('control_valid',False))
                else:
                    # Same-frame duplicate detections do not create competing IDs.
                    if any(j!=index and o['label']==d['label'] and np.linalg.norm(q-point)<=self.gate
                           for j,(o,q) in enumerate(candidates)): continue
                    self.serial+=1;key=f'fruit-{self.serial:06d}'
                    self.tracks[key]=dict(label=d['label'],position_m=point,stamp_s=d['stamp_s'],completed=False,
                                          control_valid=d.get('control_valid',False))
        return self.snapshot(now)

    def snapshot(self, now):
        if not np.isfinite(now) or now<self.now: raise ValueError('Invalid clock')
        return {k:dict(t,position_m=t['position_m'].tolist(),valid=bool(not t['completed'] and 0<=now-t['stamp_s']<=self.ttl))
                for k,t in self.tracks.items()}

    def assign(self, now, target_id=None, label=None):
        if self.selected is not None: raise RuntimeError('Assignment already latched')
        candidates={k:t for k,t in self.snapshot(now).items() if t['valid'] and (label is None or t['label']==label)}
        if target_id is None:
            if not candidates: return None
            target_id=min(candidates,key=lambda k:(candidates[k]['position_m'][2],k))
        if target_id not in candidates: raise ValueError('Target unavailable')
        self.selected=target_id
        return target_id

    def observation(self, now):
        t=self.snapshot(now).get(self.selected)
        if t is None: return dict(target_id=self.selected,position_m=[0.,0.,0.],valid=False,age_s=self.ttl)
        return dict(target_id=self.selected,position_m=t['position_m'] if t['valid'] else [0.,0.,0.],
                    valid=t['valid'],age_s=min(self.ttl,max(0.,now-t['stamp_s'])))

    def finish(self, *, success, evidence):
        if self.selected is None or not evidence: raise ValueError('Require assignment and external result evidence')
        if success: self.tracks[self.selected]['completed']=True
        self.selected=None
