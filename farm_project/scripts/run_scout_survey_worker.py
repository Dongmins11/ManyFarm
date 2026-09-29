#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
for package in ('farm_common','farm_vision'):
    sys.path.insert(0,str(ROOT/'robot/ros_ws/src'/package))
if __name__=='__main__':
    from farm_vision.survey_worker import main
    main(ROOT)
