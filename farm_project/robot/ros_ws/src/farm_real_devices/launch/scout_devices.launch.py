from launch import LaunchDescription
from launch.actions import OpaqueFunction


def unavailable(context):
    raise RuntimeError('실물 연결부는 비워두었습니다. farm_real_devices를 담당자가 구현해야 합니다.')


def generate_launch_description():
    return LaunchDescription([OpaqueFunction(function=unavailable)])
