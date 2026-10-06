"""시뮬 launch에서 현재 활성화된 비전 Python 환경을 선택합니다."""
import os
from pathlib import Path
import sys


def default_vision_python() -> str:
    """명시적 환경변수, 활성 venv, launch Python 순서. venv 심볼릭 링크를 유지합니다."""
    explicit = os.environ.get('FARM_VISION_PYTHON', '').strip()
    if explicit:
        return str(Path(explicit).expanduser().absolute())
    virtual_env = os.environ.get('VIRTUAL_ENV', '').strip()
    if virtual_env:
        python = Path(virtual_env).expanduser() / 'bin/python'
        if not python.is_file() or not os.access(python, os.X_OK):
            raise RuntimeError(f'활성 venv의 Python을 찾을 수 없습니다: {python}')
        return str(python.absolute())
    return sys.executable
