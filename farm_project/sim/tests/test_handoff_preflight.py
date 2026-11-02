"""Preflight must accept fresh Nav2 headers and reject stale collision inputs."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import single_cycle_steps as steps

@pytest.mark.parametrize('stale', [None, 'costmap_raw', 'published_footprint'])
def test_collision_header_freshness(tmp_path, monkeypatch, stale):
    runtime=tmp_path/'runtime';runtime.mkdir()
    (runtime/'harvest_task.json').write_text(json.dumps(dict(robot_id='harvest_01',
        transfer=dict(device_services={'stop':'/stop'},discharge_action={'endpoint':'/discharge'}))))
    class Client:
        def __init__(self,*args):pass
        def service_is_ready(self):return True
        def server_is_ready(self):return True
        def call_async(self,request):
            return NS(done=lambda:True,result=lambda:NS(current_state=NS(id=3)))
        def destroy(self):pass
    monkeypatch.setattr(steps,'ActionClient',Client)
    class Node:
        def get_clock(self):return NS(now=lambda:NS(nanoseconds=10_000_000_000))
        def create_client(self,*args):return Client()
        def create_subscription(self,kind,topic,callback,qos):
            msg=kind();msg.header.stamp.sec=8 if topic.endswith('/'+str(stale)) else 10
            # Nav2 metadata.update_time can be zero even with a fresh header.
            callback(msg)
            return msg
        def destroy_client(self,c):pass
        def destroy_subscription(self,s):pass
    records=[]
    def wait(check,*args):
        for _ in range(3):
            if check():return
        raise TimeoutError('not ready')
    def run():steps.harvest_handoff_ready(tmp_path,Node(),wait,None,
        lambda kind,**data:records.append(kind))
    if stale:
        with pytest.raises(TimeoutError):run()
        assert records==['harvest_handoff_not_ready']
    else:
        run()
        assert records==['harvest_handoff_ready']
