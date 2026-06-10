"""
rtabmap_mapping_pc.launch.py — RTAB-Map 3D 分布式建图 (PC 端)

管线 (小车端已完成):
  stereonet → voxel_filter → /scan_cloud

PC 端:
  /scan_cloud → rtabmap (scan-to-scan ICP 3D SLAM)
              ← /odom (EKF 融合里程计, 从小车端订阅)

输出:
  /rtabmap/cloud_map    — 3D 点云地图
  /rtabmap/grid_map     — 2D 占据栅格地图
  /rtabmap/mapGraph     — 位姿图

用法:
  ros2 launch mycar_rtabmap rtabmap_mapping_pc.launch.py
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
    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        choices=['true', 'false'],
        description='启动 RViz2 可视化')

    # === RTAB-Map 节点（YAML 传参，纯 scan-cloud ICP 模式） ===
    rtabmap_config = os.path.join(
        get_package_share_directory('mycar_rtabmap'), 'config', 'rtabmap.yaml')
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=[rtabmap_config],
    )

    # === RViz2（预配置: MapCloud + MapGraph + Grid + TF + RobotModel） ===
    rviz_config = os.path.join(pkg_dir, 'config', 'rtabmap_mapping.rviz')

    from launch.conditions import IfCondition
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    return LaunchDescription([
        use_rviz_arg,
        rtabmap_node,
        rviz_node,
    ])
