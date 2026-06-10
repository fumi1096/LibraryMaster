"""
slam.launch.py — mycar_f 在线异步建图

启动:
  - slam_toolbox (online_async) → /map
  - RViz2 (显示 /map + /scan + RobotModel + TF)

输入依赖 (由 bringup 提供):
  - /scan (LaserScan)
  - /odom (EKF 融合里程计)
  - TF 树 (URDF + odom→base_footprint)

用法:
  ros2 launch mycar_slam slam.launch.py

建图完成后保存地图:
  ros2 run nav2_map_server map_saver_cli -f ~/mycar_map
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('mycar_slam')
    slam_config = os.path.join(pkg_dir, 'config', 'slam_toolbox_mapping.yaml')

    # === 参数 ===
    slam_params_arg = DeclareLaunchArgument(
        'slam_params_file', default_value=slam_config,
        description='slam_toolbox 参数文件路径')

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='使用仿真时间 (Gazebo)')

    # === slam_toolbox (online async) ===
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            LaunchConfiguration('slam_params_file'),
            {'use_sim_time': LaunchConfiguration('use_sim_time')},
        ],
    )

    # === RViz2 (预配置: Map + LaserScan + TF + RobotModel, Fixed Frame=map) ===
    rviz_config = os.path.join(pkg_dir, 'config', 'slam_mapping.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
    )

    return LaunchDescription([
        slam_params_arg,
        use_sim_time_arg,
        slam_toolbox_node,
        rviz_node,
    ])
