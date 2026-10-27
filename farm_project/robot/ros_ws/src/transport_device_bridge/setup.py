from glob import glob
from setuptools import setup

package_name = 'transport_device_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='채윤식',
    maintainer_email='micoleb3@gmail.com',
    description='운송로봇 바구니 기구 UART ↔ ROS 2 서비스 브리지',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'device_bridge = transport_device_bridge.device_bridge:main',
        ],
    },
)
