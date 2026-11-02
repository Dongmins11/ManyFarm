"""Domain13 실행 노드의 파라미터를 읽기만 한다. 각 단계 대기는 5초로 제한."""
import json
from pathlib import Path
import time
import rclpy
from rcl_interfaces.srv import ListParameters, GetParameters
from rclpy.parameter import parameter_value_to_python

rclpy.init()
node = rclpy.create_node('threshold_audit_read_only')
names = ['/harvest_01/controller_server', '/harvest_01/handoff/controller_server',
         '/scout_01/controller_server', '/transport_01/controller_server', '/hcr_sorter']
output = {}
try:
    pending = {}
    for name in names:
        client = node.create_client(ListParameters, name+'/list_parameters')
        pending[name] = (client, client.call_async(ListParameters.Request()))
    deadline = time.monotonic()+5
    while not all(f.done() for _, f in pending.values()) and time.monotonic()<deadline:
        rclpy.spin_once(node, timeout_sec=.1)
    gets = {}
    for name, (_, f) in pending.items():
        if not f.done() or f.exception():
            output[name] = {'error': 'list timeout/unavailable'}
            continue
        keys = f.result().result.names
        c = node.create_client(GetParameters, name+'/get_parameters')
        gets[name] = (keys, c, c.call_async(GetParameters.Request(names=keys)))
    deadline = time.monotonic()+5
    while not all(f.done() for _, _, f in gets.values()) and time.monotonic()<deadline:
        rclpy.spin_once(node, timeout_sec=.1)
    for name, (keys, _, f) in gets.items():
        output[name] = ({k:parameter_value_to_python(v) for k,v in zip(keys,f.result().values)}
                        if f.done() and not f.exception() else {'error':'get timeout'})
    Path(__file__).with_name('live_parameters.json').write_text(json.dumps(output,indent=2)+'\n')
    print({k:len(v) for k,v in output.items()})
finally:
    node.destroy_node()
    rclpy.shutdown()
