"""실제 어댑터 valid 메서드를 ROS 없이 로드해 센서별 상태 패킷 계약을 검사."""
import ast
import copy
import json
import math
from pathlib import Path
import time
import unittest
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py'
module=ast.parse(SOURCE.read_text())
finite=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='finite_vector')
cls=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='SimRosAdapter')
valid=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='valid')
namespace={'math':math,'time':time}
exec(compile(ast.Module(body=[finite,valid],type_ignores=[]),str(SOURCE),'exec'),namespace)

class AdapterTests(unittest.TestCase):
    def fixture(self,robot):
        config=json.loads((ROOT/f'sim/ros_ws/src/farm_sim_config/config/{robot}.json').read_text())
        frames=config['frames']
        pairs=[('base_footprint','base_link'),('base_link','scan')]
        if config['camera']['enabled']:pairs.append(('base_link','camera_optical'))
        state=dict(kind='state',session='test',seq=1,stamp_ns=1,sent=time.monotonic(),
            odom=[0.,0.,0.,0.,0.],joint_positions=[0.,0.],joint_velocities=[0.,0.],scan=None,
            static_tf=[dict(parent=frames[a],child=frames[b],translation=[0.,0.,0.],rotation_xyzw=[0.,0.,0.,1.]) for a,b in pairs])
        self.config=config
        return state
    def test_harvest_without_camera_accepted(self):
        state=self.fixture('harvest');self.assertEqual(len(state['static_tf']),2)
        self.assertTrue(namespace['valid'](self,state))
    def test_scout_with_camera_accepted(self):
        state=self.fixture('scout');self.assertEqual(len(state['static_tf']),3)
        self.assertTrue(namespace['valid'](self,state))
    def test_missing_sensor_rejected(self):
        state=self.fixture('scout');state['static_tf'].pop()
        self.assertFalse(namespace['valid'](self,state))
    def test_wrong_robot_frame_rejected(self):
        state=self.fixture('harvest');state['static_tf'][0]['child']='scout_01/base_link'
        self.assertFalse(namespace['valid'](self,state))

if __name__=='__main__':unittest.main()
