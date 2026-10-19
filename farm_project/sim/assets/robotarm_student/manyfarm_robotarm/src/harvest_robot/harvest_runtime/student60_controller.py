"""Shared live-observation wrapper; no Isaac, ROS, Teacher, or hardware imports."""
import numpy as np
from .student60 import TargetFilter,decode_command
from .student60_contract import encode_targets
from harvest_rl.student_v2 import measured_proprio
from harvest_rl.student_v3 import pack_observation
from harvest_rl.student60_model import Student60Inference


class Student60Controller:
    def __init__(self,checkpoint,contract,device='cpu'):
        self.policy=Student60Inference(checkpoint,contract,device)
        self.contract=contract
        self.target_filter=TargetFilter(contract['box_from_arm'],contract['box_min'],contract['box_max'])
        self.target_id=None;self.pending=False

    def start(self,target_id,initial_target_rad):
        if not target_id:raise ValueError('Explicit target assignment required')
        self.policy.reset();self.target_filter.reset();self.target_id=target_id
        self.previous_q=np.asarray(initial_target_rad,float).copy()
        self.previous=encode_targets(self.previous_q,self.contract['lower_rad'],self.contract['upper_rad'])
        self.last_stamp=None;self.pending=False;self.measured_jaw=None

    def step(self,frames,q_rad,qd_rad_s,tcp_arm,target,now,capture):
        if self.pending:raise ValueError('Acknowledge the executed command before another step')
        if self.target_id is None or target['target_id']!=self.target_id:raise ValueError('Target assignment changed without reset')
        if self.last_stamp is not None and abs(now-self.last_stamp-.05)>1e-6:raise ValueError('Require sequential20Hz control timestamps')
        filtered=self.target_filter.filter(target)
        proprio=measured_proprio(q_rad,qd_rad_s,self.previous,self.contract['lower_rad'],self.contract['upper_rad'])
        observation=pack_observation(frames,proprio,tcp_arm,filtered,now,capture)
        command=self.policy.predict(observation,self.target_id)
        self.pending=True;self.tcp=np.asarray(tcp_arm,float).copy();self.last_stamp=now
        self.measured_jaw=float(q_rad[-1])
        return command,dict(target=filtered,release_latched=self.target_filter.released)

    def acknowledge(self,actually_executed_command):
        if not self.pending:raise ValueError('No outstanding command')
        q,_=decode_command(actually_executed_command,self.contract['lower_rad'],self.contract['upper_rad'])
        released_before=self.target_filter.released
        self.target_filter.observe_command(self.previous_q,q,self.tcp)
        if (not released_before and self.measured_jaw is not None
                and q[-1]<=self.measured_jaw+1e-4):
            self.target_filter.opening=0;self.target_filter.released=False
        self.previous_q=q;self.previous=np.asarray(actually_executed_command[:6]).copy()
        self.policy.acknowledge(actually_executed_command);self.pending=False
