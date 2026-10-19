"""Assigned-fruit tracking using native detections, fixed ROI and image continuity.

No simulator pose, color override, contact, or expert command enters this module.
An existing ID is preserved; ambiguous or stale observations stay invalid.
"""
import numpy as np
from .tracking import TrackManager


def bbox_iou(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != (4,) or b.shape != (4,) or not np.isfinite(np.r_[a, b]).all():
        return 0.
    area_a, area_b = np.prod(np.maximum(0, a[2:]-a[:2])), np.prod(np.maximum(0, b[2:]-b[:2]))
    intersection = np.prod(np.maximum(0, np.minimum(a[2:], b[2:])-np.maximum(a[:2], b[:2])))
    union = area_a+area_b-intersection
    return float(intersection/union) if union > 0 else 0.


class AssignedFruitTracker(TrackManager):
    def __init__(self, roi):
        super().__init__(allow_provisional=True, deduplicate=True)
        self.roi = np.asarray(roi, float)
        if self.roi.shape != (2, 3) or not np.isfinite(self.roi).all() or np.any(self.roi[0] >= self.roi[1]):
            raise ValueError('Finite fixed assignment ROI required')
        self.box = None
        self.camera = None
        self.last_update = {}

    def assign(self, now, target_id=None, label=None):
        result = super().assign(now, target_id, label)
        if result:
            self.tracks = {result: self.tracks[result]}
        return result

    def update(self, records, now):
        if not np.isfinite(now) or now < self.now:
            raise ValueError('Clock reset requires a new tracker')
        selected = self.tracks.get(self.selected)
        if selected is None:
            scoped = []
            for record in records:
                point = record.get('grasp_estimate_arm_m')
                if point is not None and np.all(np.asarray(point) >= self.roi[0]) and np.all(np.asarray(point) <= self.roi[1]):
                    scoped.append(record)
            result = super().update(scoped, now)
            self.last_update = dict(reason='initial_fixed_roi',candidates=len(scoped),selected=None)
            # Remember initial boxes per track so assignment has an image anchor.
            self.initial_boxes = {}
            for key, track in self.tracks.items():
                matches = [r for r in scoped if r['label'] == track['label'] and r.get('grasp_estimate_arm_m') is not None
                           and np.linalg.norm(np.asarray(r['grasp_estimate_arm_m'])-track['position_m']) < 1e-8]
                if matches:
                    self.initial_boxes[key] = (matches[0].get('bbox'),matches[0]['camera_id'])
            return result
        if self.box is None and self.selected in getattr(self,'initial_boxes',{}):
            self.box,self.camera=self.initial_boxes[self.selected]
        candidates=[]
        for record in records:
            point=record.get('grasp_estimate_arm_m')
            if not record.get('candidate_valid') or record['label'] != selected['label'] or point is None:
                continue
            point=np.asarray(point,float)
            if point.shape != (3,) or not np.isfinite(point).all() or not 0 <= now-record['stamp_s'] <= self.ttl:
                continue
            distance=float(np.linalg.norm(point-selected['position_m']))
            overlap=bbox_iou(self.box,record.get('bbox',[])) if self.box is not None and record['camera_id']==self.camera else 0.
            # Image continuity can recover a moderate native-depth jump. Reject
            # arbitrary distant same-color fruit even if the original ID is old.
            if distance<=self.gate or (overlap>=.25 and distance<=.12):
                area=float(np.prod(np.maximum(0,np.asarray(record['bbox'])[2:]-np.asarray(record['bbox'])[:2])))
                candidates.append((record,point,distance,overlap,area))
        self.now=now
        if candidates:
            candidates.sort(key=lambda x:(x[3],x[4],float(x[0].get('confidence',0))),reverse=True)
            winner=candidates[0]
            conflicting=[c for c in candidates[1:] if np.linalg.norm(c[1]-winner[1])>.025
                         and c[3]>=max(.1,winner[3]*.8)]
            if not conflicting:
                record,point,distance,overlap,_=winner
                if record['stamp_s'] >= selected['stamp_s']:
                    selected.update(position_m=point,stamp_s=record['stamp_s'],control_valid=record.get('control_valid',False))
                    self.box,self.camera=record.get('bbox'),record['camera_id']
                self.last_update=dict(reason='assigned_image_depth_match',candidates=len(candidates),
                    distance_m=distance,image_iou=overlap,selected=self.selected)
                return self.snapshot(now)
            reason='ambiguous_assigned_candidates'
        else:
            reason='no_assigned_candidate'
        self.last_update=dict(reason=reason,candidates=len(candidates),selected=self.selected)
        return self.snapshot(now)
