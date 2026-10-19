"""Opt-in sensor robustness for BC/DAgger; no simulator, ROS or hardware imports.

These are sensitivity experiments, not a physical stereo-camera simulator.
Episode biases differ from frame noise; repeated/overlapping frames stay coherent.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import torch


def load_profile(path):
    raw=Path(path).read_bytes();p=json.loads(raw)
    keys={'version','status','rgb_gain_range','rgb_contrast_range','depth_noise_std_m',
          'depth_dropout_probability','depth_min_m','depth_max_m','target_bias_bound_m',
          'target_noise_std_m','single_camera_dropout_probability','camera_delay_steps_max','target_ttl_s','note'}
    if set(p)!=keys or p['version']!='student_observation_shift_v1':raise ValueError('Unknown observation shift profile/schema')
    for key in ('rgb_gain_range','rgb_contrast_range'):
        x=p[key]
        if not isinstance(x,list) or len(x)!=2 or not all(type(v) in (int,float) and math.isfinite(v) for v in x) or not .5<=x[0]<=x[1]<=1.5:
            raise ValueError(f'Invalid {key}')
    for key,limit in (('depth_noise_std_m',.01),('target_noise_std_m',.01),
                      ('depth_dropout_probability',.2),('single_camera_dropout_probability',.2)):
        v=p[key]
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=limit:raise ValueError(f'Invalid {key}')
    bias=p['target_bias_bound_m']
    if not isinstance(bias,list) or len(bias)!=3 or not all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=.02 for v in bias):
        raise ValueError('Invalid target bias bounds')
    if type(p['camera_delay_steps_max'])!=int or not 0<=p['camera_delay_steps_max']<=2:raise ValueError('Delay must be 0..2 control steps')
    for k in ('depth_min_m','depth_max_m','target_ttl_s'):
        if type(p[k]) not in (int,float) or not math.isfinite(p[k]):raise ValueError(f'Invalid {k}')
    if not 0<p['depth_min_m']<p['depth_max_m']<=3 or p['target_ttl_s']!=.3:raise ValueError('Require existing Student depth/TTL contract')
    return p,dict(profile_sha256=hashlib.sha256(raw).hexdigest(),profile=p,
                  implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def tcp_metadata(path):
    note=json.loads(Path(path).read_text()).get('observation_geometry',{})
    tcp=np.asarray(note.get('tcp_arm_m',[]),dtype=np.float32)
    if note.get('schema')!='arm_tcp_v1' or tcp.shape!=(3,) or not np.isfinite(tcp).all():
        raise ValueError(f'Delay augmentation requires synchronized measured TCP metadata: {path}; recollect, do not substitute fruit truth')
    return tcp


def validate_latency_metadata(episodes):
    for episode in episodes:
        for i in range(episode['samples']):tcp_metadata(Path(episode['path'])/f'{i:06d}.json')


class ObservationShift:
    def __init__(self,profile,seed,control_dt):
        if not math.isfinite(control_dt) or control_dt<=0:raise ValueError('Invalid control timestep')
        self.profile=profile;self.seed=seed;self.control_dt=control_dt
        # Shared epoch reaches persistent DataLoader workers without restarting them.
        self.epoch=torch.zeros(1,dtype=torch.int64).share_memory_()

    def set_epoch(self,epoch):self.epoch[0]=epoch

    def _rng(self,episode,kind):
        key=f'{self.seed}:{int(self.epoch[0])}:{episode}:{kind}'.encode()
        return np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8],'little'))

    def delay(self,episode):
        return int(self._rng(episode,'episode').integers(self.profile['camera_delay_steps_max']+1))

    def apply(self,episode,current,sensor,source_indices,lags,tcp_current=None,tcp_sensor=None):
        p=self.profile;prng=self._rng(episode,'episode')
        # Sample from the same episode stream every time; order is independent of
        # WeightedRandomSampler and worker scheduling.
        prng.integers(p['camera_delay_steps_max']+1)
        gain=prng.uniform(*p['rgb_gain_range'],size=2)
        contrast=prng.uniform(*p['rgb_contrast_range'],size=2)
        bias=prng.uniform(-np.array(p['target_bias_bound_m']),np.array(p['target_bias_bound_m'])).astype(np.float32)
        out={k:np.array(sensor[k],copy=True) for k in ('rgb','depth_m','camera_valid')}
        out['state']=np.array(current['state'],copy=True)
        for t,index in enumerate(source_indices):
            rng=self._rng(episode,f'frame:{index}')
            for camera in range(2):
                if not out['camera_valid'][t,camera]:
                    out['rgb'][t,camera]=0;out['depth_m'][t,camera]=0;continue
                rgb=out['rgb'][t,camera].astype(np.float32)
                rgb=((rgb-127.5)*contrast[camera]+127.5)*gain[camera]
                out['rgb'][t,camera]=np.rint(rgb.clip(0,255)).astype(np.uint8)
                d=out['depth_m'][t,camera]
                noisy=d+rng.normal(0,p['depth_noise_std_m'],size=d.shape).astype(np.float32)
                good=(d>0)&(noisy>=p['depth_min_m'])&(noisy<=p['depth_max_m'])
                good &= rng.random(d.shape)>=p['depth_dropout_probability']
                out['depth_m'][t,camera]=np.where(good,noisy,0).astype(np.float32)
            if out['camera_valid'][t].all() and rng.random()<p['single_camera_dropout_probability']:
                c=int(rng.integers(2));out['camera_valid'][t,c]=False
                out['rgb'][t,c]=0;out['depth_m'][t,c]=0
            age=float(sensor['state'][t,22])+lags[t]*self.control_dt
            valid=bool(sensor['state'][t,21]) and age<=p['target_ttl_s']
            out['state'][t,18:21]=0
            out['state'][t,21]=float(valid);out['state'][t,22]=min(age,p['target_ttl_s'])
            if valid:
                delta=sensor['state'][t,18:21].copy()
                if lags[t]:
                    if tcp_current is None or tcp_sensor is None:raise ValueError('Delayed target requires current/capture-time TCP; old relative delta is not a valid current delta')
                    delta+=tcp_sensor[t]-tcp_current[t]
                out['state'][t,18:21]=delta+bias+rng.normal(0,p['target_noise_std_m'],3).astype(np.float32)
        return out
