from glob import glob
from pathlib import Path
from setuptools import find_packages, setup

package_name = 'farm_sim_config'
setup(
    name=package_name, version='0.5.4', packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/maps', glob('maps/*')),
        ('share/' + package_name + '/config', [p for p in glob('config/*') if Path(p).is_file()]),
        ('share/' + package_name + '/config/tag_localization', glob('config/tag_localization/*')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Farm Team', maintainer_email='maintainer@example.com',
    description='Farm integration scaffold', license='Proprietary',
    entry_points={'console_scripts': []},
)
