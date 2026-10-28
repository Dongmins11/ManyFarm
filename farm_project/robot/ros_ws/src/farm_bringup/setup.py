from glob import glob
from setuptools import find_packages, setup

package_name = 'farm_bringup'
setup(
    name=package_name, version='0.3.0', packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Farm Team', maintainer_email='maintainer@example.com',
    description='Farm integration scaffold', license='Proprietary',
    entry_points={'console_scripts': ['scout_navigation_start = farm_bringup.scout_navigation_start:main']},
)
