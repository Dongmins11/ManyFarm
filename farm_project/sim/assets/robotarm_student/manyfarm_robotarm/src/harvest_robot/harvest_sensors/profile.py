"""Measured D435 internal geometry and shared real/sim pinhole preprocessing.

No ROS, CUDA, simulator or hardware is imported. Nonzero lens distortion fails
closed: this version requires already rectified or zero-coefficient images.
"""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np

SCHEMA = 'd435_student_sensor_v1'
STREAMS = ('rgb', 'depth', 'ir_left', 'ir_right')
VARIANTS = {'rgbd': (), 'rgbd_ir_left': ('ir_left',),
            'rgbd_ir_right': ('ir_right',), 'rgbd_ir_pair': ('ir_left', 'ir_right')}


def matrix(spec):
    i = spec['intrinsics']
    return np.array([[i['fx'], 0, i['ppx']], [0, i['fy'], i['ppy']], [0, 0, 1]], float)


def validate(config):
    if config.get('schema') != SCHEMA:
        raise ValueError('Wrong sensor schema; nominal/v2 config is not interchangeable')
    for name, view in config['views'].items():
        for stream, spec in view['streams'].items():
            if stream not in STREAMS or spec['width'] <= 0 or spec['height'] <= 0 or spec['fps'] <= 0:
                raise ValueError('Invalid stream profile')
            k = matrix(spec)
            if not np.isfinite(k).all() or min(k[0, 0], k[1, 1]) <= 0:
                raise ValueError('Invalid K')
            if any(float(c) != 0 for c in spec['intrinsics']['coeffs']):
                raise ValueError('Nonzero distortion requires explicit rectification before this pinhole path')
            t = np.asarray(view['rgb_from_stream'][stream], float)
            if t.shape != (4, 4) or not np.isfinite(t).all() or not np.allclose(t[3], [0, 0, 0, 1]):
                raise ValueError('Invalid optical transform')
            if not np.allclose(t[:3, :3].T @ t[:3, :3], np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(t[:3, :3]), 1, atol=1e-5):
                raise ValueError('Optical transform must be a rigid rotation')
        if not np.allclose(view['rgb_from_stream']['rgb'], np.eye(4)):
            raise ValueError('RGB optical frame must be the reference')
    if not 0 < config['depth_min_m'] < config['depth_max_m']:
        raise ValueError('Invalid depth acceptance range')
    return config


def from_snapshot(path, rear_nominal=None):
    path = Path(path)
    raw = path.read_bytes(); data = json.loads(raw)
    if data.get('schema') != 'd435_all_inputs_v1':
        raise ValueError('Expected original SDK capture metadata')
    streams = copy.deepcopy(data['streams'])
    view = dict(streams=streams, rgb_from_stream=data['rgb_from_stream'],
        internal_calibration_verified=True, mount_calibration_verified=False,
        rgb_optical_frame='arm_2/wrist_camera_color_optical_frame',
        mount_reference='current composed URDF; real gripper-to-camera hand-eye not measured',
        device=data['device'], emitter_setting=data['original_emitter_setting'],depth_scale_m=data['depth_scale_m'])
    result = dict(schema=SCHEMA, source=dict(path=str(path.resolve()),
        sha256=hashlib.sha256(raw).hexdigest(), started_utc=data['started_utc']),
        views={'right': view}, render_near_m=.01, render_far_m=20.,
        depth_min_m=.28, depth_max_m=3.,
        sim_depth_model='ideal optical-Z plus conservative range gate; not physical stereo confidence',
        sim_ir_model='luminance of visible-light render at factory IR pose; not NIR/projector simulation',
        acquisition_hz=streams['rgb']['fps'], policy_hz=20,
        preprocessing='aspect-preserving letterbox 160x90; depth nearest; RGB/IR area; separate branches',
        training_started=False)
    if rear_nominal is not None:
        rear = {'streams': {}, 'rgb_from_stream': {}, 'internal_calibration_verified': False,
                'mount_calibration_verified': False, 'rgb_optical_frame': 'top_camera_color_optical_frame',
                'mount_reference': 'unmeasured rear; nominal composed URDF', 'emitter_setting': None}
        for stream in ('rgb', 'depth'):
            s = rear_nominal[stream]; f = s['width'] / (2*np.tan(np.deg2rad(s['horizontal_fov_deg'])/2))
            rear['streams'][stream] = dict(width=s['width'], height=s['height'], fps=rear_nominal['fps'],
                intrinsics=dict(fx=float(f), fy=float(f), ppx=s['width']/2, ppy=s['height']/2,
                                coeffs=[0]*5, distortion_model='nominal_pinhole'))
        rear['rgb_from_stream']['rgb'] = np.eye(4).tolist()
        # Explicitly resolved from URDF by optical_poses, not guessed from the wrist SDK.
        rear['rgb_from_stream']['depth'] = np.eye(4).tolist()
        rear['resolve_depth_extrinsic_from_urdf'] = True
        result['views']['rear'] = rear
    return validate(result)


def optical_poses(kin, q, config, world_from_robot=None):
    world = np.eye(4) if world_from_robot is None else np.asarray(world_from_robot)
    result = {}
    for name, view in config['views'].items():
        rgb = world @ kin.fk(q, view['rgb_optical_frame'])
        result[name] = {s: rgb @ np.asarray(view['rgb_from_stream'][s]) for s in view['streams']}
        if view.get('resolve_depth_extrinsic_from_urdf'):
            result[name]['depth'] = world @ kin.fk(q, 'top_camera_depth_optical_frame')
    return result


def fov_degrees(spec):
    k = matrix(spec); w, h = spec['width'], spec['height']
    # Off-centre left+right / top+bottom angles, rather than centred approximation.
    return [float(np.rad2deg(np.arctan(k[0,2]/k[0,0]) + np.arctan((w-k[0,2])/k[0,0]))),
            float(np.rad2deg(np.arctan(k[1,2]/k[1,1]) + np.arctan((h-k[1,2])/k[1,1])))]


def centred_render_spec(spec):
    """Superset render + inverse remap bypasses Isaac Lab's centred square K.

    The ray at each delivered native pixel uses the requested measured K. The
    render canvas is slightly larger so off-centre edges are never cropped.
    """
    k = matrix(spec); f = k[0, 0]
    width = int(np.ceil(2*max(k[0,2], spec['width']-1-k[0,2]))) + 6
    height = int(np.ceil(2*max(k[1,2], spec['height']-1-k[1,2])*f/k[1,1])) + 6
    render_k = np.array([[f,0,width/2],[0,f,height/2],[0,0,1]], float)
    y,x = np.mgrid[:spec['height'], :spec['width']]
    mx = ((x-k[0,2])/k[0,0]*f+width/2).astype(np.float32)
    my = ((y-k[1,2])/k[1,1]*f+height/2).astype(np.float32)
    return width, height, render_k, mx, my


def remap_render(array, spec, depth=False):
    import cv2
    w,h,_,mx,my = centred_render_spec(spec)
    if array.shape[:2] != (h,w):
        raise ValueError('Rendered image dimensions differ from planned superset')
    return cv2.remap(array, mx, my, cv2.INTER_NEAREST if depth else cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def letterbox(image, width=160, height=90, nearest=False):
    import cv2
    h,w = image.shape[:2]; scale = min(width/w, height/h)
    rw,rh = min(width, max(1, round(w*scale))), min(height, max(1, round(h*scale)))
    x,y = (width-rw)//2, (height-rh)//2
    resized = cv2.resize(image, (rw,rh), interpolation=cv2.INTER_NEAREST if nearest else cv2.INTER_AREA)
    out = np.zeros((height,width)+image.shape[2:], image.dtype); mask = np.zeros((height,width), bool)
    out[y:y+rh,x:x+rw] = resized; mask[y:y+rh,x:x+rw] = True
    return out, mask, dict(scale_xy=[rw/w,rh/h], offset_xy=[x,y], native_wh=[w,h])


def pack_view(rgb, aligned_depth, ir, variant='rgbd', maximum=3.):
    if variant not in VARIANTS:
        raise ValueError('Unknown sensor comparison variant')
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or aligned_depth.shape != rgb.shape[:2]:
        raise ValueError('Expected native RGB8 and RGB-aligned depth')
    colour,pad,geometry = letterbox(rgb)
    depth,_,_ = letterbox(aligned_depth, nearest=True)
    valid = np.isfinite(depth) & (depth>0) & (depth<=maximum)
    rgbd = np.concatenate([colour.astype(np.float32)/255, np.where(valid,depth/maximum,0)[...,None],
                           valid[...,None].astype(np.float32)],axis=2).transpose(2,0,1)
    result = dict(rgbd=rgbd, rgb_pixel_valid=pad, rgb_resize=geometry)
    for stream in VARIANTS[variant]:
        native = ir[stream]
        if native.dtype != np.uint8 or native.ndim != 2:
            raise ValueError('Expected IR Y8 in its own optical view')
        a,m,g = letterbox(native)
        result[stream] = a[None].astype(np.float32)/255
        result[stream+'_pixel_valid'] = m
        result[stream+'_resize'] = g
    return result


class AcquisitionGate:
    """Acquire at sensor rate, hold last frame between controller ticks."""
    def __init__(self, fps):
        if not np.isfinite(fps) or fps <= 0: raise ValueError('Invalid sensor fps')
        self.period = 1/float(fps); self.time = 0.; self.last = None; self.sequence = -1; self.next_due = None

    def update(self, dt):
        if not np.isfinite(dt) or dt < 0: raise ValueError('Invalid dt')
        self.time += dt
        due = self.next_due is None or self.time >= self.next_due-1e-9
        if due:
            self.last = self.time; self.sequence += 1
            if self.next_due is None:
                self.next_due = self.time+self.period
            else:
                self.next_due += (int(np.floor((self.time-self.next_due+1e-9)/self.period))+1)*self.period
        return due

    @property
    def age(self):
        return None if self.last is None else self.time-self.last
