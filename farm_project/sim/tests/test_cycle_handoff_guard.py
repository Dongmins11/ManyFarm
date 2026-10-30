"""가상 과실 인계가 오래된 세션·정렬·이동 중 요청을 거절해야 한다."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as S
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.sorter_runtime import SorterRuntime


def make(tmp_path):
    runtime=SorterRuntime.__new__(SorterRuntime)
    runtime.session='current'
    runtime.scene=S(output=tmp_path)
    runtime.events=[]
    runtime.record=lambda event,**data:runtime.events.append((event,data))
    runtime.basket_monitor=S(latest=dict(hold_pass=True,sim_time_s=10.),ids={'harvest':'h'})
    def robot(rid):
        body=S(get_linear_velocity=lambda:np.zeros(3),get_angular_velocity=lambda:np.zeros(3))
        return dict(cfg=dict(robot_id=rid),base=S(robot=body),arm=S(travel_ready=True,busy=False))
    runtime.robots=[robot('h'),robot('t')]
    runtime.transport=lambda:runtime.robots[1]
    return runtime


@pytest.mark.parametrize('fault,reason',[
    ('session','현재 세션'),('stale','정렬 유지'),('moving','실제 정지'),('arm','팔 복귀')])
def test_invalid_handoff_never_accesses_or_moves_fruit(tmp_path,fault,reason):
    runtime=make(tmp_path)
    request=dict(request_id='one',session='current',authorized_event='TRANSFER_COMPLETE')
    if fault=='session':request['session']='previous'
    if fault=='stale':runtime.basket_monitor.latest['sim_time_s']=9.
    if fault=='moving':runtime.robots[1]['base'].robot.get_linear_velocity=lambda:np.array([.1,0,0])
    if fault=='arm':runtime.robots[0]['arm'].busy=True
    (tmp_path/'handoff_request.json').write_text(json.dumps(request))
    # scene에는 physics/attachments조차 없다. 거절 전에 과실을 조회/변경하면 실패한다.
    runtime.handoff(10.)
    result=json.loads((tmp_path/'handoff_result.json').read_text())
    assert result['success'] is False and reason in result['error']
    assert result['fruit_paths']==[]
    runtime.handoff(10.1)
    assert len(runtime.events)==1
