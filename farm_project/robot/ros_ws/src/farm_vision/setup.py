from setuptools import setup, find_packages
setup(name='farm_vision', version='0.4.0', packages=find_packages(),
    data_files=[('share/ament_index/resource_index/packages',['resource/farm_vision']),
                ('share/farm_vision',['package.xml'])],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Farm Team', maintainer_email='maintainer@example.com',
    description='Shared B observation preprocessing and YOLO segmentation', license='Proprietary')
