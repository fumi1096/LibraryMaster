from setuptools import setup
import os
from glob import glob

package_name = 'mycar_rtabmap'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*.launch.py'))),
        (os.path.join('share', package_name, 'config'),
            glob(os.path.join('config', '*.yaml')) +
            glob(os.path.join('config', '*.rviz'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='user',
    maintainer_email='user@todo.com',
    description='mycar RTAB-Map 3D mapping',
    license='BSD',
    entry_points={
        'console_scripts': [
            'keyboard_control = mycar_rtabmap.keyboard_control:main',
            'image_relay = mycar_rtabmap.image_relay:main',
        ],
    },
)
