import json,tempfile,unittest
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader
from harvest_rl.student_bc import prepare,audit_root,verify_prepared,BCDataset,action_loss,evaluate,atomic_save
from harvest_rl.student_v2 import DualRGBDStudent,StudentInference


def make_root(root,seed=1):
    root.mkdir();e=root/'episode_0000';e.mkdir()
    manifest=dict(capture_contract='synchronised_rgbd_v1',schema_version=2,camera_order=['right','rear'],history=3,
        camera_config={},frame_id='arm_2/base_link',control_dt=.05,lower_rad=[-1]*6,upper_rad=[1]*6,
        joint_names=list('abcdef'),detector_sha256='detector',action_contract='six increments',experts={'runtime':{'seed':seed,'mass':.035}})
    for key in ('checkpoint','grasp_expert','transport_expert','place_expert'):manifest[key]={'sha256':key}
    (root/'dataset_manifest.json').write_text(json.dumps(manifest))
    (root/'run.json').write_text(json.dumps({'current_asset':{'asset_input_sha256':'same_robot'}}))
    (e/'metadata.json').write_text(json.dumps(dict(seed=seed,episode=0,layout={'target_color':'Red'})))
    (e/'result.json').write_text(json.dumps(dict(status='SUCCEEDED',samples=4)))
    for i,stage in enumerate((-1,0,1,2)):
        state=np.zeros(23,np.float32);state[21]=1
        rgb=np.zeros((2,90,160,3),np.uint8);rgb[:,:,0]=i+1
        np.savez(e/f'{i:06d}.npz',rgb=rgb,depth_m=np.ones((2,90,160),np.float32),
                 camera_valid=np.ones(2,np.bool_),state=state,action=np.full(6,.1,np.float32))
        (e/f'{i:06d}.json').write_text(json.dumps(dict(stamp_s=i*.05,expert_stage=stage,target={'target_id':'fruit-1'})))
    return e


class BCTests(unittest.TestCase):
    def test_centre_offset_contract_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b';make_root(a);make_root(b,2)
            p=b/'dataset_manifest.json';m=json.loads(p.read_text());m['centre_offset_m']=.026;p.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'Incompatible'):
                prepare([a],[b])

    def test_execution_contract_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b';make_root(a);make_root(b,2)
            p=b/'dataset_manifest.json';m=json.loads(p.read_text())
            m['experts']['action_execution']={'version':1,'transport_initial_scale':.25,'transport_ramp_s':3.}
            p.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'Incompatible'):prepare([a],[b])
    def test_success_without_place_is_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'data';ep=make_root(root)
            path=ep/'000003.json';row=json.loads(path.read_text());row['expert_stage']=1;path.write_text(json.dumps(row))
            _,episodes,skipped,_=audit_root(root)
            self.assertEqual(episodes,[])
            self.assertEqual(skipped[0]['missing'],[2])
    def test_split_audit_and_changed_file(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b';make_root(a);make_root(b,2)
            plan=prepare([a],[b]);verify_prepared(plan)
            self.assertEqual(plan['summary']['train']['frames'],4)
            dataset=BCDataset(plan['train']);obs,action,stage=dataset[0]
            np.testing.assert_equal(obs['rgb'][0],obs['rgb'][2]);self.assertEqual(stage,-1)
            (a/'episode_0000/000000.json').write_text('{}')
            with self.assertRaises(ValueError):verify_prepared(plan)
    def test_seed_leakage_and_oom_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b';make_root(a);make_root(b)
            with self.assertRaises(ValueError):prepare([a],[b])
            (a/'DO_NOT_TRAIN.json').write_text('{}')
            with self.assertRaises(ValueError):audit_root(a)
    def test_corrupt_action_and_unsynced_data(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';e=make_root(a)
            with np.load(e/'000000.npz') as z:row={k:z[k] for k in z.files}
            row['action'][0]=np.nan;np.savez(e/'000000.npz',**row)
            with self.assertRaises(ValueError):audit_root(a)
    def test_backprop_and_checkpoint_inference(self):
        # One synthetic unit-test update only. No collected robot data / training run.
        torch.set_num_threads(2)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'data';make_root(root)
            _,episodes,_,_=audit_root(root);loader=DataLoader(BCDataset(episodes),batch_size=4)
            model=DualRGBDStudent();opt=torch.optim.AdamW(model.parameters(),lr=1e-4)
            obs,label,_=next(iter(loader));before=model.actor[-2].weight.detach().clone()
            loss=action_loss(model(**obs),label);loss.backward();opt.step()
            self.assertFalse(torch.equal(before,model.actor[-2].weight))
            metrics=evaluate(model,loader,'cpu');self.assertEqual(set(metrics['stage_mse']),{'-1','0','1','2'})
            checkpoint=Path(d)/'student.pt';atomic_save(dict(schema_version=2,camera_order=['right','rear'],student=model.state_dict()),checkpoint)
            self.assertIsNotNone(StudentInference(checkpoint))
    def test_cli_dry_run_and_synthetic_resume(self):
        import sys
        from unittest.mock import patch
        from train_student_bc import main
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a';b=root/'b';make_root(a);make_root(b,2)
            plan=root/'prepared.json';plan.write_text(json.dumps(prepare([a],[b])))
            common=['train_student_bc.py','--data',str(plan),'--device','cpu','--workers','0','--batch-size','4']
            with patch.object(sys,'argv',common):main()
            self.assertFalse((root/'first').exists())
            with patch.object(sys,'argv',common+['--execute','--epochs','1','--output',str(root/'first')]):main()
            with patch.object(sys,'argv',common+['--execute','--epochs','2','--resume',str(root/'first/student_last.pt'),'--output',str(root/'second')]):main()
            checkpoint=torch.load(root/'second/student_last.pt',weights_only=True)
            self.assertEqual(checkpoint['epoch'],2)
            self.assertTrue((root/'second/student_best.pt').exists())

if __name__=='__main__':unittest.main()


class RuntimeCompatibilityTest(unittest.TestCase):
    def test_only_missing_disabled_guards_are_equivalent(self):
        from harvest_rl.student_bc import canonical_teacher_runtime as canon
        old={'seed':70,'mass':.035}
        self.assertEqual(canon(old),canon(dict(old,seed=71,detached_capture_orientation=False,post_detach_hold_guard=False)))
        self.assertNotEqual(canon(old),canon(dict(old,post_detach_hold_guard=True)))
        self.assertNotEqual(canon(old),canon(dict(old,mass=.012)))
        self.assertNotIn('post_detach_hold_guard',old)
