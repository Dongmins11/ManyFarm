#!/usr/bin/env python3
"""기존 명령 호환용 진입점. 시뮬 영상 실행 설정은 sim/tools에서 관리합니다."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    runpy.run_path(str(root / 'sim/tools/run_scout_vision.py'), run_name='__main__')
