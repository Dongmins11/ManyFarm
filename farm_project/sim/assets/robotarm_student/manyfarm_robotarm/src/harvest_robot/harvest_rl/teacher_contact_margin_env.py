"""Separate V4 grasp reward; original class, actuator commands and certification unchanged."""
import torch
from .teacher_capture_v4_env import TeacherCaptureV4Env
from .grasp_contact_margin_60hz import SPEC,contact_centroid,contact_geometry,contact_margin_reward
from .contact_points_60hz import recording_views


class TeacherContactMarginEnv(TeacherCaptureV4Env):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # Retain the broad pool; only final-stage train resets emphasize far points.
        if kwargs['domain_split']=='train':
            pool=self.domain_pools[-1]
            far=pool[self.domain_distances[pool]>SPEC['far_distance_m']]
            self.domain_pools[-1]=torch.cat([pool]+[far]*SPEC['extra_far_pool_repeats'])
        self.margin_views,self.margin_sensor_metadata=recording_views(self)

    def _get_rewards(self):
        reward=super()._get_rewards()
        if not hasattr(self,'margin_views'):return reward
        contacts=[]
        for jaw in ('fixed','moving'):
            force,points,_,_,counts,starts=self.margin_views[jaw].get_contact_data(dt=self.physics_dt)
            contacts.append(contact_centroid(force,points,counts,starts,self.target_index))
        fruit=self._target_fruit().data
        geometry=contact_geometry(*contacts,self._grasp_center(self._target_fruit()),fruit.root_link_quat_w)
        extra,d=contact_margin_reward(geometry,self.distance,self.grip & self.raw_grip,
            self._t(self.attached),self.success,self.step_dt)
        self.last_diagnostics.update({k:v.clone() for k,v in d.items()})
        self.extras['log'].update({'GraspContact/'+k:v.float().mean() for k,v in d.items()})
        return reward+extra
