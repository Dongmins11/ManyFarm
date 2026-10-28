from glob import glob
from pathlib import Path

description_files = {}
for source in Path("description").rglob("*"):
    if source.is_file():
        destination = "share/farm_real_devices/" + str(source.parent)
        description_files.setdefault(destination, []).append(str(source))
from setuptools import find_packages, setup

package_name = 'farm_real_devices'
setup(
    name=package_name, version='0.1.0', packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*')),
        *description_files.items(),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Farm Team', maintainer_email='maintainer@example.com',
    description='Farm integration scaffold', license='Proprietary',
    entry_points={'console_scripts': []},
)
