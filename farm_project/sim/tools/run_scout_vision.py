#!/usr/bin/env python3
"""시뮬 RGB-D 영상 실행. 공통 비전 구현을 시뮬 전용 설정으로 호출합니다."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    """YOLO/PyTorch 환경에서 실행하며 기존 비전 CLI 인자를 그대로 전달합니다."""
    for package in ('farm_common', 'farm_vision'):
        sys.path.insert(0, str(ROOT / 'robot/ros_ws/src' / package))
    try:
        from farm_vision.live import main as run_vision
        args = sys.argv[1:]
        if not any(arg == '--config' or arg.startswith('--config=') for arg in args):
            config = ROOT / 'sim/ros_ws/src/farm_sim_config/config/scout_vision.json'
            args = ['--config', str(config), *args]
        run_vision(args, project_root=ROOT)
    except ImportError as error:
        raise SystemExit(f'추론 환경의 의존성을 확인하세요: {error}. sim/README.md 참고.')
    except (ValueError, RuntimeError, FileNotFoundError) as error:
        raise SystemExit(f'비전 실행 실패: {error}')


if __name__ == '__main__':
    main()
