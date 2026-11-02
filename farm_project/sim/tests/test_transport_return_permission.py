"""하역 이후 운송 복귀 허가에 다른 시도/실패/미도착 결과를 사용하지 않는다."""
import ast
import json
from pathlib import Path
import pytest

@pytest.mark.parametrize('change,expected',[(None,True),('old_token',False),('failed',False),('not_docked',False),('wrong_robot',False),('missing',False)])
def test_harvest_return_permission(tmp_path,change,expected):
    source=Path(__file__).resolve().parents[2]/'sim/tools/probe_sorter_cycle.py'
    fn=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='harvest_return_authorized')
    ns={'json':json};exec(compile(ast.Module(body=[fn],type_ignores=[]),'gate','exec'),ns)
    data={'token':'current','reply':{'status':4,'result':{'result_code':'SUCCESS','docked':True,'robot_id':'harvest_01','station_id':'STATION_HARVEST_01'}}}
    if change=='old_token':data['token']='previous'
    if change=='failed':data['reply']['status']=6
    if change=='not_docked':data['reply']['result']['docked']=False
    if change=='wrong_robot':data['reply']['result']['robot_id']='transport_01'
    if change!='missing':(tmp_path/'harvest_return_complete.json').write_text(json.dumps(data))
    assert ns['harvest_return_authorized'](tmp_path,'current') is expected
