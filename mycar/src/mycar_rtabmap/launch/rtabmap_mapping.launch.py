"""
rtabmap_mapping.launch.py — RTAB-Map 3D 建图

管线:
  stereonet → voxel_filter (下采样 0.05m) → rtabmap (3D SLAM)
                                          ← /odom (EKF 融合里程计)

输出:
  /rtabmap/cloud_map    — 3D 点云地图
  /rtabmap/grid_map     — 2D 占据栅格地图
  /rtabmap/mapGraph     — 位姿图

用法:
  ros2 launch mycar_rtabmap rtabmap_mapping.launch.py
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_rtabmap')

    # === 参数 ===
    voxel_size_arg = DeclareLaunchArgument(
        'voxel_size', default_value='0.05',
        description='体素下采样尺寸 (m)')

    # === 体素下采样节点 ===
    voxel_node = Node(
        package='mycar_rtabmap',
        executable='voxel_filter',
        name='voxel_filter',
        parameters=[{'voxel_size': LaunchConfiguration('voxel_size')}],
    )

    # === RTAB-Map 节点（YAML 传参） ===
    rtabmap_config = os.path.join(
        get_package_share_directory('mycar_rtabmap'), 'config', 'rtabmap.yaml')
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=[rtabmap_config],
    )

    # === RViz2（预配置） ===
    rviz_config = os.path.join(pkg_dir, 'config', 'rtabmap_mapping.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
    )

    return LaunchDescription([
        voxel_size_arg,
        voxel_node,
        rtabmap_node,
        rviz_node,
    ])
