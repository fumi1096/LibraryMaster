"""
calibrate.launch.py — 里程计标定后台启动文件

仅启动 driver + odom（不含标定节点）。
标定节点需要交互式 stdin，必须通过 ros2 run 在前台运行。

用法（配合 calibrate_odom.sh 一键启动）:
  ./calibrate_odom.sh
  ./calibrate_odom.sh /dev/ttyUSB1
"""
import os
import re
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_driver')
    default_params = os.path.join(pkg_dir, 'config', 'driver_params.yaml')

    # 从 driver.launch.py 读取当前 scale 值（保证 odom_node 使用最新标定结果）
    current_linear = 1.0
    current_angular = 1.0
    try:
        launch_path = os.path.join(pkg_dir, 'launch', 'driver.launch.py')
        with open(launch_path, 'r') as f:
            content = f.read()
        m = re.search(r"'linear_scale':\s*([\d.]+)", content)
        if m:
            current_linear = float(m.group(1))
        m = re.search(r"'angular_scale':\s*([\d.]+)", content)
        if m:
            current_angular = float(m.group(1))
    except Exception:
        pass

    # === 参数 ===
    serial_port_arg = DeclareLaunchArgument(
        'serial_port', default_value='/dev/ttyUSB0',
        description='串口设备路径')

    # === 驱动节点 ===
    driver_node = Node(
        package='mycar_driver',
        executable='driver_node',
        name='driver_node',
        output='screen',
        parameters=[default_params, {
            'serial_port': LaunchConfiguration('serial_port'),
        }],
    )

    # === 里程计节点（使用当前 scale） ===
    odom_node = Node(
        package='mycar_driver',
        executable='odom_node',
        name='odom_node',
        output='screen',
        parameters=[{
            'odom_frame': 'odom',
            'base_frame': 'base_footprint',
            'pub_odom_tf': True,
            'linear_scale': current_linear,
            'angular_scale': current_angular,
        }],
    )

    return LaunchDescription([
        serial_port_arg,
        driver_node,
        odom_node,
    ])
