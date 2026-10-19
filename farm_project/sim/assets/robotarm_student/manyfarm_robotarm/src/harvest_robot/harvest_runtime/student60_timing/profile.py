"""Provenance-bearing timing samples. Missing measurements are never zero by default."""
from dataclasses import dataclass
import copy
import json
import math
from pathlib import Path
import random

STAGES=('camera_right','camera_rear','vision','policy','dispatch','joint_feedback')


@dataclass
class TimingProfile:
    value: dict
    seed: int = 0

    def __post_init__(self):
        self.value=copy.deepcopy(self.value)
        if self.value.get('schema')!='student60_timing_profile_v1':raise ValueError('Unknown timing profile')
        self.random=random.Random(self.seed)
        for name in STAGES:
            stage=self.value['stages'][name];samples=stage['samples_s']
            if not stage.get('source') or not samples or any(not math.isfinite(v) or v<0 or v>10 for v in samples):
                raise ValueError('Missing/invalid timing provenance: '+name)
            if stage['measurement_kind'] not in ('hardware','recorded_compute','assumption','stress'):
                raise ValueError('Unclassified timing measurement')
        for name,p in self.value.get('drop_probability',{}).items():
            if name not in STAGES or not 0<=p<=1:raise ValueError('Invalid drop probability')
        self.phase_age=self.value['helper_target_max_age_s']
        if set(self.phase_age)!={'observe','approach','insert','close'} or any(not 0<v<=.3 for v in self.phase_age.values()):
            raise ValueError('Unbounded or incomplete helper target age')
        for key in ('command_max_age_s','joint_max_age_s'):
            if not 0<self.value[key]<=.3:raise ValueError('Invalid command/feedback age')
        if self.value.get('neural_target_max_age_s',.05)!=.05 or self.value.get('camera_input_ttl_s',.3)!=.3:
            raise ValueError('Frozen neural input ages cannot be changed by a timing profile')

    @classmethod
    def read(cls,path,seed=0):return cls(json.loads(Path(path).read_text()),seed)

    def delay(self,name):return float(self.random.choice(self.value['stages'][name]['samples_s']))

    def drop(self,name):return self.random.random()<self.value.get('drop_probability',{}).get(name,0.)

    @property
    def real_end_to_end_measured(self):
        return bool(self.value.get('end_to_end_hardware_measured',False)) and all(
            self.value['stages'][s]['measurement_kind']=='hardware' for s in STAGES)

    def require_hardware(self):
        if not self.real_end_to_end_measured:raise ValueError('Incomplete real camera-to-actuator measurement; hardware execution refused')


def build_partial_profile(benchmark,policy_samples,inventory):
    """Use known compute samples and explicit unmeasured transport margins."""
    stages={
        'camera_right':dict(samples_s=[1/30],measurement_kind='assumption',source='Unmeasured camera delivery; one additional frame margin'),
        'camera_rear':dict(samples_s=[1/30],measurement_kind='assumption',source='D435 absent; unmeasured delivery, one frame margin'),
        'vision':dict(samples_s=list(benchmark['raw_seconds']['optimized_vision']),measurement_kind='recorded_compute',source='latency_candidate/recorded_benchmark_v2.json: RGB IPC + segmentation + native3D; excludes sensor delivery'),
        'policy':dict(samples_s=list(policy_samples),measurement_kind='recorded_compute',source='Frozen v20 trace student_observation_inference_s: Student + assistance'),
        'dispatch':dict(samples_s=[.005],measurement_kind='assumption',source='Unmeasured serial transport; explicit5ms simulation margin'),
        'joint_feedback':dict(samples_s=[.005],measurement_kind='assumption',source='Unmeasured serial feedback; explicit5ms simulation margin')}
    return dict(schema='student60_timing_profile_v1',end_to_end_hardware_measured=False,
        model_sensor_family='d435_deployment_v2',connected_U20_is_not_model_camera=True,
        stages=stages,drop_probability={},inventory=inventory,
        helper_target_max_age_s=dict(observe=.25,approach=.15,insert=.12,close=.12),
        neural_target_max_age_s=.05,camera_input_ttl_s=.3,command_max_age_s=.1,joint_max_age_s=.075,
        helper_age_contract='Experimental helper-only budgets; no stale point is relabelled fresh for the frozen neural model',
        hardware_execution_authorized=False)
