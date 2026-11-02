"""기존 수신·정렬 코드는 재사용하고 실행 프로파일은 프로젝트 JSON에서 지정합니다."""
import json
from pathlib import Path
import threading
import time
from typing import Any
import pyrealsense2 as rs
import numpy as np
from continuous_camera import ContinuousCamera


class ConfiguredCamera(ContinuousCamera):
    def __init__(self, settings: dict[str, Any]) -> None:
        super().__init__()
        self._settings=settings
        self._color_sensor=None

    def start(self) -> dict[str, Any]:
        begin=time.monotonic()
        c=self._settings
        config=rs.config()
        config.enable_stream(rs.stream.color,c['width'],c['height'],rs.format.rgb8,c['fps'])
        config.enable_stream(rs.stream.depth,c['width'],c['height'],rs.format.z16,c['fps'])
        try:
            profile=self.pipe.start(config)
            pipeline_ready=time.monotonic()
            self.started=True
            self._color_sensor=profile.get_device().first_color_sensor()
            for option,value in ((rs.option.enable_auto_white_balance,c['auto_white_balance']),
                                 (rs.option.enable_auto_exposure,c['auto_exposure'])):
                if not self._color_sensor.supports(option):raise RuntimeError(f'Unsupported camera option: {option}')
                self._color_sensor.set_option(option,float(value))
            self.scale=profile.get_device().first_depth_sensor().get_depth_scale()
            options_ready=time.monotonic()
            self.thread=threading.Thread(target=self._receive,daemon=True)
            self.thread.start()
            deadline=time.monotonic()+c['warmup_timeout_s']
            with self.condition:
                while self.sequence<c['warmup_frames']:
                    self._check()
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise RuntimeError('Camera warmup timed out')
                    self.condition.wait(remaining)
            return {'start_and_warmup_s':time.monotonic()-begin,
                    'pipeline_start_s':pipeline_ready-begin,
                    'sensor_setup_s':options_ready-pipeline_ready,
                    'warmup_s':time.monotonic()-options_ready,**self._options()}
        except Exception:
            self.close()
            raise

    def _options(self) -> dict[str, Any]:
        sensor=self._color_sensor
        return {'white_balance':sensor.get_option(rs.option.white_balance),
                'auto_white_balance':sensor.get_option(rs.option.enable_auto_white_balance),
                'auto_exposure':sensor.get_option(rs.option.enable_auto_exposure),
                'warmup_frames':self._settings['warmup_frames']}

    def capture(self, output: str | Path, samples: int = 1) -> tuple[dict,dict]:
        info,timing=super().capture(output,samples)
        # 이전 로봇 워커는 depth_size를 기록하지 않아 실제 저장 배열에서 확인합니다.
        depth=np.load(Path(output)/'depth_m.npy',mmap_mode='r')
        info['depth_size']=[int(depth.shape[1]),int(depth.shape[0])]
        expected=[self._settings['width'],self._settings['height']]
        if info['rgb_size']!=expected or info['depth_size']!=expected:
            raise RuntimeError(f'Camera resolution mismatch: {info}')
        info.update(self._options(),requested_fps=self._settings['fps'])
        (Path(output)/'info.json').write_text(json.dumps(info,indent=2))
        return info,timing
