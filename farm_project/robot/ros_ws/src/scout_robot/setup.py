from glob import glob
from setuptools import setup, find_packages
setup(name='scout_robot', version='0.5.5', packages=find_packages(),
    data_files=[('share/ament_index/resource_index/packages', ['resource/scout_robot']),
                ('share/scout_robot', ['package.xml']),
                ('share/scout_robot/config', glob('config/*'))],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Farm Team', maintainer_email='maintainer@example.com',
    description='Common scout route preview and explicit navigation client', license='Proprietary',
    entry_points={'console_scripts': ['route_preview = scout_robot.route_preview:main',
                                     'drive_route = scout_robot.drive_route:main',
                                     'survey_server = scout_robot.survey_server:main']})
