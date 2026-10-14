"""Corners -> two IPPE candidates -> map base pose, with explicit assets.

This module does not accept AMCL or fused TF as a pose prior. Registration and
mounts are inputs; it does not learn them from its own localization output.
"""
from copy import deepcopy
from dataclasses import dataclass
import math
import numpy as np
from .geometry import finite, transform, inverse, from_pose6, pose6, planar, covariance


def cv():
    import cv2
    return cv2


def square(edge):
    if not math.isfinite(edge) or edge <= 0:
        raise ValueError('positive_measured_tag_edge_required')
    h = edge/2
    return np.array([[-h,h,0],[h,h,0],[h,-h,0],[-h,-h,0]], dtype=float)


@dataclass
class Camera:
    width: int
    height: int
    k: np.ndarray
    d: np.ndarray
    optical_frame: str
    version: str
    rectified: bool = False
    rectification_r: np.ndarray | None = None
    pose_solver: str = 'ippe'

    def __post_init__(self):
        if self.pose_solver not in ('ippe','ippe_lm'):
            raise ValueError('unsupported_pose_solver')
        if type(self.width) is not int or type(self.height) is not int or min(self.width,self.height) <= 0:
            raise ValueError('valid_image_size_required')
        self.k = finite(self.k,(3,3))
        self.d = np.array(self.d,dtype=float).reshape(-1)
        if (len(self.d) not in (0,4,5,8) or not np.isfinite(self.d).all() or
                min(self.k[0,0],self.k[1,1]) <= 0 or
                not np.allclose(self.k[2],[0,0,1]) or abs(self.k[0,1])+abs(self.k[1,0]) > 1e-12):
            raise ValueError('unsupported_camera_model')
        if not self.optical_frame or not self.version:
            raise ValueError('camera_identity_required')
        r = np.eye(3) if self.rectification_r is None else finite(self.rectification_r,(3,3))
        t = np.eye(4); t[:3,:3] = r
        self.rectification_r = transform(t)[:3,:3]
        if self.rectified and np.any(self.d):
            raise ValueError('rectified_pixels_require_zero_distortion')
        if not self.rectified and not np.allclose(r,np.eye(3)):
            raise ValueError('raw_pixels_cannot_use_rectification_rotation')

    @classmethod
    def from_camera_info(cls, info, *, rectified, version, pose_solver='ippe'):
        if info['distortion_model'] not in ('plumb_bob','rational_polynomial'):
            raise ValueError('unsupported_distortion_model')
        if any(info.get('binning', [0,0])) or any(info.get('roi', [0,0,0,0])):
            raise ValueError('cropped_or_binned_camera_info_requires_explicit_adapter')
        if rectified:
            p = finite(np.array(info['p']).reshape(3,4),(3,4))
            if np.any(p[:,3]):
                raise ValueError('stereo_projection_requires_separate_adapter')
            return cls(info['width'],info['height'],p[:,:3],[],info['frame_id'],version,
                       True,np.array(info['r']).reshape(3,3),pose_solver)
        return cls(info['width'],info['height'],np.array(info['k']).reshape(3,3),info['d'],info['frame_id'],version,pose_solver=pose_solver)

    def project(self, t_camera_tag, edge):
        t = transform(t_camera_tag)
        if self.rectified:
            rect = np.eye(4); rect[:3,:3] = self.rectification_r
            t = rect @ t
        points = square(edge)
        if np.min((points @ t[:3,:3].T+t[:3,3])[:,2]) <= 0:
            raise ValueError('corner_behind_camera')
        rvec,_ = cv().Rodrigues(t[:3,:3])
        pixels,_ = cv().projectPoints(points,rvec,t[:3,3],self.k,self.d)
        return pixels.reshape(4,2)

    def solve(self, corners, edge):
        corners = finite(corners,(4,2))
        # Some IPPE/OpenCV builds lose precision close to a 180-degree in-plane
        # rotation. Solve in two equivalent optical bases and retain the pair
        # with the best reprojection fit. Corner identities and both pose
        # hypotheses remain intact; this is not an AMCL-based branch selection.
        normalized=cv().undistortPoints(corners.reshape(-1,1,2),self.k,self.d).reshape(4,2)
        quarter=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
        rotated=np.column_stack([-normalized[:,1],normalized[:,0]])
        choices=[]
        for basis,pixels,k,d in ((np.eye(3),corners,self.k,self.d),(quarter,rotated,np.eye(3),np.zeros(5))):
            result=cv().solvePnPGeneric(square(edge),pixels,k,d,flags=cv().SOLVEPNP_IPPE_SQUARE)
            candidates=self._solutions_in_original_optical(result,basis,corners,edge)
            if candidates:choices.append(candidates)
        pair=min(choices,key=lambda pair:pair[0]['rms_px']) if choices else []
        return self._refine_pair(pair,corners,edge) if self.pose_solver=='ippe_lm' else pair

    def _refine_pair(self, pair, corners, edge):
        """Refine each hypothesis without odom/AMCL or previous-frame seeds.

        Distinct optima stay distinct. Only numerically identical transforms
        are coalesced; this is not a statistical ambiguity threshold.
        A failed seed invalidates the frame rather than hiding ambiguity.
        """
        if not pair:return []
        refined=[]
        for seed in pair:
            t=seed['t_camera_tag'].copy()
            if self.rectified:
                r=np.eye(4);r[:3,:3]=self.rectification_r;t=r@t
            rv,_=cv().Rodrigues(t[:3,:3]);tv=t[:3,3].reshape(3,1).copy()
            try:
                rv,tv=cv().solvePnPRefineLM(square(edge),np.ascontiguousarray(corners),self.k,self.d,
                    rv,tv,criteria=(cv().TERM_CRITERIA_EPS+cv().TERM_CRITERIA_COUNT,100,1e-10))
                candidate=self._solutions_in_original_optical((True,[rv],[tv]),np.eye(3),corners,edge)
            except (cv().error,ValueError):return []
            if not candidate or candidate[0]['rms_px']>seed['rms_px']+1e-6:return []
            c=candidate[0];c.update(candidate_id=seed['candidate_id'],solver='ippe_lm',
                seed_candidate_ids=[seed['candidate_id']],seed_rms_px=[seed['rms_px']])
            duplicate=None
            for old in refined:
                delta=old['t_camera_tag'][:3,:3].T@c['t_camera_tag'][:3,:3]
                angle=math.acos(float(np.clip((np.trace(delta)-1)/2,-1,1)))
                if (np.linalg.norm(old['t_camera_tag'][:3,3]-c['t_camera_tag'][:3,3])<=1e-6
                        and angle<=1e-5 and abs(old['rms_px']-c['rms_px'])<=1e-4):
                    duplicate=old;break
            if duplicate is None:refined.append(c)
            else:
                duplicate['seed_candidate_ids']+=c['seed_candidate_ids']
                duplicate['seed_rms_px']+=c['seed_rms_px']
                if c['rms_px']<duplicate['rms_px']:
                    duplicate['t_camera_tag']=c['t_camera_tag'];duplicate['rms_px']=c['rms_px']
        return sorted(refined,key=lambda c:(c['rms_px'],c['candidate_id']))

    def _solutions_in_original_optical(self, result, basis, corners, edge):
        candidates=[]
        for index,(rvec,tvec) in enumerate(zip(result[1],result[2])):
            if not np.isfinite(rvec).all() or not np.isfinite(tvec).all():
                continue
            t = np.eye(4); t[:3,:3],_ = cv().Rodrigues(rvec); t[:3,3] = tvec.reshape(3)
            t[:3,:]=basis.T@t[:3,:]
            if self.rectified:
                rect = np.eye(4); rect[:3,:3] = self.rectification_r.T
                t = rect @ t
            try:
                error = self.project(t,edge)-corners
            except ValueError:
                continue
            rms = float(np.sqrt(np.mean(np.sum(error**2,axis=1))))
            if math.isfinite(rms): candidates.append({'candidate_id':index,'t_camera_tag':t,'rms_px':rms})
        return sorted(candidates,key=lambda c:(c['rms_px'],c['candidate_id']))


@dataclass
class Landmark:
    family: str
    tag_id: int
    edge_m: float
    t_map_tag: np.ndarray
    convention: str = 'ippe_square_v1'
    section_id: str | None = None

    def __post_init__(self):
        self.t_map_tag = transform(self.t_map_tag)
        square(self.edge_m)
        if self.convention != 'ippe_square_v1' or self.family != 'tag36h11' or type(self.tag_id) is not int or self.tag_id < 0:
            raise ValueError('unsupported_landmark_identity_or_axes')
        if self.section_id is not None and (not isinstance(self.section_id, str) or not self.section_id):
            raise ValueError('invalid_landmark_section')


@dataclass(frozen=True)
class QualityLimits:
    min_area_px2: float
    max_rms_px: float
    min_margin: float
    max_hamming: int
    base_z_m: float
    max_z_error_m: float
    max_roll_rad: float
    max_pitch_rad: float
    max_detections: int

    def __post_init__(self):
        if any(not math.isfinite(x) for x in (self.min_area_px2,self.max_rms_px,self.min_margin,
                                             self.base_z_m,self.max_z_error_m,self.max_roll_rad,self.max_pitch_rad)):
            raise ValueError('finite_explicit_quality_limits_required')
        if min(self.min_area_px2,self.max_rms_px,self.max_z_error_m,self.max_roll_rad,self.max_pitch_rad) <= 0:
            raise ValueError('positive_quality_envelope_required')
        if type(self.max_hamming) is not int or self.max_hamming < 0 or type(self.max_detections) is not int or self.max_detections < 1:
            raise ValueError('bounded_detection_limits_required')


class Observer:
    def __init__(self, context, camera, landmarks, t_base_camera, quality, *, uncertainty_model=None,
                 covariance_model_id=None):
        self.context, self.camera, self.quality = context,camera,quality
        self.t_base_camera = transform(t_base_camera)
        # 반복 ID 지도는 구간 안에서만 태그가 유일하다. 실물의 전역 유일 ID 계약도 유지한다.
        self.landmarks = {}
        self.section_landmarks = {}
        for landmark in landmarks:
            target = (self.landmarks if landmark.section_id is None else
                      self.section_landmarks.setdefault(landmark.section_id, {}))
            key = (landmark.family, landmark.tag_id)
            if key in target:
                raise ValueError('duplicate_landmark_id')
            target[key] = deepcopy(landmark)
        if self.landmarks and self.section_landmarks:
            raise ValueError('mixed_scoped_and_global_landmarks')
        if camera.version != context.calibration_version or not context.tag_map_version or not context.extrinsics_version:
            raise ValueError('registered_asset_versions_required')
        self.uncertainty_model,self.model_id=uncertainty_model,covariance_model_id

    def project_map_base(self,t_map_base,landmark):
        t_camera_tag = inverse(transform(t_map_base) @ self.t_base_camera) @ landmark.t_map_tag
        return self.camera.project(t_camera_tag,landmark.edge_m)

    def observe(self, frame, detections):
        c=self.context
        if frame['stamp_ns'] != frame['camera_info_stamp_ns'] or type(frame['stamp_ns']) is not int or frame['stamp_ns'] < 0:
            raise ValueError('image_camera_info_time_mismatch')
        if (frame['optical_frame'] != self.camera.optical_frame or
                tuple(frame['image_size']) != (self.camera.width,self.camera.height) or
                frame['calibration_version'] != self.camera.version or frame['rectified'] != self.camera.rectified):
            raise ValueError('image_camera_model_mismatch')
        if frame['session_id'] != c.session_id or frame['epoch'] != c.epoch:
            raise ValueError('image_epoch_mismatch')
        if not isinstance(frame.get('image_uid'),str) or not frame['image_uid']:
            raise ValueError('image_uid_required')
        if len(detections)>self.quality.max_detections: raise ValueError('detection_count_limit')
        landmarks = self.landmarks
        if self.section_landmarks:
            section_id = frame.get('section_id')
            if not isinstance(section_id, str) or section_id not in self.section_landmarks:
                return {'selected':None, 'all_packets':[],
                        'excluded':[{'reason':'active_section_required_or_unknown'}],
                        'stamp_ns':frame['stamp_ns']}
            landmarks = self.section_landmarks[section_id]
        keys=[(d.get('family'),d.get('tag_id')) for d in detections]
        repeated={key for key in keys if keys.count(key)>1}
        packets=[]; excluded=[]
        for d in detections:
            key=(d.get('family'),d.get('tag_id'))
            if key in repeated or key not in landmarks:
                excluded.append({'tag':key,'reason':'duplicate_or_unregistered_tag'}); continue
            # AprilTag C p[] uses the IPPE object-point index order. A different
            # decoder's printed-tag orientation needs its own verified adapter.
            if d.get('corner_convention') not in ('ippe_square_v1','apriltag_c_p_v1'):
                excluded.append({'tag':key,'reason':'unknown_corner_order'}); continue
            try:
                corners=finite(d['corners'],(4,2))
            except (ValueError, TypeError, KeyError):
                excluded.append({'tag':key,'reason':'invalid_corners'}); continue
            # Preserve decoded corner identity; never reorder by screen left/top.
            edges=np.roll(corners,-1,axis=0)-corners
            cross=edges[:,0]*np.roll(edges,-1,axis=0)[:,1]-edges[:,1]*np.roll(edges,-1,axis=0)[:,0]
            if not (np.all(cross>0) or np.all(cross<0)):
                excluded.append({'tag':key,'reason':'nonconvex_or_repeated_corners'}); continue
            area=abs(float(np.sum(corners[:,0]*np.roll(corners[:,1],-1)-corners[:,1]*np.roll(corners[:,0],-1))))/2
            margin=d.get('decision_margin'); hamming=d.get('hamming')
            if (area<self.quality.min_area_px2 or type(hamming) is not int or not 0<=hamming<=self.quality.max_hamming or
                    type(margin) not in (float,int) or not math.isfinite(margin) or margin<self.quality.min_margin or
                    np.any(corners[:,0]<0) or np.any(corners[:,0]>=self.camera.width) or
                    np.any(corners[:,1]<0) or np.any(corners[:,1]>=self.camera.height)):
                excluded.append({'tag':key,'reason':'detection_quality_or_incomplete_corners'}); continue
            landmark=landmarks[key]
            packet={'frame':deepcopy(frame),'detection':deepcopy(d),'tag':key,'area_px2':area,
                    'candidates':[],'covariance_model_id':self.model_id,'corners':corners.tolist()}
            if landmark.section_id is not None:
                packet['section_id'] = landmark.section_id
            try:
                solutions=self.camera.solve(corners,landmark.edge_m)
            except cv().error:
                excluded.append({'tag':key,'reason':'pnp_failed'}); continue
            for solution in solutions:
                t_map_base=landmark.t_map_tag @ inverse(solution['t_camera_tag']) @ inverse(self.t_base_camera)
                try: p6=pose6(t_map_base)
                except ValueError: continue
                q=p6[[0,1,5]]
                reasons=[]
                if solution['rms_px']>self.quality.max_rms_px: reasons.append('reprojection_quality')
                if (abs(p6[2]-self.quality.base_z_m)>self.quality.max_z_error_m or
                        abs(p6[3])>self.quality.max_roll_rad or abs(p6[4])>self.quality.max_pitch_rad):
                    reasons.append('outside_planar_model')
                if frame.get('capture_time_model_valid') is not True: reasons.append('capture_time_model_unvalidated')
                cov6=None
                if self.uncertainty_model is None or not self.model_id:
                    reasons.append('uncertainty_model_unavailable')
                else:
                    try:
                        cov6=covariance(self.uncertainty_model(self,deepcopy(packet),deepcopy(solution),t_map_base.copy()),6)
                    except (ValueError,np.linalg.LinAlgError) as exc:
                        reasons.append('invalid_uncertainty_model:'+str(exc))
                packet['candidates'].append({'candidate_id':solution['candidate_id'],
                    'q':q.tolist(),'pose6':p6.tolist(),'t_map_base':t_map_base.tolist(),
                    't_camera_tag':solution['t_camera_tag'].tolist(),'rms_px':solution['rms_px'],
                    'solver':solution.get('solver','ippe'),
                    'seed_candidate_ids':solution.get('seed_candidate_ids',[solution['candidate_id']]),
                    'p6':None if cov6 is None else cov6.tolist(),
                    'p':None if cov6 is None else cov6[np.ix_([0,1,5],[0,1,5])].tolist(),
                    'usable':not reasons,'reasons':reasons})
            usable=[x for x in packet['candidates'] if x['usable']]
            packet['usable_candidates']=usable
            packet['ambiguous']=len(usable)>1
            packets.append(packet)
        valid=[p for p in packets if p['usable_candidates']]
        single=[p for p in valid if len(p['usable_candidates'])==1]
        if single:
            chosen=min(single,key=lambda p:(float(np.linalg.slogdet(p['usable_candidates'][0]['p'])[1]),-p['area_px2'],p['tag']))
        elif valid:
            chosen=min(valid,key=lambda p:(-p['area_px2'],p['tag']))
        else: chosen=None
        return {'selected':chosen,'all_packets':packets,'excluded':excluded,'stamp_ns':frame['stamp_ns']}

    def estimator_event(self,packet):
        c=self.context; f=packet['frame']; candidates=packet['usable_candidates']
        if not candidates or not self.model_id: raise ValueError('usable_observation_required')
        return {'schema':'estimator_event_v1','kind':'tag','uid':f['image_uid'],'image_uid':f['image_uid'],
                'session_id':c.session_id,'epoch':c.epoch,'environment_id':c.environment_id,'map_version':c.map_version,
                'source':c.tag_source,'stamp_ns':f['stamp_ns'],'frame_id':c.map_frame,'base_frame':c.base_frame,
                'model_id':self.model_id,'tag_map_version':c.tag_map_version,'calibration_version':c.calibration_version,
                'extrinsics_version':c.extrinsics_version,'quality_valid':True,
                'candidates':[{'q':p['q'],'p':p['p'],'candidate_id':p['candidate_id']} for p in candidates]}
