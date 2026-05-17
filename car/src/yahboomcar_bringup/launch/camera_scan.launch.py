"""
camera_scan.launch.py — 双目深度相机 + 点云转 LaserScan 管线

启动：
1. hobot_stereonet（双目深度算法）→ /StereoNetNode/stereonet_pointcloud2
2. pointcloud_to_laserscan → /scan

适用场景：嵌入式和 PC 端复用。
- 嵌入式：为 Nav2 AMCL 提供 /scan
- PC：为 slam_toolbox 提供 /scan（或直接订阅嵌入式发布的 /scan）

注意：
- 启动前需确保已有 ros 环境 source
- stereo_frame_id 需与 URDF 中 camera link 名一致（camera_Link）
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # === 相机参数 ===
    stereo_frame_id_arg = DeclareLaunchArgument(
        'stereo_frame_id', default_value='camera_Link',
        description='双目点云的 TF frame_id'
    )
    pointcloud_topic_arg = DeclareLaunchArgument(
        'pointcloud_topic', default_value='/StereoNetNode/stereonet_pointcloud2',
        description='输入点云话题'
    )
    scan_topic_arg = DeclareLaunchArgument(
        'scan_topic', default_value='/scan',
        description='输出 LaserScan 话题'
    )
    # 点云裁剪范围（过滤地面和远方噪声）
    min_height_arg = DeclareLaunchArgument(
        'min_height', default_value='0.05',
        description='点云最小高度（过滤地面），单位 m'
    )
    max_height_arg = DeclareLaunchArgument(
        'max_height', default_value='1.5',
        description='点云最大高度，单位 m'
    )
    angle_min_arg = DeclareLaunchArgument(
        'angle_min', default_value='-1.57',
        description='LaserScan 最小角度 (rad)，-90° = -1.57'
    )
    angle_max_arg = DeclareLaunchArgument(
        'angle_max', default_value='1.57',
        description='LaserScan 最大角度 (rad)，+90° = +1.57'
    )
    range_min_arg = DeclareLaunchArgument(
        'range_min', default_value='0.1',
        description='最小测距距离 (m)'
    )
    range_max_arg = DeclareLaunchArgument(
        'range_max', default_value='5.0',
        description='最大测距距离 (m)'
    )

    # === pointcloud_to_laserscan 节点 ===
    pointcloud_to_laserscan_node = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        remappings=[
            ('cloud_in', LaunchConfiguration('pointcloud_topic')),
            ('scan', LaunchConfiguration('scan_topic')),
        ],
        parameters=[{
            'target_frame': LaunchConfiguration('stereo_frame_id'),
            'transform_tolerance': 0.01,
            'min_height': LaunchConfiguration('min_height'),
            'max_height': LaunchConfiguration('max_height'),
            'angle_min': LaunchConfiguration('angle_min'),
            'angle_max': LaunchConfiguration('angle_max'),
            'angle_increment': LaunchConfiguration('angle_increment', default='0.0087'),  # ~0.5°
            'scan_time': 0.1,  # 10Hz
            'range_min': LaunchConfiguration('range_min'),
            'range_max': LaunchConfiguration('range_max'),
            'use_inf': True,
            'inf_epsilon': 1.0,
            'concurrency_level': 1,
        }],
    )

    return LaunchDescription([
        stereo_frame_id_arg,
        pointcloud_topic_arg,
        scan_topic_arg,
        min_height_arg,
        max_height_arg,
        angle_min_arg,
        angle_max_arg,
        range_min_arg,
        range_max_arg,
        pointcloud_to_laserscan_node,
    ])
