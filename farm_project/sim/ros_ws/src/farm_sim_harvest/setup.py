from setuptools import find_packages, setup
setup(name='farm_sim_harvest', version='0.1.0', packages=find_packages(),
      data_files=[('share/ament_index/resource_index/packages', ['resource/farm_sim_harvest']),
                  ('share/farm_sim_harvest', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      maintainer='Farm Team', maintainer_email='maintainer@example.com', license='Proprietary',
      description='수확 작업 종료 이벤트 기반 시뮬 전용 과실 평가',
      entry_points={'console_scripts': ['harvest_audit = farm_sim_harvest.audit_node:main']})
