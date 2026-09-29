"""B observation geometry + reversible crop/letterbox. No noise or blur.

The design plane is vertical and transverse to the camera's horizontal heading.
This is valid for a stopped, bed-facing observation, not a map-localized bed plane.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np


class GeometryError(ValueError):
    pass


def observation_polygon(metadata, width, height, config):
    K = np.asarray(metadata['K'], dtype=float)
    T = np.asarray(metadata['T_odom_camera_optical'], dtype=float)
    if K.shape != (3, 3) or T.shape != (4, 4) or not np.isfinite(K).all() or not np.isfinite(T).all():
        raise GeometryError('Camera K/pose is invalid')
    if not np.allclose(K[2], [0, 0, 1]) or abs(K[0, 1]) > 1e-6 or K[0, 0] <= 0 or K[1, 1] <= 0:
        raise GeometryError('Expected rectified pinhole intrinsics')
    R, eye = T[:3, :3], T[:3, 3]
    if not np.allclose(R.T @ R, np.eye(3), atol=1e-4) or not np.isclose(np.linalg.det(R), 1.0, atol=1e-4):
        raise GeometryError('Camera rotation is invalid')
    edge = float(config['edge_fraction'])
    distance = float(config['camera_to_bed_plane_m'])
    zlo, zhi = map(float, config['height_band_m'])
    if not all(map(math.isfinite, [edge, distance, zlo, zhi])) or not 0 <= edge < .4 or distance <= 0 or zlo >= zhi:
        raise GeometryError('Invalid B observation settings')
    up = np.array([0., 0., 1.])
    normal = R[:, 2].copy(); normal[2] = 0.
    length = np.linalg.norm(normal)
    if length < .1:
        raise GeometryError('Camera must face a vertical bed, not the ground/sky')
    normal /= length
    right = np.cross(normal, up)
    def project(s, z):
        local = R.T @ (normal*distance + right*s + up*(z-eye[2]))
        if local[2] <= 0: raise GeometryError('Observation plane is behind camera')
        return (K @ local)[:2] / local[2]
    # Same B rule: safe horizontal interval shared by BOTH height boundaries.
    intervals = []
    for z in (zlo, zhi):
        limits = []
        for u in (width*edge, width*(1-edge)):
            column_plane = R[:, 0] - ((u-K[0, 2])/K[0, 0])*R[:, 2]
            denom = column_plane @ right
            if abs(denom) < 1e-8: raise GeometryError('Camera view is not transverse to bed')
            s = -float(column_plane @ (normal*distance + up*(z-eye[2]))) / denom
            uv = project(s, z)
            if not -1e-5 <= uv[1] <= height+1e-5:
                raise GeometryError(f'B height band {zlo:.2f}..{zhi:.2f} m is outside camera vertical FOV')
            limits.append(s)
        intervals.append(sorted(limits))
    lo = max(x[0] for x in intervals); hi = min(x[1] for x in intervals)
    if hi <= lo: raise GeometryError('B common observation width is empty')
    polygon = np.array([project(lo,zhi),project(hi,zhi),project(hi,zlo),project(lo,zlo)])
    if (polygon[:,0] < -1e-4).any() or (polygon[:,0] > width+1e-4).any():
        raise GeometryError('B common observation polygon leaves the image')
    return polygon, {'usable_width_m': hi-lo, 'height_band_m': [zlo,zhi],
                     'plane_distance_m': distance, 'plane_scope': 'transverse_design_plane_not_map_bed'}


@dataclass
class CropTransform:
    x0: int
    y0: int
    x1: int
    y1: int
    resized_width: int
    resized_height: int
    pad_left: int
    pad_top: int
    size: int

    @property
    def scale_x(self): return self.resized_width / (self.x1-self.x0)
    @property
    def scale_y(self): return self.resized_height / (self.y1-self.y0)

    def to_original(self, xy):
        """Pixel-centre convention matching OpenCV resize; do not apply K to padded pixels."""
        xy = np.asarray(xy, dtype=float).copy()
        xy[...,0] = (xy[...,0]-self.pad_left+.5)/self.scale_x-.5+self.x0
        xy[...,1] = (xy[...,1]-self.pad_top+.5)/self.scale_y-.5+self.y0
        return xy

    def to_network(self, xy):
        xy = np.asarray(xy, dtype=float).copy()
        xy[...,0] = (xy[...,0]-self.x0+.5)*self.scale_x-.5+self.pad_left
        xy[...,1] = (xy[...,1]-self.y0+.5)*self.scale_y-.5+self.pad_top
        return xy

    def to_dict(self): return dict(asdict(self), scale_x=self.scale_x, scale_y=self.scale_y)

    def mask_to_original(self, mask, width, height):
        import cv2
        if mask.shape != (self.size, self.size): raise ValueError('Unexpected network mask size')
        roi = mask[self.pad_top:self.pad_top+self.resized_height,
                   self.pad_left:self.pad_left+self.resized_width].astype(np.uint8)
        result = np.zeros((height,width),np.uint8)
        result[self.y0:self.y1,self.x0:self.x1] = cv2.resize(roi,(self.x1-self.x0,self.y1-self.y0),interpolation=cv2.INTER_NEAREST)
        return result.astype(bool)


def prepare(rgb, metadata, config):
    import cv2
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError('Expected RGB uint8 HWC image')
    h,w = rgb.shape[:2]
    polygon, geometry = observation_polygon(metadata,w,h,config)
    # Expand actual image coverage, including the inference mask, before letterboxing.
    margin_fraction = float(config.get('vertical_margin_fraction', 0.0))
    if not math.isfinite(margin_fraction) or not 0 <= margin_fraction <= 1:
        raise GeometryError('vertical_margin_fraction must be finite and between 0 and 1')
    geometry['observation_polygon_original_px'] = polygon.tolist()
    margin_px = float(np.ptp(polygon[:, 1])) * margin_fraction
    if margin_px > 0:
        expanded = cv2.convexHull(np.vstack([
            polygon + [0., -margin_px], polygon + [0., margin_px]
        ]).astype(np.float32)).reshape(-1, 2)
        image_bounds = np.array([[0,0],[w,0],[w,h],[0,h]], dtype=np.float32)
        area, clipped = cv2.intersectConvexConvex(expanded, image_bounds)
        if clipped is None or area <= 0:
            raise GeometryError('Expanded observation crop is empty')
        polygon = clipped.reshape(-1, 2)
    geometry['vertical_margin_fraction'] = margin_fraction
    geometry['vertical_margin_requested_px'] = margin_px
    x0,y0 = np.maximum(np.floor(polygon.min(axis=0)).astype(int),[0,0])
    x1,y1 = np.minimum(np.ceil(polygon.max(axis=0)).astype(int),[w,h])
    if x1-x0 < 2 or y1-y0 < 2: raise GeometryError('Observation crop is too small')
    valid = np.zeros((h,w),np.uint8)
    cv2.fillConvexPoly(valid,np.rint(polygon).astype(np.int32),1)
    size = int(config['input_size']); fill = int(config['pad_value'])
    if not 32 <= size <= 2048 or size % 32 or not 0 <= fill <= 255:
        raise ValueError('input_size must be a multiple of 32; pad_value must be 0..255')
    # NumPy input to Ultralytics uses BGR; shared memory is explicitly RGB.
    crop = np.ascontiguousarray(rgb[y0:y1,x0:x1,::-1])
    crop[valid[y0:y1,x0:x1] == 0] = fill
    scale = min(size/(x1-x0),size/(y1-y0))
    rw,rh = max(1,round((x1-x0)*scale)),max(1,round((y1-y0)*scale))
    left,top = (size-rw)//2,(size-rh)//2
    transform = CropTransform(int(x0),int(y0),int(x1),int(y1),rw,rh,left,top,size)
    network = np.full((size,size,3),fill,np.uint8)
    network[top:top+rh,left:left+rw] = cv2.resize(crop,(rw,rh),interpolation=cv2.INTER_LINEAR)
    network_valid = np.zeros((size,size),np.uint8)
    network_valid[top:top+rh,left:left+rw] = cv2.resize(valid[y0:y1,x0:x1],(rw,rh),interpolation=cv2.INTER_NEAREST)
    geometry['polygon_original_px'] = polygon.tolist()
    return network, network_valid.astype(bool), transform, geometry
