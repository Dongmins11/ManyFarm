#!/usr/bin/env python3
"""카메라 최신 프레임을 읽는 예시. 추론은 reader.read() 다음에 연결하세요."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot/ros_ws/src/farm_common'))
import numpy as np
from farm_common.rgbd_shm import RgbdReader

parser=argparse.ArgumentParser()
parser.add_argument('--name',default='farm_scout_01_rgbd')
args=parser.parse_args()
reader=RgbdReader(args.name)
print('RGB-D 대기. Ctrl+C로 종료합니다.',flush=True)
last_print=0.0
try:
    while True:
        frame=reader.read()
        if frame is not None and time.monotonic()-last_print>=1.0:
            m=frame['metadata'];valid=np.isfinite(frame['depth'])
            print(f"frame={m['sequence']} sim={m['stamp_ns']/1e9:.3f}s RGB={frame['rgb'].shape} depth_valid={valid.mean():.1%}",flush=True)
            last_print=time.monotonic()
        time.sleep(.005)
except KeyboardInterrupt:pass
