"""Camera input only: no ROS publication, marker detection, or motion commands."""
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
import time
import numpy as np
import yaml


@dataclass(frozen=True)
class Frame:
    pixels: object
    stamp_ns: int
    frame_id: str
    received_at: float


class LatestFrame:
    def __init__(self):
        self._lock = Lock()
        self._frame = None
        self._last_stamp = -1

    def put(self, frame):
        with self._lock:
            if frame.stamp_ns <= self._last_stamp:
                return False
            self._last_stamp = frame.stamp_ns
            self._frame = frame
            return True

    def take(self):
        with self._lock:
            frame, self._frame = self._frame, None
            return frame

    def clear(self):
        with self._lock:
            self._frame = None
            self._last_stamp = -1


def load_calibration(filename, width, height):
    data = yaml.safe_load(Path(filename).expanduser().read_text())
    if (data.get('image_width'), data.get('image_height')) != (width, height):
        raise ValueError('Calibration resolution differs from capture resolution')
    if data.get('distortion_model') != 'plumb_bob':
        raise ValueError('Only raw plumb_bob calibration is supported')
    k = np.asarray(data['camera_matrix']['data'], dtype=float).reshape(3, 3)
    d = np.asarray(data['distortion_coefficients']['data'], dtype=float)
    if (not np.isfinite(k).all() or not np.isfinite(d).all()
            or k[0, 0] <= 0 or k[1, 1] <= 0 or d.size not in (4, 5, 8, 12, 14)):
        raise ValueError('Invalid calibration coefficients')
    return k, d


class PicameraInput:
    """Picamera2 callback copies one latest BGR frame; executor performs detection.

    SensorTimestamp uses CLOCK_BOOTTIME. Conversion preserves acquisition age,
    rather than stamping delivery time. Real hardware only (no use_sim_time).
    Explicit sensor mode and ScalerCrop must match the calibrated pipeline.
    """
    def __init__(self, slot, ros_now_ns, *, index, width, height, fps,
                 frame_id, sensor_size, sensor_bit_depth, crop):
        if (width <= 0 or height <= 0 or fps <= 0
                or len(sensor_size) != 2 or min(sensor_size) <= 0
                or sensor_bit_depth <= 0 or len(crop) != 4
                or min(crop[:2]) < 0 or min(crop[2:]) <= 0):
            raise ValueError('Explicit valid capture geometry is required')
        self.slot, self.now = slot, ros_now_ns
        self.index, self.size, self.fps = index, (width, height), fps
        self.frame_id = frame_id
        self.sensor_size, self.sensor_bit_depth = sensor_size, sensor_bit_depth
        self.crop = crop
        self.camera = None
        self.error = None
        self.active = False
        self._lock = Lock()

    def start(self):
        if self.camera is not None:
            return
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise RuntimeError('Direct capture requires compatible Picamera2/libcamera bindings') from exc
        camera = Picamera2(self.index)
        try:
            cfg = camera.create_preview_configuration(
                main={'size': self.size, 'format': 'RGB888'},
                sensor={'output_size': tuple(self.sensor_size), 'bit_depth': self.sensor_bit_depth},
                controls={'FrameRate': self.fps, 'ScalerCrop': tuple(self.crop)},
                buffer_count=4, queue=False)
            camera.configure(cfg)
            self.error = None
            self.active = True
            camera.pre_callback = self._capture
            self.camera = camera
            camera.start()
        except Exception:
            self.active = False
            self.camera = None
            camera.close()
            raise

    def _capture(self, request):
        with self._lock:
            if not self.active:
                return
            try:
                metadata = request.get_metadata()
                if tuple(metadata.get('ScalerCrop', ())) != tuple(self.crop):
                    raise ValueError('Actual ScalerCrop differs from calibrated capture configuration')
                stamp = int(metadata['SensorTimestamp'])
                age_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME) - stamp
                if age_ns < 0:
                    raise ValueError('Invalid sensor timestamp clock')
                image = request.make_array('main').copy()
                if image.shape != (self.size[1], self.size[0], 3):
                    raise ValueError('Unexpected capture dimensions')
                # libcamera RGB888 is BGR byte order, suitable for OpenCV.
                self.slot.put(Frame(image, self.now() - age_ns,
                                    self.frame_id, time.monotonic()))
            except Exception as exc:
                self.error = str(exc)
                self.active = False

    def stop(self):
        with self._lock:
            self.active = False
        camera, self.camera = self.camera, None
        if camera is not None:
            try:
                camera.stop()
            finally:
                camera.close()
        self.slot.clear()
