from setuptools import find_packages, setup
setup(name='farm_docking', version='0.1.0', packages=find_packages(),
 data_files=[('share/ament_index/resource_index/packages',['resource/farm_docking']),('share/farm_docking',['package.xml'])],
 install_requires=['setuptools'], maintainer='Farm Team', maintainer_email='maintainer@example.com', license='Proprietary',
 description='공통 정밀주행 전략 및 속도 소유권', entry_points={'console_scripts':[
 'precision_server = farm_docking.precision_server:main', 'motion_gate = farm_docking.motion_gate:main']})
