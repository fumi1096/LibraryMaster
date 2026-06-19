"""
laserscan.launch.py — 点云 → LaserScan 转换（单节点合并版）

数据流:
  hobot_stereonet → scan_publisher (旋转+时间戳+投影) → /scan

合并了原来的 pointcloud_republisher + pointcloud_to_laserscan 两个节点，
消除中间 1.7MB 点云话题的 DDS 传输，大幅降低延迟。

用法:
  ros2 launch mycar_driver laserscan.launch.py
  ros2 launch mycar_driver laserscan.launch.py angle_increment:=0.0174 max_height:=1.5
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    stereo_frame_id_arg = DeclareLaunchArgument(
        'stereo_frame_id', default_value='base_footprint',
        description='LaserScan 输出的 TF frame_id')

    scan_topic_arg = DeclareLaunchArgument(
        'scan_topic', default_value='/scan',
        description='输出 LaserScan 话题')

    min_height_arg = DeclareLaunchArgument(
        'min_height', default_value='0.05',
        description='点云最小高度（过滤地面），单位 m')

    max_height_arg = DeclareLaunchArgument(
        'max_height', default_value='0.8',
        description='点云最大高度，单位 m')

    angle_min_arg = DeclareLaunchArgument(
        'angle_min', default_value='-1.57',
        description='LaserScan 最小角度 (rad)')

    angle_max_arg = DeclareLaunchArgument(
        'angle_max', default_value='1.57',
        description='LaserScan 最大角度 (rad)')

    angle_increment_arg = DeclareLaunchArgument(
        'angle_increment', default_value='0.0174',
        description='角分辨率 (rad)')

    range_min_arg = DeclareLaunchArgument(
        'range_min', default_value='0.1',
        description='最小测距距离 (m)')

    range_max_arg = DeclareLaunchArgument(
        'range_max', default_value='5.0',
        description='最大测距距离 (m)')

    scan_time_arg = DeclareLaunchArgument(
        'scan_time', default_value='0.1',
        description='扫描周期 (s)')

    # === 合并节点：旋转 + 时间戳修正 + 投影 → /scan ===
    scan_publisher_node = Node(
        package='mycar_driver',
        executable='scan_fixer',
        name='scan_publisher',
        output='screen',
        parameters=[{
            'target_frame': LaunchConfiguration('stereo_frame_id'),
            'min_height': LaunchConfiguration('min_height'),
            'max_height': LaunchConfiguration('max_height'),
            'angle_min': LaunchConfiguration('angle_min'),
            'angle_max': LaunchConfiguration('angle_max'),
            'angle_increment': LaunchConfiguration('angle_increment'),
            'range_min': LaunchConfiguration('range_min'),
            'range_max': LaunchConfiguration('range_max'),
            'scan_time': LaunchConfiguration('scan_time'),
        }],
    )

    return LaunchDescription([
        stereo_frame_id_arg,
        scan_topic_arg,
        min_height_arg,
        max_height_arg,
        angle_min_arg,
        angle_max_arg,
        angle_increment_arg,
        range_min_arg,
        range_max_arg,
        scan_time_arg,
        scan_publisher_node,
    ])
