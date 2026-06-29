"""
mycar_driver 驱动节点启动文件

启动节点:
  - driver_node  四驱驱动节点（串口通信 + 传感器 + 运动控制）
  - odom_node    里程计节点（速度积分）

用法:
  ros2 launch mycar_driver driver.launch.py
  ros2 launch mycar_driver driver.launch.py serial_port:=/dev/ttyUSB1
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_driver')
    default_params = os.path.join(pkg_dir, 'config', 'driver_params.yaml')

    # === 参数 ===
    serial_port_arg = DeclareLaunchArgument(
        'serial_port', default_value='/dev/ttyUSB0',
        description='串口设备路径')

    params_file_arg = DeclareLaunchArgument(
        'params_file', default_value=default_params,
        description='驱动参数文件路径')

    # === 驱动节点 ===
    driver_node = Node(
        package='mycar_driver',
        executable='driver_node',
        name='driver_node',
        output='screen',
        parameters=[LaunchConfiguration('params_file'), {
            'serial_port': LaunchConfiguration('serial_port'),
        }],
    )

    # === 里程计节点 ===
    odom_node = Node(
        package='mycar_driver',
        executable='odom_node',
        name='odom_node',
        output='screen',
        parameters=[{
            'odom_frame': 'odom',
            'base_frame': 'base_footprint',
            'pub_odom_tf': True,
            'linear_scale': 1.0408,
            'angular_scale': 1.0421,
        }],
    )

    return LaunchDescription([
        serial_port_arg,
        params_file_arg,
        driver_node,
        odom_node,
    ])
