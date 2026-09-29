from launch import LaunchDescription
from launch.actions import OpaqueFunction


def unavailable(context):
    raise RuntimeError('all bringup은 후속 구현 대상입니다. 현재 scout의 경로 점검만 지원합니다.')


def generate_launch_description():
    return LaunchDescription([OpaqueFunction(function=unavailable)])
