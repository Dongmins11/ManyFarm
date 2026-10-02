"""기존 import 경로 호환. 실제 공통 구현은 farm_navigation에 있습니다."""
from farm_navigation.route import (
    load_route
)

__all__ = ['load_route']
