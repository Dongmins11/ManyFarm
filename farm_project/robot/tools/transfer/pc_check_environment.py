"""PC 검사 래퍼의 환경만 검증한다. 운영 실행·설정 변경은 하지 않는다."""
import os
from pathlib import Path
import sys


def validate(root: Path) -> None:
    downloads=(Path.home()/'Downloads').resolve()
    if not root.resolve().is_relative_to(downloads):
        raise RuntimeError('PC 후보는 Downloads 내부여야 합니다.')
    expected={'HARVEST_PC_CHECK':'1','ROS_DOMAIN_ID':'95','ROS_LOCALHOST_ONLY':'1',
              'RMW_IMPLEMENTATION':'rmw_fastrtps_cpp'}
    if any(os.environ.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('명시 PC 격리 환경 불일치')
    from ament_index_python.packages import get_package_prefix
    for package in ('farm_arc_controller','farm_nav2_controller','farm_wall_controller'):
        actual=Path(get_package_prefix(package)).resolve()
        if not actual.is_relative_to(downloads):
            raise RuntimeError('독립 PC 설치본 아님: '+package)
    import farm_navigation, harvest_robot
    for module,package in ((farm_navigation,'farm_navigation'),(harvest_robot,'harvest_robot')):
        expected_path=root/'robot/ros_ws/src'/package/package/'__init__.py'
        if Path(module.__file__).resolve()!=expected_path.resolve():
            raise RuntimeError('검사 후보 Python 모듈 불일치: '+package)


if __name__=='__main__':validate(Path(sys.argv[1]))
