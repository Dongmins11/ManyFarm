from setuptools import find_packages, setup
setup(name='transport_robot', version='0.1.0', packages=find_packages(),
 data_files=[('share/ament_index/resource_index/packages',['resource/transport_robot']),
 ('share/transport_robot',['package.xml'])], install_requires=['setuptools'],
 maintainer='Farm Team',maintainer_email='maintainer@example.com',license='Proprietary',
 description='공통 주행을 사용하는 운송 FSM과 단계별 주행 검증',
 entry_points={'console_scripts':['transport_node = transport_robot.transport_node:main',
 'transport_route = transport_robot.route_cli:main']})
