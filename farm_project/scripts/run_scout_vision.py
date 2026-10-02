#!/usr/bin/env python3
"""Run in the YOLO/PyTorch environment; ROS Python is not required."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
for package in ('farm_common','farm_vision'):
    sys.path.insert(0,str(ROOT/'robot/ros_ws/src'/package))
if __name__ == '__main__':
    try:
        from farm_vision.live import main
        args=sys.argv[1:]
        if not any(a == '--config' or a.startswith('--config=') for a in args):
            args=['--config',str(ROOT/'robot/config/vision/scout.json'),*args]
        main(args,project_root=ROOT)
    except ImportError as error:
        raise SystemExit(f'추론 환경의 의존성을 확인하세요: {error}. docs/vision_stage.md 참고.')
    except (ValueError,RuntimeError,FileNotFoundError) as error:
        raise SystemExit(f'비전 실행 실패: {error}')
