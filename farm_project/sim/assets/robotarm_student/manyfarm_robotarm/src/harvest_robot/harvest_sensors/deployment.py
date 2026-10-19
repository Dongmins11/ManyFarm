"""Deployment RGB-D geometry and timing contract. No simulator imports."""
import copy
import json
from pathlib import Path
import numpy as np
from .profile import validate, SCHEMA, optical_poses

SCHEMA_DEPLOYMENT = 'd435_deployment_v2'
CAPTURE_CONTRACT = 'physics_scheduled_multimodal_v3'


def is_deployment(config):
    return config.get('schema') == SCHEMA_DEPLOYMENT


def validate_deployment(config):
    if not is_deployment(config):
        raise ValueError('Expected deployment camera profile')
    adapted = copy.deepcopy(config); adapted['schema'] = SCHEMA
    validate(adapted)
    if config['camera_order'] != ['right', 'rear'] or set(config['views']) != {'right', 'rear'}:
        raise ValueError('Require right/rear camera order')
    if config['capture_contract'] != CAPTURE_CONTRACT or config['history'] != 3:
        raise ValueError('Wrong deployment history/capture contract')
    if not np.isclose(config['control_dt'], .05) or config['policy_hz'] != 20:
        raise ValueError('Deployment controller must remain 20Hz')
    if config['fps'] != 30 or not np.isclose(config['sensor_dt'], 1/30):
        raise ValueError('Deployment acquisition must be 30Hz')
    for view in config['views'].values():
        required={'rgb','depth','ir_right'} if view is config['views']['right'] else {'rgb','depth'}
        if set(view['streams']) != required:
            raise ValueError('Require wrist RGB+right IR and rear RGB-D')
        for stream, wh in [('rgb', (1280, 720)), ('depth', (848, 480))]:
            spec = view['streams'][stream]
            if (spec['width'], spec['height']) != wh or spec['fps'] != 30:
                raise ValueError('Unexpected deployment stream resolution/rate')
        if 'ir_right' in view['streams']:
            ir=view['streams']['ir_right']
            if (ir['width'],ir['height'],ir['fps'])!=(848,480,30):raise ValueError('Unexpected wrist IR profile')
    if config['student_schema_version'] != 3 or config['policy_inputs'] != {'right':['rgb','ir_right'],'rear':['rgb','aligned_depth_m','depth_valid']}:
        raise ValueError('Wrong multimodal Student contract')
    return adapted


class PhysicsCaptureClock:
    """Integer physics-step clock; no frame invented at control boundaries."""
    def __init__(self, physics_dt, control_dt=.05, fps=30):
        self.dt = float(physics_dt)
        self.stride = round(1/fps/self.dt)
        self.control_stride = round(control_dt/self.dt)
        if self.stride < 1 or not np.isclose(self.stride*self.dt, 1/fps, atol=1e-10):
            raise ValueError('Sensor period must be an integer number of physics steps')
        if not np.isclose(self.control_stride*self.dt, control_dt, atol=1e-10):
            raise ValueError('Controller period must be an integer number of physics steps')
        self.reset()

    def reset(self):
        self.steps = 0; self.sequence = 0; self.stamp = 0.

    @property
    def time(self):
        return self.steps*self.dt

    def advance(self, dt):
        if not np.isclose(dt, self.dt, atol=1e-12):
            raise ValueError('Capture hook must run once per physical step')
        self.steps += 1
        if self.steps % self.stride:
            return False
        self.sequence += 1; self.stamp = self.time
        return True


def expected_poses(kin, q, config, world_from_robot=None):
    # RGB mount comes from composed URDF, depth mount from factory internal TF.
    return optical_poses(kin, q, config, world_from_robot)


def audit_camera_sample(annotation, control_dt, previous=None):
    """Check saved acquisition evidence independently of current control joints."""
    now = annotation['stamp_s']; cameras = annotation['cameras']
    if set(cameras) != {'right', 'rear'}:
        raise ValueError('Missing acquisition evidence')
    for name, c in cameras.items():
        t, p, number = c['stamp_s'], c['pose_stamp_s'], c['frame_number']
        if not np.isfinite([now, t, p, c['fk_max_error']]).all():
            raise ValueError('Nonfinite camera evidence')
        if abs(t-p) > 1e-9 or not -1e-9 <= now-t < 1/30+1e-8:
            raise ValueError('Camera/pose time mismatch or stale frame')
        if not isinstance(number, int) or number < 0 or abs(t-number/30) > 1e-8:
            raise ValueError('Camera number/timestamp mismatch')
        if c['fk_max_error'] > 2e-4 or len(c['capture_joint_rad']) != 6:
            raise ValueError('Missing/invalid acquisition FK')
        if previous is not None:
            old = previous['cameras'][name]
            delta = number-old['frame_number']
            if delta < 0 or delta > 2:
                raise ValueError('Incorrect camera sequence at 20Hz control')
            if delta == 0 and (t != old['stamp_s'] or p != old['pose_stamp_s']):
                raise ValueError('Reused frame timestamp changed')
        raw = c.get('raw_capture')
        if not raw:
            raise ValueError('Missing original RGB/depth evidence')


def audit_raw_captures(root, manifest, run):
    """Recompute capture-time FK/K/transform and check *all* native frames."""
    from harvest_rl.kinematics import ArmKinematics
    from .profile import matrix
    kin = ArmKinematics(Path(run['current_asset']['source_urdf']))
    world = np.asarray(run['current_base_to_policy_world'])
    counts = {}; maximum = 0.; durations = {}
    for name in ('right', 'rear'):
        folder = Path(root)/'raw_captures'/name
        files = sorted(folder.glob('*.npz')); counts[name] = len(files)
        if not files: raise ValueError('Missing native acquisitions')
        last = None
        for number, path in enumerate(files):
            m = json.loads(path.with_suffix('.json').read_text())
            if m['frame_number'] != number or abs(m['stamp_s']-number/30) > 1e-8 or m['stamp_s'] != m['pose_stamp_s']:
                raise ValueError('Native sequence/time mismatch')
            poses = expected_poses(kin, np.asarray(m['capture_joint_rad']), manifest['camera_config'], world)[name]
            for stream, expected in poses.items():
                error = float(np.abs(expected-np.asarray(m['world_from_optical'][stream])).max())
                maximum = max(maximum, error)
                if error > 2e-4: raise ValueError('Saved native FK mismatch')
                np.testing.assert_allclose(m['intrinsics'][stream], matrix(manifest['camera_config']['views'][name]['streams'][stream]), atol=1e-8)
            relative = np.linalg.inv(np.asarray(m['world_from_optical']['rgb'])) @ np.asarray(m['world_from_optical']['depth'])
            if not np.allclose(relative, m['color_from_depth'], atol=2e-6): raise ValueError('Saved depth transform mismatch')
            if not np.allclose(relative, manifest['camera_config']['views'][name]['rgb_from_stream']['depth'], atol=2e-6):
                raise ValueError('Factory transform direction mismatch')
            with np.load(path, allow_pickle=False) as z:
                if z['rgb'].shape != (720,1280,3) or z['rgb'].dtype != np.uint8 or z['raw_depth_m'].shape != (480,848):
                    raise ValueError('Native profile mismatch')
                if z['aligned_depth_m'].shape != (720,1280) or z['raw_depth_m'].dtype != np.float32:
                    raise ValueError('Native optical-Z dtype/shape mismatch')
                if not np.array_equal(z['aligned_depth_m'] > 0, z['aligned_depth_valid']): raise ValueError('Aligned mask mismatch')
                if name=='right' and (z['ir_right'].shape!=(480,848) or z['ir_right'].dtype!=np.uint8):raise ValueError('Right IR profile mismatch')
            last = m['stamp_s']
        durations[name] = last
    if counts['right'] != counts['rear']: raise ValueError('Camera acquisition counts differ')
    return dict(native_frames=counts, duration_s=durations, camera_hz=30, max_camera_fk_matrix_error=maximum)


class RawCaptureWriter:
    """Append-only native data for every acquisition, outside Student input NPZ."""
    def __init__(self, root):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)

    def append(self, capture):
        for name, data in capture.items():
            folder = self.root/name; folder.mkdir(exist_ok=True)
            path = folder/f"{data['frame_number']:06d}.npz"
            with path.open('xb') as f:
                np.savez_compressed(f, rgb=data['rgb'], raw_depth_m=data['raw_depth_m'],
                    depth_valid=data['depth_valid'], aligned_depth_m=data['aligned_depth_m'],
                    aligned_depth_valid=data['aligned_depth_m'] > 0, **data['ir'])
            data['raw_capture'] = str(path.resolve())
            meta = {k: data[k] for k in ('frame_number', 'stamp_s', 'pose_stamp_s', 'capture_joint_rad', 'fk_max_error')}
            meta.update(intrinsics={s:k.tolist() for s,k in data['intrinsics'].items()},
                world_from_optical={s:t.tolist() for s,t in data['world_from_optical'].items()},
                color_from_depth=data['color_from_depth'].tolist(), renderer_checks=data['renderer_checks'])
            path.with_suffix('.json').write_text(json.dumps(meta, indent=2))
