from glob import glob
from setuptools import find_packages, setup

package_name = 'farm_sim_devices'
setup(
    name=package_name, version='0.2.0', packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Farm Team', maintainer_email='maintainer@example.com',
    description='Farm integration scaffold', license='Proprietary',
    entry_points={'console_scripts': ['ros_adapter = farm_sim_devices.ros_adapter:main']},
)
