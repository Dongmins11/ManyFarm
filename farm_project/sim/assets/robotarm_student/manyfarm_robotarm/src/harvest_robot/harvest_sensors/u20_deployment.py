"""Opt-in wrist U20 RGB / rear D435 RGB-D contract; no invented IR/depth."""
import copy, json, hashlib
from pathlib import Path
import numpy as np
from .profile import SCHEMA, validate, matrix
from .deployment import RawCaptureWriter as D435Writer, expected_poses

SCHEMA_U20='u20_wrist_rgb_rear_d435_v1'
CAPTURE_CONTRACT='physics_scheduled_u20_rgb_v1'

def is_u20(config):return config.get('schema')==SCHEMA_U20

def reference_urdf(config):
    from harvest_rl.settings import ROOT,URDF
    path=Path(config.get('sensor_reference_urdf',URDF))
    return path if path.is_absolute() else ROOT/path

def validate_u20(config):
    if not is_u20(config):raise ValueError('Expected U20 wrist camera profile')
    if config.get('wrist_visual_arms') != [1,2]:raise ValueError('Both wrists must use U20 visuals in this revision')
    if config['camera_order']!=['right','rear'] or set(config['views'])!={'right','rear'}:raise ValueError('U20 view order')
    if set(config['views']['right']['streams'])!={'rgb'}:raise ValueError('U20 has no depth or right IR')
    if set(config['views']['rear']['streams'])!={'rgb','depth'}:raise ValueError('Rear must remain D435 RGB-D')
    adapted=copy.deepcopy(config);adapted['schema']=SCHEMA;validate(adapted)
    if config['capture_contract']!=CAPTURE_CONTRACT or config['student_schema_version']!=4:raise ValueError('U20 data contract')
    if config['policy_inputs']!={'right':['rgb'],'rear':['rgb','aligned_depth_m','depth_valid']}:raise ValueError('U20 input contract')
    if config['history']!=3 or config['fps']!=30 or config['policy_hz']!=20 or not np.isclose(config['control_dt'],.05):raise ValueError('U20 timing contract')
    for view in config['views'].values():
        if any(s['fps']!=30 for s in view['streams'].values()):raise ValueError('All streams must be30Hz')
    path=reference_urdf(config)
    if not path.is_file():raise ValueError('Missing U20 variant URDF; run build_u20_wrist_variant.py')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=config['sensor_reference_urdf_sha256']:
        raise ValueError('U20 URDF differs from pinned camera profile; preserve old datasets and create a new revision')
    return adapted

def pack_observation(frames,proprio,tcp_arm,target,now,capture,ttl=.3):
    from harvest_rl.student_v2 import pack_observation as pack
    result=pack(frames,proprio,tcp_arm,target,now,ttl)
    result['depth_m'][0]=0 # Explicit absent wrist modality, never simulated U20 depth.
    if capture['right'].get('ir') or capture['right'].get('depth_available') is not False:
        raise ValueError('U20 capture must be RGB-only')
    return result

class RawCaptureWriter(D435Writer):
    def append(self,capture):
        super().append({'rear':capture['rear']})
        data=capture['right'];folder=self.root/'right';folder.mkdir(exist_ok=True)
        path=folder/f"{data['frame_number']:06d}.npz"
        with path.open('xb') as f:np.savez_compressed(f,rgb=data['rgb'])
        data['raw_capture']=str(path.resolve())
        meta={k:data[k] for k in ('frame_number','stamp_s','pose_stamp_s','capture_joint_rad','fk_max_error')}
        meta.update(camera_model='U20CAM-1080P-1',available_streams=['rgb'],
            intrinsics={'rgb':data['intrinsics']['rgb'].tolist()},world_from_optical={'rgb':data['world_from_optical']['rgb'].tolist()},
            renderer_checks=data['renderer_checks'])
        path.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')

def audit_raw_captures(root,manifest,run):
    from harvest_rl.kinematics import ArmKinematics
    kin=ArmKinematics(Path(run['current_asset']['source_urdf']));config=manifest['camera_config']
    counts={};maximum=0.
    for name,view in config['views'].items():
        files=sorted((Path(root)/'raw_captures'/name).glob('*.npz'));counts[name]=len(files)
        if not files:raise ValueError('Missing U20 native acquisitions')
        for number,path in enumerate(files):
            m=json.loads(path.with_suffix('.json').read_text())
            if m['frame_number']!=number or abs(m['stamp_s']-number/30)>1e-8 or m['stamp_s']!=m['pose_stamp_s']:raise ValueError('Native frame clock mismatch')
            poses=expected_poses(kin,np.asarray(m['capture_joint_rad']),config,np.asarray(run['current_base_to_policy_world']))[name]
            for stream,pose in poses.items():
                error=float(np.abs(pose-np.asarray(m['world_from_optical'][stream])).max());maximum=max(maximum,error)
                if error>2e-4:raise ValueError('U20 capture-time FK mismatch')
                np.testing.assert_allclose(m['intrinsics'][stream],matrix(view['streams'][stream]),atol=1e-8)
            with np.load(path,allow_pickle=False) as z:
                spec=view['streams']['rgb']
                if z['rgb'].shape!=(spec['height'],spec['width'],3) or z['rgb'].dtype!=np.uint8:raise ValueError('U20 RGB profile mismatch')
                if name=='right' and set(z.files)!={'rgb'}:raise ValueError('Invented U20 modality')
                if name=='rear' and (z['raw_depth_m'].shape!=(480,848) or not np.array_equal(z['aligned_depth_m']>0,z['aligned_depth_valid'])):raise ValueError('Rear depth mismatch')
    if counts['right']!=counts['rear']:raise ValueError('Camera counts differ')
    return dict(audit_passed=True,native_frames=counts,max_camera_fk_matrix_error=maximum,capture_contract=CAPTURE_CONTRACT)
