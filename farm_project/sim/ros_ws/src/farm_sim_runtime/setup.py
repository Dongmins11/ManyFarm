from glob import glob
from setuptools import find_packages, setup

package_name = 'farm_sim_runtime'
setup(
    name=package_name, version='0.5.6', packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Farm Team', maintainer_email='maintainer@example.com',
    description='Farm integration scaffold', license='Proprietary',
    entry_points={'console_scripts': []},
)
