from setuptools import setup
import os
from glob import glob

package_name = 'mycar_driver'

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
            glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='user',
    maintainer_email='user@todo.com',
    description='mycar driver package — serial bridge, sensors, motion, odometry',
    license='BSD',
    entry_points={
        'console_scripts': [
            'driver_node = mycar_driver.driver_node:main',
            'odom_node = mycar_driver.odom_node:main',
            'test_motion = mycar_driver.test_motion:main',
            'keyboard_control = mycar_driver.keyboard_control:main',
            'pc_republish = mycar_driver.pointcloud_republisher:main',
            'image_republish = mycar_driver.image_republisher:main',
            'scan_fixer = mycar_driver.scan_publisher:main',
            'odom_delay = mycar_driver.odom_delay:main',
            'calibrate_odom = mycar_driver.calibrate_odom:main',
            'verify_odom = mycar_driver.verify_odom:main',
        ],
    },
)
