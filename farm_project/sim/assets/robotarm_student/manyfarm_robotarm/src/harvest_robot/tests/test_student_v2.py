import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from harvest_vision.tracking import TrackManager
from harvest_vision.geometry import Frame
from harvest_vision.dataset import EpisodeWriter,Demonstrations
from harvest_rl.student_v2 import pack_observation,DualHistory,DualRGBDStudent


def detection(x=0.,stamp=0.,camera='rear',label='Red',control=True):
    return dict(camera_id=camera,frame_id='arm_2/base_link',clock_id='simulation',stamp_s=stamp,
                grasp_estimate_arm_m=[x,0.,.2],candidate_valid=True,control_valid=control,label=label)

class TrackingTests(unittest.TestCase):
    def test_fusion_loss_reacquire_and_completion(self):
        t=TrackManager();t.update([detection(),detection(.01,camera='right')],0)
        self.assertEqual(len(t.tracks),1);identity=t.assign(0)
        self.assertFalse(t.observation(.4)['valid'])
        t.update([detection(.02,.5)],.5)
        self.assertEqual(t.selected,identity);self.assertTrue(t.observation(.5)['valid'])
        t.finish(success=True,evidence='box_passage_confirmed')
        t.update([detection(.02,.6)],.6)
        self.assertIsNone(t.assign(.6))
    def test_provisional_and_frame(self):
        t=TrackManager();t.update([detection(control=False)],0);self.assertFalse(t.tracks)
        d=detection();d['clock_id']='other'
        with self.assertRaises(ValueError): t.update([d],0)
    def test_ambiguous_association(self):
        t=TrackManager();t.update([detection(-.05),detection(.05)],0)
        t.update([detection(0,.2)],.2)
        self.assertTrue(all(v['stamp_s']==0 for v in t.tracks.values()))
    def test_assignment_not_switched_after_loss(self):
        t=TrackManager();t.update([detection()],0);identity=t.assign(0)
        t.update([detection(.5,3.)],3.)
        self.assertEqual(t.selected,identity);self.assertFalse(t.observation(3.)['valid'])
        with self.assertRaises(RuntimeError): t.assign(3.)
    def test_lowest(self):
        d=detection(.2,label='Yellow');d['grasp_estimate_arm_m'][2]=.1
        t=TrackManager();t.update([detection(),d],0)
        self.assertEqual(t.tracks[t.assign(0)]['label'],'Yellow')

class StudentTests(unittest.TestCase):
    def observation(self):
        f=Frame(np.zeros((90,160,3),np.uint8),np.ones((90,160),np.float32),
                np.array([[100.,0,80],[0,100,45],[0,0,1]]),np.eye(4),0.,0.,'rear')
        return pack_observation({'rear':f},np.zeros(18),[.1,0,0],
            dict(position_m=[.3,0,.2],valid=True,age_s=0),0.)
    def test_network_and_mask(self):
        obs=self.observation();self.assertEqual(obs['state'].shape,(23,))
        self.assertEqual(obs['camera_valid'].tolist(),[False,True])
        np.testing.assert_allclose(obs['state'][18:21],[.2,0,.2],atol=1e-6)
        history=DualHistory(obs);model=DualRGBDStudent()
        output=model(**history.tensors());self.assertEqual(output.shape,(1,6))
        self.assertTrue(torch.isfinite(output).all());self.assertTrue((output.abs()<=1).all())
    def test_episode_storage_and_no_boundary_leak(self):
        obs=self.observation()
        with tempfile.TemporaryDirectory() as temp:
            for i,status in enumerate(['SUCCEEDED','FAILED']):
                writer=EpisodeWriter(Path(temp)/f'episode_{i:04d}',{})
                writer.append(obs,np.ones(6)*.1,{'stamp_s':0})
                writer.finish(status)
            dataset=Demonstrations(temp);self.assertEqual(len(dataset),1)
            item,action=dataset[0];self.assertEqual(item['rgb'].shape,(3,2,90,160,3))
            np.testing.assert_equal(item['state'][0],item['state'][2])
            self.assertEqual(len(Demonstrations(temp,successful_only=False)),2)
            with self.assertRaises(RuntimeError): writer.append(obs,np.zeros(6),{})


class ContractTests(unittest.TestCase):
    def test_inference_requires_v2_and_resets_identity(self):
        from harvest_rl.student_v2 import StudentInference,measured_proprio
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'student.pt';torch.save({'student':DualRGBDStudent().state_dict()},path)
            with self.assertRaises(ValueError): StudentInference(path)
            torch.save(dict(schema_version=2,camera_order=['right','rear'],student=DualRGBDStudent().state_dict()),path)
            policy=StudentInference(path);obs=StudentTests().observation()
            self.assertEqual(policy.predict(obs,'fruit-1').shape,(6,))
            policy.predict(obs,'fruit-2');self.assertEqual(policy.target_id,'fruit-2')
            state=measured_proprio(np.zeros(6),np.ones(6)*1.5,np.zeros(6),-np.ones(6),np.ones(6))
            np.testing.assert_array_equal(state[6:12],np.ones(6))
    def test_dataset_rejects_privileged_input(self):
        with tempfile.TemporaryDirectory() as temp:
            writer=EpisodeWriter(Path(temp)/'episode',{});obs=StudentTests().observation();obs['fruit_truth']=np.zeros(3)
            with self.assertRaises(ValueError): writer.append(obs,np.zeros(6),{})
    def test_appearance_change_requires_same_structure(self):
        from harvest_rl.current_robot import appearance_only_change
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'a.urdf';b=Path(temp)/'b.urdf'
            text='<robot><material name="arm_1/3d_printed"><color rgba="VALUE"/></material><link name="base"/></robot>'
            a.write_text(text.replace('VALUE','1 1 0 1'));b.write_text(text.replace('VALUE','0 0 0 1'))
            old=dict(usd=str(a.with_suffix('.usd')),source_files={'mesh':'same'})
            new=dict(usd=str(b.with_suffix('.usd')),source_files={'mesh':'same'})
            self.assertTrue(appearance_only_change(old,new))
            b.write_text(b.read_text().replace('name="base"','name="other"'))
            self.assertFalse(appearance_only_change(old,new))

if __name__=='__main__': unittest.main()
