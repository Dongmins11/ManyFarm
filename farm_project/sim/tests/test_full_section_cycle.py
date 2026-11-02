"""섹션별 전체시험은 필요한 복귀/선별을 생략해서 통과시키지 않는다."""
import ast
import copy
import json
import math
import sys
from pathlib import Path

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim/tools'))
from run_fresh_cycle_until_success import complete


def test_single_section_completion_still_requires_all_returns_and_sorting():
    ok=dict(status=4,result=dict(result_code='SUCCESS'))
    result={k:copy.deepcopy(ok) for k in ('scout','scout_return','harvest_return','pickup_final','dock_final')}
    result['dock_final']['result'].update(transfer_complete=True,transport_clear=True,restore_complete=True)
    result.update(passed=True,single_section=True,section='SEC16',window_count=1,harvest_results=[ok])
    result['sorter_and_transport_return']=dict(unload=ok,sort=ok,**{'return':ok},count_valid=True,
        input_count=2,sorted_count=2,remaining_fruit_paths=[],all_input_fruits_sorted=True)
    assert complete(result)
    for key in ('scout_return','harvest_return','pickup_final','dock_final'):
        missing=copy.deepcopy(result);del missing[key]
        assert not complete(missing)
    result['sorter_and_transport_return']['sorted_count']=1
    result['sorter_and_transport_return'].update(remaining_fruit_paths=['unobserved'], all_input_fruits_sorted=False)
    assert complete(result)
    result['sorter_and_transport_return']['sort'] = dict(status=6,result=dict(result_code='FAILED'))
    assert not complete(result)


@pytest.mark.parametrize('section',[f'SEC{i:02d}' for i in range(1,17)])
def test_pickup_projection_uses_selected_section(tmp_path,section):
    source=ROOT/'sim/tools/single_cycle_steps.py'
    function=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='pickup_pose')
    namespace=dict(json=json,copy=copy,ROOT=ROOT)
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
    config=ROOT/'sim/ros_ws/src/farm_sim_config/config'
    spec=yaml.safe_load((config/'task.yaml').read_text())['sections'][section]
    profile=yaml.safe_load((config/'transport_runtime.yaml').read_text())
    graph=json.loads((ROOT/profile['route_graph']).read_text())
    nodes={f['properties']['id']:f['geometry']['coordinates'] for f in graph['features'] if f['geometry']['type']=='Point'}
    (tmp_path/'runtime').mkdir()
    layout=tmp_path/'layout.json'
    layout.write_text(json.dumps(dict(markers=[dict(id=42,center_m=[.34,-.06,.081],
        reference_prim='/World/harvest_robot/base_footprint')])))
    (tmp_path/'runtime/fleet.json').write_text(json.dumps(dict(docking_markers=str(layout))))
    (tmp_path/'runtime/harvest.json').write_bytes((config/'harvest.json').read_bytes())
    profiles=tmp_path/'profiles.json'
    profiles.write_text(json.dumps(dict(profiles=dict(harvest_approach_42=dict(target_marker_id=42,
        acquire_then_odom=dict(distance_corridor=dict(target_range_m=.54)),
        route_handoff=dict(approach_margin_m=.1))))))
    profile.update(precision_profiles=str(profiles),pickup_workflow=dict(approach_profile='harvest_approach_42'))
    (tmp_path/'single_cycle.json').write_text(json.dumps(dict(single_section=True,section=section)))
    (tmp_path/'runtime/transport_runtime.json').write_text(json.dumps(profile))
    y=sum(spec['survey_geometry'][name][1] for name in ('start_xy_m','end_xy_m'))/2
    pose=dict(frame_id='map',position=dict(x=spec['harvest_route']['x_m'],y=y,z=0),yaw=spec['observations'][0]['yaw_rad'])
    namespace['pickup_pose'](tmp_path,dict(goal_pose=pose))
    actual=json.loads((tmp_path/'runtime/pickup_goal.json').read_text())
    assert actual['position']['x']==nodes[spec['harvest_route']['entry_node_id']][0]
    assert actual['position']['y']==pytest.approx(y-.98*math.sin(pose['yaw']))
    assert actual['yaw']==pose['yaw']
    # 수확로봇 중심까지 진행하지 않고 마커 대기 거리를 남긴다.
    assert abs(actual['position']['y']-y)==pytest.approx(.98)


@pytest.mark.parametrize('becomes_ready',[True,False])
def test_transport_preflight_requires_new_ready_status(monkeypatch,becomes_ready):
    from types import SimpleNamespace as S
    source=ROOT/'sim/tools/single_cycle_steps.py'
    function=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='transport_robot_ready')
    monkeypatch.setitem(sys.modules,'farm_interfaces.msg',S(RobotStatus=object))
    monkeypatch.setitem(sys.modules,'rclpy.qos',S(qos_profile_sensor_data=object()))
    namespace=dict(message_to_ordereddict=lambda m:m)
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
    callbacks=[];destroyed=[];events=[]
    node=S(create_subscription=lambda kind,topic,callback,qos:callbacks.append(callback) or 'subscription',
           destroy_subscription=destroyed.append)
    def wait(predicate,timeout,label):
        assert not predicate()  # 액션 서버가 있더라도 새 RobotStatus 없이는 진행 불가.
        callbacks[0](dict(ready=False,state='IDLE',error_code='LOCALIZATION_LOST'))
        assert not predicate()
        if not becomes_ready:raise TimeoutError(label)
        callbacks[0](dict(ready=True,state='IDLE',error_code=''))
        assert predicate()
    record=lambda kind,**data:events.append((kind,data))
    if becomes_ready:
        namespace['transport_robot_ready'](node,wait,record)
        assert events[-1][0]=='transport_robot_ready'
    else:
        with pytest.raises(TimeoutError):namespace['transport_robot_ready'](node,wait,record)
        assert events[-1][0]=='transport_not_ready'
        assert events[-1][1]['data']['error_code']=='LOCALIZATION_LOST'
    assert destroyed==['subscription']
