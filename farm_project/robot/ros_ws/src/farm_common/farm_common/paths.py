"""설정은 ROS 패키지 위치에서, 큰 자산은 명시한 assets_root에서 찾습니다."""
from pathlib import Path


def package_file(package, relative):
    from ament_index_python.packages import get_package_share_directory
    return required_file(Path(get_package_share_directory(package)) / relative)


def required_file(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'필요한 파일이 없습니다: {path}')
    return path


def asset_file(root, relative):
    root = Path(root).expanduser().resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('자산 경로는 assets_root 내부여야 합니다.')
    return required_file(path)
