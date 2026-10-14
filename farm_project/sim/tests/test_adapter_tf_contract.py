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
        transforms=[dict(parent=frames[a],child=frames[b],translation=[0.,0.,0.],rotation_xyzw=[0.,0.,0.,1.]) for a,b in pairs]
        if config.get('scout_mount_asset'):
            transforms.extend(dict(parent=frames['base_link'],child='scout_01/'+name,
                translation=[0.,0.,0.],rotation_xyzw=[0.,0.,0.,1.]) for name in
                ('bmany_camera_link','camera_color_optical_frame','picam_frame','picam_optical_frame'))
        state=dict(kind='state',session='test',seq=1,stamp_ns=1,sent=time.monotonic(),
            odom=[0.,0.,0.,0.,0.],joint_positions=[0.,0.],joint_velocities=[0.,0.],scan=None,
            static_tf=transforms)
        self.config=config
        return state
    def test_harvest_without_camera_accepted(self):
        state=self.fixture('harvest')
        self.config['camera']['enabled']=False
        state['static_tf'].pop()
        self.assertEqual(len(state['static_tf']),2)
        self.assertTrue(namespace['valid'](self,state))
    def test_harvest_apriltag_camera_accepted(self):
        state=self.fixture('harvest');self.assertEqual(len(state['static_tf']),3)
        self.assertTrue(namespace['valid'](self,state))
    def test_scout_with_camera_accepted(self):
        state=self.fixture('scout');self.assertEqual(len(state['static_tf']),7)
        self.assertTrue(namespace['valid'](self,state))
    def test_scout_without_mount_uses_original_frames(self):
        state=self.fixture('scout');self.config.pop('scout_mount_asset');self.config.pop('tag_camera',None)
        state['static_tf']=state['static_tf'][:3]
        self.assertTrue(namespace['valid'](self,state))
    def test_missing_mount_frames_rejected(self):
        state=self.fixture('scout');state['static_tf']=state['static_tf'][:3]
        self.assertFalse(namespace['valid'](self,state))
    def test_duplicate_mount_frame_rejected(self):
        state=self.fixture('scout');state['static_tf'][-1]=copy.deepcopy(state['static_tf'][-2])
        self.assertFalse(namespace['valid'](self,state))
    def test_unknown_mount_frame_rejected(self):
        state=self.fixture('scout');state['static_tf'][-1]['child']='scout_01/unknown_frame'
        self.assertFalse(namespace['valid'](self,state))
    def test_wrong_mount_namespace_rejected(self):
        state=self.fixture('scout');state['static_tf'][-1]['child']='harvest_01/picam_optical_frame'
        self.assertFalse(namespace['valid'](self,state))
    def test_tag_camera_optical_frame_must_match_published_mount(self):
        state=self.fixture('scout')
        self.config['frames']['tag_camera_optical']='scout_01/wrong_tag_camera'
        self.assertFalse(namespace['valid'](self,state))
    def test_unconfigured_harvest_mount_frame_rejected(self):
        state=self.fixture('harvest')
        state['static_tf'].append(dict(parent=self.config['frames']['base_link'],
            child='harvest_01/picam_frame',translation=[0.,0.,0.],rotation_xyzw=[0.,0.,0.,1.]))
        self.assertFalse(namespace['valid'](self,state))
    def test_missing_sensor_rejected(self):
        state=self.fixture('scout');state['static_tf'].pop(2)
        self.assertFalse(namespace['valid'](self,state))
    def test_wrong_robot_frame_rejected(self):
        state=self.fixture('harvest');state['static_tf'][0]['child']='scout_01/base_link'
        self.assertFalse(namespace['valid'](self,state))

if __name__=='__main__':unittest.main()
