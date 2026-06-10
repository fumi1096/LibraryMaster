"""
laserscan.launch.py — 点云 → LaserScan 转换

包含两个节点:
1. pc_republish: 修正 hobot_stereonet 点云时间戳（相机时钟→ROS时钟）
2. pointcloud_to_laserscan: 点云→LaserScan

用法:
  ros2 launch mycar_driver laserscan.launch.py
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
        description='输出 LaserScan 话题名')

    # 点云时间戳修正节点（相机时间 → ROS 时间）
    pc_republish_node = Node(
        package='mycar_driver',
        executable='pc_republish',
        name='pointcloud_republisher',
    )

    # 点云 → LaserScan 转换节点
    pointcloud_to_laserscan_node = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        remappings=[
            ('cloud_in', '/pointcloud_republisher/pointcloud_fixed'),
            ('scan', LaunchConfiguration('scan_topic')),
        ],
        parameters=[{
            'target_frame': LaunchConfiguration('stereo_frame_id'),
            'transform_tolerance': 1.0,
            'min_height': 0.05,
            'max_height': 1.5,
            'angle_min': -1.57,
            'angle_max': 1.57,
            'angle_increment': 0.0174,   # 1° (降分辨率减轻SLAM负载)
            'scan_time': 0.5,            # 2Hz (嵌入式算力有限)
            'range_min': 0.1,
            'range_max': 5.0,
            'use_inf': True,
            'inf_epsilon': 1.0,
            'concurrency_level': 1,
        }],
    )

    return LaunchDescription([
        stereo_frame_id_arg,
        scan_topic_arg,
        pc_republish_node,
        pointcloud_to_laserscan_node,
    ])
