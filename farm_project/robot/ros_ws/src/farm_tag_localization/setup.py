from setuptools import setup, find_packages
setup(name='farm_tag_localization', version='0.1.0', packages=find_packages(),
 data_files=[('share/ament_index/resource_index/packages',['resource/farm_tag_localization']),('share/farm_tag_localization',['package.xml','README.md','PROVENANCE.json'])],
 install_requires=['setuptools'], zip_safe=True, maintainer='Farm Team', maintainer_email='maintainer@example.com', description='태그 관측을 AMCL에 연결하는 독립 보정 노드', license='Proprietary',
 entry_points={'console_scripts':['tag_amcl_adapter = farm_tag_localization.node:main', 'tag_capture_session = farm_tag_localization.capture_session:main', 'tag_capture = farm_tag_localization.ros_capture:main']})

