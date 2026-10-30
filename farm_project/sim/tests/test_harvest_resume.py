"""비활성 과실 복원은 PhysX view가 아닌 보존 좌표로 bbox 중심을 맞춰야 한다."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as S
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.sorter_runtime import SorterRuntime


def test_restore_uses_cached_inactive_pose(tmp_path,monkeypatch):
    box=S(GetMin=lambda:np.array([4.,5.,6.]),GetMax=lambda:np.array([6.,7.,8.]))
    cache=S(ComputeWorldBound=lambda prim:S(ComputeAlignedRange=lambda:box))
    monkeypatch.setitem(sys.modules,'pxr',S(Usd=S(TimeCode=S(Default=lambda:0)),
        UsdGeom=S(BBoxCache=lambda *a,**k:cache)))
    (tmp_path/'manifest.json').write_text(json.dumps(dict(source_session='old',harvested_count=1,
        restore_mode='bbox',fruits=[dict(gt_id='/fruit',class_name='red',center_world_m=[10.,20.,30.])])))
    calls=[]
    a=S(paths=['/fruit'],current_positions=lambda:np.array([[5.,6.,6.9]]),
        rest_orientation=np.array([[1.,0.,0.,0.]]),
        relocate_detached=lambda *args,**kw:calls.append((args,kw)))
    runtime=SorterRuntime.__new__(SorterRuntime);runtime.fixture=[];runtime.session='new'
    runtime.scene=S(root=tmp_path,settings={'harvest_resume_manifest':'manifest.json'},
        physics=S(attachments=a),stage=S(GetPrimAtPath=lambda p:S(GetAttribute=lambda name:S(Get=lambda:'red'))))
    runtime.record=lambda *a,**k:None;runtime.write=lambda *a:None
    runtime.restore_harvest()
    args,kwargs=calls[0]
    assert args[0]==['/fruit'] and kwargs['fixture']
    np.testing.assert_allclose(args[1],[[10.,20.,29.9]])
    np.testing.assert_allclose(args[2],[[1.,0.,0.,0.]])
