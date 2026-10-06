from setuptools import find_packages, setup
setup(name='harvest_robot', version='0.1.0', packages=find_packages(),
      data_files=[('share/ament_index/resource_index/packages', ['resource/harvest_robot']),
                  ('share/harvest_robot', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      maintainer='Farm Team', maintainer_email='maintainer@example.com', license='Proprietary',
      description='sim/real 공통 수확 Action 서버',
      entry_points={'console_scripts': ['harvest_node = harvest_robot.node:main']})
