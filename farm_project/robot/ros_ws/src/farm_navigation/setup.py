from setuptools import setup, find_packages
setup(name='farm_navigation', version='0.1.0', packages=find_packages(),
      data_files=[('share/ament_index/resource_index/packages',['resource/farm_navigation']),
                  ('share/farm_navigation',['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      maintainer='Farm Team', maintainer_email='maintainer@example.com',
      description='Shared graph routing and ROS navigation adapters', license='Proprietary')
