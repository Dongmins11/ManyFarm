"""SEC01의13개를 원본 레인에 넣고 판 밖 과실은 이동 전에 거절해야 한다."""
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as S

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'sim/vendor/hcr3a_20261008/HCR3A_SIM_TEAM_20261008/workspace'
sys.path.insert(0,str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
sys.path.insert(0,str(SOURCE/'src/sorting_station'))
from farm_sim_runtime.sorter_runtime import SorterRuntime


@pytest.mark.parametrize('count,accepted',[(13,True),(16,True),(17,False)])
def test_deposit_keeps_whole_fruit_on_original_ramp(tmp_path,count,accepted):
    cfg=json.loads((SOURCE/'src/smartfarm_description/config/hcr3a_random8_validation.json').read_text())
    calls=[];paths=[f'/fruit/{i}' for i in range(count)]
    attachment=S(paths=paths,current_positions=lambda:np.tile([-.15,0.,.08],(count,1)),
                 relocate_detached=lambda p,xyz,q:calls.append(xyz))
    runtime=SorterRuntime.__new__(SorterRuntime)
    runtime.session='current';runtime.request_id=None;runtime.deposited=False;runtime.pending=None
    runtime.ctl=S(phase='IDLE');runtime.cargo_pose=lambda:np.eye(4)
    runtime.transport=lambda:dict(base=S(pose=lambda:(np.array([1.,0.,0.]),None),
        robot=S(get_linear_velocity=lambda:np.zeros(3),get_angular_velocity=lambda:np.zeros(3))))
    runtime.scene=S(output=tmp_path,cfg=cfg,origin=np.zeros(3),rotation=Rotation.identity(),
        physics=S(attachments=attachment),bind=lambda p:None,
        stage=S(GetPrimAtPath=lambda p:S(GetAttribute=lambda name:S(Get=lambda:'red'))))
    runtime.record=lambda *args,**kwargs:None
    (tmp_path/'deposit_request.json').write_text(json.dumps(dict(
        session='current',request_id='one',task_id='actual',fruit_paths=paths)))
    runtime.deposit(10.)
    if accepted:
        assert runtime.pending and len(calls)==1
        intake=cfg['intake'];radius=cfg['physics']['pepper_diameter']/2
        edge=intake['low_x']+math.sqrt(intake['slope_length']**2-intake['rise']**2)
        assert np.all(calls[0][:,0]+radius <= edge)
        assert np.all(calls[0][:,0]-radius >= intake['low_x'])
        assert runtime.pending['paths']==paths
    else:
        assert not calls and runtime.pending is None
        assert runtime.deposit_result['success'] is False
        assert '용량' in runtime.deposit_result['error']
